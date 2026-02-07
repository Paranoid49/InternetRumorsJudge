"""
查询处理器单元测试

测试 QueryCoordinator 的核心功能：
- 查询解析
- 缓存检查
- 并行解析和检索
- 查询处理流程
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.core.coordinators.query_processor import QueryProcessor
from src.analyzers.query_parser import QueryAnalysis


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_parser_chain():
    """Mock解析器链"""
    mock_chain = Mock()
    mock_chain.invoke = Mock(return_value=QueryAnalysis(
        entity="维生素C",
        claim="可以预防感冒",
        category="健康养生"
    ))
    return mock_chain


@pytest.fixture
def mock_cache_manager():
    """Mock缓存管理器"""
    mock_cache = Mock()
    mock_cache.get_verdict = Mock(return_value=None)
    mock_cache.set_verdict = Mock()
    return mock_cache


@pytest.fixture
def mock_hybrid_retriever():
    """Mock混合检索器"""
    mock_retriever = Mock()
    mock_retriever.search_local = Mock(return_value=[])
    return mock_retriever


@pytest.fixture
def query_processor(mock_parser_chain, mock_cache_manager, mock_hybrid_retriever):
    """创建查询处理器实例"""
    return QueryProcessor(
        parser_chain=mock_parser_chain,
        cache_manager=mock_cache_manager,
        hybrid_retriever=mock_hybrid_retriever
    )


@pytest.fixture
def sample_query():
    """示例查询"""
    return "维生素C可以预防感冒吗？"


@pytest.fixture
def sample_cached_verdict():
    """示例缓存裁决"""
    from src.analyzers.truth_summarizer import FinalVerdict, VerdictType
    return FinalVerdict(
        verdict=VerdictType.FALSE,
        confidence=90,
        summary="没有科学证据表明维生素C能预防感冒",
        risk_level="低"
    )


# ============================================
# 查询解析测试
# ============================================

class TestParseQuery:
    """测试查询解析功能"""

    def test_parse_query_success(self, query_processor, sample_query):
        """测试成功解析查询"""
        result = query_processor.parse_query(sample_query)

        assert result is not None
        assert isinstance(result, QueryAnalysis)
        assert result.entity == "维生素C"
        assert result.claim == "可以预防感冒"
        assert result.category == "健康养生"
        query_processor.parser_chain.invoke.assert_called_once_with({"query": sample_query})

    def test_parse_query_no_parser(self, mock_cache_manager, mock_hybrid_retriever):
        """测试解析器链未初始化"""
        processor = QueryProcessor(
            parser_chain=None,
            cache_manager=mock_cache_manager,
            hybrid_retriever=mock_hybrid_retriever
        )

        result = processor.parse_query("测试查询")

        assert result is None

    def test_parse_query_exception(self, query_processor, sample_query):
        """测试解析异常处理"""
        query_processor.parser_chain.invoke = Mock(side_effect=Exception("解析失败"))

        result = query_processor.parse_query(sample_query)

        assert result is None


# ============================================
# 缓存检查测试
# ============================================

class TestCheckCache:
    """测试缓存检查功能"""

    def test_check_cache_hit(self, query_processor, sample_query, sample_cached_verdict):
        """测试缓存命中"""
        query_processor.cache_manager.get_verdict = Mock(return_value=sample_cached_verdict)

        result = query_processor.check_cache(sample_query)

        assert result is not None
        assert result.verdict.value == "假"
        assert result.confidence == 90
        query_processor.cache_manager.get_verdict.assert_called_once_with(sample_query)

    def test_check_cache_miss(self, query_processor, sample_query):
        """测试缓存未命中"""
        query_processor.cache_manager.get_verdict = Mock(return_value=None)

        result = query_processor.check_cache(sample_query)

        assert result is None

    def test_check_cache_exception(self, query_processor, sample_query):
        """测试缓存检查异常处理"""
        query_processor.cache_manager.get_verdict = Mock(side_effect=Exception("缓存失败"))

        result = query_processor.check_cache(sample_query)

        assert result is None


# ============================================
# 并行解析和检索测试
# ============================================

class TestParseWithParallelRetrieval:
    """测试并行解析和检索功能"""

    def test_parallel_success(self, query_processor, sample_query):
        """测试并行执行成功"""
        # Mock检索返回结果
        mock_docs = [Mock(page_content="测试证据")]
        query_processor.hybrid_retriever.search_local = Mock(return_value=mock_docs)

        analysis, docs = query_processor.parse_with_parallel_retrieval(sample_query)

        assert analysis is not None
        assert isinstance(analysis, QueryAnalysis)
        assert docs == mock_docs
        query_processor.parser_chain.invoke.assert_called()
        query_processor.hybrid_retriever.search_local.assert_called_once_with(sample_query)

    def test_parallel_no_components(self, mock_cache_manager):
        """测试组件未初始化"""
        processor = QueryProcessor(
            parser_chain=None,
            cache_manager=mock_cache_manager,
            hybrid_retriever=None
        )

        analysis, docs = processor.parse_with_parallel_retrieval("测试")

        assert analysis is None
        assert docs == []

    def test_parallel_exception(self, query_processor, sample_query):
        """测试并行执行异常处理"""
        query_processor.parser_chain.invoke = Mock(side_effect=Exception("并行失败"))

        analysis, docs = query_processor.parse_with_parallel_retrieval(sample_query)

        assert analysis is None
        assert docs == []

    def test_parallel_empty_retrieval(self, query_processor, sample_query):
        """测试检索结果为空"""
        query_processor.hybrid_retriever.search_local = Mock(return_value=[])

        analysis, docs = query_processor.parse_with_parallel_retrieval(sample_query)

        assert analysis is not None
        assert docs == []


# ============================================
# 查询处理流程测试
# ============================================

class TestProcess:
    """测试查询处理流程"""

    def test_process_with_cache_hit(self, query_processor, sample_query, sample_cached_verdict):
        """测试缓存命中时的处理"""
        query_processor.cache_manager.get_verdict = Mock(return_value=sample_cached_verdict)

        result = query_processor.process(sample_query, use_cache=True)

        assert result['cached'] is not None
        assert result['from_cache'] is True
        assert result['parsed'] is None  # 缓存命中时不需要解析

    def test_process_with_cache_miss(self, query_processor, sample_query):
        """测试缓存未命中时的处理"""
        query_processor.cache_manager.get_verdict = Mock(return_value=None)

        result = query_processor.process(sample_query, use_cache=True)

        assert result['cached'] is None
        assert result['from_cache'] is False
        assert result['parsed'] is not None
        assert isinstance(result['parsed'], QueryAnalysis)

    def test_process_without_cache(self, query_processor, sample_query):
        """测试不使用缓存的处理"""
        result = query_processor.process(sample_query, use_cache=False)

        assert result['cached'] is None
        assert result['from_cache'] is False
        assert result['parsed'] is not None

    def test_process_parse_failure(self, query_processor, sample_query):
        """测试解析失败"""
        query_processor.parser_chain.invoke = Mock(side_effect=Exception("解析失败"))
        query_processor.cache_manager.get_verdict = Mock(return_value=None)

        result = query_processor.process(sample_query, use_cache=True)

        assert result['parsed'] is None
        assert result['cached'] is None
        assert result['from_cache'] is False
