"""
测试 API 监控回调处理器
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.outputs import LLMResult

from src.observability.api_monitor_callback import (
    APIMonitorCallbackHandler,
    get_api_monitor_callback
)


class TestAPIMonitorCallbackHandler:
    """测试 API 监控回调处理器"""

    def test_init(self):
        """测试初始化"""
        handler = APIMonitorCallbackHandler()
        assert handler._monitor is None

    def test_get_monitor_lazy_load(self):
        """测试延迟加载 API 监控器"""
        handler = APIMonitorCallbackHandler()

        # 第一次调用应该加载监控器
        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_monitor = Mock()
            mock_get.return_value = mock_monitor

            monitor = handler._get_monitor()
            assert monitor is mock_monitor
            mock_get.assert_called_once()

        # 第二次调用应该使用缓存的监控器
        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            monitor = handler._get_monitor()
            assert monitor is mock_monitor
            mock_get.assert_not_called()

    def test_get_monitor_failure(self):
        """测试监控器加载失败"""
        handler = APIMonitorCallbackHandler()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_get.side_effect = Exception("导入失败")

            # 第一次调用失败
            monitor = handler._get_monitor()
            assert monitor is None

            # 第二次调用应该返回 None（不再尝试）
            monitor = handler._get_monitor()
            assert monitor is None

    @pytest.fixture
    def mock_llm_result(self):
        """创建模拟的 LLM 结果"""
        def create_result(token_usage=None, model_name="qwen-plus"):
            llm_output = {}
            if token_usage:
                llm_output['token_usage'] = token_usage
            llm_output['model_name'] = model_name

            result = Mock(spec=LLMResult)
            result.llm_output = llm_output
            result.generations = [[]]
            return result
        return create_result

    def test_on_llm_end_with_tokens(self, mock_llm_result):
        """测试 LLM 结束回调（有 token 信息）"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.001
        handler._monitor = mock_monitor

        # 创建带有 token 信息的响应
        token_usage = {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150
        }
        response = mock_llm_result(token_usage)

        # 调用回调
        handler.on_llm_end(response)

        # 验证 API 调用被记录
        mock_monitor.record_api_call.assert_called_once_with(
            provider='dashscope',
            model='qwen-plus',
            endpoint='chat',
            input_tokens=100,
            output_tokens=50
        )

    def test_on_llm_end_with_alternative_token_names(self, mock_llm_result):
        """测试使用替代 token 字段名"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.001
        handler._monitor = mock_monitor

        # 使用替代字段名
        token_usage = {
            'input_tokens': 80,
            'output_tokens': 40
        }
        response = mock_llm_result(token_usage)

        handler.on_llm_end(response)

        mock_monitor.record_api_call.assert_called_once_with(
            provider='dashscope',
            model='qwen-plus',
            endpoint='chat',
            input_tokens=80,
            output_tokens=40
        )

    def test_on_llm_end_with_completion_count(self, mock_llm_result):
        """测试使用 completion_count 字段"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.001
        handler._monitor = mock_monitor

        token_usage = {
            'prompt_count': 60,
            'completion_count': 30
        }
        response = mock_llm_result(token_usage)

        handler.on_llm_end(response)

        mock_monitor.record_api_call.assert_called_once_with(
            provider='dashscope',
            model='qwen-plus',
            endpoint='chat',
            input_tokens=60,
            output_tokens=30
        )

    def test_on_llm_end_without_token_info(self, mock_llm_result):
        """测试没有 token 信息的情况"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        handler._monitor = mock_monitor

        response = mock_llm_result({})

        handler.on_llm_end(response)

        # 不应该记录 API 调用
        mock_monitor.record_api_call.assert_not_called()

    def test_on_llm_end_with_zero_total_tokens(self, mock_llm_result):
        """测试 total_tokens 为 0 但有显式 token 字段的情况"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0
        handler._monitor = mock_monitor

        # 当 token_usage 字段存在（即使值为 0），会记录
        token_usage = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        response = mock_llm_result(token_usage, model_name="test-model")
        response.generations = []  # 空 generations，无法估算

        handler.on_llm_end(response)

        # 应该记录 API 调用（即使 tokens 为 0）
        mock_monitor.record_api_call.assert_called_once_with(
            provider='dashscope',
            model='test-model',
            endpoint='chat',
            input_tokens=0,
            output_tokens=0
        )

    def test_on_llm_end_without_monitor(self, mock_llm_result):
        """测试没有监控器的情况"""
        handler = APIMonitorCallbackHandler()
        # _monitor 为 None

        token_usage = {
            'prompt_tokens': 100,
            'completion_tokens': 50
        }
        response = mock_llm_result(token_usage)

        # 不应该抛出异常
        handler.on_llm_end(response)

    def test_on_llm_end_with_exception(self, mock_llm_result):
        """测试记录时抛出异常"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.side_effect = Exception("记录失败")
        handler._monitor = mock_monitor

        token_usage = {
            'prompt_tokens': 100,
            'completion_tokens': 50
        }
        response = mock_llm_result(token_usage)

        # 不应该抛出异常
        handler.on_llm_end(response)

    def test_on_llm_end_calculates_total_tokens(self, mock_llm_result):
        """测试计算 total_tokens"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.002
        handler._monitor = mock_monitor

        # 只提供 input 和 output tokens
        token_usage = {
            'prompt_tokens': 120,
            'completion_tokens': 60
        }
        response = mock_llm_result(token_usage)

        handler.on_llm_end(response)

        # 应该正确计算和传递
        mock_monitor.record_api_call.assert_called_once()
        call_args = mock_monitor.record_api_call.call_args
        assert call_args.kwargs['input_tokens'] == 120
        assert call_args.kwargs['output_tokens'] == 60

    def test_on_llm_end_with_unknown_model(self, mock_llm_result):
        """测试未知模型名称"""
        handler = APIMonitorCallbackHandler()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.001
        handler._monitor = mock_monitor

        response = mock_llm_result({}, model_name=None)

        handler.on_llm_end(response)

        # 由于没有 token 信息，不会记录
        mock_monitor.record_api_call.assert_not_called()


class TestGetApiMonitorCallback:
    """测试获取 API 监控回调处理器"""

    def test_get_api_monitor_callback(self):
        """测试获取回调处理器实例"""
        callback = get_api_monitor_callback()
        assert isinstance(callback, APIMonitorCallbackHandler)

    def test_get_api_monitor_callback_singleton(self):
        """测试每次调用返回新实例"""
        callback1 = get_api_monitor_callback()
        callback2 = get_api_monitor_callback()

        # 不是单例，每次返回新实例
        assert callback1 is not callback2
        assert isinstance(callback1, APIMonitorCallbackHandler)
        assert isinstance(callback2, APIMonitorCallbackHandler)
