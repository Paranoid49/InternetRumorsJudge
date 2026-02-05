"""
结构化日志配置

使用 structlog 提供 JSON 格式的结构化日志
支持链路追踪（trace_id）贯穿整个请求生命周期
"""
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False
    # 回退到标准 logging
    import logging
    structlog = None


# 链路追踪上下文
TRACE_CONTEXT: ContextVar[str] = ContextVar('trace_context', default='')


def configure_logging(log_level: str = "INFO", json_output: bool = True):
    """
    配置结构化日志

    Args:
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR）
        json_output: 是否输出 JSON 格式（生产环境推荐 True）
    """
    if not STRUCTLOG_AVAILABLE:
        # 回退到标准 logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return

    # 配置 structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # JSON 格式（生产环境）
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 可读格式（开发环境）
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 配置标准 logging 以捕获第三方库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    structlog.get_logger().info("结构化日志已配置", json_output=json_output, level=log_level)


def get_logger(name: str) -> Any:
    """
    获取结构化日志记录器

    如果 structlog 不可用，回退到标准 logging

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器实例
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
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

    Args:
        logger: 日志记录器
        **context: 要添加的上下文键值对

    Returns:
        绑定了上下文的日志记录器
    """
    if STRUCTLOG_AVAILABLE:
        return logger.bind(**context)
    else:
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
