"""
上下文压缩器

智能压缩LLM请求的上下文，以避免token超限错误
"""
import logging
from typing import List, Dict, Tuple
import re

logger = logging.getLogger("ContextCompressor")


class ContextCompressor:
    """
    上下文压缩器

    功能：
    1. 压缩证据文本（保留关键信息）
    2. 压缩系统提示词（保留核心指令）
    3. 减少证据数量（保留最相关的）
    """

    def __init__(self):
        self.max_evidence_length = 500  # 单条证据最大字符数
        self.min_evidence_length = 100  # 单条证据最小字符数

    def compress_evidence_text(self, evidence_text: str, target_length: int = 300) -> str:
        """
        压缩单条证据文本

        策略：
        1. 保留开头和结尾
        2. 保留关键句子
        3. 去除冗余信息

        Args:
            evidence_text: 证据文本
            target_length: 目标长度

        Returns:
            压缩后的文本
        """
        if len(evidence_text) <= target_length:
            return evidence_text

        # 分割成句子
        sentences = re.split(r'[。！？；\n]', evidence_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 2:
            # 太短，直接截断
            return evidence_text[:target_length] + "..."

        # 保留首尾句子，中间压缩
        first = sentences[0]
        last = sentences[-1]
        middle = ' '.join(sentences[1:-1])

        # 计算可用长度
        available = target_length - len(first) - len(last) - 10  # 10字符用于连接符

        if available <= 0:
            # 空间不够，只返回开头
            return first[:target_length-3] + "..."

        # 压缩中间部分
        if len(middle) > available:
            middle = middle[:available-3] + "..."

        return f"{first} {middle} {last}"

    def compress_evidence_list(
        self,
        evidence_list: List[Dict],
        max_count: int = 3,
        target_length: int = 300
    ) -> List[Dict]:
        """
        压缩证据列表

        策略：
        1. 限制证据数量
        2. 压缩每条证据的文本

        Args:
            evidence_list: 证据列表
            max_count: 最大证据数量
            target_length: 单条证据目标长度

        Returns:
            压缩后的证据列表
        """
        # 1. 限制数量
        if len(evidence_list) > max_count:
            logger.info(f"证据数量压缩: {len(evidence_list)} -> {max_count}")
            evidence_list = evidence_list[:max_count]

        # 2. 压缩每条证据的文本
        compressed = []
        for ev in evidence_list:
            compressed_ev = ev.copy()
            original_text = ev.get('text', '')
            compressed_text = self.compress_evidence_text(original_text, target_length)

            compressed_ev['text'] = compressed_text
            compressed_ev['original_length'] = len(original_text)
            compressed_ev['compressed_length'] = len(compressed_text)

            if len(compressed_text) < len(original_text):
                logger.info(f"证据文本压缩: {len(original_text)} -> {len(compressed_text)} 字符")

            compressed.append(compressed_ev)

        return compressed

    def compress_prompt(self, prompt_template: str, max_length: int = 1000) -> str:
        """
        压缩系统提示词

        策略：
        1. 保留核心指令
        2. 去除示例（Few-Shot）
        3. 简化描述

        Args:
            prompt_template: 提示词模板
            max_length: 最大长度

        Returns:
            压缩后的提示词
        """
        if len(prompt_template) <= max_length:
            return prompt_template

        # 移除Few-Shot示例
        lines = prompt_template.split('\n')
        essential_lines = []
        in_example = False

        for line in lines:
            # 检测是否进入示例区域
            if '示例' in line or 'Example' in line or 'example' in line:
                in_example = True
                continue

            # 跳过示例内容
            if in_example:
                if line.strip() and not line.startswith(' '):
                    in_example = False
                else:
                    continue

            essential_lines.append(line)

        compressed = '\n'.join(essential_lines)

        # 如果还是太长，截断
        if len(compressed) > max_length:
            compressed = compressed[:max_length-3] + "..."

        logger.info(f"提示词压缩: {len(prompt_template)} -> {len(compressed)} 字符")
        return compressed

    def estimate_token_count(self, text: str) -> int:
        """
        估算token数量（粗略估计：中文1字符≈1.5 token，英文1词≈1 token）

        Args:
            text: 文本

        Returns:
            估算的token数
        """
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 统计英文单词
        english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))

        return int(chinese_chars * 1.5 + english_words)


def should_compress_context(error: Exception) -> bool:
    """
    判断是否需要压缩上下文

    Args:
        error: 异常对象

    Returns:
        是否需要压缩
    """
    from src.utils.error_parser import parse_llm_error

    parsed = parse_llm_error(error)
    return parsed.should_compress_context()
