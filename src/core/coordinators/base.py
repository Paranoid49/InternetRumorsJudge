"""
协调器基类

提供协调器的公共功能，减少代码重复
"""
import logging
from typing import List, Dict, Any, Optional
from abc import ABC

from src.core.exceptions import RetrievalException, CacheException


logger = logging.getLogger("BaseCoordinator")


class BaseCoordinator(ABC):
    """
    协调器基类

    职责：
    1. 提供文档格式转换
    2. 提供文档去重功能
    3. 提供证据验证功能
    4. 统一的日志和异常处理模式
    """

    def __init__(self, name: str = None):
        """
        初始化协调器基类

        Args:
            name: 协调器名称（用于日志）
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(self.name)

    def _convert_to_dict_format(
        self,
        documents: List
    ) -> List[Dict[str, Any]]:
        """
        将文档对象转换为字典格式

        Args:
            documents: 文档对象列表（LangChain Document 或字典）

        Returns:
            字典格式的证据列表

        示例:
            >>> docs = [Document(page_content="内容", metadata={"source": "本地"})]
            >>> result = self._convert_to_dict_format(docs)
            >>> assert result[0]["content"] == "内容"
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
                    # 确保字典有必要的字段
                    if 'content' not in doc and 'text' in doc:
                        doc = dict(doc)  # 复制以避免修改原对象
                        doc['content'] = doc['text']
                    evidences.append(doc)
                else:
                    self.logger.warning(f"未知的文档格式: {type(doc)}")
            except Exception as e:
                self.logger.error(f"文档转换失败: {e}")

        return evidences

    def _deduplicate_docs(self, documents: List, hybrid_retriever=None) -> List:
        """
        文档去重

        Args:
            documents: 文档列表
            hybrid_retriever: 混合检索器（可选，用于使用其去重功能）
                            如果为None，会尝试从子类的self.hybrid_retriever获取

        Returns:
            去重后的文档列表

        策略:
            1. 优先使用混合检索器的去重功能（如果有）
            2. 回退到基于内容哈希的简单去重
        """
        if not documents:
            return []

        # 尝试获取混合检索器
        if hybrid_retriever is None and hasattr(self, 'hybrid_retriever'):
            hybrid_retriever = self.hybrid_retriever

        # 使用混合检索器的去重功能
        if hybrid_retriever and hasattr(hybrid_retriever, '_deduplicate_docs'):
            return hybrid_retriever._deduplicate_docs(documents)

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
        """
        文档去重

        Args:
            documents: 文档列表
            hybrid_retriever: 混合检索器（可选，用于使用其去重功能）

        Returns:
            去重后的文档列表

        策略:
            1. 优先使用混合检索器的去重功能（如果有）
            2. 回退到基于内容哈希的简单去重
        """
        if not documents:
            return []

        # 使用混合检索器的去重功能
        if hybrid_retriever and hasattr(hybrid_retriever, '_deduplicate_docs'):
            return hybrid_retriever._deduplicate_docs(documents)

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

    def validate_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        require_content: bool = True,
        require_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        验证证据列表

        Args:
            evidence_list: 证据列表
            require_content: 是否要求content字段
            require_metadata: 是否要求metadata字段

        Returns:
            有效的证据列表

        验证规则:
            1. 必须是字典类型
            2. 根据参数要求content和metadata字段
            3. 字段不能为空
        """
        valid_evidence = []

        for ev in evidence_list:
            # 基本验证
            if not isinstance(ev, dict):
                self.logger.warning(f"证据格式错误，非字典类型: {type(ev)}")
                continue

            # 内容验证
            if require_content and ('content' not in ev or not ev.get('content')):
                self.logger.debug("证据缺少content字段或为空，跳过")
                continue

            # 元数据验证
            if require_metadata and ('metadata' not in ev or not ev.get('metadata')):
                self.logger.debug("证据缺少metadata字段或为空，跳过")
                continue

            # 通过验证
            valid_evidence.append(ev)

        self.logger.info(f"证据验证: {len(evidence_list)} -> {len(valid_evidence)}")
        return valid_evidence

    def get_retrieval_stats(self, evidence_list: List[Dict[str, Any]]) -> dict:
        """
        获取检索统计信息

        Args:
            evidence_list: 证据列表

        Returns:
            统计信息字典:
            {
                'total': 总证据数,
                'local': 本地证据数,
                'web': 网络证据数,
                'is_web_search': 是否使用了网络搜索
            }
        """
        if not evidence_list:
            return {
                'total': 0,
                'local': 0,
                'web': 0,
                'is_web_search': False
            }

        local_count = sum(
            1 for ev in evidence_list
            if ev.get('metadata', {}).get('type') == 'local'
        )
        web_count = sum(
            1 for ev in evidence_list
            if ev.get('metadata', {}).get('type') == 'web'
        )

        return {
            'total': len(evidence_list),
            'local': local_count,
            'web': web_count,
            'is_web_search': web_count > 0
        }

    def _safe_operation(self, operation_name: str, operation_func, *args, **kwargs):
        """
        安全执行操作的模板方法

        Args:
            operation_name: 操作名称（用于日志）
            operation_func: 操作函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            操作结果，失败返回None
        """
        try:
            self.logger.info(f"开始执行: {operation_name}")
            result = operation_func(*args, **kwargs)
            self.logger.info(f"完成执行: {operation_name}")
            return result
        except Exception as e:
            self.logger.error(f"{operation_name}失败: {e}")
            return None
