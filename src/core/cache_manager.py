import hashlib
import logging
import os
import sys
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from diskcache import Cache
from langchain_chroma import Chroma

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.analyzers.truth_summarizer import FinalVerdict
from src import config

# 导入版本管理器（可选）
try:
    from src.core.version_manager import VersionManager, KnowledgeVersion
except ImportError:
    VersionManager = None
    KnowledgeVersion = None

logger = logging.getLogger("CacheManager")

class CacheManager:
    """
    缓存管理器（线程安全）

    功能：
    1. 精确匹配缓存
    2. 语义相似度缓存
    3. 版本感知缓存失效

    [v0.3.0 升级] 线程安全改进：
    - vector_cache延迟初始化使用锁保护
    - 版本检查使用锁保护
    """

    def __init__(self, cache_dir: str = None, vector_cache_dir: str = None, embeddings: Any = None):
        # 获取项目根目录
        project_root = Path(__file__).resolve().parent.parent.parent

        # 默认路径使用项目根目录下的 storage/
        if cache_dir is None:
            cache_dir = str(project_root / "storage" / "cache")
        if vector_cache_dir is None:
            vector_cache_dir = str(project_root / "storage" / "semantic_cache")

        self.cache = Cache(cache_dir)
        # 从 config 读取默认缓存过期时间
        self.default_ttl = getattr(config, 'DEFAULT_CACHE_TTL', 86400)
        self.embeddings = embeddings
        self.vector_cache_dir = vector_cache_dir
        self._vector_cache = None
        self._vector_cache_lock = threading.Lock()  # 向量缓存初始化锁

        # 从 config 读取语义匹配阈值
        self.semantic_threshold = getattr(config, 'SEMANTIC_CACHE_THRESHOLD', 0.96)

        # 初始化版本管理器（支持缓存失效）
        self._version_manager = None
        self._current_kb_version = None
        self._version_lock = threading.Lock()  # 版本检查锁
        if VersionManager is not None:
            storage_base = project_root / "storage"
            self._version_manager = VersionManager(base_dir=storage_base)
            self._current_kb_version = self._version_manager.get_current_version()
            logger.info(f"缓存管理器已启用版本感知: {self._current_kb_version.version_id if self._current_kb_version else 'None'}")

    @property
    def vector_cache(self) -> Chroma:
        """初始化或获取语义缓存向量库（线程安全）"""
        if self._vector_cache is None and self.embeddings:
            with self._vector_cache_lock:
                # 双重检查
                if self._vector_cache is None and self.embeddings:
                    try:
                        self._vector_cache = Chroma(
                            persist_directory=self.vector_cache_dir,
                            embedding_function=self.embeddings,
                            collection_name="semantic_cache",
                            collection_metadata={"hnsw:space": "cosine"}
                        )
                        logger.info("语义缓存向量库初始化成功")
                    except Exception as e:
                        logger.error(f"语义缓存向量库初始化失败: {e}")
        return self._vector_cache

    def _generate_key(self, query: str) -> str:
        """生成基于查询字符串的唯一键"""
        # 规范化查询：去除首尾空格，转小写
        normalized_query = query.strip().lower()
        return hashlib.md5(normalized_query.encode('utf-8')).hexdigest()

    def get_verdict(self, query: str) -> Optional[FinalVerdict]:
        """
        尝试获取缓存的裁决结果（支持精确匹配和语义匹配）

        新增：检查知识库版本一致性，如果版本不匹配则缓存失效
        """
        # 检查知识库版本是否变化
        if self._is_version_changed():
            logger.info("知识库版本已变化，缓存已失效")
            # 版本变化时不返回缓存，触发重新查询
            return None

        # 1. 首先尝试精确匹配（极速）
        key = self._generate_key(query)
        data = self.cache.get(key)

        if data:
            # 再次检查缓存条目的版本（防御性检查）
            if self._is_cache_version_valid(data):
                logger.info(f"精确命中缓存: '{query}'")
                return self._to_verdict(data)
            else:
                logger.info(f"缓存版本过期，失效: '{query}'")
                # 删除过期缓存
                self.cache.delete(key)

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
                        if semantic_data and self._is_cache_version_valid(semantic_data):
                            # 为了加速下次匹配，将当前查询也存入精确缓存
                            self.cache.set(key, semantic_data, expire=self.default_ttl)
                            return self._to_verdict(semantic_data)
                        else:
                            logger.info(f"语义缓存版本过期，失效")
            except Exception as e:
                logger.error(f"语义缓存检索出错: {e}")

        return None

    def _to_verdict(self, data: dict) -> Optional[FinalVerdict]:
        try:
            return FinalVerdict(**data)
        except Exception as e:
            logger.warning(f"缓存反序列化失败: {e}")
            return None

    def _is_version_changed(self) -> bool:
        """检查知识库版本是否变化（线程安全）"""
        if not self._version_manager:
            return False

        with self._version_lock:
            current_version = self._version_manager.get_current_version()

            # 版本变化检测
            if self._current_kb_version != current_version:
                if current_version:
                    logger.info(f"知识库版本变化: {self._current_kb_version.version_id if self._current_kb_version else 'None'} -> {current_version.version_id}")
                else:
                    logger.info(f"知识库版本变化: {self._current_kb_version.version_id if self._current_kb_version else 'None'} -> None")

                # 更新当前版本
                self._current_kb_version = current_version
                return True

            return False

    def _is_cache_version_valid(self, cached_data: dict) -> bool:
        """检查缓存条目的版本是否有效"""
        if not self._version_manager:
            return True  # 没有版本管理器，认为缓存有效

        current_version = self._version_manager.get_current_version()

        # 缓存中没有版本信息（旧版本缓存），认为无效
        if "kb_version" not in cached_data:
            if current_version:
                logger.debug("缓存条目缺少版本信息，认为是旧版本缓存")
                return False
            return True  # 没有当前版本，认为有效

        # 检查版本是否匹配
        cached_version = cached_data.get("kb_version")
        current_version_id = current_version.version_id if current_version else None

        if cached_version != current_version_id:
            logger.debug(f"缓存版本不匹配: cached={cached_version}, current={current_version_id}")
            return False

        return True

    def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
        """
        缓存裁决结果并存入语义索引

        新增：存储时附带知识库版本信息
        """
        if not verdict:
            return

        key = self._generate_key(query)
        data = verdict.model_dump()
        expire = ttl or self.default_ttl

        # 添加知识库版本信息
        if self._version_manager and self._current_kb_version:
            data["kb_version"] = self._current_kb_version.version_id
            logger.debug(f"缓存已绑定版本: {self._current_kb_version.version_id}")

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
                    metadata = {
                        "cache_key": key,
                        "timestamp": datetime.now().isoformat()
                    }
                    # 添加版本信息到语义缓存
                    if self._current_kb_version:
                        metadata["kb_version"] = self._current_kb_version.version_id

                    self.vector_cache.add_texts(
                        texts=[query],
                        metadatas=[metadata]
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
