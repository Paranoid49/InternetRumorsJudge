"""
统一异常定义

定义系统中使用的所有异常类型，提供清晰的错误处理层次

[v0.8.0] 增强版本：
- 添加标准化错误码枚举 (ErrorCode)
- 支持用户友好的错误信息
- 支持异常链追踪
- 提供 HTTP 状态码映射
"""
from typing import Optional, Any, Dict, Union
from enum import Enum


class ErrorCode(str, Enum):
    """
    标准化错误码枚举

    命名规范：<类别>_<具体错误>
    编码规范：<类别前缀>_<三位数字>

    类别前缀：
    - CACHE: 缓存相关
    - RET: 检索相关
    - LLM: LLM 调用相关
    - ANL: 分析相关
    - VRD: 裁决相关
    - SYS: 系统相关
    """

    # 缓存相关 (CACHE_xxx)
    CACHE_MISS = "CACHE_001"
    CACHE_TIMEOUT = "CACHE_002"
    CACHE_CORRUPTED = "CACHE_003"
    CACHE_VERSION_MISMATCH = "CACHE_004"
    CACHE_WRITE_FAILED = "CACHE_005"

    # 检索相关 (RET_xxx)
    RETRIEVAL_FAILED = "RET_001"
    RETRIEVAL_TIMEOUT = "RET_002"
    LOCAL_KB_EMPTY = "RET_003"
    LOCAL_KB_NOT_FOUND = "RET_004"
    WEB_SEARCH_FAILED = "RET_005"
    WEB_SEARCH_TIMEOUT = "RET_006"
    WEB_SEARCH_RATE_LIMITED = "RET_007"

    # LLM 相关 (LLM_xxx)
    LLM_TIMEOUT = "LLM_001"
    LLM_RATE_LIMITED = "LLM_002"
    LLM_INVALID_RESPONSE = "LLM_003"
    LLM_API_ERROR = "LLM_004"
    LLM_QUOTA_EXCEEDED = "LLM_005"

    # 分析相关 (ANL_xxx)
    ANALYSIS_FAILED = "ANL_001"
    ANALYSIS_NO_EVIDENCE = "ANL_002"
    ANALYSIS_PARSE_ERROR = "ANL_003"

    # 裁决相关 (VRD_xxx)
    VERDICT_GENERATION_FAILED = "VRD_001"
    VERDICT_FALLBACK_USED = "VRD_002"
    VERDICT_INVALID_TYPE = "VRD_003"

    # 系统相关 (SYS_xxx)
    SYSTEM_NOT_INITIALIZED = "SYS_001"
    SYSTEM_BUSY = "SYS_002"
    SYSTEM_RESOURCE_EXHAUSTED = "SYS_003"
    INVALID_INPUT = "SYS_004"
    CONFIGURATION_ERROR = "SYS_005"
    DEPENDENCY_MISSING = "SYS_006"

    @classmethod
    def get_default_user_message(cls, code: 'ErrorCode') -> str:
        """获取错误码对应的默认用户友好信息"""
        default_messages = {
            # 缓存
            cls.CACHE_TIMEOUT: "系统繁忙，请稍后重试",
            cls.CACHE_CORRUPTED: "缓存数据异常，正在重新处理",
            cls.CACHE_VERSION_MISMATCH: "知识库已更新，正在刷新缓存",

            # 检索
            cls.RETRIEVAL_FAILED: "无法获取相关信息，请稍后重试",
            cls.RETRIEVAL_TIMEOUT: "检索超时，请稍后重试",
            cls.LOCAL_KB_EMPTY: "本地知识库为空，请先构建",
            cls.WEB_SEARCH_FAILED: "网络搜索暂时不可用",
            cls.WEB_SEARCH_TIMEOUT: "网络搜索超时",
            cls.WEB_SEARCH_RATE_LIMITED: "搜索请求过于频繁，请稍后重试",

            # LLM
            cls.LLM_TIMEOUT: "AI分析超时，请稍后重试",
            cls.LLM_RATE_LIMITED: "AI服务繁忙，请稍后重试",
            cls.LLM_INVALID_RESPONSE: "AI响应格式异常",
            cls.LLM_API_ERROR: "AI服务暂时不可用",
            cls.LLM_QUOTA_EXCEEDED: "API配额已用尽",

            # 分析
            cls.ANALYSIS_FAILED: "分析过程出错",
            cls.ANALYSIS_NO_EVIDENCE: "暂无足够证据支持判断",

            # 裁决
            cls.VERDICT_GENERATION_FAILED: "无法生成判断结论",
            cls.VERDICT_FALLBACK_USED: "使用备用分析方式",

            # 系统
            cls.SYSTEM_NOT_INITIALIZED: "系统初始化中，请稍后",
            cls.SYSTEM_BUSY: "系统繁忙，请稍后重试",
            cls.SYSTEM_RESOURCE_EXHAUSTED: "系统资源不足",
            cls.INVALID_INPUT: "输入内容无效，请检查后重试",
            cls.CONFIGURATION_ERROR: "系统配置错误",
            cls.DEPENDENCY_MISSING: "系统依赖缺失",
        }
        return default_messages.get(code, "系统处理异常，请稍后重试")


class RumorJudgeException(Exception):
    """
    基础异常类

    所有自定义异常的基类，提供统一的异常接口

    [v0.8.0] 增强功能：
    - 支持标准化错误码 (ErrorCode)
    - 支持用户友好信息 (user_message)
    - 支持异常链追踪 (cause)
    - 支持 HTTP 状态码映射
    """

    # 默认 HTTP 状态码映射
    DEFAULT_HTTP_STATUS = 500

    def __init__(
        self,
        message: str,
        error_code: Optional[Any] = None,  # 支持 str 或 ErrorCode
        user_message: Optional[str] = None,
        details: Optional[Any] = None,
        cause: Optional[Exception] = None
    ):
        """
        初始化异常

        Args:
            message: 技术错误消息（用于日志）
            error_code: 错误代码（支持字符串或 ErrorCode 枚举）
            user_message: 用户友好信息（用于 API 响应）
            details: 额外详情（可选，可以是任何类型）
            cause: 原始异常（用于异常链追踪）
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.user_message = user_message or self._get_default_user_message()
        self.details = details
        self.cause = cause

        # 如果有原始异常，设置 __cause__
        if cause is not None and not isinstance(cause, RumorJudgeException):
            self.__cause__ = cause

    def _get_default_user_message(self) -> str:
        """获取默认用户友好信息"""
        if isinstance(self.error_code, ErrorCode):
            return ErrorCode.get_default_user_message(self.error_code)
        return "系统处理异常，请稍后重试"

    def get_http_status(self) -> int:
        """获取对应的 HTTP 状态码"""
        if not isinstance(self.error_code, ErrorCode):
            return self.DEFAULT_HTTP_STATUS

        status_map = {
            # 400 - 客户端错误
            ErrorCode.INVALID_INPUT: 400,
            ErrorCode.CONFIGURATION_ERROR: 400,

            # 404 - 资源未找到
            ErrorCode.CACHE_MISS: 404,
            ErrorCode.LOCAL_KB_NOT_FOUND: 404,

            # 503 - 服务暂时不可用
            ErrorCode.CACHE_TIMEOUT: 503,
            ErrorCode.RETRIEVAL_TIMEOUT: 503,
            ErrorCode.WEB_SEARCH_TIMEOUT: 503,
            ErrorCode.WEB_SEARCH_RATE_LIMITED: 503,
            ErrorCode.LLM_TIMEOUT: 503,
            ErrorCode.LLM_RATE_LIMITED: 503,
            ErrorCode.LLM_QUOTA_EXCEEDED: 503,
            ErrorCode.SYSTEM_NOT_INITIALIZED: 503,
            ErrorCode.SYSTEM_BUSY: 503,
            ErrorCode.SYSTEM_RESOURCE_EXHAUSTED: 503,
        }
        return status_map.get(self.error_code, self.DEFAULT_HTTP_STATUS)

    def __str__(self) -> str:
        """返回友好的错误消息"""
        code_str = self.error_code.value if isinstance(self.error_code, ErrorCode) else self.error_code
        if self.details:
            return f"[{code_str}] {self.message} - {self.details}"
        return f"[{code_str}] {self.message}"

    def to_dict(self, include_details: bool = True) -> dict:
        """
        转换为字典格式（用于 API 响应）

        Args:
            include_details: 是否包含详细信息（生产环境建议关闭）

        Returns:
            包含错误信息的字典
        """
        code_str = self.error_code.value if isinstance(self.error_code, ErrorCode) else self.error_code

        result = {
            'success': False,
            'error': {
                'code': code_str,
                'message': self.user_message,
            }
        }

        if include_details:
            result['error']['details'] = self.details
            result['error']['technical_message'] = self.message

        return result


# ==================== 缓存相关异常 ====================

class CacheException(RumorJudgeException):
    """
    缓存异常

    缓存操作失败时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        cache_type: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化缓存异常

        Args:
            message: 错误消息
            error_code: 错误代码
            cache_type: 缓存类型（如 'exact_match', 'semantic'）
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'cache_type': cache_type} if cache_type else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.CACHE_MISS,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class CacheMissException(CacheException):
    """
    缓存未命中异常

    当需要强制缓存命中但未命中时抛出
    """

    def __init__(self, message: str = "缓存未命中", **kwargs):
        super().__init__(message, error_code=ErrorCode.CACHE_MISS, **kwargs)


class CacheStaleException(CacheException):
    """
    缓存过期异常

    当缓存数据已过期时抛出
    """

    def __init__(self, message: str = "缓存已过期", **kwargs):
        super().__init__(message, error_code=ErrorCode.CACHE_VERSION_MISMATCH, **kwargs)


# ==================== 检索相关异常 ====================

class RetrievalException(RumorJudgeException):
    """
    检索异常

    证据检索失败时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        retrieval_type: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化检索异常

        Args:
            message: 错误消息
            error_code: 错误代码
            retrieval_type: 检索类型（如 'local', 'web', 'hybrid'）
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'retrieval_type': retrieval_type} if retrieval_type else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.RETRIEVAL_FAILED,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class KnowledgeBaseException(RetrievalException):
    """
    知识库异常

    知识库操作失败时抛出
    """

    def __init__(
        self,
        message: str,
        kb_version: Optional[str] = None,
        error_code: Optional[Union[str, ErrorCode]] = None,
        **kwargs
    ):
        """
        初始化知识库异常

        Args:
            message: 错误消息
            kb_version: 知识库版本
            error_code: 错误代码
        """
        details = kwargs.pop('details', None) or {}
        if kb_version:
            details['kb_version'] = kb_version
        super().__init__(
            message,
            error_code=error_code or ErrorCode.LOCAL_KB_NOT_FOUND,
            details=details,
            **kwargs
        )


class WebSearchException(RetrievalException):
    """
    网络搜索异常

    网络搜索失败时抛出
    """

    def __init__(
        self,
        message: str,
        search_query: Optional[str] = None,
        error_code: Optional[Union[str, ErrorCode]] = None,
        **kwargs
    ):
        """
        初始化网络搜索异常

        Args:
            message: 错误消息
            search_query: 搜索查询词
            error_code: 错误代码
        """
        details = kwargs.pop('details', None) or {}
        if search_query:
            details['search_query'] = search_query
        super().__init__(
            message,
            error_code=error_code or ErrorCode.WEB_SEARCH_FAILED,
            details=details,
            **kwargs
        )


# ==================== 分析相关异常 ====================

class AnalysisException(RumorJudgeException):
    """
    分析异常

    证据分析失败时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        analysis_type: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化分析异常

        Args:
            message: 错误消息
            error_code: 错误代码
            analysis_type: 分析类型（如 'query_parse', 'evidence_analyze'）
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'analysis_type': analysis_type} if analysis_type else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.ANALYSIS_FAILED,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class QueryParseException(AnalysisException):
    """
    查询解析异常

    查询解析失败时抛出
    """

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        error_code: Optional[Union[str, ErrorCode]] = None,
        **kwargs
    ):
        """
        初始化查询解析异常

        Args:
            message: 错误消息
            query: 原始查询
            error_code: 错误代码
        """
        details = kwargs.pop('details', None) or {}
        if query:
            details['query'] = query
        super().__init__(
            message,
            error_code=error_code or ErrorCode.ANALYSIS_PARSE_ERROR,
            analysis_type='query_parse',
            details=details,
            **kwargs
        )


class EvidenceAnalyzeException(AnalysisException):
    """
    证据分析异常

    证据分析失败时抛出
    """

    def __init__(
        self,
        message: str,
        evidence_count: Optional[int] = None,
        error_code: Optional[Union[str, ErrorCode]] = None,
        **kwargs
    ):
        """
        初始化证据分析异常

        Args:
            message: 错误消息
            evidence_count: 证据数量
            error_code: 错误代码
        """
        details = kwargs.pop('details', None) or {}
        if evidence_count is not None:
            details['evidence_count'] = evidence_count
        super().__init__(
            message,
            error_code=error_code or ErrorCode.ANALYSIS_FAILED,
            analysis_type='evidence_analyze',
            details=details,
            **kwargs
        )


class VerdictGenerateException(AnalysisException):
    """
    裁决生成异常

    裁决生成失败时抛出
    """

    def __init__(self, message: str = "裁决生成失败", **kwargs):
        kwargs.setdefault('error_code', ErrorCode.VERDICT_GENERATION_FAILED)
        super().__init__(message, analysis_type='verdict_generate', **kwargs)


# ==================== LLM 相关异常 ====================

class LLMException(RumorJudgeException):
    """
    LLM 调用异常

    LLM 调用失败时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        model_name: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化 LLM 异常

        Args:
            message: 错误消息
            error_code: 错误代码
            model_name: 模型名称
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'model_name': model_name} if model_name else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.LLM_API_ERROR,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class LLMTimeoutException(LLMException):
    """
    LLM 超时异常

    LLM 调用超时时抛出
    """

    def __init__(self, message: str = "LLM 调用超时", **kwargs):
        kwargs.setdefault('error_code', ErrorCode.LLM_TIMEOUT)
        super().__init__(message, **kwargs)


class LLMQuotaException(LLMException):
    """
    LLM 配额异常

    LLM 配额不足时抛出
    """

    def __init__(self, message: str = "LLM 配额已用尽", **kwargs):
        kwargs.setdefault('error_code', ErrorCode.LLM_QUOTA_EXCEEDED)
        super().__init__(message, **kwargs)


# ==================== 配置相关异常 ====================

class ConfigurationException(RumorJudgeException):
    """
    配置异常

    配置错误时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        config_key: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化配置异常

        Args:
            message: 错误消息
            error_code: 错误代码
            config_key: 配置键名
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'config_key': config_key} if config_key else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.CONFIGURATION_ERROR,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class DependencyException(ConfigurationException):
    """
    依赖异常

    依赖缺失或版本不兼容时抛出
    """

    def __init__(
        self,
        message: str,
        dependency_name: Optional[str] = None,
        **kwargs
    ):
        """
        初始化依赖异常

        Args:
            message: 错误消息
            dependency_name: 依赖名称
        """
        details = kwargs.pop('details', None) or {}
        if dependency_name:
            details['dependency_name'] = dependency_name
        kwargs['details'] = details
        super().__init__(message, error_code=ErrorCode.DEPENDENCY_MISSING, **kwargs)


# ==================== 并发相关异常 ====================

class ConcurrencyException(RumorJudgeException):
    """
    并发异常

    并发操作失败时抛出
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[str, ErrorCode]] = None,
        operation: Optional[str] = None,
        user_message: Optional[str] = None,
        details=None,
        cause: Optional[Exception] = None
    ):
        """
        初始化并发异常

        Args:
            message: 错误消息
            error_code: 错误代码
            operation: 操作名称
            user_message: 用户友好信息
            details: 额外详情（可选）
            cause: 原始异常
        """
        merged_details = {'operation': operation} if operation else {}
        if details:
            merged_details.update(details)
        super().__init__(
            message=message,
            error_code=error_code or ErrorCode.SYSTEM_BUSY,
            user_message=user_message,
            details=merged_details if merged_details else None,
            cause=cause
        )


class LockTimeoutException(ConcurrencyException):
    """
    锁超时异常

    获取锁超时时抛出
    """

    def __init__(self, message: str = "获取锁超时", **kwargs):
        kwargs.setdefault('error_code', ErrorCode.SYSTEM_BUSY)
        super().__init__(message, **kwargs)


# ==================== 工具函数 ====================

def handle_exception(
    exception: Exception,
    logger=None,
    context: Optional[str] = None,
    reraise: bool = False,
    error_code: Optional[ErrorCode] = None
) -> Optional[RumorJudgeException]:
    """
    统一异常处理函数

    Args:
        exception: 原始异常
        logger: 日志记录器（可选）
        context: 上下文信息（如操作名称）
        reraise: 是否重新抛出异常
        error_code: 指定的错误码（可选）

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

    # 推断错误码
    inferred_code = error_code or _infer_error_code_from_exception(exception)

    wrapped = RumorJudgeException(
        message=str(exception),
        error_code=inferred_code,
        details={'original_type': type(exception).__name__},
        cause=exception
    )

    if reraise:
        raise wrapped from exception

    return wrapped


def _infer_error_code_from_exception(exception: Exception) -> ErrorCode:
    """
    从异常推断错误码

    Args:
        exception: 原始异常

    Returns:
        推断的错误码
    """
    error_type = type(exception).__name__.lower()
    error_message = str(exception).lower()

    # 超时
    if 'timeout' in error_type or 'timeout' in error_message:
        return ErrorCode.LLM_TIMEOUT

    # 限流
    if 'rate' in error_message or 'limit' in error_message:
        return ErrorCode.LLM_RATE_LIMITED

    # 连接
    if 'connection' in error_message or 'network' in error_message:
        return ErrorCode.WEB_SEARCH_FAILED

    # 文件/资源未找到
    if 'notfound' in error_type or 'not found' in error_message:
        return ErrorCode.LOCAL_KB_NOT_FOUND

    # 配置
    if 'config' in error_type:
        return ErrorCode.CONFIGURATION_ERROR

    # 默认
    return ErrorCode.SYSTEM_RESOURCE_EXHAUSTED


def create_exception_from_error(
    error_code: Union[str, ErrorCode],
    message: str,
    details: Optional[Any] = None
) -> RumorJudgeException:
    """
    根据错误代码创建异常

    Args:
        error_code: 错误代码（字符串或 ErrorCode 枚举）
        message: 错误消息
        details: 额外详情

    Returns:
        对应的异常实例

    Raises:
        ValueError: 如果错误代码未知
    """
    # 如果是 ErrorCode 枚举，使用映射
    if isinstance(error_code, ErrorCode):
        code_to_class = {
            ErrorCode.CACHE_MISS: CacheMissException,
            ErrorCode.CACHE_TIMEOUT: CacheException,
            ErrorCode.CACHE_VERSION_MISMATCH: CacheStaleException,
            ErrorCode.RETRIEVAL_FAILED: RetrievalException,
            ErrorCode.LOCAL_KB_NOT_FOUND: KnowledgeBaseException,
            ErrorCode.WEB_SEARCH_FAILED: WebSearchException,
            ErrorCode.ANALYSIS_FAILED: AnalysisException,
            ErrorCode.ANALYSIS_PARSE_ERROR: QueryParseException,
            ErrorCode.VERDICT_GENERATION_FAILED: VerdictGenerateException,
            ErrorCode.LLM_API_ERROR: LLMException,
            ErrorCode.LLM_TIMEOUT: LLMTimeoutException,
            ErrorCode.LLM_QUOTA_EXCEEDED: LLMQuotaException,
            ErrorCode.CONFIGURATION_ERROR: ConfigurationException,
            ErrorCode.DEPENDENCY_MISSING: DependencyException,
            ErrorCode.SYSTEM_BUSY: ConcurrencyException,
        }
        exception_class = code_to_class.get(error_code, RumorJudgeException)
        return exception_class(message=message, error_code=error_code, details=details)

    # 字符串错误码（向后兼容）
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
