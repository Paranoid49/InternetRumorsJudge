"""
异步谣言核查引擎

提供异步的完整核查流程

[v0.8.0] 新增模块 - 异步 I/O 优化第四阶段

特性：
- 完全异步的核查流程
- 并行执行各阶段任务
- 与同步引擎并存，可切换
- 同步兼容层支持
"""
import asyncio
import logging
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger("AsyncRumorJudgeEngine")

# 导入统一结果类型
from src.core.pipeline import (
    UnifiedVerificationResult,
    ProcessingMetadata,
    PipelineStage,
)


class AsyncRumorJudgeEngine:
    """
    异步谣言核查引擎

    特性：
    - 完全异步的核查流程
    - 并行执行查询解析和检索
    - 并行证据分析
    - 后台知识集成
    - 与同步引擎并存

    使用方式：
    ```python
    # 异步使用
    engine = AsyncRumorJudgeEngine()
    result = await engine.run_async("查询内容")

    # 同步兼容
    result = engine.run("查询内容")
    ```
    """

    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 延迟初始化标志
        self._components_initialized = False
        self._init_lock = threading.RLock()

        # 组件占位符
        self._kb = None
        self._cache_manager = None
        self._hybrid_retriever = None
        self._parser_chain = None
        self._knowledge_integrator = None

        # 异步协调器
        self._async_query_processor = None
        self._async_retrieval_coordinator = None
        self._async_analysis_coordinator = None
        self._async_verdict_generator = None

        # 统计信息
        self._stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "web_searches": 0,
            "successful": 0,
            "failed": 0,
            "total_time_ms": 0,
        }

        self._initialized = True
        logger.info("AsyncRumorJudgeEngine 实例已创建（组件将延迟初始化）")

    async def _lazy_init_async(self):
        """异步延迟初始化"""
        if self._components_initialized:
            return

        with self._init_lock:
            if self._components_initialized:
                return

            logger.info("正在执行异步组件初始化...")
            start_time = datetime.now()

            try:
                # 1. 初始化基础组件（复用同步引擎的组件）
                from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
                from src.core.cache_manager import CacheManager
                from src.retrievers.hybrid_retriever import HybridRetriever
                from src.retrievers.web_search_tool import WebSearchTool
                from src.knowledge.knowledge_integrator import KnowledgeIntegrator
                from src.analyzers.query_parser import build_chain

                self._kb = EvidenceKnowledgeBase()
                self._cache_manager = CacheManager(embeddings=self._kb.embeddings)
                self._web_search_tool = WebSearchTool()
                self._knowledge_integrator = KnowledgeIntegrator()

                self._hybrid_retriever = HybridRetriever(
                    local_kb=self._kb,
                    web_tool=self._web_search_tool
                )

                # 确保知识库就绪
                if not self._kb.persist_dir.exists():
                    logger.warning(f"向量知识库不存在，正在构建...")
                    self._kb.build()

                # 初始化解析链
                try:
                    self._parser_chain = build_chain()
                except Exception as e:
                    logger.error(f"解析器初始化失败: {e}")
                    self._parser_chain = None

                # 2. 初始化异步协调器
                await self._init_async_coordinators()

                self._components_initialized = True
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.info(f"异步组件初始化完成，耗时 {elapsed:.0f}ms")

            except Exception as e:
                logger.exception(f"异步组件初始化失败: {e}")
                raise

    async def _init_async_coordinators(self):
        """初始化异步协调器"""
        try:
            # 尝试使用新的异步协调器
            from src.core.coordinators.async_coordinator import (
                AsyncQueryProcessor,
                AsyncRetrievalCoordinator,
            )
            from src.core.coordinators.async_analysis_coordinator import (
                AsyncAnalysisCoordinator,
            )
            from src.core.coordinators.async_verdict_generator import (
                AsyncVerdictGenerator,
            )

            self._async_query_processor = AsyncQueryProcessor(
                parser_chain=self._parser_chain,
                cache_manager=self._cache_manager,
                hybrid_retriever=self._hybrid_retriever,
            )

            self._async_retrieval_coordinator = AsyncRetrievalCoordinator(
                hybrid_retriever=self._hybrid_retriever,
                kb=self._kb,
            )

            self._async_analysis_coordinator = AsyncAnalysisCoordinator()

            self._async_verdict_generator = AsyncVerdictGenerator()

            logger.info("异步协调器初始化成功")

        except ImportError as e:
            logger.warning(f"部分异步协调器不可用，使用降级模式: {e}")
            # 降级：使用同步协调器
            self._async_query_processor = None
            self._async_retrieval_coordinator = None
            self._async_analysis_coordinator = None
            self._async_verdict_generator = None

    @property
    def is_ready(self) -> bool:
        """检查引擎是否就绪"""
        return self._components_initialized

    async def run_async(
        self,
        query: str,
        use_cache: bool = True,
    ) -> UnifiedVerificationResult:
        """
        异步执行完整核查流程

        Args:
            query: 查询内容
            use_cache: 是否使用缓存

        Returns:
            UnifiedVerificationResult
        """
        start_time = datetime.now()
        self._stats["total_queries"] += 1

        logger.info(f"开始异步核查: {query[:50]}...")

        # 确保组件已初始化
        await self._lazy_init_async()

        result = UnifiedVerificationResult(query=query)

        try:
            # ========== 阶段 1: 查询处理 ==========
            logger.info("阶段1: 异步查询处理")

            parsed, local_docs = await self._process_query_async(query)

            if parsed:
                result.entity = getattr(parsed, 'entity', None)
                result.claim = getattr(parsed, 'claim', None)
                result.category = getattr(parsed, 'category', None)
                result.add_metadata(PipelineStage.PARSING, True)

            # ========== 阶段 2: 缓存检查 ==========
            if use_cache:
                cached = await self._check_cache_async(query)
                if cached:
                    result.is_cached = True
                    result.final_verdict = cached.verdict.value
                    result.confidence_score = cached.confidence
                    result.risk_level = cached.risk_level
                    result.summary_report = cached.summary
                    self._stats["cache_hits"] += 1

                    result.add_metadata(
                        PipelineStage.CACHE_CHECK,
                        True,
                        duration=(datetime.now() - start_time).total_seconds() * 1000
                    )

                    logger.info(f"缓存命中，直接返回")
                    return result

            result.add_metadata(PipelineStage.CACHE_CHECK, True, "未命中")

            # ========== 阶段 3: 证据检索 ==========
            logger.info("阶段2: 异步证据检索")
            retrieval_start = datetime.now()

            evidence_list = await self._retrieve_evidence_async(
                query, parsed, local_docs
            )

            result.retrieved_evidence = evidence_list
            is_web_search = any(
                ev.get('metadata', {}).get('type') == 'web'
                for ev in evidence_list
            )
            result.is_web_search = is_web_search

            if is_web_search:
                self._stats["web_searches"] += 1
                result.add_metadata(
                    PipelineStage.WEB_SEARCH,
                    True,
                    duration=(datetime.now() - retrieval_start).total_seconds() * 1000
                )
            else:
                result.add_metadata(
                    PipelineStage.RETRIEVAL,
                    True,
                    duration=(datetime.now() - retrieval_start).total_seconds() * 1000
                )

            logger.info(f"检索完成: {len(evidence_list)} 条证据, web_search={is_web_search}")

            # ========== 阶段 4: 证据分析 ==========
            logger.info("阶段3: 异步证据分析")

            if evidence_list:
                claim = result.claim if result.claim else query
                assessments = await self._analyze_evidence_async(claim, evidence_list)
                result.evidence_assessments = assessments
                result.add_metadata(PipelineStage.ANALYSIS, True)
            else:
                logger.warning("无证据，跳过分析")
                result.add_metadata(PipelineStage.ANALYSIS, True, "无证据")

            # ========== 阶段 5: 裁决生成 ==========
            logger.info("阶段4: 异步裁决生成")
            verdict_start = datetime.now()

            verdict = await self._generate_verdict_async(
                query, result.entity, result.claim,
                evidence_list, result.evidence_assessments
            )

            if verdict:
                result.final_verdict = verdict.verdict.value
                result.confidence_score = verdict.confidence
                result.risk_level = verdict.risk_level
                result.summary_report = verdict.summary

                # 缓存结果
                await self._cache_result_async(query, verdict)

                result.add_metadata(
                    PipelineStage.VERDICT,
                    True,
                    duration=(datetime.now() - verdict_start).total_seconds() * 1000
                )

                # 后台知识集成
                asyncio.create_task(self._auto_integrate_knowledge_async(result))

                self._stats["successful"] += 1
            else:
                result.final_verdict = "证据不足"
                result.summary_report = "无法生成有效裁决"
                result.add_metadata(PipelineStage.VERDICT, False, "裁决生成失败")
                self._stats["failed"] += 1

            # 更新总耗时
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            self._stats["total_time_ms"] += elapsed

            logger.info(f"异步核查完成: 裁决={result.final_verdict}, 耗时={elapsed:.0f}ms")

            return result

        except Exception as e:
            logger.exception(f"异步核查失败: {e}")
            self._stats["failed"] += 1

            result.is_fallback = True
            result.final_verdict = "处理失败"
            result.summary_report = f"系统处理异常: {str(e)}"
            result.add_metadata(PipelineStage.VERDICT, False, str(e))

            return result

    async def _process_query_async(
        self,
        query: str,
    ) -> tuple:
        """异步查询处理"""
        if self._async_query_processor:
            return await self._async_query_processor.parse_with_parallel_retrieval(query)

        # 降级：使用线程池执行同步操作
        loop = asyncio.get_event_loop()

        # 并行执行解析和检索
        async def parse_task():
            if self._parser_chain:
                return await loop.run_in_executor(
                    None,
                    lambda: self._parser_chain.invoke({"query": query})
                )
            return None

        async def search_task():
            return await loop.run_in_executor(
                None,
                lambda: self._hybrid_retriever.search_local(query)
            )

        results = await asyncio.gather(parse_task(), search_task(), return_exceptions=True)

        parsed = results[0] if not isinstance(results[0], Exception) else None
        local_docs = results[1] if not isinstance(results[1], Exception) else []

        return parsed, local_docs

    async def _check_cache_async(self, query: str):
        """异步缓存检查"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._cache_manager.get_verdict(query)
        )

    async def _retrieve_evidence_async(
        self,
        query: str,
        parsed_info: Any,
        local_docs: List,
    ) -> List[Dict]:
        """异步证据检索"""
        if self._async_retrieval_coordinator:
            return await self._async_retrieval_coordinator.retrieve_with_parsed_query(
                query, parsed_info, local_docs
            )

        # 降级：使用同步协调器
        loop = asyncio.get_event_loop()

        # 创建临时同步协调器
        from src.core.coordinators import RetrievalCoordinator
        sync_coordinator = RetrievalCoordinator(
            hybrid_retriever=self._hybrid_retriever,
            kb=self._kb
        )

        return await loop.run_in_executor(
            None,
            lambda: sync_coordinator.retrieve_with_parsed_query(query, parsed_info, local_docs)
        )

    async def _analyze_evidence_async(
        self,
        claim: str,
        evidence_list: List[Dict],
    ) -> List[Any]:
        """异步证据分析"""
        if self._async_analysis_coordinator:
            return await self._async_analysis_coordinator.analyze_async(claim, evidence_list)

        # 降级：使用同步分析器
        loop = asyncio.get_event_loop()
        from src.analyzers.evidence_analyzer import EvidenceAnalyzer
        analyzer = EvidenceAnalyzer()

        return await loop.run_in_executor(
            None,
            lambda: analyzer.analyze(claim, evidence_list)
        )

    async def _generate_verdict_async(
        self,
        query: str,
        entity: Optional[str],
        claim: Optional[str],
        evidence_list: List[Dict],
        assessments: List[Any],
    ) -> Optional[Any]:
        """异步裁决生成"""
        if self._async_verdict_generator:
            return await self._async_verdict_generator.generate_async(
                query, entity, claim, evidence_list, assessments
            )

        # 降级：使用同步生成器
        loop = asyncio.get_event_loop()
        from src.core.coordinators import VerdictGenerator
        generator = VerdictGenerator()

        return await loop.run_in_executor(
            None,
            lambda: generator.generate(query, entity, claim, evidence_list, assessments)
        )

    async def _cache_result_async(self, query: str, verdict: Any):
        """异步缓存结果"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._cache_manager.set_verdict(query, verdict)
        )

    async def _auto_integrate_knowledge_async(self, result: UnifiedVerificationResult):
        """异步自动知识集成"""
        # 检查集成条件
        from src import config

        min_confidence = getattr(config, 'AUTO_INTEGRATE_MIN_CONFIDENCE', 90)
        min_evidence = getattr(config, 'AUTO_INTEGRATE_MIN_EVIDENCE', 3)

        if result.final_verdict not in ["真", "假"]:
            return

        if result.confidence_score < min_confidence:
            return

        if len(result.retrieved_evidence) < min_evidence:
            return

        if not result.is_web_search:
            return

        logger.info(f"开始异步知识集成: {result.query[:30]}...")

        try:
            loop = asyncio.get_event_loop()

            # 生成知识内容
            combined_evidence = "\n\n".join([
                f"来源: {ev['metadata']['source']}\n内容: {ev['content']}"
                for ev in result.retrieved_evidence
            ])

            content = await loop.run_in_executor(
                None,
                lambda: self._knowledge_integrator.generate_knowledge_content(
                    query=result.query,
                    comment=f"系统自动联网核查结果：\n结论：{result.final_verdict}\n总结：{result.summary_report}\n\n外部参考：\n{combined_evidence}"
                )
            )

            if content:
                # 写入文件
                timestamp = int(datetime.now().timestamp())
                safe_title = "".join([c for c in result.query if c.isalnum()])[:20]
                filename = f"AUTO_GEN_{timestamp}_{safe_title}.txt"
                file_path = self._knowledge_integrator.rumor_data_dir / filename

                await loop.run_in_executor(
                    None,
                    lambda: file_path.write_text(content, encoding='utf-8')
                )

                logger.info(f"✅ 自动生成知识文件: {filename}")

                # 重构向量库
                await loop.run_in_executor(
                    None,
                    lambda: self._knowledge_integrator.rebuild_knowledge_base()
                )

                logger.info("异步知识集成完成")

        except Exception as e:
            logger.error(f"异步知识集成失败: {e}")

    def run(self, query: str, use_cache: bool = True) -> UnifiedVerificationResult:
        """
        同步接口（兼容现有代码）

        Args:
            query: 查询内容
            use_cache: 是否使用缓存

        Returns:
            UnifiedVerificationResult
        """
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环已在运行，创建新循环
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.run_async(query, use_cache)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.run_async(query, use_cache))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.run_async(query, use_cache))

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_queries"] > 0:
            stats["cache_hit_rate"] = (
                stats["cache_hits"] / stats["total_queries"] * 100
            )
            stats["success_rate"] = (
                stats["successful"] / stats["total_queries"] * 100
            )
            stats["avg_time_ms"] = (
                stats["total_time_ms"] / stats["successful"]
                if stats["successful"] > 0 else 0
            )
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "web_searches": 0,
            "successful": 0,
            "failed": 0,
            "total_time_ms": 0,
        }


# 便捷函数
async def async_verify(query: str, use_cache: bool = True) -> UnifiedVerificationResult:
    """
    异步核查便捷函数

    Args:
        query: 查询内容
        use_cache: 是否使用缓存

    Returns:
        UnifiedVerificationResult
    """
    engine = AsyncRumorJudgeEngine()
    return await engine.run_async(query, use_cache)


def verify(query: str, use_cache: bool = True) -> UnifiedVerificationResult:
    """
    同步核查便捷函数（兼容）

    Args:
        query: 查询内容
        use_cache: 是否使用缓存

    Returns:
        UnifiedVerificationResult
    """
    engine = AsyncRumorJudgeEngine()
    return engine.run(query, use_cache)
