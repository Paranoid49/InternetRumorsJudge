#!/usr/bin/env python3
"""
测试运行脚本

提供便捷的测试运行命令
"""
import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'=' * 60}")
    print(f"运行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print('=' * 60)

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"\n✅ {description} - 成功")
    else:
        print(f"\n❌ {description} - 失败 (退出码: {result.returncode})")

    return result.returncode == 0


def main():
    """主函数"""
    print("=" * 60)
    print("互联网谣言判断系统 - 测试运行器")
    print("=" * 60)

    # 解析命令行参数
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
    else:
        test_type = "unit"

    # 基础pytest命令
    pytest_base = ["python", "-m", "pytest"]

    # 测试类型映射
    test_commands = {
        "unit": {
            "description": "单元测试",
            "args": ["-m", "unit", "-v"],
            "required": False
        },
        "integration": {
            "description": "集成测试",
            "args": ["-m", "integration", "-v"],
            "required": False
        },
        "e2e": {
            "description": "端到端测试",
            "args": ["-m", "e2e", "-v"],
            "required": False
        },
        "all": {
            "description": "所有测试",
            "args": ["-v"],
            "required": False
        },
        "coverage": {
            "description": "测试覆盖率",
            "args": ["--cov=src", "--cov-report=html", "--cov-report=term"],
            "required": False
        },
        "fast": {
            "description": "快速测试（跳过慢速测试）",
            "args": ["-m", "not slow", "-v"],
            "required": False
        },
        "concurrent": {
            "description": "并发测试",
            "args": ["-m", "concurrent", "-v"],
            "required": False
        }
    }

    if test_type not in test_commands:
        print(f"\n❌ 未知的测试类型: {test_type}")
        print("\n可用的测试类型:")
        for key, value in test_commands.items():
            print(f"  - {key}: {value['description']}")
        print("\n示例:")
        print("  python scripts/run_tests.py unit")
        print("  python scripts/run_tests.py coverage")
        return 1

    # 构建命令
    config = test_commands[test_type]
    cmd = pytest_base + config["args"]

    # 运行测试
    success = run_command(cmd, config['description'])

    if success and test_type == "coverage":
        print("\n📊 覆盖率报告已生成: htmlcov/index.html")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
