import hashlib
import logging
import os
from datetime import datetime
from typing import Optional, Any
from diskcache import Cache
from truth_summarizer import FinalVerdict
from langchain_chroma import Chroma

logger = logging.getLogger("CacheManager")

class CacheManager:
    def __init__(self, cache_dir: str = ".cache", vector_cache_dir: str = "vector_cache", embeddings: Any = None):
        self.cache = Cache(cache_dir)
        # 默认缓存过期时间：24小时 (秒)
        self.default_ttl = 86400 
        self.embeddings = embeddings
        self.vector_cache_dir = vector_cache_dir
        self._vector_cache = None
        self.semantic_threshold = 0.96 # 语义匹配阈值，高于此值认为命中相同问题

    @property
    def vector_cache(self) -> Chroma:
        """初始化或获取语义缓存向量库"""
        if self._vector_cache is None and self.embeddings:
            try:
                self._vector_cache = Chroma(
                    persist_directory=self.vector_cache_dir,
                    embedding_function=self.embeddings,
                    collection_name="semantic_cache",
                    collection_metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.error(f"语义缓存向量库初始化失败: {e}")
        return self._vector_cache

    def _generate_key(self, query: str) -> str:
        """生成基于查询字符串的唯一键"""
        # 规范化查询：去除首尾空格，转小写
        normalized_query = query.strip().lower()
        return hashlib.md5(normalized_query.encode('utf-8')).hexdigest()

    def get_verdict(self, query: str) -> Optional[FinalVerdict]:
        """尝试获取缓存的裁决结果（支持精确匹配和语义匹配）"""
        # 1. 首先尝试精确匹配（极速）
        key = self._generate_key(query)
        data = self.cache.get(key)
        
        if data:
            # 记录一下命中的查询，便于日志查看
            logger.info(f"精确命中缓存: '{query}'")
            return self._to_verdict(data)

        # 2. 尝试语义匹配（如果配置了 embeddings）
        if self.vector_cache:
            try:
                # 检索最相似的已缓存查询
                results = self.vector_cache.similarity_search_with_score(query, k=1)
                if results:
                    doc, distance = results[0]
                    similarity = 1.0 - distance
                    if similarity >= self.semantic_threshold:
                        cached_query = doc.page_content
                        semantic_key = doc.metadata.get("cache_key")
                        logger.info(f"语义命中缓存: '{query}' -> '{cached_query}' (相似度: {similarity:.4f})")
                        
                        semantic_data = self.cache.get(semantic_key)
                        if semantic_data:
                            # 为了加速下次匹配，将当前查询也存入精确缓存
                            self.cache.set(key, semantic_data, expire=self.default_ttl)
                            return self._to_verdict(semantic_data)
            except Exception as e:
                logger.error(f"语义缓存检索出错: {e}")

        return None

    def _to_verdict(self, data: dict) -> Optional[FinalVerdict]:
        try:
            return FinalVerdict(**data)
        except Exception as e:
            logger.warning(f"缓存反序列化失败: {e}")
            return None

    def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
        """缓存裁决结果并存入语义索引"""
        if not verdict:
            return
            
        key = self._generate_key(query)
        data = verdict.model_dump()
        expire = ttl or self.default_ttl
        
        # 1. 存入精确匹配缓存
        self.cache.set(key, data, expire=expire)

        # 2. 存入语义向量库（如果配置了 embeddings 且不存在高度相似的记录）
        if self.vector_cache:
            try:
                # 检查是否已经有极其相似的查询已在向量库中，避免重复添加
                existing = self.vector_cache.similarity_search_with_score(query, k=1)
                should_add = True
                if existing:
                    _, dist = existing[0]
                    if (1.0 - dist) > 0.99: # 几乎完全一样的查询不再重复向量化
                        should_add = False
                
                if should_add:
                    self.vector_cache.add_texts(
                        texts=[query],
                        metadatas=[{"cache_key": key, "timestamp": datetime.now().isoformat()}]
                    )
            except Exception as e:
                logger.error(f"语义缓存存入失败: {e}")

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        if self._vector_cache:
            # Chroma 无法直接 clear，通常通过删除目录或 collection 处理
            import shutil
            if os.path.exists(self.vector_cache_dir):
                shutil.rmtree(self.vector_cache_dir)
            self._vector_cache = None

    def close(self):
        """关闭缓存连接"""
        self.cache.close()
