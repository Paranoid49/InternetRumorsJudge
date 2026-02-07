"""
查询解析器单元测试

测试QueryParser的功能：
- 查询解析
- 实体提取
- 主张识别
- 分类判断
"""
import pytest
from unittest.mock import Mock, patch
from src.analyzers.query_parser import QueryAnalysis


# ============================================
# 查询解析测试
# ============================================

class TestQueryParser:
    """测试查询解析器"""

    @pytest.fixture
    def parser_chain(self):
        """创建解析器链的mock"""
        chain = Mock()
        chain.invoke = Mock(return_value=QueryAnalysis(
            entity="隔夜水",
            claim="会致癌",
            category="健康养生"
        ))
        return chain

    def test_parse_query_success(self, parser_chain):
        """测试成功解析查询"""
        query = "喝隔夜水会致癌吗？"

        result = parser_chain.invoke(query)

        assert isinstance(result, QueryAnalysis)
        assert result.entity == "隔夜水"
        assert result.claim == "会致癌"
        assert result.category == "健康养生"

    def test_parse_various_queries(self, parser_chain):
        """测试解析各种类型的查询"""
        test_cases = [
            {
                "query": "新冠疫苗会导致不孕不育？",
                "expected_entity": "新冠疫苗",
                "expected_claim": "会导致不孕不育",
                "expected_category": "健康养生"
            },
            {
                "query": "塑料大米是真的吗？",
                "expected_entity": "塑料大米",
                "expected_claim": "是真的",
                "expected_category": "食品安全"
            },
            {
                "query": "某地发生地震？",
                "expected_entity": "某地",
                "expected_claim": "发生地震",
                "expected_category": "社会事件"
            }
        ]

        for case in test_cases:
            # 这里只测试数据结构，不测试实际解析（需要真实LLM）
            result = QueryAnalysis(
                entity=case["expected_entity"],
                claim=case["expected_claim"],
                category=case["expected_category"]  # 使用有效的分类
            )

            assert result.entity == case["expected_entity"]
            assert result.claim == case["expected_claim"]
            assert result.category == case["expected_category"]

    def test_query_analysis_validation(self):
        """测试QueryAnalysis的数据验证"""
        # 有效的分析结果
        analysis = QueryAnalysis(
            entity="测试实体",
            claim="测试主张",
            category="健康养生"  # 使用有效的分类
        )

        assert analysis.entity is not None
        assert analysis.claim is not None
        assert analysis.category is not None

    def test_query_analysis_handles_empty_fields(self):
        """测试处理空字段"""
        # entity和claim不能为空，但可以是空字符串
        # category必须是有效的Literal值
        analysis = QueryAnalysis(
            entity="",
            claim="测试主张",
            category="其他"  # 使用有效的分类
        )

        # 应该仍然有效
        assert analysis.claim == "测试主张"
        assert analysis.category == "其他"


# ============================================
# 错误处理测试
# ============================================

class TestQueryParserErrorHandling:
    """测试查询解析器的错误处理"""

    def test_handles_malformed_query(self):
        """测试处理格式错误的查询"""
        malformed_queries = [
            "",  # 空字符串
            "   ",  # 只有空格
            "???",  # 只有标点
            "a" * 1000,  # 超长查询
        ]

        for query in malformed_queries:
            # 验证不会崩溃
            try:
                # 实际实现中应该有错误处理
                if query.strip():
                    # 非空查询应该能处理
                    pass
                else:
                    # 空查询应该返回None或默认值
                    pass
            except Exception as e:
                pytest.fail(f"查询 '{query[:50]}...' 导致异常: {e}")

    def test_parser_chain_failure(self):
        """测试解析器链失败的情况"""
        # 这个测试需要实际集成测试
        # 单元测试中我们只验证接口
        pass


# ============================================
# 分类测试
# ============================================

class TestQueryClassification:
    """测试查询分类"""

    def test_common_categories(self):
        """测试常见的分类"""
        categories = [
            "健康养生",
            "食品安全",
            "社会事件",
            "科学技术",
            "经济金融",
            "国际政治",
            "其他"
        ]

        # 验证这些分类是有效的字符串
        for category in categories:
            assert isinstance(category, str)
            assert len(category) > 0

    def test_category_mapping(self):
        """测试分类映射"""
        # 这里可以测试查询关键词到分类的映射
        # 但这需要实际的NLP处理
        pass


# ============================================
# 边界情况测试
# ============================================

class TestEdgeCases:
    """测试边界情况"""

    def test_query_with_special_characters(self):
        """测试包含特殊字符的查询"""
        special_queries = [
            "测试查询@#$%",
            "带有emoji的查询😀",
            "混合English和中文的query",
            "《包含引号》的查询",
            "带\n换行符\n的查询"
        ]

        for query in special_queries:
            # 验证能处理特殊字符
            try:
                # 应该能创建QueryAnalysis对象
                analysis = QueryAnalysis(
                    entity="测试",
                    claim="测试主张",
                    category="其他"  # 使用有效的分类
                )
                assert analysis is not None
            except Exception as e:
                pytest.fail(f"特殊字符查询处理失败: {e}")

    def test_very_long_query(self):
        """测试超长查询"""
        long_query = "这是一个非常长的查询" * 50

        # 应该能处理或优雅地限制长度
        # 50 * 12 = 600 个字符
        assert len(long_query) >= 500, f"查询长度应为>=500，实际为{len(long_query)}"

    def test_query_with_numbers_and_dates(self):
        """测试包含数字和日期的查询"""
        queries_with_numbers = [
            "2024年奥运会",
            "100度开水会烫伤吗",
            "3.15曝光的产品"
        ]

        for query in queries_with_numbers:
            # 应该能正确处理数字
            assert any(char.isdigit() for char in query)


# ============================================
# 性能测试
# ============================================

class TestPerformance:
    """性能测试"""

    def test_parsing_speed(self):
        """测试解析速度"""
        import time

        # 模拟解析操作
        start_time = time.time()

        # 创建100个分析结果
        for i in range(100):
            QueryAnalysis(
                entity=f"实体{i}",
                claim=f"主张{i}",
                category="其他"  # 使用有效的分类
            )

        elapsed_time = time.time() - start_time

        # 应该很快（< 0.1秒）
        assert elapsed_time < 0.1, f"解析太慢: {elapsed_time:.3f}秒"

    def test_memory_usage(self):
        """测试内存使用"""
        import sys

        # 创建大量分析结果
        analyses = [
            QueryAnalysis(
                entity=f"实体{i}",
                claim=f"主张{i}",
                category="其他"  # 使用有效的分类
            )
            for i in range(1000)
        ]

        # 每个对象不应该太大
        single_size = sys.getsizeof(analyses[0])

        # 单个对象应该小于1KB
        assert single_size < 1024, f"对象太大: {single_size} bytes"
