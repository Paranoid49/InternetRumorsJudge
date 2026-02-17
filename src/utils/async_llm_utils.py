"""
异步 LLM 工具模块

提供异步的 LLM 调用能力，用于：
1. 异步 LLM 调用
2. 并发控制
3. 重试机制
4. 批量处理

[v0.8.0] 新增模块 - 异步 I/O 优化第一阶段
"""
import asyncio
import logging
import time
from typing import Optional, Any, List, Dict, Callable
from datetime import datetime

logger = logging.getLogger("AsyncLLMUtils")

# 检查异步支持
try:
    from langchain_core.language_models import BaseChatModel
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain 未安装，异步 LLM 功能受限")


class AsyncLLMWrapper:
    """
    LLM 异步包装器

    特性：
    - 异步调用（原生或线程池回退）
    - 并发控制（信号量）
    - 自动重试
    - 性能统计
    """

    def __init__(
        self,
        llm: Any,
        max_concurrency: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
    ):
        """
        初始化异步 LLM 包装器

        Args:
            llm: LangChain LLM 实例
            max_concurrency: 最大并发数
            max_retries: 最大重试次数
            retry_delay: 初始重试延迟（秒）
            retry_backoff: 重试延迟倍数
        """
        self._llm = llm
        self._max_concurrency = max_concurrency
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._retry_backoff = retry_backoff

        # 并发控制
        self._semaphore: Optional[asyncio.Semaphore] = None

        # 统计信息
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time_ms": 0,
            "total_tokens": 0,
        }

    def _get_semaphore(self) -> asyncio.Semaphore:
        """获取信号量（延迟初始化）"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
        return self._semaphore

    async def ainvoke(
        self,
        input: Any,
        config: Optional[Dict] = None,
        **kwargs
    ) -> Any:
        """
        异步调用 LLM

        Args:
            input: 输入（prompt 或消息列表）
            config: 配置选项
            **kwargs: 其他参数

        Returns:
            LLM 响应

        Raises:
            Exception: 调用失败时抛出
        """
        semaphore = self._get_semaphore()
        start_time = datetime.now()
        current_delay = self._retry_delay

        async with semaphore:
            for attempt in range(self._max_retries + 1):
                try:
                    self._stats["total_calls"] += 1

                    # 尝试原生异步调用
                    if hasattr(self._llm, 'ainvoke'):
                        result = await self._llm.ainvoke(input, config or {}, **kwargs)
                    elif hasattr(self._llm, 'ainvoke'):
                        result = await self._llm.ainvoke(input, config=config, **kwargs)
                    else:
                        # 回退到线程池
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda: self._llm.invoke(input, config or {}, **kwargs)
                        )

                    # 更新统计
                    elapsed = (datetime.now() - start_time).total_seconds() * 1000
                    self._stats["successful_calls"] += 1
                    self._stats["total_time_ms"] += elapsed

                    # 尝试提取 token 使用量
                    self._extract_token_usage(result)

                    return result

                except Exception as e:
                    error_msg = str(e).lower()

                    # 限流错误，等待后重试
                    if 'rate' in error_msg or 'limit' in error_msg or '429' in error_msg:
                        if attempt < self._max_retries:
                            wait_time = current_delay * 2  # 限流时加倍等待
                            logger.warning(
                                f"LLM 限流，等待 {wait_time}s 后重试 "
                                f"(attempt {attempt + 1}/{self._max_retries + 1})"
                            )
                            await asyncio.sleep(wait_time)
                            current_delay *= self._retry_backoff
                            continue

                    # 超时错误
                    if 'timeout' in error_msg:
                        if attempt < self._max_retries:
                            logger.warning(
                                f"LLM 超时，重试中 "
                                f"(attempt {attempt + 1}/{self._max_retries + 1})"
                            )
                            await asyncio.sleep(current_delay)
                            current_delay *= self._retry_backoff
                            continue

                    # 其他错误
                    if attempt < self._max_retries:
                        logger.warning(
                            f"LLM 调用失败: {e}，重试中 "
                            f"(attempt {attempt + 1}/{self._max_retries + 1})"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= self._retry_backoff
                        continue

                    # 最终失败
                    self._stats["failed_calls"] += 1
                    logger.error(f"LLM 调用最终失败: {e}")
                    raise

    async def abatch(
        self,
        inputs: List[Any],
        config: Optional[Dict] = None,
        return_exceptions: bool = False,
        **kwargs
    ) -> List[Any]:
        """
        批量异步调用 LLM

        Args:
            inputs: 输入列表
            config: 配置选项
            return_exceptions: 是否返回异常而非抛出
            **kwargs: 其他参数

        Returns:
            结果列表
        """
        tasks = [
            self.ainvoke(input, config, **kwargs)
            for input in inputs
        ]

        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)

    async def ainvoke_with_fallback(
        self,
        input: Any,
        fallback_llm: Optional[Any] = None,
        fallback_value: Any = None,
        **kwargs
    ) -> Any:
        """
        带回退的异步调用

        Args:
            input: 输入
            fallback_llm: 备用 LLM
            fallback_value: 最终回退值

        Returns:
            结果或回退值
        """
        try:
            return await self.ainvoke(input, **kwargs)
        except Exception as e:
            logger.warning(f"主 LLM 调用失败: {e}")

            if fallback_llm is not None:
                try:
                    # 创建备用包装器
                    fallback_wrapper = AsyncLLMWrapper(
                        fallback_llm,
                        max_concurrency=self._max_concurrency,
                        max_retries=1,
                    )
                    return await fallback_wrapper.ainvoke(input, **kwargs)
                except Exception as e2:
                    logger.error(f"备用 LLM 也失败: {e2}")

            return fallback_value

    def _extract_token_usage(self, result: Any):
        """从结果中提取 token 使用量"""
        try:
            if hasattr(result, 'usage_metadata'):
                self._stats["total_tokens"] += getattr(
                    result.usage_metadata, 'total_tokens', 0
                )
            elif hasattr(result, 'response_metadata'):
                token_usage = result.response_metadata.get('token_usage', {})
                self._stats["total_tokens"] += token_usage.get('total_tokens', 0)
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        stats = self._stats.copy()
        if stats["total_calls"] > 0:
            stats["success_rate"] = (
                stats["successful_calls"] / stats["total_calls"] * 100
            )
            stats["avg_time_ms"] = (
                stats["total_time_ms"] / stats["successful_calls"]
                if stats["successful_calls"] > 0 else 0
            )
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_time_ms": 0,
            "total_tokens": 0,
        }


class AsyncLLMPool:
    """
    异步 LLM 连接池

    管理多个 LLM 实例，提供负载均衡和故障转移
    """

    def __init__(
        self,
        llms: List[Any],
        max_concurrency_per_llm: int = 5,
        strategy: str = "round_robin",
    ):
        """
        初始化 LLM 连接池

        Args:
            llms: LLM 实例列表
            max_concurrency_per_llm: 每个 LLM 的最大并发数
            strategy: 负载均衡策略 ("round_robin", "random", "least_busy")
        """
        self._wrappers = [
            AsyncLLMWrapper(llm, max_concurrency=max_concurrency_per_llm)
            for llm in llms
        ]
        self._strategy = strategy
        self._current_index = 0

    def _select_wrapper(self) -> AsyncLLMWrapper:
        """选择一个 LLM 包装器"""
        if self._strategy == "round_robin":
            wrapper = self._wrappers[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._wrappers)
            return wrapper

        elif self._strategy == "random":
            import random
            return random.choice(self._wrappers)

        elif self._strategy == "least_busy":
            # 选择最空闲的（成功调用最少）
            return min(self._wrappers, key=lambda w: w._stats["successful_calls"])

        return self._wrappers[0]

    async def ainvoke(self, input: Any, **kwargs) -> Any:
        """异步调用（自动选择 LLM）"""
        wrapper = self._select_wrapper()
        return await wrapper.ainvoke(input, **kwargs)

    def get_all_stats(self) -> List[Dict]:
        """获取所有 LLM 的统计信息"""
        return [wrapper.get_stats() for wrapper in self._wrappers]


# 便捷函数
def create_async_llm_wrapper(
    llm: Any,
    max_concurrency: int = 10,
) -> AsyncLLMWrapper:
    """
    创建异步 LLM 包装器

    Args:
        llm: LangChain LLM 实例
        max_concurrency: 最大并发数

    Returns:
        AsyncLLMWrapper 实例
    """
    return AsyncLLMWrapper(llm, max_concurrency=max_concurrency)


async def run_sync_in_executor(func: Callable, *args, **kwargs) -> Any:
    """
    在线程池中运行同步函数

    Args:
        func: 同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数结果
    """
    loop = asyncio.get_event_loop()

    def wrapper():
        return func(*args, **kwargs)

    return await loop.run_in_executor(None, wrapper)
