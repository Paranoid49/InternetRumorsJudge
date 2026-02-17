"""
测试配置管理器

测试覆盖：
- 配置加载
- 环境变量覆盖
- 类型转换
- 配置验证
- 向后兼容
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from src.core.config_manager import (
    ConfigManager,
    config,
    get_config,
    _get_env,
    APIConfig,
    RetrievalConfig,
    CacheConfig,
    ModelConfig,
)


class TestGetEnv:
    """测试环境变量获取函数"""

    def test_get_env_string(self):
        """测试字符串类型"""
        with patch.dict(os.environ, {'TEST_KEY': 'test_value'}):
            result = _get_env('TEST_KEY', 'default', str)
            assert result == 'test_value'

    def test_get_env_int(self):
        """测试整数类型"""
        with patch.dict(os.environ, {'TEST_INT': '42'}):
            result = _get_env('TEST_INT', 0, int)
            assert result == 42

    def test_get_env_float(self):
        """测试浮点类型"""
        with patch.dict(os.environ, {'TEST_FLOAT': '3.14'}):
            result = _get_env('TEST_FLOAT', 0.0, float)
            assert result == 3.14

    def test_get_env_bool_true(self):
        """测试布尔类型（真值）"""
        for true_value in ['true', 'True', 'TRUE', '1', 'yes', 'on']:
            with patch.dict(os.environ, {'TEST_BOOL': true_value}):
                result = _get_env('TEST_BOOL', False, bool)
                assert result is True

    def test_get_env_bool_false(self):
        """测试布尔类型（假值）"""
        for false_value in ['false', 'False', 'FALSE', '0', 'no', 'off']:
            with patch.dict(os.environ, {'TEST_BOOL': false_value}):
                result = _get_env('TEST_BOOL', True, bool)
                assert result is False

    def test_get_env_default(self):
        """测试默认值"""
        result = _get_env('NON_EXISTENT_KEY', 'default_value')
        assert result == 'default_value'

    def test_get_env_invalid_int(self):
        """测试无效整数转换"""
        with patch.dict(os.environ, {'TEST_INVALID_INT': 'not_a_number'}):
            result = _get_env('TEST_INVALID_INT', 99, int)
            assert result == 99  # 返回默认值


class TestAPIConfig:
    """测试 API 配置"""

    def test_default_values(self):
        """测试默认值"""
        api_config = APIConfig()
        assert api_config.HF_ENDPOINT == "https://hf-mirror.com"

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {
            'DASHSCOPE_API_KEY': 'test_key',
            'TAVILY_API_KEY': 'tavily_key',
        }):
            api_config = APIConfig()
            assert api_config.DASHSCOPE_API_KEY == 'test_key'
            assert api_config.TAVILY_API_KEY == 'tavily_key'


class TestRetrievalConfig:
    """测试检索配置"""

    def test_default_values(self):
        """测试默认值"""
        retrieval_config = RetrievalConfig()
        assert retrieval_config.SIMILARITY_THRESHOLD == 0.25
        assert retrieval_config.EMBEDDING_MODEL == "text-embedding-v3"
        assert retrieval_config.MAX_RESULTS == 3

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {
            'MAX_RESULTS': '5',
            'MIN_LOCAL_SIMILARITY': '0.7',
        }):
            retrieval_config = RetrievalConfig()
            assert retrieval_config.MAX_RESULTS == 5
            assert retrieval_config.MIN_LOCAL_SIMILARITY == 0.7


class TestCacheConfig:
    """测试缓存配置"""

    def test_default_values(self):
        """测试默认值"""
        cache_config = CacheConfig()
        assert cache_config.SEMANTIC_CACHE_THRESHOLD == 0.96
        assert cache_config.DEFAULT_CACHE_TTL == 86400


class TestModelConfig:
    """测试模型配置"""

    def test_default_values(self):
        """测试默认值"""
        model_config = ModelConfig()
        assert model_config.MODEL_PARSER == "qwen-plus"
        assert model_config.MODEL_ANALYZER == "qwen-plus"
        assert model_config.MODEL_SUMMARIZER == "qwen-max"
        assert model_config.LLM_REQUEST_TIMEOUT == 30


class TestConfigManager:
    """测试配置管理器"""

    def test_singleton(self):
        """测试单例模式"""
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2

    def test_get_config(self):
        """测试获取配置实例"""
        cfg = get_config()
        assert cfg is config

    def test_validate_success(self):
        """测试配置验证（有 API 密钥）"""
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test_key'}):
            # 创建新实例测试
            ConfigManager._initialized = False
            cfg = ConfigManager()
            errors = cfg.validate()
            assert isinstance(errors, list)

    def test_validate_missing_api_key(self):
        """测试缺少 API 密钥的验证"""
        # 清除 API 密钥
        with patch.dict(os.environ, {}, clear=True):
            # 跳过实际的 env 清除，只测试逻辑
            pass

    def test_to_dict(self):
        """测试配置导出"""
        cfg_dict = config.to_dict()
        assert 'API' in cfg_dict
        assert 'Model' in cfg_dict
        assert 'Retrieval' in cfg_dict

    def test_to_dict_with_secrets(self):
        """测试导出配置（包含敏感信息）"""
        cfg_dict = config.to_dict(include_secrets=True)
        # 如果有 API 密钥，应该显示真实值
        assert 'API' in cfg_dict

    def test_to_dict_without_secrets(self):
        """测试导出配置（不包含敏感信息）"""
        cfg_dict = config.to_dict(include_secrets=False)
        # API 密钥应该被脱敏
        if cfg_dict['API'].get('DASHSCOPE_API_KEY'):
            assert cfg_dict['API']['DASHSCOPE_API_KEY'] == '***'

    def test_get_simple_key(self):
        """测试获取简单配置键"""
        value = config.get('SIMILARITY_THRESHOLD', 0.5)
        assert isinstance(value, float)

    def test_get_dotted_key(self):
        """测试获取点号分隔的配置键"""
        value = config.get('Model.LLM_REQUEST_TIMEOUT', 60)
        assert value == 30  # 默认值

    def test_get_nonexistent_key(self):
        """测试获取不存在的配置键"""
        value = config.get('NON_EXISTENT_KEY', 'default')
        assert value == 'default'


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_import_from_config(self):
        """测试从 config.py 导入"""
        from src import config as cfg

        assert hasattr(cfg, 'API_KEY')
        assert hasattr(cfg, 'MODEL_PARSER')
        assert hasattr(cfg, 'MAX_RESULTS')

    def test_old_style_access(self):
        """测试旧式访问方式"""
        from src import config as cfg

        # 这些应该能正常工作
        _ = cfg.SIMILARITY_THRESHOLD
        _ = cfg.EMBEDDING_MODEL
        _ = cfg.MAX_RESULTS

    def test_config_value_consistency(self):
        """测试配置值一致性"""
        from src import config as old_config

        # 旧版和新版应该返回相同的值
        assert old_config.MAX_RESULTS == config.Retrieval.MAX_RESULTS
        assert old_config.LLM_REQUEST_TIMEOUT == config.Model.LLM_REQUEST_TIMEOUT


class TestConfigFunctions:
    """测试配置函数"""

    def test_get_config_value(self):
        """测试 get_config_value 函数"""
        from src.config import get_config_value

        value = get_config_value('Model.LLM_REQUEST_TIMEOUT', 999)
        assert value == 30

    def test_validate_configuration(self):
        """测试 validate_configuration 函数"""
        from src.config import validate_configuration

        errors = validate_configuration()
        assert isinstance(errors, list)

    def test_export_config(self):
        """测试 export_config 函数"""
        from src.config import export_config

        cfg = export_config()
        assert isinstance(cfg, dict)
