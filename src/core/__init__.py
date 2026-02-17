"""
Core Module

包含系统核心组件：引擎、协调器、缓存、健康检查、异常定义等

[v0.8.0] 新增异步引擎和 ErrorCode
"""
from .pipeline import RumorJudgeEngine, UnifiedVerificationResult, PipelineStage
from .cache_manager import CacheManager
from .parallelism_config import get_parallelism_config, ParallelismConfig
from .health_check import HealthChecker, get_health_checker, health_check_endpoint, HealthCheckStatus
from .exceptions import (
    ErrorCode,
    RumorJudgeException,
    CacheException,
    CacheMissException,
    CacheStaleException,
    RetrievalException,
    KnowledgeBaseException,
    WebSearchException,
    AnalysisException,
    QueryParseException,
    EvidenceAnalyzeException,
    VerdictGenerateException,
    LLMException,
    LLMTimeoutException,
    LLMQuotaException,
    ConfigurationException,
    DependencyException,
    ConcurrencyException,
    LockTimeoutException,
    handle_exception,
    create_exception_from_error
)

# 异步引擎（可选导入）
try:
    from .async_pipeline import AsyncRumorJudgeEngine, async_verify, verify
    ASYNC_ENGINE_AVAILABLE = True
except ImportError:
    ASYNC_ENGINE_AVAILABLE = False

__all__ = [
    # 同步引擎
    'RumorJudgeEngine',
    'UnifiedVerificationResult',
    'PipelineStage',
    # 异步引擎
    'AsyncRumorJudgeEngine',
    'async_verify',
    'verify',
    'ASYNC_ENGINE_AVAILABLE',
    # 缓存
    'CacheManager',
    # 并行度配置
    'get_parallelism_config',
    'ParallelismConfig',
    # 健康检查
    'HealthChecker',
    'get_health_checker',
    'health_check_endpoint',
    'HealthCheckStatus',
    # 异常（v0.8.0 增强）
    'ErrorCode',
    'RumorJudgeException',
    'CacheException',
    'CacheMissException',
    'CacheStaleException',
    'RetrievalException',
    'KnowledgeBaseException',
    'WebSearchException',
    'AnalysisException',
    'QueryParseException',
    'EvidenceAnalyzeException',
    'VerdictGenerateException',
    'LLMException',
    'LLMTimeoutException',
    'LLMQuotaException',
    'ConfigurationException',
    'DependencyException',
    'ConcurrencyException',
    'LockTimeoutException',
    'handle_exception',
    'create_exception_from_error',
]
