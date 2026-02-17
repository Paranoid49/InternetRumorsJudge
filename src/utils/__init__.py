"""
工具模块

提供各种工具函数和类
"""

# 错误处理工具
from src.utils.error_handler import (
    handle_errors,
    safe_execute,
    retry_on_exception,
    ErrorContext,
)

# 异步 LLM 工具（可选，依赖 aiohttp）
try:
    from src.utils.async_llm_utils import (
        AsyncLLMWrapper,
        AsyncLLMPool,
        create_async_llm_wrapper,
        run_sync_in_executor,
    )
except ImportError:
    pass

__all__ = [
    # 错误处理
    'handle_errors',
    'safe_execute',
    'retry_on_exception',
    'ErrorContext',
    # 异步工具（可选）
    'AsyncLLMWrapper',
    'AsyncLLMPool',
    'create_async_llm_wrapper',
    'run_sync_in_executor',
]
