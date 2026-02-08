"""
统一异常定义

定义系统中使用的所有异常类型，提供清晰的错误处理层次
"""
from typing import Optional, Any


class RumorJudgeException(Exception):
    """
    基础异常类

    所有自定义异常的基类，提供统一的异常接口
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Any] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            error_code: 错误代码（可选，用于错误分类）
            details: 额外详情（可选，可以是任何类型）
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details

    def __str__(self) -> str:
        """返回友好的错误消息"""
        if self.details:
            return f"[{self.error_code}] {self.message} - {self.details}"
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict:
        """
        转换为字典格式（用于 API 响应）

        Returns:
            包含错误信息的字典
        """
        return {
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details
        }


# ==================== 缓存相关异常 ====================

class CacheException(RumorJudgeException):
    """
    缓存异常

    缓存操作失败时抛出
    """

    def __init__(self, message: str, cache_type: Optional[str] = None, details=None):
        """
        初始化缓存异常

        Args:
            message: 错误消息
            cache_type: 缓存类型（如 'exact_match', 'semantic'）
            details: 额外详情（可选）
        """
        merged_details = {'cache_type': cache_type} if cache_type else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class CacheMissException(CacheException):
    """
    缓存未命中异常

    当需要强制缓存命中但未命中时抛出
    """
    pass


class CacheStaleException(CacheException):
    """
    缓存过期异常

    当缓存数据已过期时抛出
    """
    pass


# ==================== 检索相关异常 ====================

class RetrievalException(RumorJudgeException):
    """
    检索异常

    证据检索失败时抛出
    """

    def __init__(self, message: str, retrieval_type: Optional[str] = None, details=None):
        """
        初始化检索异常

        Args:
            message: 错误消息
            retrieval_type: 检索类型（如 'local', 'web', 'hybrid'）
            details: 额外详情（可选）
        """
        merged_details = {'retrieval_type': retrieval_type} if retrieval_type else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class KnowledgeBaseException(RetrievalException):
    """
    知识库异常

    知识库操作失败时抛出
    """

    def __init__(self, message: str, kb_version: Optional[str] = None):
        """
        初始化知识库异常

        Args:
            message: 错误消息
            kb_version: 知识库版本
        """
        details = {'kb_version': kb_version} if kb_version else None
        super().__init__(message, details=details)


class WebSearchException(RetrievalException):
    """
    网络搜索异常

    网络搜索失败时抛出
    """

    def __init__(self, message: str, search_query: Optional[str] = None):
        """
        初始化网络搜索异常

        Args:
            message: 错误消息
            search_query: 搜索查询词
        """
        details = {'search_query': search_query} if search_query else None
        super().__init__(message, details=details)


# ==================== 分析相关异常 ====================

class AnalysisException(RumorJudgeException):
    """
    分析异常

    证据分析失败时抛出
    """

    def __init__(self, message: str, analysis_type: Optional[str] = None, details=None):
        """
        初始化分析异常

        Args:
            message: 错误消息
            analysis_type: 分析类型（如 'query_parse', 'evidence_analyze'）
            details: 额外详情（可选）
        """
        merged_details = {'analysis_type': analysis_type} if analysis_type else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class QueryParseException(AnalysisException):
    """
    查询解析异常

    查询解析失败时抛出
    """

    def __init__(self, message: str, query: Optional[str] = None):
        """
        初始化查询解析异常

        Args:
            message: 错误消息
            query: 原始查询
        """
        details = {'query': query} if query else None
        super().__init__(message, analysis_type='query_parse', details=details)


class EvidenceAnalyzeException(AnalysisException):
    """
    证据分析异常

    证据分析失败时抛出
    """

    def __init__(self, message: str, evidence_count: Optional[int] = None):
        """
        初始化证据分析异常

        Args:
            message: 错误消息
            evidence_count: 证据数量
        """
        details = {'evidence_count': evidence_count} if evidence_count is not None else None
        super().__init__(message, analysis_type='evidence_analyze', details=details)


class VerdictGenerateException(AnalysisException):
    """
    裁决生成异常

    裁决生成失败时抛出
    """
    pass


# ==================== LLM 相关异常 ====================

class LLMException(RumorJudgeException):
    """
    LLM 调用异常

    LLM 调用失败时抛出
    """

    def __init__(self, message: str, model_name: Optional[str] = None, details=None):
        """
        初始化 LLM 异常

        Args:
            message: 错误消息
            model_name: 模型名称
            details: 额外详情（可选）
        """
        merged_details = {'model_name': model_name} if model_name else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class LLMTimeoutException(LLMException):
    """
    LLM 超时异常

    LLM 调用超时时抛出
    """
    pass


class LLMQuotaException(LLMException):
    """
    LLM 配额异常

    LLM 配额不足时抛出
    """
    pass


# ==================== 配置相关异常 ====================

class ConfigurationException(RumorJudgeException):
    """
    配置异常

    配置错误时抛出
    """

    def __init__(self, message: str, config_key: Optional[str] = None, details=None):
        """
        初始化配置异常

        Args:
            message: 错误消息
            config_key: 配置键名
            details: 额外详情（可选）
        """
        merged_details = {'config_key': config_key} if config_key else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class DependencyException(ConfigurationException):
    """
    依赖异常

    依赖缺失或版本不兼容时抛出
    """

    def __init__(self, message: str, dependency_name: Optional[str] = None):
        """
        初始化依赖异常

        Args:
            message: 错误消息
            dependency_name: 依赖名称
        """
        details = {'dependency_name': dependency_name} if dependency_name else None
        super().__init__(message, details=details)


# ==================== 并发相关异常 ====================

class ConcurrencyException(RumorJudgeException):
    """
    并发异常

    并发操作失败时抛出
    """

    def __init__(self, message: str, operation: Optional[str] = None, details=None):
        """
        初始化并发异常

        Args:
            message: 错误消息
            operation: 操作名称
            details: 额外详情（可选）
        """
        merged_details = {'operation': operation} if operation else {}
        if details:
            merged_details.update(details)
        super().__init__(message, details=merged_details if merged_details else None)


class LockTimeoutException(ConcurrencyException):
    """
    锁超时异常

    获取锁超时时抛出
    """
    pass


# ==================== 工具函数 ====================

def handle_exception(
    exception: Exception,
    logger=None,
    context: Optional[str] = None,
    reraise: bool = False
) -> Optional[RumorJudgeException]:
    """
    统一异常处理函数

    Args:
        exception: 原始异常
        logger: 日志记录器（可选）
        context: 上下文信息（如操作名称）
        reraise: 是否重新抛出异常

    Returns:
        转换后的 RumorJudgeException（如果是原始异常）
    """
    context_msg = f"[{context}] " if context else ""

    # 已经是自定义异常
    if isinstance(exception, RumorJudgeException):
        if logger:
            logger.error(f"{context_msg}{exception}")
        if reraise:
            raise
        return exception

    # 系统异常，记录并包装
    if logger:
        logger.error(f"{context_msg}未处理的异常: {type(exception).__name__}: {exception}")
    wrapped = RumorJudgeException(
        message=str(exception),
        error_code=type(exception).__name__,
        details={'original_type': type(exception).__name__}
    )

    if reraise:
        raise wrapped from exception

    return wrapped


def create_exception_from_error(
    error_code: str,
    message: str,
    details: Optional[Any] = None
) -> RumorJudgeException:
    """
    根据错误代码创建异常

    Args:
        error_code: 错误代码
        message: 错误消息
        details: 额外详情

    Returns:
        对应的异常实例

    Raises:
        ValueError: 如果错误代码未知
    """
    exception_map = {
        'CacheException': CacheException,
        'CacheMissException': CacheMissException,
        'RetrievalException': RetrievalException,
        'KnowledgeBaseException': KnowledgeBaseException,
        'WebSearchException': WebSearchException,
        'AnalysisException': AnalysisException,
        'QueryParseException': QueryParseException,
        'EvidenceAnalyzeException': EvidenceAnalyzeException,
        'VerdictGenerateException': VerdictGenerateException,
        'LLMException': LLMException,
        'ConfigurationException': ConfigurationException,
        'DependencyException': DependencyException,
        'ConcurrencyException': ConcurrencyException,
    }

    exception_class = exception_map.get(error_code)
    if exception_class is None:
        raise ValueError(f"未知的错误代码: {error_code}")

    return exception_class(message=message, details=details)
