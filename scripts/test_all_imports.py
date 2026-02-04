# -*- coding: utf-8 -*-
"""
完整导入测试 - 验证所有模块路径
"""
import sys
from pathlib import Path

# 设置控制台编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("完整模块导入测试")
print("=" * 60)

modules_to_test = [
    # 核心模块
    ("src.core.pipeline", "RumorJudgeEngine"),
    ("src.core.cache_manager", "CacheManager"),

    # 检索模块
    ("src.retrievers.evidence_retriever", "EvidenceKnowledgeBase"),
    ("src.retrievers.hybrid_retriever", "HybridRetriever"),
    ("src.retrievers.web_search_tool", "WebSearchTool"),

    # 分析模块
    ("src.analyzers.query_parser", "QueryAnalysis"),
    ("src.analyzers.evidence_analyzer", "EvidenceAnalyzer"),
    ("src.analyzers.truth_summarizer", "TruthSummarizer"),

    # 知识模块
    ("src.knowledge.knowledge_integrator", "KnowledgeIntegrator"),

    # 服务模块
    ("src.services.api_service", "app"),
    ("src.services.web_interface", None),

    # 配置
    ("src.config", None),
]

failed_imports = []
success_count = 0

for module_path, class_name in modules_to_test:
    try:
        if class_name:
            exec(f"from {module_path} import {class_name}")
            print(f"[OK] {module_path}.{class_name}")
        else:
            exec(f"import {module_path}")
            print(f"[OK] {module_path}")
        success_count += 1
    except Exception as e:
        print(f"[FAIL] {module_path}: {str(e)[:60]}")
        failed_imports.append((module_path, str(e)))

print("\n" + "=" * 60)
print(f"测试结果: {success_count}/{len(modules_to_test)} 成功")

if failed_imports:
    print("\n失败的导入:")
    for module, error in failed_imports:
        print(f"  - {module}: {error[:80]}")
else:
    print("\n所有模块导入成功！")

print("=" * 60)

# 测试实例化关键组件
print("\n[组件实例化测试]")
try:
    from src.core.pipeline import RumorJudgeEngine
    from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
    from src.core.cache_manager import CacheManager

    print("[OK] RumorJudgeEngine 类可访问")

    kb = EvidenceKnowledgeBase()
    print(f"[OK] EvidenceKnowledgeBase 实例化成功")
    print(f"     - 数据目录: {kb.data_dir}")
    print(f"     - 向量库目录: {kb.persist_dir}")

    cache_mgr = CacheManager()
    print(f"[OK] CacheManager 实例化成功")
    print(f"     - 缓存目录: {cache_mgr.cache.directory}")
    print(f"     - 语义缓存目录: {cache_mgr.vector_cache_dir}")

except Exception as e:
    print(f"[FAIL] 组件实例化失败: {e}")

print("\n测试完成！")
