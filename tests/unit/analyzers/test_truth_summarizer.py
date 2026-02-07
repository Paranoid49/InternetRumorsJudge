"""
真相总结器单元测试

测试 TruthSummarizer 的核心功能：
- 真相总结
- 重试机制
- 兜底分析
- 基于规则的fallback
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.analyzers.truth_summarizer import (
    TruthSummarizer,
    summarize_truth,
    summarize_with_fallback,
    FinalVerdict,
    VerdictType,
    EvidenceAssessment
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
def sample_assessments():
    """示例证据评估"""
    return [
        EvidenceAssessment(
            id=1,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="多项研究不支持",
            supporting_quote="维生素C不能预防感冒",
            confidence=0.9,
            authority_score=5
        ),
        EvidenceAssessment(
            id=2,
            relevance="高",
            stance="反对",
            complexity_label="无特殊情况",
            reason="荟萃分析结论",
            supporting_quote="不支持预防效果",
            confidence=0.85,
            authority_score=5
        ),
        EvidenceAssessment(
            id=3,
            relevance="中",
            stance="中立/不相关",
            complexity_label="无特殊情况",
            reason="可能缩短病程",
            supporting_quote="轻微效果",
            confidence=0.6,
            authority_score=4
        )
    ]


@pytest.fixture
def sample_final_verdict():
    """示例最终裁决"""
    return FinalVerdict(
        summary="多项科学研究表明维生素C不能预防感冒",
        verdict=VerdictType.FALSE,
        confidence=90,
        risk_level="低"
    )


# ============================================
# 总结功能测试
# ============================================

class TestSummarize:
    """测试总结功能"""

    def test_summarize_success(self, sample_claim, sample_assessments, sample_final_verdict):
        """测试总结成功"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=sample_final_verdict)
        summarizer.chain = mock_chain

        result = summarizer.summarize(sample_claim, sample_assessments)

        assert result is not None
        assert isinstance(result, FinalVerdict)
        assert result.verdict == VerdictType.FALSE
        assert result.confidence == 90
        mock_chain.invoke.assert_called_once()

    def test_summarize_empty_assessments(self, sample_claim):
        """测试空评估列表"""
        summarizer = TruthSummarizer()
        result = summarizer.summarize(sample_claim, [])

        assert result is not None
        assert result.verdict == VerdictType.INSUFFICIENT
        assert result.confidence == 0
        assert "无法对该主张的真实性做出判断" in result.summary

    def test_summarize_with_retry(self, sample_claim, sample_assessments, sample_final_verdict):
        """测试重试机制"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        # 前两次失败，第三次成功
        mock_chain.invoke = Mock(side_effect=[
            Exception("失败1"),
            Exception("失败2"),
            sample_final_verdict
        ])
        summarizer.chain = mock_chain

        result = summarizer.summarize(sample_claim, sample_assessments)

        assert result is not None
        assert mock_chain.invoke.call_count == 3

    def test_summarize_all_retries_failed(self, sample_claim, sample_assessments):
        """测试所有重试都失败"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(side_effect=Exception("始终失败"))
        summarizer.chain = mock_chain

        result = summarizer.summarize(sample_claim, sample_assessments)

        # 应该使用规则兜底
        assert result is not None
        assert "系统自动生成报告" in result.summary

    def test_summarize_formats_evidence_context(self, sample_claim, sample_assessments, sample_final_verdict):
        """测试证据上下文格式化"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=sample_final_verdict)
        summarizer.chain = mock_chain

        summarizer.summarize(sample_claim, sample_assessments)

        # 验证调用参数
        call_args = mock_chain.invoke.call_args[0][0]
        assert 'claim' in call_args
        assert 'evidence_context' in call_args
        assert '证据 #1' in call_args['evidence_context']
        assert '证据 #2' in call_args['evidence_context']


# ============================================
# 规则兜底测试
# ============================================

class TestRuleBasedFallback:
    """测试基于规则的兜底逻辑"""

    def test_rule_based_fallback_opposing(self, sample_claim, sample_assessments):
        """测试反对证据占多数"""
        summarizer = TruthSummarizer()
        result = summarizer._rule_based_fallback(sample_claim, sample_assessments)

        assert result is not None
        # 反对证据多，应该判定为假
        assert result.verdict in [VerdictType.FALSE, VerdictType.LIKELY_FALSE]
        assert "系统自动生成报告" in result.summary

    def test_rule_based_fallback_supporting(self, sample_claim):
        """测试支持证据占多数"""
        supporting_assessments = [
            EvidenceAssessment(
                id=i,
                relevance="高",
                stance="支持",
                complexity_label="无特殊情况",
                reason=f"支持{i}",
                supporting_quote=f"支持{i}",
                confidence=0.8,
                authority_score=5
            )
            for i in range(1, 4)
        ]

        summarizer = TruthSummarizer()
        result = summarizer._rule_based_fallback(sample_claim, supporting_assessments)

        assert result is not None
        # 支持证据多，应该判定为真
        assert result.verdict in [VerdictType.TRUE, VerdictType.LIKELY_TRUE]

    def test_rule_based_fallback_mixed(self, sample_claim):
        """测试混合证据"""
        mixed_assessments = [
            EvidenceAssessment(
                id=1, relevance="高", stance="支持",
                complexity_label="无特殊情况", reason="支持",
                supporting_quote="支持", confidence=0.8, authority_score=5
            ),
            EvidenceAssessment(
                id=2, relevance="高", stance="反对",
                complexity_label="无特殊情况", reason="反对",
                supporting_quote="反对", confidence=0.8, authority_score=5
            )
        ]

        summarizer = TruthSummarizer()
        result = summarizer._rule_based_fallback(sample_claim, mixed_assessments)

        assert result is not None
        # 混合证据，应该判定为争议或不确定
        assert result.verdict in [VerdictType.CONTROVERSIAL, VerdictType.LIKELY_TRUE, VerdictType.LIKELY_FALSE]

    def test_rule_based_fallback_empty(self, sample_claim):
        """测试空评估列表"""
        summarizer = TruthSummarizer()
        result = summarizer._rule_based_fallback(sample_claim, [])

        assert result.verdict == VerdictType.INSUFFICIENT
        assert result.confidence == 0

    def test_rule_based_fallback_includes_summary(self, sample_claim, sample_assessments):
        """测试兜底summary包含统计信息"""
        summarizer = TruthSummarizer()
        result = summarizer._rule_based_fallback(sample_claim, sample_assessments)

        assert "系统分析了 3 条证据" in result.summary
        assert "统计结果" in result.summary
        assert "支持" in result.summary
        assert "反对" in result.summary


# ============================================
# 基于知识的兜底测试
# ============================================

class TestSummarizeBasedOnKnowledge:
    """测试基于内部知识的兜底分析"""

    def test_summarize_based_on_knowledge_success(self, sample_claim, sample_final_verdict):
        """测试基于知识的总结成功"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=sample_final_verdict)
        summarizer.fallback_chain = mock_chain

        result = summarizer.summarize_based_on_knowledge(sample_claim)

        assert result is not None
        assert isinstance(result, FinalVerdict)
        mock_chain.invoke.assert_called_once_with({"claim": sample_claim})

    def test_summarize_based_on_knowledge_with_retry(self, sample_claim, sample_final_verdict):
        """测试重试机制"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(side_effect=[
            Exception("失败1"),
            Exception("失败2"),
            sample_final_verdict
        ])
        summarizer.fallback_chain = mock_chain

        result = summarizer.summarize_based_on_knowledge(sample_claim)

        assert result is not None
        assert mock_chain.invoke.call_count == 3

    def test_summarize_based_on_knowledge_all_failed(self, sample_claim):
        """测试所有重试失败"""
        summarizer = TruthSummarizer()

        # 创建一个有 invoke 方法的 mock 对象
        from unittest.mock import Mock
        mock_chain = Mock()
        mock_chain.invoke = Mock(side_effect=Exception("始终失败"))
        summarizer.fallback_chain = mock_chain

        result = summarizer.summarize_based_on_knowledge(sample_claim)

        assert result is None


# ============================================
# 函数式接口测试
# ============================================

class TestFunctionalInterface:
    """测试函数式接口"""

    def test_summarize_truth_function(self, sample_claim, sample_assessments, sample_final_verdict):
        """测试summarize_truth函数"""
        with patch('src.analyzers.truth_summarizer.TruthSummarizer') as mock_class:
            mock_summarizer = Mock()
            mock_summarizer.summarize = Mock(return_value=sample_final_verdict)
            mock_class.return_value = mock_summarizer

            result = summarize_truth(sample_claim, sample_assessments)

            mock_class.assert_called_once()
            mock_summarizer.summarize.assert_called_once_with(sample_claim, sample_assessments)

    def test_summarize_with_fallback_function(self, sample_claim, sample_final_verdict):
        """测试summarize_with_fallback函数"""
        with patch('src.analyzers.truth_summarizer.TruthSummarizer') as mock_class:
            mock_summarizer = Mock()
            mock_summarizer.summarize_based_on_knowledge = Mock(return_value=sample_final_verdict)
            mock_class.return_value = mock_summarizer

            result = summarize_with_fallback(sample_claim)

            mock_class.assert_called_once()
            mock_summarizer.summarize_based_on_knowledge.assert_called_once_with(sample_claim)


# ============================================
# Pydantic模型测试
# ============================================

class TestModels:
    """测试Pydantic模型"""

    def test_final_verdict_model(self):
        """测试FinalVerdict模型"""
        verdict = FinalVerdict(
            summary="测试总结",
            verdict=VerdictType.FALSE,
            confidence=90,
            risk_level="低"
        )

        assert verdict.summary == "测试总结"
        assert verdict.verdict == VerdictType.FALSE
        assert verdict.confidence == 90
        assert verdict.risk_level == "低"

    def test_verdict_type_enum(self):
        """测试VerdictType枚举"""
        assert VerdictType.TRUE.value == "真"
        assert VerdictType.FALSE.value == "假"
        assert VerdictType.INSUFFICIENT.value == "证据不足"
        assert VerdictType.CONTROVERSIAL.value == "存在争议"

    def test_final_verdict_dict_method(self, sample_final_verdict):
        """测试FinalVerdict的dict方法"""
        verdict_dict = sample_final_verdict.dict()

        assert isinstance(verdict_dict, dict)
        assert 'summary' in verdict_dict
        assert 'verdict' in verdict_dict
        assert 'confidence' in verdict_dict
        assert 'risk_level' in verdict_dict

    def test_final_verdict_validation(self):
        """测试FinalVerdict验证"""
        # confidence超出范围应该抛出错误
        with pytest.raises(Exception):
            FinalVerdict(
                summary="测试",
                verdict=VerdictType.FALSE,
                confidence=150,  # 超出0-100范围
                risk_level="低"
            )
