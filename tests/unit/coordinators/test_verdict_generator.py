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
        verdict_generator,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments,
        sample_final_verdict
    ):
        """测试有评估结果时的裁决生成"""
        with patch('src.core.coordinators.verdict_generator.summarize_truth') as mock_summarize:
            mock_summarize.return_value = sample_final_verdict

            result = verdict_generator.generate(
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
            mock_summarize.assert_called_once()

    def test_generate_without_assessments(
        self,
        verdict_generator,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_final_verdict
    ):
        """测试无评估结果时使用兜底机制"""
        with patch('src.core.coordinators.verdict_generator.summarize_with_fallback') as mock_fallback:
            mock_fallback.return_value = sample_final_verdict

            result = verdict_generator.generate(
                query=sample_query,
                entity=sample_entity,
                claim=sample_claim,
                evidence_list=sample_evidence_list,
                assessments=[]
            )

            assert result is not None
            mock_fallback.assert_called_once()

    def test_generate_with_none_assessments(
        self,
        verdict_generator,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_final_verdict
    ):
        """测试assessments为None时使用兜底机制"""
        with patch('src.core.coordinators.verdict_generator.summarize_with_fallback') as mock_fallback:
            mock_fallback.return_value = sample_final_verdict

            result = verdict_generator.generate(
                query=sample_query,
                entity=sample_entity,
                claim=sample_claim,
                evidence_list=sample_evidence_list,
                assessments=None
            )

            assert result is not None
            mock_fallback.assert_called_once()

    def test_generate_exception_handling(
        self,
        verdict_generator,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments
    ):
        """测试异常处理"""
        with patch('src.core.coordinators.verdict_generator.summarize_truth') as mock_summarize:
            mock_summarize.side_effect = Exception("生成失败")

            result = verdict_generator.generate(
                query=sample_query,
                entity=sample_entity,
                claim=sample_claim,
                evidence_list=sample_evidence_list,
                assessments=sample_assessments
            )

            assert result is None

    def test_generate_full_claim_construction(
        self,
        verdict_generator,
        sample_query,
        sample_evidence_list,
        sample_assessments,
        sample_final_verdict
    ):
        """测试完整claim的构造"""
        with patch('src.core.coordinators.verdict_generator.summarize_truth') as mock_summarize:
            mock_summarize.return_value = sample_final_verdict

            # 有entity和claim
            verdict_generator.generate(
                query=sample_query,
                entity="维生素C",
                claim="可以预防感冒",
                evidence_list=sample_evidence_list,
                assessments=sample_assessments
            )

            # 验证传入的claim是完整的
            call_args = mock_summarize.call_args[0]
            assert "维生素C" in call_args[0]
            assert "可以预防感冒" in call_args[0]

    def test_generate_fallback_to_query(
        self,
        verdict_generator,
        sample_query,
        sample_evidence_list,
        sample_assessments,
        sample_final_verdict
    ):
        """测试fallback到原始查询"""
        with patch('src.core.coordinators.verdict_generator.summarize_truth') as mock_summarize:
            mock_summarize.return_value = sample_final_verdict

            # entity和claim都为None
            verdict_generator.generate(
                query=sample_query,
                entity=None,
                claim=None,
                evidence_list=sample_evidence_list,
                assessments=sample_assessments
            )

            # 验证使用原始查询
            call_args = mock_summarize.call_args[0]
            assert call_args[0] == sample_query

    def test_generate_returns_none_on_summarize_failure(
        self,
        verdict_generator,
        sample_query,
        sample_entity,
        sample_claim,
        sample_evidence_list,
        sample_assessments
    ):
        """测试summarize返回None时的情况"""
        with patch('src.core.coordinators.verdict_generator.summarize_truth') as mock_summarize:
            mock_summarize.return_value = None

            result = verdict_generator.generate(
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
