import logging
import os
from typing import List, Dict, Any
from ddgs import DDGS
from langchain_tavily import TavilySearch

# 项目路径由 src/__init__.py 统一设置
from src import config

logger = logging.getLogger("WebSearchTool")

class WebSearchTool:
    """
    联网搜索工具类
    封装 LangChain 适配的 Tavily AI (首选) 和 DuckDuckGo 搜索。

    [v1.0.1] 新增 API 监控支持
    """

    def __init__(self, max_results: int = 5, enable_monitoring: bool = True):
        self.max_results = max_results
        self.tavily_tool = None

        # API 监控器（v1.0.1）
        self._monitor = None
        if enable_monitoring:
            try:
                from src.observability.api_monitor import get_api_monitor
                self._monitor = get_api_monitor()
                logger.debug("API 监控已启用")
            except Exception as e:
                logger.warning(f"无法初始化 API 监控: {e}")

        # 确保环境变量已设置，LangChain 的 TavilySearchResults 会自动读取 TAVILY_API_KEY
        if config.TAVILY_API_KEY:
            os.environ["TAVILY_API_KEY"] = config.TAVILY_API_KEY
            try:
                self.tavily_tool = TavilySearch(
                    max_results=self.max_results,
                    search_depth="basic" # 从 advanced 改为 basic 以提升速度
                )
                logger.info("LangChain Tavily 搜索工具初始化成功。")
            except Exception as e:
                logger.error(f"LangChain Tavily 搜索工具初始化失败: {e}")

    def _record_search_api(self, provider: str, num_results: int):
        """
        记录搜索 API 调用

        Args:
            provider: 提供商（tavily 或 ddg）
            num_results: 结果数量
        """
        if self._monitor is None:
            return

        try:
            # Tavily 按次计费，DuckDuckGo 免费
            if provider == 'tavily':
                cost = self._monitor.record_api_call(
                    provider='tavily',
                    model='search',
                    endpoint='search',
                    input_tokens=0,
                    output_tokens=0
                )
                logger.debug(f"Tavily 搜索已记录: {num_results} 结果, cost={cost:.6f}元")

        except Exception as e:
            logger.error(f"记录搜索 API 调用时出错: {e}")

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        执行搜索并返回结果列表。优先使用 Tavily AI，失败或未配置则使用 DuckDuckGo。
        """
        # 1. 尝试使用 Tavily AI (LangChain 版)
        if self.tavily_tool:
            try:
                logger.info(f"正在使用 Tavily AI 搜索: {query} ...")
                # TavilySearch 的 invoke 方法返回一个包含 'results' 列表的字典
                search_query = f"{query} 辟谣 核查"
                response = self.tavily_tool.invoke({"query": search_query})
                
                results = []
                # 检查返回格式，确保它是字典且包含 'results'
                if isinstance(response, dict) and 'results' in response:
                    for r in response['results']:
                        results.append({
                            "content": r.get('content', ''),
                            "metadata": {
                                "source": r.get('url', ''),
                                "title": r.get('title', 'Tavily 搜索结果'),
                                "type": "tavily_search",
                                "score": r.get('score', 0)
                            }
                        })
                elif isinstance(response, list):
                    # 兼容某些版本可能直接返回列表的情况
                    for r in response:
                        if isinstance(r, dict):
                            results.append({
                                "content": r.get('content', ''),
                                "metadata": {
                                    "source": r.get('url', ''),
                                    "title": r.get('title', 'Tavily 搜索结果'),
                                    "type": "tavily_search"
                                }
                            })
                
                if results:
                    logger.info(f"Tavily AI 搜索完成，找到 {len(results)} 条线索。")
                    # 记录 API 调用（v1.0.1）
                    self._record_search_api('tavily', len(results))
                    return results
            except Exception as e:
                logger.error(f"Tavily AI 搜索发生错误: {e}，将尝试备用方案。")

        # 2. 备用方案：DuckDuckGo
        return self._search_duckduckgo(query)

    def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """
        DuckDuckGo 搜索实现
        """
        logger.info(f"正在使用 DuckDuckGo 搜索: {query} ...")
        results = []
        try:
            with DDGS() as ddgs:
                search_query = f"{query} 辟谣"
                ddgs_gen = ddgs.text(search_query, region='cn-zh', safesearch='off', timelimit='y')
                
                for r in ddgs_gen:
                    results.append({
                        "content": r['body'],
                        "metadata": {
                            "source": r['href'],
                            "title": r['title'],
                            "type": "ddg_search"
                        }
                    })
                    if len(results) >= self.max_results:
                        break
                        
            logger.info(f"DuckDuckGo 搜索完成，找到 {len(results)} 条线索。")
            # DuckDuckGo 免费，不记录成本
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索发生错误: {e}")

        return results

if __name__ == "__main__":
    # 测试代码
    from src.observability.logger_config import configure_logging, get_logger
    configure_logging()
    tool = WebSearchTool()
    res = tool.search("喝童子尿可以治新冠吗？")
    for i, r in enumerate(res):
        print(f"[{i+1}] {r['metadata'].get('title', '无标题')} ({r['metadata']['type']})\n    {r['metadata']['source']}\n")
