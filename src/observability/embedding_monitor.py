"""
Embedding 调用监控模块

监控向量嵌入调用的 token 使用量和成本。
"""
import logging
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("EmbeddingMonitor")


class EmbeddingMonitorCallback(BaseCallbackHandler):
    """
    Embedding 调用监控回调

    功能：
    1. 记录 Embedding 调用次数
    2. 估算 token 使用量
    3. 计算并记录成本
    """

    def __init__(self):
        super().__init__()
        self._monitor = None
        self._pending_texts: Dict[str, List[str]] = {}

    @property
    def monitor(self):
        """延迟获取监控器"""
        if self._monitor is None:
            try:
                from src.observability.api_monitor import get_api_monitor
                self._monitor = get_api_monitor()
            except Exception as e:
                logger.warning(f"无法获取 API 监控器: {e}")
        return self._monitor

    def on_embed_documents_start(
        self,
        serialized: Dict[str, Any],
        texts: List[str],
        **kwargs
    ) -> None:
        """Embedding 批量调用开始"""
        run_id = str(kwargs.get("run_id", id(texts)))
        self._pending_texts[run_id] = texts
        logger.debug(f"Embedding 开始: {len(texts)} 个文本")

    def on_embed_documents_end(
        self,
        embeddings: List[List[float]],
        texts: List[str],
        **kwargs
    ) -> None:
        """Embedding 批量调用结束"""
        run_id = str(kwargs.get("run_id", ""))

        # 获取记录的文本数量
        pending = self._pending_texts.pop(run_id, texts)
        actual_texts = pending if pending else texts

        # 估算 token 数量（中文约 1.5 字符/token，英文约 4 字符/token）
        estimated_tokens = 0
        for text in actual_texts:
            # 简单估算：中文按1.5，其他按4
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            estimated_tokens += int(chinese_chars / 1.5 + other_chars / 4)

        if self.monitor:
            try:
                cost = self.monitor.record_api_call(
                    provider='dashscope',
                    model='text-embedding-v4',
                    endpoint='embeddings',
                    input_tokens=estimated_tokens,
                    output_tokens=0
                )

                logger.info(
                    f"Embedding 完成: {len(actual_texts)} 个文本, "
                    f"~{estimated_tokens} tokens, cost={cost:.6f}元"
                )
            except Exception as e:
                logger.error(f"记录 Embedding 调用失败: {e}")
        else:
            logger.debug(f"Embedding 完成: {len(actual_texts)} 个文本")

        # 清理
        self._pending_texts.pop(run_id, None)

    def on_embed_documents_error(
        self,
        error: Exception,
        texts: List[str],
        **kwargs
    ) -> None:
        """Embedding 调用错误"""
        run_id = str(kwargs.get("run_id", ""))
        logger.error(f"Embedding 失败: {len(texts)} 个文本, error={error}")

        # 清理
        self._pending_texts.pop(run_id, None)

    def on_embed_query_start(
        self,
        serialized: Dict[str, Any],
        text: str,
        **kwargs
    ) -> None:
        """单个查询 Embedding 开始"""
        logger.debug(f"Embedding 查询开始: {text[:50]}...")

    def on_embed_query_end(
        self,
        embedding: List[float],
        text: str,
        **kwargs
    ) -> None:
        """单个查询 Embedding 结束"""
        # 估算 token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        estimated_tokens = int(chinese_chars / 1.5 + other_chars / 4)

        if self.monitor:
            try:
                cost = self.monitor.record_api_call(
                    provider='dashscope',
                    model='text-embedding-v4',
                    endpoint='embeddings',
                    input_tokens=estimated_tokens,
                    output_tokens=0
                )
                logger.debug(f"Embedding 查询完成: ~{estimated_tokens} tokens, cost={cost:.6f}元")
            except Exception as e:
                logger.error(f"记录 Embedding 查询失败: {e}")


# 全局实例
_embedding_callback: Optional[EmbeddingMonitorCallback] = None


def get_embedding_monitor_callback() -> EmbeddingMonitorCallback:
    """获取全局 Embedding 监控回调"""
    global _embedding_callback
    if _embedding_callback is None:
        _embedding_callback = EmbeddingMonitorCallback()
    return _embedding_callback
