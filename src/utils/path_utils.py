"""
路径工具模块

提供项目路径管理工具，避免在多个文件中重复路径计算代码
"""
import sys
from pathlib import Path


def setup_project_path():
    """
    自动设置项目根目录到 Python 路径

    该函数通过查找项目根目录的标记文件（如 pyproject.toml, setup.py 等）
    自动识别项目根目录，并将其添加到 sys.path 中。

    应在模块导入时尽早调用，通常在文件顶部：

        from src.utils.path_utils import setup_project_path
        setup_project_path()

    Returns:
        Path: 项目根目录路径
    """
    # 从当前文件开始向上查找项目根目录
    current_file = Path(__file__).resolve()

    # 项目根目录的标记文件
    root_markers = ['pyproject.toml', 'setup.py', 'setup.cfg', '.git']

    # 向上遍历查找项目根目录
    for parent in [current_file, *current_file.parents]:
        if any((parent / marker).exists() for marker in root_markers):
            project_root = parent
            break
    else:
        # 如果未找到标记文件，使用默认的 src 上级目录
        project_root = Path(__file__).parent.parent.parent

    # 将项目根目录添加到 sys.path
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    return project_root


def get_project_root() -> Path:
    """
    获取项目根目录路径

    Returns:
        Path: 项目根目录路径
    """
    # 从当前文件开始向上查找项目根目录
    current_file = Path(__file__).resolve()
    root_markers = ['pyproject.toml', 'setup.py', 'setup.cfg', '.git']

    for parent in [current_file, *current_file.parents]:
        if any((parent / marker).exists() for marker in root_markers):
            return parent

    # 回退方案
    return Path(__file__).parent.parent.parent


# 自动设置项目路径（模块导入时执行）
setup_project_path()
