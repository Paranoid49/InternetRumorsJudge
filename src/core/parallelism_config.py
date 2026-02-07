"""
并行度配置模块

提供动态并行度调整策略，根据系统资源和任务特征自动调整并行度。
"""
import os
import logging
from typing import Optional
from threading import Lock

logger = logging.getLogger("ParallelismConfig")


class ParallelismConfig:
    """
    并行度配置类

    职责：
    1. 根据CPU核心数计算建议并行度
    2. 支持环境变量配置覆盖
    3. 提供不同场景的并行度策略
    4. 线程安全的单例模式
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化并行度配置"""
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return

        # 获取CPU核心数
        self._cpu_count = os.cpu_count() or 4

        # 从环境变量读取配置
        self._max_workers = self._read_env_var('MAX_WORKERS', None)
        self._evidence_analyzer_workers = self._read_env_var('EVIDENCE_ANALYZER_WORKERS', None)
        self._retrieval_workers = self._read_env_var('RETRIEVAL_WORKERS', None)

        # 计算默认并行度（CPU核心数的1.5倍，最少2个，最多10个）
        default_workers = min(max(self._cpu_count * 1.5, 2), 10)
        self._default_workers = int(default_workers)

        logger.info(
            f"并行度配置初始化: CPU核心={self._cpu_count}, "
            f"默认并行度={self._default_workers}, "
            f"配置MAX_WORKERS={self._max_workers or '未设置'}"
        )

        self._initialized = True

    def _read_env_var(self, key: str, default: Optional[int]) -> Optional[int]:
        """
        读取环境变量并转换为整数

        Args:
            key: 环境变量名
            default: 默认值

        Returns:
            整数值或None
        """
        value = os.getenv(key, '')
        if not value:
            return default

        try:
            return int(value)
        except ValueError:
            logger.warning(f"环境变量 {key}={value} 不是有效整数，使用默认值")
            return default

    def get_max_workers(self, task_type: str = 'default') -> int:
        """
        获取最大并行度

        Args:
            task_type: 任务类型 ('default', 'evidence_analyzer', 'retrieval', 'embedding')

        Returns:
            最大并行度
        """
        # 全局配置优先
        if self._max_workers is not None:
            return self._max_workers

        # 任务类型特定配置
        if task_type == 'evidence_analyzer':
            if self._evidence_analyzer_workers is not None:
                return self._evidence_analyzer_workers
            # 证据分析是IO密集型，可以更高
            return min(self._default_workers * 2, 15)

        if task_type == 'retrieval':
            if self._retrieval_workers is not None:
                return self._retrieval_workers
            # 检索也是IO密集型
            return min(self._default_workers * 1.5, 12)

        if task_type == 'embedding':
            # 嵌入计算是CPU密集型，不宜过高
            return min(self._default_workers, 8)

        # 默认并行度
        return self._default_workers

    def get_adaptive_workers(
        self,
        task_count: int,
        task_type: str = 'default',
        min_workers: int = 1
    ) -> int:
        """
        获取自适应并行度

        根据任务数量动态调整并行度，避免创建过多线程

        Args:
            task_count: 任务数量
            task_type: 任务类型
            min_workers: 最小并行度

        Returns:
            建议的并行度
        """
        max_workers = self.get_max_workers(task_type)

        # 任务数少于最大并行度时，使用任务数
        if task_count < max_workers:
            return max(task_count, min_workers)

        # 任务数多于最大并行度时，使用最大并行度
        return max_workers

    def get_info(self) -> dict:
        """
        获取配置信息

        Returns:
            配置信息字典
        """
        return {
            'cpu_count': self._cpu_count,
            'default_workers': self._default_workers,
            'max_workers': self._max_workers,
            'evidence_analyzer_workers': self._evidence_analyzer_workers,
            'retrieval_workers': self._retrieval_workers,
        }


# 全局单例
_parallelism_config = None


def get_parallelism_config() -> ParallelismConfig:
    """
    获取并行度配置单例

    Returns:
        ParallelismConfig 实例
    """
    global _parallelism_config
    if _parallelism_config is None:
        _parallelism_config = ParallelismConfig()
    return _parallelism_config
