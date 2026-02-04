import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from difflib import SequenceMatcher

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
from src.retrievers.web_search_tool import WebSearchTool
from src import config

logger = logging.getLogger("HybridRetriever")

class HybridRetriever(BaseRetriever):
    """
    混合检索器：集成项目本地向量库 (RAG) + 实时网络搜索 (Tavily/DDG)。
    
    设计理念：
    1. 优先本地检索：如果本地库有高质量证据（相似度 > 阈值），则优先信任。
    2. 自动联网补齐：如果本地结果置信度低或数量不足，自动触发联网搜索。
    3. 内容去重与标准化：整合两端结果，去重后返回统一的 Document 对象。
    """
    
    local_kb: Any = None
    web_tool: Any = None
    min_local_similarity: float = config.MIN_LOCAL_SIMILARITY  # 从 config 读取：相似度达到阈值即视为本地有高质量证据，不再触发联网
    max_results: int = config.MAX_RESULTS  # 从 config 读取：检索返回的最大证据数量

    def __init__(self, local_kb: EvidenceKnowledgeBase, web_tool: WebSearchTool, **kwargs):
        # BaseRetriever 是 Pydantic 模型，需要通过 super().__init__ 初始化
        super().__init__(local_kb=local_kb, web_tool=web_tool, **kwargs)

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """核心检索逻辑 (LangChain 标准接口)"""
        return self.search_hybrid(query)

    def search_local(self, query: str) -> List[Document]:
        """仅执行本地检索"""
        logger.info(f"仅本地检索: '{query}'")
        local_results = self.local_kb.search(query, k=self.max_results)
        
        local_docs = []
        for res in local_results:
            doc = Document(
                page_content=res['full_text'],
                metadata={
                    "source": res['source'],
                    "similarity": res['similarity'],
                    "type": "local",
                    "rank": res['rank']
                }
            )
            local_docs.append(doc)
        return local_docs

    def search_hybrid(self, query: str, existing_local_docs: List[Document] = None) -> List[Document]:
        """执行混合检索逻辑"""
        logger.info(f"混合检索启动: '{query}'")
        
        # 1. 如果没有传入现成的本地结果，则执行本地检索
        if existing_local_docs is None:
            all_docs = self.search_local(query)
        else:
            all_docs = existing_local_docs
        
        max_similarity = 0.0
        if all_docs:
            # 计算最大相似度时，对自动生成的文档进行降权处理，避免其虚高阻断联网
            weighted_similarities = []
            auto_gen_weight = getattr(config, 'AUTO_GEN_WEIGHT', 0.9)  # 从 config 读取加权系数
            for d in all_docs:
                raw_sim = d.metadata['similarity']
                # 如果是自动生成的内容，应用加权系数
                if "AUTO_GEN_" in d.metadata['source']:
                    raw_sim *= auto_gen_weight
                weighted_similarities.append(raw_sim)
            max_similarity = max(weighted_similarities)
            
        logger.info(f"本地检索完成，最高加权相似度: {max_similarity:.4f}")
        
        # 2. 判断是否需要联网搜索
        should_search_web = (
            len(all_docs) == 0 or 
            max_similarity < self.min_local_similarity
        )
        
        if should_search_web:
            reason = "本地无结果" if len(all_docs) == 0 else f"相似度 {max_similarity:.2f} 低于阈值 {self.min_local_similarity}"
            logger.info(f"触发联网搜索机制 (原因: {reason})")
            web_results = self.web_tool.search(query)
            
            web_docs = []
            for i, res in enumerate(web_results):
                doc = Document(
                    page_content=res['content'],
                    metadata={
                        "source": res['metadata']['source'],
                        "title": res['metadata'].get('title', '联网搜索结果'),
                        "type": "web",
                        "score": res['metadata'].get('score', 0.5), # Tavily 分数或默认值
                        "rank": i + 1
                    }
                )
                web_docs.append(doc)
            
            logger.info(f"联网搜索完成，新增 {len(web_docs)} 条证据。")
            all_docs.extend(web_docs)
        else:
            logger.info(f"本地相似度足够 ({max_similarity:.2f} >= {self.min_local_similarity})，跳过联网搜索。")
        
        # 3. 去重与精选
        unique_docs = self._deduplicate_docs(all_docs)
        if len(unique_docs) < len(all_docs):
            logger.info(f"证据去重完成: {len(all_docs)} -> {len(unique_docs)}")
        
        # 排序：本地高质量优先，然后是联网高质量
        # 这里简单按类型和相似度/分数排序
        def sort_key(doc):
            # 给本地证据一个基础权重，联网证据根据其原始分数
            if doc.metadata['type'] == 'local':
                base_score = doc.metadata['similarity'] + 0.5  # 提升本地证据权重
                # 再次应用降权逻辑，确保排序时自动生成内容排在人工核查内容之后
                if "AUTO_GEN_" in doc.metadata['source']:
                    base_score -= 0.1  # 略微降低排名得分
                return base_score
            return doc.metadata.get('score', 0.5)
            
        sorted_docs = sorted(unique_docs, key=sort_key, reverse=True)
        final_docs = sorted_docs[:self.max_results]
        
        logger.info(f"混合检索最终返回 {len(final_docs)} 条证据。")
        return final_docs

    def _deduplicate_docs(self, docs: List[Document]) -> List[Document]:
        """
        智能去重：结合哈希和内容相似度判断

        策略：
        1. 使用完整内容的哈希进行精确去重
        2. 对剩余文档使用内容相似度进行模糊去重（相似度 > 0.85 视为重复）
        """
        if not docs:
            return []

        # 第一阶段：精确哈希去重
        seen_hashes = set()
        hash_unique = []
        for doc in docs:
            # 使用完整内容的前 500 字符（更长的片段提高准确性）
            content = doc.page_content[:500].strip()
            if not content:
                continue
            h = hash(content)
            if h not in seen_hashes:
                seen_hashes.add(h)
                hash_unique.append(doc)

        # 第二阶段：内容相似度模糊去重
        unique = []
        seen_signatures = []

        for doc in hash_unique:
            content = doc.page_content
            # 简化签名：去除空格和换行，保留核心内容
            content_clean = ' '.join(content.split())

            is_duplicate = False
            for seen_doc in unique:
                # 检查内容相似度
                similarity = SequenceMatcher(None, content_clean[:300],
                                            ' '.join(seen_doc.page_content.split())[:300]).ratio()

                if similarity > 0.85:  # 相似度阈值
                    logger.info(f"发现相似文档，已去重 (相似度: {similarity:.2f})")
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(doc)

        logger.info(f"去重统计: 原始 {len(docs)} -> 哈希去重 {len(hash_unique)} -> 最终 {len(unique)}")
        return unique
