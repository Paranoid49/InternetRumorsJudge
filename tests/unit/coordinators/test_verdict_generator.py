"""
裁决生成器单元测试

测试 VerdictGenerator 的核心功能：
- 裁决生成
- 兜底机制
- 格式化输出
- 关键信息提取
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.core.coordinators.verdict_generator import VerdictGenerator
from src.analyzers.truth_summarizer import FinalVerdict, VerdictType


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def verdict_generator():
    """创建裁决生成器实例"""
    return VerdictGenerator()


@pytest.fixture
def sample_query():
    """示例查询"""
    return "维生素C可以预防感冒吗？"


@pytest.fixture
def sample_entity():
    """示例实体"""
    return "维生素C"


@pytest.fixture
def sample_claim():
    """示例主张"""
    return "可以预防感冒"


@pytest.fixture
def sample_evidence_list():
    """示例证据列表"""
    return [
        {
            "content": "研究表明维生素C对感冒没有预防作用",
            "metadata": {"source": "医学期刊"}
        },
        {
            "content": "荟萃分析显示不支持维生素C预防感冒",
            "metadata": {"source": "科研机构"}
        }
    ]


@pytest.fixture
def sample_assessments():
    """示例证据评估"""
    from src.analyzers.evidence_analyzer import EvidenceAssessment
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
        )
    ]


@pytest.fixture
def sample_final_verdict():
    """示例最终裁决"""
    return FinalVerdict(
        verdict=VerdictType.FALSE,
        confidence=90,
        summary="多项科学研究表明维生素C不能预防感冒",
        risk_level="低"
    )


# ============================================
# 裁决生成测试
# ============================================

class TestGenerate:
    """测试裁决生成功能"""

    def test_generate_with_assessments(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments,
        sample_final_verdict
    ):
        """测试有评估结果时的裁决生成 - 使用依赖注入"""
        # 创建 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize.return_value = sample_final_verdict

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        result = generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=sample_assessments
        )

        assert result is not None
        assert isinstance(result, FinalVerdict)
        assert result.verdict == VerdictType.FALSE
        assert result.confidence == 90
        mock_summarizer.summarize.assert_called_once()

    def test_generate_without_assessments(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_final_verdict
    ):
        """测试无评估结果时使用兜底机制 - 使用依赖注入"""
        # 创建 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize_based_on_knowledge.return_value = sample_final_verdict

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        result = generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=[]
        )

        assert result is not None
        mock_summarizer.summarize_based_on_knowledge.assert_called_once()

    def test_generate_with_none_assessments(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_final_verdict
    ):
        """测试 assessments 为 None 时使用兜底机制"""
        # 创建 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize_based_on_knowledge.return_value = sample_final_verdict

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        result = generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=None
        )

        assert result is not None
        mock_summarizer.summarize_based_on_knowledge.assert_called_once()

    def test_generate_exception_handling(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments
    ):
        """测试异常处理"""
        # 创建会抛出异常的 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize.side_effect = Exception("生成失败")

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        result = generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=sample_assessments
        )

        assert result is None

    def test_generate_full_claim_construction(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments,
        sample_final_verdict
    ):
        """测试完整 claim 的构建"""
        # 创建 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize.return_value = sample_final_verdict

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=sample_assessments
        )

        # 验证完整 claim 被正确构建
        called_args = mock_summarizer.summarize.call_args
        full_claim = called_args[0][0]  # 第一个位置参数
        assert sample_entity in full_claim
        assert sample_claim in full_claim

    def test_generate_fallback_to_query(
        self,
        sample_query,
        sample_evidence_list,
        sample_final_verdict
    ):
        """测试当 entity 和 claim 都为 None 时回退到 query"""
        # 创建 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize_based_on_knowledge.return_value = sample_final_verdict

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        generator.generate(
            query=sample_query,
            entity=None,
            claim=None,
            evidence_list=sample_evidence_list,
            assessments=[]
        )

        # 验证回退到 query
        called_args = mock_summarizer.summarize_based_on_knowledge.call_args
        full_claim = called_args[0][0]
        assert full_claim == sample_query

    def test_generate_returns_none_on_summarize_failure(
        self,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments
    ):
        """测试 summarize 返回 None 时的处理"""
        # 创建返回 None 的 Mock summarizer
        mock_summarizer = Mock()
        mock_summarizer.summarize.return_value = None

        # 使用依赖注入创建生成器
        generator = VerdictGenerator(summarizer=mock_summarizer)

        result = generator.generate(
            query=sample_query,
            entity=sample_entity,
            claim=sample_claim,
            evidence_list=sample_evidence_list,
            assessments=sample_assessments
        )

        assert result is None


# ============================================
# 格式化输出测试
# ============================================

class TestFormatForCache:
    """测试格式化输出功能"""

    def test_format_for_cache(self, verdict_generator, sample_final_verdict):
        """测试格式化为缓存格式"""
        result = verdict_generator.format_for_cache(sample_final_verdict)

        assert isinstance(result, dict)
        assert 'verdict' in result
        assert 'confidence' in result
        assert 'summary' in result
        assert 'risk_level' in result

    def test_format_for_cache_values(self, verdict_generator, sample_final_verdict):
        """测试格式化后的值正确"""
        result = verdict_generator.format_for_cache(sample_final_verdict)

        assert result['verdict'] == VerdictType.FALSE
        assert result['confidence'] == 90
        assert result['summary'] == "多项科学研究表明维生素C不能预防感冒"
        assert result['risk_level'] == "低"


# ============================================
# 关键信息提取测试
# ============================================

class TestExtractKeyInfo:
    """测试关键信息提取功能"""

    def test_extract_key_info(self, verdict_generator, sample_final_verdict):
        """测试提取关键信息"""
        result = verdict_generator.extract_key_info(sample_final_verdict)

        assert isinstance(result, dict)
        assert result['verdict'] == str(VerdictType.FALSE)
        assert result['confidence'] == 90
        assert result['summary'] == "多项科学研究表明维生素C不能预防感冒"
        assert result['risk_level'] == "低"

    def test_extract_key_info_fields(self, verdict_generator, sample_final_verdict):
        """测试提取的字段完整"""
        result = verdict_generator.extract_key_info(sample_final_verdict)

        expected_keys = {'verdict', 'confidence', 'summary', 'risk_level'}
        assert set(result.keys()) == expected_keys

    def test_extract_key_info_verdict_as_string(self, verdict_generator, sample_final_verdict):
        """测试裁决转换为字符串"""
        result = verdict_generator.extract_key_info(sample_final_verdict)

        assert isinstance(result['verdict'], str)
        # str(Enum) 返回枚举名，.value 返回枚举值
        # 这里我们验证返回的是字符串类型（可能是枚举名或值）
        assert result['verdict'] in ["VerdictType.FALSE", "假"]
