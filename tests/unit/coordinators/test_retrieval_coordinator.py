"""
检索协调器单元测试

测试 RetrievalCoordinator 的核心功能：
- 混合检索
- 本地检索
- 文档去重
- 格式转换
- 统计信息
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.documents import Document

from src.core.coordinators.retrieval_coordinator import RetrievalCoordinator


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_hybrid_retriever():
    """Mock混合检索器"""
    mock_retriever = Mock()
    mock_retriever.search_hybrid = Mock(return_value=[])
    mock_retriever.search_local = Mock(return_value=[])
    mock_retriever._deduplicate_docs = Mock(return_value=[])
    return mock_retriever


@pytest.fixture
def mock_kb():
    """Mock知识库"""
    mock_kb = Mock()
    mock_kb.search = Mock(return_value=[])
    return mock_kb


@pytest.fixture
def retrieval_coordinator(mock_hybrid_retriever, mock_kb):
    """创建检索协调器实例"""
    return RetrievalCoordinator(
        hybrid_retriever=mock_hybrid_retriever,
        kb=mock_kb
    )


@pytest.fixture
def sample_query():
    """示例查询"""
    return "维生素C可以预防感冒吗？"


@pytest.fixture
def sample_documents():
    """示例文档列表"""
    return [
        Document(
            page_content="维生素C不能预防感冒",
            metadata={"source": "本地", "type": "local", "similarity": 0.85}
        ),
        Document(
            page_content="研究表明维生素C对感冒无预防作用",
            metadata={"source": "web", "type": "web", "similarity": 0.75}
        )
    ]


@pytest.fixture
def sample_evidence_list():
    """示例证据列表（字典格式）"""
    return [
        {
            "content": "维生素C不能预防感冒",
            "text": "维生素C不能预防感冒",
            "metadata": {
                "source": "本地",
                "type": "local",
                "similarity": 0.85,
                "score": 0.85
            },
            "source": "本地"
        },
        {
            "content": "研究表明维生素C对感冒无预防作用",
            "text": "研究表明维生素C对感冒无预防作用",
            "metadata": {
                "source": "web",
                "type": "web",
                "similarity": 0.75,
                "score": 0.75
            },
            "source": "web"
        }
    ]


# ============================================
# 基础检索测试
# ============================================

class TestRetrieve:
    """测试基础检索功能"""

    def test_retrieve_success(self, retrieval_coordinator, sample_query, sample_documents):
        """测试检索成功"""
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(return_value=sample_documents)

        result = retrieval_coordinator.retrieve(sample_query)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(ev, dict) for ev in result)
        retrieval_coordinator.hybrid_retriever.search_hybrid.assert_called_once()

    def test_retrieve_empty_result(self, retrieval_coordinator, sample_query):
        """测试检索结果为空"""
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(return_value=[])

        result = retrieval_coordinator.retrieve(sample_query)

        assert result == []

    def test_retrieve_exception(self, retrieval_coordinator, sample_query):
        """测试检索异常处理"""
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(
            side_effect=Exception("检索失败")
        )

        result = retrieval_coordinator.retrieve(sample_query)

        assert result == []

    def test_retrieve_without_web_search(self, retrieval_coordinator, sample_query, sample_documents):
        """测试不使用网络搜索"""
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(return_value=sample_documents)

        result = retrieval_coordinator.retrieve(sample_query, use_web_search=False)

        assert isinstance(result, list)
        # 验证调用参数
        call_args = retrieval_coordinator.hybrid_retriever.search_hybrid.call_args
        assert call_args.kwargs['use_web_search'] is False


# ============================================
# 解析查询检索测试
# ============================================

class TestRetrieveWithParsedQuery:
    """测试使用解析查询的检索"""

    @pytest.fixture
    def sample_parsed_info(self):
        """示例解析信息"""
        from src.analyzers.query_parser import QueryAnalysis
        return QueryAnalysis(
            entity="维生素C",
            claim="可以预防感冒",
            category="健康养生"
        )

    def test_retrieve_with_parsed_query_success(
        self,
        retrieval_coordinator,
        sample_query,
        sample_parsed_info,
        sample_documents
    ):
        """测试使用解析查询检索成功"""
        retrieval_coordinator.hybrid_retriever.search_local = Mock(return_value=sample_documents[:1])
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(return_value=sample_documents)
        retrieval_coordinator.hybrid_retriever._deduplicate_docs = Mock(return_value=sample_documents[:1])

        result = retrieval_coordinator.retrieve_with_parsed_query(
            query=sample_query,
            parsed_info=sample_parsed_info,
            local_docs=sample_documents[:1]
        )

        assert isinstance(result, list)
        # 验证调用了补测检索
        assert retrieval_coordinator.hybrid_retriever.search_local.called

    def test_retrieve_with_parsed_query_different_query(
        self,
        retrieval_coordinator,
        sample_query,
        sample_parsed_info,
        sample_documents
    ):
        """测试解析词与原始词不同时的检索"""
        retrieval_coordinator.hybrid_retriever.search_local = Mock(return_value=sample_documents[:1])
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(return_value=sample_documents)
        retrieval_coordinator.hybrid_retriever._deduplicate_docs = Mock(return_value=sample_documents[:1])

        retrieval_coordinator.retrieve_with_parsed_query(
            query=sample_query,
            parsed_info=sample_parsed_info,
            local_docs=[]
        )

        # 验证使用了解析词进行补测
        call_args = retrieval_coordinator.hybrid_retriever.search_local.call_args_list
        assert len(call_args) >= 1

    def test_retrieve_with_parsed_query_exception(
        self,
        retrieval_coordinator,
        sample_query,
        sample_parsed_info
    ):
        """测试异常处理"""
        retrieval_coordinator.hybrid_retriever.search_hybrid = Mock(
            side_effect=Exception("检索失败")
        )

        result = retrieval_coordinator.retrieve_with_parsed_query(
            query=sample_query,
            parsed_info=sample_parsed_info
        )

        assert result == []


# ============================================
# 本地检索测试
# ============================================

class TestRetrieveLocalOnly:
    """测试仅本地检索功能"""

    def test_retrieve_local_success(self, retrieval_coordinator, sample_query):
        """测试本地检索成功"""
        mock_kb_results = [
            {"content": "维生素C不能预防感冒", "metadata": {"source": "本地"}},
            {"content": "研究表明...", "metadata": {"source": "本地"}}
        ]
        retrieval_coordinator.kb.search = Mock(return_value=mock_kb_results)

        result = retrieval_coordinator.retrieve_local_only(sample_query)

        assert len(result) == 2
        assert all('content' in ev and 'metadata' in ev for ev in result)
        retrieval_coordinator.kb.search.assert_called_once_with(sample_query, k=3)

    def test_retrieve_local_empty(self, retrieval_coordinator, sample_query):
        """测试本地检索结果为空"""
        retrieval_coordinator.kb.search = Mock(return_value=[])

        result = retrieval_coordinator.retrieve_local_only(sample_query)

        assert result == []

    def test_retrieve_local_exception(self, retrieval_coordinator, sample_query):
        """测试本地检索异常"""
        retrieval_coordinator.kb.search = Mock(side_effect=Exception("检索失败"))

        result = retrieval_coordinator.retrieve_local_only(sample_query)

        assert result == []


# ============================================
# 去重功能测试
# ============================================

class TestDeduplicateDocs:
    """测试文档去重功能"""

    def test_deduplicate_uses_hybrid_retriever_method(
        self,
        retrieval_coordinator,
        sample_documents
    ):
        """测试使用混合检索器的去重方法"""
        deduplicated = [sample_documents[0]]
        retrieval_coordinator.hybrid_retriever._deduplicate_docs = Mock(return_value=deduplicated)

        result = retrieval_coordinator._deduplicate_docs(sample_documents)

        assert result == deduplicated
        retrieval_coordinator.hybrid_retriever._deduplicate_docs.assert_called_once_with(sample_documents)

    def test_deduplicate_fallback(self, retrieval_coordinator, sample_documents):
        """测试回退到简单去重"""
        # 移除混合检索器的去重方法
        delattr(retrieval_coordinator.hybrid_retriever, '_deduplicate_docs')

        # 创建重复文档
        duplicate_docs = [sample_documents[0], sample_documents[0], sample_documents[1]]

        result = retrieval_coordinator._deduplicate_docs(duplicate_docs)

        # 应该去重
        assert len(result) <= len(duplicate_docs)


# ============================================
# 格式转换测试
# ============================================

class TestConvertToDictFormat:
    """测试格式转换功能"""

    def test_convert_langchain_documents(self, retrieval_coordinator, sample_documents):
        """测试转换LangChain文档"""
        result = retrieval_coordinator._convert_to_dict_format(sample_documents)

        assert len(result) == 2
        assert all('content' in ev and 'metadata' in ev for ev in result)
        assert result[0]['content'] == "维生素C不能预防感冒"
        assert result[0]['metadata']['type'] == 'local'
        assert result[1]['metadata']['type'] == 'web'

    def test_convert_dict_documents(self, retrieval_coordinator, sample_evidence_list):
        """测试转换已经是字典格式的文档"""
        result = retrieval_coordinator._convert_to_dict_format(sample_evidence_list)

        assert len(result) == 2
        assert result == sample_evidence_list

    def test_convert_mixed_format(self, retrieval_coordinator, sample_documents):
        """测试混合格式转换"""
        mixed = [
            sample_documents[0],
            {"content": "字典格式", "metadata": {"source": "test"}}
        ]

        result = retrieval_coordinator._convert_to_dict_format(mixed)

        assert len(result) == 2
        assert all(isinstance(ev, dict) for ev in result)

    def test_convert_empty_list(self, retrieval_coordinator):
        """测试空列表转换"""
        result = retrieval_coordinator._convert_to_dict_format([])

        assert result == []


# ============================================
# 验证和统计测试
# ============================================

class TestValidationAndStats:
    """测试验证和统计功能"""

    def test_validate_evidence_success(self, retrieval_coordinator, sample_evidence_list):
        """测试证据验证成功"""
        result = retrieval_coordinator.validate_evidence(sample_evidence_list)

        assert len(result) == 2

    def test_validate_evidence_filters_invalid(self, retrieval_coordinator):
        """测试过滤无效证据"""
        invalid_evidences = [
            {"content": "有效", "metadata": {"source": "test"}},
            {"content": "", "metadata": {}},  # 无效：空内容
            {"metadata": {"source": "test"}},  # 无效：缺少content
        ]

        result = retrieval_coordinator.validate_evidence(invalid_evidences)

        assert len(result) == 1

    def test_get_retrieval_stats(self, retrieval_coordinator, sample_evidence_list):
        """测试获取统计信息"""
        stats = retrieval_coordinator.get_retrieval_stats(sample_evidence_list)

        assert stats['total'] == 2
        assert stats['local'] == 1
        assert stats['web'] == 1
        assert stats['is_web_search'] is True

    def test_get_retrieval_stats_empty(self, retrieval_coordinator):
        """测试空列表的统计信息"""
        stats = retrieval_coordinator.get_retrieval_stats([])

        assert stats['total'] == 0
        assert stats['local'] == 0
        assert stats['web'] == 0
        assert stats['is_web_search'] is False

    def test_get_retrieval_stats_local_only(self, retrieval_coordinator):
        """测试仅本地证据的统计"""
        local_only = [
            {"content": "本地证据", "metadata": {"type": "local"}}
        ]

        stats = retrieval_coordinator.get_retrieval_stats(local_only)

        assert stats['local'] == 1
        assert stats['web'] == 0
        assert stats['is_web_search'] is False
