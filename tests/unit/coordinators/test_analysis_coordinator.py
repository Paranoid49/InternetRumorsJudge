"""
分析协调器单元测试

测试 AnalysisCoordinator 的核心功能：
- 证据分析协调
- 批量分析优化
- 分析结果聚合
- 高质量证据筛选
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.core.coordinators.analysis_coordinator import AnalysisCoordinator
from src.analyzers.evidence_analyzer import EvidenceAssessment


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def analysis_coordinator():
    """创建分析协调器实例"""
    return AnalysisCoordinator()


@pytest.fixture
def sample_claim():
    """示例主张"""
    return "维生素C可以预防感冒"


@pytest.fixture
def sample_evidence_list():
    """示例证据列表"""
    return [
        {
            "content": "研究表明维生素C对感冒没有预防作用",
            "text": "研究表明维生素C对感冒没有预防作用",
            "metadata": {"source": "医学期刊", "type": "local"}
        },
        {
            "content": "多项荟萃分析显示维生素C不能预防感冒",
            "text": "多项荟萃分析显示维生素C不能预防感冒",
            "metadata": {"source": "科研机构", "type": "local"}
        },
        {
            "content": "有些研究表明维生素C可能缩短感冒病程",
            "text": "有些研究表明维生素C可能缩短感冒病程",
            "metadata": {"source": "营养研究", "type": "local"}
        }
    ]


@pytest.fixture
def sample_assessments():
    """示例证据评估列表"""
    return [
        EvidenceAssessment(
            id=1,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="多项研究不支持",
            supporting_quote="研究表明维生素C对感冒没有预防作用",
            confidence=0.88,
            authority_score=5
        ),
        EvidenceAssessment(
            id=2,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="荟萃分析结论",
            supporting_quote="荟萃分析显示维生素C不能预防感冒",
            confidence=0.9,
            authority_score=5
        ),
        EvidenceAssessment(
            id=3,
            relevance="中",
            stance="中立/不相关",
            complexity_label="无特殊情况",
            reason="可能缩短病程",
            supporting_quote="有些研究表明维生素C可能缩短感冒病程",
            confidence=0.75,  # 修改为0.75以符合测试阈值
            authority_score=4
        )
    ]


# ============================================
# 证据分析测试
# ============================================

class TestAnalyze:
    """测试证据分析功能"""

    def test_analyze_success(self, sample_claim, sample_evidence_list, sample_assessments):
        """测试分析成功 - 使用依赖注入的 Mock analyzer"""
        # 创建 Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.return_value = sample_assessments

        # 使用依赖注入创建协调器
        coordinator = AnalysisCoordinator(analyzer=mock_analyzer)

        result = coordinator.analyze(sample_claim, sample_evidence_list)

        assert isinstance(result, list)
        assert all(isinstance(a, EvidenceAssessment) for a in result)
        mock_analyzer.analyze.assert_called_once_with(
            claim=sample_claim,
            evidence_list=sample_evidence_list
        )

    def test_analyze_empty_evidence_list(self, analysis_coordinator, sample_claim):
        """测试空证据列表"""
        result = analysis_coordinator.analyze(sample_claim, [])

        assert result == []

    def test_analyze_exception(self, sample_claim, sample_evidence_list):
        """测试分析异常处理 - 使用依赖注入的 Mock analyzer"""
        # 创建会抛出异常的 Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.analyze.side_effect = Exception("分析失败")

        # 使用依赖注入创建协调器
        coordinator = AnalysisCoordinator(analyzer=mock_analyzer)

        result = coordinator.analyze(sample_claim, sample_evidence_list)

        assert result == []


# ============================================
# 分析汇总测试
# ============================================

class TestSummarizeAssessments:
    """测试分析汇总功能"""

    def test_summarize_with_assessments(self, analysis_coordinator, sample_assessments):
        """测试有评估结果的汇总"""
        result = analysis_coordinator.summarize_assessments(sample_assessments)

        assert result['total'] == 3
        assert result['supporting'] == 0
        assert result['opposing'] == 2
        assert result['neutral'] == 1
        assert 0.7 < result['avg_confidence'] < 0.9

    def test_summarize_empty_assessments(self, analysis_coordinator):
        """测试空评估列表的汇总"""
        result = analysis_coordinator.summarize_assessments([])

        assert result['total'] == 0
        assert result['supporting'] == 0
        assert result['opposing'] == 0
        assert result['neutral'] == 0
        assert result['avg_confidence'] == 0.0

    def test_summarize_all_supporting(self, analysis_coordinator):
        """测试全部支持的评估"""
        assessments = [
            EvidenceAssessment(
                id=i,
                relevance="高",
                stance="支持",
                complexity_label="无特殊情况",
                reason="支持点",
                supporting_quote="支持引用",
                confidence=0.85,
                authority_score=4
            )
            for i in range(1, 4)
        ]

        result = analysis_coordinator.summarize_assessments(assessments)

        assert result['total'] == 3
        assert result['supporting'] == 3
        assert result['opposing'] == 0
        assert result['neutral'] == 0

    def test_summarize_mixed_stances(self, analysis_coordinator):
        """测试混合立场的评估"""
        assessments = [
            EvidenceAssessment(
                id=1, relevance="高", stance="支持",
                complexity_label="无特殊情况",
                reason="支持", supporting_quote="支持引用",
                confidence=0.8, authority_score=4
            ),
            EvidenceAssessment(
                id=2, relevance="高", stance="反对",
                complexity_label="无特殊情况",
                reason="反对", supporting_quote="反对引用",
                confidence=0.8, authority_score=4
            ),
            EvidenceAssessment(
                id=3, relevance="高", stance="中立/不相关",
                complexity_label="无特殊情况",
                reason="中立", supporting_quote="中立引用",
                confidence=0.8, authority_score=4
            )
        ]

        result = analysis_coordinator.summarize_assessments(assessments)

        assert result['total'] == 3
        assert result['supporting'] == 1
        assert result['opposing'] == 1
        assert result['neutral'] == 1


# ============================================
# 高质量证据筛选测试
# ============================================

class TestGetHighQualityEvidence:
    """测试高质量证据筛选功能"""

    def test_get_high_quality_evidence(self, analysis_coordinator, sample_assessments):
        """测试筛选高质量证据"""
        result = analysis_coordinator.get_high_quality_evidence(
            sample_assessments,
            min_authority=5,
            min_confidence=0.8
        )

        # 应该筛选出前两个（authority_score=5, confidence>=0.8）
        assert len(result) == 2
        assert all(a.authority_score >= 5 and a.confidence >= 0.8 for a in result)

    def test_get_high_quality_none_meet_criteria(self, analysis_coordinator, sample_assessments):
        """测试没有符合条件的证据"""
        result = analysis_coordinator.get_high_quality_evidence(
            sample_assessments,
            min_authority=10,  # 过高阈值
            min_confidence=0.99
        )

        assert len(result) == 0

    def test_get_high_quality_all_meet_criteria(self, analysis_coordinator, sample_assessments):
        """测试所有证据都符合条件"""
        result = analysis_coordinator.get_high_quality_evidence(
            sample_assessments,
            min_authority=1,  # 低阈值
            min_confidence=0.5
        )

        assert len(result) == 3

    def test_get_high_quality_empty_list(self, analysis_coordinator):
        """测试空列表"""
        result = analysis_coordinator.get_high_quality_evidence(
            [],
            min_authority=3,
            min_confidence=0.7
        )

        assert result == []

    def test_get_high_quality_custom_thresholds(self, analysis_coordinator, sample_assessments):
        """测试自定义阈值"""
        result = analysis_coordinator.get_high_quality_evidence(
            sample_assessments,
            min_authority=4,
            min_confidence=0.75
        )

        # 所有三个都符合（authority>=4, confidence>=0.7）
        assert len(result) == 3
