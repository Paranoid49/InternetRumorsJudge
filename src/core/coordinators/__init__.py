"""
核心协调器模块

提供流程编排的各个协调器组件

[v0.8.0] 新增异步协调器
"""
from .base import BaseCoordinator
from .query_processor import QueryProcessor
from .retrieval_coordinator import RetrievalCoordinator
from .analysis_coordinator import AnalysisCoordinator
from .verdict_generator import VerdictGenerator

# 异步协调器（可选导入）
try:
    from .async_coordinator import (
        AsyncQueryProcessor,
        AsyncRetrievalCoordinator,
        AsyncAnalysisCoordinator as AsyncAnalysisCoordinatorBase,
    )
    from .async_analysis_coordinator import AsyncAnalysisCoordinator
    from .async_verdict_generator import AsyncVerdictGenerator
    ASYNC_COORDINATORS_AVAILABLE = True
except ImportError:
    ASYNC_COORDINATORS_AVAILABLE = False

__all__ = [
    # 同步协调器
    'BaseCoordinator',
    'QueryProcessor',
    'RetrievalCoordinator',
    'AnalysisCoordinator',
    'VerdictGenerator',
    # 异步协调器
    'AsyncQueryProcessor',
    'AsyncRetrievalCoordinator',
    'AsyncAnalysisCoordinator',
    'AsyncVerdictGenerator',
    # 状态标志
    'ASYNC_COORDINATORS_AVAILABLE',
]
