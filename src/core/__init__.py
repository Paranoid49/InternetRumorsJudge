"""
Core Module

包含系统核心组件：引擎、协调器、缓存、健康检查等
"""
from .pipeline import RumorJudgeEngine, UnifiedVerificationResult, PipelineStage
from .cache_manager import CacheManager
from .parallelism_config import get_parallelism_config, ParallelismConfig
from .health_check import HealthChecker, get_health_checker, health_check_endpoint, HealthCheckStatus

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
]
