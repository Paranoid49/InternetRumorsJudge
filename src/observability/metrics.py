"""
指标采集器

采集关键性能指标和业务指标
- 各阶段耗时
- 缓存命中率
- API 调用次数和成本
- 错误率
"""
import time
from collections import defaultdict
from contextvars import ContextVar
from typing import Dict, List, Optional
from datetime import datetime

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = None


# 请求上下文变量
METRICS_CONTEXT: ContextVar[Dict] = ContextVar('metrics_context', default={})


class MetricsCollector:
    """
    指标采集器

    采集系统关键指标，支持 Prometheus 格式导出
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and PROMETHEUS_AVAILABLE

        if self.enabled:
            # 定义 Prometheus 指标
            self._setup_prometheus_metrics()

        # 内存中的统计数据（用于非 Prometheus 环境）
        self._stats = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0.0,
            "errors": 0,
            "last_update": None
        })

    def _setup_prometheus_metrics(self):
        """设置 Prometheus 指标"""

        # 请求计数器
        self.request_counter = Counter(
            'rumorjudge_requests_total',
            'Total number of requests',
            ['endpoint', 'status']
        )

        # 请求耗时直方图
        self.request_duration = Histogram(
            'rumorjudge_request_duration_seconds',
            'Request duration in seconds',
            ['stage']  # stage: cache_check, parsing, retrieval, analysis, verdict
        )

        # 缓存命中率
        self.cache_hits = Counter(
            'rumorjudge_cache_hits_total',
            'Total cache hits',
            ['cache_type']  # cache_type: exact, semantic, miss
        )

        # API 调用次数
        self.api_calls = Counter(
            'rumorjudge_api_calls_total',
            'Total API calls',
            ['provider', 'model']  # provider: dashscope, tavily
        )

        # 错误计数
        self.errors = Counter(
            'rumorjudge_errors_total',
            'Total errors',
            ['component', 'error_type']
        )

        # 活跃查询数（Gauge）
        self.active_queries = Gauge(
            'rumorjudge_active_queries',
            'Number of active queries'
        )

    def record_request(self, endpoint: str, status: str = "success"):
        """记录请求"""
        if self.enabled:
            self.request_counter.labels(endpoint=endpoint, status=status).inc()

        # 更新内存统计
        self._stats[f"request_{endpoint}_{status}"]["count"] += 1
        self._stats[f"request_{endpoint}_{status}"]["last_update"] = datetime.now().isoformat()

    def record_duration(self, stage: str, duration: float):
        """记录阶段耗时"""
        if self.enabled:
            self.request_duration.labels(stage=stage).observe(duration)

        # 更新内存统计
        key = f"duration_{stage}"
        self._stats[key]["count"] += 1
        self._stats[key]["total_duration"] += duration
        self._stats[key]["last_update"] = datetime.now().isoformat()

    def record_cache_hit(self, cache_type: str):
        """记录缓存命中"""
        if self.enabled:
            self.cache_hits.labels(cache_type=cache_type).inc()

        # 更新内存统计
        self._stats[f"cache_hit_{cache_type}"]["count"] += 1
        self._stats[f"cache_hit_{cache_type}"]["last_update"] = datetime.now().isoformat()

    def record_api_call(self, provider: str, model: str):
        """记录 API 调用"""
        if self.enabled:
            self.api_calls.labels(provider=provider, model=model).inc()

        # 更新内存统计
        key = f"api_call_{provider}_{model}"
        self._stats[key]["count"] += 1
        self._stats[key]["last_update"] = datetime.now().isoformat()

    def record_error(self, component: str, error_type: str):
        """记录错误"""
        if self.enabled:
            self.errors.labels(component=component, error_type=error_type).inc()

        # 更新内存统计
        key = f"error_{component}_{error_type}"
        self._stats[key]["count"] += 1
        self._stats[key]["errors"] += 1
        self._stats[key]["last_update"] = datetime.now().isoformat()

    def inc_active_queries(self):
        """增加活跃查询数"""
        if self.enabled:
            self.active_queries.inc()

    def dec_active_queries(self):
        """减少活跃查询数"""
        if self.enabled:
            self.active_queries.dec()

    def get_stats(self) -> Dict:
        """获取内存中的统计数据"""
        stats = dict(self._stats)

        # 计算平均值
        averages = {}
        for key, data in self._stats.items():
            if key.startswith("duration_") and data["count"] > 0:
                avg = data["total_duration"] / data["count"]
                averages[key.replace("duration_", "avg_duration_")] = round(avg, 3)

        stats.update(averages)
        return stats

    def export_metrics(self) -> Optional[bytes]:
        """导出 Prometheus 格式的指标"""
        if self.enabled:
            return generate_latest(REGISTRY)
        return None

    def reset_stats(self):
        """重置统计数据"""
        self._stats.clear()


# 全局指标采集器实例
_global_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标采集器实例"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


class StageTimer:
    """
    阶段计时器（上下文管理器）

    自动记录阶段耗时到指标采集器

    用法：
        with StageTimer("parsing", metrics_collector):
            # 执行解析操作
            pass
    """

    def __init__(self, stage_name: str, collector: MetricsCollector = None):
        self.stage_name = stage_name
        self.collector = collector or get_metrics_collector()
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.collector.record_duration(self.stage_name, duration)

        if exc_type is not None:
            self.collector.record_error(self.stage_name, exc_type.__name__)


def observe_stage(stage_name: str):
    """
    装饰器：自动观察函数执行时间和错误

    用法：
        @observe_stage("parsing")
        def parse_query(query):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            with StageTimer(stage_name, collector):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    collector.record_error(stage_name, type(e).__name__)
                    raise
        return wrapper
    return decorator
