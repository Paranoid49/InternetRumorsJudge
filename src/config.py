# config.py
"""
项目配置入口

[v1.3.0] 重构为配置管理器的代理层，保持向后兼容

使用方式：
    # 旧版方式（仍然支持）
    from src import config
    api_key = config.API_KEY

    # 新版方式（推荐）
    from src.core.config_manager import config
    api_key = config.API.DASHSCOPE_API_KEY
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# 环境变量配置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 导入统一配置管理器
from src.core.config_manager import config, get_config, validate_config

# ============================================
# 向后兼容：直接暴露配置属性
# ============================================

# API 密钥
API_KEY = config.API.DASHSCOPE_API_KEY
TAVILY_API_KEY = config.API.TAVILY_API_KEY

# 检索配置
SIMILARITY_THRESHOLD = config.Retrieval.SIMILARITY_THRESHOLD
EMBEDDING_MODEL = config.Retrieval.EMBEDDING_MODEL
MIN_LOCAL_SIMILARITY = config.Retrieval.MIN_LOCAL_SIMILARITY
MAX_RESULTS = config.Retrieval.MAX_RESULTS
DEDUP_SIMILARITY_THRESHOLD = config.Retrieval.DEDUP_SIMILARITY_THRESHOLD

# 缓存配置
SEMANTIC_CACHE_THRESHOLD = config.Cache.SEMANTIC_CACHE_THRESHOLD
DEFAULT_CACHE_TTL = config.Cache.DEFAULT_CACHE_TTL

# 自动集成配置
AUTO_INTEGRATE_MIN_CONFIDENCE = config.AutoIntegration.AUTO_INTEGRATE_MIN_CONFIDENCE
AUTO_INTEGRATE_MIN_EVIDENCE = config.AutoIntegration.AUTO_INTEGRATE_MIN_EVIDENCE
AUTO_GEN_WEIGHT = config.AutoIntegration.AUTO_GEN_WEIGHT

# 模型配置
MODEL_PARSER = config.Model.MODEL_PARSER
MODEL_ANALYZER = config.Model.MODEL_ANALYZER
MODEL_SUMMARIZER = config.Model.MODEL_SUMMARIZER

# 自动收集配置
ENABLE_AUTO_COLLECT = config.AutoIntegration.ENABLE_AUTO_COLLECT
AUTO_COLLECT_INTERVAL = config.AutoIntegration.AUTO_COLLECT_INTERVAL

# 超时配置
LLM_REQUEST_TIMEOUT = config.Model.LLM_REQUEST_TIMEOUT
WEB_SEARCH_TIMEOUT = config.Performance.WEB_SEARCH_TIMEOUT

# 证据预过滤配置
ENABLE_EVIDENCE_PREFILTER = config.Prefilter.ENABLE_EVIDENCE_PREFILTER
PREFILTER_MAX_EVIDENCE = config.Prefilter.PREFILTER_MAX_EVIDENCE
PREFILTER_MIN_SIMILARITY = config.Prefilter.PREFILTER_MIN_SIMILARITY
PREFILTER_HIGH_QUALITY_THRESHOLD = config.Prefilter.PREFILTER_HIGH_QUALITY_THRESHOLD
PREFILTER_MIN_EVIDENCE_COUNT = config.Prefilter.PREFILTER_MIN_EVIDENCE_COUNT

# 性能优化配置
ENABLE_FAST_MODE = config.Performance.ENABLE_FAST_MODE
ANALYZER_MAX_TOKENS = config.Performance.ANALYZER_MAX_TOKENS
PARALLEL_ANALYZE_THRESHOLD = config.Performance.PARALLEL_ANALYZE_THRESHOLD
BATCH_EMBEDDING_ENABLED = config.Performance.BATCH_EMBEDDING_ENABLED


# ============================================
# 便捷函数
# ============================================

def get_config_value(key: str, default=None):
    """
    获取配置值（支持点号分隔的路径）

    Args:
        key: 配置键，如 "API.DASHSCOPE_API_KEY"
        default: 默认值

    Returns:
        配置值
    """
    return config.get(key, default)


def validate_configuration():
    """验证配置，返回错误列表"""
    return config.validate()


def export_config(include_secrets: bool = False):
    """导出配置（用于调试）"""
    return config.to_dict(include_secrets)


# 导出
__all__ = [
    # 配置管理器
    'config',
    'get_config',
    'validate_config',
    # 旧版属性
    'API_KEY',
    'TAVILY_API_KEY',
    'SIMILARITY_THRESHOLD',
    'EMBEDDING_MODEL',
    'MIN_LOCAL_SIMILARITY',
    'MAX_RESULTS',
    'DEDUP_SIMILARITY_THRESHOLD',
    'SEMANTIC_CACHE_THRESHOLD',
    'DEFAULT_CACHE_TTL',
    'AUTO_INTEGRATE_MIN_CONFIDENCE',
    'AUTO_INTEGRATE_MIN_EVIDENCE',
    'AUTO_GEN_WEIGHT',
    'MODEL_PARSER',
    'MODEL_ANALYZER',
    'MODEL_SUMMARIZER',
    'ENABLE_AUTO_COLLECT',
    'AUTO_COLLECT_INTERVAL',
    'LLM_REQUEST_TIMEOUT',
    'WEB_SEARCH_TIMEOUT',
    'ENABLE_EVIDENCE_PREFILTER',
    'PREFILTER_MAX_EVIDENCE',
    'PREFILTER_MIN_SIMILARITY',
    'PREFILTER_HIGH_QUALITY_THRESHOLD',
    'PREFILTER_MIN_EVIDENCE_COUNT',
    'ENABLE_FAST_MODE',
    'ANALYZER_MAX_TOKENS',
    'PARALLEL_ANALYZE_THRESHOLD',
    'BATCH_EMBEDDING_ENABLED',
    # 便捷函数
    'get_config_value',
    'validate_configuration',
    'export_config',
]
