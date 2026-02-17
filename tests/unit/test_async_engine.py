"""
测试异步引擎和协调器

验证异步组件的基本功能
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock


class TestAsyncAnalysisCoordinator:
    """测试异步分析协调器"""

    def test_import(self):
        """测试模块导入"""
        from src.core.coordinators.async_analysis_coordinator import AsyncAnalysisCoordinator
        assert AsyncAnalysisCoordinator is not None

    def test_init(self):
        """测试初始化"""
        from src.core.coordinators.async_analysis_coordinator import AsyncAnalysisCoordinator

        coordinator = AsyncAnalysisCoordinator(
            max_concurrency=5,
            enable_prefilter=True,
        )

        assert coordinator.max_concurrency == 5
        assert coordinator.enable_prefilter == True

    def test_stats(self):
        """测试统计信息"""
        from src.core.coordinators.async_analysis_coordinator import AsyncAnalysisCoordinator

        coordinator = AsyncAnalysisCoordinator()
        stats = coordinator.get_stats()

        assert "total_analyzed" in stats
        assert "successful" in stats
        assert "failed" in stats

    @pytest.mark.asyncio
    async def test_analyze_empty_list(self):
        """测试空证据列表"""
        from src.core.coordinators.async_analysis_coordinator import AsyncAnalysisCoordinator

        coordinator = AsyncAnalysisCoordinator()
        result = await coordinator.analyze_async("测试主张", [])

        assert result == []


class TestAsyncVerdictGenerator:
    """测试异步裁决生成器"""

    def test_import(self):
        """测试模块导入"""
        from src.core.coordinators.async_verdict_generator import AsyncVerdictGenerator
        assert AsyncVerdictGenerator is not None

    def test_init(self):
        """测试初始化"""
        from src.core.coordinators.async_verdict_generator import AsyncVerdictGenerator

        generator = AsyncVerdictGenerator(
            max_concurrency=3,
            max_retries=2,
        )

        assert generator.max_concurrency == 3
        assert generator.max_retries == 2

    def test_stats(self):
        """测试统计信息"""
        from src.core.coordinators.async_verdict_generator import AsyncVerdictGenerator

        generator = AsyncVerdictGenerator()
        stats = generator.get_stats()

        assert "total_generated" in stats
        assert "successful" in stats
        assert "fallback_used" in stats

    @pytest.mark.asyncio
    async def test_generate_no_assessments(self):
        """测试无评估时的生成"""
        from src.core.coordinators.async_verdict_generator import AsyncVerdictGenerator

        generator = AsyncVerdictGenerator()
        # 无评估时会使用兜底机制，可能返回 None
        result = await generator.generate_async(
            query="测试查询",
            entity="测试实体",
            claim="测试主张",
            evidence_list=[],
            assessments=[],
        )
        # 结果可能是 None 或 FinalVerdict
        # 这里只验证不会抛出异常


class TestAsyncRumorJudgeEngine:
    """测试异步引擎"""

    def test_import(self):
        """测试模块导入"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine
        assert AsyncRumorJudgeEngine is not None

    def test_singleton(self):
        """测试单例模式"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine1 = AsyncRumorJudgeEngine()
        engine2 = AsyncRumorJudgeEngine()

        assert engine1 is engine2

    def test_stats(self):
        """测试统计信息"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine = AsyncRumorJudgeEngine()
        stats = engine.get_stats()

        assert "total_queries" in stats
        assert "cache_hits" in stats
        assert "web_searches" in stats
        assert "successful" in stats
        assert "failed" in stats

    def test_sync_interface_exists(self):
        """测试同步接口存在"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine = AsyncRumorJudgeEngine()
        assert hasattr(engine, 'run')
        assert callable(engine.run)

    def test_async_interface_exists(self):
        """测试异步接口存在"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine = AsyncRumorJudgeEngine()
        assert hasattr(engine, 'run_async')
        # 检查是否是协程函数
        import asyncio
        assert asyncio.iscoroutinefunction(engine.run_async)

    def test_is_ready_property(self):
        """测试就绪状态属性"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine = AsyncRumorJudgeEngine()
        assert hasattr(engine, 'is_ready')
        # 初始化前应该是 False
        assert engine.is_ready == False

    def test_reset_stats(self):
        """测试重置统计"""
        from src.core.async_pipeline import AsyncRumorJudgeEngine

        engine = AsyncRumorJudgeEngine()
        engine.reset_stats()
        stats = engine.get_stats()

        assert stats["total_queries"] == 0
        assert stats["cache_hits"] == 0


class TestAsyncConvenienceFunctions:
    """测试便捷函数"""

    def test_async_verify_exists(self):
        """测试异步便捷函数存在"""
        from src.core.async_pipeline import async_verify
        import asyncio
        assert asyncio.iscoroutinefunction(async_verify)

    def test_sync_verify_exists(self):
        """测试同步便捷函数存在"""
        from src.core.async_pipeline import verify
        assert callable(verify)


class TestAsyncQueryProcessor:
    """测试异步查询处理器"""

    def test_import(self):
        """测试模块导入"""
        from src.core.coordinators.async_coordinator import AsyncQueryProcessor
        assert AsyncQueryProcessor is not None


class TestAsyncRetrievalCoordinator:
    """测试异步检索协调器"""

    def test_import(self):
        """测试模块导入"""
        from src.core.coordinators.async_coordinator import AsyncRetrievalCoordinator
        assert AsyncRetrievalCoordinator is not None


class TestModuleIntegration:
    """测试模块集成"""

    def test_all_async_modules_importable(self):
        """测试所有异步模块可导入"""
        modules = [
            "src.core.async_pipeline",
            "src.core.coordinators.async_coordinator",
            "src.core.coordinators.async_analysis_coordinator",
            "src.core.coordinators.async_verdict_generator",
            "src.retrievers.async_web_search_tool",
            "src.utils.async_llm_utils",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"无法导入模块 {module}: {e}")

    def test_coordinator_exports(self):
        """测试协调器导出"""
        from src.core.coordinators.async_coordinator import (
            AsyncQueryProcessor,
            AsyncRetrievalCoordinator,
            AsyncAnalysisCoordinator,
        )

        assert AsyncQueryProcessor is not None
        assert AsyncRetrievalCoordinator is not None
        assert AsyncAnalysisCoordinator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
