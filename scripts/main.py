import sys
import logging
from pathlib import Path
from typing import Optional

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config
from src.core.pipeline import RumorJudgeEngine, UnifiedVerificationResult, PipelineStage

# 设置日志级别，避免干扰输出
logging.getLogger("RumorJudgeEngine").setLevel(logging.WARNING)
logging.getLogger("EvidenceRetriever").setLevel(logging.WARNING)

def format_output(result: UnifiedVerificationResult):
    """格式化并打印核查结果"""
    print(f"\n🔍 正在分析: {result.query}")
    print("-" * 50)

    # 缓存命中提示
    if result.is_cached:
        print(f"⚡ [缓存命中] 发现已有核查结果，跳过分析流程。")
    
    # 解析结果
    if result.entity or result.claim:
        print("📊 [解析结果]")
        if result.entity:
            print(f"   实体: {result.entity}")
        if result.claim:
            print(f"   主张: {result.claim}")
        if result.category:
            print(f"   分类: {result.category}")

    # 检索结果 (如果不是缓存命中)
    if not result.is_cached and result.retrieved_evidence:
        search_query = f"{result.entity} {result.claim}" if result.entity and result.claim else result.query
        print(f"\n📚 [检索证据] (检索词: {search_query})")
        
        for res in result.retrieved_evidence:
            print(f"\n   📄 来源: {res.get('source', '未知')} (相似度: {res.get('similarity', 0):.4f})")
            print(f"      {res.get('text', '').strip()}")

    # 分析结果 (如果不是缓存命中)
    if not result.is_cached and result.evidence_assessments:
        print("\n🧠 [多角度分析]")
        for assessment in result.evidence_assessments:
            print(f"\n   🔬 证据 #{assessment.id} 分析:")
            print(f"      • 相关性: {assessment.relevance}")
            print(f"      • 立场: {assessment.stance}")
            
            if hasattr(assessment, 'complexity_label') and assessment.complexity_label != "无特殊情况":
                print(f"      • ⚠️ 复杂情况: {assessment.complexity_label}")
            
            if hasattr(assessment, 'confidence'):
                print(f"      • 🎯 置信度: {assessment.confidence:.2f}")
                
            print(f"      • 权威性: {assessment.authority_score}/5")
            print(f"      • 理由: {assessment.reason}")
            
            if hasattr(assessment, 'supporting_quote') and assessment.supporting_quote:
                print(f"      • 📝 引用: \"{assessment.supporting_quote}\"")

    # 最终结论
    if result.final_verdict:
        print("\n⚖️ [真相总结]")
        
        # 区分本地知识库验证和 LLM 兜底验证
        if result.is_fallback:
             print(f"   ⚠️ 警告: 未找到本地证据，以下结果基于 LLM 通用知识，仅供参考。")
        
        print(f"   📢 结论: {result.final_verdict} (置信度: {result.confidence_score}/100)")
        if result.risk_level:
            print(f"   ⚠️ 风险等级: {result.risk_level}")
        if result.summary_report:
            print(f"\n   📝 总结报告:\n   {result.summary_report}")
        
        # 修复 Bug 1: 只有真正保存到缓存时才提示
        if result.saved_to_cache:
             print(f"\n💾 [系统] 结果已缓存，下次查询将加速。")
             
    elif any(m.stage == PipelineStage.RETRIEVAL and not m.success for m in result.metadata):
         print(f"\n⚠️ 未找到相关证据，且兜底分析失败。")

    print("-" * 50)
    
    # 打印错误信息 (如果有)
    for meta in result.metadata:
        if not meta.success and meta.error_message:
             print(f"⚠️ {meta.stage} 阶段警告: {meta.error_message}")


def main():
    engine = RumorJudgeEngine()
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        result = engine.run(query)
        format_output(result)
        return
        
    print("🤖 谣言粉碎机 - 交互模式 (Engine Powered)")
    print("输入一句话进行解析和查证，直接回车退出。")
    
    while True:
        try:
            query = input("\n请输入要验证的陈述：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            break
        try:
            result = engine.run(query)
            format_output(result)
        except Exception as e:
            print(f"处理出错: {e}")
            print()

if __name__ == "__main__":
    main()
