"""
知识库版本管理器 - 支持双缓冲策略

功能：
1. 管理知识库版本号
2. 支持原子性切换（双缓冲）
3. 提供并发安全的版本查询
"""
import logging
import os
import platform
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("VersionManager")


class KnowledgeVersion:
    """知识库版本信息"""

    def __init__(self, version_id: str, timestamp: str, doc_count: int, path: str):
        self.version_id = version_id
        self.timestamp = timestamp
        self.doc_count = doc_count
        self.path = path

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp,
            "doc_count": self.doc_count,
            "path": self.path
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeVersion":
        return cls(
            version_id=data["version_id"],
            timestamp=data["timestamp"],
            doc_count=data["doc_count"],
            path=data["path"]
        )


class VersionManager:
    """
    知识库版本管理器

    支持双缓冲策略：
    - storage/vector_db/         (当前活跃)
    - storage/vector_db_new/     (新构建)
    - 构建完成后原子性切换
    """

    def __init__(self, base_dir: Path, version_file: str = ".version"):
        self.base_dir = Path(base_dir)
        self.version_file = self.base_dir / version_file
        self.active_dir = self.base_dir / "vector_db"
        self.staging_dir = self.base_dir / "vector_db_staging"
        self._lock = threading.Lock()

        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_current_version(self) -> Optional[KnowledgeVersion]:
        """获取当前活跃的版本信息"""
        try:
            if not self.version_file.exists():
                logger.debug("版本文件不存在，返回 None")
                return None

            with open(self.version_file, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                return KnowledgeVersion.from_dict(data)
        except Exception as e:
            logger.error(f"读取版本文件失败: {e}")
            return None

    def get_active_db_path(self) -> Path:
        """获取当前活跃的向量库路径"""
        version = self.get_current_version()
        if version and version.path:
            return Path(version.path)
        return self.active_dir

    def create_staging_dir(self) -> Path:
        """创建临时构建目录"""
        # 使用时间戳创建唯一的临时目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        staging_dir = self.staging_dir / f"build_{timestamp}"

        # 清理旧的临时目录
        if self.staging_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.staging_dir)
            except Exception as e:
                logger.warning(f"清理旧临时目录失败: {e}")

        staging_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"创建临时构建目录: {staging_dir}")
        return staging_dir

    def commit_version(self, staging_path: Path, doc_count: int, force: bool = False) -> bool:
        """
        提交新版本（原子性切换）

        Args:
            staging_path: 临时构建目录路径
            doc_count: 文档数量
            force: 是否强制提交（即使当前有新版本）

        Returns:
            是否成功提交
        """
        with self._lock:
            try:
                # 生成新版本号
                timestamp = datetime.now().isoformat()
                version_id = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # 准备新版本的完整路径
                new_version_path = self.base_dir / f"vector_db_{version_id}"

                # 验证临时目录存在且有内容
                if not staging_path.exists():
                    logger.error(f"临时目录不存在: {staging_path}")
                    return False

                # 检查是否有向量库文件
                chroma_files = list(staging_path.rglob("*.bin"))
                if not chroma_files:
                    logger.warning(f"临时目录中没有向量库文件: {staging_path}")
                    # 继续执行，因为可能是空库

                # 原子性切换：
                # 1. 重命名临时目录为新版本目录
                import shutil
                if new_version_path.exists():
                    logger.warning(f"目标版本目录已存在，将覆盖: {new_version_path}")
                    shutil.rmtree(new_version_path)

                # Windows 下使用复制（ChromaDB 有文件锁定）
                if platform.system() == "Windows":
                    logger.info(f"Windows 环境，使用复制而非移动（避免文件锁定）")
                    shutil.copytree(str(staging_path), str(new_version_path))
                    # 删除临时目录
                    try:
                        shutil.rmtree(str(staging_path))
                    except Exception as e:
                        logger.warning(f"清理临时目录失败: {e}")
                else:
                    shutil.move(str(staging_path), str(new_version_path))

                logger.info(f"临时目录已移动到: {new_version_path}")

                # 2. 更新活跃链接（使用符号链接或更新配置）
                # 旧的活跃目录备份
                old_active_backup = None
                if self.active_dir.exists() and str(self.active_dir) != str(new_version_path):
                    old_active_backup = self.active_dir / f".old_{version_id}"
                    try:
                        # 备份旧目录
                        import shutil
                        if self.active_dir.is_symlink() or self.active_dir.is_dir():
                            backup_path = self.base_dir / f"vector_db_backup_{version_id}"
                            if backup_path.exists():
                                shutil.rmtree(backup_path)
                            shutil.move(str(self.active_dir), str(backup_path))
                            old_active_backup = backup_path
                    except Exception as e:
                        logger.warning(f"备份旧活跃目录失败: {e}")

                # 更新活跃目录指向新版本
                try:
                    # Windows 下可能无法创建符号链接，使用复制或更新路径引用
                    if platform.system() == "Windows":
                        # Windows：使用 junction 或者直接更新路径
                        try:
                            # 尝试删除旧目录/链接
                            if self.active_dir.is_symlink() or self.active_dir.is_dir():
                                if self.active_dir.exists():
                                    shutil.rmtree(str(self.active_dir))

                            # 创建目录连接（Windows junction - 需要管理员权限）
                            # 或直接复制内容（最安全但慢）
                            logger.info(f"Windows 环境，将新版本内容复制到活跃目录: {self.active_dir}")
                            shutil.copytree(str(new_version_path), str(self.active_dir), dirs_exist_ok=True)

                        except Exception as copy_error:
                            logger.warning(f"复制失败，使用路径引用方式: {copy_error}")
                            # 回退：只更新路径引用，不复制文件
                            self.active_dir = new_version_path
                    else:
                        # Unix/Linux：使用符号链接
                        if self.active_dir.is_symlink():
                            self.active_dir.unlink()
                        elif self.active_dir.exists():
                            shutil.rmtree(self.active_dir)

                        self.active_dir.parent.mkdir(parents=True, exist_ok=True)
                        os.symlink(str(new_version_path), str(self.active_dir))
                        logger.info(f"创建符号链接: {self.active_dir} -> {new_version_path}")

                except Exception as e:
                    logger.error(f"更新活跃目录失败: {e}，使用路径引用方式")
                    # 最终回退方案：只更新路径引用
                    self.active_dir = new_version_path

                # 3. 写入版本文件（原子操作）
                new_version = KnowledgeVersion(
                    version_id=version_id,
                    timestamp=timestamp,
                    doc_count=doc_count,
                    path=str(self.active_dir)
                )

                # 先写入临时文件，然后重命名（确保原子性）
                temp_version_file = self.version_file.with_suffix('.tmp')
                with open(temp_version_file, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(new_version.to_dict(), f, indent=2, ensure_ascii=False)

                # 原子性重命名
                temp_version_file.replace(self.version_file)
                logger.info(f"版本文件已更新: {version_id}")

                # 4. 清理旧版本（保留最近3个版本）
                self._cleanup_old_versions(keep=3)

                return True

            except Exception as e:
                logger.error(f"提交版本失败: {e}", exc_info=True)
                return False

    def _cleanup_old_versions(self, keep: int = 3):
        """清理旧版本，保留最近的几个版本"""
        try:
            import shutil
            version_dirs = sorted(
                self.base_dir.glob("vector_db_v_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # 保留最近的版本，删除其余的
            for old_dir in version_dirs[keep:]:
                try:
                    shutil.rmtree(old_dir)
                    logger.info(f"清理旧版本: {old_dir.name}")
                except Exception as e:
                    logger.warning(f"清理旧版本失败 {old_dir}: {e}")

            # 清理备份目录
            backup_dirs = sorted(
                self.base_dir.glob("vector_db_backup_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_dir in backup_dirs[1:]:  # 只保留最新的1个备份
                try:
                    shutil.rmtree(old_dir)
                    logger.info(f"清理旧备份: {old_dir.name}")
                except Exception as e:
                    logger.warning(f"清理旧备份失败 {old_dir}: {e}")

        except Exception as e:
            logger.warning(f"清理旧版本时出错: {e}")

    def rollback_version(self, version_id: str) -> bool:
        """回滚到指定版本"""
        with self._lock:
            try:
                # 查找目标版本目录
                target_dir = self.base_dir / f"vector_db_{version_id}"
                if not target_dir.exists():
                    logger.error(f"目标版本不存在: {version_id}")
                    return False

                # 备份当前版本
                if self.active_dir.exists():
                    backup_path = self.base_dir / f"vector_db_rollback_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    import shutil
                    shutil.move(str(self.active_dir), str(backup_path))

                # 切换到目标版本
                if self.active_dir.is_symlink():
                    self.active_dir.unlink()
                elif self.active_dir.exists():
                    import shutil
                    shutil.rmtree(self.active_dir)

                os.symlink(str(target_dir), str(self.active_dir))

                logger.info(f"已回滚到版本: {version_id}")
                return True

            except Exception as e:
                logger.error(f"回滚版本失败: {e}")
                return False

    def list_versions(self) -> list:
        """列出所有可用版本"""
        try:
            versions = []
            for version_dir in sorted(self.base_dir.glob("vector_db_v_*")):
                stat = version_dir.stat()
                versions.append({
                    "version_id": version_dir.name.replace("vector_db_", ""),
                    "path": str(version_dir),
                    "size_mb": stat.st_size / (1024 * 1024),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return versions
        except Exception as e:
            logger.error(f"列出版本失败: {e}")
            return []
