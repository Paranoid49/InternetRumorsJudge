# config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# 请在此处替换为你的真实API密钥
API_KEY = os.environ.get("DASHSCOPE_API_KEY")
# 或其他你使用的模型API密钥
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# 检索配置
SIMILARITY_THRESHOLD = 0.4  # 相似度阈值，低于此分数的检索结果将被过滤