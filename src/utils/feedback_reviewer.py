import json
import logging
from pathlib import Path
from datetime import datetime
import glob
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s') # Simplified format for CLI interaction
logger = logging.getLogger("FeedbackReviewer")

class FeedbackReviewer:
    def __init__(self, data_dir: str = "optimization_data", output_dir: str = "reviewed_data"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def get_latest_negative_file(self):
        """Find the most recent negative feedback file."""
        files = glob.glob(str(self.data_dir / "negative_feedback_*.json"))
        if not files:
            return None
        return max(files, key=os.path.getctime)

    def load_reviewed_ids(self, file_path):
        """Load already reviewed items to avoid duplication."""
        if not file_path.exists():
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Create a unique signature for each reviewed item
            return set(f"{d['query']}_{d['comment']}" for d in data)

    def review_loop(self):
        """Interactive CLI loop for reviewing feedback."""
        input_file = self.get_latest_negative_file()
        if not input_file:
            print("❌ 未找到待审核的负面反馈文件 (optimization_data/negative_feedback_*.json)")
            return

        print(f"📂 正在加载文件: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            items = json.load(f)

        valid_file = self.output_dir / "valid_corrections.json"
        invalid_file = self.output_dir / "invalid_complaints.json"

        # Load existing progress
        reviewed_sigs = self.load_reviewed_ids(valid_file) | self.load_reviewed_ids(invalid_file)
        
        valid_items = []
        if valid_file.exists():
            with open(valid_file, 'r', encoding='utf-8') as f: valid_items = json.load(f)
            
        invalid_items = []
        if invalid_file.exists():
            with open(invalid_file, 'r', encoding='utf-8') as f: invalid_items = json.load(f)

        print(f"📊 总计: {len(items)} 条 | 已审核: {len(reviewed_sigs)} 条 | 待审核: {len(items) - len(reviewed_sigs)} 条")
        print("-" * 50)
        print("⌨️  操作指南: [y] 有效问题 [n] 无效/误报 [s] 跳过 [q] 退出")
        print("-" * 50)

        newly_reviewed_count = 0

        for i, item in enumerate(items):
            sig = f"{item['query']}_{item['comment']}"
            if sig in reviewed_sigs:
                continue

            print(f"\n📝 案例 #{i+1}")
            print(f"🔹 用户查询: {item['query']}")
            print(f"🔹 用户反馈: {item['comment']}")
            print(f"🔹 优先级: {item.get('priority', 'medium')}")
            
            while True:
                choice = input("👉 这是一个有效的问题反馈吗? (y/n/s/q): ").lower().strip()
                
                if choice == 'q':
                    print("👋 退出审核")
                    self._check_integration(newly_reviewed_count)
                    return
                
                if choice == 's':
                    print("⏭️  跳过")
                    break
                    
                if choice == 'n':
                    reason = input("   (可选) 为什么无效? (直接回车跳过): ")
                    item['rejection_reason'] = reason
                    item['reviewed_at'] = datetime.now().isoformat()
                    invalid_items.append(item)
                    self.save_json(invalid_file, invalid_items)
                    print("❌ 已标记为无效")
                    newly_reviewed_count += 1
                    break
                    
                if choice == 'y':
                    print("   🔍 问题类型:")
                    print("   1. 知识缺失 (Knowledge Missing)")
                    print("   2. 推理错误 (Reasoning Error)")
                    print("   3. 态度/语气问题 (Tone/Style)")
                    print("   4. 其他 (Other)")
                    cat_map = {'1': 'knowledge_missing', '2': 'reasoning_error', '3': 'tone_issue', '4': 'other'}
                    cat = input("   选择类型 (1-4): ").strip()
                    
                    item['issue_type'] = cat_map.get(cat, 'other')
                    item['reviewed_at'] = datetime.now().isoformat()
                    valid_items.append(item)
                    self.save_json(valid_file, valid_items)
                    print("✅ 已标记为有效修正项")
                    newly_reviewed_count += 1
                    break

        print("\n🎉 所有待审核项目已处理完毕！")
        self._check_integration(newly_reviewed_count)

    def _check_integration(self, count):
        if count > 0:
            print("\n" + "="*50)
            print("🚀 自动化集成建议")
            print("="*50)
            choice = input("是否立即运行自动化集成(生成新知识并重建向量库)? (y/n): ").lower().strip()
            if choice == 'y':
                import subprocess
                print("正在启动 knowledge_integrator.py ...")
                subprocess.run(["python", "knowledge_integrator.py"])
            else:
                print("已跳过。你可以稍后运行 'python knowledge_integrator.py' 手动集成。")

    def save_json(self, path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    reviewer = FeedbackReviewer()
    reviewer.review_loop()
