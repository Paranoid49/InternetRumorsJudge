"""
pytest配置和共享fixtures

提供测试所需的通用fixtures和工具
"""
import sys
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Generator

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================
# 环境配置
# ============================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置测试环境变量
    os.environ['TESTING'] = '1'
    os.environ['LOG_LEVEL'] = 'WARNING'  # 减少测试日志输出

    yield

    # 清理
    os.environ.pop('TESTING', None)
    os.environ.pop('LOG_LEVEL', None)


# ============================================
# Mock Embeddings
# ============================================

@pytest.fixture
def mock_embeddings():
    """创建Mock Embeddings对象"""
    embeddings = Mock()
    embeddings.embed_query = Mock(return_value=[0.1] * 1536)
    embeddings.embed_documents = Mock(return_value=[[0.1] * 1536, [0.2] * 1536])
    return embeddings


@pytest.fixture
def mock_embeddings_small():
    """创建小维度的Mock Embeddings（用于快速测试）"""
    embeddings = Mock()
    embeddings.embed_query = Mock(return_value=[0.1] * 10)
    embeddings.embed_documents = Mock(return_value=[[0.1] * 10, [0.2] * 10])
    return embeddings


# ============================================
# 临时目录
# ============================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录，测试后自动清理"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # 清理
    if temp_path.exists():
        shutil.rmtree(temp_path)


# ============================================
# Mock LLM Chains
# ============================================

@pytest.fixture
def mock_parser_chain():
    """创建Mock查询解析链"""
    from src.analyzers.query_parser import QueryAnalysis

    chain = Mock()
    chain.invoke = Mock(return_value=QueryAnalysis(
        entity="测试实体",
        claim="测试主张",
        category="健康养生"  # 使用有效的分类值
    ))
    return chain


@pytest.fixture
def mock_evidence_analyzer():
    """创建Mock证据分析器"""
    from src.analyzers.evidence_analyzer import EvidenceAssessment

    def mock_analyze(claim, evidence, index):
        return EvidenceAssessment(
            relevance="高",
            stance="支持",
            complexity_label=None,
            confidence=0.9,
            authority_score=4,
            reasoning="测试分析",
            key_points=["关键点1", "关键点2"]
        )

    return mock_analyze


@pytest.fixture
def mock_truth_summarizer():
    """创建Mock真相总结器"""
    from src.analyzers.truth_summarizer import FinalVerdict, VerdictType

    summarizer = Mock()
    summarizer.invoke = Mock(return_value=FinalVerdict(
        verdict=VerdictType.TRUE,
        confidence=95,
        summary="这是测试总结",
        risk_level="低"
    ))
    return summarizer


# ============================================
# Mock 知识库
# ============================================

@pytest.fixture
def mock_knowledge_base(mock_embeddings):
    """创建Mock知识库"""
    kb = Mock()
    kb.embeddings = mock_embeddings
    kb.search = Mock(return_value=[
        {
            'content': '测试证据内容',
            'metadata': {
                'source': 'test_source.txt',
                'category': '测试分类'
            }
        }
    ])
    kb.persist_dir = Path('/tmp/test_kb')
    kb.data_dir = Path('/tmp/test_data')
    return kb


# ============================================
# Mock 缓存管理器
# ============================================

@pytest.fixture
def mock_cache_manager():
    """创建Mock缓存管理器"""
    cache_mgr = Mock()
    cache_mgr.get_verdict = Mock(return_value=None)  # 默认缓存未命中
    cache_mgr.set_verdict = Mock()
    return cache_mgr


# ============================================
# Mock Web搜索工具
# ============================================

@pytest.fixture
def mock_web_search_tool():
    """创建Mock Web搜索工具"""
    tool = Mock()
    tool.search = Mock(return_value=[
        {
            'content': '搜索结果1',
            'metadata': {'source': 'https://example.com/1', 'title': '标题1'}
        },
        {
            'content': '搜索结果2',
            'metadata': {'source': 'https://example.com/2', 'title': '标题2'}
        }
    ])
    return tool


# ============================================
# 引擎实例（用于测试）
# ============================================

@pytest.fixture
def engine():
    """创建引擎实例（每次测试都是新的）"""
    from src.core.pipeline import RumorJudgeEngine

    # 重置单例（确保每个测试都是干净的）
    RumorJudgeEngine._instance = None
    RumorJudgeEngine._initialized = False

    engine = RumorJudgeEngine()
    yield engine

    # 清理
    RumorJudgeEngine._instance = None
    RumorJudgeEngine._initialized = False


# ============================================
# 测试数据
# ============================================

@pytest.fixture
def sample_query():
    """示例查询"""
    return "喝隔夜水会致癌吗？"


@pytest.fixture
def sample_evidence():
    """示例证据"""
    return [
        {
            'content': '隔夜水中亚硝酸盐含量很低，不会致癌',
            'metadata': {
                'source': 'health_authority.txt',
                'category': '健康养生'
            }
        },
        {
            'content': '实验证明隔夜水亚硝酸盐含量远未达致癌标准',
            'metadata': {
                'source': 'research_paper.txt',
                'category': '科学研究'
            }
        }
    ]


@pytest.fixture
def sample_verification_result():
    """示例核查结果"""
    from src.core.pipeline import UnifiedVerificationResult, PipelineStage
    from datetime import datetime

    result = UnifiedVerificationResult(
        query="喝隔夜水会致癌吗？",
        entity="隔夜水",
        claim="会致癌",
        category="健康养生",
        retrieved_evidence=[
            {
                'content': '隔夜水不会致癌',
                'metadata': {'source': 'test.txt'}
            }
        ],
        final_verdict="假",
        confidence_score=95,
        summary_report="科学研究表明隔夜水不会致癌"
    )
    return result


# ============================================
# 跳过条件
# ============================================

def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "slow: 标记为慢速测试"
    )
    config.addinivalue_line(
        "markers", "concurrent: 标记为并发测试"
    )
    config.addinivalue_line(
        "markers", "requires_api: 标记为需要API密钥的测试"
    )


def pytest_collection_modifyitems(config, items):
    """根据标记修改测试项"""
    # 跳过需要API的测试（除非显式运行）
    if not config.getoption("--run-api-tests", default=False):
        skip_api = pytest.mark.skip(reason="需要 --run-api-tests 选项")
        for item in items:
            if "requires_api" in item.keywords:
                item.add_marker(skip_api)
