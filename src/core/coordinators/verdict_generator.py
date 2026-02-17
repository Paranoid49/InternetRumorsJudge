"""
裁决生成器

负责生成最终的真假裁决
"""
import logging
from typing import List, Dict, Any, Optional

from src.core.coordinators.base import BaseCoordinator

logger = logging.getLogger("VerdictGenerator")


class VerdictGenerator(BaseCoordinator):
    """
    裁决生成器

    职责：
    1. 生成最终裁决
    2. 兜底机制
    3. 裁决后处理

    [v0.7.1] 支持依赖注入，提高可测试性
    """

    def __init__(self, summarizer: Optional[Any] = None):
        """
        初始化裁决生成器

        Args:
            summarizer: TruthSummarizer 实例（可选，用于依赖注入）
                       如果不提供，将在首次使用时自动创建
        """
        super().__init__("VerdictGenerator")
        self._summarizer = summarizer

    @property
    def summarizer(self):
        """延迟初始化 TruthSummarizer"""
        if self._summarizer is None:
            from src.analyzers.truth_summarizer import TruthSummarizer
            self._summarizer = TruthSummarizer()
        return self._summarizer

    def generate(
        self,
        query: str,
        entity: Optional[str],
        claim: Optional[str],
        evidence_list: List[Dict[str, Any]],
        assessments: List[Any]
    ) -> Optional[Any]:
        """
        生成最终裁决

        Args:
            query: 原始查询
            entity: 实体
            claim: 主张
            evidence_list: 证据列表
            assessments: 证据评估列表 (List[EvidenceAssessment])

        Returns:
            FinalVerdict 对象，失败返回 None
        """
        try:
            logger.info("开始生成裁决")

            # 构建完整的claim
            full_claim = f"{entity} {claim}" if entity and claim else (claim or query)

            # 根据是否有assessments选择不同的生成策略
            if assessments and len(assessments) > 0:
                # 有证据评估，使用注入的总结器
                verdict = self.summarizer.summarize(full_claim, assessments)
            else:
                # 无证据评估，使用兜底机制
                logger.info("无证据评估，使用兜底机制")
                verdict = self.summarizer.summarize_based_on_knowledge(full_claim)

            if verdict:
                logger.info(
                    f"裁决生成成功: {verdict.verdict} "
                    f"(置信度: {verdict.confidence}%, "
                    f"风险: {verdict.risk_level})"
                )
            else:
                logger.warning("裁决生成失败，返回None")

            return verdict

        except Exception as e:
            logger.error(f"裁决生成异常: {e}")
            return None

    def format_for_cache(self, verdict: Any) -> dict:
        """
        格式化裁决以便缓存

        Args:
            verdict: FinalVerdict 对象

        Returns:
            可缓存的字典
        """
        return verdict.dict()

    def extract_key_info(self, verdict: Any) -> dict:
        """
        提取裁决的关键信息

        Args:
            verdict: FinalVerdict 对象

        Returns:
            关键信息字典
        """
        return {
            'verdict': str(verdict.verdict),
            'confidence': verdict.confidence,
            'summary': verdict.summary,
            'risk_level': verdict.risk_level
        }
