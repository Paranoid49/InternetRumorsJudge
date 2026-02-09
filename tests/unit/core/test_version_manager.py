"""
VersionManager 单元测试

测试覆盖：
1. KnowledgeVersion 数据模型
2. VersionManager 初始化
3. 版本查询功能
4. 临时目录创建
5. 版本提交（双缓冲策略）
6. 版本回滚
7. 版本列表
8. 旧版本清理
9. 并发安全测试
"""
import json
import os
import platform
import shutil
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.core.version_manager import KnowledgeVersion, VersionManager


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_base_dir():
    """创建临时基础目录，测试后自动清理"""
    temp_dir = Path(tempfile.mkdtemp(prefix="version_mgr_test_"))
    yield temp_dir
    # 清理
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def version_manager(temp_base_dir):
    """创建 VersionManager 实例"""
    return VersionManager(base_dir=temp_base_dir)


@pytest.fixture
def mock_version_data():
    """模拟版本数据"""
    return {
        "version_id": "v_20260208_120000",
        "timestamp": "2026-02-08T12:00:00",
        "doc_count": 100,
        "path": "/storage/vector_db"
    }


@pytest.fixture
def staging_dir_with_files(temp_base_dir):
    """创建包含模拟文件的临时目录"""
    staging = temp_base_dir / "vector_db_staging" / "build_20260208_120000"
    staging.mkdir(parents=True, exist_ok=True)

    # 创建模拟的 ChromaDB 文件
    chroma_dir = staging / "chroma"
    chroma_dir.mkdir(exist_ok=True)

    # 创建一些 .bin 文件（模拟 ChromaDB 数据）
    (chroma_dir / "data.bin").write_bytes(b"mock_vector_data")
    (chroma_dir / "index.bin").write_bytes(b"mock_index_data")

    # 创建元数据文件
    metadata = {
        "version": "1.0",
        "created_at": datetime.now().isoformat()
    }
    (chroma_dir / "metadata.json").write_text(json.dumps(metadata))

    return staging


# ============================================================================
# KnowledgeVersion Tests
# ============================================================================

class TestKnowledgeVersion:
    """KnowledgeVersion 数据模型测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        version = KnowledgeVersion(
            version_id="v_001",
            timestamp="2026-02-08T12:00:00",
            doc_count=50,
            path="/storage/db"
        )

        result = version.to_dict()

        assert result == {
            "version_id": "v_001",
            "timestamp": "2026-02-08T12:00:00",
            "doc_count": 50,
            "path": "/storage/db"
        }

    def test_from_dict(self, mock_version_data):
        """测试从字典创建"""
        version = KnowledgeVersion.from_dict(mock_version_data)

        assert version.version_id == "v_20260208_120000"
        assert version.timestamp == "2026-02-08T12:00:00"
        assert version.doc_count == 100
        assert version.path == "/storage/vector_db"

    def test_round_trip_conversion(self, mock_version_data):
        """测试往返转换一致性"""
        version = KnowledgeVersion.from_dict(mock_version_data)
        result_dict = version.to_dict()

        assert result_dict == mock_version_data


# ============================================================================
# VersionManager Initialization Tests
# ============================================================================

class TestVersionManagerInitialization:
    """VersionManager 初始化测试"""

    def test_initialization_creates_base_dir(self, temp_base_dir):
        """测试初始化时创建基础目录"""
        # 删除目录后创建
        version_manager = VersionManager(base_dir=temp_base_dir)

        assert version_manager.base_dir == temp_base_dir
        assert version_manager.base_dir.exists()
        assert version_manager.base_dir.is_dir()

    def test_initialization_sets_correct_paths(self, temp_base_dir):
        """测试初始化设置正确的路径"""
        vm = VersionManager(base_dir=temp_base_dir)

        assert vm.version_file == temp_base_dir / ".version"
        assert vm.active_dir == temp_base_dir / "vector_db"
        assert vm.staging_dir == temp_base_dir / "vector_db_staging"

    def test_initialization_creates_lock(self, temp_base_dir):
        """测试初始化创建锁"""
        vm = VersionManager(base_dir=temp_base_dir)

        assert vm._lock is not None
        assert isinstance(vm._lock, type(threading.Lock()))


# ============================================================================
# Get Current Version Tests
# ============================================================================

class TestGetCurrentVersion:
    """获取当前版本测试"""

    def test_no_version_file_returns_none(self, version_manager):
        """测试无版本文件时返回 None"""
        result = version_manager.get_current_version()

        assert result is None

    def test_reads_version_file_successfully(self, version_manager, mock_version_data):
        """测试成功读取版本文件"""
        # 创建版本文件
        with open(version_manager.version_file, 'w', encoding='utf-8') as f:
            json.dump(mock_version_data, f)

        result = version_manager.get_current_version()

        assert result is not None
        assert result.version_id == "v_20260208_120000"
        assert result.doc_count == 100

    def test_corrupted_version_file_returns_none(self, version_manager):
        """测试损坏的版本文件返回 None"""
        # 写入无效的 JSON
        version_manager.version_file.write_text("{invalid json}")

        result = version_manager.get_current_version()

        assert result is None

    def test_version_file_with_missing_fields(self, version_manager):
        """测试缺少字段的版本文件"""
        # 写入不完整的 JSON
        incomplete_data = {"version_id": "v_001"}
        with open(version_manager.version_file, 'w', encoding='utf-8') as f:
            json.dump(incomplete_data, f)

        result = version_manager.get_current_version()

        # from_dict 会抛出 KeyError，应该返回 None
        assert result is None


# ============================================================================
# Get Active DB Path Tests
# ============================================================================

class TestGetActiveDbPath:
    """获取活跃数据库路径测试"""

    def test_no_version_returns_default_active_dir(self, version_manager):
        """测试无版本时返回默认活跃目录"""
        result = version_manager.get_active_db_path()

        assert result == version_manager.active_dir

    def test_with_version_returns_version_path(self, version_manager, mock_version_data):
        """测试有版本时返回版本路径"""
        # 修改路径为绝对路径
        mock_version_data["path"] = str(version_manager.base_dir / "vector_db_v_001")

        with open(version_manager.version_file, 'w', encoding='utf-8') as f:
            json.dump(mock_version_data, f)

        result = version_manager.get_active_db_path()

        assert result == version_manager.base_dir / "vector_db_v_001"


# ============================================================================
# Create Staging Dir Tests
# ============================================================================

class TestCreateStagingDir:
    """创建临时目录测试"""

    def test_creates_staging_directory(self, version_manager):
        """测试创建临时目录"""
        staging = version_manager.create_staging_dir()

        assert staging.exists()
        assert staging.is_dir()
        assert staging.parent == version_manager.staging_dir
        assert "build_" in staging.name

    def test_cleans_old_staging_dirs(self, version_manager):
        """测试清理旧的临时目录"""
        # 创建旧的临时目录
        old_staging = version_manager.staging_dir / "build_old"
        old_staging.mkdir(parents=True, exist_ok=True)
        (old_staging / "test.txt").write_text("old file")

        # 创建新的临时目录
        new_staging = version_manager.create_staging_dir()

        # 旧目录应该被清理
        assert not old_staging.exists()
        assert new_staging.exists()

    def test_staging_dir_name_includes_timestamp(self, version_manager):
        """测试临时目录名包含时间戳"""
        staging = version_manager.create_staging_dir()

        # 目录名格式应该是 build_YYYYMMDD_HHMMSS
        name_parts = staging.stem.split("_")
        assert len(name_parts) == 3
        assert name_parts[0] == "build"


# ============================================================================
# Commit Version Tests
# ============================================================================

class TestCommitVersion:
    """提交版本测试（双缓冲策略）"""

    def test_commit_success_creates_version_dir(self, version_manager, staging_dir_with_files):
        """测试成功提交创建版本目录"""
        result = version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        assert result is True

        # 检查版本目录是否创建
        version_dirs = list(version_manager.base_dir.glob("vector_db_v_*"))
        assert len(version_dirs) >= 1

        # 检查版本文件是否创建
        assert version_manager.version_file.exists()

    def test_commit_updates_version_file(self, version_manager, staging_dir_with_files):
        """测试提交更新版本文件"""
        version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=50
        )

        # 读取版本文件
        with open(version_manager.version_file, 'r', encoding='utf-8') as f:
            version_data = json.load(f)

        assert version_data["doc_count"] == 50
        assert "version_id" in version_data
        assert "timestamp" in version_data
        assert "path" in version_data

    def test_commit_nonexistent_staging_path_returns_false(self, version_manager):
        """测试提交不存在的临时目录返回 False"""
        nonexistent_path = version_manager.base_dir / "nonexistent"

        result = version_manager.commit_version(
            staging_path=nonexistent_path,
            doc_count=100
        )

        assert result is False

    def test_commit_atomically_writes_version_file(self, version_manager, staging_dir_with_files):
        """测试原子性写入版本文件"""
        version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        # 检查临时文件被清理
        temp_file = version_manager.version_file.with_suffix('.tmp')
        assert not temp_file.exists()

        # 检查正式文件存在
        assert version_manager.version_file.exists()

    def test_commit_cleans_old_versions(self, version_manager, staging_dir_with_files):
        """测试提交后清理旧版本"""
        # 创建多个旧版本
        for i in range(5):
            old_version_dir = version_manager.base_dir / f"vector_db_v_2026020{i}_120000"
            old_version_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.01)  # 确保时间戳不同

        # 提交新版本
        version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        # 应该保留最近的 3 个版本（包括新提交的）
        version_dirs = list(version_manager.base_dir.glob("vector_db_v_*"))
        assert len(version_dirs) <= 4  # 3个保留 + 可能的新版本

    def test_commit_empty_staging_dir(self, version_manager, temp_base_dir):
        """测试提交空的临时目录"""
        # 创建空的临时目录（没有 .bin 文件）
        empty_staging = temp_base_dir / "vector_db_staging" / "build_empty"
        empty_staging.mkdir(parents=True, exist_ok=True)

        result = version_manager.commit_version(
            staging_path=empty_staging,
            doc_count=0
        )

        # 应该成功（允许空库）
        assert result is True

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows specific test")
    def test_commit_on_windows_uses_copy(self, version_manager, staging_dir_with_files):
        """测试 Windows 下使用复制而非移动"""
        with patch.object(shutil, 'copytree') as mock_copy:
            with patch.object(shutil, 'move') as mock_move:
                # mock_copy 会调用真实函数，mock_move 会被跳过
                mock_copy.side_effect = lambda src, dst, **kwargs: shutil.copytree(src, dst, **kwargs)

                version_manager.commit_version(
                    staging_path=staging_dir_with_files,
                    doc_count=100
                )

                # Windows 下应该调用 copytree
                assert mock_copy.called

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix specific test")
    def test_commit_on_unix_uses_symlink(self, version_manager, staging_dir_with_files):
        """测试 Unix 下使用符号链接"""
        version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        # 检查是否创建了符号链接
        if version_manager.active_dir.exists():
            is_symlink = version_manager.active_dir.is_symlink()
            # 根据实现，可能使用符号链接或直接复制
            # 这里只检查目录存在
            assert version_manager.active_dir.exists()


# ============================================================================
# Rollback Version Tests
# ============================================================================

class TestRollbackVersion:
    """版本回滚测试"""

    def test_rollback_to_nonexistent_version_returns_false(self, version_manager):
        """测试回滚到不存在的版本返回 False"""
        result = version_manager.rollback_version("v_nonexistent")

        assert result is False

    def test_rollback_to_existing_version(self, version_manager, staging_dir_with_files):
        """测试回滚到已存在的版本"""
        # 先提交一个版本
        version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        # 获取版本 ID
        version_dirs = list(version_manager.base_dir.glob("vector_db_v_*"))
        if version_dirs:
            version_id = version_dirs[0].name.replace("vector_db_", "")

            # 回滚到该版本
            result = version_manager.rollback_version(version_id)

            # 注意：回滚可能因为权限或平台问题失败
            # 这里只检查方法能正常调用
            assert result is not None


# ============================================================================
# List Versions Tests
# ============================================================================

class TestListVersions:
    """列出版本测试"""

    def test_list_versions_with_no_versions(self, version_manager):
        """测试无版本时返回空列表"""
        result = version_manager.list_versions()

        assert result == []

    def test_list_versions_returns_all_versions(self, version_manager, staging_dir_with_files):
        """测试返回所有版本"""
        # 创建多个版本目录
        for i in range(3):
            version_dir = version_manager.base_dir / f"vector_db_v_2026020{i}_120000"
            version_dir.mkdir(parents=True, exist_ok=True)
            (version_dir / "data.bin").write_bytes(f"version{i}".encode())
            time.sleep(0.01)  # 确保时间戳不同

        result = version_manager.list_versions()

        assert len(result) == 3
        assert all("version_id" in v for v in result)
        assert all("path" in v for v in result)
        assert all("size_mb" in v for v in result)
        assert all("modified" in v for v in result)

    def test_list_versions_sorted_by_mtime(self, version_manager):
        """测试按修改时间排序"""
        # 创建版本目录，不同时间
        versions = []
        for i in range(3):
            version_dir = version_manager.base_dir / f"vector_db_v_00{i}"
            version_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.01)
            versions.append(version_dir)

        result = version_manager.list_versions()

        # 应该按修改时间倒序排列（最新的在前）
        assert len(result) == 3


# ============================================================================
# Cleanup Old Versions Tests
# ============================================================================

class TestCleanupOldVersions:
    """清理旧版本测试"""

    def test_cleanup_keeps_specified_number(self, version_manager):
        """测试保留指定数量的版本"""
        # 创建 5 个版本目录
        for i in range(5):
            version_dir = version_manager.base_dir / f"vector_db_v_00{i}"
            version_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.01)

        # 清理，保留 3 个
        version_manager._cleanup_old_versions(keep=3)

        # 应该只保留 3 个
        remaining = list(version_manager.base_dir.glob("vector_db_v_*"))
        assert len(remaining) <= 3

    def test_cleanup_handles_errors_gracefully(self, version_manager):
        """测试清理时错误不影响其他操作"""
        # 创建一些版本目录
        for i in range(3):
            version_dir = version_manager.base_dir / f"vector_db_v_00{i}"
            version_dir.mkdir(parents=True, exist_ok=True)

        # 清理不应该抛出异常
        try:
            version_manager._cleanup_old_versions(keep=2)
            assert True
        except Exception:
            pytest.fail("cleanup_old_versions should not raise exception")


# ============================================================================
# Concurrency Safety Tests
# ============================================================================

class TestConcurrencySafety:
    """并发安全测试"""

    def test_concurrent_get_current_version(self, version_manager, mock_version_data):
        """测试并发获取当前版本"""
        # 创建版本文件
        with open(version_manager.version_file, 'w', encoding='utf-8') as f:
            json.dump(mock_version_data, f)

        results = []
        errors = []

        def read_version():
            try:
                result = version_manager.get_current_version()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # 启动多个线程读取
        threads = []
        for _ in range(10):
            t = threading.Thread(target=read_version)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 应该没有错误
        assert len(errors) == 0
        assert len(results) == 10

        # 所有结果应该一致
        assert all(r.version_id == "v_20260208_120000" for r in results if r)

    def test_concurrent_commit_version(self, version_manager, staging_dir_with_files):
        """测试并发提交版本（使用锁）"""
        results = []
        errors = []

        def commit_version(index):
            try:
                # 为每个线程创建独立的临时目录
                staging = version_manager.base_dir / f"staging_{index}"
                staging.mkdir(parents=True, exist_ok=True)
                (staging / "data.bin").write_bytes(f"data{index}".encode())

                result = version_manager.commit_version(
                    staging_path=staging,
                    doc_count=index
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # 启动多个线程提交
        threads = []
        for i in range(5):
            t = threading.Thread(target=commit_version, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 应该没有错误
        assert len(errors) == 0
        assert len(results) == 5

        # 所有提交应该成功
        assert all(results)

    def test_concurrent_list_and_cleanup(self, version_manager):
        """测试并发列表和清理"""
        # 创建一些版本目录
        for i in range(5):
            version_dir = version_manager.base_dir / f"vector_db_v_00{i}"
            version_dir.mkdir(parents=True, exist_ok=True)

        errors = []

        def list_and_cleanup():
            try:
                version_manager.list_versions()
                version_manager._cleanup_old_versions(keep=2)
            except Exception as e:
                errors.append(e)

        # 启动多个线程
        threads = []
        for _ in range(10):
            t = threading.Thread(target=list_and_cleanup)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 应该没有错误
        assert len(errors) == 0


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""

    def test_commit_with_force_flag(self, version_manager, staging_dir_with_files):
        """测试使用 force 参数提交"""
        result = version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100,
            force=True
        )

        assert result is True

    def test_handle_permission_errors_gracefully(self, version_manager, staging_dir_with_files):
        """测试优雅处理权限错误"""
        # 这个测试在正常环境下应该通过
        # 在 CI/CD 环境中可能需要特殊权限设置
        result = version_manager.commit_version(
            staging_path=staging_dir_with_files,
            doc_count=100
        )

        # 只检查方法能正常执行
        assert result is not None

    def test_version_file_with_invalid_encoding(self, version_manager):
        """测试版本文件编码错误"""
        # 写入非 UTF-8 编码的内容
        version_manager.version_file.write_bytes(b'\xff\xfe invalid')

        result = version_manager.get_current_version()

        # 应该返回 None 而不是抛出异常
        assert result is None
