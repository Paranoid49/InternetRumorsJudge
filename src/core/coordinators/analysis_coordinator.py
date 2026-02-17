"""
分析协调器

负责证据分析的协调工作

[v1.1.0] 使用增强版基类功能
"""
import logging
from typing import List, Dict, Any, Optional

from src.core.coordinators.base import BaseCoordinator

logger = logging.getLogger("AnalysisCoordinator")


class AnalysisCoordinator(BaseCoordinator):
    """
    分析协调器

    职责：
    1. 协调证据分析
    2. 批量分析优化
    3. 分析结果聚合

    [v0.7.1] 支持依赖注入，提高可测试性
    [v1.1.0] 使用基类的安全操作方法
    """

    def __init__(self, analyzer: Optional[Any] = None):
        """
        初始化分析协调器

        Args:
            analyzer: EvidenceAnalyzer 实例（可选，用于依赖注入）
                     如果不提供，将在首次使用时自动创建
        """
        super().__init__("AnalysisCoordinator")
        self._analyzer = analyzer

    @property
    def analyzer(self):
        """延迟初始化 EvidenceAnalyzer"""
        if self._analyzer is None:
            from src.analyzers.evidence_analyzer import EvidenceAnalyzer
            self._analyzer = EvidenceAnalyzer()
        return self._analyzer

    def analyze(
        self,
        claim: str,
        evidence_list: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        分析证据列表

        Args:
            claim: 主张陈述
            evidence_list: 证据列表

        Returns:
            证据评估列表 (List[EvidenceAssessment])
        """
        if not evidence_list:
            self.logger.warning("证据列表为空，跳过分析")
            return []

        # 使用基类的安全操作方法
        def _do_analyze():
            return self.analyzer.analyze(
                claim=claim,
                evidence_list=evidence_list
            )

        result = self._safe_operation_with_default(
            f"分析 {len(evidence_list)} 条证据",
            _do_analyze,
            default_value=[]
        )

        if result:
            summary = self.summarize_assessments(result)
            self.logger.info(f"分析完成: {summary}")

        return result or []

    def summarize_assessments(
        self,
        assessments: List[Any]
    ) -> Dict[str, Any]:
        """
        汇总分析结果

        Args:
            assessments: 证据评估列表 (List[EvidenceAssessment])

        Returns:
            汇总信息字典
        """
        if not assessments:
            return {
                'total': 0,
                'supporting': 0,
                'opposing': 0,
                'neutral': 0,
                'partial': 0,
                'avg_confidence': 0.0,
                'avg_authority': 0.0
            }

        total = len(assessments)
        supporting = 0
        opposing = 0
        neutral = 0
        partial = 0
        total_confidence = 0.0
        total_authority = 0.0

        for a in assessments:
            stance = getattr(a, 'stance', '中立/不相关')
            if stance == "支持":
                supporting += 1
            elif stance == "反对":
                opposing += 1
            elif stance == "部分支持/条件性反驳":
                partial += 1
            else:
                neutral += 1

            total_confidence += getattr(a, 'confidence', 0.0)
            total_authority += getattr(a, 'authority_score', 0)

        summary = {
            'total': total,
            'supporting': supporting,
            'opposing': opposing,
            'neutral': neutral,
            'partial': partial,
            'avg_confidence': round(total_confidence / total, 3) if total > 0 else 0.0,
            'avg_authority': round(total_authority / total, 2) if total > 0 else 0.0
        }

        return summary

    def get_high_quality_evidence(
        self,
        assessments: List[Any],
        min_authority: int = 3,
        min_confidence: float = 0.7
    ) -> List[Any]:
        """
        筛选高质量证据

        Args:
            assessments: 证据评估列表 (List[EvidenceAssessment])
            min_authority: 最低权威性评分
            min_confidence: 最低置信度

        Returns:
            高质量证据列表
        """
        high_quality = [
            a for a in assessments
            if getattr(a, 'authority_score', 0) >= min_authority
            and getattr(a, 'confidence', 0) >= min_confidence
        ]

        self.logger.info(f"高质量证据: {len(high_quality)}/{len(assessments)}")
        return high_quality
