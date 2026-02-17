import json
import logging
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# [v1.2.0] 统一日志配置
try:
    from src.observability.logger_config import configure_logging, get_logger
    configure_logging()
    logger = get_logger("FeedbackAnalyzer")
except ImportError:
    # 回退到标准 logging（独立运行时）
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("FeedbackAnalyzer")

class FeedbackAnalyzer:
    def __init__(self, feedback_file: str = "user_feedback.jsonl"):
        self.feedback_file = Path(feedback_file)
        self.raw_data = []
        self.clean_df = pd.DataFrame()
        self.spam_data = []
        
        # Simple spam patterns
        self.spam_patterns = [
            r'^[a-zA-Z]+$', # Only letters (risky, but valid for nonsense like "asdf")
            r'(\w)\1{3,}', # Repeated characters like "aaaaa"
            r'^[0-9]+$', # Only numbers
        ]
        
    def load_feedback(self) -> int:
        """Load feedback from JSONL file."""
        if not self.feedback_file.exists():
            logger.warning(f"Feedback file {self.feedback_file} not found.")
            return 0
            
        count = 0
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            self.raw_data.append(entry)
                            count += 1
                        except json.JSONDecodeError:
                            logger.warning(f"Skipping invalid JSON line: {line[:50]}...")
        except Exception as e:
            logger.error(f"Error reading feedback file: {e}")
            
        logger.info(f"Loaded {count} raw feedback entries.")
        return count

    def is_spam(self, comment: str) -> bool:
        """Check if a comment looks like spam."""
        if not comment:
            return False 
            
        comment = comment.strip()
        if len(comment) < 2: return True
        
        for pattern in self.spam_patterns:
            if re.search(pattern, comment): return True
                
        if len(comment) > 5:
            unique_ratio = len(set(comment)) / len(comment)
            if unique_ratio < 0.2: return True
                
        return False

    def process_data(self):
        """Filter data and convert to DataFrame for analysis."""
        seen = set()
        clean_entries = []
        self.spam_data = []
        
        for entry in self.raw_data:
            # 1. Deduplication
            sig = (entry.get('query'), entry.get('rating'), entry.get('comment'))
            if sig in seen: continue
            seen.add(sig)
            
            # 2. Spam Filtering
            comment = entry.get('comment', "")
            if comment and self.is_spam(comment):
                entry['filter_reason'] = "Spam comment"
                self.spam_data.append(entry)
                continue
            
            # 3. Standardize Fields for Analysis
            # Map rating text to helpful boolean/score for calculation
            rating = entry.get('rating')
            is_helpful = True if rating == "有用" else False
            
            clean_entries.append({
                "timestamp": entry.get("timestamp"),
                "query": entry.get("query"),
                "rating": rating,
                "is_helpful": is_helpful,
                "comment": comment
            })
            
        self.clean_df = pd.DataFrame(clean_entries)
        logger.info(f"Processing complete. Clean DataFrame shape: {self.clean_df.shape}")

    def generate_report(self):
        """Generate analysis report (Inspired by user's implementation)."""
        if self.clean_df.empty:
            print("⚠️ 没有有效数据可分析")
            return

        total = len(self.clean_df)
        helpful_count = self.clean_df[self.clean_df['is_helpful']].shape[0]
        helpful_rate = helpful_count / total

        print("\n" + "=" * 50)
        print("📊 用户反馈分析报告 (Feedback Analysis Report)")
        print("=" * 50)
        print(f"总有效反馈数: {total}")
        print(f"被拦截垃圾/重复数据: {len(self.raw_data) - total}")
        print(f"认为有用 (Positive): {helpful_count} ({helpful_rate:.1%})")
        print(f"认为无用/错误 (Negative): {total - helpful_count} ({(1 - helpful_rate):.1%})")
        
        # Analysis of negative feedback
        neg_df = self.clean_df[~self.clean_df['is_helpful']]
        if not neg_df.empty:
            print(f"\n❌ 重点关注案例 (Top 5):")
            for _, row in neg_df.head(5).iterrows():
                print(f"  - 查询: {row['query']}")
                print(f"    评价: {row['rating']}")
                if row['comment']:
                    print(f"    反馈: {row['comment']}")
                print("    ---")

        # Save summary stats
        stats = {
            "total": total,
            "helpful_rate": helpful_rate,
            "generated_at": datetime.now().isoformat()
        }
        with open("feedback_stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

    def generate_datasets(self, output_dir: str = "optimization_data"):
        """Generate training datasets with priority tagging."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        if self.clean_df.empty: return

        # 1. Positive Samples (Reinforcement)
        pos_df = self.clean_df[self.clean_df['is_helpful']]
        pos_data = pos_df[['query', 'comment']].to_dict('records')
        
        # 2. Negative Samples (Correction) with Priority
        neg_df = self.clean_df[~self.clean_df['is_helpful']].copy()
        
        def get_priority(row):
            comment = str(row['comment'])
            if "错误" in comment or "误导" in comment: return "high"
            if not comment: return "low"
            return "medium"
            
        neg_df['priority'] = neg_df.apply(get_priority, axis=1)
        neg_data = neg_df[['query', 'rating', 'comment', 'priority']].to_dict('records')

        # Save
        date_str = datetime.now().strftime('%Y%m%d')
        pos_file = output_path / f"positive_samples_{date_str}.json"
        neg_file = output_path / f"negative_feedback_{date_str}.json"
        
        with open(pos_file, 'w', encoding='utf-8') as f:
            json.dump(pos_data, f, ensure_ascii=False, indent=2)
            
        with open(neg_file, 'w', encoding='utf-8') as f:
            json.dump(neg_data, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 数据集已生成:")
        print(f"  - 正样本 ({len(pos_data)}): {pos_file}")
        print(f"  - 负样本 ({len(neg_data)}): {neg_file}")

if __name__ == "__main__":
    analyzer = FeedbackAnalyzer()
    if analyzer.load_feedback() > 0:
        analyzer.process_data()
        analyzer.generate_report()
        analyzer.generate_datasets()
    else:
        print("未找到反馈数据，请先在Web界面提交一些反馈。")
