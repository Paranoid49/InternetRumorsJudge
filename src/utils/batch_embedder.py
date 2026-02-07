"""
批量Embedding处理器

优化多次Embedding调用，减少API请求次数

[v0.3.0 升级] 线程安全改进：
- 全局实例使用线程安全的单例模式
- 缓存访问使用锁保护
- 防止并发初始化问题
"""
import logging
import time
import hashlib
import threading
from typing import List, Dict, Tuple, Optional
from collections import OrderedDict

logger = logging.getLogger("BatchEmbedder")


class BatchEmbedder:
    """
    批量Embedding处理器（线程安全）

    功能：
    1. 缓存已计算的Embedding
    2. 批量提交Embedding请求
    3. 减少API调用次数

    线程安全保证：
    - 使用RLock保护缓存访问
    - 使用Lock保护统计信息更新
    - 支持高并发场景
    """

    def __init__(self, embeddings):
        """
        初始化批量Embedder

        Args:
            embeddings: LangChain Embeddings 对象
        """
        self.embeddings = embeddings
        self.cache = OrderedDict()  # 有序缓存，便于管理
        self._cache_lock = threading.RLock()  # 缓存访问锁

        # 统计信息
        self._cache_hits = 0
        self._cache_misses = 0
        self._stats_lock = threading.Lock()  # 统计信息锁

    def embed_texts(self, texts: List[str], use_cache: bool = True) -> List[List[float]]:
        """
        批量计算文本的Embedding（线程安全）

        Args:
            texts: 文本列表
            use_cache: 是否使用缓存

        Returns:
            Embedding向量列表
        """
        results = []
        uncached_indices = []
        uncached_texts = []

        # 1. 检查缓存（线程安全）
        if use_cache:
            with self._cache_lock:
                for i, text in enumerate(texts):
                    # 使用文本的哈希作为缓存key
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
                    if text_hash in self.cache:
                        results.append((i, self.cache[text_hash]))
                        with self._stats_lock:
                            self._cache_hits += 1
                    else:
                        uncached_indices.append(i)
                        uncached_texts.append(text)
        else:
            # 不使用缓存，全部需要计算
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts

        # 2. 批量计算未缓存的Embedding
        if uncached_texts:
            try:
                # 尝试使用embed_documents（批量）
                logger.info(f"批量计算 {len(uncached_texts)} 个文本的Embedding")
                new_embeddings = self.embeddings.embed_documents(uncached_texts)

                # 存入缓存（线程安全）
                with self._cache_lock:
                    for idx, emb in zip(uncached_indices, new_embeddings):
                        text_hash = hashlib.md5(texts[idx].encode('utf-8')).hexdigest()
                        self.cache[text_hash] = emb

                    with self._stats_lock:
                        self._cache_misses += len(uncached_texts)

                    # 限制缓存大小（防止内存泄漏）
                    if len(self.cache) > 1000:
                        # 移除最旧的100个
                        for _ in range(100):
                            self.cache.popitem(last=False)

                # 添加到结果
                for idx, emb in zip(uncached_indices, new_embeddings):
                    results.append((idx, emb))

            except Exception as e:
                logger.error(f"批量Embedding失败: {e}")
                # 回退到逐个计算
                logger.warning("回退到逐个计算Embedding")
                for idx, text in zip(uncached_indices, uncached_texts):
                    try:
                        emb = self.embeddings.embed_query(text)
                        results.append((idx, emb))
                        with self._stats_lock:
                            self._cache_misses += 1
                    except Exception as e2:
                        logger.error(f"Embedding计算失败: {e2}")
                        # 返回零向量
                        results.append((idx, [0.0] * 1536))  # 假设维度是1536

        # 3. 按顺序返回
        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def embed_query(self, query: str, use_cache: bool = True) -> List[float]:
        """
        单个查询的Embedding（兼容接口）

        Args:
            query: 查询文本
            use_cache: 是否使用缓存

        Returns:
            Embedding向量
        """
        result = self.embed_texts([query], use_cache=use_cache)
        return result[0] if result else []

    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_requests": total,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache)
        }

    def clear_cache(self):
        """清空缓存（线程安全）"""
        with self._cache_lock:
            self.cache.clear()
        logger.info("Embedding缓存已清空")


# 全局BatchEmbedder实例（线程安全的单例）
_global_batch_embedder = None
_global_batch_embedder_lock = threading.Lock()
_global_batch_embedder_initialized = False


def get_batch_embedder(embeddings=None):
    """
    获取全局BatchEmbedder实例（线程安全）

    使用双重检查锁定模式确保线程安全

    Args:
        embeddings: LangChain Embeddings 对象（首次创建时必需）

    Returns:
        全局BatchEmbedder实例
    """
    global _global_batch_embedder, _global_batch_embedder_initialized

    # 快速路径：已初始化则直接返回
    if _global_batch_embedder_initialized:
        return _global_batch_embedder

    # 慢速路径：需要初始化
    with _global_batch_embedder_lock:
        # 双重检查
        if _global_batch_embedder_initialized:
            return _global_batch_embedder

        if _global_batch_embedder is None and embeddings is not None:
            _global_batch_embedder = BatchEmbedder(embeddings)
            _global_batch_embedder_initialized = True
            logger.info("全局BatchEmbedder已创建（线程安全）")
        elif _global_batch_embedder is None:
            logger.warning("无法创建全局BatchEmbedder：未提供embeddings参数")

        return _global_batch_embedder


def reset_global_batch_embedder():
    """重置全局BatchEmbedder实例（主要用于测试）"""
    global _global_batch_embedder, _global_batch_embedder_initialized
    with _global_batch_embedder_lock:
        _global_batch_embedder = None
        _global_batch_embedder_initialized = False
    logger.info("全局BatchEmbedder已重置")
