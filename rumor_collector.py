import logging
import time
import threading
from typing import List, Set
from datetime import datetime
import config
from web_search_tool import WebSearchTool
from pipeline import RumorJudgeEngine, UnifiedVerificationResult
from knowledge_integrator import KnowledgeIntegrator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RumorCollector")

class RumorCollector:
    """
    自动谣言收集器
    职责：
    1. 自动从互联网发现最新谣言/传闻
    2. 利用引擎进行核查
    3. 将高价值结果沉淀为本地知识
    """
    
    def __init__(self):
        self.web_search = WebSearchTool(max_results=10)
        self.engine = RumorJudgeEngine()
        self.integrator = KnowledgeIntegrator()
        
        # 用于提取主题的轻量级模型
        self.llm = ChatOpenAI(
            model=config.MODEL_PARSER,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=config.API_KEY,
            temperature=0.3
        )
        
        self.processed_topics: Set[str] = set()
        self._running = False
        self._thread = None

    def discover_topics(self) -> List[str]:
        """从互联网搜索并提取潜在的谣言主题"""
        search_keywords = ["近期热门辟谣", "最新社交媒体传闻", "今日事实核查", "近期流行谣言清单"]
        all_snippets = []
        
        logger.info("正在从互联网发现新话题...")
        for kw in search_keywords:
            results = self.web_search.search(kw)
            for r in results:
                all_snippets.append(f"标题: {r['metadata'].get('title')}\n摘要: {r['content']}")
        
        if not all_snippets:
            return []

        # 利用 LLM 从搜索结果中提取具体的谣言陈述
        context = "\n---\n".join(all_snippets[:15])
        prompt = f"""
        以下是最近关于辟谣和传闻的搜索结果：
        {context}
        
        请从中提取出最近比较热门、具体的谣言或传闻陈述（每条陈述应该是独立、完整的句子）。
        只提取那些看起来有核查价值的内容。
        
        输出格式：
        1. 谣言陈述1
        2. 谣言陈述2
        ...
        """
        
        try:
            messages = [
                SystemMessage(content="你是一个敏感的谣言监测助手。"),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            lines = response.content.strip().split('\n')
            topics = []
            for line in lines:
                # 简单清洗
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    topic = line.split('.', 1)[-1].split('-', 1)[-1].strip()
                    if len(topic) > 5:
                        topics.append(topic)
            return list(set(topics))
        except Exception as e:
            logger.error(f"提取话题失败: {e}")
            return []

    def collect_once(self):
        """执行一次完整的收集流程"""
        logger.info("开始执行自动收集任务...")
        topics = self.discover_topics()
        logger.info(f"发现 {len(topics)} 个潜在话题。")
        
        count = 0
        for topic in topics:
            if topic in self.processed_topics:
                continue
            
            # 简单检查本地库是否已存在（通过相似度）
            # 这里可以调用 engine 的缓存检查逻辑
            try:
                # 1. 执行核查 (使用缓存)
                result: UnifiedVerificationResult = self.engine.run(topic, use_cache=True)
                
                # 2. 如果是新发现（非缓存）且置信度高，则沉淀
                if not result.is_cached and result.confidence_score >= 80:
                    logger.info(f"发现高价值新知识，准备沉淀: {topic}")
                    
                    # 构造沉淀内容
                    combined_evidence = "\n\n".join([
                        f"来源: {ev['metadata']['source']}\n内容: {ev['content']}" 
                        for ev in result.retrieved_evidence
                    ])
                    
                    content = self.integrator.generate_knowledge_content(
                        query=topic, 
                        comment=f"系统自动核查结果：\n结论：{result.final_verdict}\n总结：{result.summary_report}\n\n参考证据：\n{combined_evidence}"
                    )
                    
                    if content:
                        timestamp = int(time.time())
                        safe_title = "".join([c for c in topic if c.isalnum()])[:20]
                        filename = f"COLLECT_{timestamp}_{safe_title}.txt"
                        file_path = self.integrator.rumor_data_dir / filename
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        logger.info(f"✅ 自动沉淀新知识: {filename}")
                        count += 1
                
                self.processed_topics.add(topic)
                # 限制一次任务处理的数量，避免过度消耗 Token
                if count >= 5:
                    break
                    
            except Exception as e:
                logger.error(f"处理话题 '{topic}' 时出错: {e}")
                continue
        
        if count > 0:
            logger.info(f"本次任务共沉淀 {count} 条新知识，触发向量库重构...")
            self.integrator.rebuild_knowledge_base()
        else:
            logger.info("本次任务未发现需要沉淀的新知识。")

    def start_background_loop(self):
        """启动后台循环任务"""
        if self._running:
            return
            
        self._running = True
        def loop():
            while self._running:
                try:
                    # 检查是否在闲时（例如凌晨 1-5 点，或者根据配置）
                    # 这里为了演示，我们根据 config 中的间隔执行
                    self.collect_once()
                except Exception as e:
                    logger.error(f"自动收集循环出错: {e}")
                
                # 等待配置的时间间隔
                interval = getattr(config, 'AUTO_COLLECT_INTERVAL', 3600 * 12) # 默认 12 小时
                logger.info(f"等待下次自动收集 ({interval}秒后)...")
                time.sleep(interval)
        
        self._thread = threading.Thread(target=loop, name="RumorCollectorThread")
        self._thread.daemon = True
        self._thread.start()
        logger.info("自动谣言收集后台线程已启动。")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

if __name__ == "__main__":
    # 简单的独立测试
    collector = RumorCollector()
    collector.collect_once()
