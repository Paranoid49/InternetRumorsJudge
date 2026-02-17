"""
统一配置管理器

[v1.3.0] 提供集中式配置管理，支持：
- 环境变量加载
- 类型验证和转换
- 默认值管理
- 配置导出和调试

[v1.3.1] 改进：所有默认值集中在文件顶部，便于修改

使用方式：
    from src.core.config_manager import config

    # 获取配置值
    api_key = config.API.DASHSCOPE_API_KEY
    timeout = config.Model.LLM_REQUEST_TIMEOUT

    # 检查配置状态
    config.validate()  # 验证必要配置
    config.to_dict()   # 导出所有配置（用于调试）

修改配置默认值：
    1. 直接修改下方的 DEFAULT_* 常量
    2. 或通过环境变量覆盖（推荐生产环境）
"""
import os
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, get_type_hints
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from functools import lru_cache

# 延迟导入 dotenv
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

logger = logging.getLogger("ConfigManager")


# ============================================
# 【集中式默认值定义】
# 所有配置默认值在此处定义，便于查找和修改
# ============================================

# API 配置
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"

# 检索配置
DEFAULT_SIMILARITY_THRESHOLD = 0.25
DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"
DEFAULT_MIN_LOCAL_SIMILARITY = 0.6
DEFAULT_MAX_RESULTS = 3
DEFAULT_DEDUP_SIMILARITY_THRESHOLD = 0.85

# 缓存配置
DEFAULT_SEMANTIC_CACHE_THRESHOLD = 0.96
DEFAULT_CACHE_TTL = 86400  # 24小时

# 模型配置（常用修改项）
DEFAULT_MODEL_PARSER = "qwen-plus"      # 意图解析模型
DEFAULT_MODEL_ANALYZER = "qwen-plus"    # 证据分析模型
DEFAULT_MODEL_SUMMARIZER = "qwen-max"   # 最终裁决模型（最强）
DEFAULT_LLM_REQUEST_TIMEOUT = 30

# 预过滤配置
DEFAULT_ENABLE_EVIDENCE_PREFILTER = True
DEFAULT_PREFILTER_MAX_EVIDENCE = 5
DEFAULT_PREFILTER_MIN_SIMILARITY = 0.3
DEFAULT_PREFILTER_HIGH_QUALITY_THRESHOLD = 0.7
DEFAULT_PREFILTER_MIN_EVIDENCE_COUNT = 2

# 性能配置
DEFAULT_ENABLE_FAST_MODE = False
DEFAULT_ANALYZER_MAX_TOKENS = 1024
DEFAULT_PARALLEL_ANALYZE_THRESHOLD = 2
DEFAULT_BATCH_EMBEDDING_ENABLED = True
DEFAULT_WEB_SEARCH_TIMEOUT = 15

# 自动集成配置
DEFAULT_AUTO_INTEGRATE_MIN_CONFIDENCE = 90
DEFAULT_AUTO_INTEGRATE_MIN_EVIDENCE = 3
DEFAULT_AUTO_GEN_WEIGHT = 0.9
DEFAULT_ENABLE_AUTO_COLLECT = True
DEFAULT_AUTO_COLLECT_INTERVAL = 86400  # 24小时

# 日志配置
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_JSON_OUTPUT = False

# 特性开关
DEFAULT_USE_ASYNC_ENGINE = False


# ============================================
# 工具函数
# ============================================

def _get_env(key: str, default: Any = None, cast: Optional[Type] = None) -> Any:
    """
    从环境变量获取值并进行类型转换

    Args:
        key: 环境变量名
        default: 默认值
        cast: 目标类型（str, int, float, bool）

    Returns:
        转换后的值
    """
    value = os.environ.get(key)

    if value is None:
        return default

    if cast is None:
        return value

    try:
        if cast is bool:
            # 布尔值特殊处理
            return value.lower() in ('true', '1', 'yes', 'on')
        elif cast is int:
            return int(value)
        elif cast is float:
            return float(value)
        elif cast is str:
            return value
        else:
            return cast(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"配置 {key}={value} 转换为 {cast} 失败，使用默认值 {default}: {e}")
        return default


# ============================================
# 配置分组 DataClasses
# ============================================

@dataclass
class APIConfig:
    """API 密钥配置"""
    DASHSCOPE_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    HF_ENDPOINT: str = DEFAULT_HF_ENDPOINT

    def __post_init__(self):
        self.DASHSCOPE_API_KEY = _get_env("DASHSCOPE_API_KEY", self.DASHSCOPE_API_KEY)
        self.TAVILY_API_KEY = _get_env("TAVILY_API_KEY", self.TAVILY_API_KEY)
        self.HF_ENDPOINT = _get_env("HF_ENDPOINT", self.HF_ENDPOINT)
        os.environ.setdefault("HF_ENDPOINT", self.HF_ENDPOINT)


@dataclass
class RetrievalConfig:
    """检索配置"""
    SIMILARITY_THRESHOLD: float = DEFAULT_SIMILARITY_THRESHOLD
    EMBEDDING_MODEL: str = DEFAULT_EMBEDDING_MODEL
    MIN_LOCAL_SIMILARITY: float = DEFAULT_MIN_LOCAL_SIMILARITY
    MAX_RESULTS: int = DEFAULT_MAX_RESULTS
    DEDUP_SIMILARITY_THRESHOLD: float = DEFAULT_DEDUP_SIMILARITY_THRESHOLD

    def __post_init__(self):
        self.SIMILARITY_THRESHOLD = _get_env("SIMILARITY_THRESHOLD", self.SIMILARITY_THRESHOLD, float)
        self.EMBEDDING_MODEL = _get_env("EMBEDDING_MODEL", self.EMBEDDING_MODEL)
        self.MIN_LOCAL_SIMILARITY = _get_env("MIN_LOCAL_SIMILARITY", self.MIN_LOCAL_SIMILARITY, float)
        self.MAX_RESULTS = _get_env("MAX_RESULTS", self.MAX_RESULTS, int)
        self.DEDUP_SIMILARITY_THRESHOLD = _get_env("DEDUP_SIMILARITY_THRESHOLD", self.DEDUP_SIMILARITY_THRESHOLD, float)


@dataclass
class CacheConfig:
    """缓存配置"""
    SEMANTIC_CACHE_THRESHOLD: float = DEFAULT_SEMANTIC_CACHE_THRESHOLD
    DEFAULT_CACHE_TTL: int = DEFAULT_CACHE_TTL

    def __post_init__(self):
        self.SEMANTIC_CACHE_THRESHOLD = _get_env("SEMANTIC_CACHE_THRESHOLD", self.SEMANTIC_CACHE_THRESHOLD, float)
        self.DEFAULT_CACHE_TTL = _get_env("DEFAULT_CACHE_TTL", self.DEFAULT_CACHE_TTL, int)


@dataclass
class ModelConfig:
    """模型配置"""
    MODEL_PARSER: str = DEFAULT_MODEL_PARSER
    MODEL_ANALYZER: str = DEFAULT_MODEL_ANALYZER
    MODEL_SUMMARIZER: str = DEFAULT_MODEL_SUMMARIZER
    LLM_REQUEST_TIMEOUT: int = DEFAULT_LLM_REQUEST_TIMEOUT

    def __post_init__(self):
        self.MODEL_PARSER = _get_env("MODEL_PARSER", self.MODEL_PARSER)
        self.MODEL_ANALYZER = _get_env("MODEL_ANALYZER", self.MODEL_ANALYZER)
        self.MODEL_SUMMARIZER = _get_env("MODEL_SUMMARIZER", self.MODEL_SUMMARIZER)
        self.LLM_REQUEST_TIMEOUT = _get_env("LLM_REQUEST_TIMEOUT", self.LLM_REQUEST_TIMEOUT, int)


@dataclass
class PrefilterConfig:
    """证据预过滤配置"""
    ENABLE_EVIDENCE_PREFILTER: bool = DEFAULT_ENABLE_EVIDENCE_PREFILTER
    PREFILTER_MAX_EVIDENCE: int = DEFAULT_PREFILTER_MAX_EVIDENCE
    PREFILTER_MIN_SIMILARITY: float = DEFAULT_PREFILTER_MIN_SIMILARITY
    PREFILTER_HIGH_QUALITY_THRESHOLD: float = DEFAULT_PREFILTER_HIGH_QUALITY_THRESHOLD
    PREFILTER_MIN_EVIDENCE_COUNT: int = DEFAULT_PREFILTER_MIN_EVIDENCE_COUNT

    def __post_init__(self):
        self.ENABLE_EVIDENCE_PREFILTER = _get_env("ENABLE_EVIDENCE_PREFILTER", self.ENABLE_EVIDENCE_PREFILTER, bool)
        self.PREFILTER_MAX_EVIDENCE = _get_env("PREFILTER_MAX_EVIDENCE", self.PREFILTER_MAX_EVIDENCE, int)
        self.PREFILTER_MIN_SIMILARITY = _get_env("PREFILTER_MIN_SIMILARITY", self.PREFILTER_MIN_SIMILARITY, float)
        self.PREFILTER_HIGH_QUALITY_THRESHOLD = _get_env("PREFILTER_HIGH_QUALITY_THRESHOLD", self.PREFILTER_HIGH_QUALITY_THRESHOLD, float)
        self.PREFILTER_MIN_EVIDENCE_COUNT = _get_env("PREFILTER_MIN_EVIDENCE_COUNT", self.PREFILTER_MIN_EVIDENCE_COUNT, int)


@dataclass
class PerformanceConfig:
    """性能配置"""
    ENABLE_FAST_MODE: bool = DEFAULT_ENABLE_FAST_MODE
    ANALYZER_MAX_TOKENS: int = DEFAULT_ANALYZER_MAX_TOKENS
    PARALLEL_ANALYZE_THRESHOLD: int = DEFAULT_PARALLEL_ANALYZE_THRESHOLD
    BATCH_EMBEDDING_ENABLED: bool = DEFAULT_BATCH_EMBEDDING_ENABLED
    WEB_SEARCH_TIMEOUT: int = DEFAULT_WEB_SEARCH_TIMEOUT

    def __post_init__(self):
        self.ENABLE_FAST_MODE = _get_env("ENABLE_FAST_MODE", self.ENABLE_FAST_MODE, bool)
        self.ANALYZER_MAX_TOKENS = _get_env("ANALYZER_MAX_TOKENS", self.ANALYZER_MAX_TOKENS, int)
        self.PARALLEL_ANALYZE_THRESHOLD = _get_env("PARALLEL_ANALYZE_THRESHOLD", self.PARALLEL_ANALYZE_THRESHOLD, int)
        self.BATCH_EMBEDDING_ENABLED = _get_env("BATCH_EMBEDDING_ENABLED", self.BATCH_EMBEDDING_ENABLED, bool)
        self.WEB_SEARCH_TIMEOUT = _get_env("WEB_SEARCH_TIMEOUT", self.WEB_SEARCH_TIMEOUT, int)


@dataclass
class AutoIntegrationConfig:
    """自动集成配置"""
    AUTO_INTEGRATE_MIN_CONFIDENCE: int = DEFAULT_AUTO_INTEGRATE_MIN_CONFIDENCE
    AUTO_INTEGRATE_MIN_EVIDENCE: int = DEFAULT_AUTO_INTEGRATE_MIN_EVIDENCE
    AUTO_GEN_WEIGHT: float = DEFAULT_AUTO_GEN_WEIGHT
    ENABLE_AUTO_COLLECT: bool = DEFAULT_ENABLE_AUTO_COLLECT
    AUTO_COLLECT_INTERVAL: int = DEFAULT_AUTO_COLLECT_INTERVAL

    def __post_init__(self):
        self.AUTO_INTEGRATE_MIN_CONFIDENCE = _get_env("AUTO_INTEGRATE_MIN_CONFIDENCE", self.AUTO_INTEGRATE_MIN_CONFIDENCE, int)
        self.AUTO_INTEGRATE_MIN_EVIDENCE = _get_env("AUTO_INTEGRATE_MIN_EVIDENCE", self.AUTO_INTEGRATE_MIN_EVIDENCE, int)
        self.AUTO_GEN_WEIGHT = _get_env("AUTO_GEN_WEIGHT", self.AUTO_GEN_WEIGHT, float)
        self.ENABLE_AUTO_COLLECT = _get_env("ENABLE_AUTO_COLLECT", self.ENABLE_AUTO_COLLECT, bool)
        self.AUTO_COLLECT_INTERVAL = _get_env("AUTO_COLLECT_INTERVAL", self.AUTO_COLLECT_INTERVAL, int)


@dataclass
class LogConfig:
    """日志配置"""
    LOG_LEVEL: str = DEFAULT_LOG_LEVEL
    LOG_JSON_OUTPUT: bool = DEFAULT_LOG_JSON_OUTPUT

    def __post_init__(self):
        self.LOG_LEVEL = _get_env("LOG_LEVEL", self.LOG_LEVEL)
        self.LOG_JSON_OUTPUT = _get_env("LOG_JSON_OUTPUT", self.LOG_JSON_OUTPUT, bool)


@dataclass
class FeatureConfig:
    """特性开关配置"""
    USE_ASYNC_ENGINE: bool = DEFAULT_USE_ASYNC_ENGINE

    def __post_init__(self):
        self.USE_ASYNC_ENGINE = _get_env("USE_ASYNC_ENGINE", self.USE_ASYNC_ENGINE, bool)


class ConfigManager:
    """
    统一配置管理器

    功能：
    1. 集中管理所有配置
    2. 支持环境变量覆盖
    3. 提供配置验证
    4. 支持配置导出

    使用示例：
        from src.core.config_manager import config

        # 访问配置
        print(config.API.DASHSCOPE_API_KEY)
        print(config.Model.MODEL_SUMMARIZER)

        # 验证配置
        config.validate()

        # 导出配置（调试用）
        debug_info = config.to_dict()
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ConfigManager._initialized:
            return

        # 加载 .env 文件
        self._load_dotenv()

        # 初始化各配置分组
        self.API = APIConfig()
        self.Retrieval = RetrievalConfig()
        self.Cache = CacheConfig()
        self.Model = ModelConfig()
        self.Prefilter = PrefilterConfig()
        self.Performance = PerformanceConfig()
        self.AutoIntegration = AutoIntegrationConfig()
        self.Log = LogConfig()
        self.Feature = FeatureConfig()

        ConfigManager._initialized = True
        logger.info("配置管理器已初始化")

    def _load_dotenv(self):
        """加载 .env 文件"""
        if DOTENV_AVAILABLE:
            # 查找 .env 文件
            env_paths = [
                Path.cwd() / ".env",
                Path(__file__).parent.parent.parent / ".env",
            ]
            for env_path in env_paths:
                if env_path.exists():
                    load_dotenv(env_path)
                    logger.debug(f"已加载环境文件: {env_path}")
                    break

    def validate(self) -> List[str]:
        """
        验证必要配置

        Returns:
            错误消息列表（空列表表示验证通过）
        """
        errors = []

        # 验证 API 密钥
        if not self.API.DASHSCOPE_API_KEY:
            errors.append("DASHSCOPE_API_KEY 未配置")

        # 验证数值范围
        if not 0 <= self.Retrieval.SIMILARITY_THRESHOLD <= 1:
            errors.append(f"SIMILARITY_THRESHOLD 应在 0-1 之间，当前值: {self.Retrieval.SIMILARITY_THRESHOLD}")

        if not 0 <= self.Cache.SEMANTIC_CACHE_THRESHOLD <= 1:
            errors.append(f"SEMANTIC_CACHE_THRESHOLD 应在 0-1 之间，当前值: {self.Cache.SEMANTIC_CACHE_THRESHOLD}")

        if self.Model.LLM_REQUEST_TIMEOUT <= 0:
            errors.append(f"LLM_REQUEST_TIMEOUT 应大于 0，当前值: {self.Model.LLM_REQUEST_TIMEOUT}")

        if errors:
            logger.warning(f"配置验证失败: {errors}")
        else:
            logger.debug("配置验证通过")

        return errors

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        导出配置为字典（用于调试）

        Args:
            include_secrets: 是否包含敏感信息（API密钥等）

        Returns:
            配置字典
        """
        result = {}

        for group_name in ['API', 'Retrieval', 'Cache', 'Model', 'Prefilter', 'Performance', 'AutoIntegration', 'Log', 'Feature']:
            group = getattr(self, group_name)
            group_dict = asdict(group)

            # 脱敏处理
            if not include_secrets and group_name == 'API':
                group_dict = {k: '***' if 'KEY' in k else v for k, v in group_dict.items()}

            result[group_name] = group_dict

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）

        Args:
            key: 配置键，如 "API.DASHSCOPE_API_KEY" 或 "Model.LLM_REQUEST_TIMEOUT"
            default: 默认值

        Returns:
            配置值
        """
        try:
            parts = key.split('.')
            if len(parts) == 1:
                # 尝试在所有分组中查找
                for group_name in ['API', 'Retrieval', 'Cache', 'Model', 'Prefilter', 'Performance', 'AutoIntegration', 'Log', 'Feature']:
                    group = getattr(self, group_name)
                    if hasattr(group, key):
                        return getattr(group, key)
                return default
            elif len(parts) == 2:
                group_name, attr_name = parts
                group = getattr(self, group_name)
                return getattr(group, attr_name, default)
            else:
                logger.warning(f"不支持的配置键格式: {key}")
                return default
        except Exception as e:
            logger.warning(f"获取配置 {key} 失败: {e}")
            return default

    def reload(self):
        """重新加载配置"""
        ConfigManager._initialized = False
        self.__init__()
        logger.info("配置已重新加载")


# 全局配置实例
config = ConfigManager()


# ============================================
# 向后兼容：提供旧版 config.py 的属性访问
# ============================================

# API 密钥
API_KEY = property(lambda self: config.API.DASHSCOPE_API_KEY)
TAVILY_API_KEY = property(lambda self: config.API.TAVILY_API_KEY)

# 检索配置
SIMILARITY_THRESHOLD = property(lambda self: config.Retrieval.SIMILARITY_THRESHOLD)
EMBEDDING_MODEL = property(lambda self: config.Retrieval.EMBEDDING_MODEL)
MIN_LOCAL_SIMILARITY = property(lambda self: config.Retrieval.MIN_LOCAL_SIMILARITY)
MAX_RESULTS = property(lambda self: config.Retrieval.MAX_RESULTS)
DEDUP_SIMILARITY_THRESHOLD = property(lambda self: config.Retrieval.DEDUP_SIMILARITY_THRESHOLD)

# 缓存配置
SEMANTIC_CACHE_THRESHOLD = property(lambda self: config.Cache.SEMANTIC_CACHE_THRESHOLD)
DEFAULT_CACHE_TTL = property(lambda self: config.Cache.DEFAULT_CACHE_TTL)

# 模型配置
MODEL_PARSER = property(lambda self: config.Model.MODEL_PARSER)
MODEL_ANALYZER = property(lambda self: config.Model.MODEL_ANALYZER)
MODEL_SUMMARIZER = property(lambda self: config.Model.MODEL_SUMMARIZER)
LLM_REQUEST_TIMEOUT = property(lambda self: config.Model.LLM_REQUEST_TIMEOUT)

# 预过滤配置
ENABLE_EVIDENCE_PREFILTER = property(lambda self: config.Prefilter.ENABLE_EVIDENCE_PREFILTER)
PREFILTER_MAX_EVIDENCE = property(lambda self: config.Prefilter.PREFILTER_MAX_EVIDENCE)
PREFILTER_MIN_SIMILARITY = property(lambda self: config.Prefilter.PREFILTER_MIN_SIMILARITY)
PREFILTER_HIGH_QUALITY_THRESHOLD = property(lambda self: config.Prefilter.PREFILTER_HIGH_QUALITY_THRESHOLD)
PREFILTER_MIN_EVIDENCE_COUNT = property(lambda self: config.Prefilter.PREFILTER_MIN_EVIDENCE_COUNT)

# 性能配置
ENABLE_FAST_MODE = property(lambda self: config.Performance.ENABLE_FAST_MODE)
ANALYZER_MAX_TOKENS = property(lambda self: config.Performance.ANALYZER_MAX_TOKENS)
PARALLEL_ANALYZE_THRESHOLD = property(lambda self: config.Performance.PARALLEL_ANALYZE_THRESHOLD)
BATCH_EMBEDDING_ENABLED = property(lambda self: config.Performance.BATCH_EMBEDDING_ENABLED)
WEB_SEARCH_TIMEOUT = property(lambda self: config.Performance.WEB_SEARCH_TIMEOUT)

# 自动集成配置
AUTO_INTEGRATE_MIN_CONFIDENCE = property(lambda self: config.AutoIntegration.AUTO_INTEGRATE_MIN_CONFIDENCE)
AUTO_INTEGRATE_MIN_EVIDENCE = property(lambda self: config.AutoIntegration.AUTO_INTEGRATE_MIN_EVIDENCE)
AUTO_GEN_WEIGHT = property(lambda self: config.AutoIntegration.AUTO_GEN_WEIGHT)
ENABLE_AUTO_COLLECT = property(lambda self: config.AutoIntegration.ENABLE_AUTO_COLLECT)
AUTO_COLLECT_INTERVAL = property(lambda self: config.AutoIntegration.AUTO_COLLECT_INTERVAL)


# 导出便捷函数
def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    return config


def validate_config() -> List[str]:
    """验证配置"""
    return config.validate()
