"""
依赖检查模块 - 确保系统依赖完整

在启动时检查关键依赖，提供友好的错误提示
"""
import logging
from pathlib import Path

logger = logging.getLogger("DependencyCheck")


def check_dependencies() -> bool:
    """
    检查关键依赖是否可用

    Returns:
        bool: 所有依赖是否可用
    """
    errors = []

    # 1. 检查版本管理器
    try:
        from src.core.version_manager import VersionManager
        logger.info("✅ VersionManager 可用")
    except ImportError as e:
        errors.append("❌ VersionManager 导入失败 - 知识库并发安全将无法保证")
        logger.error(f"VersionManager 导入失败: {e}")

    # 2. 检查 API Key
    from src import config
    if not config.API_KEY:
        errors.append("❌ DASHSCOPE_API_KEY 未设置 - 请在 .env 文件中配置")
    else:
        logger.info("✅ DASHSCOPE_API_KEY 已设置")

    # 3. 检查存储目录
    storage_dir = Path("storage")
    if not storage_dir.exists():
        storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info("✅ 创建存储目录")

    if errors:
        error_msg = "\n".join(errors)
        logger.error(f"依赖检查失败:\n{error_msg}")
        print("\n" + "="*60)
        print("⚠️  系统依赖检查失败")
        print("="*60)
        for error in errors:
            print(error)
        print("="*60)
        print("\n请解决上述问题后重新启动系统")
        return False

    logger.info("✅ 所有依赖检查通过")
    return True


def get_system_info() -> dict:
    """获取系统信息，用于诊断"""
    import platform
    import sys

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
    }
