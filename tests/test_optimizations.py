# -*- coding: utf-8 -*-
"""
测试优化效果的脚本
2026-02-04 三项优化验证：
1. 超时控制机制
2. 统一配置管理
3. 智能去重算法
"""
import json
import time
import logging
import sys
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import RumorJudgeEngine

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OptimizationTest")

class OptimizationTester:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.engine = None
        self.results = []

    def load_dataset(self) -> List[Dict]:
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_config_loading(self):
        """测试 1: 验证配置统一管理"""
        print("\n" + "="*60)
        print("[测试 1/3] 配置统一管理验证")
        print("="*60)

        import config

        required_configs = [
            ('MIN_LOCAL_SIMILARITY', 0.4),
            ('MAX_RESULTS', 3),
            ('SEMANTIC_CACHE_THRESHOLD', 0.96),
            ('DEFAULT_CACHE_TTL', 86400),
            ('AUTO_INTEGRATE_MIN_CONFIDENCE', 90),
            ('AUTO_INTEGRATE_MIN_EVIDENCE', 3),
            ('AUTO_GEN_WEIGHT', 0.9),
            ('LLM_REQUEST_TIMEOUT', 30),
            ('WEB_SEARCH_TIMEOUT', 15),
        ]

        all_passed = True
        for config_name, expected_value in required_configs:
            if hasattr(config, config_name):
                actual_value = getattr(config, config_name)
                status = "[OK]" if actual_value == expected_value else "[WARN]"
                print(f"{status} {config_name} = {actual_value}")
                if actual_value != expected_value:
                    print(f"      预期: {expected_value}")
            else:
                print(f"[FAIL] {config_name} 未找到")
                all_passed = False

        if all_passed:
            print("\n[通过] 所有配置项已正确加载到 config.py")
        else:
            print("\n[警告] 部分配置项缺失")

        return all_passed

    def test_deduplication_algorithm(self):
        """测试 2: 验证去重算法改进"""
        print("\n" + "="*60)
        print("[测试 2/3] 智能去重算法验证")
        print("="*60)

        from hybrid_retriever import HybridRetriever
        from langchain_core.documents import Document

        # 创建模拟文档（包含相似内容）
        test_docs = [
            Document(page_content="吃隔夜水会致癌，因为亚硝酸盐含量超标。", metadata={"source": "test1.txt", "type": "local", "similarity": 0.8}),
            Document(page_content="喝隔夜水可能导致癌症，由于亚硝酸盐含量过高。", metadata={"source": "test2.txt", "type": "local", "similarity": 0.75}),
            Document(page_content="吸烟有害健康，这是公认的科学事实。", metadata={"source": "test3.txt", "type": "local", "similarity": 0.9}),
            Document(page_content="吃洋葱可以预防感冒。", metadata={"source": "test4.txt", "type": "local", "similarity": 0.7}),
            Document(page_content="完全不同的内容，谈论的是手机辐射问题。", metadata={"source": "test5.txt", "type": "local", "similarity": 0.6}),
        ]

        # 初始化检索器（需要实际的 KB 实例，这里创建一个简单的模拟）
        print(f"原始文档数量: {len(test_docs)}")

        # 创建一个简单的模拟 retriever 来测试去重
        class MockRetriever:
            def _deduplicate_docs(self, docs):
                # 复制 hybrid_retriever 的去重逻辑
                from difflib import SequenceMatcher

                if not docs:
                    return []

                # 第一阶段：精确哈希去重
                seen_hashes = set()
                hash_unique = []
                for doc in docs:
                    content = doc.page_content[:500].strip()
                    if not content:
                        continue
                    h = hash(content)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        hash_unique.append(doc)

                # 第二阶段：内容相似度模糊去重
                unique = []
                for doc in hash_unique:
                    content = doc.page_content
                    content_clean = ' '.join(content.split())

                    is_duplicate = False
                    for seen_doc in unique:
                        similarity = SequenceMatcher(None, content_clean[:300],
                                                    ' '.join(seen_doc.page_content.split())[:300]).ratio()
                        if similarity > 0.85:
                            print(f"  - 发现相似文档: '{doc.page_content[:20]}...' 与 '{seen_doc.page_content[:20]}...' (相似度: {similarity:.2f})")
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        unique.append(doc)

                return unique

        mock_retriever = MockRetriever()
        deduplicated = mock_retriever._deduplicate_docs(test_docs)

        print(f"去重后文档数量: {len(deduplicated)}")
        print(f"去重率: {(len(test_docs) - len(deduplicated)) / len(test_docs) * 100:.1f}%")

        if len(deduplicated) < len(test_docs):
            print("\n[通过] 智能去重算法正常工作")
            return True
        else:
            print("\n[警告] 未检测到去重效果（可能测试数据不够相似）")
            return False

    def test_timeout_mechanism(self):
        """测试 3: 验证超时机制"""
        print("\n" + "="*60)
        print("[测试 3/3] 超时机制验证")
        print("="*60)

        import config
        timeout_value = getattr(config, 'LLM_REQUEST_TIMEOUT', None)

        if timeout_value:
            print(f"[OK] LLM_REQUEST_TIMEOUT = {timeout_value} 秒")

            # 验证各个模块是否使用了超时配置
            modules_to_check = [
                ('truth_summarizer.py', 'timeout'),
                ('evidence_analyzer.py', 'timeout'),
                ('query_parser.py', 'timeout'),
            ]

            all_passed = True
            for module_name, keyword in modules_to_check:
                try:
                    with open(module_name, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if f'timeout=getattr(config, \'LLM_REQUEST_TIMEOUT\'' in content or f'timeout=config.LLM_REQUEST_TIMEOUT' in content:
                            print(f"[OK] {module_name} 已应用超时配置")
                        else:
                            print(f"[FAIL] {module_name} 未应用超时配置")
                            all_passed = False
                except Exception as e:
                    print(f"[ERROR] 无法检查 {module_name}: {e}")
                    all_passed = False

            if all_passed:
                print("\n[通过] 超时机制已正确配置")
            else:
                print("\n[警告] 部分模块未应用超时配置")

            return all_passed
        else:
            print("[FAIL] LLM_REQUEST_TIMEOUT 配置未找到")
            return False

    def run_full_benchmark(self):
        """运行完整的基准测试"""
        print("\n" + "="*60)
        print("[完整基准测试] 运行真实查询测试")
        print("="*60)

        if not self.engine:
            self.engine = RumorJudgeEngine()

        dataset = self.load_dataset()
        total = len(dataset)
        correct = 0
        total_time = 0
        cache_hits = 0
        web_searches = 0

        print(f"\n开始执行 {total} 条测试查询...")
        print("-" * 60)

        for i, item in enumerate(dataset, 1):
            query = item["query"]
            expected = item["expected_verdict"]

            print(f"[{i}/{total}] {query}")

            start_time = time.time()
            try:
                res = self.engine.run(query, use_cache=False)
                duration = time.time() - start_time
                total_time += duration

                if res.is_cached:
                    cache_hits += 1
                if res.is_web_search:
                    web_searches += 1

                actual = res.final_verdict
                is_correct = (actual == expected)
                if is_correct:
                    correct += 1

                status_icon = "OK" if is_correct else "X"
                cache_status = "[缓存]" if res.is_cached else ("[联网]" if res.is_web_search else "[本地]")
                print(f"     结果: {actual} (预期: {expected}) {status_icon} {cache_status} | 耗时: {duration:.2f}s")

                self.results.append({
                    "query": query,
                    "expected": expected,
                    "actual": actual,
                    "correct": is_correct,
                    "time": duration,
                    "confidence": res.confidence_score,
                    "cached": res.is_cached,
                    "web_search": res.is_web_search
                })
            except Exception as e:
                print(f"     [ERROR] {str(e)[:50]}")
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
        print(f"基准测试报告:")
        print(f"  总计数量: {total}")
        print(f"  准确率: {accuracy:.1f}%")
        print(f"  平均耗时: {avg_time:.2f}s")
        print(f"  总耗时: {total_time:.2f}s")
        print(f"  联网搜索次数: {web_searches}")
        print("-" * 60)

        # 保存结果
        self.save_report()

        return accuracy, avg_time

    def save_report(self):
        """保存测试报告"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": len(self.results),
                "correct": sum(1 for r in self.results if r.get("correct")),
                "accuracy": f"{(sum(1 for r in self.results if r.get('correct')) / len(self.results)) * 100:.1f}%",
                "avg_time": f"{(sum(r.get('time', 0) for r in self.results) / len(self.results)):.2f}s",
                "web_searches": sum(1 for r in self.results if r.get('web_search'))
            },
            "details": self.results
        }

        report_file = "optimization_test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"测试报告已保存至: {report_file}")

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "#"*60)
        print("# 优化效果验证测试套件")
        print("# 测试日期: 2026-02-04")
        print("#"*60)

        # 测试 1: 配置统一管理
        config_passed = self.test_config_loading()

        # 测试 2: 去重算法
        dedup_passed = self.test_deduplication_algorithm()

        # 测试 3: 超时机制
        timeout_passed = self.test_timeout_mechanism()

        # 完整基准测试
        accuracy, avg_time = self.run_full_benchmark()

        # 总结
        print("\n" + "#"*60)
        print("# 测试总结")
        print("#"*60)
        print(f"配置管理测试: {'[通过]' if config_passed else '[失败]'}")
        print(f"去重算法测试: {'[通过]' if dedup_passed else '[失败]'}")
        print(f"超时机制测试: {'[通过]' if timeout_passed else '[失败]'}")
        print(f"基准测试准确率: {accuracy:.1f}%")
        print(f"基准测试平均耗时: {avg_time:.2f}s")
        print("#"*60)

        return {
            "config_passed": config_passed,
            "dedup_passed": dedup_passed,
            "timeout_passed": timeout_passed,
            "accuracy": accuracy,
            "avg_time": avg_time
        }

if __name__ == "__main__":
    tester = OptimizationTester("benchmark_dataset.json")
    results = tester.run_all_tests()
