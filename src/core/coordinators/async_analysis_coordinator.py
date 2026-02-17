"""
异步分析协调器

提供异步的证据分析协调能力

[v0.8.0] 新增模块 - 异步 I/O 优化第三阶段
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("AsyncAnalysisCoordinator")

# 检查异步 LLM 工具
try:
    from src.utils.async_llm_utils import AsyncLLMWrapper, run_sync_in_executor
    ASYNC_LLM_AVAILABLE = True
except ImportError:
    ASYNC_LLM_AVAILABLE = False
    logger.warning("异步 LLM 工具不可用")


class AsyncAnalysisCoordinator:
    """
    异步分析协调器

    特性：
    - 异步并行证据分析
    - 动态并发控制
    - 容错处理
    - 预过滤支持
    """

    def __init__(
        self,
        analyzer: Any = None,
        max_concurrency: int = 10,
        enable_prefilter: bool = True,
        prefilter_max_evidence: int = 5,
    ):
        """
        初始化异步分析协调器

        Args:
            analyzer: EvidenceAnalyzer 实例（可选，支持依赖注入）
            max_concurrency: 最大并发数
            enable_prefilter: 是否启用预过滤
            prefilter_max_evidence: 预过滤后最大证据数
        """
        self._analyzer = analyzer
        self.max_concurrency = max_concurrency
        self.enable_prefilter = enable_prefilter
        self.prefilter_max_evidence = prefilter_max_evidence

        # 并发控制
        self._semaphore: Optional[asyncio.Semaphore] = None

        # 统计信息
        self._stats = {
            "total_analyzed": 0,
            "successful": 0,
            "failed": 0,
            "total_time_ms": 0,
        }

    @property
    def analyzer(self):
        """延迟初始化 EvidenceAnalyzer"""
        if self._analyzer is None:
            from src.analyzers.evidence_analyzer import EvidenceAnalyzer
            self._analyzer = EvidenceAnalyzer()
        return self._analyzer

    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取信号量（延迟初始化）"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    async def analyze_async(
        self,
        claim: str,
        evidence_list: List[Dict[str, Any]],
    ) -> List[Any]:
        """
        异步分析证据列表

        Args:
            claim: 主张
            evidence_list: 证据列表

        Returns:
            EvidenceAssessment 列表
        """
        if not evidence_list:
            logger.warning("证据列表为空，跳过分析")
            return []

        start_time = datetime.now()
        logger.info(f"异步分析开始: {len(evidence_list)} 条证据")

        try:
            # 1. 预过滤（可选）
            if self.enable_prefilter:
                evidence_list = await self._prefilter_async(claim, evidence_list)
                if not evidence_list:
                    return []

            # 2. 并行分析
            count = len(evidence_list)
            if count == 1:
                result = await self._analyze_single_async(claim, evidence_list[0], 0)
                return [result] if result else []

            # 多证据并行分析
            assessments = await self._analyze_parallel_async(claim, evidence_list)

            # 更新统计
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            self._stats["total_analyzed"] += count
            self._stats["successful"] += len(assessments)
            self._stats["total_time_ms"] += elapsed

            logger.info(
                f"异步分析完成: {len(assessments)}/{count} 条成功, "
                f"耗时 {elapsed:.0f}ms"
            )

            return assessments

        except Exception as e:
            logger.exception(f"异步分析失败: {e}")
            self._stats["failed"] += len(evidence_list)
            return []

    async def _prefilter_async(
        self,
        claim: str,
        evidence_list: List[Dict],
    ) -> List[Dict]:
        """
        异步预过滤证据

        Args:
            claim: 主张
            evidence_list: 证据列表

        Returns:
            过滤后的证据列表
        """
        # 预过滤是 CPU 密集型，在线程池中执行
        loop = asyncio.get_event_loop()

        def do_prefilter():
            return self.analyzer._prefilter_evidence(claim, evidence_list)

        return await loop.run_in_executor(None, do_prefilter)

    async def _analyze_parallel_async(
        self,
        claim: str,
        evidence_list: List[Dict],
    ) -> List[Any]:
        """
        异步并行分析证据

        Args:
            claim: 主张
            evidence_list: 证据列表

        Returns:
            EvidenceAssessment 列表
        """
        semaphore = self._get_semaphore()

        async def analyze_with_semaphore(evidence: Dict, index: int):
            async with semaphore:
                return await self._analyze_single_async(claim, evidence, index)

        # 创建所有任务
        tasks = [
            analyze_with_semaphore(evidence, i)
            for i, evidence in enumerate(evidence_list)
        ]

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤有效结果
        assessments = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"证据 {i} 分析失败: {result}")
            elif result is not None:
                assessments.append(result)

        # 按 ID 排序
        assessments.sort(key=lambda x: getattr(x, 'id', 0))

        return assessments

    async def _analyze_single_async(
        self,
        claim: str,
        evidence: Dict,
        index: int,
    ) -> Optional[Any]:
        """
        异步分析单个证据

        Args:
            claim: 主张
            evidence: 证据
            index: 索引

        Returns:
            EvidenceAssessment 或 None
        """
        try:
            loop = asyncio.get_event_loop()

            # 调用同步分析器
            result = await loop.run_in_executor(
                None,
                lambda: self.analyzer._analyze_single_evidence(claim, evidence, index)
            )

            return result

        except Exception as e:
            logger.error(f"分析证据 {index} 失败: {e}")
            return None

    async def summarize_assessments_async(
        self,
        assessments: List[Any],
    ) -> Dict[str, Any]:
        """
        异步汇总评估结果

        Args:
            assessments: 评估列表

        Returns:
            汇总信息字典
        """
        if not assessments:
            return {
                "total": 0,
                "support": 0,
                "oppose": 0,
                "neutral": 0,
                "avg_confidence": 0.0,
                "avg_authority": 0.0,
            }

        # 统计（CPU 密集型，在当前协程中执行）
        support = sum(1 for a in assessments if getattr(a, 'stance', '') == '支持')
        oppose = sum(1 for a in assessments if getattr(a, 'stance', '') == '反对')
        neutral = sum(1 for a in assessments if getattr(a, 'stance', '') in ['中立/不相关', '部分支持/条件性反驳'])

        confidences = [getattr(a, 'confidence', 0.0) for a in assessments]
        authorities = [getattr(a, 'authority_score', 3) for a in assessments]

        return {
            "total": len(assessments),
            "support": support,
            "oppose": oppose,
            "neutral": neutral,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "avg_authority": sum(authorities) / len(authorities) if authorities else 0.0,
        }

    async def get_high_quality_evidence_async(
        self,
        assessments: List[Any],
        min_confidence: float = 0.7,
        min_authority: int = 3,
    ) -> List[Any]:
        """
        异步筛选高质量证据

        Args:
            assessments: 评估列表
            min_confidence: 最小置信度
            min_authority: 最小权威性

        Returns:
            高质量评估列表
        """
        high_quality = [
            a for a in assessments
            if getattr(a, 'confidence', 0) >= min_confidence
            and getattr(a, 'authority_score', 0) >= min_authority
            and getattr(a, 'relevance', '') in ['高', '中']
        ]

        logger.info(f"高质量证据: {len(high_quality)}/{len(assessments)}")
        return high_quality

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_analyzed"] > 0:
            stats["success_rate"] = (
                stats["successful"] / stats["total_analyzed"] * 100
            )
            stats["avg_time_ms"] = (
                stats["total_time_ms"] / stats["successful"]
                if stats["successful"] > 0 else 0
            )
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_analyzed": 0,
            "successful": 0,
            "failed": 0,
            "total_time_ms": 0,
        }
