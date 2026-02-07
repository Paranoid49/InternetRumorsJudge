"""
线程安全工具模块

提供细粒度锁管理和线程安全的上下文管理器
"""
import threading
from contextlib import contextmanager
from typing import Dict, Optional
from functools import wraps
import logging

logger = logging.getLogger("ThreadUtils")


class LockManager:
    """
    细粒度锁管理器

    特性：
    1. 支持多个命名锁，避免锁冲突
    2. 自动记录锁等待时间
    3. 防止死锁的超时机制
    4. 可观测性支持
    """

    def __init__(self):
        self._locks: Dict[str, threading.RLock] = {}
        self._lock_stats: Dict[str, dict] = {}
        self._meta_lock = threading.Lock()

    def _get_lock(self, name: str) -> threading.RLock:
        """获取或创建命名锁"""
        with self._meta_lock:
            if name not in self._locks:
                self._locks[name] = threading.RLock()
                self._lock_stats[name] = {
                    'acquire_count': 0,
                    'contention_count': 0,
                    'total_wait_time_ms': 0
                }
            return self._locks[name]

    @contextmanager
    def acquire(self, name: str, timeout: Optional[float] = None):
        """
        获取命名锁的上下文管理器

        Args:
            name: 锁名称
            timeout: 超时时间（秒），None表示无限等待

        Raises:
            TimeoutError: 如果获取锁超时
        """
        import time
        lock = self._get_lock(name)
        stats = self._lock_stats[name]
        start_time = time.time()

        acquired = False
        try:
            if timeout is None:
                lock.acquire()
            else:
                acquired = lock.acquire(timeout=timeout)
                if not acquired:
                    wait_time = (time.time() - start_time) * 1000
                    stats['contention_count'] += 1
                    logger.error(
                        f"锁 '{name}' 获取超时 (等待 {wait_time:.2f}ms)"
                    )
                    raise TimeoutError(f"获取锁 '{name}' 超时")

            wait_time = (time.time() - start_time) * 1000
            stats['acquire_count'] += 1
            stats['total_wait_time_ms'] += wait_time

            if wait_time > 10:  # 等待超过10ms记录警告
                logger.warning(
                    f"锁 '{name}' 等待时间较长: {wait_time:.2f}ms"
                )

            yield

        finally:
            if acquired or timeout is None:
                lock.release()

    def get_stats(self, name: Optional[str] = None) -> dict:
        """
        获取锁统计信息

        Args:
            name: 锁名称，None表示返回所有锁的统计

        Returns:
            统计信息字典
        """
        if name is not None:
            return self._lock_stats.get(name, {})
        return self._lock_stats.copy()

    def reset_stats(self, name: Optional[str] = None):
        """重置锁统计信息"""
        with self._meta_lock:
            if name is not None:
                if name in self._lock_stats:
                    self._lock_stats[name] = {
                        'acquire_count': 0,
                        'contention_count': 0,
                        'total_wait_time_ms': 0
                    }
            else:
                for key in self._lock_stats:
                    self._lock_stats[key] = {
                        'acquire_count': 0,
                        'contention_count': 0,
                        'total_wait_time_ms': 0
                    }


# 全局锁管理器实例
_global_lock_manager = LockManager()


def get_lock_manager() -> LockManager:
    """获取全局锁管理器实例"""
    return _global_lock_manager


def synchronized(lock_name: str = None, timeout: Optional[float] = None):
    """
    方法同步装饰器

    Args:
        lock_name: 锁名称，None使用方法名
        timeout: 超时时间（秒）

    Usage:
        @synchronized("my_resource")
        def critical_section(self):
            # 临界区代码
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = lock_name if lock_name is not None else func.__name__
            with get_lock_manager().acquire(name, timeout=timeout):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class ThreadSafeLazyLoader:
    """
    线程安全的延迟加载器

    特性：
    1. 双重检查锁定
    2. 支持初始化函数
    3. 线程安全的属性访问
    """

    def __init__(self, init_func, lock_name: str = None):
        """
        Args:
            init_func: 初始化函数
            lock_name: 使用的锁名称
        """
        self._init_func = init_func
        self._lock_name = lock_name if lock_name else "lazy_loader"
        self._value = None
        self._initialized = False

    def get(self):
        """获取值，如果未初始化则先初始化"""
        if self._initialized:
            return self._value

        with get_lock_manager().acquire(self._lock_name):
            # 双重检查
            if self._initialized:
                return self._value

            try:
                self._value = self._init_func()
                self._initialized = True
                logger.debug(f"延迟加载器 '{self._lock_name}' 初始化完成")
                return self._value
            except Exception as e:
                logger.error(f"延迟加载器 '{self._lock_name}' 初始化失败: {e}")
                raise

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def reset(self):
        """重置（用于测试）"""
        with get_lock_manager().acquire(self._lock_name):
            self._value = None
            self._initialized = False


def run_with_timeout(func, timeout: float, default=None):
    """
    在超时时间内运行函数

    Args:
        func: 要执行的函数
        timeout: 超时时间（秒）
        default: 超时时的返回值

    Returns:
        函数结果或默认值
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning(f"函数执行超时 ({timeout}秒)，返回默认值")
            return default
