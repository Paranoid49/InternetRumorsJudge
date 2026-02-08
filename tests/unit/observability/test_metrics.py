"""
测试指标采集器
"""
import pytest
import time
from unittest.mock import patch, Mock
from collections import defaultdict

from src.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
    StageTimer,
    observe_stage,
    METRICS_CONTEXT,
    PROMETHEUS_AVAILABLE
)


class TestMetricsCollector:
    """测试指标采集器"""

    def test_init_with_prometheus_disabled(self):
        """测试 Prometheus 不可用时的初始化"""
        with patch('src.observability.metrics.PROMETHEUS_AVAILABLE', False):
            collector = MetricsCollector(enabled=True)
            assert collector.enabled is False
            assert isinstance(collector._stats, defaultdict)

    def test_init_with_prometheus_available(self):
        """测试 Prometheus 可用时的初始化"""
        if PROMETHEUS_AVAILABLE:
            collector = MetricsCollector(enabled=True)
            assert collector.enabled is True
            assert hasattr(collector, 'request_counter')
            assert hasattr(collector, 'request_duration')
            assert hasattr(collector, 'cache_hits')
            assert hasattr(collector, 'api_calls')
            assert hasattr(collector, 'errors')
            assert hasattr(collector, 'active_queries')

    def test_init_disabled(self):
        """测试禁用采集器"""
        collector = MetricsCollector(enabled=False)
        assert collector.enabled is False

    def test_record_request_enabled(self):
        """测试记录请求（启用状态）"""
        collector = MetricsCollector(enabled=False)  # 禁用 Prometheus

        # 记录请求
        collector.record_request("/test", "success")

        # 验证内存统计更新
        stats = collector.get_stats()
        assert "request_/test_success" in stats
        assert stats["request_/test_success"]["count"] == 1
        assert stats["request_/test_success"]["last_update"] is not None

    def test_record_request_multiple(self):
        """测试记录多个请求"""
        collector = MetricsCollector(enabled=False)

        collector.record_request("/api1", "success")
        collector.record_request("/api1", "success")
        collector.record_request("/api1", "error")

        stats = collector.get_stats()
        assert stats["request_/api1_success"]["count"] == 2
        assert stats["request_/api1_error"]["count"] == 1

    def test_record_duration(self):
        """测试记录耗时"""
        collector = MetricsCollector(enabled=False)

        collector.record_duration("parsing", 0.5)
        collector.record_duration("parsing", 1.5)

        stats = collector.get_stats()
        assert "duration_parsing" in stats
        assert stats["duration_parsing"]["count"] == 2
        assert stats["duration_parsing"]["total_duration"] == 2.0

    def test_record_duration_calculates_average(self):
        """测试计算平均耗时"""
        collector = MetricsCollector(enabled=False)

        collector.record_duration("retrieval", 1.0)
        collector.record_duration("retrieval", 2.0)
        collector.record_duration("retrieval", 3.0)

        stats = collector.get_stats()
        assert "avg_duration_retrieval" in stats
        assert stats["avg_duration_retrieval"] == 2.0

    def test_record_cache_hit(self):
        """测试记录缓存命中"""
        collector = MetricsCollector(enabled=False)

        collector.record_cache_hit("exact")
        collector.record_cache_hit("semantic")
        collector.record_cache_hit("exact")

        stats = collector.get_stats()
        assert stats["cache_hit_exact"]["count"] == 2
        assert stats["cache_hit_semantic"]["count"] == 1

    def test_record_api_call(self):
        """测试记录 API 调用"""
        collector = MetricsCollector(enabled=False)

        collector.record_api_call("dashscope", "qwen-plus")
        collector.record_api_call("dashscope", "qwen-max")
        collector.record_api_call("tavily", "search")

        stats = collector.get_stats()
        assert stats["api_call_dashscope_qwen-plus"]["count"] == 1
        assert stats["api_call_dashscope_qwen-max"]["count"] == 1
        assert stats["api_call_tavily_search"]["count"] == 1

    def test_record_error(self):
        """测试记录错误"""
        collector = MetricsCollector(enabled=False)

        collector.record_error("parsing", "ValueError")
        collector.record_error("retrieval", "ConnectionError")
        collector.record_error("parsing", "TypeError")

        stats = collector.get_stats()
        assert stats["error_parsing_ValueError"]["count"] == 1
        assert stats["error_parsing_ValueError"]["errors"] == 1
        assert stats["error_parsing_TypeError"]["errors"] == 1
        assert stats["error_retrieval_ConnectionError"]["count"] == 1

    def test_inc_and_dec_active_queries(self):
        """测试增减活跃查询数"""
        collector = MetricsCollector(enabled=False)

        # 禁用 Prometheus 时不应抛出异常
        collector.inc_active_queries()
        collector.inc_active_queries()
        collector.dec_active_queries()

    def test_get_stats(self):
        """测试获取统计数据"""
        collector = MetricsCollector(enabled=False)

        collector.record_request("/test", "success")
        collector.record_duration("parsing", 1.0)
        collector.record_cache_hit("exact")

        stats = collector.get_stats()
        assert isinstance(stats, dict)
        assert "request_/test_success" in stats
        assert "duration_parsing" in stats
        assert "cache_hit_exact" in stats

    def test_export_metrics_without_prometheus(self):
        """测试没有 Prometheus 时导出指标"""
        collector = MetricsCollector(enabled=False)

        metrics = collector.export_metrics()
        assert metrics is None

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
    def test_export_metrics_with_prometheus(self):
        """测试有 Prometheus 时导出指标"""
        # 清除可能存在的全局指标
        from prometheus_client import REGISTRY
        collectors_to_keep = set()
        for collector in REGISTRY._collector_to_names.keys():
            collectors_to_keep.add(collector)
        for collector in collectors_to_keep:
            REGISTRY.unregister(collector)

        collector = MetricsCollector(enabled=True)

        metrics = collector.export_metrics()
        assert metrics is not None
        assert isinstance(metrics, bytes)

    def test_reset_stats(self):
        """测试重置统计数据"""
        collector = MetricsCollector(enabled=False)

        collector.record_request("/test", "success")
        collector.record_duration("parsing", 1.0)

        assert len(collector.get_stats()) > 0

        collector.reset_stats()
        stats = collector.get_stats()
        assert len(stats) == 0


class TestGetMetricsCollector:
    """测试获取全局指标采集器"""

    def test_get_metrics_collector_singleton(self):
        """测试单例模式"""
        # 清除全局实例和注册表
        import src.observability.metrics as metrics_module
        metrics_module._global_collector = None

        # 清除 Prometheus 注册表中的指标
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import REGISTRY
            collectors_to_keep = set()
            for collector in list(REGISTRY._collector_to_names.keys()):
                collectors_to_keep.add(collector)
            for collector in collectors_to_keep:
                try:
                    REGISTRY.unregister(collector)
                except Exception:
                    pass

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2

        # 清理
        metrics_module._global_collector = None

    def test_get_metrics_collector_initialization(self):
        """测试初始化"""
        # 清除全局实例和注册表
        import src.observability.metrics as metrics_module
        metrics_module._global_collector = None

        # 清除 Prometheus 注册表中的指标
        if PROMETHEUS_AVAILABLE:
            from prometheus_client import REGISTRY
            collectors_to_keep = set()
            for collector in list(REGISTRY._collector_to_names.keys()):
                collectors_to_keep.add(collector)
            for collector in collectors_to_keep:
                try:
                    REGISTRY.unregister(collector)
                except Exception:
                    pass

        collector = get_metrics_collector()
        assert isinstance(collector, MetricsCollector)

        # 清理
        metrics_module._global_collector = None


class TestStageTimer:
    """测试阶段计时器"""

    def test_stage_timer_records_duration(self):
        """测试记录阶段耗时"""
        collector = MetricsCollector(enabled=False)

        with StageTimer("test_stage", collector):
            time.sleep(0.01)

        stats = collector.get_stats()
        assert "duration_test_stage" in stats
        assert stats["duration_test_stage"]["count"] == 1
        assert stats["duration_test_stage"]["total_duration"] >= 0.01

    def test_stage_timer_with_default_collector(self):
        """测试使用默认采集器"""
        import src.observability.metrics as metrics_module

        # 设置全局采集器
        collector = MetricsCollector(enabled=False)
        metrics_module._global_collector = collector

        with StageTimer("default_test"):
            time.sleep(0.01)

        stats = collector.get_stats()
        assert "duration_default_test" in stats

        # 清理
        metrics_module._global_collector = None

    def test_stage_timer_with_exception(self):
        """测试操作抛出异常时记录错误"""
        collector = MetricsCollector(enabled=False)

        with pytest.raises(ValueError):
            with StageTimer("failing_stage", collector):
                raise ValueError("测试错误")

        stats = collector.get_stats()
        assert "duration_failing_stage" in stats
        assert "error_failing_stage_ValueError" in stats
        assert stats["error_failing_stage_ValueError"]["count"] == 1

    def test_stage_timer_no_exception(self):
        """测试正常操作不记录错误"""
        collector = MetricsCollector(enabled=False)

        with StageTimer("normal_stage", collector):
            pass

        stats = collector.get_stats()
        assert "duration_normal_stage" in stats
        # 不应该有错误记录
        error_keys = [k for k in stats.keys() if k.startswith("error_")]
        assert len(error_keys) == 0


class TestObserveStage:
    """测试观察阶段装饰器"""

    def test_observe_stage_decorator(self):
        """测试装饰器正常执行"""
        import src.observability.metrics as metrics_module

        collector = MetricsCollector(enabled=False)
        metrics_module._global_collector = collector

        @observe_stage("decorated_test")
        def test_function(x, y):
            return x + y

        result = test_function(2, 3)
        assert result == 5

        stats = collector.get_stats()
        assert "duration_decorated_test" in stats

        # 清理
        metrics_module._global_collector = None

    def test_observe_stage_with_exception(self):
        """测试装饰器捕获异常"""
        import src.observability.metrics as metrics_module

        collector = MetricsCollector(enabled=False)
        metrics_module._global_collector = collector

        @observe_stage("failing_decorator_test")
        def failing_function():
            raise ValueError("装饰器测试错误")

        with pytest.raises(ValueError):
            failing_function()

        stats = collector.get_stats()
        assert "duration_failing_decorator_test" in stats
        assert "error_failing_decorator_test_ValueError" in stats

        # 清理
        metrics_module._global_collector = None

    def test_observe_stage_with_arguments(self):
        """测试装饰器传递参数"""
        import src.observability.metrics as metrics_module

        collector = MetricsCollector(enabled=False)
        metrics_module._global_collector = collector

        @observe_stage("args_test")
        def function_with_args(a, b, c=10):
            return a + b + c

        result = function_with_args(1, 2, c=3)
        assert result == 6

        stats = collector.get_stats()
        assert "duration_args_test" in stats

        # 清理
        metrics_module._global_collector = None


class TestMetricsContext:
    """测试指标上下文"""

    def test_metrics_context_var(self):
        """测试指标上下文变量"""
        from src.observability.metrics import METRICS_CONTEXT

        # 默认应该是空字典
        assert METRICS_CONTEXT.get() == {}

    def test_metrics_context_with_custom_value(self):
        """测试设置自定义上下文"""
        test_context = {"request_id": "123"}
        METRICS_CONTEXT.set(test_context)

        assert METRICS_CONTEXT.get() == test_context

        # 清理
        METRICS_CONTEXT.set({})
