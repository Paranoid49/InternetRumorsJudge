"""
Observability Module

提供结构化日志、指标采集、API监控和链路追踪功能

[v1.1.0] 新增 LLM 和 Embedding 监控回调
[v1.2.0] 增强日志配置：支持环境变量、避免重复配置
"""
from .logger_config import (
    get_logger,
    configure_logging,
    ensure_configured,
    is_configured,
    set_trace_id,
    get_trace_id,
    clear_trace_id,
    RequestContext,
    Timer,
    STRUCTLOG_AVAILABLE
)
from .metrics import MetricsCollector
from .api_monitor import APIMonitor, QuotaConfig, get_api_monitor
from .llm_monitor_callback import LLMMonitorCallback, get_llm_monitor_callback
from .embedding_monitor import EmbeddingMonitorCallback, get_embedding_monitor_callback

__all__ = [
    # 日志配置
    'get_logger',
    'configure_logging',
    'ensure_configured',
    'is_configured',
    # 链路追踪
    'set_trace_id',
    'get_trace_id',
    'clear_trace_id',
    'RequestContext',
    # 工具
    'Timer',
    'STRUCTLOG_AVAILABLE',
    # 指标采集
    'MetricsCollector',
    # API 监控
    'APIMonitor',
    'QuotaConfig',
    'get_api_monitor',
    # LLM 监控
    'LLMMonitorCallback',
    'get_llm_monitor_callback',
    # Embedding 监控
    'EmbeddingMonitorCallback',
    'get_embedding_monitor_callback'
]
