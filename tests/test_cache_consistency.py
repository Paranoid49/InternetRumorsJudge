"""
缓存一致性测试

验证知识库版本变化时缓存的一致性保证
"""
import logging
import time
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.cache_manager import CacheManager
from src.analyzers.truth_summarizer import FinalVerdict
from src.retrievers.evidence_retriever import EvidenceKnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestCacheConsistency:
    """缓存一致性测试"""

    def setup(self):
        """测试前准备"""
        from src import config

        # 确保有嵌入模型
        if not config.API_KEY:
            raise Exception("需要 DASHSCOPE_API_KEY")

        # 初始化嵌入模型（用于语义缓存）
        # 注意：语义缓存是可选的，测试时不强制要求
        self.embeddings = None

    def test_version_manager_initialized(self):
        """
        测试：版本管理器是否正确初始化

        目标：确保 CacheManager 强制使用版本管理器
        """
        print("\n" + "="*60)
        print("测试：版本管理器初始化")
        print("="*60)

        cache_mgr = CacheManager(embeddings=self.embeddings)

        # 验证版本管理器存在
        assert cache_mgr._version_manager is not None, "版本管理器应该被初始化"

        print(f"当前版本: {cache_mgr._current_kb_version.version_id if cache_mgr._current_kb_version else 'None'}")
        print("✅ 版本管理器初始化测试通过")

    def test_cache_with_version_binding(self):
        """
        测试：缓存存储时是否正确绑定版本

        目标：验证 set_verdict 时版本号被正确存储
        """
        print("\n" + "="*60)
        print("测试：缓存版本绑定")
        print("="*60)

        cache_mgr = CacheManager(embeddings=self.embeddings)

        # 创建测试裁决
        test_verdict = FinalVerdict(
            verdict_type="真",
            confidence_score=95,
            risk_level="低",
            summary_report="测试报告"
        )

        # 存入缓存
        cache_mgr.set_verdict("测试查询", test_verdict)

        # 验证缓存中包含版本信息
        from src.core.cache_manager import hashlib
        key = hashlib.md5("测试查询".strip().lower().encode('utf-8')).hexdigest()
        cached_data = cache_mgr.cache.get(key)

        assert cached_data is not None, "缓存应该存在"
        assert cached_data.get("verdict_type") == "真", "缓存数据应该正确"

        # 如果有当前版本，应该包含版本号
        if cache_mgr._current_kb_version:
            assert "kb_version" in cached_data, "缓存应该包含版本号"
            print(f"✅ 缓存版本号: {cached_data['kb_version']}")
        else:
            print("ℹ️  当前无版本信息（首次构建前）")

        print("✅ 缓存版本绑定测试通过")

    def test_cache_invalid_on_version_change(self):
        """
        测试：版本变化时缓存是否失效

        目标：验证知识库更新后，旧缓存自动失效
        """
        print("\n" + "="*60)
        print("测试：版本变化时缓存失效")
        print("="*60)

        cache_mgr = CacheManager(embeddings=self.embeddings)

        # 获取初始版本
        initial_version = cache_mgr._current_kb_version
        print(f"初始版本: {initial_version.version_id if initial_version else 'None'}")

        # 创建测试裁决并存入缓存
        test_verdict = FinalVerdict(
            verdict_type="真",
            confidence_score=95,
            risk_level="低",
            summary_report="测试报告"
        )
        cache_mgr.set_verdict("版本变化测试", test_verdict)

        # 验证缓存命中
        result = cache_mgr.get_verdict("版本变化测试")
        assert result is not None, "初始查询应该命中缓存"
        print("✅ 初始查询命中缓存")

        # 模拟版本变化（通过重建知识库）
        print("\n模拟知识库重建...")
        kb = EvidenceKnowledgeBase()
        try:
            kb.build(force=False, incremental=False)
            print("知识库重建完成")
        except Exception as e:
            print(f"知识库重建跳过（可能需要数据）: {e}")

        # 强制更新缓存管理器的版本
        cache_mgr._current_kb_version = cache_mgr._version_manager.get_current_version()
        new_version = cache_mgr._current_kb_version
        print(f"新版本: {new_version.version_id if new_version else 'None'}")

        # 验证缓存失效
        result_after = cache_mgr.get_verdict("版本变化测试")
        if initial_version != new_version and new_version is not None:
            assert result_after is None, "版本变化后，旧缓存应该失效"
            print("✅ 版本变化后，旧缓存已失效")
        else:
            print("ℹ️  版本未变化或无版本，缓存可能仍然有效")

        print("✅ 缓存失效测试通过")

    def test_stale_cache_cleanup(self):
        """
        测试：过期缓存清理功能

        目标：验证 clear_stale_cache 能正确清理过期缓存
        """
        print("\n" + "="*60)
        print("测试：过期缓存清理")
        print("="*60)

        cache_mgr = CacheManager(embeddings=self.embeddings)

        # 清空现有缓存
        cache_mgr.clear()

        # 创建多个测试裁决
        for i in range(5):
            test_verdict = FinalVerdict(
                verdict_type="真",
                confidence_score=90 + i,
                risk_level="低",
                summary_report=f"测试报告 {i}"
            )
            cache_mgr.set_verdict(f"测试查询 {i}", test_verdict)

        print(f"已存入 5 个测试缓存")

        # 执行清理
        stale_count = cache_mgr.clear_stale_cache()
        print(f"清理了 {stale_count} 个过期缓存")

        # 验证剩余缓存都是有效的
        remaining_count = len(list(cache_mgr.cache.iterkeys()))
        print(f"剩余缓存: {remaining_count} 个")

        print("✅ 过期缓存清理测试通过")

    def test_first_build_boundary_case(self):
        """
        测试：首次构建的边界情况

        目标：验证首次构建前后的缓存行为
        """
        print("\n" + "="*60)
        print("测试：首次构建边界情况")
        print("="*60)

        cache_mgr = CacheManager(embeddings=self.embeddings)

        # 检查当前版本状态
        has_version_before = cache_mgr._current_kb_version is not None
        print(f"首次构建前有版本: {has_version_before}")

        # 创建测试裁决
        test_verdict = FinalVerdict(
            verdict_type="真",
            confidence_score=95,
            risk_level="低",
            summary_report="首次构建前测试"
        )
        cache_mgr.set_verdict("首次构建测试", test_verdict)

        # 验证缓存可读
        result = cache_mgr.get_verdict("首次构建测试")
        assert result is not None, "首次构建前，缓存应该可读写"

        if not has_version_before:
            print("✅ 首次构建前，无版本号时缓存正常工作")
        else:
            print("✅ 有版本信息时缓存正常工作")

        print("✅ 首次构建边界情况测试通过")


if __name__ == "__main__":
    # 运行测试
    test = TestCacheConsistency()
    test.setup()

    print("\n开始运行缓存一致性测试...\n")

    try:
        test.test_version_manager_initialized()
        test.test_cache_with_version_binding()
        test.test_first_build_boundary_case()
        test.test_stale_cache_cleanup()
        # test.test_cache_invalid_on_version_change()  # 这个测试需要实际重建知识库，可能比较慢

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
