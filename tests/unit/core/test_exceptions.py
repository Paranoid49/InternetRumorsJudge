"""
测试统一异常体系

[v0.8.0] 更新：适配 ErrorCode 枚举和增强的异常类
"""
import pytest
from src.core.exceptions import (
    ErrorCode,
    RumorJudgeException,
    CacheException,
    CacheMissException,
    CacheStaleException,
    RetrievalException,
    KnowledgeBaseException,
    WebSearchException,
    AnalysisException,
    QueryParseException,
    EvidenceAnalyzeException,
    VerdictGenerateException,
    LLMException,
    LLMTimeoutException,
    LLMQuotaException,
    ConfigurationException,
    DependencyException,
    ConcurrencyException,
    LockTimeoutException,
    handle_exception,
    create_exception_from_error
)


class TestErrorCode:
    """测试错误码枚举"""

    def test_error_code_values(self):
        """测试错误码值"""
        assert ErrorCode.CACHE_MISS.value == "CACHE_001"
        assert ErrorCode.LLM_TIMEOUT.value == "LLM_001"
        assert ErrorCode.WEB_SEARCH_FAILED.value == "RET_005"

    def test_get_default_user_message(self):
        """测试默认用户信息"""
        msg = ErrorCode.get_default_user_message(ErrorCode.LLM_TIMEOUT)
        assert msg  # 不为空
        assert "超时" in msg or "稍后" in msg


class TestRumorJudgeException:
    """测试基础异常类"""

    def test_basic_exception(self):
        """测试基本异常"""
        exc = RumorJudgeException(message="测试错误")
        assert "测试错误" in exc.message
        assert exc.error_code is not None

    def test_exception_with_error_code(self):
        """测试带错误代码的异常"""
        exc = RumorJudgeException(message="测试错误", error_code=ErrorCode.SYSTEM_BUSY)
        assert exc.error_code == ErrorCode.SYSTEM_BUSY
        assert "SYS_002" in str(exc) or "SYSTEM_BUSY" in str(exc)

    def test_exception_with_user_message(self):
        """测试带用户信息的异常"""
        exc = RumorJudgeException(
            message="技术错误",
            error_code=ErrorCode.LLM_TIMEOUT,
            user_message="请稍后重试"
        )
        assert exc.message == "技术错误"
        assert exc.user_message == "请稍后重试"

    def test_exception_with_cause(self):
        """测试带原因的异常"""
        original = ValueError("原始错误")
        exc = RumorJudgeException(message="包装错误", cause=original)
        assert exc.cause == original
        assert exc.__cause__ == original

    def test_exception_with_details(self):
        """测试带详情的异常"""
        details = {"key": "value"}
        exc = RumorJudgeException(message="测试错误", details=details)
        assert exc.details == details

    def test_to_dict(self):
        """测试转换为字典"""
        exc = RumorJudgeException(
            message="测试错误",
            error_code=ErrorCode.CACHE_TIMEOUT,
            details={"key": "value"}
        )
        result = exc.to_dict(include_details=True)
        assert result["success"] == False
        assert result["error"]["code"] == "CACHE_002"

    def test_get_http_status(self):
        """测试 HTTP 状态码映射"""
        exc = RumorJudgeException(message="测试", error_code=ErrorCode.INVALID_INPUT)
        assert exc.get_http_status() == 400

        exc = RumorJudgeException(message="测试", error_code=ErrorCode.LLM_TIMEOUT)
        assert exc.get_http_status() == 503


class TestCacheExceptions:
    """测试缓存异常"""

    def test_cache_exception(self):
        """测试缓存异常"""
        exc = CacheException(message="缓存失败", cache_type="exact_match")
        assert exc.error_code == ErrorCode.CACHE_MISS
        assert exc.details.get('cache_type') == "exact_match"

    def test_cache_miss_exception(self):
        """测试缓存未命中异常"""
        exc = CacheMissException(message="未命中缓存")
        assert exc.error_code == ErrorCode.CACHE_MISS
        assert isinstance(exc, CacheException)

    def test_cache_stale_exception(self):
        """测试缓存过期异常"""
        exc = CacheStaleException(message="缓存已过期")
        assert exc.error_code == ErrorCode.CACHE_VERSION_MISMATCH
        assert isinstance(exc, CacheException)


class TestRetrievalExceptions:
    """测试检索异常"""

    def test_retrieval_exception(self):
        """测试检索异常"""
        exc = RetrievalException(message="检索失败", retrieval_type="local")
        assert exc.error_code == ErrorCode.RETRIEVAL_FAILED
        assert exc.details.get('retrieval_type') == "local"

    def test_knowledge_base_exception(self):
        """测试知识库异常"""
        exc = KnowledgeBaseException(message="知识库错误", kb_version="v1.0")
        assert exc.error_code == ErrorCode.LOCAL_KB_NOT_FOUND
        assert isinstance(exc, RetrievalException)
        assert exc.details.get('kb_version') == "v1.0"

    def test_web_search_exception(self):
        """测试网络搜索异常"""
        exc = WebSearchException(message="搜索失败", search_query="测试查询")
        assert exc.error_code == ErrorCode.WEB_SEARCH_FAILED
        assert isinstance(exc, RetrievalException)
        assert exc.details.get('search_query') == "测试查询"


class TestAnalysisExceptions:
    """测试分析异常"""

    def test_analysis_exception(self):
        """测试分析异常"""
        exc = AnalysisException(message="分析失败", analysis_type="evidence_analyze")
        assert exc.error_code == ErrorCode.ANALYSIS_FAILED
        assert exc.details.get('analysis_type') == "evidence_analyze"

    def test_query_parse_exception(self):
        """测试查询解析异常"""
        exc = QueryParseException(message="解析失败", query="测试查询")
        assert exc.error_code == ErrorCode.ANALYSIS_PARSE_ERROR
        assert isinstance(exc, AnalysisException)
        assert exc.details.get('query') == "测试查询"

    def test_evidence_analyze_exception(self):
        """测试证据分析异常"""
        exc = EvidenceAnalyzeException(message="分析失败", evidence_count=5)
        assert exc.error_code == ErrorCode.ANALYSIS_FAILED
        assert isinstance(exc, AnalysisException)
        assert exc.details.get('evidence_count') == 5

    def test_verdict_generate_exception(self):
        """测试裁决生成异常"""
        exc = VerdictGenerateException(message="生成失败")
        assert exc.error_code == ErrorCode.VERDICT_GENERATION_FAILED
        assert isinstance(exc, AnalysisException)


class TestLLMExceptions:
    """测试 LLM 异常"""

    def test_llm_exception(self):
        """测试 LLM 异常"""
        exc = LLMException(message="调用失败", model_name="qwen-plus")
        assert exc.error_code == ErrorCode.LLM_API_ERROR
        assert exc.details.get('model_name') == "qwen-plus"

    def test_llm_timeout_exception(self):
        """测试 LLM 超时异常"""
        exc = LLMTimeoutException(message="超时")
        assert exc.error_code == ErrorCode.LLM_TIMEOUT
        assert isinstance(exc, LLMException)

    def test_llm_quota_exception(self):
        """测试 LLM 配额异常"""
        exc = LLMQuotaException(message="配额不足")
        assert exc.error_code == ErrorCode.LLM_QUOTA_EXCEEDED
        assert isinstance(exc, LLMException)


class TestConfigurationExceptions:
    """测试配置异常"""

    def test_configuration_exception(self):
        """测试配置异常"""
        exc = ConfigurationException(message="配置错误", config_key="API_KEY")
        assert exc.error_code == ErrorCode.CONFIGURATION_ERROR
        assert exc.details.get('config_key') == "API_KEY"

    def test_dependency_exception(self):
        """测试依赖异常"""
        exc = DependencyException(message="依赖缺失", dependency_name="chromadb")
        assert exc.error_code == ErrorCode.DEPENDENCY_MISSING
        assert isinstance(exc, ConfigurationException)
        assert exc.details.get('dependency_name') == "chromadb"


class TestConcurrencyExceptions:
    """测试并发异常"""

    def test_concurrency_exception(self):
        """测试并发异常"""
        exc = ConcurrencyException(message="并发错误", operation="kb_rebuild")
        assert exc.error_code == ErrorCode.SYSTEM_BUSY
        assert exc.details.get('operation') == "kb_rebuild"

    def test_lock_timeout_exception(self):
        """测试锁超时异常"""
        exc = LockTimeoutException(message="锁超时")
        assert exc.error_code == ErrorCode.SYSTEM_BUSY
        assert isinstance(exc, ConcurrencyException)


class TestHandleException:
    """测试异常处理函数"""

    def test_handle_custom_exception(self):
        """测试处理自定义异常"""
        exc = CacheException(message="缓存错误")
        result = handle_exception(exc, logger=None, context="测试")
        assert result is exc

    def test_handle_standard_exception_no_reraise(self):
        """测试处理标准异常（不重新抛出）"""
        exc = ValueError("标准错误")
        result = handle_exception(exc, logger=None)
        assert isinstance(result, RumorJudgeException)
        # 现在会推断错误码
        assert result.error_code is not None

    def test_handle_standard_exception_reraise(self):
        """测试处理标准异常（重新抛出）"""
        exc = ValueError("标准错误")
        with pytest.raises(RumorJudgeException):
            handle_exception(exc, logger=None, reraise=True)


class TestCreateExceptionFromError:
    """测试从错误代码创建异常"""

    def test_create_from_error_code_enum(self):
        """测试从 ErrorCode 枚举创建"""
        exc = create_exception_from_error(ErrorCode.LLM_TIMEOUT, "超时错误")
        assert isinstance(exc, LLMException)
        assert exc.error_code == ErrorCode.LLM_TIMEOUT

    def test_create_cache_exception(self):
        """测试创建缓存异常"""
        exc = create_exception_from_error("CacheException", message="缓存错误")
        assert isinstance(exc, CacheException)
        assert exc.message == "缓存错误"

    def test_create_retrieval_exception(self):
        """测试创建检索异常"""
        exc = create_exception_from_error("RetrievalException", message="检索错误")
        assert isinstance(exc, RetrievalException)

    def test_create_with_details(self):
        """测试创建带详情的异常"""
        details = {"key": "value"}
        exc = create_exception_from_error("CacheException", message="缓存错误", details=details)
        assert exc.details == details

    def test_create_unknown_error_code(self):
        """测试创建未知错误代码"""
        with pytest.raises(ValueError, match="未知"):
            create_exception_from_error("UnknownException", message="错误")
