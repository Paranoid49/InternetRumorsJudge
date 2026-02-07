#!/usr/bin/env python3
"""
依赖验证脚本
用于快速检查依赖是否正确安装
"""
import sys
import importlib
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 需要验证的核心依赖
REQUIRED_DEPENDENCIES = {
    'langchain_core': 'LangChain核心',
    'langchain': 'LangChain',
    'langchain_openai': 'LangChain OpenAI集成',
    'langchain_community': 'LangChain社区',
    'langchain_chroma': 'LangChain Chroma集成',
    'langchain_text_splitters': 'LangChain文本切分',
    'pydantic': 'Pydantic',
    'gradio': 'Gradio',
    'fastapi': 'FastAPI',
    'uvicorn': 'Uvicorn',
    'pandas': 'Pandas',
    'requests': 'Requests',
    'diskcache': 'Diskcache',
    'structlog': 'Structlog',
    'prometheus_client': 'Prometheus客户端',
    'tenacity': 'Tenacity',
}


def check_dependency(module_name: str, display_name: str) -> bool:
    """检查单个依赖是否可导入"""
    try:
        importlib.import_module(module_name)
        print(f"[OK] {display_name} ({module_name})")
        return True
    except ImportError as e:
        print(f"[FAIL] {display_name} ({module_name}): {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("互联网谣言判断系统 - 依赖验证")
    print("=" * 60)
    print()

    success_count = 0
    fail_count = 0

    for module_name, display_name in REQUIRED_DEPENDENCIES.items():
        if check_dependency(module_name, display_name):
            success_count += 1
        else:
            fail_count += 1

    print()
    print("=" * 60)
    print(f"验证结果：{success_count} 成功, {fail_count} 失败")
    print("=" * 60)

    if fail_count > 0:
        print("\n[WARNING] 部分依赖未正确安装")
        print("请运行：pip install -r requirements.lock")
        sys.exit(1)
    else:
        print("\n[SUCCESS] 所有依赖验证通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
