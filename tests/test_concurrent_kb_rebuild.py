"""
并发知识库重构测试

验证在并发查询场景下，知识库重构不会导致查询失败
"""
import concurrent.futures
import logging
import pytest
import time
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.retrievers.evidence_retriever import EvidenceKnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestConcurrentKBRebuild:
    """并发知识库重构测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前准备"""
        self.data_dir = Path(__file__).parent.parent / "data" / "rumors"
        self.test_results = {"query_errors": 0, "query_success": 0}

    def test_concurrent_query_during_rebuild(self):
        """
        测试：在知识库重构期间进行并发查询

        目标：验证查询不会因为重构而失败
        """
        print("\n" + "="*60)
        print("测试：并发查询 + 知识库重构")
        print("="*60)

        kb = EvidenceKnowledgeBase()

        # 定义查询任务
        def query_task(task_id):
            """执行查询"""
            try:
                results = kb.search("测试查询", k=3)
                self.test_results["query_success"] += 1
                logger.info(f"Task {task_id}: 查询成功，返回 {len(results)} 条结果")
                return True
            except Exception as e:
                self.test_results["query_errors"] += 1
                logger.error(f"Task {task_id}: 查询失败 - {e}")
                return False

        # 定义重构任务
        def rebuild_task():
            """执行知识库重构"""
            try:
                logger.info("开始知识库重构...")
                kb.build(force=False, incremental=False)
                logger.info("知识库重构完成")
                return True
            except Exception as e:
                logger.error(f"知识库重构失败: {e}")
                return False

        # 并发执行：10个查询线程 + 1个重构线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=11) as executor:
            # 提交重构任务（延迟启动）
            rebuild_future = executor.submit(lambda: (time.sleep(0.5), rebuild_task())[1])

            # 提交查询任务
            query_futures = []
            for i in range(10):
                future = executor.submit(query_task, i)
                query_futures.append(future)
                time.sleep(0.1)  # 错开查询时间

            # 等待所有任务完成
            concurrent.futures.wait(query_futures + [rebuild_future])

        # 验证结果
        print("\n" + "="*60)
        print("测试结果")
        print("="*60)
        print(f"✅ 成功查询: {self.test_results['query_success']}")
        print(f"❌ 失败查询: {self.test_results['query_errors']}")
        print("="*60)

        # 断言：所有查询都应该成功（双缓冲策略保证）
        assert self.test_results["query_errors"] == 0, f"存在 {self.test_results['query_errors']} 个失败的查询"
        assert self.test_results["query_success"] > 0, "没有成功的查询"

    def test_rapid_consecutive_rebuilds(self):
        """
        测试：快速连续多次重构

        目标：验证版本管理器能够正确处理连续重构
        """
        print("\n" + "="*60)
        print("测试：快速连续重构")
        print("="*60)

        kb = EvidenceKnowledgeBase()

        # 执行3次连续重构
        for i in range(3):
            logger.info(f"第 {i+1} 次重构...")
            kb.build(force=False, incremental=False)
            time.sleep(0.5)  # 短暂间隔

        # 验证：最后一次重构后查询应该正常工作
        results = kb.search("测试查询", k=3)
        assert isinstance(results, list), "查询结果应该是列表"

        print("✅ 连续重构测试通过")

    def test_version_manager_initialized(self):
        """
        测试：版本管理器是否正确初始化

        目标：确保 EvidenceKnowledgeBase 使用版本管理器
        """
        print("\n" + "="*60)
        print("测试：版本管理器初始化")
        print("="*60)

        kb = EvidenceKnowledgeBase()

        # 验证版本管理器存在
        assert kb._version_manager is not None, "版本管理器应该被初始化"

        # 验证当前版本
        current_version = kb._version_manager.get_current_version()
        print(f"当前版本: {current_version.version_id if current_version else 'None'}")

        print("✅ 版本管理器初始化测试通过")


if __name__ == "__main__":
    # 运行测试
    test = TestConcurrentKBRebuild()
    test.setup()

    print("\n开始运行并发测试...\n")

    try:
        test.test_version_manager_initialized()
        test.test_rapid_consecutive_rebuilds()
        test.test_concurrent_query_during_rebuild()

        print("\n" + "="*60)
        print("🎉 所有测试通过！")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
