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
SIMILARITY_THRESHOLD = 0.25
EMBEDDING_MODEL = "text-embedding-v4"

# 模型分级配置 (Model Tiering)
# 使用更快的模型处理中间任务，核心总结使用最强模型
MODEL_PARSER = "qwen-plus"     # 意图解析：需要逻辑，但不需要极高深度
MODEL_ANALYZER = "qwen-plus"   # 证据分析：任务量大，追求速度与准确平衡
MODEL_SUMMARIZER = "qwen-max" # 最终裁决：追求极高准确度与逻辑严密性

# 自动收集配置 (Auto-Collector)
ENABLE_AUTO_COLLECT = True     # 是否开启自动收集互联网谣言
AUTO_COLLECT_INTERVAL = 3600 * 24 # 自动收集间隔时间（秒），默认 24 小时