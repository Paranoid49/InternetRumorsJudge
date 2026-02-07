"""
并行度配置模块测试

测试 ParallelismConfig 类的功能，包括：
- 单例模式
- 并行度计算
- 自适应并行度
- 环境变量配置
"""
import pytest
import os
from unittest.mock import patch

from src.core.parallelism_config import ParallelismConfig, get_parallelism_config


class TestParallelismConfigSingleton:
    """测试单例模式"""

    def test_singleton_returns_same_instance(self):
        """测试多次调用返回同一个实例"""
        config1 = get_parallelism_config()
        config2 = get_parallelism_config()

        assert config1 is config2
        assert id(config1) == id(config2)

    def test_singleton_thread_safety(self):
        """测试单例模式的线程安全性"""
        import threading

        instances = []
        lock = threading.Lock()

        def get_instance():
            config = get_parallelism_config()
            with lock:
                instances.append(config)

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应该获得同一个实例
        assert len(instances) == 10
        assert all(inst is instances[0] for inst in instances)


class TestParallelismConfigCalculation:
    """测试并行度计算"""

    def test_default_workers_calculation(self):
        """测试默认并行度计算基于CPU核心数"""
        config = ParallelismConfig()

        # 默认并行度应该是 CPU核心数的1.5倍，最少2个，最多10个
        expected = min(max(config._cpu_count * 1.5, 2), 10)
        assert config._default_workers == int(expected)

    def test_get_max_workers_default(self):
        """测试获取默认任务类型的最大并行度"""
        config = ParallelismConfig()

        workers = config.get_max_workers('default')
        assert workers == config._default_workers

    def test_get_max_workers_evidence_analyzer(self):
        """测试证据分析任务的并行度更高"""
        config = ParallelismConfig()

        default_workers = config.get_max_workers('default')
        analyzer_workers = config.get_max_workers('evidence_analyzer')

        # 证据分析是IO密集型，应该有更高的并行度
        assert analyzer_workers >= default_workers
        assert analyzer_workers <= 15  # 最多15个

    def test_get_max_workers_retrieval(self):
        """测试检索任务的并行度"""
        config = ParallelismConfig()

        default_workers = config.get_max_workers('default')
        retrieval_workers = config.get_max_workers('retrieval')

        # 检索也是IO密集型
        assert retrieval_workers >= default_workers
        assert retrieval_workers <= 12  # 最多12个

    def test_get_max_workers_embedding(self):
        """测试嵌入计算的并行度较低（CPU密集型）"""
        config = ParallelismConfig()

        default_workers = config.get_max_workers('default')
        embedding_workers = config.get_max_workers('embedding')

        # 嵌入计算是CPU密集型，并行度不宜过高
        assert embedding_workers <= config._default_workers
        assert embedding_workers <= 8  # 最多8个


class TestAdaptiveParallelism:
    """测试自适应并行度"""

    def test_adaptive_workers_with_few_tasks(self):
        """测试任务数少于最大并行度时，使用任务数"""
        config = ParallelismConfig()

        # 3个任务，应该使用3个worker
        workers = config.get_adaptive_workers(
            task_count=3,
            task_type='evidence_analyzer',
            min_workers=1
        )
        assert workers == 3

    def test_adaptive_workers_with_many_tasks(self):
        """测试任务数多于最大并行度时，使用最大并行度"""
        config = ParallelismConfig()

        max_workers = config.get_max_workers('evidence_analyzer')
        workers = config.get_adaptive_workers(
            task_count=100,  # 大量任务
            task_type='evidence_analyzer',
            min_workers=1
        )
        assert workers == max_workers

    def test_adaptive_workers_respects_min_workers(self):
        """测试自适应并行度遵守最小worker数"""
        config = ParallelismConfig()

        workers = config.get_adaptive_workers(
            task_count=5,
            task_type='default',
            min_workers=3  # 设置最小值为3
        )
        assert workers >= 3

    def test_adaptive_workers_with_single_task(self):
        """测试单个任务时返回1个worker"""
        config = ParallelismConfig()

        workers = config.get_adaptive_workers(
            task_count=1,
            task_type='default',
            min_workers=1
        )
        assert workers == 1


class TestEnvironmentVariables:
    """测试环境变量配置"""

    def setup_method(self):
        """每个测试前保存并清理环境变量"""
        self.original_env = {}
        env_keys = ['MAX_WORKERS', 'EVIDENCE_ANALYZER_WORKERS', 'RETRIEVAL_WORKERS']
        for key in env_keys:
            self.original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """测试后恢复环境变量"""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    def test_max_workers_env_variable(self):
        """测试通过环境变量设置全局并行度（需要先设置环境变量再创建实例）"""
        os.environ['MAX_WORKERS'] = '8'

        # 重新导入模块以应用新的环境变量
        from importlib import reload
        import src.core.parallelism_config
        reload(src.core.parallelism_config)
        from src.core.parallelism_config import ParallelismConfig as NewConfig

        config = NewConfig()
        assert config._max_workers == 8
        assert config.get_max_workers('default') == 8

    def test_evidence_analyzer_workers_env_variable(self):
        """测试通过环境变量设置证据分析并行度（需要先设置环境变量再创建实例）"""
        os.environ['EVIDENCE_ANALYZER_WORKERS'] = '12'

        # 重新导入模块以应用新的环境变量
        from importlib import reload
        import src.core.parallelism_config
        reload(src.core.parallelism_config)
        from src.core.parallelism_config import ParallelismConfig as NewConfig

        config = NewConfig()
        assert config._evidence_analyzer_workers == 12
        assert config.get_max_workers('evidence_analyzer') == 12

    def test_retrieval_workers_env_variable(self):
        """测试通过环境变量设置检索并行度（需要先设置环境变量再创建实例）"""
        os.environ['RETRIEVAL_WORKERS'] = '10'

        # 重新导入模块以应用新的环境变量
        from importlib import reload
        import src.core.parallelism_config
        reload(src.core.parallelism_config)
        from src.core.parallelism_config import ParallelismConfig as NewConfig

        config = NewConfig()
        assert config._retrieval_workers == 10
        assert config.get_max_workers('retrieval') == 10

    def test_invalid_env_variable_ignored(self):
        """测试无效的环境变量被忽略（回退到默认值）"""
        os.environ['MAX_WORKERS'] = 'invalid'  # 非数字

        # 重新导入模块以应用新的环境变量
        from importlib import reload
        import src.core.parallelism_config
        reload(src.core.parallelism_config)
        from src.core.parallelism_config import ParallelismConfig as NewConfig

        config = NewConfig()
        # 无效值应该被忽略，_max_workers 保持为 None
        assert config._max_workers is None
        # 应该使用默认并行度
        assert config.get_max_workers('default') == config._default_workers


class TestConfigInfo:
    """测试配置信息获取"""

    def test_get_info_returns_all_fields(self):
        """测试获取配置信息包含所有字段"""
        config = ParallelismConfig()
        info = config.get_info()

        assert 'cpu_count' in info
        assert 'default_workers' in info
        assert 'max_workers' in info
        assert 'evidence_analyzer_workers' in info
        assert 'retrieval_workers' in info

    def test_get_info_contains_correct_values(self):
        """测试配置信息的值正确"""
        config = ParallelismConfig()
        info = config.get_info()

        assert info['cpu_count'] == config._cpu_count
        assert info['default_workers'] == config._default_workers
