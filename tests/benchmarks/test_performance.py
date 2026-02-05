"""
系统性能基准测试

测试不同场景下的响应时间，给出量化结果
"""
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import RumorJudgeEngine

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PerformanceBenchmark")


class PerformanceBenchmark:
    """性能基准测试"""

    def __init__(self):
        self.engine = RumorJudgeEngine()
        self.results = []

    def test_cache_hit_exact(self, query: str, iterations: int = 5) -> Dict:
        """
        场景1: 精确缓存命中

        预期响应时间: < 5ms
        """
        print(f"\n[场景1] 精确缓存命中测试 ({iterations}次迭代)")
        print(f"查询: {query}")

        times = []
        for i in range(iterations):
            start = time.time()
            result = self.engine.run(query, use_cache=True)
            duration = (time.time() - start) * 1000  # 转换为毫秒
            times.append(duration)

            # 第一次可能未命中缓存，从第二次开始统计
            if i == 0:
                print(f"  第1次查询: {duration:.2f}ms (缓存未命中: {result.is_cached})")
            else:
                print(f"  第{i+1}次查询: {duration:.2f}ms (缓存: {result.is_cached})")

        # 排除第一次（可能未命中缓存）
        cache_hits = [t for i, t in enumerate(times) if i > 0]

        return {
            "scenario": "精确缓存命中",
            "query": query,
            "iterations": len(cache_hits),
            "min_ms": round(min(cache_hits), 2),
            "max_ms": round(max(cache_hits), 2),
            "avg_ms": round(sum(cache_hits) / len(cache_hits), 2),
            "median_ms": round(sorted(cache_hits)[len(cache_hits)//2], 2),
            "p95_ms": round(sorted(cache_hits)[int(len(cache_hits)*0.95)], 2),
            "p99_ms": round(sorted(cache_hits)[int(len(cache_hits)*0.99)], 2),
            "times": cache_hits
        }

    def test_cache_hit_semantic(self, query: str, iterations: int = 5) -> Dict:
        """
        场景2: 语义缓存命中

        预期响应时间: < 50ms
        """
        print(f"\n[场景2] 语义缓存命中测试 ({iterations}次迭代)")
        print(f"查询: {query}")

        # 首先查询相似的问题建立缓存
        similar_query = query.replace("？", "").replace("吗", "").strip() + "是真的吗"
        print(f"  预先查询相似问题: {similar_query}")
        self.engine.run(similar_query, use_cache=True)
        time.sleep(0.5)

        times = []
        for i in range(iterations):
            start = time.time()
            result = self.engine.run(query, use_cache=True)
            duration = (time.time() - start) * 1000
            times.append(duration)
            print(f"  第{i+1}次查询: {duration:.2f}ms (缓存: {result.is_cached})")

        return {
            "scenario": "语义缓存命中",
            "query": query,
            "iterations": iterations,
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "avg_ms": round(sum(times) / len(times), 2),
            "median_ms": round(sorted(times)[len(times)//2], 2),
            "p95_ms": round(sorted(times)[int(len(times)*0.95)], 2),
            "p99_ms": round(sorted(times)[int(len(times)*0.99)], 2),
            "times": times
        }

    def test_local_rag_only(self, query: str, iterations: int = 3) -> Dict:
        """
        场景3: 本地RAG（无网络搜索）

        预期响应时间: 5-8秒
        """
        print(f"\n[场景3] 本地RAG测试 ({iterations}次迭代)")
        print(f"查询: {query}")

        times = []
        for i in range(iterations):
            start = time.time()
            result = self.engine.run(query, use_cache=False)  # 禁用缓存
            duration = time.time() - start
            times.append(duration)

            web_search = "是" if result.is_web_search else "否"
            print(f"  第{i+1}次查询: {duration:.2f}s (联网: {web_search}, 证据: {len(result.retrieved_evidence)}条)")

        return {
            "scenario": "本地RAG",
            "query": query,
            "iterations": iterations,
            "min_s": round(min(times), 2),
            "max_s": round(max(times), 2),
            "avg_s": round(sum(times) / len(times), 2),
            "median_s": round(sorted(times)[len(times)//2], 2),
            "p95_s": round(sorted(times)[int(len(times)*0.95)], 2),
            "p99_s": round(sorted(times)[int(len(times)*0.99)], 2),
            "times": times
        }

    def test_full_pipeline(self, query: str, iterations: int = 2) -> Dict:
        """
        场景4: 完整流程（包含网络搜索）

        预期响应时间: 20-30秒
        """
        print(f"\n[场景4] 完整流程测试（含网络搜索）({iterations}次迭代)")
        print(f"查询: {query}")

        times = []
        for i in range(iterations):
            start = time.time()
            result = self.engine.run(query, use_cache=False)
            duration = time.time() - start
            times.append(duration)

            web_search = "是" if result.is_web_search else "否"
            print(f"  第{i+1}次查询: {duration:.2f}s (联网: {web_search}, 裁决: {result.final_verdict})")

        return {
            "scenario": "完整流程",
            "query": query,
            "iterations": iterations,
            "min_s": round(min(times), 2),
            "max_s": round(max(times), 2),
            "avg_s": round(sum(times) / len(times), 2),
            "median_s": round(sorted(times)[len(times)//2], 2),
            "p95_s": round(sorted(times)[int(len(times)*0.95)], 2),
            "p99_s": round(sorted(times)[int(len(times)*0.99)], 2),
            "times": times
        }

    def test_batch_queries(self, queries: List[str]) -> Dict:
        """
        场景5: 批量查询（模拟并发场景）

        测试系统在连续多个查询下的性能表现
        """
        print(f"\n[场景5] 批量查询测试 ({len(queries)}个查询)")

        start_all = time.time()
        individual_times = []

        for i, query in enumerate(queries):
            start = time.time()
            result = self.engine.run(query, use_cache=True)  # 允许缓存
            duration = time.time() - start
            individual_times.append(duration)

            cached = "[缓存]" if result.is_cached else "[实时]"
            print(f"  查询{i+1}: {duration:.2f}s {cached} - {result.final_verdict}")

        total_time = time.time() - start_all

        return {
            "scenario": "批量查询",
            "total_queries": len(queries),
            "total_time_s": round(total_time, 2),
            "avg_time_s": round(sum(individual_times) / len(individual_times), 2),
            "min_s": round(min(individual_times), 2),
            "max_s": round(max(individual_times), 2),
            "cache_hit_rate": round(sum(1 for i, q in enumerate(queries) if i > 0 and individual_times[i] < 1) / (len(queries) - 1), 2),
            "individual_times": individual_times
        }

    def run_all_benchmarks(self) -> Dict:
        """运行所有基准测试"""
        print("="*70)
        print("系统性能基准测试")
        print("="*70)
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 测试查询
        test_queries = {
            "cache_exact": "维生素C能预防感冒吗？",
            "cache_semantic": "吃维生素C会致癌吗",
            "local_rag": "喝隔夜水会致癌吗",  # 本地库有此内容
            "full_pipeline": "2025年地球会毁灭吗",  # 需要联网搜索
            "batch": [
                "维生素C能预防感冒吗？",
                "喝隔夜水会致癌吗",
                "吃洋葱能治感冒吗",
                "手机辐射会导致脑癌吗",
                "吸烟有害健康吗"
            ]
        }

        results = {}

        # 场景1: 精确缓存命中
        results["cache_exact"] = self.test_cache_hit_exact(
            test_queries["cache_exact"],
            iterations=5
        )

        # 场景2: 语义缓存命中
        results["cache_semantic"] = self.test_cache_hit_semantic(
            test_queries["cache_semantic"],
            iterations=5
        )

        # 场景3: 本地RAG
        results["local_rag"] = self.test_local_rag_only(
            test_queries["local_rag"],
            iterations=3
        )

        # 场景4: 完整流程
        results["full_pipeline"] = self.test_full_pipeline(
            test_queries["full_pipeline"],
            iterations=2
        )

        # 场景5: 批量查询
        results["batch"] = self.test_batch_queries(test_queries["batch"])

        # 生成报告
        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "python_version": sys.version,
                "platform": sys.platform
            },
            "benchmarks": results
        }

    def print_report(self, report: Dict):
        """打印性能测试报告"""
        print("\n" + "="*70)
        print("性能测试报告")
        print("="*70)

        benchmarks = report["benchmarks"]

        for key, data in benchmarks.items():
            print(f"\n【{data['scenario']}】")
            print(f"  测试查询: {data.get('query', 'N/A')}")

            if 'avg_ms' in data:  # 毫秒级结果
                print(f"  迭代次数: {data['iterations']}")
                print(f"  平均响应: {data['avg_ms']} ms")
                print(f"  中位数: {data['median_ms']} ms")
                print(f"  最小值: {data['min_ms']} ms")
                print(f"  最大值: {data['max_ms']} ms")
                print(f"  P95: {data['p95_ms']} ms")
                print(f"  P99: {data['p99_ms']} ms")
            elif 'avg_s' in data:  # 秒级结果
                print(f"  迭代次数: {data['iterations']}")
                print(f"  平均响应: {data['avg_s']} s")
                print(f"  中位数: {data['median_s']} s")
                print(f"  最小值: {data['min_s']} s")
                print(f"  最大值: {data['max_s']} s")
                print(f"  P95: {data['p95_s']} s")
                print(f"  P99: {data['p99_s']} s")
            elif 'avg_time_s' in data:  # 批量查询
                print(f"  查询数量: {data['total_queries']}")
                print(f"  总耗时: {data['total_time_s']} s")
                print(f"  平均耗时: {data['avg_time_s']} s")
                print(f"  缓存命中率: {data['cache_hit_rate']*100:.1f}%")

        # 总结
        print("\n" + "="*70)
        print("关键性能指标总结")
        print("="*70)

        cache_exact = benchmarks["cache_exact"]["avg_ms"]
        local_rag = benchmarks["local_rag"]["avg_s"]
        full_pipeline = benchmarks["full_pipeline"]["avg_s"]

        print(f"✅ 精确缓存响应: {cache_exact} ms (目标: < 5ms)")
        print(f"✅ 本地RAG响应: {local_rag} s (目标: < 8s)")
        print(f"✅ 完整流程响应: {full_pipeline} s (目标: < 30s)")
        print(f"✅ 批量查询缓存命中率: {benchmarks['batch']['cache_hit_rate']*100:.1f}%")

        # 性能评级
        if cache_exact < 5:
            print(f"\n🏆 性能评级: 优秀 (缓存响应极快)")
        elif cache_exact < 50:
            print(f"\n🥈 性能评级: 良好 (缓存响应正常)")
        else:
            print(f"\n⚠️  性能评级: 需优化 (缓存响应偏慢)")

    def save_report(self, report: Dict):
        """保存性能测试报告"""
        report_file = Path(__file__).parent.parent / "performance_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n报告已保存至: {report_file}")


def main():
    """主函数"""
    try:
        benchmark = PerformanceBenchmark()
        report = benchmark.run_all_benchmarks()
        benchmark.print_report(report)
        benchmark.save_report(report)
        return 0
    except Exception as e:
        logger.error(f"性能测试失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
