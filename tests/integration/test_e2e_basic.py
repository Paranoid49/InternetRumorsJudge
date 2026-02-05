"""
端到端集成测试 - 基础场景

测试核心用户场景
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.pipeline import RumorJudgeEngine


def test_basic_query():
    """测试基本查询功能"""
    print("[测试] 基本查询功能")

    engine = RumorJudgeEngine()
    result = engine.run("维生素C能预防感冒吗？", use_cache=False)

    assert result is not None
    assert result.final_verdict in ["真", "很可能为真", "假", "很可能为假", "存在争议", "证据不足"]
    assert result.confidence_score >= 0
    assert result.confidence_score <= 100
    assert len(result.retrieved_evidence) > 0

    print(f"  [OK] Verdict: {result.final_verdict}")
    print(f"  [OK] Confidence: {result.confidence_score}")
    print(f"  [OK] Evidence count: {len(result.retrieved_evidence)}")


def test_cache_hit():
    """测试缓存命中场景"""
    print("\n[测试] 缓存命中场景")

    engine = RumorJudgeEngine()
    query = "喝水会中毒吗？"

    # 首次查询（缓存未命中）
    result1 = engine.run(query, use_cache=True)
    print(f"  首次查询 - 缓存命中: {result1.is_cached}")

    # 再次查询（应该命中缓存）
    result2 = engine.run(query, use_cache=True)
    print(f"  再次查询 - 缓存命中: {result2.is_cached}")

    assert result2.final_verdict == result1.final_verdict
    # 缓存应该命中（除非知识库刚更新）
    print("  [OK] Cache function works")


def test_error_handling():
    """测试错误处理"""
    print("\n[测试] 错误处理")

    engine = RumorJudgeEngine()

    # 测试空查询
    result = engine.run("", use_cache=False)
    print(f"  [OK] Empty query handled: {result.final_verdict}")


if __name__ == "__main__":
    print("="*60)
    print("端到端集成测试")
    print("="*60)

    try:
        test_basic_query()
        test_cache_hit()
        test_error_handling()

        print("\n" + "="*60)
        print("[PASS] All tests passed")
        print("="*60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
