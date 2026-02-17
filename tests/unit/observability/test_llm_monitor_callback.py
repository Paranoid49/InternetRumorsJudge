"""
测试 LLM 监控回调处理器

测试覆盖：
- 初始化
- LLM 调用开始/结束/错误回调
- Token 使用量提取（多种格式）
- 监控器延迟加载
"""
import pytest
import time
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from src.observability.llm_monitor_callback import (
    LLMMonitorCallback,
    get_llm_monitor_callback
)


class TestLLMMonitorCallbackInit:
    """测试初始化"""

    def test_init_default_values(self):
        """测试默认初始化值"""
        callback = LLMMonitorCallback()
        assert callback._monitor is None
        assert callback._start_times == {}
        assert callback._current_model == {}
        assert callback._call_context == {}

    def test_inherits_from_base_callback(self):
        """测试继承自 BaseCallbackHandler"""
        from langchain_core.callbacks import BaseCallbackHandler
        callback = LLMMonitorCallback()
        assert isinstance(callback, BaseCallbackHandler)


class TestMonitorProperty:
    """测试监控器属性"""

    def test_monitor_lazy_load(self):
        """测试监控器延迟加载"""
        callback = LLMMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_monitor = Mock()
            mock_get.return_value = mock_monitor

            monitor = callback.monitor
            assert monitor is mock_monitor
            mock_get.assert_called_once()

    def test_monitor_cached(self):
        """测试监控器缓存"""
        callback = LLMMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_monitor = Mock()
            mock_get.return_value = mock_monitor

            # 第一次调用
            _ = callback.monitor
            # 第二次调用（应该使用缓存）
            _ = callback.monitor

            # 只调用一次
            mock_get.assert_called_once()

    def test_monitor_load_failure(self):
        """测试监控器加载失败"""
        callback = LLMMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_get.side_effect = Exception("导入失败")

            monitor = callback.monitor
            assert monitor is None


class TestOnLLMStart:
    """测试 LLM 调用开始回调"""

    def test_on_llm_start_basic(self):
        """测试基本开始回调"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={"name": "test"},
            prompts=["Hello"],
            run_id="test-run-1"
        )

        assert "test-run-1" in callback._start_times
        assert "test-run-1" in callback._current_model
        assert "test-run-1" in callback._call_context

    def test_on_llm_start_extracts_model_name(self):
        """测试提取模型名称"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Hello"],
            invocation_params={"model": "qwen-plus"},
            run_id="test-run-2"
        )

        assert callback._current_model["test-run-2"] == "qwen-plus"

    def test_on_llm_start_extracts_model_name_alternative(self):
        """测试使用 model_name 字段"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Hello"],
            invocation_params={"model_name": "qwen-turbo"},
            run_id="test-run-3"
        )

        assert callback._current_model["test-run-3"] == "qwen-turbo"

    def test_on_llm_start_records_context(self):
        """测试记录上下文"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Hello", "World"],
            run_id="test-run-4"
        )

        context = callback._call_context["test-run-4"]
        assert context["prompts_count"] == 2
        assert context["prompts_length"] == 10  # len("Hello") + len("World")

    def test_on_llm_start_without_run_id(self):
        """测试没有 run_id 的情况"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Test"]
        )

        # 应该记录了一些内容
        assert len(callback._start_times) > 0


class TestOnLLMEnd:
    """测试 LLM 调用结束回调"""

    def test_on_llm_end_with_token_usage(self):
        """测试有 token 使用量的结束回调"""
        callback = LLMMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.001
        callback._monitor = mock_monitor

        # 先调用 start
        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            invocation_params={"model": "qwen-plus"},
            run_id="test-end-1"
        )

        # 创建响应
        response = Mock()
        response.usage_metadata = {
            'input_tokens': 100,
            'output_tokens': 50,
            'total_tokens': 150
        }

        callback.on_llm_end(response, run_id="test-end-1")

        # 验证记录
        mock_monitor.record_api_call.assert_called_once()
        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        assert call_kwargs['model'] == 'qwen-plus'
        assert call_kwargs['input_tokens'] == 100
        assert call_kwargs['output_tokens'] == 50

    def test_on_llm_end_cleans_up(self):
        """测试结束回调清理状态"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            run_id="test-cleanup"
        )

        response = Mock()
        response.usage_metadata = {}

        callback.on_llm_end(response, run_id="test-cleanup")

        # 清理后应该没有记录
        assert "test-cleanup" not in callback._start_times
        assert "test-cleanup" not in callback._current_model
        assert "test-cleanup" not in callback._call_context

    def test_on_llm_end_without_monitor(self):
        """测试没有监控器的结束回调"""
        callback = LLMMonitorCallback()
        # _monitor 为 None

        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            run_id="test-no-monitor"
        )

        response = Mock()
        response.usage_metadata = {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}

        # 不应该抛出异常
        callback.on_llm_end(response, run_id="test-no-monitor")

    def test_on_llm_end_recording_failure(self):
        """测试记录失败"""
        callback = LLMMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.side_effect = Exception("记录失败")
        callback._monitor = mock_monitor

        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            run_id="test-fail"
        )

        response = Mock()
        response.usage_metadata = {'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150}

        # 不应该抛出异常
        callback.on_llm_end(response, run_id="test-fail")


class TestOnLLMError:
    """测试 LLM 调用错误回调"""

    def test_on_llm_error_logs_error(self):
        """测试错误回调记录日志"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            invocation_params={"model": "qwen-plus"},
            run_id="test-error-1"
        )

        error = ValueError("测试错误")
        callback.on_llm_error(error, run_id="test-error-1")

        # 验证清理
        assert "test-error-1" not in callback._start_times
        assert "test-error-1" not in callback._current_model

    def test_on_llm_error_cleans_up(self):
        """测试错误回调清理状态"""
        callback = LLMMonitorCallback()

        callback.on_llm_start(
            serialized={},
            prompts=["Test"],
            run_id="test-error-cleanup"
        )

        callback.on_llm_error(Exception("错误"), run_id="test-error-cleanup")

        assert "test-error-cleanup" not in callback._start_times


class TestExtractTokenUsage:
    """测试 Token 使用量提取"""

    def test_extract_from_usage_metadata(self):
        """测试从 usage_metadata 提取"""
        callback = LLMMonitorCallback()

        response = Mock()
        response.usage_metadata = {
            'input_tokens': 100,
            'output_tokens': 50,
            'total_tokens': 150
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 100
        assert result['output_tokens'] == 50
        assert result['total_tokens'] == 150

    def test_extract_from_usage_metadata_alternative_names(self):
        """测试替代字段名"""
        callback = LLMMonitorCallback()

        response = Mock()
        response.usage_metadata = {
            'prompt_tokens': 80,
            'completion_tokens': 40,
            'total_tokens': 120
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 80
        assert result['output_tokens'] == 40

    def test_extract_from_response_metadata(self):
        """测试从 response_metadata 提取"""
        callback = LLMMonitorCallback()

        response = Mock()
        response.usage_metadata = None
        response.response_metadata = {
            'token_usage': {
                'input_tokens': 200,
                'output_tokens': 100,
                'total_tokens': 300
            }
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 200
        assert result['total_tokens'] == 300

    def test_extract_from_response_metadata_direct(self):
        """测试从 response_metadata 直接提取"""
        callback = LLMMonitorCallback()

        response = Mock()
        response.usage_metadata = None
        response.response_metadata = {
            'input_tokens': 150,
            'output_tokens': 75
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 150
        assert result['output_tokens'] == 75

    def test_extract_from_dict_format(self):
        """测试从字典格式提取"""
        callback = LLMMonitorCallback()

        response = {
            'usage': {
                'prompt_tokens': 90,
                'completion_tokens': 45,
                'total_tokens': 135
            }
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 90
        assert result['output_tokens'] == 45

    def test_extract_from_dict_token_usage(self):
        """测试从字典的 token_usage 提取"""
        callback = LLMMonitorCallback()

        response = {
            'token_usage': {
                'input_tokens': 70,
                'output_tokens': 35
            }
        }

        result = callback._extract_token_usage(response)
        assert result['input_tokens'] == 70

    def test_extract_returns_none_for_invalid_format(self):
        """测试无效格式返回 None"""
        callback = LLMMonitorCallback()

        response = Mock()
        response.usage_metadata = None
        response.response_metadata = {}

        result = callback._extract_token_usage(response)
        assert result is None

    def test_extract_handles_exception(self):
        """测试异常处理"""
        callback = LLMMonitorCallback()

        # 创建一个会抛出异常的响应
        response = Mock()
        type(response).usage_metadata = PropertyMock(side_effect=Exception("属性错误"))

        result = callback._extract_token_usage(response)
        assert result is None


class TestGetLLMMonitorCallback:
    """测试获取全局回调"""

    def test_returns_callback_instance(self):
        """测试返回回调实例"""
        # 重置全局实例
        import src.observability.llm_monitor_callback as module
        module._llm_callback = None

        callback = get_llm_monitor_callback()
        assert isinstance(callback, LLMMonitorCallback)

    def test_singleton_behavior(self):
        """测试单例行为"""
        # 重置全局实例
        import src.observability.llm_monitor_callback as module
        module._llm_callback = None

        callback1 = get_llm_monitor_callback()
        callback2 = get_llm_monitor_callback()

        assert callback1 is callback2
