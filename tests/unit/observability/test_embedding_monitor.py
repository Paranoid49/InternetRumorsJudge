"""
测试 Embedding 监控回调处理器

测试覆盖：
- 初始化
- Embedding 批量调用开始/结束/错误回调
- 单个查询 Embedding 开始/结束回调
- Token 估算逻辑
- 监控器延迟加载
"""
import pytest
from unittest.mock import Mock, patch

from src.observability.embedding_monitor import (
    EmbeddingMonitorCallback,
    get_embedding_monitor_callback
)


class TestEmbeddingMonitorCallbackInit:
    """测试初始化"""

    def test_init_default_values(self):
        """测试默认初始化值"""
        callback = EmbeddingMonitorCallback()
        assert callback._monitor is None
        assert callback._pending_texts == {}

    def test_inherits_from_base_callback(self):
        """测试继承自 BaseCallbackHandler"""
        from langchain_core.callbacks import BaseCallbackHandler
        callback = EmbeddingMonitorCallback()
        assert isinstance(callback, BaseCallbackHandler)


class TestMonitorProperty:
    """测试监控器属性"""

    def test_monitor_lazy_load(self):
        """测试监控器延迟加载"""
        callback = EmbeddingMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_monitor = Mock()
            mock_get.return_value = mock_monitor

            monitor = callback.monitor
            assert monitor is mock_monitor
            mock_get.assert_called_once()

    def test_monitor_cached(self):
        """测试监控器缓存"""
        callback = EmbeddingMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_monitor = Mock()
            mock_get.return_value = mock_monitor

            _ = callback.monitor
            _ = callback.monitor

            mock_get.assert_called_once()

    def test_monitor_load_failure(self):
        """测试监控器加载失败"""
        callback = EmbeddingMonitorCallback()

        with patch('src.observability.api_monitor.get_api_monitor') as mock_get:
            mock_get.side_effect = Exception("导入失败")

            monitor = callback.monitor
            assert monitor is None


class TestOnEmbedDocumentsStart:
    """测试批量 Embedding 开始回调"""

    def test_on_embed_documents_start_stores_texts(self):
        """测试存储文本"""
        callback = EmbeddingMonitorCallback()

        callback.on_embed_documents_start(
            serialized={},
            texts=["文本1", "文本2"],
            run_id="test-start-1"
        )

        assert "test-start-1" in callback._pending_texts
        assert len(callback._pending_texts["test-start-1"]) == 2

    def test_on_embed_documents_start_without_run_id(self):
        """测试没有 run_id"""
        callback = EmbeddingMonitorCallback()

        callback.on_embed_documents_start(
            serialized={},
            texts=["测试文本"]
        )

        # 应该存储了一些内容
        assert len(callback._pending_texts) > 0


class TestOnEmbedDocumentsEnd:
    """测试批量 Embedding 结束回调"""

    def test_on_embed_documents_end_with_monitor(self):
        """测试有监控器的结束回调"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0001
        callback._monitor = mock_monitor

        # 先调用 start
        callback.on_embed_documents_start(
            serialized={},
            texts=["这是中文测试"],
            run_id="test-end-1"
        )

        # 调用 end
        embeddings = [[0.1, 0.2, 0.3]]
        callback.on_embed_documents_end(
            embeddings=embeddings,
            texts=["这是中文测试"],
            run_id="test-end-1"
        )

        # 验证记录
        mock_monitor.record_api_call.assert_called_once()
        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        assert call_kwargs['provider'] == 'dashscope'
        assert call_kwargs['model'] == 'text-embedding-v4'
        assert call_kwargs['endpoint'] == 'embeddings'
        assert call_kwargs['input_tokens'] > 0
        assert call_kwargs['output_tokens'] == 0

    def test_on_embed_documents_end_cleans_up(self):
        """测试清理"""
        callback = EmbeddingMonitorCallback()

        callback.on_embed_documents_start(
            serialized={},
            texts=["测试"],
            run_id="test-cleanup"
        )

        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=["测试"],
            run_id="test-cleanup"
        )

        assert "test-cleanup" not in callback._pending_texts

    def test_on_embed_documents_end_without_monitor(self):
        """测试没有监控器"""
        callback = EmbeddingMonitorCallback()
        # _monitor 为 None

        callback.on_embed_documents_start(
            serialized={},
            texts=["测试"],
            run_id="test-no-monitor"
        )

        # 不应该抛出异常
        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=["测试"],
            run_id="test-no-monitor"
        )

    def test_on_embed_documents_end_recording_failure(self):
        """测试记录失败"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.side_effect = Exception("记录失败")
        callback._monitor = mock_monitor

        callback.on_embed_documents_start(
            serialized={},
            texts=["测试"],
            run_id="test-fail"
        )

        # 不应该抛出异常
        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=["测试"],
            run_id="test-fail"
        )

    def test_token_estimation_chinese(self):
        """测试中文 token 估算"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0
        callback._monitor = mock_monitor

        # 纯中文文本
        callback.on_embed_documents_start(
            serialized={},
            texts=["这是一段中文文本"],
            run_id="test-chinese"
        )

        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=["这是一段中文文本"],
            run_id="test-chinese"
        )

        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        # 中文约 1.5 字符/token
        # 8 个中文字符 / 1.5 ≈ 5 tokens
        assert call_kwargs['input_tokens'] > 0

    def test_token_estimation_english(self):
        """测试英文 token 估算"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0
        callback._monitor = mock_monitor

        # 纯英文文本
        english_text = "Hello World Test"
        callback.on_embed_documents_start(
            serialized={},
            texts=[english_text],
            run_id="test-english"
        )

        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=[english_text],
            run_id="test-english"
        )

        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        # 英文约 4 字符/token
        # 17 个字符 / 4 ≈ 4 tokens
        assert call_kwargs['input_tokens'] > 0

    def test_token_estimation_mixed(self):
        """测试混合文本 token 估算"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0
        callback._monitor = mock_monitor

        # 混合文本
        mixed_text = "Hello世界Test测试"
        callback.on_embed_documents_start(
            serialized={},
            texts=[mixed_text],
            run_id="test-mixed"
        )

        callback.on_embed_documents_end(
            embeddings=[[0.1]],
            texts=[mixed_text],
            run_id="test-mixed"
        )

        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        assert call_kwargs['input_tokens'] > 0


class TestOnEmbedDocumentsError:
    """测试批量 Embedding 错误回调"""

    def test_on_embed_documents_error_logs_and_cleans(self):
        """测试错误日志和清理"""
        callback = EmbeddingMonitorCallback()

        callback.on_embed_documents_start(
            serialized={},
            texts=["测试"],
            run_id="test-error-1"
        )

        callback.on_embed_documents_error(
            error=ValueError("测试错误"),
            texts=["测试"],
            run_id="test-error-1"
        )

        assert "test-error-1" not in callback._pending_texts


class TestOnEmbedQueryStart:
    """测试单个查询 Embedding 开始"""

    def test_on_embed_query_start(self):
        """测试查询开始"""
        callback = EmbeddingMonitorCallback()

        # 不应该抛出异常
        callback.on_embed_query_start(
            serialized={},
            text="这是一个测试查询"
        )


class TestOnEmbedQueryEnd:
    """测试单个查询 Embedding 结束"""

    def test_on_embed_query_end_with_monitor(self):
        """测试有监控器的查询结束"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.return_value = 0.0001
        callback._monitor = mock_monitor

        callback.on_embed_query_end(
            embedding=[0.1, 0.2, 0.3],
            text="测试查询"
        )

        mock_monitor.record_api_call.assert_called_once()
        call_kwargs = mock_monitor.record_api_call.call_args.kwargs
        assert call_kwargs['endpoint'] == 'embeddings'
        assert call_kwargs['output_tokens'] == 0

    def test_on_embed_query_end_without_monitor(self):
        """测试没有监控器"""
        callback = EmbeddingMonitorCallback()
        # _monitor 为 None

        # 不应该抛出异常
        callback.on_embed_query_end(
            embedding=[0.1],
            text="测试查询"
        )

    def test_on_embed_query_end_recording_failure(self):
        """测试记录失败"""
        callback = EmbeddingMonitorCallback()
        mock_monitor = Mock()
        mock_monitor.record_api_call.side_effect = Exception("记录失败")
        callback._monitor = mock_monitor

        # 不应该抛出异常
        callback.on_embed_query_end(
            embedding=[0.1],
            text="测试查询"
        )


class TestGetEmbeddingMonitorCallback:
    """测试获取全局回调"""

    def test_returns_callback_instance(self):
        """测试返回回调实例"""
        # 重置全局实例
        import src.observability.embedding_monitor as module
        module._embedding_callback = None

        callback = get_embedding_monitor_callback()
        assert isinstance(callback, EmbeddingMonitorCallback)

    def test_singleton_behavior(self):
        """测试单例行为"""
        # 重置全局实例
        import src.observability.embedding_monitor as module
        module._embedding_callback = None

        callback1 = get_embedding_monitor_callback()
        callback2 = get_embedding_monitor_callback()

        assert callback1 is callback2
