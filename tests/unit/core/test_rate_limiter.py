"""
测试请求限流器

测试覆盖：
- RateLimiter 令牌桶限流器
- SlidingWindowRateLimiter 滑动窗口限流器
- 全局限流器获取
"""
import pytest
import time
from unittest.mock import patch

from src.core.rate_limiter import (
    RateLimiter,
    SlidingWindowRateLimiter,
    get_rate_limiter
)


class TestRateLimiter:
    """测试令牌桶限流器"""

    def test_init_default_values(self):
        """测试默认初始化值"""
        limiter = RateLimiter()
        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 10

    def test_init_custom_values(self):
        """测试自定义初始化值"""
        limiter = RateLimiter(requests_per_minute=30, burst_size=5)
        assert limiter.requests_per_minute == 30
        assert limiter.burst_size == 5

    def test_is_allowed_initial(self):
        """测试初始请求允许"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)

        allowed, wait_time = limiter.is_allowed("client1")
        assert allowed is True
        assert wait_time is None

    def test_is_allowed_multiple_clients(self):
        """测试多客户端独立限流"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)

        # 客户端1可以请求2次
        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client1")[0] is False  # 第三次被拒绝

        # 客户端2独立的限流
        assert limiter.is_allowed("client2")[0] is True
        assert limiter.is_allowed("client2")[0] is True
        assert limiter.is_allowed("client2")[0] is False

    def test_is_allowed_returns_wait_time(self):
        """测试返回等待时间"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # 第一次允许
        limiter.is_allowed("client1")
        # 第二次被拒绝
        allowed, wait_time = limiter.is_allowed("client1")
        assert allowed is False
        assert wait_time is not None
        assert wait_time > 0

    def test_reset_specific_client(self):
        """测试重置特定客户端"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # 消耗客户端1的令牌
        limiter.is_allowed("client1")
        assert limiter.is_allowed("client1")[0] is False

        # 重置客户端1
        limiter.reset("client1")
        assert limiter.is_allowed("client1")[0] is True

    def test_reset_all_clients(self):
        """测试重置所有客户端"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # 消耗令牌
        limiter.is_allowed("client1")
        limiter.is_allowed("client2")

        # 重置所有
        limiter.reset()
        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client2")[0] is True

    def test_token_refill(self):
        """测试令牌补充"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)

        # 消耗令牌
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        assert limiter.is_allowed("client1")[0] is False

        # 手动设置 bucket 的时间戳，模拟时间流逝
        import time as time_module
        original_time = time_module.time()
        limiter._buckets["client1"]["last_refill"] = original_time - 2  # 2秒前

        # 现在触发 refill
        limiter._refill_tokens("client1")

        # 2秒 * (60/60) = 2 个令牌补充，但 burst_size=2
        # 所以应该有2个令牌
        assert limiter._buckets["client1"]["tokens"] == 2.0

    def test_default_client(self):
        """测试默认客户端ID"""
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)

        # 不提供client_id
        assert limiter.is_allowed()[0] is True
        assert limiter.is_allowed()[0] is False


class TestSlidingWindowRateLimiter:
    """测试滑动窗口限流器"""

    def test_init_default_values(self):
        """测试默认初始化值"""
        limiter = SlidingWindowRateLimiter()
        assert limiter.max_requests == 60
        assert limiter.window_seconds == 60

    def test_init_custom_values(self):
        """测试自定义初始化值"""
        limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=30)
        assert limiter.max_requests == 30
        assert limiter.window_seconds == 30

    def test_is_allowed_initial(self):
        """测试初始请求允许"""
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)

        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client1")[0] is True

    def test_is_allowed_exceeds_limit(self):
        """测试超过限制"""
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)

        limiter.is_allowed("client1")
        limiter.is_allowed("client1")

        allowed, wait_time = limiter.is_allowed("client1")
        assert allowed is False
        assert wait_time is not None

    def test_is_allowed_multiple_clients(self):
        """测试多客户端独立限流"""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client1")[0] is False

        assert limiter.is_allowed("client2")[0] is True
        assert limiter.is_allowed("client2")[0] is False

    def test_reset_specific_client(self):
        """测试重置特定客户端"""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

        limiter.is_allowed("client1")
        assert limiter.is_allowed("client1")[0] is False

        limiter.reset("client1")
        assert limiter.is_allowed("client1")[0] is True

    def test_reset_all_clients(self):
        """测试重置所有客户端"""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

        limiter.is_allowed("client1")
        limiter.is_allowed("client2")

        limiter.reset()

        assert limiter.is_allowed("client1")[0] is True
        assert limiter.is_allowed("client2")[0] is True

    def test_default_client(self):
        """测试默认客户端ID"""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

        assert limiter.is_allowed()[0] is True
        assert limiter.is_allowed()[0] is False

    def test_window_expiry(self):
        """测试窗口过期"""
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=1)

        # 第一次请求
        limiter.is_allowed("client1")
        assert limiter.is_allowed("client1")[0] is False

        # 等待窗口过期
        time.sleep(1.1)

        # 窗口过期后应该允许
        assert limiter.is_allowed("client1")[0] is True


class TestGetRateLimiter:
    """测试获取全局限流器"""

    def test_returns_limiter_instance(self):
        """测试返回限流器实例"""
        # 重置全局实例
        import src.core.rate_limiter as module
        module._global_limiter = None

        limiter = get_rate_limiter()
        assert isinstance(limiter, SlidingWindowRateLimiter)

    def test_singleton_behavior(self):
        """测试单例行为"""
        # 重置全局实例
        import src.core.rate_limiter as module
        module._global_limiter = None

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_default_configuration(self):
        """测试默认配置"""
        import src.core.rate_limiter as module
        module._global_limiter = None

        limiter = get_rate_limiter()
        assert limiter.max_requests == 60
        assert limiter.window_seconds == 60
