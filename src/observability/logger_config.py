"""
结构化日志配置

[v1.3.0] 统一日志配置入口，强制标准日志格式

标准日志格式：时间戳 - 模块名 - 日志等级 - 消息
示例：2026-02-16 12:00:00,123 - CacheManager - INFO - 缓存初始化完成

所有模块应使用此模块的 get_logger() 或 configure_logging()
避免在各模块中直接调用 logging.basicConfig()
"""
import logging
import sys
import time
import uuid
import os
from contextvars import ContextVar
from typing import Any, Dict, Optional

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    # 回退到标准 logging
    structlog = None


# 链路追踪上下文
TRACE_CONTEXT: ContextVar[str] = ContextVar('trace_context', default='')

# 标记是否已配置（避免重复配置）
_CONFIGURED = False

# 标准日志格式（强制使用）
# 格式：时间戳 - 模块名 - 日志等级 - 消息
STANDARD_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 从环境变量读取配置
DEFAULT_LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
DEFAULT_JSON_OUTPUT = os.getenv('LOG_JSON_OUTPUT', 'false').lower() == 'true'


def configure_logging(
    log_level: Optional[str] = None,
    json_output: Optional[bool] = None,
    force: bool = False
) -> bool:
    """
    配置结构化日志（全局统一入口）

    [v1.2.0] 增强：
    - 支持环境变量配置
    - 避免重复配置
    - 支持强制重新配置

    Args:
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR），默认从环境变量读取
        json_output: 是否输出 JSON 格式（生产环境推荐 True），默认从环境变量读取
        force: 是否强制重新配置（即使已配置过）

    Returns:
        bool: 是否执行了配置（False 表示已配置过且未强制）

    使用示例:
        # 在应用入口处调用一次
        from src.observability.logger_config import configure_logging
        configure_logging(log_level="DEBUG", json_output=False)

        # 或者使用环境变量
        # export LOG_LEVEL=DEBUG
        # export LOG_JSON_OUTPUT=true
        configure_logging()
    """
    global _CONFIGURED

    # 避免重复配置
    if _CONFIGURED and not force:
        return False

    # 使用默认值（从环境变量读取）
    if log_level is None:
        log_level = DEFAULT_LOG_LEVEL
    if json_output is None:
        json_output = DEFAULT_JSON_OUTPUT

    if not STRUCTLOG_AVAILABLE:
        # 回退到标准 logging
        _configure_standard_logging(log_level)
        _CONFIGURED = True
        return True

    # 配置 structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # JSON 格式（生产环境）
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 可读格式（开发环境）- 使用标准格式
        processors.append(structlog.dev.ConsoleRenderer(
            colors=False,
            pad_level=False,
            exception_formatter=structlog.dev.plain_traceback
        ))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 配置标准 logging - 强制使用标准格式
    # 这确保即使使用 logging.getLogger() 也有正确的格式
    logging.basicConfig(
        format=STANDARD_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
        force=True  # 强制覆盖之前的配置
    )

    # 降低第三方库的日志级别
    _quiet_third_party_loggers()

    # 输出配置完成信息（使用标准 logging 格式）
    logging.getLogger("LoggerConfig").info(
        f"结构化日志已配置 (json_output={json_output}, level={log_level})"
    )
    _CONFIGURED = True
    return True


def _configure_standard_logging(log_level: str):
    """
    配置标准 logging（当 structlog 不可用时）

    Args:
        log_level: 日志级别
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=STANDARD_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True  # 强制覆盖之前的配置
    )

    # 降低第三方库的日志级别
    _quiet_third_party_loggers()

    # 输出配置完成信息
    logging.getLogger("LoggerConfig").info("标准日志已配置")


def _quiet_third_party_loggers():
    """降低第三方库的日志级别，避免干扰"""
    third_party_loggers = [
        'httpx',
        'httpcore',
        'urllib3',
        'requests',
        'chromadb',
        'langchain',
        'openai',
        'httpbeat',
        'benchmark',
    ]

    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器

    [v1.3.0] 始终返回标准 logging.Logger，确保格式统一

    Args:
        name: 日志记录器名称（通常使用 __name__）

    Returns:
        logging.Logger 实例

    使用示例:
        from src.observability.logger_config import get_logger
        logger = get_logger(__name__)
        logger.info("操作完成")
    """
    return logging.getLogger(name)


def set_trace_id(trace_id: str = None):
    """设置当前链路的追踪 ID"""
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    TRACE_CONTEXT.set(trace_id)
    return trace_id


def get_trace_id() -> str:
    """获取当前链路的追踪 ID"""
    return TRACE_CONTEXT.get()


def clear_trace_id():
    """清除当前链路的追踪 ID"""
    TRACE_CONTEXT.set('')


class RequestContext:
    """
    请求上下文管理器

    自动管理 trace_id 和其他上下文信息
    """

    def __init__(self, trace_id: str = None, **context):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.context = context
        self.old_trace_id = None

    def __enter__(self):
        self.old_trace_id = get_trace_id()
        set_trace_id(self.trace_id)

        # 添加额外的上下文
        if STRUCTLOG_AVAILABLE and self.context:
            logger = structlog.get_logger()
            for key, value in self.context.items():
                logger = logger.bind(**{key: value})

        return self.trace_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_trace_id()
        if self.old_trace_id:
            set_trace_id(self.old_trace_id)


def log_with_context(logger, **context):
    """
    添加结构化上下文到日志

    [v1.3.0] 由于 get_logger() 现在返回标准 logging.Logger，
    此函数简单返回原 logger（标准 logging 不支持 bind）

    Args:
        logger: 日志记录器
        **context: 要添加的上下文键值对（标准 logging 下被忽略）

    Returns:
        原日志记录器
    """
    # 标准 logging 不支持 bind，直接返回原 logger
    # 如果需要结构化日志，可以在消息中包含上下文信息
    return logger


class Timer:
    """
    上下文管理器：用于测量代码块执行时间

    用法：
        with Timer(logger, "operation_name"):
            # 执行操作
            pass
    """

    def __init__(self, logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"开始: {self.operation}", **self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        log_context = {
            **self.context,
            "operation": self.operation,
            "duration_seconds": round(duration, 3)
        }

        if exc_type is None:
            self.logger.info(f"完成: {self.operation}", **log_context)
        else:
            log_context["error"] = str(exc_val)
            log_context["error_type"] = exc_type.__name__
            self.logger.error(f"失败: {self.operation}", **log_context)


def ensure_configured() -> bool:
    """
    确保日志已配置（便捷函数）

    如果尚未配置，使用默认配置（从环境变量读取）
    适用于模块级别的延迟初始化

    Returns:
        bool: 是否执行了配置

    使用示例:
        # 在模块顶部
        from src.observability.logger_config import ensure_configured, get_logger

        ensure_configured()  # 确保日志已配置
        logger = get_logger(__name__)
    """
    return configure_logging()


def is_configured() -> bool:
    """检查日志是否已配置"""
    return _CONFIGURED


# 导出的公共 API
__all__ = [
    'configure_logging',
    'get_logger',
    'ensure_configured',
    'is_configured',
    'set_trace_id',
    'get_trace_id',
    'clear_trace_id',
    'RequestContext',
    'log_with_context',
    'Timer',
    'STRUCTLOG_AVAILABLE',
]
