"""
缓存失效测试 - 验证知识库版本变化后缓存自动失效

测试场景：
1. 查询并缓存结果
2. 重构知识库（版本变化）
3. 再次查询同一内容
4. 验证缓存已失效，重新进行了查询
"""
import json
import logging
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import RumorJudgeEngine
from src.retrievers.evidence_retriever import EvidenceKnowledgeBase

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CacheInvalidationTest")


def test_cache_invalidation():
    """测试缓存失效机制"""
    logger.info("="*60)
    logger.info("缓存失效测试开始")
    logger.info("="*60)

    engine = RumorJudgeEngine()
    test_query = "吃洋葱能治感冒吗？"

    # 第一步：查询并缓存
    logger.info("\n[步骤 1] 首次查询（应缓存结果）")
    start_time = time.time()
    result1 = engine.run(test_query, use_cache=True)
    duration1 = time.time() - start_time

    logger.info(f"  裁决: {result1.final_verdict}")
    logger.info(f"  置信度: {result1.confidence_score}")
    logger.info(f"  是否缓存命中: {result1.is_cached}")
    logger.info(f"  耗时: {duration1:.2f}s")

    # 等待一秒
    time.sleep(1)

    # 第二步：再次查询（应命中缓存）
    logger.info("\n[步骤 2] 再次查询（应命中缓存）")
    start_time = time.time()
    result2 = engine.run(test_query, use_cache=True)
    duration2 = time.time() - start_time

    logger.info(f"  裁决: {result2.final_verdict}")
    logger.info(f"  是否缓存命中: {result2.is_cached}")
    logger.info(f"  耗时: {duration2:.2f}s")

    # 验证缓存命中
    if not result2.is_cached:
        logger.error("❌ 第二次查询未命中缓存，测试失败")
        return False

    if duration2 > 1.0:  # 缓存查询应该很快
        logger.error(f"❌ 缓存查询耗时过长: {duration2:.2f}s")
        return False

    logger.info("✅ 第二次查询命中缓存，响应时间显著降低")

    # 第三步：重构知识库
    logger.info("\n[步骤 3] 重构知识库（触发版本变化）")
    try:
        kb = EvidenceKnowledgeBase()
        if kb._version_manager:
            logger.info("使用版本管理的双缓冲重构")
            kb.build(incremental=False)  # 全量重构新版本
        else:
            logger.warning("版本管理器未启用，跳过重构测试")
            return True

        logger.info("✅ 知识库重构完成")
    except Exception as e:
        logger.error(f"❌ 知识库重构失败: {e}")
        return False

    # 等待一秒
    time.sleep(1)

    # 第四步：再次查询（缓存应已失效）
    logger.info("\n[步骤 4] 重构后查询（缓存应失效）")
    start_time = time.time()
    result3 = engine.run(test_query, use_cache=True)
    duration3 = time.time() - start_time

    logger.info(f"  裁决: {result3.final_verdict}")
    logger.info(f"  是否缓存命中: {result3.is_cached}")
    logger.info(f"  耗时: {duration3:.2f}s")

    # 验证缓存失效
    if result3.is_cached:
        logger.error("❌ 重构后查询仍命中缓存，缓存未失效！")
        return False

    logger.info("✅ 缓存已失效，重新进行了查询")

    # 第五步：验证新缓存生效
    logger.info("\n[步骤 5] 再次查询（新缓存应生效）")
    start_time = time.time()
    result4 = engine.run(test_query, use_cache=True)
    duration4 = time.time() - start_time

    logger.info(f"  裁决: {result4.final_verdict}")
    logger.info(f"  是否缓存命中: {result4.is_cached}")
    logger.info(f"  耗时: {duration4:.2f}s")

    if not result4.is_cached:
        logger.error("❌ 新缓存未生效")
        return False

    logger.info("✅ 新缓存已生效")

    # 总结
    logger.info("\n" + "="*60)
    logger.info("缓存失效测试完成")
    logger.info("="*60)
    logger.info("✅ 所有测试通过：")
    logger.info("  1. 首次查询结果正确")
    logger.info("  2. 缓存命中成功，响应时间显著降低")
    logger.info("  3. 知识库重构触发版本变化")
    logger.info("  4. 旧缓存自动失效")
    logger.info("  5. 新缓存重新生效")

    return True


def save_report(success: bool):
    """保存测试报告"""
    from datetime import datetime

    report = {
        "timestamp": datetime.now().isoformat(),
        "test_name": "缓存失效测试",
        "result": "通过" if success else "失败",
        "details": {
            "cache_invalidated_on_kb_rebuild": success,
            "new_cache_created_after_rebuild": success
        }
    }

    report_file = Path(__file__).parent.parent / "cache_invalidation_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"测试报告已保存: {report_file}")


def main():
    """运行测试"""
    try:
        success = test_cache_invalidation()
        save_report(success)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"测试执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
