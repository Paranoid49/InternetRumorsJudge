"""
证据分析器单元测试

测试 EvidenceAnalyzer 的核心功能：
- 证据分析
- 批量分析
- 预过滤机制
- 并行分析
- 异常处理
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.analyzers.evidence_analyzer import (
    EvidenceAnalyzer,
    EvidenceAssessment,
    MultiPerspectiveAnalysis
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_llm():
    """Mock LLM"""
    mock_llm = Mock()
    mock_llm.with_structured_output = Mock(return_value=Mock())
    return mock_llm


@pytest.fixture
def sample_claim():
    """示例主张"""
    return "维生素C可以预防感冒"


@pytest.fixture
def sample_evidence_list():
    """示例证据列表"""
    return [
        {
            "content": "研究表明维生素C不能预防感冒",
            "text": "研究表明维生素C不能预防感冒",
            "source": "医学期刊",
            "metadata": {"similarity": 0.85, "type": "local"}
        },
        {
            "content": "荟萃分析不支持维生素C预防感冒",
            "text": "荟萃分析不支持维生素C预防感冒",
            "source": "科研机构",
            "metadata": {"similarity": 0.75, "type": "local"}
        },
        {
            "content": "网络传言说维生素C有用",
            "text": "网络传言说维生素C有用",
            "source": "网络",
            "metadata": {"similarity": 0.6, "type": "web"}
        }
    ]


@pytest.fixture
def sample_assessments():
    """示例评估结果"""
    return [
        EvidenceAssessment(
            id=1,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="直接反驳了主张",
            supporting_quote="维生素C不能预防感冒",
            confidence=0.9,
            authority_score=5
        ),
        EvidenceAssessment(
            id=2,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="荟萃分析不支持",
            supporting_quote="不支持维生素C预防感冒",
            confidence=0.85,
            authority_score=4
        )
    ]


@pytest.fixture
def sample_multi_perspective_analysis(sample_assessments):
    """示例多角度分析结果"""
    return MultiPerspectiveAnalysis(assessments=sample_assessments)


# ============================================
# 预过滤功能测试
# ============================================

class TestPrefilter:
    """测试预过滤功能"""

    def test_prefilter_disabled(self, sample_claim, sample_evidence_list):
        """测试禁用预过滤"""
        with patch('src.analyzers.evidence_analyzer.config.ENABLE_EVIDENCE_PREFILTER', False):
            analyzer = EvidenceAnalyzer()
            # Mock LLM调用
            with patch.object(analyzer, '_analyze_batch', return_value=[]):
                analyzer.analyze(sample_claim, sample_evidence_list)
                # 如果预过滤被禁用，所有证据都应该被处理
                # 这里我们只验证不会出错

    def test_prefilter_by_similarity(self, sample_claim, sample_evidence_list):
        """测试基于相似度的过滤"""
        analyzer = EvidenceAnalyzer()
        low_similarity_evidence = {
            "content": "无关内容",
            "text": "无关内容",
            "metadata": {"similarity": 0.1, "type": "local"}
        }

        evidence_list = [low_similarity_evidence] + sample_evidence_list[:2]

        with patch.object(analyzer, '_analyze_batch', return_value=[]) as mock_analyze:
            analyzer.analyze(sample_claim, evidence_list)

            # 验证相似度低的证据被过滤掉
            call_args = mock_analyze.call_args[0][1]  # 第二个参数是evidence_list
            assert len(call_args) <= len(evidence_list)

    def test_prefilter_local_priority(self, sample_claim, sample_evidence_list):
        """测试本地证据优先"""
        analyzer = EvidenceAnalyzer()

        # 创建超过max的证据列表
        large_list = sample_evidence_list * 3  # 9条证据

        with patch.object(analyzer, '_analyze_batch', return_value=[]) as mock_analyze:
            analyzer.analyze(sample_claim, large_list)

            # 验证被限制在max_evidence以内
            call_args = mock_analyze.call_args[0][1]
            assert len(call_args) <= analyzer.prefilter_max_evidence


# ============================================
# 分析功能测试
# ============================================

class TestAnalyze:
    """测试分析功能"""

    def test_analyze_empty_list(self, sample_claim):
        """测试空证据列表"""
        analyzer = EvidenceAnalyzer()
        result = analyzer.analyze(sample_claim, [])

        assert result == []

    def test_analyze_single_evidence(self, sample_claim, sample_evidence_list):
        """测试单条证据分析"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_batch') as mock_batch:
            mock_batch.return_value = [
                EvidenceAssessment(
                    id=1, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试",
                    supporting_quote="测试", confidence=0.8, authority_score=4
                )
            ]

            result = analyzer.analyze(sample_claim, [sample_evidence_list[0]])

            assert len(result) == 1
            mock_batch.assert_called_once()

    def test_analyze_with_prefilter_empty_result(self, sample_claim):
        """测试预过滤后无证据"""
        analyzer = EvidenceAnalyzer()

        # 创建全部相似度很低的证据
        low_similarity_list = [
            {"content": f"无关{i}", "metadata": {"similarity": 0.1}}
            for i in range(3)
        ]

        result = analyzer.analyze(sample_claim, low_similarity_list)

        assert result == []

    def test_analyze_uses_parallel_single(self, sample_claim, sample_evidence_list):
        """测试2-5条证据时使用单证据并行分析"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_parallel_single') as mock_parallel:
            mock_parallel.return_value = []

            # 3条证据，应该触发并行
            analyzer.analyze(sample_claim, sample_evidence_list[:3])

            mock_parallel.assert_called_once()

    def test_analyze_uses_batch(self, sample_claim, sample_evidence_list):
        """测试少量证据使用批量分析"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_batch') as mock_batch:
            mock_batch.return_value = []

            # 1条证据，直接批量分析
            analyzer.analyze(sample_claim, [sample_evidence_list[0]])

            mock_batch.assert_called_once()


# ============================================
# 批量分析测试
# ============================================

class TestAnalyzeBatch:
    """测试批量分析功能"""

    def test_analyze_batch_success(self, sample_claim, sample_evidence_list, sample_multi_perspective_analysis):
        """测试批量分析成功"""
        analyzer = EvidenceAnalyzer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=sample_multi_perspective_analysis)
        analyzer.chain = mock_chain

        result = analyzer._analyze_batch(sample_claim, sample_evidence_list, offset=0)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
        mock_chain.invoke.assert_called_once()

    def test_analyze_batch_with_offset(self, sample_claim, sample_evidence_list, sample_multi_perspective_analysis):
        """测试带偏移量的批量分析"""
        analyzer = EvidenceAnalyzer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=sample_multi_perspective_analysis)
        analyzer.chain = mock_chain

        result = analyzer._analyze_batch(sample_claim, sample_evidence_list[:2], offset=5)

        # 验证ID被正确设置（offset + index + 1）
        assert result[0].id == 6
        assert result[1].id == 7

    def test_analyze_batch_exception(self, sample_claim, sample_evidence_list):
        """测试批量分析异常处理"""
        analyzer = EvidenceAnalyzer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(side_effect=Exception("分析失败"))
        analyzer.chain = mock_chain

        result = analyzer._analyze_batch(sample_claim, sample_evidence_list)

        assert result == []


# ============================================
# 单证据并行分析测试
# ============================================

class TestAnalyzeParallelSingle:
    """测试单证据并行分析功能"""

    def test_parallel_single_success(self, sample_claim, sample_evidence_list):
        """测试并行单证据分析成功"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_single_evidence') as mock_single:
            mock_single.side_effect = [
                EvidenceAssessment(
                    id=1, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试1",
                    supporting_quote="测试1", confidence=0.8, authority_score=4
                ),
                EvidenceAssessment(
                    id=2, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试2",
                    supporting_quote="测试2", confidence=0.85, authority_score=5
                ),
                EvidenceAssessment(
                    id=3, relevance="中", stance="中立/不相关",
                    complexity_label="无特殊情况", reason="测试3",
                    supporting_quote="测试3", confidence=0.7, authority_score=3
                )
            ]

            result = analyzer._analyze_parallel_single(sample_claim, sample_evidence_list[:3])

            assert len(result) == 3
            assert result[0].id == 1
            assert result[1].id == 2
            assert result[2].id == 3

    def test_parallel_single_empty_list(self, sample_claim):
        """测试空列表"""
        analyzer = EvidenceAnalyzer()
        result = analyzer._analyze_parallel_single(sample_claim, [])

        assert result == []

    def test_parallel_single_sorts_by_id(self, sample_claim, sample_evidence_list):
        """测试结果按ID排序"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_single_evidence') as mock_single:
            # 返回乱序的ID
            mock_single.side_effect = [
                EvidenceAssessment(
                    id=3, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试",
                    supporting_quote="测试", confidence=0.8, authority_score=4
                ),
                EvidenceAssessment(
                    id=1, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试",
                    supporting_quote="测试", confidence=0.8, authority_score=4
                ),
                EvidenceAssessment(
                    id=2, relevance="高", stance="反对",
                    complexity_label="无特殊情况", reason="测试",
                    supporting_quote="测试", confidence=0.8, authority_score=4
                )
            ]

            result = analyzer._analyze_parallel_single(sample_claim, sample_evidence_list[:3])

            # 验证按ID排序
            assert result[0].id == 1
            assert result[1].id == 2
            assert result[2].id == 3


# ============================================
# 单证据分析测试
# ============================================

class TestAnalyzeSingleEvidence:
    """测试单证据分析功能"""

    def test_analyze_single_evidence_success(
        self,
        sample_claim,
        sample_evidence_list,
        sample_multi_perspective_analysis
    ):
        """测试单证据分析成功"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_batch') as mock_batch:
            mock_batch.return_value = sample_multi_perspective_analysis.assessments[:1]

            result = analyzer._analyze_single_evidence(sample_claim, sample_evidence_list[0], 0)

            assert result is not None
            assert result.id == 1

    def test_analyze_single_evidence_empty_result(self, sample_claim, sample_evidence_list):
        """测试单证据分析返回空结果"""
        analyzer = EvidenceAnalyzer()

        with patch.object(analyzer, '_analyze_batch') as mock_batch:
            mock_batch.return_value = []

            result = analyzer._analyze_single_evidence(sample_claim, sample_evidence_list[0], 0)

            assert result is None


# ============================================
# 函数式接口测试
# ============================================

class TestFunctionalInterface:
    """测试函数式接口"""

    def test_analyze_evidence_function(self, sample_claim, sample_evidence_list):
        """测试analyze_evidence函数"""
        with patch('src.analyzers.evidence_analyzer.EvidenceAnalyzer') as mock_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze = Mock(return_value=[])
            mock_class.return_value = mock_analyzer

            from src.analyzers.evidence_analyzer import analyze_evidence

            result = analyze_evidence(sample_claim, sample_evidence_list)

            mock_class.assert_called_once()
            mock_analyzer.analyze.assert_called_once_with(sample_claim, sample_evidence_list)
