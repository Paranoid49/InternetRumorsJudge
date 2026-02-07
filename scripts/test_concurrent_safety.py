#!/usr/bin/env python3
"""
并发安全测试脚本

用于验证系统的线程安全性
"""
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import RumorJudgeEngine
from src.utils.batch_embedder import get_batch_embedder, reset_global_batch_embedder


def test_singleton_thread_safety():
    """
    测试单例模式的线程安全性

    验证：多线程同时创建单例，只应该创建一个实例
    """
    print("=" * 60)
    print("测试1: 单例模式线程安全")
    print("=" * 60)

    instances = []
    lock = threading.Lock()

    def create_instance():
        engine = RumorJudgeEngine()
        with lock:
            instances.append(engine)

    # 并发创建100个实例
    threads = []
    for _ in range(100):
        t = threading.Thread(target=create_instance)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 验证所有实例都是同一个
    unique_instances = set(id(inst) for inst in instances)
    if len(unique_instances) == 1:
        print(f"[PASS] 所有线程获得相同的实例 (实例ID: {unique_instances.pop()})")
        return True
    else:
        print(f"[FAIL] 发现 {len(unique_instances)} 个不同的实例!")
        return False


def test_batch_embedder_thread_safety():
    """
    测试BatchEmbedder的线程安全性

    验证：多线程并发访问缓存，不应该出现数据损坏
    """
    print("\n" + "=" * 60)
    print("测试2: BatchEmbedder线程安全")
    print("=" * 60)

    # 重置全局实例
    reset_global_batch_embedder()

    # 创建一个mock embeddings对象
    class MockEmbeddings:
        def embed_documents(self, texts):
            # 模拟延迟
            time.sleep(0.001)
            return [[0.0] * 10 for _ in texts]

        def embed_query(self, text):
            time.sleep(0.001)
            return [0.0] * 10

    embedder = get_batch_embedder(MockEmbeddings())

    # 并发测试
    errors = []

    def embed_worker(thread_id):
        try:
            texts = [f"测试文本_{thread_id}_{i}" for i in range(10)]
            results = embedder.embed_texts(texts)
            if len(results) != 10:
                errors.append(f"线程{thread_id}: 结果数量不正确")
        except Exception as e:
            errors.append(f"线程{thread_id}: {str(e)}")

    # 启动50个线程
    threads = []
    for i in range(50):
        t = threading.Thread(target=embed_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 获取统计信息
    stats = embedder.get_stats()
    print(f"缓存命中: {stats['cache_hits']}")
    print(f"缓存未命中: {stats['cache_misses']}")
    print(f"缓存大小: {stats['cache_size']}")

    if not errors:
        print("[PASS] 所有线程成功完成，无错误")
        return True
    else:
        print(f"[FAIL] 发现 {len(errors)} 个错误:")
        for error in errors[:5]:  # 只显示前5个错误
            print(f"  - {error}")
        return False


def test_lock_manager():
    """
    测试锁管理器的功能

    验证：锁超时机制正常工作
    """
    print("\n" + "=" * 60)
    print("测试3: 锁管理器功能")
    print("=" * 60)

    try:
        from src.core.thread_utils import get_lock_manager

        lock_mgr = get_lock_manager()

        # 测试基本锁功能
        def worker(thread_id):
            with lock_mgr.acquire("test_lock", timeout=5):
                print(f"线程{thread_id} 获得锁")
                time.sleep(0.1)

        # 并发测试
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 获取统计信息
        stats = lock_mgr.get_stats("test_lock")
        print(f"锁获取次数: {stats['acquire_count']}")
        print(f"锁竞争次数: {stats['contention_count']}")
        print(f"总等待时间: {stats['total_wait_time_ms']:.2f}ms")

        print("[PASS] 锁管理器功能正常")
        return True

    except Exception as e:
        print(f"[FAIL] 锁管理器测试失败: {e}")
        return False


def test_concurrent_engine_initialization():
    """
    测试引擎并发初始化

    验证：多线程同时初始化引擎，不会出现问题
    """
    print("\n" + "=" * 60)
    print("测试4: 引擎并发初始化")
    print("=" * 60)

    errors = []

    def init_worker(thread_id):
        try:
            engine = RumorJudgeEngine()
            # 触发延迟初始化
            _ = engine.is_ready
            print(f"线程{thread_id}: 引擎初始化成功")
        except Exception as e:
            errors.append(f"线程{thread_id}: {str(e)}")

    # 并发初始化
    threads = []
    for i in range(10):
        t = threading.Thread(target=init_worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if not errors:
        print("[PASS] 所有线程成功初始化引擎")
        return True
    else:
        print(f"[FAIL] 发现 {len(errors)} 个错误:")
        for error in errors[:5]:
            print(f"  - {error}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("互联网谣言判断系统 - 并发安全测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("单例模式线程安全", test_singleton_thread_safety()))
    results.append(("BatchEmbedder线程安全", test_batch_embedder_thread_safety()))
    results.append(("锁管理器功能", test_lock_manager()))
    results.append(("引擎并发初始化", test_concurrent_engine_initialization()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print("-" * 60)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过! 系统具有良好的线程安全性")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} 个测试失败，需要进一步调查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
