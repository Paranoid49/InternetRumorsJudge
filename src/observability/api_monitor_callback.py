"""
API 监控回调处理器

通过 LangChain 回调机制自动记录 LLM 调用的 token 使用和成本

版本：v1.0.1
"""
import logging
from typing import Any, Dict, Optional, List
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("APIMonitorCallback")


class APIMonitorCallbackHandler(BaseCallbackHandler):
    """
    API 监控回调处理器

    在 LLM 调用结束时自动提取 token 使用量并记录到 API 监控系统

    功能：
    - 自动提取 input_tokens 和 output_tokens
    - 计算成本
    - 记录到 API 监控器
    - 线程安全
    """

    def __init__(self):
        super().__init__()
        self._monitor = None

    def _get_monitor(self):
        """延迟加载 API 监控器（避免导入循环）"""
        if self._monitor is None:
            try:
                from src.observability.api_monitor import get_api_monitor
                self._monitor = get_api_monitor()
            except Exception as e:
                logger.warning(f"无法获取 API 监控器: {e}")
                self._monitor = False  # 标记为失败，避免重复尝试
        return self._monitor if self._monitor is not False else None

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """
        LLM 调用结束时的回调

        Args:
            response: LLM 响应对象，包含 token 使用信息
            **kwargs: 其他参数
        """
        monitor = self._get_monitor()
        if monitor is None:
            return

        try:
            # 提取 token 使用信息
            llm_output = response.llm_output or {}
            token_usage = llm_output.get('token_usage', {})

            # 兼容不同的 token 字段名
            input_tokens = (
                token_usage.get('prompt_tokens') or
                token_usage.get('input_tokens') or
                token_usage.get('prompt_count') or
                0
            )
            output_tokens = (
                token_usage.get('completion_tokens') or
                token_usage.get('output_tokens') or
                token_usage.get('completion_count') or
                0
            )
            total_tokens = (
                token_usage.get('total_tokens') or
                input_tokens + output_tokens
            )

            # 提取模型名称
            model_name = llm_output.get('model_name', 'unknown')

            # 如果没有 token 信息，尝试从 generations 中估算
            if total_tokens == 0 and response.generations:
                # 估算：假设每个 generation 包含输出 tokens
                # 输入 tokens 无法估算，跳过
                logger.debug("无法从 llm_output 获取 token 信息，尝试估算")
                # 不做估算，因为不准确
                return

            # 记录到 API 监控
            cost = monitor.record_api_call(
                provider='dashscope',
                model=model_name,
                endpoint='chat',
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            logger.debug(
                f"API 调用已记录: {model_name}, "
                f"input={input_tokens}, output={output_tokens}, "
                f"cost={cost:.6f}元"
            )

        except Exception as e:
            logger.error(f"记录 API 调用时出错: {e}")


def get_api_monitor_callback() -> APIMonitorCallbackHandler:
    """
    获取 API 监控回调处理器实例

    Returns:
        APIMonitorCallbackHandler: 回调处理器实例
    """
    return APIMonitorCallbackHandler()


# 便捷导出
__all__ = [
    'APIMonitorCallbackHandler',
    'get_api_monitor_callback'
]
