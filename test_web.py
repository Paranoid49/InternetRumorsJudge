"""
简单测试脚本 - 验证Web界面
"""
import sys
import time
import subprocess

print("[1] 正在启动Gradio Web界面...")
print("[提示] 界面将在浏览器中打开，请手动测试查询功能")
print("[提示] 测试完成后按Ctrl+C停止服务\n")

# 启动Gradio服务
process = subprocess.Popen(
    [sys.executable, "scripts/web_interface.py"],
    stdout=None,
    stderr=None,
    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
)

print(f"[2] Gradio服务已启动（PID: {process.pid}）")
print("[3] 请在浏览器中访问: http://localhost:7860")
print("\n建议测试查询:")
print("  - 维生素C能预防感冒吗？（应该命中缓存）")
print("  - 喝隔夜水会致癌吗（应该命中缓存）")
print("\n按Ctrl+C停止测试...")

try:
    # 等待用户中断
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n[4] 正在停止服务...")
    process.terminate()
    process.wait(timeout=10)
    print("测试完成")
