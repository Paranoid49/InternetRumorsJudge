"""
健康检查模块

提供系统健康状态检查功能，用于生产环境监控和诊断
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from src import config
from src.core.cache_manager import CacheManager
from src.core.parallelism_config import get_parallelism_config
from src.observability.api_monitor import get_api_monitor

logger = logging.getLogger(__name__)


class HealthCheckStatus:
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthChecker:
    """
    系统健康检查器

    提供全面的系统健康状态检查，包括：
    - 配置检查
    - 依赖服务检查
    - 资源使用检查
    - 性能指标检查
    """

    def __init__(self):
        """初始化健康检查器"""
        self.start_time = datetime.now()

    def check_all(self) -> Dict[str, Any]:
        """
        执行完整的健康检查

        Returns:
            健康检查结果字典
        """
        results = {
            "status": HealthCheckStatus.HEALTHY,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "checks": {}
        }

        # 执行各项检查
        checks = [
            ("configuration", self._check_configuration),
            ("dependencies", self._check_dependencies),
            ("storage", self._check_storage),
            ("cache", self._check_cache),
            ("parallelism", self._check_parallelism),
            ("api_monitoring", self._check_api_monitoring),
        ]

        for check_name, check_func in checks:
            try:
                check_result = check_func()
                results["checks"][check_name] = check_result

                # 如果有检查失败，降低整体状态
                if check_result["status"] == "error":
                    results["status"] = HealthCheckStatus.UNHEALTHY
                elif check_result["status"] == "warning" and results["status"] != HealthCheckStatus.UNHEALTHY:
                    results["status"] = HealthCheckStatus.DEGRADED

            except Exception as e:
                logger.error(f"健康检查失败: {check_name}, 错误: {e}")
                results["checks"][check_name] = {
                    "status": "error",
                    "message": f"检查异常: {str(e)}"
                }
                results["status"] = HealthCheckStatus.UNHEALTHY

        return results

    def _check_configuration(self) -> Dict[str, Any]:
        """检查配置"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            # 检查API密钥
            if config.API_KEY:
                result["details"]["api_key"] = "configured"
            else:
                result["status"] = "error"
                result["details"]["api_key"] = "missing"
                result["message"] = "DASHSCOPE_API_KEY 未配置"

            # 检查模型配置
            result["details"]["models"] = {
                "parser": config.MODEL_PARSER,
                "analyzer": config.MODEL_ANALYZER,
                "summarizer": config.MODEL_SUMMARIZER,
                "embedding": config.EMBEDDING_MODEL
            }

            # 检查阈值配置
            result["details"]["thresholds"] = {
                "similarity": config.SIMILARITY_THRESHOLD,
                "min_local": config.MIN_LOCAL_SIMILARITY
            }

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)

        return result

    def _check_dependencies(self) -> Dict[str, Any]:
        """检查依赖服务"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            # 检查关键依赖
            dependencies = {
                "langchain": "langchain",
                "langchain_openai": "langchain_openai",
                "chromadb": "chromadb",
                "pydantic": "pydantic"
            }

            for name, module_path in dependencies.items():
                try:
                    __import__(module_path)
                    result["details"][name] = "available"
                except ImportError:
                    result["details"][name] = "missing"
                    if result["status"] == "pass":
                        result["status"] = "error"

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)

        return result

    def _check_storage(self) -> Dict[str, Any]:
        """检查存储目录"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            # 检查关键目录
            directories = {
                "storage": Path("storage"),
                "vector_db": Path("storage/vector_db"),
                "cache": Path("storage/cache"),
                "data_rumors": Path("data/rumors"),
            }

            for name, path in directories.items():
                if path.exists():
                    result["details"][name] = {
                        "exists": True,
                        "writable": path.is_dir() and oct(path.stat().st_mode)[-3:]
                    }
                else:
                    result["details"][name] = {
                        "exists": False,
                        "writable": False
                    }
                    # storage目录不存在是错误，其他是警告
                    if name == "storage":
                        result["status"] = "error"
                    elif result["status"] == "pass":
                        result["status"] = "warning"

        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)

        return result

    def _check_cache(self) -> Dict[str, Any]:
        """检查缓存系统"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            cache_mgr = CacheManager()

            # 检查精确匹配缓存
            result["details"]["exact_cache"] = {
                "enabled": True,
                "keys": len(cache_mgr._cache) if hasattr(cache_mgr, '_cache') else 0
            }

            # 检查语义缓存
            if hasattr(cache_mgr, '_semantic_cache'):
                result["details"]["semantic_cache"] = {
                    "enabled": True,
                    "threshold": cache_mgr._semantic_threshold
                }

        except Exception as e:
            result["status"] = "warning"
            result["message"] = f"缓存检查异常: {str(e)}"

        return result

    def _check_parallelism(self) -> Dict[str, Any]:
        """检查并行度配置"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            parallelism_config = get_parallelism_config()

            result["details"] = {
                "cpu_cores": parallelism_config.cpu_cores,
                "default_workers": parallelism_config.get_max_workers('default'),
                "evidence_analyzer_workers": parallelism_config.get_max_workers('evidence_analyzer'),
                "retrieval_workers": parallelism_config.get_max_workers('retrieval')
            }

        except Exception as e:
            result["status"] = "warning"
            result["message"] = str(e)

        return result

    def _check_api_monitoring(self) -> Dict[str, Any]:
        """检查API监控"""
        result = {
            "status": "pass",
            "details": {}
        }

        try:
            monitor = get_api_monitor()

            # 获取今日统计
            summary = monitor.get_daily_summary()

            result["details"] = {
                "enabled": True,
                "today_calls": summary.get('api_calls', 0),
                "today_cost": summary.get('total_cost', 0.0),
                "today_tokens": summary.get('total_tokens', 0)
            }

        except Exception as e:
            result["status"] = "warning"
            result["message"] = f"API监控检查异常: {str(e)}"

        return result

    def get_quick_status(self) -> str:
        """
        获取快速健康状态（仅返回状态字符串）

        Returns:
            健康状态: healthy, degraded, or unhealthy
        """
        full_check = self.check_all()
        return full_check["status"]


# 单例实例
_health_checker_instance: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """
    获取健康检查器单例实例

    Returns:
        HealthChecker 实例
    """
    global _health_checker_instance
    if _health_checker_instance is None:
        _health_checker_instance = HealthChecker()
    return _health_checker_instance


def health_check_endpoint() -> Dict[str, Any]:
    """
    健康检查端点（用于API服务）

    Returns:
        健康检查结果，适合HTTP响应
    """
    checker = get_health_checker()
    return checker.check_all()


if __name__ == "__main__":
    # 测试健康检查
    import json

    checker = HealthChecker()
    result = checker.check_all()

    print("=== 系统健康检查报告 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\n快速状态: {checker.get_quick_status()}")
