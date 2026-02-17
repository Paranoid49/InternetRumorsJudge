"""
异步裁决生成器

提供异步的裁决生成能力

[v0.8.0] 新增模块 - 异步 I/O 优化第三阶段
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger("AsyncVerdictGenerator")

# 检查异步 LLM 工具
try:
    from src.utils.async_llm_utils import AsyncLLMWrapper
    ASYNC_LLM_AVAILABLE = True
except ImportError:
    ASYNC_LLM_AVAILABLE = False
    logger.warning("异步 LLM 工具不可用")


class AsyncVerdictGenerator:
    """
    异步裁决生成器

    特性：
    - 异步裁决生成
    - 自动重试
    - 兜底机制
    - 并发控制
    """

    def __init__(
        self,
        summarizer: Any = None,
        max_concurrency: int = 5,
        max_retries: int = 2,
    ):
        """
        初始化异步裁决生成器

        Args:
            summarizer: TruthSummarizer 实例（可选，支持依赖注入）
            max_concurrency: 最大并发数
            max_retries: 最大重试次数
        """
        self._summarizer = summarizer
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries

        # 并发控制
        self._semaphore: Optional[asyncio.Semaphore] = None

        # 统计信息
        self._stats = {
            "total_generated": 0,
            "successful": 0,
            "fallback_used": 0,
            "failed": 0,
            "total_time_ms": 0,
        }

    @property
    def summarizer(self):
        """延迟初始化 TruthSummarizer"""
        if self._summarizer is None:
            from src.analyzers.truth_summarizer import TruthSummarizer
            self._summarizer = TruthSummarizer()
        return self._summarizer

    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取信号量（延迟初始化）"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    async def generate_async(
        self,
        query: str,
        entity: Optional[str],
        claim: Optional[str],
        evidence_list: List[Dict[str, Any]],
        assessments: List[Any],
    ) -> Optional[Any]:
        """
        异步生成裁决

        Args:
            query: 原始查询
            entity: 实体
            claim: 主张
            evidence_list: 证据列表
            assessments: 评估列表

        Returns:
            FinalVerdict 或 None
        """
        start_time = datetime.now()
        semaphore = self._get_semaphore()

        async with semaphore:
            self._stats["total_generated"] += 1

            try:
                # 构建完整的 claim
                full_claim = f"{entity} {claim}" if entity and claim else (claim or query)

                # 根据是否有评估选择不同的生成策略
                if assessments and len(assessments) > 0:
                    result = await self._generate_with_assessments_async(
                        full_claim, assessments
                    )
                else:
                    result = await self._generate_with_fallback_async(full_claim)

                # 更新统计
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                self._stats["successful"] += 1
                self._stats["total_time_ms"] += elapsed

                if result:
                    logger.info(
                        f"裁决生成成功: {result.verdict} "
                        f"(置信度: {result.confidence}%, "
                        f"耗时: {elapsed:.0f}ms)"
                    )

                return result

            except Exception as e:
                self._stats["failed"] += 1
                logger.exception(f"裁决生成失败: {e}")
                return None

    async def _generate_with_assessments_async(
        self,
        claim: str,
        assessments: List[Any],
    ) -> Optional[Any]:
        """
        使用评估结果异步生成裁决

        Args:
            claim: 主张
            assessments: 评估列表

        Returns:
            FinalVerdict 或 None
        """
        for attempt in range(self.max_retries + 1):
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.summarizer.summarize(claim, assessments)
                )
                return result

            except Exception as e:
                logger.warning(
                    f"裁决生成失败 (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0)

        # 所有重试失败，使用规则兜底
        logger.warning("所有重试失败，使用规则兜底")
        return await self._rule_based_fallback_async(claim, assessments)

    async def _generate_with_fallback_async(
        self,
        claim: str,
    ) -> Optional[Any]:
        """
        使用兜底机制异步生成裁决

        Args:
            claim: 主张

        Returns:
            FinalVerdict 或 None
        """
        self._stats["fallback_used"] += 1
        logger.info("无评估结果，使用兜底机制")

        for attempt in range(self.max_retries + 1):
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.summarizer.summarize_based_on_knowledge(claim)
                )
                return result

            except Exception as e:
                logger.warning(
                    f"兜底生成失败 (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0)

        return None

    async def _rule_based_fallback_async(
        self,
        claim: str,
        assessments: List[Any],
    ) -> Any:
        """
        异步规则兜底（调用同步方法）

        Args:
            claim: 主张
            assessments: 评估列表

        Returns:
            FinalVerdict
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.summarizer._rule_based_fallback(claim, assessments)
        )

    async def format_for_cache_async(
        self,
        verdict: Any,
    ) -> Dict:
        """
        异步格式化裁决以便缓存

        Args:
            verdict: FinalVerdict 对象

        Returns:
            可缓存的字典
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: verdict.dict()
        )

    async def extract_key_info_async(
        self,
        verdict: Any,
    ) -> Dict:
        """
        异步提取裁决的关键信息

        Args:
            verdict: FinalVerdict 对象

        Returns:
            关键信息字典
        """
        # 简单操作，直接执行
        return {
            'verdict': str(verdict.verdict),
            'confidence': verdict.confidence,
            'summary': verdict.summary,
            'risk_level': verdict.risk_level
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["total_generated"] > 0:
            stats["success_rate"] = (
                stats["successful"] / stats["total_generated"] * 100
            )
            stats["fallback_rate"] = (
                stats["fallback_used"] / stats["total_generated"] * 100
            )
            stats["avg_time_ms"] = (
                stats["total_time_ms"] / stats["successful"]
                if stats["successful"] > 0 else 0
            )
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_generated": 0,
            "successful": 0,
            "fallback_used": 0,
            "failed": 0,
            "total_time_ms": 0,
        }
