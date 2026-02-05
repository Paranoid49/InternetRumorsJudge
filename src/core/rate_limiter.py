"""
请求限流器

防止突发流量导致成本失控
支持IP级别的限流
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("RateLimiter")


class RateLimiter:
    """
    简单的令牌桶限流器

    支持按客户端IP限流
    """

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        """
        初始化限流器

        Args:
            requests_per_minute: 每分钟请求数限制
            burst_size: 突发流量缓冲区大小
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size

        # 存储每个客户端的令牌桶状态
        # 格式: {client_id: {"tokens": float, "last_refill": float}}
        self._buckets: Dict[str, Dict] = defaultdict(lambda: {
            "tokens": float(burst_size),
            "last_refill": time.time()
        })

    def _refill_tokens(self, client_id: str):
        """补充令牌"""
        now = time.time()
        bucket = self._buckets[client_id]

        # 计算自上次补充以来经过的时间
        time_passed = now - bucket["last_refill"]

        # 根据时间补充令牌（每分钟 requests_per_minute 个令牌）
        tokens_to_add = time_passed * (self.requests_per_minute / 60.0)

        # 补充令牌，不超过 burst_size
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now

    def is_allowed(self, client_id: str = "default") -> tuple[bool, Optional[float]]:
        """
        检查请求是否允许通过

        Args:
            client_id: 客户端标识（通常是IP地址）

        Returns:
            (是否允许, 等待秒数)
        """
        self._refill_tokens(client_id)
        bucket = self._buckets[client_id]

        # 检查是否有足够的令牌
        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True, None
        else:
            # 计算需要等待的时间
            tokens_needed = 1.0 - bucket["tokens"]
            wait_time = tokens_needed * (60.0 / self.requests_per_minute)
            return False, wait_time

    def reset(self, client_id: str = None):
        """重置限流状态"""
        if client_id:
            if client_id in self._buckets:
                del self._buckets[client_id]
        else:
            self._buckets.clear()


class SlidingWindowRateLimiter:
    """
    滑动窗口限流器

    更精确的限流实现，基于时间窗口内的实际请求数
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """
        初始化滑动窗口限流器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口大小（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # 存储每个客户端的请求时间戳
        # 格式: {client_id: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_id: str = "default") -> tuple[bool, Optional[float]]:
        """
        检查请求是否允许通过

        Args:
            client_id: 客户端标识

        Returns:
            (是否允许, 等待秒数)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # 获取该客户端的请求时间戳列表
        requests = self._requests[client_id]

        # 移除窗口外的旧请求
        self._requests[client_id] = [ts for ts in requests if ts > window_start]
        requests = self._requests[client_id]

        # 检查是否超过限制
        if len(requests) < self.max_requests:
            # 允许请求，记录时间戳
            requests.append(now)
            return True, None
        else:
            # 计算需要等待的时间（最早的请求何时过期）
            oldest_request = requests[0]
            wait_time = oldest_request + self.window_seconds - now
            return False, max(0.0, wait_time)

    def reset(self, client_id: str = None):
        """重置限流状态"""
        if client_id:
            if client_id in self._requests:
                del self._requests[client_id]
        else:
            self._requests.clear()


# 全局限流器实例（默认配置）
_global_limiter = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """获取全局限流器实例"""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = SlidingWindowRateLimiter(
            max_requests=60,  # 每分钟60个请求
            window_seconds=60
        )
    return _global_limiter
