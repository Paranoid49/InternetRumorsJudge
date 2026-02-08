"""
Core Module

包含系统核心组件：引擎、协调器、缓存、健康检查、异常定义等
"""
from .pipeline import RumorJudgeEngine, UnifiedVerificationResult, PipelineStage
from .cache_manager import CacheManager
from .parallelism_config import get_parallelism_config, ParallelismConfig
from .health_check import HealthChecker, get_health_checker, health_check_endpoint, HealthCheckStatus
from .exceptions import (
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

__all__ = [
    'RumorJudgeEngine',
    'UnifiedVerificationResult',
    'PipelineStage',
    'CacheManager',
    'get_parallelism_config',
    'ParallelismConfig',
    'HealthChecker',
    'get_health_checker',
    'health_check_endpoint',
    'HealthCheckStatus',
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
