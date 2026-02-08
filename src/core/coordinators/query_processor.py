"""
查询处理器

负责查询的解析和预处理
"""
import logging
import concurrent.futures
from typing import Optional, Tuple
from datetime import datetime

from src.analyzers.query_parser import QueryAnalysis
from src.core.pipeline import PipelineStage
from src.core.coordinators.base import BaseCoordinator

# 导入并行度配置（v0.6.0新增）
try:
    from src.core.parallelism_config import get_parallelism_config
    PARALLELISM_CONFIG_AVAILABLE = True
except ImportError:
    PARALLELISM_CONFIG_AVAILABLE = False

logger = logging.getLogger("QueryProcessor")


class QueryProcessor(BaseCoordinator):
    """
    查询处理器

    职责：
    1. 解析查询（实体、主张、分类）
    2. 缓存检查
    3. 并行执行解析和检索
    4. 查询预处理
    """

    def __init__(self, parser_chain, cache_manager, hybrid_retriever=None):
        """
        初始化查询处理器

        Args:
            parser_chain: 查询解析链
            cache_manager: 缓存管理器
            hybrid_retriever: 混合检索器（可选，用于并行检索）
        """
        super().__init__("QueryProcessor")
        self.parser_chain = parser_chain
        self.cache_manager = cache_manager
        self.hybrid_retriever = hybrid_retriever

    def parse_query(self, query: str) -> Optional[QueryAnalysis]:
        """
        解析查询

        Args:
            query: 原始查询

        Returns:
            QueryAnalysis 对象，解析失败返回 None
        """
        if not self.parser_chain:
            logger.warning("解析器链未初始化，跳过解析")
            return None

        try:
            result = self.parser_chain.invoke({"query": query})
            logger.info(f"查询解析成功: {result.entity} | {result.claim} | {result.category}")
            return result
        except Exception as e:
            logger.error(f"查询解析失败: {e}")
            return None

    def check_cache(self, query: str):
        """
        检查缓存

        Args:
            query: 原始查询

        Returns:
            缓存的裁决结果，未命中返回 None
        """
        try:
            cached_result = self.cache_manager.get_verdict(query)
            if cached_result:
                logger.info(f"缓存命中: {query}")
                return cached_result
            return None
        except Exception as e:
            logger.error(f"缓存检查失败: {e}")
            return None

    def parse_with_parallel_retrieval(
        self,
        query: str
    ) -> Tuple[Optional[QueryAnalysis], list]:
        """
        并行执行查询解析和本地检索（v0.5.1 增强）

        Args:
            query: 原始查询

        Returns:
            (QueryAnalysis, local_documents) 元组
        """
        if not self.parser_chain or not self.hybrid_retriever:
            logger.warning("解析器或检索器未初始化")
            return None, []

        try:
            # [v0.6.0] 使用动态并行度配置
            # 对于2个任务，使用2个worker是合适的
            # 但仍使用配置以保持一致性
            if PARALLELISM_CONFIG_AVAILABLE:
                max_workers = get_parallelism_config().get_adaptive_workers(
                    task_count=2,
                    task_type='retrieval',
                    min_workers=2
                )
            else:
                max_workers = 2

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 任务 1: LLM 解析意图
                parse_future = executor.submit(self.parser_chain.invoke, {"query": query})
                # 任务 2: 原始词直接去本地库查一把（抢跑）
                raw_search_future = executor.submit(self.hybrid_retriever.search_local, query)

                # 等待解析完成
                analysis = parse_future.result()
                logger.info(f"意图解析完成: 实体='{analysis.entity}', 主张='{analysis.claim}'")

                # 获取抢跑检索结果
                local_docs = raw_search_future.result()
                if local_docs:
                    logger.info(f"原始词抢跑检索命中 {len(local_docs)} 条证据")

                return analysis, local_docs

        except Exception as e:
            logger.error(f"并行解析和检索失败: {e}")
            return None, []

    def process(self, query: str, use_cache: bool = True) -> dict:
        """
        处理查询（解析 + 缓存检查）

        Args:
            query: 原始查询
            use_cache: 是否使用缓存

        Returns:
            处理结果字典:
            {
                'parsed': QueryAnalysis or None,
                'cached': FinalVerdict or None,
                'from_cache': bool
            }
        """
        result = {
            'parsed': None,
            'cached': None,
            'from_cache': False
        }

        # 1. 检查缓存
        if use_cache:
            cached = self.check_cache(query)
            if cached:
                result['cached'] = cached
                result['from_cache'] = True
                return result

        # 2. 解析查询
        parsed = self.parse_query(query)
        result['parsed'] = parsed

        return result

