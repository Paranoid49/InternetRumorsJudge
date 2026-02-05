"""
统一重试策略

为所有外部调用提供一致的重试机制
"""
import logging
from typing import Callable, Type, Tuple
from functools import wraps

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    # 简单的回退实现
    def retry(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator


logger = logging.getLogger("RetryPolicy")


# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# 网络相关异常（可能来自 httpx, requests）
try:
    import httpx
    RETRYABLE_EXCEPTIONS += (httpx.TimeoutException, httpx.ConnectError)
except ImportError:
    pass


def create_retry_policy(
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 10.0,
    exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS
):
    """
    创建重试装饰器

    Args:
        max_attempts: 最大重试次数
        wait_min: 最小等待时间（秒）
        wait_max: 最大等待时间（秒）
        exceptions: 需要重试的异常类型

    Returns:
        装饰器函数
    """
    if not TENACITY_AVAILABLE:
        # 回退：简单的重试
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_attempts - 1:
                            wait_time = wait_min * (2 ** attempt)
                            logger.warning(f"重试 {attempt + 1}/{max_attempts}: {func.__name__} - {e}")
                            import time
                            time.sleep(min(wait_time, wait_max))
                        else:
                            logger.error(f"重试失败: {func.__name__}")
                raise last_exception
            return wrapper
        return decorator

    # 使用 tenacity
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


# 预定义的重试策略
def with_llm_retry(func):
    """LLM调用重试装饰器"""
    return create_retry_policy(
        max_attempts=3,
        wait_min=2.0,
        wait_max=30.0,
        exceptions=RETRYABLE_EXCEPTIONS + (Exception,)  # LLM可能返回各种错误
    )(func)


def with_web_search_retry(func):
    """网络搜索重试装饰器"""
    return create_retry_policy(
        max_attempts=2,
        wait_min=1.0,
        wait_max=10.0,
        exceptions=RETRYABLE_EXCEPTIONS
    )(func)


def with_db_retry(func):
    """数据库操作重试装饰器"""
    return create_retry_policy(
        max_attempts=3,
        wait_min=0.5,
        wait_max=5.0,
        exceptions=RETRYABLE_EXCEPTIONS
    )(func)
