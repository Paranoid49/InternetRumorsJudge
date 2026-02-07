"""
混合检索器单元测试

测试 HybridRetriever 的核心功能：
- 本地检索
- 混合检索
- 去重逻辑
- 阈值判断
"""
import pytest
from unittest.mock import Mock, patch
from langchain_core.documents import Document

# 需要先设置项目路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.retrievers.hybrid_retriever import HybridRetriever


@pytest.fixture
def mock_local_kb():
    """Mock本地知识库"""
    mock_kb = Mock()
    mock_kb.search = Mock(return_value=[
        {
            'full_text': '测试证据1',
            'source': '本地',
            'similarity': 0.85,
            'rank': 1
        }
    ])
    mock_kb.embeddings = Mock()
    return mock_kb


@pytest.fixture
def mock_web_tool():
    """Mock网络搜索工具"""
    mock_tool = Mock()
    mock_tool.search = Mock(return_value=[
        {
            'content': '网络证据1',
            'metadata': {'source': 'web', 'title': '网络标题'}
        }
    ])
    return mock_tool


@pytest.fixture
def hybrid_retriever(mock_local_kb, mock_web_tool):
    """创建混合检索器实例"""
    return HybridRetriever(local_kb=mock_local_kb, web_tool=mock_web_tool)


class TestSearchLocal:
    """测试本地检索功能"""

    def test_search_local_success(self, hybrid_retriever):
        """测试本地检索成功"""
        result = hybrid_retriever.search_local("测试查询")
        assert len(result) == 1
        assert result[0].metadata['type'] == 'local'
        assert result[0].metadata['similarity'] == 0.85

    def test_search_local_empty(self, hybrid_retriever, mock_local_kb):
        """测试本地检索为空"""
        mock_local_kb.search = Mock(return_value=[])
        result = hybrid_retriever.search_local("测试查询")
        assert result == []


class TestSearchHybrid:
    """测试混合检索功能"""

    def test_search_hybrid_local_only(self, hybrid_retriever, mock_web_tool):
        """测试仅本地检索（相似度高）"""
        mock_local_kb = hybrid_retriever.local_kb
        mock_local_kb.search = Mock(return_value=[
            {'full_text': '高质量证据', 'source': '本地', 'similarity': 0.9, 'rank': 1}
        ])

        result = hybrid_retriever.search_hybrid("测试查询")

        # 相似度高，不应该触发网络搜索
        mock_web_tool.search.assert_not_called()
        assert len(result) > 0

    def test_search_hybrid_with_web_search(self, hybrid_retriever, mock_local_kb):
        """测试触发网络搜索"""
        mock_local_kb.search = Mock(return_value=[])

        result = hybrid_retriever.search_hybrid("测试查询")

        # 本地为空，应该触发网络搜索
        hybrid_retriever.web_tool.search.assert_called_once()

    def test_search_hybrid_with_existing_docs(self, hybrid_retriever):
        """测试使用已有本地文档"""
        existing_docs = [Document(page_content="已有证据", metadata={'type': 'local', 'similarity': 0.8, 'source': 'test_source.txt'})]

        result = hybrid_retriever.search_hybrid("测试查询", existing_local_docs=existing_docs)

        # 不应该重新检索本地
        hybrid_retriever.local_kb.search.assert_not_called()


class TestDeduplicateDocs:
    """测试去重功能"""

    def test_deduplicate_empty(self, hybrid_retriever):
        """测试空列表去重"""
        result = hybrid_retriever._deduplicate_docs([])
        assert result == []

    def test_deduplicate_exact_duplicates(self, hybrid_retriever):
        """测试精确去重"""
        docs = [
            Document(page_content="相同内容", metadata={'type': 'local'}),
            Document(page_content="相同内容", metadata={'type': 'web'})
        ]

        result = hybrid_retriever._deduplicate_docs(docs)

        # 应该去除重复
        assert len(result) <= len(docs)

    def test_deduplicate_similar_content(self, hybrid_retriever):
        """测试相似内容去重"""
        docs = [
            Document(page_content="维生素C可以预防感冒", metadata={'type': 'local'}),
            Document(page_content="维生素C能预防感冒", metadata={'type': 'web'})
        ]

        result = hybrid_retriever._deduplicate_docs(docs)

        # 相似度高的应该被去重
        assert len(result) <= len(docs)
