"""
协调器基类

提供协调器的公共功能，减少代码重复

[v1.1.0] 增强版：
- 添加线程安全支持
- 增强智能去重（哈希 + 相似度）
- 统一的错误处理
- 更完善的检索统计
"""
import logging
import threading
from typing import List, Dict, Any, Optional, Callable
from abc import ABC
from datetime import datetime

from src import config

# 尝试导入 rapidfuzz 用于相似度计算
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


logger = logging.getLogger("BaseCoordinator")


class BaseCoordinator(ABC):
    """
    协调器基类

    职责：
    1. 提供文档格式转换
    2. 提供智能文档去重功能
    3. 提供证据验证功能
    4. 统一的日志和异常处理模式
    5. 线程安全支持
    """

    def __init__(self, name: str = None):
        """
        初始化协调器基类

        Args:
            name: 协调器名称（用于日志）
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(self.name)
        self._lock = threading.RLock()  # 线程安全锁
        self._dedup_threshold = getattr(config, 'DEDUP_SIMILARITY_THRESHOLD', 0.85)

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
        for i, doc in enumerate(documents):
            try:
                # 处理 LangChain Document 对象
                if hasattr(doc, 'page_content') and hasattr(doc, 'metadata'):
                    metadata = doc.metadata or {}
                    evidences.append({
                        "id": i + 1,
                        "content": doc.page_content,
                        "text": doc.page_content,  # 兼容 evidence_analyzer
                        "metadata": {
                            "source": metadata.get('source', '未知'),
                            "type": metadata.get('type', 'local'),
                            "similarity": metadata.get('similarity', 0.0),
                            "score": metadata.get('score', 0.0),
                            "rank": metadata.get('rank', i + 1)
                        },
                        "source": metadata.get('source', '未知')  # 兼容旧版
                    })
                # 处理已经是字典格式的对象
                elif isinstance(doc, dict):
                    # 确保字典有必要的字段
                    doc_copy = dict(doc)  # 复制以避免修改原对象
                    doc_copy.setdefault('id', i + 1)
                    if 'content' not in doc_copy and 'text' in doc_copy:
                        doc_copy['content'] = doc_copy['text']
                    if 'text' not in doc_copy and 'content' in doc_copy:
                        doc_copy['text'] = doc_copy['content']
                    if 'metadata' not in doc_copy:
                        doc_copy['metadata'] = {
                            "source": doc_copy.get('source', '未知'),
                            "type": doc_copy.get('type', 'local'),
                            "similarity": doc_copy.get('similarity', 0.0)
                        }
                    evidences.append(doc_copy)
                else:
                    self.logger.warning(f"未知的文档格式: {type(doc)}")
            except Exception as e:
                self.logger.error(f"文档转换失败: {e}")

        return evidences

    def _deduplicate_docs(
        self,
        documents: List,
        hybrid_retriever=None,
        use_similarity: bool = True
    ) -> List:
        """
        智能文档去重

        Args:
            documents: 文档列表
            hybrid_retriever: 混合检索器（可选，用于使用其去重功能）
            use_similarity: 是否使用相似度去重（更精确但更慢）

        Returns:
            去重后的文档列表

        策略:
            1. 优先使用混合检索器的去重功能（如果有）
            2. 第一阶段：精确哈希去重
            3. 第二阶段：内容相似度去重（可选）
        """
        if not documents:
            return []

        # 尝试获取混合检索器
        if hybrid_retriever is None and hasattr(self, 'hybrid_retriever'):
            hybrid_retriever = self.hybrid_retriever

        # 使用混合检索器的去重功能
        if hybrid_retriever and hasattr(hybrid_retriever, '_deduplicate_docs'):
            return hybrid_retriever._deduplicate_docs(documents)

        # 第一阶段：精确哈希去重
        seen_hashes = set()
        hash_unique = []

        for doc in documents:
            content = self._get_doc_content(doc)
            content_hash = hash(content[:200].strip())

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                hash_unique.append(doc)

        if not use_similarity:
            self.logger.info(
                f"去重统计: 原始 {len(documents)} -> 哈希去重 {len(hash_unique)}"
            )
            return hash_unique

        # 第二阶段：内容相似度去重
        unique = []

        for doc in hash_unique:
            content = self._get_doc_content(doc).strip()
            is_duplicate = False

            for seen_doc in unique:
                seen_content = self._get_doc_content(seen_doc).strip()[:300]

                similarity = self._calculate_similarity(content[:300], seen_content)

                if similarity > self._dedup_threshold:
                    self.logger.debug(
                        f"发现相似文档，已去重 (相似度: {similarity:.2f})"
                    )
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(doc)

        self.logger.info(
            f"去重统计: 原始 {len(documents)} -> 哈希去重 {len(hash_unique)} -> 最终 {len(unique)}"
        )

        return unique

    def _get_doc_content(self, doc: Any) -> str:
        """从文档中提取内容"""
        if hasattr(doc, 'page_content'):
            return doc.page_content
        elif isinstance(doc, dict):
            return doc.get('text', doc.get('content', doc.get('full_text', '')))
        return str(doc)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if RAPIDFUZZ_AVAILABLE:
            return fuzz.ratio(text1, text2) / 100.0
        else:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, text1, text2).ratio()

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
            if require_content:
                content = ev.get('content') or ev.get('text')
                if not content:
                    self.logger.debug("证据缺少content/text字段或为空，跳过")
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
                'is_web_search': 是否使用了网络搜索,
                'avg_similarity': 平均相似度,
                'sources': 来源统计
            }
        """
        if not evidence_list:
            return {
                'total': 0,
                'local': 0,
                'web': 0,
                'is_web_search': False,
                'avg_similarity': 0.0,
                'sources': {}
            }

        local_count = 0
        web_count = 0
        total_similarity = 0.0
        sources = {}

        for ev in evidence_list:
            metadata = ev.get('metadata', {})

            # 统计来源类型
            doc_type = metadata.get('type', 'local')
            if doc_type == 'local':
                local_count += 1
            else:
                web_count += 1

            # 统计相似度
            similarity = metadata.get('similarity', 0.0)
            if similarity > 0:
                total_similarity += similarity

            # 统计来源
            source = metadata.get('source', '未知')
            sources[source] = sources.get(source, 0) + 1

        avg_similarity = total_similarity / len(evidence_list) if evidence_list else 0.0

        return {
            'total': len(evidence_list),
            'local': local_count,
            'web': web_count,
            'is_web_search': web_count > 0,
            'avg_similarity': round(avg_similarity, 4),
            'sources': sources
        }

    def _safe_operation(
        self,
        operation_name: str,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Any:
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
        start_time = datetime.now()
        try:
            self.logger.info(f"开始执行: {operation_name}")
            result = operation_func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.info(f"完成执行: {operation_name} (耗时: {duration:.0f}ms)")
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.error(f"{operation_name}失败 (耗时: {duration:.0f}ms): {e}")
            return None

    def _safe_operation_with_default(
        self,
        operation_name: str,
        operation_func: Callable,
        default_value: Any = None,
        *args,
        **kwargs
    ) -> Any:
        """
        安全执行操作，失败返回默认值

        Args:
            operation_name: 操作名称
            operation_func: 操作函数
            default_value: 失败时的默认返回值
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            操作结果或默认值
        """
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"{operation_name}失败: {e}")
            return default_value
