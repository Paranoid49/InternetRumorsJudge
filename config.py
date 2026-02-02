# config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# 环境变量配置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 使用国内镜像加速模型下载

# 请在此处替换为你的真实API密钥
API_KEY = os.environ.get("DASHSCOPE_API_KEY")
# 或其他你使用的模型API密钥
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# 检索配置
SIMILARITY_THRESHOLD = 0.25  # 针对 v4 模型调优：降低基础过滤阈值，确保本地相关文档不被漏掉
EMBEDDING_MODEL = "text-embedding-v4"  # 阿里云 DashScope 向量模型