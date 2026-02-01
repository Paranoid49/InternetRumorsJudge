# 使用轻量级 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    # 默认 API Key，建议在运行时通过 docker-compose 或 -e 覆盖
    DASHSCOPE_API_KEY=""

# 安装系统依赖 (如果某些 Python 包需要编译)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .

# 优化安装流程：
# 1. 使用国内镜像源加速
# 2. 显式安装 CPU 版本的 torch (只有 ~150MB，比默认的 ~900MB 小得多)
# 3. 安装其它依赖
RUN pip install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制项目文件
COPY . .

# 暴露端口 (FastAPI 默认 8000, Gradio 默认 7860)
EXPOSE 8000 7860

# 启动命令在 docker-compose 中定义，或者提供一个默认启动脚本
CMD ["python", "main.py"]
