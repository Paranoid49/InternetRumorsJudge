"""
测试统一异常体系
"""
import pytest
from src.core.exceptions import (
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


class TestRumorJudgeException:
    """测试基础异常类"""

    def test_basic_exception(self):
        """测试基本异常"""
        exc = RumorJudgeException("测试错误")
        assert str(exc) == "[RumorJudgeException] 测试错误"
        assert exc.message == "测试错误"
        assert exc.error_code == "RumorJudgeException"

    def test_exception_with_error_code(self):
        """测试带错误代码的异常"""
        exc = RumorJudgeException("测试错误", error_code="TEST_ERROR")
        assert exc.error_code == "TEST_ERROR"
        assert "TEST_ERROR" in str(exc)

    def test_exception_with_details(self):
        """测试带详情的异常"""
        details = {"key": "value"}
        exc = RumorJudgeException("测试错误", details=details)
        assert exc.details == details
        assert "value" in str(exc)

    def test_to_dict(self):
        """测试转换为字典"""
        exc = RumorJudgeException("测试错误", error_code="TEST", details={"key": "value"})
        result = exc.to_dict()
        assert result == {
            'error_code': 'TEST',
            'message': '测试错误',
            'details': {'key': 'value'}
        }


class TestCacheExceptions:
    """测试缓存异常"""

    def test_cache_exception(self):
        """测试缓存异常"""
        exc = CacheException("缓存失败", cache_type="exact_match")
        assert exc.error_code == "CacheException"
        assert exc.details == {'cache_type': 'exact_match'}

    def test_cache_miss_exception(self):
        """测试缓存未命中异常"""
        exc = CacheMissException("未命中缓存")
        assert exc.error_code == "CacheMissException"
        assert isinstance(exc, CacheException)

    def test_cache_stale_exception(self):
        """测试缓存过期异常"""
        exc = CacheStaleException("缓存已过期")
        assert exc.error_code == "CacheStaleException"
        assert isinstance(exc, CacheException)


class TestRetrievalExceptions:
    """测试检索异常"""

    def test_retrieval_exception(self):
        """测试检索异常"""
        exc = RetrievalException("检索失败", retrieval_type="local")
        assert exc.error_code == "RetrievalException"
        assert exc.details == {'retrieval_type': 'local'}

    def test_knowledge_base_exception(self):
        """测试知识库异常"""
        exc = KnowledgeBaseException("知识库错误", kb_version="v1.0")
        assert exc.error_code == "KnowledgeBaseException"
        assert isinstance(exc, RetrievalException)
        assert exc.details == {'kb_version': 'v1.0'}

    def test_web_search_exception(self):
        """测试网络搜索异常"""
        exc = WebSearchException("搜索失败", search_query="测试查询")
        assert exc.error_code == "WebSearchException"
        assert isinstance(exc, RetrievalException)
        assert exc.details == {'search_query': '测试查询'}


class TestAnalysisExceptions:
    """测试分析异常"""

    def test_analysis_exception(self):
        """测试分析异常"""
        exc = AnalysisException("分析失败", analysis_type="evidence_analyze")
        assert exc.error_code == "AnalysisException"
        assert exc.details == {'analysis_type': 'evidence_analyze'}

    def test_query_parse_exception(self):
        """测试查询解析异常"""
        exc = QueryParseException("解析失败", query="测试查询")
        assert exc.error_code == "QueryParseException"
        assert isinstance(exc, AnalysisException)
        assert exc.details == {'analysis_type': 'query_parse', 'query': '测试查询'}

    def test_evidence_analyze_exception(self):
        """测试证据分析异常"""
        exc = EvidenceAnalyzeException("分析失败", evidence_count=5)
        assert exc.error_code == "EvidenceAnalyzeException"
        assert isinstance(exc, AnalysisException)
        assert exc.details == {'evidence_count': 5, 'analysis_type': 'evidence_analyze'}

    def test_verdict_generate_exception(self):
        """测试裁决生成异常"""
        exc = VerdictGenerateException("生成失败")
        assert exc.error_code == "VerdictGenerateException"
        assert isinstance(exc, AnalysisException)


class TestLLMExceptions:
    """测试 LLM 异常"""

    def test_llm_exception(self):
        """测试 LLM 异常"""
        exc = LLMException("调用失败", model_name="qwen-plus")
        assert exc.error_code == "LLMException"
        assert exc.details == {'model_name': 'qwen-plus'}

    def test_llm_timeout_exception(self):
        """测试 LLM 超时异常"""
        exc = LLMTimeoutException("超时")
        assert exc.error_code == "LLMTimeoutException"
        assert isinstance(exc, LLMException)

    def test_llm_quota_exception(self):
        """测试 LLM 配额异常"""
        exc = LLMQuotaException("配额不足")
        assert exc.error_code == "LLMQuotaException"
        assert isinstance(exc, LLMException)


class TestConfigurationExceptions:
    """测试配置异常"""

    def test_configuration_exception(self):
        """测试配置异常"""
        exc = ConfigurationException("配置错误", config_key="API_KEY")
        assert exc.error_code == "ConfigurationException"
        assert exc.details == {'config_key': 'API_KEY'}

    def test_dependency_exception(self):
        """测试依赖异常"""
        exc = DependencyException("依赖缺失", dependency_name="chromadb")
        assert exc.error_code == "DependencyException"
        assert isinstance(exc, ConfigurationException)
        assert exc.details == {'dependency_name': 'chromadb'}


class TestConcurrencyExceptions:
    """测试并发异常"""

    def test_concurrency_exception(self):
        """测试并发异常"""
        exc = ConcurrencyException("并发错误", operation="kb_rebuild")
        assert exc.error_code == "ConcurrencyException"
        assert exc.details == {'operation': 'kb_rebuild'}

    def test_lock_timeout_exception(self):
        """测试锁超时异常"""
        exc = LockTimeoutException("锁超时")
        assert exc.error_code == "LockTimeoutException"
        assert isinstance(exc, ConcurrencyException)


class TestHandleException:
    """测试异常处理函数"""

    def test_handle_custom_exception(self):
        """测试处理自定义异常"""
        exc = CacheException("缓存错误")
        result = handle_exception(exc, logger=None, context="测试")
        assert result is exc
        assert result.error_code == "CacheException"

    def test_handle_standard_exception_no_reraise(self):
        """测试处理标准异常（不重新抛出）"""
        exc = ValueError("标准错误")
        result = handle_exception(exc, logger=None)
        assert isinstance(result, RumorJudgeException)
        assert result.error_code == "ValueError"

    def test_handle_standard_exception_reraise(self):
        """测试处理标准异常（重新抛出）"""
        exc = ValueError("标准错误")
        with pytest.raises(RumorJudgeException) as exc_info:
            handle_exception(exc, logger=None, reraise=True)
        assert exc_info.value.error_code == "ValueError"


class TestCreateExceptionFromError:
    """测试从错误代码创建异常"""

    def test_create_cache_exception(self):
        """测试创建缓存异常"""
        exc = create_exception_from_error("CacheException", "缓存错误")
        assert isinstance(exc, CacheException)
        assert exc.message == "缓存错误"

    def test_create_retrieval_exception(self):
        """测试创建检索异常"""
        exc = create_exception_from_error("RetrievalException", "检索错误")
        assert isinstance(exc, RetrievalException)

    def test_create_with_details(self):
        """测试创建带详情的异常"""
        details = {"key": "value"}
        exc = create_exception_from_error("CacheException", "缓存错误", details)
        assert exc.details == details

    def test_create_unknown_error_code(self):
        """测试创建未知错误代码"""
        with pytest.raises(ValueError, match="未知的错误代码"):
            create_exception_from_error("UnknownException", "错误")
