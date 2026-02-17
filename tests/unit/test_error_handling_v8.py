"""
测试错误处理模块

验证增强的异常体系和错误处理装饰器
"""
import pytest
import logging
from unittest.mock import Mock, patch

from src.core.exceptions import (
    ErrorCode,
    RumorJudgeException,
    CacheException,
    CacheMissException,
    RetrievalException,
    WebSearchException,
    LLMException,
    LLMTimeoutException,
    AnalysisException,
    QueryParseException,
    ConfigurationException,
    ConcurrencyException,
    handle_exception,
    create_exception_from_error,
)
from src.utils.error_handler import (
    handle_errors,
    safe_execute,
    retry_on_exception,
    ErrorContext,
)


class TestErrorCode:
    """测试错误码枚举"""

    def test_error_code_values(self):
        """测试错误码值"""
        assert ErrorCode.CACHE_MISS.value == "CACHE_001"
        assert ErrorCode.LLM_TIMEOUT.value == "LLM_001"
        assert ErrorCode.WEB_SEARCH_FAILED.value == "RET_005"

    def test_get_default_user_message(self):
        """测试默认用户信息"""
        msg = ErrorCode.get_default_user_message(ErrorCode.LLM_TIMEOUT)
        assert "超时" in msg or "稍后" in msg

        msg = ErrorCode.get_default_user_message(ErrorCode.INVALID_INPUT)
        assert "无效" in msg or "检查" in msg

        # 未知错误码返回通用信息
        msg = ErrorCode.get_default_user_message(ErrorCode.SYSTEM_RESOURCE_EXHAUSTED)
        assert msg  # 不为空


class TestRumorJudgeException:
    """测试基础异常类"""

    def test_basic_exception(self):
        """测试基本异常"""
        exc = RumorJudgeException(
            message="测试错误",
            error_code=ErrorCode.SYSTEM_BUSY
        )

        assert exc.message == "测试错误"
        assert exc.error_code == ErrorCode.SYSTEM_BUSY
        assert exc.user_message is not None

    def test_exception_with_user_message(self):
        """测试自定义用户信息"""
        exc = RumorJudgeException(
            message="技术错误详情",
            error_code=ErrorCode.LLM_TIMEOUT,
            user_message="请稍后重试"
        )

        assert exc.message == "技术错误详情"
        assert exc.user_message == "请稍后重试"

    def test_exception_with_cause(self):
        """测试异常链"""
        original = ValueError("原始错误")
        exc = RumorJudgeException(
            message="包装错误",
            cause=original
        )

        assert exc.cause == original
        assert exc.__cause__ == original

    def test_to_dict(self):
        """测试转换为字典"""
        exc = RumorJudgeException(
            message="测试错误",
            error_code=ErrorCode.CACHE_TIMEOUT,
            user_message="系统繁忙",
            details={"key": "value"}
        )

        d = exc.to_dict(include_details=True)

        assert d["success"] == False
        assert d["error"]["code"] == "CACHE_002"
        assert d["error"]["message"] == "系统繁忙"
        assert d["error"]["details"]["key"] == "value"

    def test_to_dict_without_details(self):
        """测试转换时不包含详情"""
        exc = RumorJudgeException(
            message="测试错误",
            error_code=ErrorCode.CACHE_TIMEOUT,
            details={"secret": "value"}
        )

        d = exc.to_dict(include_details=False)

        assert "details" not in d["error"]

    def test_get_http_status(self):
        """测试 HTTP 状态码映射"""
        exc = RumorJudgeException(message="测试", error_code=ErrorCode.INVALID_INPUT)
        assert exc.get_http_status() == 400

        exc = RumorJudgeException(message="测试", error_code=ErrorCode.LLM_TIMEOUT)
        assert exc.get_http_status() == 503

        exc = RumorJudgeException(message="测试", error_code=ErrorCode.LLM_API_ERROR)
        assert exc.get_http_status() == 500


class TestSpecificExceptions:
    """测试具体异常类"""

    def test_cache_exception(self):
        """测试缓存异常"""
        exc = CacheException(
            message="缓存读取失败",
            cache_type="semantic"
        )

        assert exc.error_code == ErrorCode.CACHE_MISS
        assert exc.details.get("cache_type") == "semantic"

    def test_cache_miss_exception(self):
        """测试缓存未命中异常"""
        exc = CacheMissException()

        assert exc.error_code == ErrorCode.CACHE_MISS

    def test_web_search_exception(self):
        """测试网络搜索异常"""
        exc = WebSearchException(
            message="搜索失败",
            search_query="测试查询"
        )

        assert exc.error_code == ErrorCode.WEB_SEARCH_FAILED
        assert exc.details.get("search_query") == "测试查询"

    def test_llm_timeout_exception(self):
        """测试 LLM 超时异常"""
        exc = LLMTimeoutException()

        assert exc.error_code == ErrorCode.LLM_TIMEOUT

    def test_query_parse_exception(self):
        """测试查询解析异常"""
        exc = QueryParseException(
            message="解析失败",
            query="测试查询"
        )

        assert exc.error_code == ErrorCode.ANALYSIS_PARSE_ERROR
        assert exc.details.get("query") == "测试查询"


class TestHandleErrorsDecorator:
    """测试错误处理装饰器"""

    def test_handle_expected_exception(self):
        """测试处理预期异常"""
        @handle_errors(ValueError, fallback_value="fallback")
        def func():
            raise ValueError("预期错误")

        result = func()
        assert result == "fallback"

    def test_handle_with_reraise(self):
        """测试重抛异常"""
        @handle_errors(ValueError, reraise=True)
        def func():
            raise ValueError("预期错误")

        with pytest.raises(RumorJudgeException):
            func()

    def test_no_exception(self):
        """测试无异常情况"""
        @handle_errors(ValueError, fallback_value="fallback")
        def func():
            return "success"

        result = func()
        assert result == "success"

    def test_unexpected_exception(self):
        """测试未预期异常"""
        @handle_errors(ValueError, fallback_value="fallback")
        def func():
            raise RuntimeError("未预期错误")

        result = func()
        assert result == "fallback"

    def test_pass_through_rumor_judge_exception(self):
        """测试 RumorJudgeException 直接传递"""
        @handle_errors(ValueError, reraise=True)
        def func():
            raise CacheException("缓存错误")

        with pytest.raises(CacheException):
            func()


class TestRetryDecorator:
    """测试重试装饰器"""

    def test_retry_success(self):
        """测试重试成功"""
        call_count = [0]

        @retry_on_exception(ValueError, max_retries=3, delay=0.01)
        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("临时错误")
            return "success"

        result = func()
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_exhausted(self):
        """测试重试耗尽"""
        @retry_on_exception(ValueError, max_retries=2, delay=0.01)
        def func():
            raise ValueError("持续错误")

        with pytest.raises(ValueError):
            func()


class TestSafeExecute:
    """测试安全执行"""

    def test_successful_execution(self):
        """测试成功执行"""
        def add(a, b):
            return a + b

        result, error = safe_execute(add, 1, 2)
        assert result == 3
        assert error is None

    def test_failed_execution(self):
        """测试失败执行"""
        def divide(a, b):
            return a / b

        result, error = safe_execute(divide, 1, 0, default=None)
        assert result is None
        assert error is not None


class TestErrorContext:
    """测试错误上下文管理器"""

    def test_no_error(self):
        """测试无错误情况"""
        with ErrorContext("测试操作") as ctx:
            ctx.result = "success"

        assert ctx.error is None
        assert ctx.result == "success"

    def test_error_suppressed(self):
        """测试错误抑制"""
        with ErrorContext("测试操作", reraise=False) as ctx:
            raise ValueError("测试错误")

        assert ctx.error is not None
        assert isinstance(ctx.error, ValueError)

    def test_error_reraised(self):
        """测试错误重抛"""
        with pytest.raises(RumorJudgeException):
            with ErrorContext("测试操作", reraise=True):
                raise ValueError("测试错误")


class TestHandleExceptionFunction:
    """测试 handle_exception 函数"""

    def test_wrap_standard_exception(self):
        """测试包装标准异常"""
        original = ValueError("原始错误")
        wrapped = handle_exception(original, context="测试操作")

        assert isinstance(wrapped, RumorJudgeException)
        assert "测试操作" in wrapped.message or wrapped.details is not None

    def test_pass_through_custom_exception(self):
        """测试传递自定义异常"""
        original = CacheException("缓存错误")
        result = handle_exception(original)

        assert result is original

    def test_infer_error_code(self):
        """测试推断错误码"""
        # 超时
        exc = handle_exception(TimeoutError("超时"))
        assert exc.error_code == ErrorCode.LLM_TIMEOUT


class TestCreateExceptionFromError:
    """测试 create_exception_from_error 函数"""

    def test_create_from_error_code_enum(self):
        """测试从错误码枚举创建"""
        exc = create_exception_from_error(
            ErrorCode.LLM_TIMEOUT,
            "测试超时"
        )

        assert isinstance(exc, LLMException)
        assert exc.error_code == ErrorCode.LLM_TIMEOUT

    def test_create_from_string(self):
        """测试从字符串创建（向后兼容）"""
        exc = create_exception_from_error(
            "CacheException",
            "缓存错误"
        )

        assert isinstance(exc, CacheException)

    def test_unknown_error_code(self):
        """测试未知错误码"""
        with pytest.raises(ValueError):
            create_exception_from_error("UnknownCode", "测试")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
