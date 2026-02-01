import json
from collections import Counter
import pandas as pd


class FeedbackAnalyzer:
    def __init__(self, feedback_file="user_feedback.json"):
        self.feedback_file = feedback_file

    def load_feedback(self):
        """加载反馈数据"""
        feedbacks = []
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        feedbacks.append(json.loads(line.strip()))
            print(f"📊 已加载 {len(feedbacks)} 条用户反馈")
            return feedbacks
        except FileNotFoundError:
            print("⚠️ 反馈文件不存在，将创建新文件")
            return []

    def analyze_feedback(self):
        """分析反馈数据"""
        feedbacks = self.load_feedback()
        if not feedbacks:
            return

        df = pd.DataFrame(feedbacks)

        # 基础统计
        helpful_rate = df['is_helpful'].mean() if 'is_helpful' in df.columns else 0
        total_count = len(df)

        print("\n" + "=" * 50)
        print("用户反馈分析报告")
        print("=" * 50)
        print(f"总反馈数: {total_count}")
        print(f"有帮助比例: {helpful_rate:.1%}")
        print(f"无帮助比例: {(1 - helpful_rate):.1%}")

        # 分析无帮助的反馈
        if not df.empty and 'is_helpful' in df.columns:
            not_helpful = df[df['is_helpful'] == False]
            if not not_helpful.empty:
                print(f"\n❌ 无帮助案例 ({len(not_helpful)} 条):")
                for _, row in not_helpful.head(5).iterrows():
                    print(f"  - 查询: {row.get('rumor', '')[:60]}...")
                    if row.get('feedback'):
                        print(f"    反馈: {row.get('feedback')}")

        # 保存分析结果
        analysis_result = {
            "total_feedbacks": total_count,
            "helpful_rate": helpful_rate,
            "sample_problems": not_helpful[['rumor', 'feedback']].to_dict('records') if not not_helpful.empty else []
        }

        with open("feedback_analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, ensure_ascii=False, indent=2)

        return analysis_result

    def generate_training_data(self):
        """从反馈中生成优化数据"""
        feedbacks = self.load_feedback()
        training_examples = []

        for fb in feedbacks:
            # 特别关注被标记为“无帮助”的案例
            if fb.get('is_helpful') is False:
                example = {
                    "problematic_query": fb.get('rumor', ''),
                    "user_feedback": fb.get('feedback', ''),
                    "suggested_improvement": "需要优化分析或检索逻辑",
                    "priority": "high" if "错误" in fb.get('feedback', '') else "medium"
                }
                training_examples.append(example)

        if training_examples:
            with open("training_data_from_feedback.json", "w", encoding="utf-8") as f:
                json.dump(training_examples, f, ensure_ascii=False, indent=2)
            print(f"✅ 已生成 {len(training_examples)} 条优化训练数据")

        return training_examples


if __name__ == "__main__":
    analyzer = FeedbackAnalyzer()
    analyzer.analyze_feedback()
    analyzer.generate_training_data()