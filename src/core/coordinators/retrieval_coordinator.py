"""
检索协调器

负责证据检索的协调工作

[v1.1.0] 使用增强版基类功能
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.core.pipeline import PipelineStage
from src.core.coordinators.base import BaseCoordinator

logger = logging.getLogger("RetrievalCoordinator")


class RetrievalCoordinator(BaseCoordinator):
    """
    检索协调器

    职责：
    1. 协调本地检索和网络搜索
    2. 混合检索策略
    3. 证据去重和排序
    4. 格式转换
    """

    def __init__(self, hybrid_retriever, kb):
        """
        初始化检索协调器

        Args:
            hybrid_retriever: 混合检索器
            kb: 知识库实例
        """
        super().__init__("RetrievalCoordinator")
        self.hybrid_retriever = hybrid_retriever
        self.kb = kb

    def retrieve(
        self,
        query: str,
        parsed_info: Optional[Any] = None,
        use_web_search: bool = True
    ) -> List[Dict[str, Any]]:
        """
        执行检索（本地 + 网络）

        Args:
            query: 原始查询
            parsed_info: 解析后的查询信息
            use_web_search: 是否使用网络搜索

        Returns:
            证据列表（字典格式）
        """
        def _do_retrieve():
            # 使用混合检索器
            documents = self.hybrid_retriever.search_hybrid(
                query=query,
                existing_local_docs=None,
                use_web_search=use_web_search
            )
            return self._convert_to_dict_format(documents)

        result = self._safe_operation_with_default(
            f"检索: {query}",
            _do_retrieve,
            default_value=[]
        )

        if result:
            stats = self.get_retrieval_stats(result)
            self.logger.info(f"检索完成: {stats}")

        return result or []

    def retrieve_with_parsed_query(
        self,
        query: str,
        parsed_info: Any,
        local_docs: List = None
    ) -> List[Dict[str, Any]]:
        """
        使用解析后的查询进行检索（v0.5.1 增强，v1.1.0 优化）

        Args:
            query: 原始查询
            parsed_info: QueryAnalysis 对象
            local_docs: 已有的本地文档

        Returns:
            证据列表（字典格式）
        """
        def _do_retrieve():
            # 如果解析词和原始词不同，用解析词补测本地库
            parsed_query = ""
            if parsed_info and hasattr(parsed_info, 'entity') and hasattr(parsed_info, 'claim'):
                if parsed_info.entity and parsed_info.claim:
                    parsed_query = f"{parsed_info.entity} {parsed_info.claim}"

            docs = local_docs if local_docs else []

            if parsed_query and parsed_query != query:
                self.logger.info(f"尝试解析词补测本地检索: '{parsed_query}'")
                docs.extend(self.hybrid_retriever.search_local(parsed_query))

            # 汇总本地结果并去重（使用基类增强的去重功能）
            unique_local_docs = self._deduplicate_docs(docs, use_similarity=True)

            # 调用混合检索
            search_query = parsed_query if parsed_query else query
            documents = self.hybrid_retriever.search_hybrid(search_query, existing_local_docs=unique_local_docs)

            return self._convert_to_dict_format(documents)

        result = self._safe_operation_with_default(
            f"解析词检索: {query}",
            _do_retrieve,
            default_value=[]
        )

        if result:
            stats = self.get_retrieval_stats(result)
            self.logger.info(f"检索完成: {stats}")

        return result or []

    def retrieve_local_only(self, query: str) -> List[Dict[str, Any]]:
        """
        仅本地检索

        Args:
            query: 查询

        Returns:
            证据列表
        """
        def _do_local_retrieve():
            # 从知识库检索
            results = self.kb.search(query, k=3)
            return self._convert_to_dict_format(results)

        result = self._safe_operation_with_default(
            f"本地检索: {query}",
            _do_local_retrieve,
            default_value=[]
        )

        if result:
            self.logger.info(f"本地检索完成，获得 {len(result)} 条证据")

        return result or []

