"""
LLM 工厂模块

提供统一的 LLM 初始化接口，避免在多个文件中重复 ChatOpenAI 初始化代码

[v1.0.1] 新增 API 监控回调支持，自动记录 token 使用和成本
"""
from typing import Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler

from src import config


def create_dashscope_llm(
    model_name: str = None,
    temperature: float = 0.1,
    max_tokens: int = None,
    timeout: int = None,
    callbacks: Optional[List[BaseCallbackHandler]] = None,
    enable_monitoring: bool = True
) -> ChatOpenAI:
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

    Returns:
        ChatOpenAI: 配置好的 LLM 实例

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

    # 添加 API 监控回调（v1.0.1）
    if enable_monitoring:
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
