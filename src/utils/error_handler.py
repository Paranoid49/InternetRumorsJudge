"""
统一错误处理模块

提供错误处理装饰器和工具函数，用于：
1. 统一异常转换
2. 自动日志记录
3. 重试机制
4. 回退值处理

[v0.8.0] 新增模块
"""
import functools
import logging
import time
from typing import Callable, Type, Optional, Any, Union, Tuple

from src.core.exceptions import (
    RumorJudgeException,
    ErrorCode,
    CacheException,
    RetrievalException,
    LLMException,
    AnalysisException,
    ConfigurationException,
    ConcurrencyException,
)

logger = logging.getLogger("ErrorHandler")


def handle_errors(
    *expected_exceptions: Type[Exception],
    error_code: Optional[ErrorCode] = None,
    fallback_value: Any = None,
    reraise: bool = False,
    log_level: int = logging.ERROR,
    retries: int = 0,
    retry_delay: float = 1.0,
    retry_backoff: float = 2.0,
):
    """
    统一错误处理装饰器

    Args:
        *expected_exceptions: 预期的异常类型
        error_code: 转换后的错误码
        fallback_value: 失败时的回退值
        reraise: 是否重新抛出异常
        log_level: 日志级别
        retries: 重试次数（0 表示不重试）
        retry_delay: 初始重试延迟（秒）
        retry_backoff: 重试延迟倍数

    Returns:
        装饰器函数

    用法:
        @handle_errors(ValueError, error_code=ErrorCode.INVALID_INPUT, fallback_value=None)
        def parse_input(data):
            return json.loads(data)

        @handle_errors(Exception, retries=3, reraise=True)
        def call_llm(prompt):
            return llm.invoke(prompt)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = retry_delay

            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except RumorJudgeException as e:
                    # 已是标准异常，直接处理
                    logger.log(log_level, f"[{func.__name__}] {e}")
                    if reraise:
                        raise
                    return fallback_value

                except expected_exceptions as e:
                    last_exception = e
                    logger.log(
                        log_level,
                        f"[{func.__name__}] 捕获预期异常: {type(e).__name__}: {e}"
                    )

                    # 如果还有重试机会，继续
                    if attempt < retries:
                        logger.info(f"[{func.__name__}] 重试 {attempt + 1}/{retries}, 等待 {current_delay}s")
                        time.sleep(current_delay)
                        current_delay *= retry_backoff
                        continue

                    # 转换为标准异常
                    standard_error = _convert_to_standard_error(e, error_code, func.__name__)

                    if reraise:
                        raise standard_error from e
                    return fallback_value

                except Exception as e:
                    # 未预期异常
                    last_exception = e
                    logger.exception(f"[{func.__name__}] 未预期异常: {type(e).__name__}: {e}")

                    if reraise:
                        raise RumorJudgeException(
                            message=f"未预期异常: {type(e).__name__}: {e}",
                            error_code=ErrorCode.SYSTEM_RESOURCE_EXHAUSTED,
                            cause=e
                        ) from e
                    return fallback_value

            # 所有重试都失败
            return fallback_value

        return wrapper
    return decorator


def _convert_to_standard_error(
    original_error: Exception,
    error_code: Optional[ErrorCode],
    context: str
) -> RumorJudgeException:
    """
    将原始异常转换为标准异常

    Args:
        original_error: 原始异常
        error_code: 指定的错误码
        context: 上下文（函数名）

    Returns:
        转换后的 RumorJudgeException
    """
    error_message = str(original_error)
    error_type = type(original_error).__name__

    # 根据异常类型和内容推断错误码
    inferred_code = error_code or _infer_error_code(original_error, context)

    # 根据错误码选择异常类
    exception_class = _get_exception_class(inferred_code)

    return exception_class(
        message=f"[{context}] {error_message}",
        error_code=inferred_code,
        cause=original_error
    )


def _infer_error_code(error: Exception, context: str) -> ErrorCode:
    """
    根据异常类型和内容推断错误码

    Args:
        error: 原始异常
        context: 上下文

    Returns:
        推断的错误码
    """
    error_message = str(error).lower()
    error_type = type(error).__name__

    # 超时相关
    if 'timeout' in error_type.lower() or 'timeout' in error_message:
        if 'cache' in context.lower():
            return ErrorCode.CACHE_TIMEOUT
        if 'web' in context.lower() or 'search' in context.lower():
            return ErrorCode.WEB_SEARCH_TIMEOUT
        if 'llm' in context.lower():
            return ErrorCode.LLM_TIMEOUT
        return ErrorCode.RETRIEVAL_TIMEOUT

    # 限流相关
    if 'rate' in error_message or 'limit' in error_message or 'quota' in error_message:
        if 'web' in context.lower() or 'search' in context.lower():
            return ErrorCode.WEB_SEARCH_RATE_LIMITED
        if 'llm' in context.lower():
            return ErrorCode.LLM_RATE_LIMITED
        return ErrorCode.SYSTEM_BUSY

    # 连接相关
    if 'connection' in error_message or 'network' in error_message:
        return ErrorCode.WEB_SEARCH_FAILED

    # 配置相关
    if 'config' in context.lower() or 'setting' in context.lower():
        return ErrorCode.CONFIGURATION_ERROR

    # 默认
    return ErrorCode.SYSTEM_RESOURCE_EXHAUSTED


def _get_exception_class(error_code: ErrorCode) -> Type[RumorJudgeException]:
    """
    根据错误码获取对应的异常类

    Args:
        error_code: 错误码

    Returns:
        对应的异常类
    """
    code_to_class = {
        # 缓存
        ErrorCode.CACHE_MISS: CacheException,
        ErrorCode.CACHE_TIMEOUT: CacheException,
        ErrorCode.CACHE_CORRUPTED: CacheException,
        ErrorCode.CACHE_VERSION_MISMATCH: CacheException,
        ErrorCode.CACHE_WRITE_FAILED: CacheException,

        # 检索
        ErrorCode.RETRIEVAL_FAILED: RetrievalException,
        ErrorCode.RETRIEVAL_TIMEOUT: RetrievalException,
        ErrorCode.LOCAL_KB_EMPTY: RetrievalException,
        ErrorCode.LOCAL_KB_NOT_FOUND: RetrievalException,
        ErrorCode.WEB_SEARCH_FAILED: RetrievalException,
        ErrorCode.WEB_SEARCH_TIMEOUT: RetrievalException,
        ErrorCode.WEB_SEARCH_RATE_LIMITED: RetrievalException,

        # LLM
        ErrorCode.LLM_TIMEOUT: LLMException,
        ErrorCode.LLM_RATE_LIMITED: LLMException,
        ErrorCode.LLM_INVALID_RESPONSE: LLMException,
        ErrorCode.LLM_API_ERROR: LLMException,
        ErrorCode.LLM_QUOTA_EXCEEDED: LLMException,

        # 分析
        ErrorCode.ANALYSIS_FAILED: AnalysisException,
        ErrorCode.ANALYSIS_NO_EVIDENCE: AnalysisException,
        ErrorCode.ANALYSIS_PARSE_ERROR: AnalysisException,
    }

    return code_to_class.get(error_code, RumorJudgeException)


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    logger_instance: logging.Logger = None,
    **kwargs
) -> Tuple[Any, Optional[Exception]]:
    """
    安全执行函数，捕获所有异常

    Args:
        func: 要执行的函数
        *args: 位置参数
        default: 失败时的默认返回值
        logger_instance: 日志记录器
        **kwargs: 关键字参数

    Returns:
        (结果, 异常) 元组，成功时异常为 None

    用法:
        result, error = safe_execute(parse_json, '{"key": "value"}')
        if error:
            print(f"执行失败: {error}")
    """
    log = logger_instance or logger

    try:
        return func(*args, **kwargs), None
    except Exception as e:
        log.error(f"安全执行失败 [{func.__name__}]: {e}")
        return default, e


def retry_on_exception(
    *exceptions: Type[Exception],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger_instance: logging.Logger = None
):
    """
    重试装饰器（简化版）

    Args:
        *exceptions: 触发重试的异常类型
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍数
        logger_instance: 日志记录器

    用法:
        @retry_on_exception(TimeoutError, max_retries=3)
        def fetch_data():
            ...
    """
    log = logger_instance or logger

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries:
                        log.warning(
                            f"[{func.__name__}] 失败，重试 {attempt + 1}/{max_retries}: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        log.error(f"[{func.__name__}] 达到最大重试次数")

            raise last_error

        return wrapper
    return decorator


class ErrorContext:
    """
    错误上下文管理器

    用于包装可能出错的代码块，提供统一的错误处理

    用法:
        with ErrorContext("处理用户请求", reraise=False) as ctx:
            result = process_request(data)
            ctx.result = result

        if ctx.error:
            print(f"处理失败: {ctx.error}")
    """

    def __init__(
        self,
        operation: str,
        reraise: bool = False,
        error_code: ErrorCode = None,
        logger_instance: logging.Logger = None
    ):
        self.operation = operation
        self.reraise = reraise
        self.error_code = error_code
        self.logger = logger_instance or logger
        self.error: Optional[Exception] = None
        self.result: Any = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.error = exc_val
            self.logger.error(f"[{self.operation}] 发生错误: {exc_val}")

            if self.reraise:
                if isinstance(exc_val, RumorJudgeException):
                    raise
                raise RumorJudgeException(
                    message=f"[{self.operation}] {exc_val}",
                    error_code=self.error_code or ErrorCode.SYSTEM_RESOURCE_EXHAUSTED,
                    cause=exc_val
                ) from exc_val

            return True  # 抑制异常

        return False
