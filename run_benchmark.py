import json
import time
import logging
from typing import List, Dict
from pipeline import RumorJudgeEngine

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Benchmark")

class BenchmarkRunner:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.engine = RumorJudgeEngine()
        self.results = []

    def load_dataset(self) -> List[Dict]:
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run(self):
        dataset = self.load_dataset()
        total = len(dataset)
        correct = 0
        total_time = 0

        print(f"\n🚀 开始执行自动化回归测试 (共 {total} 条)...")
        print("-" * 60)

        for i, item in enumerate(dataset, 1):
            query = item["query"]
            expected = item["expected_verdict"]
            
            print(f"[{i}/{total}] 正在核查: {query}")
            
            start_time = time.time()
            try:
                # 运行核查引擎 (关闭缓存以测试真实性能)
                res = self.engine.run(query, use_cache=False)
                duration = time.time() - start_time
                total_time += duration
                
                actual = res.final_verdict
                is_correct = (actual == expected)
                if is_correct:
                    correct += 1
                
                status_icon = "✅" if is_correct else "❌"
                print(f"   结果: {actual} (预期: {expected}) {status_icon} | 耗时: {duration:.2f}s")
                
                self.results.append({
                    "query": query,
                    "expected": expected,
                    "actual": actual,
                    "correct": is_correct,
                    "time": duration,
                    "confidence": res.confidence_score
                })
            except Exception as e:
                print(f"   ❌ 出错: {e}")
                self.results.append({
                    "query": query,
                    "expected": expected,
                    "actual": "ERROR",
                    "correct": False,
                    "time": 0,
                    "error": str(e)
                })

        # 计算统计数据
        accuracy = (correct / total) * 100 if total > 0 else 0
        avg_time = (total_time / total) if total > 0 else 0

        print("-" * 60)
        print(f"📊 测试完成报告:")
        print(f"   总计数量: {total}")
        print(f"   准确率: {accuracy:.1f}%")
        print(f"   平均耗时: {avg_time:.2f}s")
        print(f"   总耗时: {total_time:.2f}s")
        print("-" * 60)

        # 保存结果到文件
        self.save_report()

    def save_report(self):
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": len(self.results),
                "correct": sum(1 for r in self.results if r.get("correct")),
                "accuracy": f"{(sum(1 for r in self.results if r.get('correct')) / len(self.results)) * 100:.1f}%",
                "avg_time": f"{(sum(r.get('time', 0) for r in self.results) / len(self.results)):.2f}s"
            },
            "details": self.results
        }
        
        report_file = "benchmark_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📝 详细报告已保存至: {report_file}")

if __name__ == "__main__":
    runner = BenchmarkRunner("benchmark_dataset.json")
    runner.run()
