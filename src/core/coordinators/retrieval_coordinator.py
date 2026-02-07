"""
检索协调器

负责证据检索的协调工作
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.core.pipeline import PipelineStage

logger = logging.getLogger("RetrievalCoordinator")


class RetrievalCoordinator:
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
        try:
            logger.info(f"开始检索: {query}")

            # 使用混合检索器
            documents = self.hybrid_retriever.search_hybrid(
                query=query,
                existing_local_docs=None,  # 可传递已有本地文档
                use_web_search=use_web_search
            )

            # 转换为字典格式
            evidence_list = self._convert_to_dict_format(documents)

            logger.info(f"检索完成，获得 {len(evidence_list)} 条证据")
            return evidence_list

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def retrieve_with_parsed_query(
        self,
        query: str,
        parsed_info: Any,
        local_docs: List = None
    ) -> List[Dict[str, Any]]:
        """
        使用解析后的查询进行检索（v0.5.1 增强）

        Args:
            query: 原始查询
            parsed_info: QueryAnalysis 对象
            local_docs: 已有的本地文档

        Returns:
            证据列表（字典格式）
        """
        try:
            # 如果解析词和原始词不同，用解析词补测本地库
            parsed_query = f"{parsed_info.entity} {parsed_info.claim}" if parsed_info.entity and parsed_info.claim else ""

            if local_docs is None:
                local_docs = []

            if parsed_query and parsed_query != query:
                logger.info(f"尝试解析词补测本地检索: '{parsed_query}'")
                local_docs.extend(self.hybrid_retriever.search_local(parsed_query))

            # 汇总本地结果并去重
            unique_local_docs = self._deduplicate_docs(local_docs)

            # 调用混合检索（传入已有的本地文档，决定是否触发联网）
            search_query = parsed_query if parsed_query else query
            documents = self.hybrid_retriever.search_hybrid(search_query, existing_local_docs=unique_local_docs)

            # 转换为字典格式
            evidence_list = self._convert_to_dict_format(documents)

            logger.info(f"检索完成，获得 {len(evidence_list)} 条证据")
            return evidence_list

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def retrieve_local_only(self, query: str) -> List[Dict[str, Any]]:
        """
        仅本地检索

        Args:
            query: 查询

        Returns:
            证据列表
        """
        try:
            logger.info(f"执行本地检索: {query}")

            # 从知识库检索
            results = self.kb.search(query, k=3)

            # 转换为字典格式
            evidence_list = []
            for doc in results:
                evidence_list.append({
                    'content': doc.get('content', ''),
                    'metadata': doc.get('metadata', {})
                })

            logger.info(f"本地检索完成，获得 {len(evidence_list)} 条证据")
            return evidence_list

        except Exception as e:
            logger.error(f"本地检索失败: {e}")
            return []

    def _deduplicate_docs(self, documents: List) -> List:
        """
        文档去重（v0.5.1 新增）

        Args:
            documents: 文档列表

        Returns:
            去重后的文档列表
        """
        if not documents:
            return []

        # 使用混合检索器的去重功能
        if hasattr(self.hybrid_retriever, '_deduplicate_docs'):
            return self.hybrid_retriever._deduplicate_docs(documents)

        # 简单去重（回退方案）
        seen = set()
        unique = []
        for doc in documents:
            # 使用内容作为去重依据
            content = getattr(doc, 'page_content', str(doc))
            if content not in seen:
                seen.add(content)
                unique.append(doc)
        return unique

    def _convert_to_dict_format(
        self,
        documents: List
    ) -> List[Dict[str, Any]]:
        """
        将文档对象转换为字典格式（v0.5.1 增强）

        Args:
            documents: 文档对象列表

        Returns:
            字典格式的证据列表
        """
        evidences = []
        for doc in documents:
            try:
                # 处理 LangChain Document 对象
                if hasattr(doc, 'page_content') and hasattr(doc, 'metadata'):
                    evidences.append({
                        "content": doc.page_content,
                        "text": doc.page_content,  # 兼容 evidence_analyzer
                        "metadata": {
                            "source": doc.metadata.get('source', '未知'),
                            "type": doc.metadata.get('type', 'local'),
                            "similarity": doc.metadata.get('similarity', 0.0),
                            "score": doc.metadata.get('score', 0.0)
                        },
                        "source": doc.metadata.get('source', '未知')  # 兼容旧版
                    })
                # 处理已经是字典格式的对象
                elif isinstance(doc, dict):
                    evidences.append(doc)
                else:
                    logger.warning(f"未知的文档格式: {type(doc)}")
            except Exception as e:
                logger.error(f"文档转换失败: {e}")

        return evidences

    def validate_evidence(self, evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        验证证据列表

        Args:
            evidence_list: 证据列表

        Returns:
            有效的证据列表
        """
        valid_evidence = []

        for ev in evidence_list:
            # 基本验证
            if isinstance(ev, dict) and 'content' in ev and 'metadata' in ev:
                if ev['content'] and ev['metadata']:
                    valid_evidence.append(ev)

        logger.info(f"证据验证: {len(evidence_list)} -> {len(valid_evidence)}")
        return valid_evidence

    def get_retrieval_stats(self, evidence_list: List[Dict[str, Any]]) -> dict:
        """
        获取检索统计信息（v0.5.1 新增）

        Args:
            evidence_list: 证据列表

        Returns:
            统计信息字典
        """
        local_count = sum(1 for ev in evidence_list if ev.get('metadata', {}).get('type') == 'local')
        web_count = sum(1 for ev in evidence_list if ev.get('metadata', {}).get('type') == 'web')

        return {
            'total': len(evidence_list),
            'local': local_count,
            'web': web_count,
            'is_web_search': web_count > 0
        }
