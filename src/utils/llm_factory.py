"""
LLM 工厂模块

提供统一的 LLM 初始化接口，避免在多个文件中重复 ChatOpenAI 初始化代码

[v1.0.1] 新增 API 监控回调支持，自动记录 token 使用和成本
[v0.7.1] 新增熔断器支持，防止级联故障
"""
from typing import Optional, List, Any
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from src import config

# 导入熔断器（可选）
try:
    from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, get_circuit_breaker
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False


class CircuitBreakerLLM(BaseChatModel):
    """
    熔断器包装的 LLM

    为任意 LLM 实例添加熔断器保护，防止级联故障。

    [v0.7.1] 新增
    """

    def __init__(
        self,
        llm: BaseChatModel,
        circuit_breaker: "CircuitBreaker" = None,
        breaker_name: str = "llm_default"
    ):
        """
        初始化熔断器包装的 LLM

        Args:
            llm: 被包装的 LLM 实例
            circuit_breaker: 熔断器实例（可选，不提供则自动创建）
            breaker_name: 熔断器名称
        """
        super().__init__()
        self._llm = llm
        if circuit_breaker:
            self._breaker = circuit_breaker
        elif CIRCUIT_BREAKER_AVAILABLE:
            self._breaker = get_circuit_breaker(breaker_name)
        else:
            self._breaker = None

    @property
    def _llm_type(self) -> str:
        return f"circuit_breaker_{self._llm._llm_type}"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成响应，使用熔断器保护"""
        if self._breaker:
            return self._breaker.call(
                self._llm._generate,
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs
            )
        return self._llm._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    @property
    def _identifying_params(self):
        return self._llm._identifying_params

    def with_structured_output(self, schema, **kwargs):
        """支持结构化输出"""
        return self._llm.with_structured_output(schema, **kwargs)


def wrap_with_circuit_breaker(
    llm: BaseChatModel,
    breaker_name: str = "llm_default",
    failure_threshold: int = 5,
    timeout: int = 60
) -> BaseChatModel:
    """
    为 LLM 实例包装熔断器

    Args:
        llm: 原始 LLM 实例
        breaker_name: 熔断器名称
        failure_threshold: 失败次数阈值
        timeout: 熔断超时（秒）

    Returns:
        包装了熔断器的 LLM 实例
    """
    if not CIRCUIT_BREAKER_AVAILABLE:
        return llm

    breaker = get_circuit_breaker(breaker_name)
    breaker.failure_threshold = failure_threshold
    breaker.timeout = timeout

    return CircuitBreakerLLM(llm, circuit_breaker=breaker)


def create_dashscope_llm(
    model_name: str = None,
    temperature: float = 0.1,
    max_tokens: int = None,
    timeout: int = None,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    enable_monitoring: bool = True,
    enable_circuit_breaker: bool = True,
    breaker_name: str = None
) -> BaseChatModel:
    """
    创建 DashScope 兼容的 LLM 实例

    统一的 LLM 初始化接口，封装了通义千问 API 的配置细节。
    避免在多个文件中重复相同的配置代码。

    Args:
        model_name: 模型名称，默认从 config 获取
        temperature: 温度参数，控制输出随机性（0.0-1.0），默认 0.1
        max_tokens: 最大输出 token 数，默认从 config 获取
        timeout: 请求超时时间（秒），默认从 config 获取
        callbacks: 自定义回调列表
        enable_monitoring: 是否启用 API 监控（默认 True）
        enable_circuit_breaker: 是否启用熔断器保护（默认 True）[v0.7.1]
        breaker_name: 熔断器名称（默认根据模型名自动生成）

    Returns:
        BaseChatModel: 配置好的 LLM 实例（可能包装了熔断器）

    Raises:
        RuntimeError: 当 API_KEY 未配置时

    Example:
        >>> from src.utils.llm_factory import create_dashscope_llm
        >>>
        >>> # 使用默认配置
        >>> llm = create_dashscope_llm()
        >>>
        >>> # 自定义模型和温度
        >>> llm = create_dashscope_llm(model_name="qwen-plus", temperature=0.5)
    """
    if not config.API_KEY:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 环境变量")

    model_name = model_name or config.MODEL_PARSER

    # 准备回调列表
    all_callbacks = callbacks or []

    # 添加 API 监控回调（v1.0.1 -> v1.1.0 升级）
    if enable_monitoring:
        try:
            from src.observability.llm_monitor_callback import get_llm_monitor_callback
            monitor_callback = get_llm_monitor_callback()
            all_callbacks.append(monitor_callback)
        except ImportError:
            # 回退到旧版本导入路径
            try:
                from src.observability.api_monitor_callback import get_api_monitor_callback
                monitor_callback = get_api_monitor_callback()
                all_callbacks.append(monitor_callback)
            except Exception as e:
                logger = __import__('logging').getLogger("LLMFactory")
                logger.warning(f"无法添加 API 监控回调: {e}")

    llm = ChatOpenAI(
        model=model_name,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=config.API_KEY,
        temperature=temperature,
        timeout=timeout or getattr(config, 'LLM_REQUEST_TIMEOUT', 30),
        max_tokens=max_tokens or getattr(config, 'MAX_TOKENS', 2048),
        callbacks=all_callbacks if all_callbacks else None,
    )

    # 熔断器包装 [v0.7.1]
    if enable_circuit_breaker and CIRCUIT_BREAKER_AVAILABLE:
        name = breaker_name or f"llm_{model_name.replace('-', '_')}"
        llm = wrap_with_circuit_breaker(llm, breaker_name=name)

    return llm


def create_parser_llm(temperature: float = 0.5) -> ChatOpenAI:
    """
    创建查询解析专用的 LLM 实例

    Args:
        temperature: 温度参数，默认 0.5

    Returns:
        ChatOpenAI: 配置好的解析器 LLM
    """
    return create_dashscope_llm(
        model_name=config.MODEL_PARSER,
        temperature=temperature
    )


def create_analyzer_llm(temperature: float = 0.1, max_tokens: int = 1024) -> ChatOpenAI:
    """
    创建证据分析专用的 LLM 实例

    Args:
        temperature: 温度参数，默认 0.1
        max_tokens: 最大输出 token 数，默认 1024

    Returns:
        ChatOpenAI: 配置好的分析器 LLM
    """
    return create_dashscope_llm(
        model_name=config.MODEL_ANALYZER,
        temperature=temperature,
        max_tokens=max_tokens
    )


def create_summarizer_llm(temperature: float = 0.1, max_tokens: int = 1024) -> ChatOpenAI:
    """
    创建裁决生成专用的 LLM 实例

    Args:
        temperature: 温度参数，默认 0.1
        max_tokens: 最大输出 token 数，默认 1024

    Returns:
        ChatOpenAI: 配置好的总结器 LLM
    """
    return create_dashscope_llm(
        model_name=config.MODEL_SUMMARIZER,
        temperature=temperature,
        max_tokens=max_tokens
    )
