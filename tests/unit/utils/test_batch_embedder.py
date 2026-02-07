"""
批量Embedder单元测试

测试 BatchEmbedder 的核心功能：
- 批量Embedding
- 缓存机制
- 线程安全
- 统计信息
"""
import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils.batch_embedder import (
    BatchEmbedder,
    get_batch_embedder,
    reset_global_batch_embedder
)


@pytest.fixture
def mock_embeddings():
    """Mock Embeddings对象"""
    mock_emb = Mock()
    mock_emb.embed_documents = Mock(return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    mock_emb.embed_query = Mock(return_value=[0.1, 0.2, 0.3])
    return mock_emb


@pytest.fixture
def batch_embedder(mock_embeddings):
    """创建BatchEmbedder实例（禁用监控）"""
    return BatchEmbedder(mock_embeddings, enable_monitoring=False)


class TestEmbedTexts:
    """测试批量Embedding功能"""

    def test_embed_texts_basic(self, batch_embedder, mock_embeddings):
        """测试基础批量Embedding"""
        texts = ["文本1", "文本2"]

        result = batch_embedder.embed_texts(texts, use_cache=False)

        assert len(result) == 2
        mock_embeddings.embed_documents.assert_called_once()

    def test_embed_texts_with_cache(self, batch_embedder, mock_embeddings):
        """测试缓存命中"""
        texts = ["文本1", "文本2"]

        # 第一次调用
        result1 = batch_embedder.embed_texts(texts, use_cache=True)
        # 第二次调用（应该命中缓存）
        result2 = batch_embedder.embed_texts(texts, use_cache=True)

        assert len(result1) == 2
        assert len(result2) == 2
        # 应该只调用一次（第二次命中缓存）
        assert mock_embeddings.embed_documents.call_count == 1

    def test_embed_texts_empty_list(self, batch_embedder):
        """测试空列表"""
        result = batch_embedder.embed_texts([])
        assert result == []

    def test_embed_texts_fallback_to_single(self, batch_embedder, mock_embeddings):
        """测试回退到单个计算"""
        mock_embeddings.embed_documents = Mock(side_effect=Exception("批量失败"))
        mock_embeddings.embed_query = Mock(return_value=[0.1, 0.2, 0.3])

        result = batch_embedder.embed_texts(["文本1"], use_cache=False)

        assert len(result) == 1
        mock_embeddings.embed_query.assert_called()


class TestCache:
    """测试缓存功能"""

    def test_cache_hit_increases_counter(self, batch_embedder):
        """测试缓存命中增加计数器"""
        texts = ["测试文本"]

        batch_embedder.embed_texts(texts, use_cache=True)
        batch_embedder.embed_texts(texts, use_cache=True)

        stats = batch_embedder.get_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 1

    def test_clear_cache(self, batch_embedder, mock_embeddings):
        """测试清空缓存"""
        texts = ["测试文本"]

        batch_embedder.embed_texts(texts, use_cache=True)
        assert batch_embedder.get_stats()['cache_size'] > 0

        batch_embedder.clear_cache()
        assert batch_embedder.get_stats()['cache_size'] == 0

    def test_cache_size_limit(self, batch_embedder, mock_embeddings):
        """测试缓存大小限制"""
        # 创建大量不同的文本
        texts = [f"文本{i}" for i in range(1100)]

        batch_embedder.embed_texts(texts, use_cache=True)

        # 缓存应该被限制在1000以内
        stats = batch_embedder.get_stats()
        assert stats['cache_size'] <= 1000


class TestThreadSafety:
    """测试线程安全"""

    def test_concurrent_embed_texts(self, batch_embedder, mock_embeddings):
        """测试并发Embedding"""
        texts = [f"文本{i}" for i in range(10)]

        results = []
        errors = []

        def embed_worker():
            try:
                result = batch_embedder.embed_texts(texts, use_cache=True)
                results.append(len(result))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=embed_worker) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5


class TestGlobalInstance:
    """测试全局单例"""

    def test_get_global_batch_embedder(self, mock_embeddings):
        """测试获取全局实例"""
        reset_global_batch_embedder()

        instance1 = get_batch_embedder(mock_embeddings)
        instance2 = get_batch_embedder()

        assert instance1 is instance2

    def test_reset_global_batch_embedder(self, mock_embeddings):
        """测试重置全局实例"""
        reset_global_batch_embedder()

        instance1 = get_batch_embedder(mock_embeddings)
        reset_global_batch_embedder()

        instance2 = get_batch_embedder(mock_embeddings)

        # 重置后应该是新实例
        assert instance1 is not instance2


class TestStats:
    """测试统计信息"""

    def test_get_stats(self, batch_embedder):
        """测试获取统计信息"""
        stats = batch_embedder.get_stats()

        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'total_requests' in stats
        assert 'hit_rate' in stats
        assert 'cache_size' in stats

    def test_hit_rate_calculation(self, batch_embedder):
        """测试命中率计算"""
        texts = ["测试文本"]

        batch_embedder.embed_texts(texts, use_cache=True)
        batch_embedder.embed_texts(texts, use_cache=True)

        stats = batch_embedder.get_stats()
        expected_hit_rate = 1 / 2  # 1次命中，2次总请求
        assert abs(stats['hit_rate'] - expected_hit_rate) < 0.01


class TestEmbedQuery:
    """测试单个查询Embedding"""

    def test_embed_query(self, batch_embedder):
        """测试单个查询Embedding"""
        result = batch_embedder.embed_query("测试查询", use_cache=False)

        assert isinstance(result, list)
        assert len(result) > 0
