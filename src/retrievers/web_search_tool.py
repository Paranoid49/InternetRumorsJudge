import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from ddgs import DDGS
from langchain_tavily import TavilySearch

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import config

logger = logging.getLogger("WebSearchTool")

class WebSearchTool:
    """
    联网搜索工具类
    封装 LangChain 适配的 Tavily AI (首选) 和 DuckDuckGo 搜索。
    """
    
    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self.tavily_tool = None
        
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
        except Exception as e:
            logger.error(f"DuckDuckGo 搜索发生错误: {e}")
            
        return results

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    tool = WebSearchTool()
    res = tool.search("喝童子尿可以治新冠吗？")
    for i, r in enumerate(res):
        print(f"[{i+1}] {r['metadata'].get('title', '无标题')} ({r['metadata']['type']})\n    {r['metadata']['source']}\n")
