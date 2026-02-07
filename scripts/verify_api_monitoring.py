"""
API 监控验证脚本

验证 API 监控是否正常工作：
1. LLM 调用是否被记录
2. Embedding 调用是否被记录
3. Web 搜索调用是否被记录
4. 成本计算是否正确

版本：v1.0.1
"""
import sys
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.observability.api_monitor import get_api_monitor, QuotaConfig
from src.analyzers.query_parser import QueryParser
from src.utils.batch_embedder import BatchEmbedder
from src.retrievers.evidence_retriever import EvidenceKnowledgeBase

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("VerifyAPIMonitoring")


def verify_llm_monitoring():
    """验证 LLM 调用监控"""
    logger.info("\n" + "="*60)
    logger.info("测试 1: LLM 调用监控")
    logger.info("="*60)

    # 获取监控器
    monitor = get_api_monitor()

    # 记录初始状态
    initial_summary = monitor.get_daily_summary()
    logger.info(f"初始状态: {initial_summary['total_calls']} 次调用, {initial_summary['total_cost']} 元")

    # 执行 LLM 调用
    parser = QueryParser()
    result = parser.parse("维生素C可以预防感冒吗？")

    if result:
        logger.info(f"解析成功: {result.entity} - {result.claim}")

    # 检查监控记录
    final_summary = monitor.get_daily_summary()
    logger.info(f"最终状态: {final_summary['total_calls']} 次调用, {final_summary['total_cost']:.6f} 元")

    # 验证
    new_calls = final_summary['total_calls'] - initial_summary['total_calls']
    new_cost = final_summary['total_cost'] - initial_summary['total_cost']

    if new_calls > 0 and new_cost > 0:
        logger.info(f"✅ LLM 调用监控正常: +{new_calls} 次调用, +{new_cost:.6f} 元")
        return True
    else:
        logger.warning(f"⚠️ LLM 调用监控可能未工作: +{new_calls} 次调用, +{new_cost:.6f} 元")
        return False


def verify_embedding_monitoring():
    """验证 Embedding 调用监控"""
    logger.info("\n" + "="*60)
    logger.info("测试 2: Embedding 调用监控")
    logger.info("="*60)

    monitor = get_api_monitor()
    initial_summary = monitor.get_daily_summary()
    logger.info(f"初始状态: {initial_summary['total_calls']} 次调用")

    # 执行 Embedding 调用
    kb = EvidenceKnowledgeBase()
    test_texts = ["测试文本1", "测试文本2", "测试文本3"]
    embeddings = kb.embedder.embed_texts(test_texts, use_cache=False)

    logger.info(f"生成了 {len(embeddings)} 个 Embedding")

    # 检查监控记录
    final_summary = monitor.get_daily_summary()
    logger.info(f"最终状态: {final_summary['total_calls']} 次调用")

    new_calls = final_summary['total_calls'] - initial_summary['total_calls']

    if new_calls > 0:
        logger.info(f"✅ Embedding 调用监控正常: +{new_calls} 次调用")
        return True
    else:
        logger.warning(f"⚠️ Embedding 调用监控可能未工作: +{new_calls} 次调用")
        return False


def verify_report_generation():
    """验证报告生成"""
    logger.info("\n" + "="*60)
    logger.info("测试 3: 报告生成")
    logger.info("="*60)

    monitor = get_api_monitor()
    report = monitor.generate_report(days=1)

    print("\n" + report)

    if "API使用监控报告" in report:
        logger.info("✅ 报告生成正常")
        return True
    else:
        logger.warning("⚠️ 报告生成异常")
        return False


def verify_quota_alert():
    """验证配额告警"""
    logger.info("\n" + "="*60)
    logger.info("测试 4: 配额告警")
    logger.info("="*60)

    # 创建一个极小的配额配置用于测试
    test_quota = QuotaConfig(
        daily_budget=0.001,  # 0.001 元
        daily_token_limit=1000,
        alert_threshold=0.5
    )

    monitor = get_api_monitor(quota_config=test_quota)

    # 执行一些 LLM 调用触发告警
    parser = QueryParser()
    parser.parse("测试查询")

    # 检查是否触发告警
    if monitor._has_alerted:
        logger.info("✅ 配额告警功能正常（已触发告警）")
        return True
    else:
        logger.info("⚠️ 配额告警未触发（可能成本未达到阈值）")
        return False


def main():
    """主函数"""
    logger.info("\n" + "="*60)
    logger.info("API 监控验证测试")
    logger.info("版本: v1.0.1")
    logger.info("="*60)

    results = []

    # 运行测试
    try:
        results.append(("LLM 监控", verify_llm_monitoring()))
    except Exception as e:
        logger.error(f"LLM 监控测试失败: {e}")
        results.append(("LLM 监控", False))

    try:
        results.append(("Embedding 监控", verify_embedding_monitoring()))
    except Exception as e:
        logger.error(f"Embedding 监控测试失败: {e}")
        results.append(("Embedding 监控", False))

    try:
        results.append(("报告生成", verify_report_generation()))
    except Exception as e:
        logger.error(f"报告生成测试失败: {e}")
        results.append(("报告生成", False))

    try:
        results.append(("配额告警", verify_quota_alert()))
    except Exception as e:
        logger.error(f"配额告警测试失败: {e}")
        results.append(("配额告警", False))

    # 汇总结果
    logger.info("\n" + "="*60)
    logger.info("测试结果汇总")
    logger.info("="*60)

    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {name}")
        if result:
            passed += 1

    logger.info(f"\n通过率: {passed}/{len(results)} ({passed/len(results)*100:.1f}%)")

    # 生成最终报告
    logger.info("\n" + "="*60)
    logger.info("最终监控报告")
    logger.info("="*60)

    monitor = get_api_monitor()
    final_report = monitor.generate_report(days=1)
    print("\n" + final_report)

    return passed == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
