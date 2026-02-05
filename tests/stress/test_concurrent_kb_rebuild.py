"""
并发重构测试 - 验证双缓冲策略不会阻塞查询

测试场景：
1. 启动多个并发查询线程
2. 在查询进行时触发知识库重构
3. 验证查询不会被重构阻塞
"""
import json
import logging
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.pipeline import RumorJudgeEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ConcurrentRebuildTest")


class ConcurrentRebuildTester:
    """并发重构测试器"""

    def __init__(self):
        self.engine = RumorJudgeEngine()
        self.query_times = []
        self.errors = []
        self.lock = threading.Lock()

    def test_query(self, query_id: int, query: str) -> dict:
        """执行单个查询"""
        start_time = time.time()
        thread_name = threading.current_thread().name

        try:
            logger.info(f"[Query-{query_id}] 开始: {query}")
            result = self.engine.run(query, use_cache=False)

            duration = time.time() - start_time

            with self.lock:
                self.query_times.append({
                    "query_id": query_id,
                    "thread": thread_name,
                    "duration": duration,
                    "success": True,
                    "verdict": result.final_verdict if result else None
                })

            logger.info(f"[Query-{query_id}] 完成: {duration:.2f}s, 裁决: {result.final_verdict if result else 'N/A'}")
            return {"success": True, "duration": duration}

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            with self.lock:
                self.errors.append({
                    "query_id": query_id,
                    "thread": thread_name,
                    "error": error_msg,
                    "duration": duration
                })

            logger.error(f"[Query-{query_id}] 失败: {error_msg}")
            return {"success": False, "error": error_msg, "duration": duration}

    def test_kb_rebuild(self) -> bool:
        """触发知识库重构"""
        thread_name = threading.current_thread().name
        logger.info(f"[Rebuild] 开始重构知识库")

        try:
            from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
            kb = EvidenceKnowledgeBase()

            # 触发重构（使用双缓冲策略）
            start_time = time.time()
            kb.build(incremental=False)  # 全量重构
            duration = time.time() - start_time

            logger.info(f"[Rebuild] 完成: {duration:.2f}s")
            return True

        except Exception as e:
            logger.error(f"[Rebuild] 失败: {e}", exc_info=True)
            return False

    def run_concurrent_test(
        self,
        num_queries: int = 20,
        num_rebuilds: int = 2,
        query_delay: float = 0.5
    ) -> dict:
        """
        运行并发测试

        Args:
            num_queries: 总查询数
            num_rebuilds: 重构次数
            query_delay: 查询间隔（秒）

        Returns:
            测试结果统计
        """
        logger.info("="*60)
        logger.info("并发重构测试开始")
        logger.info(f"配置: {num_queries} 个查询, {num_rebuilds} 次重构")
        logger.info("="*60)

        # 测试查询集
        test_queries = [
            "吃洋葱能治感冒吗？",
            "喝隔夜水会致癌吗？",
            "手机辐射会导致脑癌吗？",
            "维生素C能预防感冒吗？",
            "吃鸡蛋会升高胆固醇吗？"
        ]

        start_time = time.time()
        results = {
            "total_queries": num_queries,
            "successful_queries": 0,
            "failed_queries": 0,
            "rebuilds_completed": 0,
            "query_times": [],
            "errors": [],
            "max_query_duration": 0,
            "avg_query_duration": 0,
            "blocked_queries": 0  # 被重构阻塞的查询（耗时 > 10s）
        }

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # 提交查询任务
            for i in range(num_queries):
                query = test_queries[i % len(test_queries)]
                future = executor.submit(self.test_query, i, query)
                futures.append(("query", i, future))

                # 每隔几个查询触发一次重构
                if (i + 1) % (num_queries // num_rebuilds) == 0 and i > 0:
                    time.sleep(query_delay)  # 让一些查询先运行
                    rebuild_future = executor.submit(self.test_kb_rebuild)
                    futures.append(("rebuild", i, rebuild_future))
                    logger.info(f"在第 {i} 个查询后触发重构")

            # 收集结果
            for task_type, task_id, future in as_completed(futures):
                try:
                    result = future.result()

                    if task_type == "query":
                        if result["success"]:
                            results["successful_queries"] += 1
                            results["query_times"].append(result["duration"])

                            # 检查是否被阻塞（耗时过长）
                            if result["duration"] > 10:
                                results["blocked_queries"] += 1
                                logger.warning(f"Query-{task_id} 可能被阻塞: {result['duration']:.2f}s")
                        else:
                            results["failed_queries"] += 1
                            results["errors"].append(result.get("error", "Unknown error"))

                    elif task_type == "rebuild":
                        if result:
                            results["rebuilds_completed"] += 1

                except Exception as e:
                    logger.error(f"任务执行异常: {e}")
                    results["errors"].append(str(e))

        # 计算统计数据
        total_duration = time.time() - start_time

        if results["query_times"]:
            results["max_query_duration"] = max(results["query_times"])
            results["avg_query_duration"] = sum(results["query_times"]) / len(results["query_times"])

        results["total_duration"] = total_duration

        # 打印结果
        logger.info("="*60)
        logger.info("并发重构测试完成")
        logger.info(f"总耗时: {total_duration:.2f}s")
        logger.info(f"成功查询: {results['successful_queries']}/{num_queries}")
        logger.info(f"失败查询: {results['failed_queries']}/{num_queries}")
        logger.info(f"完成重构: {results['rebuilds_completed']}/{num_rebuilds}")
        logger.info(f"平均查询耗时: {results['avg_query_duration']:.2f}s")
        logger.info(f"最长查询耗时: {results['max_query_duration']:.2f}s")
        logger.info(f"可能被阻塞的查询: {results['blocked_queries']}")
        logger.info("="*60)

        # 判断测试是否通过
        test_passed = (
            results["failed_queries"] == 0 and
            results["rebuilds_completed"] == num_rebuilds and
            results["blocked_queries"] == 0
        )

        if test_passed:
            logger.info("✅ 测试通过：双缓冲策略有效，查询未被重构阻塞")
        else:
            logger.error("❌ 测试失败：检测到问题")

            if results["blocked_queries"] > 0:
                logger.error(f"  - 有 {results['blocked_queries']} 个查询可能被重构阻塞")
            if results["failed_queries"] > 0:
                logger.error(f"  - 有 {results['failed_queries']} 个查询失败")
            if results["rebuilds_completed"] < num_rebuilds:
                logger.error(f"  - 有 {num_rebuilds - results['rebuilds_completed']} 个重构任务失败")

        return results

    def save_report(self, results: dict):
        """保存测试报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_name": "并发重构测试（双缓冲策略验证）",
            "results": results,
            "conclusion": "通过" if results["blocked_queries"] == 0 and results["failed_queries"] == 0 else "失败"
        }

        report_file = Path(__file__).parent.parent / "stress" / "concurrent_rebuild_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"测试报告已保存: {report_file}")


def main():
    """运行测试"""
    tester = ConcurrentRebuildTester()

    # 运行测试
    results = tester.run_concurrent_test(
        num_queries=20,
        num_rebuilds=2,
        query_delay=0.5
    )

    # 保存报告
    tester.save_report(results)

    # 返回退出码
    if results["blocked_queries"] == 0 and results["failed_queries"] == 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
