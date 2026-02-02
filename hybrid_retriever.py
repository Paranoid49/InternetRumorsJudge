import logging
from typing import List, Dict, Optional, Any
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from evidence_retriever import EvidenceKnowledgeBase
from web_search_tool import WebSearchTool
import config

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
    min_local_similarity: float = 0.4  # 针对 v4 模型调优：相似度达到 0.4 即视为本地有高质量证据，不再触发联网
    max_results: int = 5

    def __init__(self, local_kb: EvidenceKnowledgeBase, web_tool: WebSearchTool, **kwargs):
        # BaseRetriever 是 Pydantic 模型，需要通过 super().__init__ 初始化
        super().__init__(local_kb=local_kb, web_tool=web_tool, **kwargs)

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """核心检索逻辑 (LangChain 标准接口)"""
        logger.info(f"混合检索启动: '{query}'")
        all_docs = []
        
        # 1. 本地检索
        logger.info("正在执行本地向量库检索...")
        local_results = self.local_kb.search(query, k=self.max_results)
        
        # 转换为 Document 对象
        local_docs = []
        max_similarity = 0.0
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
            max_similarity = max(max_similarity, res['similarity'])
        
        logger.info(f"本地检索完成，找到 {len(local_docs)} 条证据，最高相似度: {max_similarity:.4f}")
        all_docs.extend(local_docs)
        
        # 2. 判断是否需要联网搜索
        # 条件：本地没结果，或者最相关的结果相似度也低于阈值
        should_search_web = (
            len(local_docs) == 0 or 
            max_similarity < self.min_local_similarity
        )
        
        if should_search_web:
            reason = "本地无结果" if len(local_docs) == 0 else f"相似度 {max_similarity:.2f} 低于阈值 {self.min_local_similarity}"
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
                return doc.metadata['similarity'] + 0.5 # 提升本地证据权重
            return doc.metadata.get('score', 0.5)
            
        sorted_docs = sorted(unique_docs, key=sort_key, reverse=True)
        final_docs = sorted_docs[:self.max_results]
        
        logger.info(f"混合检索最终返回 {len(final_docs)} 条证据。")
        return final_docs

    def _deduplicate_docs(self, docs: List[Document]) -> List[Document]:
        """基于内容片段哈希的简单去重"""
        seen_hashes = set()
        unique = []
        for doc in docs:
            # 取前100个字符做简单哈希去重
            content_preview = doc.page_content[:100].strip()
            if not content_preview:
                continue
            h = hash(content_preview)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(doc)
        return unique
