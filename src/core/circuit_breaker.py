"""
熔断器

当下游服务（LLM、网络搜索）故障时，快速失败避免级联
"""
import time
import logging
from enum import Enum
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger("CircuitBreaker")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"       # 正常状态：请求正常通过
    OPEN = "open"           # 熔断状态：快速失败
    HALF_OPEN = "half_open" # 半开状态：尝试恢复


class CircuitBreaker:
    """
    熔断器实现

    当失败率超过阈值时，熔断器打开，快速失败
    经过一段时间后进入半开状态，尝试恢复
    """

    def __init__(
        self,
        failure_threshold: int = 5,      # 失败次数阈值
        success_threshold: int = 2,      # 成功次数阈值（半开状态）
        timeout: int = 60,               # 熔断超时（秒）
        exception_types: tuple = (Exception,)
    ):
        """
        初始化熔断器

        Args:
            failure_threshold: 失败次数阈值，超过此值熔断器打开
            success_threshold: 半开状态下需要的成功次数
            timeout: 熔断后等待多久尝试恢复（秒）
            exception_types: 哪些异常计入失败
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.exception_types = exception_types

        # 状态
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None

    def call(self, func: Callable, *args, **kwargs):
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            Exception: 如果熔断器打开，抛出 CircuitBreakerOpenError
        """
        if self.state == CircuitState.OPEN:
            # 检查是否可以尝试恢复
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("熔断器进入半开状态，尝试恢复")
            else:
                raise CircuitBreakerOpenError(
                    f"熔断器已打开，请稍后重试 (timeout: {self.timeout}s)"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.exception_types as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        if self.opened_at is None:
            return False
        return time.time() - self.opened_at >= self.timeout

    def _on_success(self):
        """处理成功调用"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(f"熔断器半开状态成功计数: {self.success_count}/{self.success_threshold}")

            if self.success_count >= self.success_threshold:
                self._reset()
                logger.info("熔断器已恢复到正常状态")
        else:
            # 正常状态下，重置失败计数
            self.failure_count = 0

    def _on_failure(self):
        """处理失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下失败，重新打开熔断器
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
            self.success_count = 0
            logger.warning(f"熔断器在半开状态下失败，重新打开 (失败计数: {self.failure_count})")
        elif self.failure_count >= self.failure_threshold:
            # 达到失败阈值，打开熔断器
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
            logger.error(f"熔断器已打开 (失败计数: {self.failure_count}/{self.failure_threshold})")

    def _reset(self):
        """重置熔断器到正常状态"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None

    def reset(self):
        """手动重置熔断器"""
        self._reset()
        logger.info("熔断器已手动重置")

    def get_state(self) -> CircuitState:
        """获取当前状态"""
        return self.state


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""
    pass


# 全局熔断器实例
_global_breakers: dict = {}


def get_circuit_breaker(name: str = "default") -> CircuitBreaker:
    """
    获取或创建熔断器实例

    Args:
        name: 熔断器名称（可以为不同服务创建不同的熔断器）

    Returns:
        CircuitBreaker 实例
    """
    if name not in _global_breakers:
        _global_breakers[name] = CircuitBreaker(
            failure_threshold=5,
            success_threshold=2,
            timeout=60
        )
        logger.info(f"创建熔断器: {name}")
    return _global_breakers[name]


def with_circuit_breaker(breaker_name: str = "default"):
    """
    装饰器：为函数添加熔断器保护

    用法：
        @with_circuit_breaker("llm_service")
        def call_llm(prompt):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            breaker = get_circuit_breaker(breaker_name)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator
