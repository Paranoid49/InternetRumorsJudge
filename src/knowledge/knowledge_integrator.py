import json
import logging
import time
from pathlib import Path
from datetime import datetime

# 设置项目路径（v0.9.0: 使用统一路径工具）
from src.utils.path_utils import setup_project_path, get_project_root
setup_project_path()

from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
from src import config
from src.utils.llm_factory import create_dashscope_llm
from langchain_core.messages import HumanMessage, SystemMessage

# 延迟导入版本管理器（避免循环导入）
def _get_version_manager():
    from src.core.version_manager import VersionManager
    return VersionManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KnowledgeIntegrator")

# 获取项目根目录（v0.9.0: 使用统一路径工具）
PROJECT_ROOT = get_project_root()

class KnowledgeIntegrator:
    def __init__(self,
                 reviewed_data_path: str = None,
                 rumor_data_dir: str = None,
                 model_name: str = "qwen3-max"):
        # 默认路径使用项目根目录
        if reviewed_data_path is None:
            reviewed_data_path = str(PROJECT_ROOT / "data" / "reviewed" / "valid_corrections.json")
        if rumor_data_dir is None:
            rumor_data_dir = str(PROJECT_ROOT / "data" / "rumors")

        self.reviewed_data_path = Path(reviewed_data_path)
        self.rumor_data_dir = Path(rumor_data_dir)
        self.rumor_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用统一的 LLM 工厂（v0.9.0）
        self.llm = create_dashscope_llm(
            model_name=model_name,
            temperature=0.7
        )

    def generate_knowledge_content(self, query: str, comment: str) -> str:
        """Use LLM to generate structured rumor knowledge file content."""
        prompt = f"""
你是一位专业的事实核查员和数据整理专家。
请根据【用户查询（传言）】和【用户反馈（纠正）】，生成一份结构化的辟谣知识档案。
你需要利用你的通用知识来验证事实，如果用户反馈比较简略，请补充相关细节。

用户查询：{query}
用户反馈/纠正：{comment}

输出格式（请严格遵守此模板）：
标题：【辟谣】关于“<Title>”的真实情况
分类：<Category>
真实性：<True/False/Controversial>
发布日期：<YYYY-MM-DD>
数据编号：AUTO-<Timestamp>
来源：<Source, e.g. User Report, General Knowledge>
标签：<Tag1>, <Tag2>

【谣言内容】
<完整的传言陈述>

【真相核查】
<详细的事实核查解释>

【关键事实】
• <事实点 1>
• <事实点 2>
• <事实点 3>

【结论】
<结论陈述>

要求：
1. 确保内容准确客观。
2. “真实性”字段应根据事实确定（对于谣言通常为“False”或“假”）。
3. 所有内容请使用中文。
4. 不要输出 Markdown 代码块，仅输出纯文本内容。
"""
        try:
            messages = [
                SystemMessage(content="你是一个帮助生成结构化辟谣数据的助手。"),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return None

    def process_valid_feedback(self):
        """Process valid feedback and generate knowledge files."""
        if not self.reviewed_data_path.exists():
            logger.warning(f"No valid corrections file found at {self.reviewed_data_path}")
            return

        with open(self.reviewed_data_path, 'r', encoding='utf-8') as f:
            items = json.load(f)

        processed_count = 0
        new_items = []
        
        # Check if items already have 'integrated_at' field
        pending_items = [item for item in items if not item.get('integrated_at')]
        
        if not pending_items:
            logger.info("No new items to integrate.")
            return

        print(f"🚀 Found {len(pending_items)} items to integrate...")

        for item in pending_items:
            query = item['query']
            comment = item['comment']
            
            logger.info(f"Processing: {query}")
            
            content = self.generate_knowledge_content(query, comment)
            if content:
                # Generate filename
                timestamp = int(time.time())
                safe_title = "".join([c for c in query if c.isalnum()])[:20]
                filename = f"AUTO_{timestamp}_{safe_title}.txt"
                file_path = self.rumor_data_dir / filename
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                logger.info(f"✅ Generated knowledge file: {filename}")
                
                item['integrated_at'] = datetime.now().isoformat()
                item['generated_file'] = filename
                processed_count += 1
            else:
                logger.error(f"❌ Failed to generate content for: {query}")

            new_items.append(item)

        # Update the JSON file with processed status
        # We need to preserve the items that were already processed (not in pending_items)
        # But wait, 'items' loaded from file contains ALL items.
        # We iterated over 'pending_items' which are references to objects inside 'items' list (if generic python list behavior holds for json objects)
        # Yes, dictionaries are mutable.
        # So 'items' should be updated.
        
        with open(self.reviewed_data_path, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        if processed_count > 0:
            print(f"🎉 Successfully generated {processed_count} new knowledge files.")
            self.rebuild_knowledge_base()
        else:
            print("⚠️ No files generated.")

    def rebuild_knowledge_base(self):
        """
        Rebuild the vector knowledge base using double-buffering strategy.

        新版本在后台构建，不会阻塞并发查询。构建完成后原子性切换。
        使用强制全量重建，确保新知识立即生效。
        """
        print("🔄 Rebuilding Knowledge Base (using double-buffering strategy)...")
        logger.info("开始重构知识库（双缓冲策略，线程安全）")

        try:
            kb = EvidenceKnowledgeBase()

            # 验证版本管理器可用（强制要求）
            if not kb._version_manager:
                raise RuntimeError("❌ 版本管理器未初始化 - 无法保证线程安全")

            # 使用版本管理的双缓冲构建（force=False，仍然使用双缓冲）
            logger.info("使用版本管理的双缓冲构建，不会阻塞并发查询")
            kb.build(force=False, incremental=False)  # 全量重建新版本（双缓冲）
            print("✅ Knowledge Base rebuilt successfully with versioning!")

        except Exception as e:
            logger.error(f"Failed to rebuild Knowledge Base: {e}", exc_info=True)
            print(f"❌ Failed to rebuild Knowledge Base: {e}")

if __name__ == "__main__":
    integrator = KnowledgeIntegrator()
    integrator.process_valid_feedback()
