"""
分析协调器

负责证据分析的协调工作
"""
import logging
from typing import List, Dict, Any

from src.analyzers.evidence_analyzer import analyze_evidence, EvidenceAssessment
from src.core.pipeline import PipelineStage
from src.core.coordinators.base import BaseCoordinator

logger = logging.getLogger("AnalysisCoordinator")


class AnalysisCoordinator(BaseCoordinator):
    """
    分析协调器

    职责：
    1. 协调证据分析
    2. 批量分析优化
    3. 分析结果聚合
    """

    def __init__(self):
        """初始化分析协调器"""
        super().__init__("AnalysisCoordinator")

    def analyze(
        self,
        claim: str,
        evidence_list: List[Dict[str, Any]]
    ) -> List[EvidenceAssessment]:
        """
        分析证据列表

        Args:
            claim: 主张陈述
            evidence_list: 证据列表

        Returns:
            证据评估列表
        """
        if not evidence_list:
            logger.warning("证据列表为空，跳过分析")
            return []

        try:
            logger.info(f"开始分析 {len(evidence_list)} 条证据")

            # 使用并行分析（在analyze_evidence内部实现）
            assessments = analyze_evidence(
                claim=claim,
                evidence_list=evidence_list
            )

            logger.info(f"分析完成，生成 {len(assessments)} 个评估")
            return assessments

        except Exception as e:
            logger.error(f"证据分析失败: {e}")
            return []

    def summarize_assessments(
        self,
        assessments: List[EvidenceAssessment]
    ) -> Dict[str, Any]:
        """
        汇总分析结果

        Args:
            assessments: 证据评估列表

        Returns:
            汇总信息字典
        """
        if not assessments:
            return {
                'total': 0,
                'supporting': 0,
                'opposing': 0,
                'neutral': 0,
                'avg_confidence': 0.0
            }

        total = len(assessments)
        supporting = sum(1 for a in assessments if a.stance == "支持")
        opposing = sum(1 for a in assessments if a.stance == "反对")
        neutral = total - supporting - opposing

        avg_confidence = sum(a.confidence for a in assessments) / total if total > 0 else 0.0

        summary = {
            'total': total,
            'supporting': supporting,
            'opposing': opposing,
            'neutral': neutral,
            'avg_confidence': avg_confidence
        }

        logger.info(f"分析汇总: {summary}")
        return summary

    def get_high_quality_evidence(
        self,
        assessments: List[EvidenceAssessment],
        min_authority: int = 3,
        min_confidence: float = 0.7
    ) -> List[EvidenceAssessment]:
        """
        筛选高质量证据

        Args:
            assessments: 证据评估列表
            min_authority: 最低权威性评分
            min_confidence: 最低置信度

        Returns:
            高质量证据列表
        """
        high_quality = [
            a for a in assessments
            if a.authority_score >= min_authority
            and a.confidence >= min_confidence
        ]

        logger.info(f"高质量证据: {len(high_quality)}/{len(assessments)}")
        return high_quality
