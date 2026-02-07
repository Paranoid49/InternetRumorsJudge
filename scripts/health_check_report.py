#!/usr/bin/env python
"""
健康检查报告脚本

用于生成系统健康状态报告
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.health_check import get_health_checker


def main():
    """主函数"""
    checker = get_health_checker()
    result = checker.check_all()

    print("=" * 60)
    print("互联网谣言粉碎机 v1.0.0 - 健康检查报告")
    print("=" * 60)
    print()

    # 整体状态
    status_icons = {
        "healthy": "✅",
        "degraded": "⚠️",
        "unhealthy": "❌"
    }
    status_icon = status_icons.get(result["status"], "❓")

    print(f"整体状态: {status_icon} {result['status'].upper()}")
    print(f"检查时间: {result['timestamp']}")
    print(f"运行时长: {result['uptime_seconds']:.2f}秒")
    print()

    # 检查项详情
    print("-" * 60)
    print("检查项详情:")
    print("-" * 60)

    for name, check in result['checks'].items():
        check_icon = "✅" if check['status'] == 'pass' else "⚠️" if check['status'] == 'warning' else "❌"
        print(f"{check_icon} {name:20s}: {check['status']}")

        # 显示关键详情
        if 'details' in check and check['details']:
            details = check['details']
            if name == "configuration":
                if 'api_key' in details:
                    print(f"   - API密钥: {details['api_key']}")
            elif name == "dependencies":
                available = sum(1 for v in details.values() if v == "available")
                print(f"   - 依赖可用: {available}/{len(details)}")
            elif name == "api_monitoring":
                if 'today_calls' in details:
                    print(f"   - 今日调用: {details['today_calls']}次")
                if 'today_cost' in details:
                    print(f"   - 今日成本: {details['today_cost']:.4f}元")

    print()
    print("=" * 60)
    print(f"快速状态: {checker.get_quick_status()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
