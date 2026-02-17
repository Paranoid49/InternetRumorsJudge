"""
测试日志配置
"""
import pytest
import logging
from unittest.mock import patch, Mock
import sys

from src.observability.logger_config import (
    configure_logging,
    get_logger,
    set_trace_id,
    get_trace_id,
    clear_trace_id,
    RequestContext,
    log_with_context,
    Timer,
    TRACE_CONTEXT,
    STRUCTLOG_AVAILABLE
)


class TestConfigureLogging:
    """测试日志配置"""

    def test_configure_logging_without_structlog(self):
        """测试没有 structlog 时的配置"""
        with patch('src.observability.logger_config.STRUCTLOG_AVAILABLE', False):
            # 不应该抛出异常
            configure_logging(log_level="INFO", json_output=False)

            # 验证标准 logging 已配置
            logger = logging.getLogger()
            # 配置后应该有处理器
            assert len(logger.handlers) > 0 or logger.level != logging.NOTSET

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not available")
    def test_configure_logging_with_structlog_json(self):
        """测试 structlog JSON 格式配置"""
        configure_logging(log_level="INFO", json_output=True)

        # 验证配置成功
        logger = get_logger("test")
        assert logger is not None

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not available")
    def test_configure_logging_with_structlog_console(self):
        """测试 structlog 控制台格式配置"""
        configure_logging(log_level="DEBUG", json_output=False)

        logger = get_logger("test")
        assert logger is not None

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not available")
    def test_configure_logging_different_levels(self):
        """测试不同的日志级别"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            configure_logging(log_level=level, json_output=False)
            logger = get_logger(f"test_{level}")
            assert logger is not None


class TestGetLogger:
    """测试获取日志记录器"""

    def test_get_logger_without_structlog(self):
        """测试没有 structlog 时获取日志记录器"""
        with patch('src.observability.logger_config.STRUCTLOG_AVAILABLE', False):
            logger = get_logger("test_logger")
            assert isinstance(logger, logging.Logger)

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not available")
    def test_get_logger_with_structlog(self):
        """测试有 structlog 时获取日志记录器"""
        configure_logging()
        logger = get_logger("test_logger")
        assert logger is not None

    def test_get_logger_different_names(self):
        """测试获取不同名称的日志记录器"""
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")
        assert logger1 is not logger2


class TestTraceId:
    """测试链路追踪 ID"""

    def test_set_and_get_trace_id(self):
        """测试设置和获取 trace_id"""
        # 清空现有 trace_id
        clear_trace_id()

        # 设置新的 trace_id
        trace_id = set_trace_id("test-trace-123")
        assert trace_id == "test-trace-123"

        # 获取 trace_id
        assert get_trace_id() == "test-trace-123"

        # 清理
        clear_trace_id()

    def test_set_trace_id_auto_generate(self):
        """测试自动生成 trace_id"""
        clear_trace_id()

        # 不传参数，自动生成
        trace_id = set_trace_id()
        assert trace_id is not None
        assert len(trace_id) > 0

        # 应该是有效的 UUID 格式
        assert len(trace_id.split('-')) == 5

        # 清理
        clear_trace_id()

    def test_get_trace_id_default(self):
        """测试获取默认 trace_id"""
        clear_trace_id()

        # 默认应该返回空字符串
        assert get_trace_id() == ""

    def test_clear_trace_id(self):
        """测试清除 trace_id"""
        set_trace_id("test-trace")
        assert get_trace_id() == "test-trace"

        clear_trace_id()
        assert get_trace_id() == ""


class TestRequestContext:
    """测试请求上下文管理器"""

    def test_request_context_with_trace_id(self):
        """测试带 trace_id 的请求上下文"""
        clear_trace_id()

        with RequestContext(trace_id="context-trace-123") as trace_id:
            assert trace_id == "context-trace-123"
            assert get_trace_id() == "context-trace-123"

        # 退出后应该恢复
        assert get_trace_id() == ""

    def test_request_context_auto_generate_trace_id(self):
        """测试自动生成 trace_id 的请求上下文"""
        clear_trace_id()

        with RequestContext() as trace_id:
            assert trace_id is not None
            assert get_trace_id() == trace_id

        assert get_trace_id() == ""

    def test_request_context_with_existing_trace_id(self):
        """测试在已有 trace_id 的情况下使用上下文"""
        clear_trace_id()
        original_trace = set_trace_id("original-trace")

        with RequestContext(trace_id="inner-trace") as inner_trace:
            assert inner_trace == "inner-trace"
            assert get_trace_id() == "inner-trace"

        # 应该恢复原始 trace_id
        assert get_trace_id() == original_trace

        clear_trace_id()

    @pytest.mark.skipif(not STRUCTLOG_AVAILABLE, reason="structlog not available")
    def test_request_context_with_additional_context(self):
        """测试带额外上下文的请求上下文"""
        clear_trace_id()

        with RequestContext(trace_id="test-trace", user_id="123", request_id="456"):
            assert get_trace_id() == "test-trace"

        clear_trace_id()


class TestLogWithContext:
    """测试带上下文的日志"""

    def test_log_with_context_standard_logging(self):
        """测试标准 logging 的上下文日志（v1.3.0: get_logger 始终返回标准 logger）"""
        configure_logging(json_output=False, force=True)
        logger = get_logger("test")

        # 标准 logging 不支持 bind，log_with_context 返回原 logger
        bound_logger = log_with_context(logger, user_id="123", action="test")
        assert bound_logger is logger


class TestTimer:
    """测试计时器上下文管理器"""

    def test_timer_success(self):
        """测试成功的操作计时"""
        logger = get_logger("test")
        logger.info = Mock()
        logger.debug = Mock()

        with Timer(logger, "test_operation", param1="value1"):
            pass

        # 应该调用 debug（开始）和 info（完成）
        assert logger.debug.called
        assert logger.info.called

        # 验证 info 调用包含操作名和耗时
        info_call = logger.info.call_args
        assert "test_operation" in str(info_call)

    def test_timer_with_exception(self):
        """测试操作抛出异常时的计时"""
        logger = get_logger("test")
        logger.debug = Mock()
        logger.error = Mock()

        with pytest.raises(ValueError):
            with Timer(logger, "failing_operation"):
                raise ValueError("测试错误")

        # 应该调用 debug（开始）和 error（失败）
        assert logger.debug.called
        assert logger.error.called

        # 验证 error 调用包含错误信息
        error_call = logger.error.call_args
        assert "failing_operation" in str(error_call)

    def test_timer_measures_duration(self):
        """测试计时器测量耗时"""
        import time

        logger = get_logger("test")
        logger.info = Mock()
        logger.debug = Mock()

        with Timer(logger, "sleep_operation"):
            time.sleep(0.01)  # 睡眠 10ms

        # 验证记录了耗时
        info_call = logger.info.call_args
        # 应该有 duration_seconds 参数
        call_kwargs = info_call[1] if len(info_call) > 1 else {}
        assert "duration_seconds" in call_kwargs or any(
            "duration" in str(arg) for arg in info_call[0]
        )

    def test_timer_with_additional_context(self):
        """测试带额外上下文的计时器"""
        logger = get_logger("test")
        logger.info = Mock()
        logger.debug = Mock()

        with Timer(logger, "test_operation", user_id="123", request_id="456"):
            pass

        # 验证上下文被传递
        debug_call = logger.debug.call_args
        info_call = logger.info.call_args

        # 检查上下文参数
        debug_kwargs = debug_call[1] if len(debug_call) > 1 else {}
        info_kwargs = info_call[1] if len(info_call) > 1 else {}

        # 至少应该有部分上下文
        assert "test_operation" in str(debug_call) or "test_operation" in str(info_call)
