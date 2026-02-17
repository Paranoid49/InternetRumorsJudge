import hashlib
import logging
import os
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict
from diskcache import Cache
from langchain_chroma import Chroma

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.analyzers.truth_summarizer import FinalVerdict
from src import config

# 导入版本管理器（强制要求，确保缓存一致性）
# 使用延迟导入避免循环依赖
def _get_version_manager_classes():
    from src.core.version_manager import VersionManager, KnowledgeVersion
    return VersionManager, KnowledgeVersion

logger = logging.getLogger("CacheManager")


class LRUCache:
    """
    [v1.1.0] 线程安全的 LRU 缓存

    用于热点查询的快速访问层。
    """

    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.capacity:
                    self.cache.popitem(last=False)
            self.cache[key] = value

    def delete(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    def clear(self):
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict:
        with self.lock:
            total = self.hits + self.misses
            return {
                'size': len(self.cache),
                'capacity': self.capacity,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': self.hits / total if total > 0 else 0
            }

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

    [v1.1.0] 增强版：
    - 添加 LRU 热点缓存层
    - 查询频率统计
    - 缓存预热支持
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

        # [v1.1.0] 热点 LRU 缓存层
        self._hot_cache = LRUCache(capacity=500)

        # [v1.1.0] 查询频率统计
        self._query_frequency: Dict[str, int] = {}
        self._frequency_lock = threading.RLock()
        self._hot_threshold = 3  # 查询次数 >= 3 视为热点

        # 初始化版本管理器（强制要求，确保缓存一致性）
        self._version_manager = None
        self._current_kb_version = None
        self._version_lock = threading.Lock()  # 版本检查锁

        # 延迟导入并强制启用版本管理器
        VersionManager, _ = _get_version_manager_classes()
        storage_base = project_root / "storage"
        self._version_manager = VersionManager(base_dir=storage_base)
        self._current_kb_version = self._version_manager.get_current_version()

        if self._current_kb_version:
            logger.info(f"缓存管理器已启用版本感知: {self._current_kb_version.version_id}")
        else:
            logger.info("缓存管理器已启用版本感知: 首次构建，暂无版本信息")

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

        [v1.1.0] 新增热点缓存层：
        查询顺序：
        1. 精确匹配缓存
        2. 热点 LRU 缓存
        3. 语义向量缓存

        新增：检查知识库版本一致性，如果版本不匹配则缓存失效
        """
        # 记录查询频率
        self._record_query_frequency(query)

        # 检查知识库版本是否变化
        if self._is_version_changed():
            logger.info("知识库版本已变化，缓存已失效")
            # 版本变化时重置热点缓存
            self._hot_cache.clear()
            return None

        key = self._generate_key(query)

        # 1. 首先尝试精确匹配（极速）
        data = self.cache.get(key)

        if data:
            # 再次检查缓存条目的版本（防御性检查）
            if self._is_cache_version_valid(data):
                logger.info(f"精确命中缓存: '{query}'")
                # 同步到热点缓存
                self._hot_cache.set(key, data)
                return self._to_verdict(data)
            else:
                logger.info(f"缓存版本过期，失效: '{query}'")
                # 删除过期缓存
                self.cache.delete(key)
                self._hot_cache.delete(key)

        # 2. [v1.1.0] 尝试热点 LRU 缓存
        hot_cached = self._hot_cache.get(key)
        if hot_cached:
            if self._is_cache_version_valid(hot_cached):
                logger.info(f"热点缓存命中: '{query}'")
                # 同步到精确缓存
                self.cache.set(key, hot_cached, expire=self.default_ttl)
                return self._to_verdict(hot_cached)
            else:
                # 热点缓存版本过期，删除
                self._hot_cache.delete(key)

        # 3. 尝试语义匹配（如果配置了 embeddings）
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
                            # 更新热点缓存
                            self._hot_cache.set(key, semantic_data)
                            # 更新精确缓存
                            self.cache.set(key, semantic_data, expire=self.default_ttl)
                            return self._to_verdict(semantic_data)
                        else:
                            logger.info(f"语义缓存版本过期，失效")
            except Exception as e:
                logger.error(f"语义缓存检索出错: {e}")

        return None

    def _record_query_frequency(self, query: str):
        """[v1.1.0] 记录查询频率"""
        key = self._generate_key(query)
        with self._frequency_lock:
            self._query_frequency[key] = self._query_frequency.get(key, 0) + 1

    def _is_hot_query(self, query: str) -> bool:
        """[v1.1.0] 判断是否为热点查询"""
        key = self._generate_key(query)
        with self._frequency_lock:
            return self._query_frequency.get(key, 0) >= self._hot_threshold

    def _to_verdict(self, data: dict) -> Optional[FinalVerdict]:
        try:
            return FinalVerdict(**data)
        except Exception as e:
            logger.warning(f"缓存反序列化失败: {e}")
            return None

    def _is_version_changed(self) -> bool:
        """
        检查知识库版本是否变化（线程安全）

        边界情况处理：
        - 首次构建：None -> 有版本，视为变化（需要清空旧缓存）
        - 版本更新：旧版本 -> 新版本，视为变化
        - 无版本文件：视为无变化（使用 TTL 机制）
        - 版本管理器不可用：视为无变化（防御性处理）
        """
        with self._version_lock:
            # 防御性检查：版本管理器不可用时，认为版本未变化
            if self._version_manager is None:
                return False

            current_version = self._version_manager.get_current_version()

            # 获取版本ID用于比较
            old_version_id = self._current_kb_version.version_id if self._current_kb_version else None
            new_version_id = current_version.version_id if current_version else None

            # 版本变化检测
            if old_version_id != new_version_id:
                if new_version_id:
                    logger.info(f"知识库版本变化: {old_version_id or 'None'} -> {new_version_id}")
                else:
                    logger.info(f"知识库版本变化: {old_version_id or 'None'} -> None")

                # 更新当前版本
                self._current_kb_version = current_version

                # 首次构建时（None -> 有版本），需要清空旧缓存
                if old_version_id is None and new_version_id is not None:
                    logger.info("检测到首次构建后的版本初始化，旧缓存将失效")
                    return True

                return True

            return False

    def _is_cache_version_valid(self, cached_data: dict) -> bool:
        """
        检查缓存条目的版本是否有效

        边界情况处理：
        - 缓存无版本号 + 当前无版本：有效（首次构建前）
        - 缓存无版本号 + 当前有版本：无效（首次构建后的旧缓存）
        - 缓存有版本号 + 版本不匹配：无效（版本更新后的旧缓存）
        - 缓存有版本号 + 版本匹配：有效
        - 版本管理器不可用：认为有效（防御性处理）
        """
        # 防御性检查：版本管理器不可用时，认为缓存有效
        if self._version_manager is None:
            return True

        current_version = self._version_manager.get_current_version()
        current_version_id = current_version.version_id if current_version else None

        # 缓存中没有版本信息（旧版本缓存）
        if "kb_version" not in cached_data:
            if current_version_id:
                logger.debug("缓存条目缺少版本信息，认为是旧版本缓存（首次构建前）")
                return False
            # 首次构建前，无版本号时认为有效
            return True

        # 检查版本是否匹配
        cached_version = cached_data.get("kb_version")
        if cached_version != current_version_id:
            logger.debug(f"缓存版本不匹配: cached={cached_version}, current={current_version_id}")
            return False

        return True

    def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
        """
        缓存裁决结果并存入语义索引

        [v1.1.0] 新增：
        - 热点查询存入热点缓存
        - 记录查询频率

        新增：存储时附带知识库版本信息
        改进：处理首次构建时无版本的边界情况
        """
        if not verdict:
            return

        key = self._generate_key(query)
        data = verdict.model_dump()
        expire = ttl or self.default_ttl

        # 添加知识库版本信息（如果存在）
        # 首次构建前可能没有版本信息，这是正常的
        if self._current_kb_version:
            data["kb_version"] = self._current_kb_version.version_id
            logger.debug(f"缓存已绑定版本: {self._current_kb_version.version_id}")
        else:
            logger.debug("当前无知识库版本，缓存未绑定版本信息（首次构建前）")

        # 1. 存入精确匹配缓存
        self.cache.set(key, data, expire=expire)

        # 2. [v1.1.0] 如果是热点查询，存入热点缓存
        if self._is_hot_query(query):
            self._hot_cache.set(key, data)
            logger.debug(f"热点查询已缓存: '{query[:30]}...'")

        # 3. 存入语义向量库（如果配置了 embeddings 且不存在高度相似的记录）
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
                    # 添加版本信息到语义缓存（如果存在）
                    if self._current_kb_version:
                        metadata["kb_version"] = self._current_kb_version.version_id

                    self.vector_cache.add_texts(
                        texts=[query],
                        metadatas=[metadata]
                    )
            except Exception as e:
                logger.error(f"语义缓存存入失败: {e}")

    def warm_up(self, queries: list):
        """
        [v1.1.0] 缓存预热

        预先加载已知的热点查询结果到热点缓存。

        Args:
            queries: 查询列表
        """
        logger.info(f"开始缓存预热: {len(queries)} 条查询")

        loaded = 0
        for query in queries:
            try:
                key = self._generate_key(query)
                data = self.cache.get(key)
                if data and self._is_cache_version_valid(data):
                    self._hot_cache.set(key, data)
                    loaded += 1
            except Exception as e:
                logger.warning(f"预热失败: {query[:30]}... - {e}")

        logger.info(f"缓存预热完成: 加载 {loaded}/{len(queries)} 条到热点缓存")

    def get_cache_stats(self) -> Dict:
        """
        [v1.1.0] 获取缓存统计

        Returns:
            缓存统计信息
        """
        hot_stats = self._hot_cache.get_stats()

        with self._frequency_lock:
            total_queries = sum(self._query_frequency.values())
            hot_queries = sum(1 for freq in self._query_frequency.values() if freq >= self._hot_threshold)

        return {
            'hot_cache': hot_stats,
            'query_frequency': {
                'total_queries': total_queries,
                'unique_queries': len(self._query_frequency),
                'hot_queries': hot_queries
            }
        }

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self._hot_cache.clear()
        if self._vector_cache:
            # Chroma 无法直接 clear，通常通过删除目录或 collection 处理
            import shutil
            if os.path.exists(self.vector_cache_dir):
                shutil.rmtree(self.vector_cache_dir)
            self._vector_cache = None

    def clear_stale_cache(self):
        """
        清理过期缓存（版本不匹配的缓存）

        遍历缓存中的所有条目，删除版本不匹配的条目
        注意：这个操作可能比较耗时，建议在后台执行
        """
        stale_keys = []
        total_checked = 0

        # 遍历缓存中的所有键
        for key in self.cache:
            total_checked += 1
            data = self.cache.get(key)
            if data and not self._is_cache_version_valid(data):
                stale_keys.append(key)
                logger.debug(f"发现过期缓存: {key}")

        # 删除过期缓存
        if stale_keys:
            logger.info(f"清理 {len(stale_keys)} 个过期缓存条目（共检查 {total_checked} 个）")
            for key in stale_keys:
                self.cache.delete(key)
        else:
            logger.info(f"未发现过期缓存（共检查 {total_checked} 个）")

        return len(stale_keys)

    def close(self):
        """关闭缓存连接"""
        self.cache.close()
