"""
简单测试脚本 - 验证API服务
"""
import sys
import time
import subprocess
import requests

# 启动uvicorn服务
print("[1] 正在启动API服务...")
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.services.api_service:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# 等待服务启动
print("[2] 等待服务启动（8秒）...")
time.sleep(8)

# 测试API
try:
    print("[3] 测试 /verify 端点...")
    response = requests.post(
        "http://127.0.0.1:8000/verify",
        json={"query": "喝隔夜水会致癌吗"},
        timeout=30
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   状态: {data.get('success', False)}")
        print(f"   结论: {data.get('verdict', 'N/A')}")
        print(f"   置信度: {data.get('confidence', 0)}")
        print(f"   耗时: {data.get('execution_time_ms', 0):.0f}ms")
        print("\n[API测试成功]")
    else:
        print(f"[错误] HTTP {response.status_code}: {response.text}")
except Exception as e:
    print(f"[错误] {e}")
finally:
    # 停止服务
    print("\n[4] 停止服务...")
    process.terminate()
    process.wait(timeout=5)
    print("完成")
