"""
异步协调器模块

提供异步的流程协调能力，用于：
1. 异步查询处理
2. 异步检索协调
3. 并行任务编排

[v0.8.0] 新增模块 - 异步 I/O 优化第一阶段
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger("AsyncCoordinator")

# 检查依赖
try:
    from src.utils.async_llm_utils import AsyncLLMWrapper
    ASYNC_LLM_AVAILABLE = True
except ImportError:
    ASYNC_LLM_AVAILABLE = False
    logger.warning("异步 LLM 工具不可用")

try:
    from src.retrievers.async_web_search_tool import AsyncWebSearchTool
    ASYNC_WEB_SEARCH_AVAILABLE = True
except ImportError:
    ASYNC_WEB_SEARCH_AVAILABLE = False
    logger.warning("异步网络搜索不可用")


class AsyncQueryProcessor:
    """
    异步查询处理器

    特性：
    - 并行执行 LLM 解析和本地检索
    - 异步缓存检查
    - 超时控制
    """

    def __init__(
        self,
        parser_chain: Any,
        cache_manager: Any,
        hybrid_retriever: Any,
        timeout: float = 30.0,
    ):
        """
        初始化异步查询处理器

        Args:
            parser_chain: LangChain 解析链
            cache_manager: 缓存管理器
            hybrid_retriever: 混合检索器
            timeout: 超时时间（秒）
        """
        self.parser_chain = parser_chain
        self.cache_manager = cache_manager
        self.hybrid_retriever = hybrid_retriever
        self.timeout = timeout

        # 异步 LLM 包装器
        self._async_llm = None
        if ASYNC_LLM_AVAILABLE and parser_chain is not None:
            try:
                # 尝试从 chain 中提取 LLM
                if hasattr(parser_chain, 'llm'):
                    self._async_llm = AsyncLLMWrapper(parser_chain.llm)
                elif hasattr(parser_chain, 'bound'):
                    self._async_llm = AsyncLLMWrapper(parser_chain.bound)
            except Exception as e:
                logger.warning(f"无法创建异步 LLM 包装器: {e}")

    async def parse_with_parallel_retrieval(
        self,
        query: str
    ) -> Tuple[Optional[Any], List]:
        """
        并行执行查询解析和本地检索

        Args:
            query: 查询字符串

        Returns:
            (解析结果, 本地文档列表) 元组
        """
        logger.info(f"异步并行处理: {query[:50]}...")
        start_time = datetime.now()

        try:
            # 创建并行任务
            tasks = []

            # 任务 1: LLM 解析
            async def parse_task():
                try:
                    if self._async_llm is not None:
                        return await self._async_llm.ainvoke({"query": query})
                    else:
                        # 回退到线程池
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(
                            None,
                            lambda: self.parser_chain.invoke({"query": query})
                        )
                except Exception as e:
                    logger.error(f"解析任务失败: {e}")
                    return None

            # 任务 2: 本地检索
            async def search_task():
                try:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None,
                        lambda: self.hybrid_retriever.search_local(query)
                    )
                except Exception as e:
                    logger.error(f"检索任务失败: {e}")
                    return []

            tasks.append(asyncio.create_task(parse_task()))
            tasks.append(asyncio.create_task(search_task()))

            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            parsed = results[0] if not isinstance(results[0], Exception) else None
            local_docs = results[1] if not isinstance(results[1], Exception) else []

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"并行处理完成: parsed={parsed is not None}, docs={len(local_docs)}, time={elapsed:.0f}ms")

            return parsed, local_docs

        except asyncio.TimeoutError:
            logger.error(f"并行处理超时: {query[:50]}")
            return None, []
        except Exception as e:
            logger.exception(f"并行处理异常: {e}")
            return None, []

    async def check_cache_async(self, query: str) -> Optional[Any]:
        """
        异步缓存检查

        Args:
            query: 查询字符串

        Returns:
            缓存的裁决或 None
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.cache_manager.get_verdict(query)
            )
        except Exception as e:
            logger.error(f"缓存检查失败: {e}")
            return None


class AsyncRetrievalCoordinator:
    """
    异步检索协调器

    特性：
    - 异步本地检索
    - 异步网络搜索
    - 智能结果合并
    """

    def __init__(
        self,
        hybrid_retriever: Any,
        kb: Any,
        async_web_tool: Any = None,
    ):
        """
        初始化异步检索协调器

        Args:
            hybrid_retriever: 混合检索器
            kb: 知识库
            async_web_tool: 异步网络搜索工具（可选）
        """
        self.hybrid_retriever = hybrid_retriever
        self.kb = kb

        # 异步网络搜索工具
        self._async_web_tool = async_web_tool
        if self._async_web_tool is None and ASYNC_WEB_SEARCH_AVAILABLE:
            try:
                self._async_web_tool = AsyncWebSearchTool()
            except Exception as e:
                logger.warning(f"无法创建异步网络搜索工具: {e}")

    async def retrieve_with_parsed_query(
        self,
        query: str,
        parsed_info: Any,
        local_docs: List = None,
    ) -> List[Dict[str, Any]]:
        """
        异步检索

        Args:
            query: 原始查询
            parsed_info: 解析后的信息
            local_docs: 已有的本地文档（可选）

        Returns:
            证据列表
        """
        logger.info(f"异步检索: {query[:50]}...")
        start_time = datetime.now()

        all_docs = local_docs or []

        try:
            # 1. 如果有解析词，补测本地库
            if parsed_info and hasattr(parsed_info, 'entity') and parsed_info.entity:
                parsed_query = f"{parsed_info.entity} {parsed_info.claim or ''}".strip()
                if parsed_query and parsed_query != query:
                    loop = asyncio.get_event_loop()
                    extra_docs = await loop.run_in_executor(
                        None,
                        lambda: self.hybrid_retriever.search_local(parsed_query)
                    )
                    all_docs.extend(extra_docs)

            # 2. 判断是否需要联网
            max_similarity = self._get_max_similarity(all_docs)
            need_web_search = (
                not all_docs or
                max_similarity < self.hybrid_retriever.min_local_similarity
            )

            # 3. 异步联网搜索
            if need_web_search and self._async_web_tool is not None:
                logger.info(f"触发异步联网搜索 (相似度: {max_similarity:.2f})")
                web_results = await self._async_web_tool.search(query)

                # 转换网络结果
                for res in web_results:
                    from langchain_core.documents import Document
                    doc = Document(
                        page_content=res.get("content", ""),
                        metadata=res.get("metadata", {})
                    )
                    all_docs.append(doc)

            # 4. 去重和格式转换
            unique_docs = self._deduplicate_docs(all_docs)
            result = self._convert_to_dict_format(unique_docs)

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"异步检索完成: docs={len(result)}, time={elapsed:.0f}ms")

            return result

        except Exception as e:
            logger.exception(f"异步检索失败: {e}")
            return []

    def _get_max_similarity(self, docs: List) -> float:
        """获取最大相似度"""
        if not docs:
            return 0.0

        max_sim = 0.0
        for doc in docs:
            sim = getattr(doc, 'metadata', {}).get('similarity', 0.0)
            if sim > max_sim:
                max_sim = sim
        return max_sim

    def _deduplicate_docs(self, docs: List) -> List:
        """去重文档"""
        if not docs:
            return []

        # 使用混合检索器的去重方法
        if hasattr(self.hybrid_retriever, '_deduplicate_docs'):
            return self.hybrid_retriever._deduplicate_docs(docs)

        # 简单去重
        seen = set()
        unique = []
        for doc in docs:
            content = getattr(doc, 'page_content', str(doc))[:100]
            h = hash(content)
            if h not in seen:
                seen.add(h)
                unique.append(doc)
        return unique

    def _convert_to_dict_format(self, docs: List) -> List[Dict]:
        """转换为字典格式"""
        result = []
        for doc in docs:
            if hasattr(doc, 'page_content'):
                result.append({
                    "content": doc.page_content,
                    "text": doc.page_content,
                    "metadata": getattr(doc, 'metadata', {}),
                })
            elif isinstance(doc, dict):
                result.append(doc)
        return result

    async def close(self):
        """关闭资源"""
        if self._async_web_tool is not None:
            await self._async_web_tool.close()


class AsyncAnalysisCoordinator:
    """
    异步分析协调器

    特性：
    - 异步证据分析
    - 批量并行处理
    """

    def __init__(self, analyzer: Any = None, max_concurrency: int = 10):
        """
        初始化异步分析协调器

        Args:
            analyzer: 证据分析器
            max_concurrency: 最大并发数
        """
        self.analyzer = analyzer
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def analyze_async(
        self,
        claim: str,
        evidence_list: List[Dict],
    ) -> List[Any]:
        """
        异步分析证据

        Args:
            claim: 主张
            evidence_list: 证据列表

        Returns:
            分析结果列表
        """
        if not evidence_list:
            return []

        logger.info(f"异步分析: {len(evidence_list)} 条证据")
        start_time = datetime.now()

        try:
            # 如果有分析器，使用它
            if self.analyzer is not None:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.analyzer.analyze(claim, evidence_list)
                )
                return result

            # 否则返回空
            return []

        except Exception as e:
            logger.exception(f"异步分析失败: {e}")
            return []

    async def analyze_single_async(
        self,
        claim: str,
        evidence: Dict,
        idx: int,
    ) -> Any:
        """
        异步分析单个证据

        Args:
            claim: 主张
            evidence: 证据
            idx: 索引

        Returns:
            分析结果
        """
        async with self._semaphore:
            try:
                loop = asyncio.get_event_loop()
                # 调用同步分析器
                if self.analyzer is not None and hasattr(self.analyzer, '_analyze_single'):
                    return await loop.run_in_executor(
                        None,
                        lambda: self.analyzer._analyze_single(claim, evidence, idx)
                    )
            except Exception as e:
                logger.error(f"分析证据 {idx} 失败: {e}")
            return None


# 导出
__all__ = [
    'AsyncQueryProcessor',
    'AsyncRetrievalCoordinator',
    'AsyncAnalysisCoordinator',
]
