"""
LLM 调用监控回调处理器

自动记录所有 LLM 调用的 token 使用量和成本。
"""
import logging
import time
from typing import Any, Dict, Optional
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("LLMMonitorCallback")


class LLMMonitorCallback(BaseCallbackHandler):
    """
    LLM 调用监控回调处理器

    功能：
    1. 记录 LLM 调用时间
    2. 提取 token 使用量
    3. 计算并记录成本
    4. 监控调用性能
    """

    def __init__(self):
        super().__init__()
        self._monitor = None
        self._start_times: Dict[str, float] = {}
        self._current_model: Dict[str, str] = {}
        self._call_context: Dict[str, Dict] = {}

    @property
    def monitor(self):
        """延迟获取监控器"""
        if self._monitor is None:
            try:
                from src.observability.api_monitor import get_api_monitor
                self._monitor = get_api_monitor()
            except Exception as e:
                logger.warning(f"无法获取 API 监控器: {e}")
        return self._monitor

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: list,
        **kwargs
    ) -> None:
        """LLM 调用开始时记录"""
        run_id = str(kwargs.get("run_id", id(prompts)))
        self._start_times[run_id] = time.time()

        # 提取模型名称
        invocation_params = kwargs.get("invocation_params", {})
        model = invocation_params.get("model", invocation_params.get("model_name", "unknown"))
        self._current_model[run_id] = model

        # 记录上下文
        self._call_context[run_id] = {
            "prompts_count": len(prompts),
            "prompts_length": sum(len(p) for p in prompts) if prompts else 0
        }

        logger.debug(f"LLM 调用开始: model={model}, run_id={run_id}")

    def on_llm_end(
        self,
        response: Any,
        **kwargs
    ) -> None:
        """LLM 调用结束时记录"""
        run_id = str(kwargs.get("run_id", ""))

        # 计算耗时
        start_time = self._start_times.pop(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        # 获取模型名称
        model = self._current_model.pop(run_id, "unknown")
        context = self._call_context.pop(run_id, {})

        # 提取 token 使用量
        token_usage = self._extract_token_usage(response)

        if token_usage and self.monitor:
            try:
                cost = self.monitor.record_api_call(
                    provider='dashscope',
                    model=model,
                    endpoint='chat',
                    input_tokens=token_usage.get('input_tokens', 0),
                    output_tokens=token_usage.get('output_tokens', 0),
                    total_tokens=token_usage.get('total_tokens', 0)
                )

                logger.info(
                    f"LLM 调用完成: model={model}, "
                    f"tokens={token_usage.get('total_tokens', 0)}, "
                    f"cost={cost:.6f}元, duration={duration_ms:.0f}ms"
                )
            except Exception as e:
                logger.error(f"记录 LLM 调用失败: {e}")
        else:
            logger.debug(
                f"LLM 调用完成: model={model}, "
                f"duration={duration_ms:.0f}ms (无token信息或监控器不可用)"
            )

        # 清理
        self._start_times.pop(run_id, None)
        self._current_model.pop(run_id, None)
        self._call_context.pop(run_id, None)

    def on_llm_error(
        self,
        error: Exception,
        **kwargs
    ) -> None:
        """LLM 调用错误时记录"""
        run_id = str(kwargs.get("run_id", ""))
        model = self._current_model.get(run_id, "unknown")
        start_time = self._start_times.get(run_id, time.time())
        duration_ms = (time.time() - start_time) * 1000

        logger.error(
            f"LLM 调用失败: model={model}, "
            f"error={type(error).__name__}: {error}, "
            f"duration={duration_ms:.0f}ms"
        )

        # 清理
        self._start_times.pop(run_id, None)
        self._current_model.pop(run_id, None)
        self._call_context.pop(run_id, None)

    def _extract_token_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """
        从响应中提取 token 使用量

        支持多种响应格式：
        - LangChain 标准格式 (usage_metadata)
        - 通义千问格式 (response_metadata.token_usage)
        - 原始字典格式
        """
        try:
            # LangChain 标准格式
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                meta = response.usage_metadata
                return {
                    'input_tokens': meta.get('input_tokens', meta.get('prompt_tokens', 0)),
                    'output_tokens': meta.get('output_tokens', meta.get('completion_tokens', 0)),
                    'total_tokens': meta.get('total_tokens', 0)
                }

            # 通义千问格式
            if hasattr(response, 'response_metadata') and response.response_metadata:
                meta = response.response_metadata
                if 'token_usage' in meta:
                    usage = meta['token_usage']
                    return {
                        'input_tokens': usage.get('input_tokens', usage.get('prompt_tokens', 0)),
                        'output_tokens': usage.get('output_tokens', usage.get('completion_tokens', 0)),
                        'total_tokens': usage.get('total_tokens', 0)
                    }
                # 某些版本直接在 response_metadata 中
                if 'input_tokens' in meta or 'prompt_tokens' in meta:
                    return {
                        'input_tokens': meta.get('input_tokens', meta.get('prompt_tokens', 0)),
                        'output_tokens': meta.get('output_tokens', meta.get('completion_tokens', 0)),
                        'total_tokens': meta.get('total_tokens', 0)
                    }

            # 生成结果对象 (AIMessage)
            if hasattr(response, 'generations'):
                # 某些包装格式
                for gen in response.generations:
                    if hasattr(gen, 'message') and hasattr(gen.message, 'response_metadata'):
                        meta = gen.message.response_metadata
                        if 'token_usage' in meta:
                            usage = meta['token_usage']
                            return {
                                'input_tokens': usage.get('input_tokens', 0),
                                'output_tokens': usage.get('output_tokens', 0),
                                'total_tokens': usage.get('total_tokens', 0)
                            }

            # 原始字典格式
            if isinstance(response, dict):
                usage = response.get('usage', response.get('token_usage', {}))
                if usage:
                    return {
                        'input_tokens': usage.get('prompt_tokens', usage.get('input_tokens', 0)),
                        'output_tokens': usage.get('completion_tokens', usage.get('output_tokens', 0)),
                        'total_tokens': usage.get('total_tokens', 0)
                    }

            return None

        except Exception as e:
            logger.warning(f"提取 token 使用量失败: {e}")
            return None


# 全局回调实例
_llm_callback: Optional[LLMMonitorCallback] = None


def get_llm_monitor_callback() -> LLMMonitorCallback:
    """获取全局 LLM 监控回调"""
    global _llm_callback
    if _llm_callback is None:
        _llm_callback = LLMMonitorCallback()
    return _llm_callback
