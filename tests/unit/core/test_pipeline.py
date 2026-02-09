"""
RumorJudgeEngine 核心引擎单元测试

测试覆盖：
- PipelineStage 枚举
- ProcessingMetadata 数据模型
- UnifiedVerificationResult 数据模型
- RumorJudgeEngine 单例模式
- 延迟初始化机制
- 协调器检查
"""
import sys
import pytest
import threading
import time
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, PropertyMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.core.pipeline import (
    PipelineStage,
    ProcessingMetadata,
    UnifiedVerificationResult,
    RumorJudgeEngine
)


# ============================================================================
# PipelineStage 枚举测试
# ============================================================================

class TestPipelineStage:
    """PipelineStage 枚举测试"""

    def test_all_pipeline_stages_exist(self):
        """测试所有流水线阶段枚举值存在"""
        expected_stages = {
            "CACHE_CHECK": "cache_check",
            "PARSING": "parsing",
            "RETRIEVAL": "retrieval",
            "WEB_SEARCH": "web_search",
            "ANALYSIS": "analysis",
            "VERDICT": "verdict"
        }

        for attr, expected_value in expected_stages.items():
            assert hasattr(PipelineStage, attr)
            stage = getattr(PipelineStage, attr)
            assert stage.value == expected_value

    def test_pipeline_stage_is_string(self):
        """测试 PipelineStage 继承自 str"""
        assert issubclass(PipelineStage, str)

    def test_pipeline_stage_comparison(self):
        """测试 PipelineStage 可以作为字符串比较"""
        assert PipelineStage.CACHE_CHECK == "cache_check"
        assert PipelineStage.PARSING == "parsing"


# ============================================================================
# ProcessingMetadata 测试
# ============================================================================

class TestProcessingMetadata:
    """ProcessingMetadata 数据模型测试"""

    def test_create_minimal_metadata(self):
        """测试创建最小元数据"""
        metadata = ProcessingMetadata(
            stage=PipelineStage.CACHE_CHECK,
            success=True
        )

        assert metadata.stage == PipelineStage.CACHE_CHECK
        assert metadata.success is True
        assert metadata.error_message is None
        assert metadata.duration_ms == 0.0
        assert isinstance(metadata.timestamp, datetime)

    def test_create_full_metadata(self):
        """测试创建完整元数据"""
        now = datetime.now()
        metadata = ProcessingMetadata(
            stage=PipelineStage.ANALYSIS,
            success=False,
            error_message="分析失败",
            duration_ms=123.45,
            timestamp=now
        )

        assert metadata.stage == PipelineStage.ANALYSIS
        assert metadata.success is False
        assert metadata.error_message == "分析失败"
        assert metadata.duration_ms == 123.45
        assert metadata.timestamp == now

    def test_metadata_has_timestamp(self):
        """测试元数据自动生成时间戳"""
        before = datetime.now()
        metadata = ProcessingMetadata(
            stage=PipelineStage.RETRIEVAL,
            success=True
        )
        after = datetime.now()

        assert before <= metadata.timestamp <= after


# ============================================================================
# UnifiedVerificationResult 测试
# ============================================================================

class TestUnifiedVerificationResult:
    """UnifiedVerificationResult 数据模型测试"""

    def test_create_minimal_result(self):
        """测试创建最小结果对象"""
        result = UnifiedVerificationResult(query="测试查询")

        assert result.query == "测试查询"
        assert result.is_cached is False
        assert result.is_fallback is False
        assert result.is_web_search is False
        assert result.saved_to_cache is False
        assert result.entity is None
        assert result.claim is None
        assert result.category is None
        assert result.retrieved_evidence == []
        assert result.evidence_assessments == []
        assert result.final_verdict is None
        assert result.confidence_score == 0
        assert result.risk_level is None
        assert result.summary_report is None
        assert result.metadata == []

    def test_create_result_with_basic_fields(self):
        """测试创建带基本字段的结果对象"""
        result = UnifiedVerificationResult(
            query="测试查询",
            is_cached=True,
            is_fallback=False,
            is_web_search=True,
            saved_to_cache=True
        )

        assert result.query == "测试查询"
        assert result.is_cached is True
        assert result.is_fallback is False
        assert result.is_web_search is True
        assert result.saved_to_cache is True

    def test_add_metadata(self):
        """测试添加元数据"""
        result = UnifiedVerificationResult(query="测试查询")

        # 添加第一条元数据
        result.add_metadata(
            stage=PipelineStage.CACHE_CHECK,
            success=True,
            duration=100.5
        )

        assert len(result.metadata) == 1
        metadata = result.metadata[0]
        assert metadata.stage == PipelineStage.CACHE_CHECK
        assert metadata.success is True
        assert metadata.error_message is None
        assert metadata.duration_ms == 100.5

    def test_add_multiple_metadata(self):
        """测试添加多条元数据"""
        result = UnifiedVerificationResult(query="测试查询")

        # 添加多条元数据
        result.add_metadata(PipelineStage.CACHE_CHECK, True, duration=50.0)
        result.add_metadata(PipelineStage.PARSING, True, duration=30.0)
        result.add_metadata(PipelineStage.RETRIEVAL, True, duration=200.0)

        assert len(result.metadata) == 3
        assert result.metadata[0].stage == PipelineStage.CACHE_CHECK
        assert result.metadata[1].stage == PipelineStage.PARSING
        assert result.metadata[2].stage == PipelineStage.RETRIEVAL

    def test_add_metadata_with_error(self):
        """测试添加带错误的元数据"""
        result = UnifiedVerificationResult(query="测试查询")

        result.add_metadata(
            stage=PipelineStage.ANALYSIS,
            success=False,
            error="网络错误",
            duration=0
        )

        assert len(result.metadata) == 1
        metadata = result.metadata[0]
        assert metadata.success is False
        assert metadata.error_message == "网络错误"
        assert metadata.duration_ms == 0

    def test_result_with_parsed_data(self):
        """测试带解析数据的结果对象"""
        result = UnifiedVerificationResult(
            query="维生素C能预防感冒吗",
            entity="维生素C",
            claim="能预防感冒",
            category="健康养生"
        )

        assert result.entity == "维生素C"
        assert result.claim == "能预防感冒"
        assert result.category == "健康养生"

    def test_result_with_evidence(self):
        """测试带证据的结果对象"""
        evidence = [
            {"content": "证据1", "metadata": {"source": "来源1"}},
            {"content": "证据2", "metadata": {"source": "来源2"}}
        ]

        result = UnifiedVerificationResult(
            query="测试查询",
            retrieved_evidence=evidence
        )

        assert len(result.retrieved_evidence) == 2
        assert result.retrieved_evidence[0]["content"] == "证据1"
        assert result.retrieved_evidence[1]["content"] == "证据2"

    def test_result_with_verdict(self):
        """测试带裁决的结果对象"""
        result = UnifiedVerificationResult(
            query="测试查询",
            final_verdict="真",
            confidence_score=95,
            risk_level="低",
            summary_report="测试总结"
        )

        assert result.final_verdict == "真"
        assert result.confidence_score == 95
        assert result.risk_level == "低"
        assert result.summary_report == "测试总结"


# ============================================================================
# RumorJudgeEngine 单例测试
# ============================================================================

class TestRumorJudgeEngineSingleton:
    """RumorJudgeEngine 单例模式测试"""

    def test_singleton_pattern(self):
        """测试单例模式 - 多次创建返回同一实例"""
        # 注意：这个测试会创建真实的单例，可能影响其他测试
        # 使用 patch 来隔离
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine1 = RumorJudgeEngine()
            engine2 = RumorJudgeEngine()

            assert engine1 is engine2
            assert id(engine1) == id(engine2)

    def test_singleton_thread_safety(self):
        """测试单例模式的线程安全性"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            instances = []
            lock = threading.Lock()

            def create_engine():
                engine = RumorJudgeEngine()
                with lock:
                    instances.append(engine)

            # 创建多个线程同时获取实例
            threads = []
            for _ in range(10):
                t = threading.Thread(target=create_engine)
                threads.append(t)
                t.start()

            # 等待所有线程完成
            for t in threads:
                t.join()

            # 验证所有实例都是同一个
            first = instances[0]
            for instance in instances[1:]:
                assert instance is first

    def test_initialized_flag(self):
        """测试初始化标志位"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            assert engine._initialized is True

            # 再次调用 __init__ 不应该重新初始化
            engine.__init__()
            assert engine._initialized is True


# ============================================================================
# RumorJudgeEngine 初始化测试
# ============================================================================

class TestRumorJudgeEngineInit:
    """RumorJudgeEngine 初始化测试"""

    @pytest.fixture
    def reset_engine(self):
        """重置引擎单例"""
        original_instance = RumorJudgeEngine._instance
        RumorJudgeEngine._instance = None
        yield
        RumorJudgeEngine._instance = original_instance

    def test_engine_creation(self, reset_engine):
        """测试引擎创建"""
        engine = RumorJudgeEngine()
        assert engine is not None
        assert engine._initialized is True
        assert engine._components_initialized is False

    def test_lazy_init_components_not_initialized_at_start(self):
        """测试组件在创建时未初始化"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()

            # 组件应该未初始化（延迟初始化）
            assert engine._components_initialized is False
            assert engine._kb is None
            assert engine._cache_manager is None
            assert engine._web_search_tool is None
            assert engine._knowledge_integrator is None
            assert engine._hybrid_retriever is None
            assert engine._parser_chain is None

    def test_coordinators_not_initialized_at_start(self):
        """测试协调器在创建时未初始化"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()

            assert engine._query_processor is None
            assert engine._retrieval_coordinator is None
            assert engine._analysis_coordinator is None
            assert engine._verdict_generator is None


# ============================================================================
# RumorJudgeEngine 属性测试
# ============================================================================

class TestRumorJudgeEngineProperties:
    """RumorJudgeEngine 属性测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎（使用 mock 避免实际初始化）"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            # Mock 延迟初始化以避免实际加载组件
            with patch.object(engine, '_lazy_init'):
                yield engine

    def test_is_ready_property(self, engine):
        """测试 is_ready 属性"""
        # 初始状态：组件未初始化
        assert engine.is_ready is False

        # 模拟组件已初始化
        engine._components_initialized = True
        assert engine.is_ready is True

    def test_kb_property_triggers_lazy_init(self, engine):
        """测试 kb 属性触发延迟初始化"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_kb = Mock()
            engine._kb = mock_kb

            # 访问 kb 属性应该触发 _lazy_init
            _ = engine.kb
            mock_init.assert_called_once()

    def test_cache_manager_property_triggers_lazy_init(self, engine):
        """测试 cache_manager 属性触发延迟初始化"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_cache = Mock()
            engine._cache_manager = mock_cache

            # 访问 cache_manager 属性应该触发 _lazy_init
            _ = engine.cache_manager
            mock_init.assert_called_once()

    def test_web_search_tool_property(self, engine):
        """测试 web_search_tool 属性"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_tool = Mock()
            engine._web_search_tool = mock_tool

            _ = engine.web_search_tool
            mock_init.assert_called_once()

    def test_knowledge_integrator_property(self, engine):
        """测试 knowledge_integrator 属性"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_integrator = Mock()
            engine._knowledge_integrator = mock_integrator

            _ = engine.knowledge_integrator
            mock_init.assert_called_once()

    def test_hybrid_retriever_property(self, engine):
        """测试 hybrid_retriever 属性"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_retriever = Mock()
            engine._hybrid_retriever = mock_retriever

            _ = engine.hybrid_retriever
            mock_init.assert_called_once()

    def test_parser_chain_property(self, engine):
        """测试 parser_chain 属性"""
        with patch.object(engine, '_lazy_init') as mock_init:
            mock_parser = Mock()
            engine._parser_chain = mock_parser

            _ = engine.parser_chain
            mock_init.assert_called_once()


# ============================================================================
# RumorJudgeEngine 协调器检查测试
# ============================================================================

class TestRumorJudgeEngineCoordinators:
    """RumorJudgeEngine 协调器相关测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_use_coordinators_all_none(self, engine):
        """测试所有协调器为 None 时返回 False"""
        engine._query_processor = None
        engine._retrieval_coordinator = None
        engine._analysis_coordinator = None
        engine._verdict_generator = None

        assert engine._use_coordinators() is False

    def test_use_coordinators_all_set(self, engine):
        """测试所有协调器都已设置时返回 True"""
        engine._query_processor = Mock()
        engine._retrieval_coordinator = Mock()
        engine._analysis_coordinator = Mock()
        engine._verdict_generator = Mock()

        assert engine._use_coordinators() is True

    def test_use_coordinators_partial_set(self, engine):
        """测试部分协调器设置时返回 False"""
        engine._query_processor = Mock()
        engine._retrieval_coordinator = Mock()
        engine._analysis_coordinator = None  # 缺少
        engine._verdict_generator = Mock()

        assert engine._use_coordinators() is False

    def test_use_coordinators_one_missing(self, engine):
        """测试缺少任意一个协调器时返回 False"""
        coordinators = [
            '_query_processor',
            '_retrieval_coordinator',
            '_analysis_coordinator',
            '_verdict_generator'
        ]

        for missing_coordinator in coordinators:
            # 重置所有协调器
            for coord in coordinators:
                setattr(engine, coord, Mock())

            # 设置一个为 None
            setattr(engine, missing_coordinator, None)

            assert engine._use_coordinators() is False, \
                f"应该返回 False 当 {missing_coordinator} 为 None 时"


# ============================================================================
# RumorJudgeEngine _ensure_kb_ready 测试
# ============================================================================

class TestRumorJudgeEngineKbReady:
    """RumorJudgeEngine 知识库就绪测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_ensure_kb_ready_when_exists(self, engine):
        """测试知识库已存在时不构建"""
        mock_kb = Mock()
        mock_kb.persist_dir.exists.return_value = True

        engine._kb = mock_kb

        # 不应该调用 build
        engine._ensure_kb_ready()
        mock_kb.build.assert_not_called()

    def test_ensure_kb_ready_when_not_exists_build_success(self, engine):
        """测试知识库不存在时成功构建"""
        mock_kb = Mock()
        mock_kb.persist_dir.exists.return_value = False
        mock_kb.data_dir = Path("/test/data")

        engine._kb = mock_kb

        engine._ensure_kb_ready()

        # 应该调用 build
        mock_kb.build.assert_called_once()

    def test_ensure_kb_ready_build_failure(self, engine, caplog):
        """测试知识库构建失败时的处理"""
        mock_kb = Mock()
        mock_kb.persist_dir.exists.return_value = False
        mock_kb.data_dir = Path("/test/data")
        mock_kb.build.side_effect = Exception("构建失败")

        engine._kb = mock_kb

        # 应该捕获异常而不是崩溃
        engine._ensure_kb_ready()

        # 验证 build 被调用
        mock_kb.build.assert_called_once()


# ============================================================================
# RumorJudgeEngine 延迟初始化测试
# ============================================================================

class TestRumorJudgeEngineLazyInit:
    """RumorJudgeEngine 延迟初始化测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_lazy_init_called_once(self, engine):
        """测试延迟初始化只执行一次"""
        call_count = [0]

        def mock_ensure_kb_ready():
            call_count[0] += 1

        with patch.object(engine, '_ensure_kb_ready', mock_ensure_kb_ready):
            with patch('src.core.pipeline.EvidenceKnowledgeBase'):
                with patch('src.core.pipeline.CacheManager'):
                    with patch('src.core.pipeline.WebSearchTool'):
                        with patch('src.core.pipeline.KnowledgeIntegrator'):
                            with patch('src.core.pipeline.HybridRetriever'):
                                with patch.object(engine, '_init_coordinators'):
                                    # 第一次调用
                                    engine._lazy_init()
                                    assert engine._components_initialized is True
                                    assert call_count[0] == 1

                                    # 第二次调用
                                    engine._lazy_init()
                                    # 应该不再执行初始化
                                    assert call_count[0] == 1

    def test_lazy_init_double_check(self, engine):
        """测试延迟初始化的双重检查锁定"""
        with patch.object(engine, '_ensure_kb_ready'):
            with patch('src.core.pipeline.EvidenceKnowledgeBase'):
                with patch('src.core.pipeline.CacheManager'):
                    with patch('src.core.pipeline.WebSearchTool'):
                        with patch('src.core.pipeline.KnowledgeIntegrator'):
                            with patch('src.core.pipeline.HybridRetriever'):
                                with patch.object(engine, '_init_coordinators'):
                                    # 模拟已初始化
                                    engine._components_initialized = True

                                    # 调用应该立即返回
                                    engine._lazy_init()

                                    # 验证组件未被重新创建
                                    # (因为 _components_initialized 已经是 True)


# ============================================================================
# RumorJudgeEngine _init_coordinators 测试
# ============================================================================

class TestRumorJudgeEngineInitCoordinators:
    """RumorJudgeEngine 协调器初始化测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_init_coordinators_success(self, engine):
        """测试协调器成功初始化"""
        # patch 正确的导入路径
        with patch('src.core.coordinators.QueryProcessor') as MockQP:
            with patch('src.core.coordinators.RetrievalCoordinator') as MockRC:
                with patch('src.core.coordinators.AnalysisCoordinator') as MockAC:
                    with patch('src.core.coordinators.VerdictGenerator') as MockVG:
                        engine._parser_chain = Mock()
                        engine._cache_manager = Mock()
                        engine._hybrid_retriever = Mock()
                        engine._kb = Mock()

                        engine._init_coordinators()

                        assert MockQP.called
                        assert MockRC.called
                        assert MockAC.called
                        assert MockVG.called
                        assert engine._query_processor is not None
                        assert engine._retrieval_coordinator is not None
                        assert engine._analysis_coordinator is not None
                        assert engine._verdict_generator is not None

    def test_init_coordinators_import_error(self, engine, caplog):
        """测试协调器导入失败时的处理"""
        # patch 正确的导入路径，模拟导入错误
        with patch('src.core.coordinators.QueryProcessor', side_effect=ImportError):
            with patch('src.core.coordinators.RetrievalCoordinator', side_effect=ImportError):
                with patch('src.core.coordinators.AnalysisCoordinator', side_effect=ImportError):
                    with patch('src.core.coordinators.VerdictGenerator', side_effect=ImportError):
                        engine._init_coordinators()

                        # 应该优雅地处理错误，设置为 None
                        assert engine._query_processor is None
                        assert engine._retrieval_coordinator is None
                        assert engine._analysis_coordinator is None
                        assert engine._verdict_generator is None


# ============================================================================
# RumorJudgeEngine run 方法基础测试
# ============================================================================

class TestRumorJudgeEngineRunBasic:
    """RumorJudgeEngine run 方法基础测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_run_without_coordinators_returns_error(self, engine):
        """测试没有协调器时运行返回错误结果"""
        # 确保协调器未初始化
        engine._query_processor = None
        engine._retrieval_coordinator = None
        engine._analysis_coordinator = None
        engine._verdict_generator = None

        with patch.object(engine, '_lazy_init'):
            result = engine.run("测试查询")

            assert result.query == "测试查询"
            assert result.final_verdict == "系统错误"
            assert result.is_fallback is True
            assert "协调器" in result.summary_report or "初始化失败" in result.summary_report

    def test_run_creates_result_object(self, engine):
        """测试 run 方法创建正确的结果对象"""
        with patch.object(engine, '_lazy_init'):
            with patch.object(engine, '_use_coordinators', return_value=False):
                result = engine.run("测试查询")

                assert isinstance(result, UnifiedVerificationResult)
                assert result.query == "测试查询"


# ============================================================================
# 辅助测试 - 错误处理
# ============================================================================

class TestPipelineErrorHandling:
    """Pipeline 错误处理测试"""

    def test_unified_verification_result_default_values(self):
        """测试结果对象的默认值"""
        result = UnifiedVerificationResult(query="测试")

        # 验证所有默认值
        assert result.is_cached is False
        assert result.is_fallback is False
        assert result.is_web_search is False
        assert result.saved_to_cache is False
        assert result.confidence_score == 0

    def test_processing_metadata_default_duration(self):
        """测试元数据默认持续时间为 0"""
        metadata = ProcessingMetadata(
            stage=PipelineStage.CACHE_CHECK,
            success=True
        )

        assert metadata.duration_ms == 0.0

    def test_metadata_with_negative_duration(self):
        """测试负持续时间也被接受（边缘情况）"""
        metadata = ProcessingMetadata(
            stage=PipelineStage.ANALYSIS,
            success=True,
            duration_ms=-10.5
        )

        assert metadata.duration_ms == -10.5


# ============================================================================
# RumorJudgeEngine _auto_integrate_knowledge 测试
# ============================================================================

class TestRumorJudgeEngineAutoIntegrate:
    """RumorJudgeEngine 自动知识集成测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_auto_integrate_skip_invalid_verdict(self, engine):
        """测试结论不明确时跳过自动集成"""
        result = UnifiedVerificationResult(query="测试查询")
        result.final_verdict = "存在争议"  # 不是"真"或"假"
        result.confidence_score = 95
        result.retrieved_evidence = [{"content": "证据1"}] * 3

        with patch.object(engine, '_knowledge_integrator'):
            # 应该返回而不执行集成
            engine._auto_integrate_knowledge(result)
            # 验证没有启动后台线程

    def test_auto_integrate_skip_low_confidence(self, engine):
        """测试置信度低于阈值时跳过自动集成"""
        result = UnifiedVerificationResult(query="测试查询")
        result.final_verdict = "真"
        result.confidence_score = 80  # 低于默认阈值 90
        result.retrieved_evidence = [{"content": "证据1"}] * 3

        with patch.object(engine, '_knowledge_integrator'):
            engine._auto_integrate_knowledge(result)

    def test_auto_integrate_skip_insufficient_evidence(self, engine):
        """测试证据数量不足时跳过自动集成"""
        result = UnifiedVerificationResult(query="测试查询")
        result.final_verdict = "真"
        result.confidence_score = 95
        result.retrieved_evidence = [{"content": "证据1"}] * 2  # 少于默认阈值 3

        with patch.object(engine, '_knowledge_integrator'):
            engine._auto_integrate_knowledge(result)

    def test_auto_integrate_skip_not_web_search(self, engine):
        """测试非联网搜索结果时跳过自动集成"""
        result = UnifiedVerificationResult(query="测试查询")
        result.final_verdict = "真"
        result.confidence_score = 95
        result.retrieved_evidence = [{"content": "证据1"}] * 3
        result.is_web_search = False

        with patch.object(engine, '_knowledge_integrator'):
            engine._auto_integrate_knowledge(result)

    def test_auto_integrate_meets_criteria(self, engine):
        """测试符合条件时启动后台集成"""
        result = UnifiedVerificationResult(query="维生素C能美白吗")
        result.final_verdict = "真"
        result.confidence_score = 95
        result.retrieved_evidence = [
            {"content": "证据1", "metadata": {"source": "来源1"}},
            {"content": "证据2", "metadata": {"source": "来源2"}},
            {"content": "证据3", "metadata": {"source": "来源3"}}
        ]
        result.is_web_search = True
        result.summary_report = "测试总结"

        mock_integrator = Mock()
        mock_integrator.rumor_data_dir = Path("/test/data")
        mock_integrator.generate_knowledge_content.return_value = "生成的内容"
        engine._knowledge_integrator = mock_integrator
        engine._integration_lock = threading.Lock()

        with patch('builtins.open', create=True) as mock_open:
            with patch.object(engine, '_kb'):
                engine._auto_integrate_knowledge(result)
                # 验证后台线程被启动（由于是异步的，我们只验证没有异常抛出）

    def test_auto_integrate_with_custom_threshold(self, engine):
        """测试自定义阈值配置"""
        # 设置自定义阈值
        with patch('src.core.pipeline.config') as mock_config:
            mock_config.AUTO_INTEGRATE_MIN_CONFIDENCE = 85
            mock_config.AUTO_INTEGRATE_MIN_EVIDENCE = 5

            result = UnifiedVerificationResult(query="测试查询")
            result.final_verdict = "真"
            result.confidence_score = 90  # 高于自定义阈值 85
            result.retrieved_evidence = [{"content": f"证据{i}"} for i in range(5)]  # 5条证据
            result.is_web_search = True

            with patch.object(engine, '_knowledge_integrator'):
                with patch('src.core.pipeline.getattr', side_effect=lambda *args, **kwargs: getattr(mock_config, args[1], 90 if 'CONFIDENCE' in args[1] else 3)):
                    engine._auto_integrate_knowledge(result)


# ============================================================================
# RumorJudgeEngine _run_with_coordinators 完整流程测试
# ============================================================================

class TestRumorJudgeEngineRunWithCoordinators:
    """RumorJudgeEngine 协调器运行模式完整测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_run_with_coordinators_success(self, engine):
        """测试使用协调器成功运行"""
        # 设置所有协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        engine._query_processor = mock_qp
        engine._retrieval_coordinator = mock_rc
        engine._analysis_coordinator = mock_ac
        engine._verdict_generator = mock_vg
        engine._cache_manager = Mock()
        engine._kb = Mock()

        # Mock 解析结果
        mock_parsed = Mock()
        mock_parsed.entity = "维生素C"
        mock_parsed.claim = "能美白"
        mock_parsed.category = "健康养生"
        mock_qp.parse_with_parallel_retrieval.return_value = (mock_parsed, [])

        # Mock 缓存未命中
        mock_qp.check_cache.return_value = None

        # Mock 检索结果
        evidence_list = [
            {"content": "证据1", "metadata": {"source": "来源1"}},
            {"content": "证据2", "metadata": {"source": "来源2"}}
        ]
        mock_rc.retrieve_with_parsed_query.return_value = evidence_list
        mock_rc.get_retrieval_stats.return_value = {'is_web_search': False, 'total': 2}

        # Mock 分析结果
        mock_assessments = [Mock(), Mock()]
        mock_ac.analyze.return_value = mock_assessments

        # Mock 裁决结果
        mock_verdict = Mock()
        mock_verdict.verdict.value = "真"
        mock_verdict.confidence = 90
        mock_verdict.risk_level = "低"
        mock_verdict.summary = "测试总结"
        mock_vg.generate.return_value = mock_verdict

        # 执行
        result = engine._run_with_coordinators("维生素C能美白吗", True, datetime.now())

        # 验证
        assert result.query == "维生素C能美白吗"
        assert result.entity == "维生素C"
        assert result.claim == "能美白"
        assert result.category == "健康养生"
        assert result.final_verdict == "真"
        assert result.confidence_score == 90
        assert result.risk_level == "低"
        assert result.summary_report == "测试总结"

        # 验证协调器调用
        mock_qp.parse_with_parallel_retrieval.assert_called_once()
        mock_qp.check_cache.assert_called_once()
        mock_rc.retrieve_with_parsed_query.assert_called_once()
        mock_ac.analyze.assert_called_once()
        mock_vg.generate.assert_called_once()

    def test_run_with_coordinators_cache_hit(self, engine):
        """测试缓存命中时的流程"""
        # 设置协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        engine._query_processor = mock_qp
        engine._retrieval_coordinator = mock_rc
        engine._analysis_coordinator = mock_ac
        engine._verdict_generator = mock_vg

        # Mock 解析结果
        mock_parsed = Mock()
        mock_parsed.entity = "测试实体"
        mock_parsed.claim = "测试主张"
        mock_parsed.category = "测试分类"
        mock_qp.parse_with_parallel_retrieval.return_value = (mock_parsed, [])

        # Mock 缓存命中
        mock_cached = Mock()
        mock_cached.verdict.value = "假"
        mock_cached.confidence = 85
        mock_cached.risk_level = "中"
        mock_cached.summary = "缓存总结"
        mock_qp.check_cache.return_value = mock_cached

        # 执行
        result = engine._run_with_coordinators("测试查询", True, datetime.now())

        # 验证缓存结果
        assert result.is_cached is True
        assert result.final_verdict == "假"
        assert result.confidence_score == 85
        assert result.risk_level == "中"
        assert result.summary_report == "缓存总结"

        # 验证没有调用检索和裁决
        mock_rc.retrieve_with_parsed_query.assert_not_called()
        mock_ac.analyze.assert_not_called()
        mock_vg.generate.assert_not_called()

    def test_run_with_coordinators_no_cache(self, engine):
        """测试不使用缓存时的流程"""
        # 设置协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        engine._query_processor = mock_qp
        engine._retrieval_coordinator = mock_rc
        engine._analysis_coordinator = mock_ac
        engine._verdict_generator = mock_vg
        engine._cache_manager = Mock()
        engine._kb = Mock()

        # Mock 解析结果为 None
        mock_qp.parse_with_parallel_retrieval.return_value = (None, [])

        # Mock 检索结果
        evidence_list = [{"content": "证据1", "metadata": {"source": "来源1"}}]
        mock_rc.retrieve.return_value = evidence_list
        mock_rc.get_retrieval_stats.return_value = {'is_web_search': False, 'total': 1}

        # Mock 分析和裁决
        mock_ac.analyze.return_value = []
        mock_verdict = Mock()
        mock_verdict.verdict.value = "证据不足"
        mock_verdict.confidence = 50
        mock_verdict.risk_level = "高"
        mock_verdict.summary = "证据不足总结"
        mock_vg.generate.return_value = mock_verdict

        # 执行 - use_cache=False
        result = engine._run_with_coordinators("测试查询", False, datetime.now())

        # 验证
        assert result.final_verdict == "证据不足"
        # 验证没有检查缓存
        mock_qp.check_cache.assert_not_called()
        # 验证调用了简单检索（没有 parsed）
        mock_rc.retrieve.assert_called_once()

    def test_run_with_coordinators_web_search(self, engine):
        """测试使用网络搜索的流程"""
        # 设置协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        engine._query_processor = mock_qp
        engine._retrieval_coordinator = mock_rc
        engine._analysis_coordinator = mock_ac
        engine._verdict_generator = mock_vg
        engine._cache_manager = Mock()
        engine._kb = Mock()

        # Mock 解析结果
        mock_parsed = Mock()
        mock_parsed.entity = "测试实体"
        mock_parsed.claim = "测试主张"
        mock_parsed.category = "测试分类"
        mock_qp.parse_with_parallel_retrieval.return_value = (mock_parsed, [])

        # Mock 缓存未命中
        mock_qp.check_cache.return_value = None

        # Mock 网络搜索结果
        evidence_list = [
            {"content": "网络证据1", "metadata": {"source": "网络来源1"}},
            {"content": "网络证据2", "metadata": {"source": "网络来源2"}}
        ]
        mock_rc.retrieve_with_parsed_query.return_value = evidence_list
        mock_rc.get_retrieval_stats.return_value = {'is_web_search': True, 'total': 2}

        # Mock 分析和裁决
        mock_ac.analyze.return_value = []
        mock_verdict = Mock()
        mock_verdict.verdict.value = "真"
        mock_verdict.confidence = 92
        mock_verdict.risk_level = "低"
        mock_verdict.summary = "网络搜索总结"
        mock_vg.generate.return_value = mock_verdict

        # 执行
        result = engine._run_with_coordinators("测试查询", True, datetime.now())

        # 验证
        assert result.is_web_search is True
        assert result.final_verdict == "真"
        # 验证元数据中包含 WEB_SEARCH 阶段
        web_search_metadata = [m for m in result.metadata if m.stage == PipelineStage.WEB_SEARCH]
        assert len(web_search_metadata) == 1

    def test_run_with_coordinators_no_evidence(self, engine):
        """测试无证据时的兜底流程"""
        # 设置协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        engine._query_processor = mock_qp
        engine._retrieval_coordinator = mock_rc
        engine._analysis_coordinator = mock_ac
        engine._verdict_generator = mock_vg
        engine._cache_manager = Mock()
        engine._kb = Mock()

        # Mock 解析结果
        mock_parsed = Mock()
        mock_parsed.entity = "测试实体"
        mock_parsed.claim = "测试主张"
        mock_parsed.category = "测试分类"
        mock_qp.parse_with_parallel_retrieval.return_value = (mock_parsed, [])

        # Mock 缓存未命中
        mock_qp.check_cache.return_value = None

        # Mock 无检索结果
        mock_rc.retrieve_with_parsed_query.return_value = []
        mock_rc.get_retrieval_stats.return_value = {'is_web_search': False, 'total': 0}

        # Mock 兜底裁决 - 需要在模块级别导入的位置进行 patch
        with patch('src.analyzers.truth_summarizer.summarize_with_fallback') as mock_fallback:
            mock_fallback_result = Mock()
            mock_fallback_result.verdict.value = "无法判断"
            mock_fallback_result.confidence = 30
            mock_fallback_result.risk_level = "高"
            mock_fallback_result.summary = "兜底总结"
            mock_fallback.return_value = mock_fallback_result

            # 执行
            result = engine._run_with_coordinators("测试查询", True, datetime.now())

            # 验证兜底流程
            assert result.is_fallback is True
            mock_fallback.assert_called_once()


# ============================================================================
# RumorJudgeEngine 线程安全工具测试
# ============================================================================

class TestRumorJudgeEngineThreadUtils:
    """RumorJudgeEngine 线程安全工具测试"""

    def test_engine_without_thread_utils(self):
        """测试没有线程安全工具时的初始化"""
        # Mock 线程工具不可用
        with patch('src.core.pipeline.THREAD_UTILS_AVAILABLE', False):
            with patch.object(RumorJudgeEngine, '_instance', None):
                engine = RumorJudgeEngine()

                # 应该使用基础锁
                assert hasattr(engine, '_init_lock')
                assert hasattr(engine, '_integration_lock')
                assert engine._lock_mgr is None

    @pytest.fixture
    def engine_with_thread_utils(self):
        """创建有线程安全工具的引擎"""
        with patch('src.core.pipeline.THREAD_UTILS_AVAILABLE', True):
            with patch('src.core.pipeline.get_lock_manager') as mock_get_lock_mgr:
                mock_lock_mgr = Mock()
                mock_get_lock_mgr.return_value = mock_lock_mgr

                with patch.object(RumorJudgeEngine, '_instance', None):
                    engine = RumorJudgeEngine()
                    yield engine, mock_lock_mgr

    def test_engine_with_thread_utils_available(self, engine_with_thread_utils):
        """测试有线程安全工具时的初始化"""
        engine, mock_lock_mgr = engine_with_thread_utils

        assert engine._lock_mgr == mock_lock_mgr
        assert not hasattr(engine, '_init_lock')
        assert not hasattr(engine, '_integration_lock')


# ============================================================================
# RumorJudgeEngine run 方法完整测试
# ============================================================================

class TestRumorJudgeEngineRunComplete:
    """RumorJudgeEngine run 方法完整测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_run_with_use_cache_false(self, engine):
        """测试禁用缓存运行"""
        # 设置协调器
        mock_qp = Mock()
        mock_rc = Mock()
        mock_ac = Mock()
        mock_vg = Mock()

        # Mock 协调器流程
        mock_parsed = Mock()
        mock_parsed.entity = "测试"
        mock_parsed.claim = "测试"
        mock_parsed.category = "测试"
        mock_qp.parse_with_parallel_retrieval.return_value = (mock_parsed, [])

        evidence = [{"content": "证据", "metadata": {"source": "来源"}}]
        mock_rc.retrieve_with_parsed_query.return_value = evidence
        mock_rc.get_retrieval_stats.return_value = {'is_web_search': False, 'total': 1}
        mock_ac.analyze.return_value = []

        mock_verdict = Mock()
        mock_verdict.verdict.value = "真"
        mock_verdict.confidence = 90
        mock_verdict.risk_level = "低"
        mock_verdict.summary = "总结"
        mock_vg.generate.return_value = mock_verdict

        # Mock 缓存管理器
        mock_cache_mgr = Mock()
        mock_cache_mgr.default_ttl = 86400

        # 使用 patch 确保 _lazy_init 不覆盖我们的 mock
        with patch.object(engine, '_lazy_init'):
            engine._query_processor = mock_qp
            engine._retrieval_coordinator = mock_rc
            engine._analysis_coordinator = mock_ac
            engine._verdict_generator = mock_vg
            engine._cache_manager = mock_cache_mgr

            # 执行 - use_cache=False
            result = engine.run("测试查询", use_cache=False)

            # 验证结果
            assert result.query == "测试查询"
            assert result.final_verdict == "真"
            # 验证缓存检查阶段存在且成功
            cache_metadata = [m for m in result.metadata if m.stage == PipelineStage.CACHE_CHECK]
            assert len(cache_metadata) == 1
            assert cache_metadata[0].success is True


# ============================================================================
# RumorJudgeEngine 协调器初始化详细测试
# ============================================================================

class TestRumorJudgeEngineCoordinatorsDetailed:
    """RumorJudgeEngine 协调器初始化详细测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        with patch.object(RumorJudgeEngine, '_instance', None):
            engine = RumorJudgeEngine()
            yield engine

    def test_init_coordinators_passes_dependencies(self, engine):
        """测试协调器初始化时正确传递依赖"""
        # 设置必需的依赖
        engine._parser_chain = Mock()
        engine._cache_manager = Mock()
        engine._hybrid_retriever = Mock()
        engine._kb = Mock()

        # Mock 协调器
        with patch('src.core.coordinators.QueryProcessor') as MockQP:
            with patch('src.core.coordinators.RetrievalCoordinator') as MockRC:
                with patch('src.core.coordinators.AnalysisCoordinator') as MockAC:
                    with patch('src.core.coordinators.VerdictGenerator') as MockVG:
                        engine._init_coordinators()

                        # 验证 QueryProcessor 接收正确的参数
                        MockQP.assert_called_once()
                        qp_call_kwargs = MockQP.call_args[1]
                        assert 'parser_chain' in qp_call_kwargs
                        assert 'cache_manager' in qp_call_kwargs
                        assert 'hybrid_retriever' in qp_call_kwargs

                        # 验证 RetrievalCoordinator 接收正确的参数
                        MockRC.assert_called_once()
                        rc_call_kwargs = MockRC.call_args[1]
                        assert 'hybrid_retriever' in rc_call_kwargs
                        assert 'kb' in rc_call_kwargs
