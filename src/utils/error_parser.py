"""
LLM错误解析器

解析模型返回的错误，识别错误类型并提供处理建议
"""
import logging
import re
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("ErrorParser")


class ErrorType(Enum):
    """错误类型枚举"""
    TOKEN_LIMIT = "token_limit"  # Token超限
    TIMEOUT = "timeout"  # 请求超时
    RATE_LIMIT = "rate_limit"  # API速率限制
    CONTENT_FILTER = "content_filter"  # 内容过滤
    INVALID_REQUEST = "invalid_request"  # 无效请求
    SERVER_ERROR = "server_error"  # 服务器错误
    NETWORK_ERROR = "network_error"  # 网络错误
    UNKNOWN = "unknown"  # 未知错误


class LLMError:
    """LLM错误对象"""

    def __init__(self, error_type: ErrorType, message: str, original_error: Exception = None):
        self.error_type = error_type
        self.message = message
        self.original_error = original_error

    def __str__(self):
        return f"[{self.error_type.value}] {self.message}"

    def should_compress_context(self) -> bool:
        """是否需要压缩上下文"""
        return self.error_type in [ErrorType.TOKEN_LIMIT, ErrorType.INVALID_REQUEST]

    def should_retry(self) -> bool:
        """是否可以重试"""
        return self.error_type not in [ErrorType.CONTENT_FILTER, ErrorType.INVALID_REQUEST]


def parse_llm_error(error: Exception) -> LLMError:
    """
    解析LLM错误，返回结构化的错误对象

    Args:
        error: 原始异常对象

    Returns:
        LLMError对象
    """
    error_str = str(error).lower()
    error_message = str(error)

    # 1. Token超限错误
    if any(keyword in error_str for keyword in [
        'token', 'context length', 'max_length', 'too long', 'exceed'
    ]):
        logger.warning(f"检测到Token超限错误: {error_message}")
        return LLMError(
            error_type=ErrorType.TOKEN_LIMIT,
            message=f"上下文长度超限: {error_message}",
            original_error=error
        )

    # 2. 超时错误
    if any(keyword in error_str for keyword in [
        'timeout', 'timed out', 'time out'
    ]):
        logger.warning(f"检测到超时错误: {error_message}")
        return LLMError(
            error_type=ErrorType.TIMEOUT,
            message=f"请求超时: {error_message}",
            original_error=error
        )

    # 3. 速率限制错误
    if any(keyword in error_str for keyword in [
        'rate limit', 'rate_limit', 'too many requests', '429'
    ]):
        logger.warning(f"检测到速率限制错误: {error_message}")
        return LLMError(
            error_type=ErrorType.RATE_LIMIT,
            message=f"API速率限制: {error_message}",
            original_error=error
        )

    # 4. 内容过滤错误
    if any(keyword in error_str for keyword in [
        'content filter', 'safety', 'policy', 'violation', 'inappropriate'
    ]):
        logger.warning(f"检测到内容过滤错误: {error_message}")
        return LLMError(
            error_type=ErrorType.CONTENT_FILTER,
            message=f"内容被过滤: {error_message}",
            original_error=error
        )

    # 5. 无效请求错误
    if any(keyword in error_str for keyword in [
        'invalid', 'malformed', 'bad request', '400'
    ]):
        logger.warning(f"检测到无效请求错误: {error_message}")
        return LLMError(
            error_type=ErrorType.INVALID_REQUEST,
            message=f"无效请求: {error_message}",
            original_error=error
        )

    # 6. 服务器错误
    if any(keyword in error_str for keyword in [
        '500', '502', '503', 'internal server error', 'service unavailable'
    ]):
        logger.warning(f"检测到服务器错误: {error_message}")
        return LLMError(
            error_type=ErrorType.SERVER_ERROR,
            message=f"服务器错误: {error_message}",
            original_error=error
        )

    # 7. 网络错误
    if any(keyword in error_str for keyword in [
        'connection', 'network', 'dns', 'resolve'
    ]):
        logger.warning(f"检测到网络错误: {error_message}")
        return LLMError(
            error_type=ErrorType.NETWORK_ERROR,
            message=f"网络错误: {error_message}",
            original_error=error
        )

    # 未知错误
    logger.warning(f"未知错误类型: {error_message}")
    return LLMError(
        error_type=ErrorType.UNKNOWN,
        message=f"未知错误: {error_message}",
        original_error=error
    )


def extract_error_details(error: Exception) -> Dict[str, Any]:
    """
    从错误中提取详细信息

    Args:
        error: 异常对象

    Returns:
        包含错误详细信息的字典
    """
    parsed = parse_llm_error(error)

    return {
        "error_type": parsed.error_type.value,
        "message": parsed.message,
        "should_compress": parsed.should_compress_context(),
        "should_retry": parsed.should_retry(),
        "original_type": type(error).__name__,
        "original_message": str(error)
    }
