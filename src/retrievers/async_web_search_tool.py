"""
异步网络搜索工具

提供异步的网络搜索能力，用于：
1. Tavily API 异步调用
2. 连接池管理
3. 超时和重试处理

[v0.8.0] 新增模块 - 异步 I/O 优化第一阶段
"""
import asyncio
import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger("AsyncWebSearchTool")

# 检查 aiohttp 是否可用
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp 未安装，异步网络搜索不可用。请执行: pip install aiohttp")


class AsyncWebSearchTool:
    """
    异步网络搜索工具

    特性：
    - 异步 HTTP 请求
    - 连接池复用
    - 自动重试
    - 超时控制
    """

    def __init__(
        self,
        api_key: str = None,
        timeout: int = 15,
        max_retries: int = 2,
        max_connections: int = 10
    ):
        """
        初始化异步网络搜索工具

        Args:
            api_key: Tavily API 密钥
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            max_connections: 最大连接数
        """
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp 未安装，无法使用异步网络搜索")

        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_connections = max_connections

        # 延迟初始化
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

        # 统计信息
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_time_ms": 0,
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        获取或创建 aiohttp 会话（延迟初始化）

        Returns:
            aiohttp.ClientSession 实例
        """
        if self._session is None or self._session.closed:
            # 创建连接器
            self._connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=5,
                ttl_dns_cache=300,
            )

            # 创建会话
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "RumorJudge/0.8.0",
                }
            )

            # 并发控制
            self._semaphore = asyncio.Semaphore(self.max_connections)

        return self._session

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        异步搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            search_depth: 搜索深度 ("basic" 或 "advanced")
            include_domains: 包含的域名列表
            exclude_domains: 排除的域名列表

        Returns:
            搜索结果列表

        Raises:
            Exception: 搜索失败时抛出
        """
        if not self.api_key:
            logger.warning("TAVILY_API_KEY 未配置，返回空结果")
            return []

        session = await self._get_session()
        start_time = datetime.now()

        # 构建请求体
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }

        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        # 带重试的请求
        async with self._semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    self._stats["total_requests"] += 1

                    async with session.post(
                        "https://api.tavily.com/search",
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            results = self._parse_results(data)

                            # 更新统计
                            elapsed = (datetime.now() - start_time).total_seconds() * 1000
                            self._stats["successful_requests"] += 1
                            self._stats["total_time_ms"] += elapsed

                            logger.info(
                                f"异步搜索成功: query='{query[:30]}...', "
                                f"results={len(results)}, time={elapsed:.0f}ms"
                            )
                            return results

                        elif response.status == 429:
                            # 限流，等待后重试
                            retry_after = int(response.headers.get("Retry-After", 5))
                            logger.warning(f"触发限流，等待 {retry_after}s 后重试")
                            await asyncio.sleep(retry_after)
                            continue

                        else:
                            error_text = await response.text()
                            logger.error(f"搜索失败: status={response.status}, {error_text}")

                            if attempt < self.max_retries:
                                await asyncio.sleep(2 ** attempt)
                                continue

                            self._stats["failed_requests"] += 1
                            return []

                except asyncio.TimeoutError:
                    logger.warning(f"搜索超时 (attempt {attempt + 1}/{self.max_retries + 1})")
                    if attempt < self.max_retries:
                        await asyncio.sleep(1)
                        continue

                    self._stats["failed_requests"] += 1
                    return []

                except aiohttp.ClientError as e:
                    logger.error(f"网络错误: {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue

                    self._stats["failed_requests"] += 1
                    return []

                except Exception as e:
                    logger.exception(f"搜索异常: {e}")
                    self._stats["failed_requests"] += 1
                    return []

        return []

    def _parse_results(self, data: Dict) -> List[Dict[str, Any]]:
        """
        解析搜索结果

        Args:
            data: API 响应数据

        Returns:
            标准化的结果列表
        """
        results = []

        for item in data.get("results", []):
            results.append({
                "content": item.get("content", ""),
                "metadata": {
                    "source": item.get("url", ""),
                    "title": item.get("title", ""),
                    "score": item.get("score", 0.5),
                    "type": "web",
                }
            })

        return results

    async def search_batch(
        self,
        queries: List[str],
        max_results_per_query: int = 3,
    ) -> Dict[str, List[Dict]]:
        """
        批量异步搜索

        Args:
            queries: 查询列表
            max_results_per_query: 每个查询的最大结果数

        Returns:
            {query: results} 字典
        """
        tasks = [
            self.search(query, max_results=max_results_per_query)
            for query in queries
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for query, result in zip(queries, results_list):
            if isinstance(result, Exception):
                logger.error(f"批量搜索失败 [{query}]: {result}")
                results[query] = []
            else:
                results[query] = result

        return results

    async def close(self):
        """
        关闭连接池和会话
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        if self._connector:
            await self._connector.close()
            self._connector = None

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        stats = self._stats.copy()
        if stats["total_requests"] > 0:
            stats["success_rate"] = (
                stats["successful_requests"] / stats["total_requests"] * 100
            )
            stats["avg_time_ms"] = (
                stats["total_time_ms"] / stats["successful_requests"]
                if stats["successful_requests"] > 0 else 0
            )
        return stats

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 便捷函数
async def async_web_search(query: str, max_results: int = 5) -> List[Dict]:
    """
    便捷的异步搜索函数

    Args:
        query: 搜索查询
        max_results: 最大结果数

    Returns:
        搜索结果列表
    """
    async with AsyncWebSearchTool() as tool:
        return await tool.search(query, max_results=max_results)
