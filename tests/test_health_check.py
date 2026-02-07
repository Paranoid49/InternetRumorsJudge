"""
健康检查模块测试

测试系统健康检查功能
"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.health_check import (
    HealthChecker,
    HealthCheckStatus,
    get_health_checker,
    health_check_endpoint
)


class TestHealthChecker:
    """健康检查器测试"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        checker1 = get_health_checker()
        checker2 = get_health_checker()

        assert checker1 is checker2

    def test_quick_status(self):
        """测试快速状态检查"""
        checker = HealthChecker()
        status = checker.get_quick_status()

        assert status in [
            HealthCheckStatus.HEALTHY,
            HealthCheckStatus.DEGRADED,
            HealthCheckStatus.UNHEALTHY
        ]

    def test_full_health_check(self):
        """测试完整健康检查"""
        checker = HealthChecker()
        result = checker.check_all()

        # 验证返回结构
        assert "status" in result
        assert "timestamp" in result
        assert "uptime_seconds" in result
        assert "checks" in result

        # 验证检查项
        checks = result["checks"]
        expected_checks = [
            "configuration",
            "dependencies",
            "storage",
            "cache",
            "parallelism",
            "api_monitoring"
        ]

        for check_name in expected_checks:
            assert check_name in checks
            assert "status" in checks[check_name]

    def test_configuration_check(self):
        """测试配置检查"""
        checker = HealthChecker()
        result = checker._check_configuration()

        assert "status" in result
        assert "details" in result

        # 验证模型配置存在
        if "details" in result:
            assert "models" in result["details"]

    def test_dependencies_check(self):
        """测试依赖检查"""
        checker = HealthChecker()
        result = checker._check_dependencies()

        assert "status" in result
        assert "details" in result

        # 验证关键依赖检查
        if "details" in result:
            # 至少应该检查langchain
            assert "langchain" in result["details"]

    def test_storage_check(self):
        """测试存储检查"""
        checker = HealthChecker()
        result = checker._check_storage()

        assert "status" in result
        assert "details" in result

    def test_cache_check(self):
        """测试缓存检查"""
        checker = HealthChecker()
        result = checker._check_cache()

        assert "status" in result
        assert "details" in result

    def test_parallelism_check(self):
        """测试并行度检查"""
        checker = HealthChecker()
        result = checker._check_parallelism()

        assert "status" in result
        assert "details" in result

        # 验证并行度信息
        if "details" in result and result["details"]:
            assert "cpu_cores" in result["details"]

    def test_api_monitoring_check(self):
        """测试API监控检查"""
        checker = HealthChecker()
        result = checker._check_api_monitoring()

        assert "status" in result
        assert "details" in result

    def test_health_check_endpoint(self):
        """测试健康检查端点"""
        result = health_check_endpoint()

        assert "status" in result
        assert "timestamp" in result
        assert "checks" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
