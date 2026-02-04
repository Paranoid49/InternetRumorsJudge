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
SIMILARITY_THRESHOLD = 0.25         # 向量检索相似度阈值（用于 evidence_retriever）
EMBEDDING_MODEL = "text-embedding-v4"

# 混合检索配置 (Hybrid Retrieval)
MIN_LOCAL_SIMILARITY = 0.4          # 本地检索相似度阈值，低于此值触发联网搜索
MAX_RESULTS = 3                     # 检索返回的最大证据数量

# 缓存配置 (Cache)
SEMANTIC_CACHE_THRESHOLD = 0.96     # 语义缓存相似度阈值，高于此值认为命中相同问题
DEFAULT_CACHE_TTL = 86400           # 默认缓存过期时间（秒），24小时

# 自动集成配置 (Auto-Integration)
AUTO_INTEGRATE_MIN_CONFIDENCE = 90  # 自动知识集成最小置信度阈值
AUTO_INTEGRATE_MIN_EVIDENCE = 3     # 自动知识集成最小证据数量
AUTO_GEN_WEIGHT = 0.9               # AUTO_GEN_* 文档的相似度加权系数

# 模型分级配置 (Model Tiering)
# 使用更快的模型处理中间任务，核心总结使用最强模型
MODEL_PARSER = "qwen-plus"     # 意图解析：需要逻辑，但不需要极高深度
MODEL_ANALYZER = "qwen-plus"   # 证据分析：任务量大，追求速度与准确平衡
MODEL_SUMMARIZER = "qwen-max" # 最终裁决：追求极高准确度与逻辑严密性

# 自动收集配置 (Auto-Collector)
ENABLE_AUTO_COLLECT = True     # 是否开启自动收集互联网谣言
AUTO_COLLECT_INTERVAL = 3600 * 24 # 自动收集间隔时间（秒），默认 24 小时

# 超时配置 (Timeout)
LLM_REQUEST_TIMEOUT = 30       # LLM 请求超时时间（秒），防止请求挂死
WEB_SEARCH_TIMEOUT = 15        # 联网搜索超时时间（秒）