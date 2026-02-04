# -*- coding: utf-8 -*-
"""路径验证测试"""
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
print("项目路径验证测试")
print("=" * 60)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
print(f"\n[1] 项目根目录: {PROJECT_ROOT}")

# 关键目录验证
paths_to_check = {
    "数据目录": PROJECT_ROOT / "data" / "rumors",
    "存储目录": PROJECT_ROOT / "storage",
    "向量数据库": PROJECT_ROOT / "storage" / "vector_db",
    "缓存目录": PROJECT_ROOT / "storage" / "cache",
    "语义缓存": PROJECT_ROOT / "storage" / "semantic_cache",
    "源代码": PROJECT_ROOT / "src",
    "核心模块": PROJECT_ROOT / "src" / "core",
    "检索模块": PROJECT_ROOT / "src" / "retrievers",
    "分析模块": PROJECT_ROOT / "src" / "analyzers",
    "知识模块": PROJECT_ROOT / "src" / "knowledge",
    "服务模块": PROJECT_ROOT / "src" / "services",
    "测试目录": PROJECT_ROOT / "tests",
    "脚本目录": PROJECT_ROOT / "scripts",
    "文档目录": PROJECT_ROOT / "docs",
    "部署目录": PROJECT_ROOT / "deployment",
}

all_exist = True
for name, path in paths_to_check.items():
    exists = path.exists()
    status = "[OK]" if exists else "[MISSING]"
    print(f"{status} {name}: {path}")
    if not exists and "rumors" not in name:  # rumors 可能是空的，但其他目录应该存在
        all_exist = False

print("\n" + "=" * 60)
if all_exist:
    print("所有关键目录验证通过！")
else:
    print("部分目录缺失，请检查。")
print("=" * 60)

# 模块导入测试
print("\n[模块导入测试]")
try:
    from src.core.pipeline import RumorJudgeEngine
    print("[OK] RumorJudgeEngine 导入成功")
except Exception as e:
    print(f"[FAIL] RumorJudgeEngine 导入失败: {e}")

try:
    from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
    kb = EvidenceKnowledgeBase()
    print(f"[OK] EvidenceKnowledgeBase 导入成功")
    print(f"     - 数据目录: {kb.data_dir}")
    print(f"     - 向量库目录: {kb.persist_dir}")
except Exception as e:
    print(f"[FAIL] EvidenceKnowledgeBase 导入失败: {e}")

try:
    from src.core.cache_manager import CacheManager
    print(f"[OK] CacheManager 导入成功")
except Exception as e:
    print(f"[FAIL] CacheManager 导入失败: {e}")

print("\n测试完成！")
