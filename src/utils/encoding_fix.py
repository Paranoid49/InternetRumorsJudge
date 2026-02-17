"""
编码配置模块 - 增强版

解决 Windows 控制台中文乱码问题和代理对（surrogate pair）问题

[v1.3.0] 使用 logging 替代 print
"""
import sys
import os
import io
import logging

# 获取编码配置专用 logger
_encoding_logger = logging.getLogger("EncodingFix")

# 配置标准输出使用 UTF-8
if sys.platform == "win32":
    try:
        # Python 3.9+ 支持 reconfigure
        if hasattr(sys.stdout, 'reconfigure'):
            # 使用surrogatepass策略处理代理对
            sys.stdout.reconfigure(encoding='utf-8', errors='surrogatepass')
            sys.stderr.reconfigure(encoding='utf-8', errors='surrogatepass')
            _encoding_logger.debug("已配置控制台为UTF-8编码（surrogatepass模式）")
        else:
            # 旧版本 Python 的处理方式
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='surrogatepass'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='surrogatepass'
            )
            _encoding_logger.debug("已使用回退方案配置UTF-8编码")
    except Exception as e:
        # 如果配置失败，使用replace模式
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
                _encoding_logger.debug("已配置UTF-8编码（replace模式）")
        except:
            import warnings
            warnings.warn(f"无法配置控制台编码为 UTF-8: {e}")

    # 修复标准输入的编码
    if hasattr(sys.stdin, 'reconfigure'):
        try:
            sys.stdin.reconfigure(encoding='utf-8', errors='surrogatepass')
        except:
            pass

# 设置环境变量（影响子进程）
os.environ['PYTHONIOENCODING'] = 'utf-8'
