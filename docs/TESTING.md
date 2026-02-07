# 测试指南

## 📋 概述

本系统采用分层测试策略，确保代码质量和系统稳定性。

## 🏗️ 测试架构

### 测试金字塔

```
        ▲
       / \          E2E Tests (少量)
      /   \         - 完整流程验证
     /-----\        - 用户场景测试
    /       \       - API/接口测试
   /---------\      Integration Tests (适量)
  /           \     - 组件交互验证
 /  Unit Tests  \   - 缓存集成测试
/_______________\  - 检索集成测试
                   Unit Tests (大量)
                   - 独立组件测试
                   - 函数/方法测试
                   - 边界条件测试
```

### 测试类型说明

| 测试类型 | 标记 | 数量 | 执行时间 | 目的 |
|---------|------|------|---------|------|
| 单元测试 | `@pytest.mark.unit` | 150+ | 快 | 验证独立组件 |
| 集成测试 | `@pytest.mark.integration` | 30+ | 中等 | 验证模块协作 |
| 端到端测试 | `@pytest.mark.e2e` | 10+ | 慢 | 验证完整流程 |
| 并发测试 | `@pytest.mark.concurrent` | 5+ | 慢 | 验证线程安全 |

## 🚀 快速开始

### 安装测试依赖

```bash
# 安装所有依赖（包括测试依赖）
pip install -r requirements.txt

# 或仅安装测试依赖
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

### 运行测试

```bash
# 方法1: 使用测试运行脚本（推荐）
python scripts/run_tests.py unit          # 运行单元测试
python scripts/run_tests.py integration  # 运行集成测试
python scripts/run_tests.py all          # 运行所有测试
python scripts/run_tests.py coverage     # 生成覆盖率报告

# 方法2: 直接使用pytest
pytest tests/unit/ -v                    # 运行单元测试
pytest tests/ -m integration -v          # 运行集成测试
pytest tests/ -v --cov=src               # 运行测试并生成覆盖率

# 方法3: 运行特定测试文件
pytest tests/unit/test_engine.py -v

# 方法4: 运行特定测试用例
pytest tests/unit/test_engine.py::TestSingletonPattern::test_singleton_returns_same_instance -v
```

## 📁 测试目录结构

```
tests/
├── conftest.py              # pytest配置和共享fixtures
├── unit/                    # 单元测试
│   ├── test_engine.py       # 核心引擎测试
│   ├── test_query_parser.py # 查询解析器测试
│   ├── test_cache_manager.py # 缓存管理器测试
│   ├── test_retrievers.py   # 检索器测试
│   └── test_analyzers.py    # 分析器测试
├── integration/             # 集成测试
│   ├── test_pipeline.py     # 完整流程测试
│   ├── test_cache_integration.py # 缓存集成测试
│   └── test_kb_integration.py # 知识库集成测试
└── e2e/                     # 端到端测试
    ├── test_api.py          # API测试
    └── test_web_interface.py # Web界面测试
```

## 🎯 测试覆盖目标

### 当前覆盖率 (v0.4.0)

| 模块 | 目标覆盖率 | 当前覆盖率 | 状态 |
|------|-----------|-----------|------|
| 核心引擎 | 80% | 待测试 | 🔴 |
| 查询解析器 | 70% | 待测试 | 🔴 |
| 证据分析器 | 70% | 待测试 | 🔴 |
| 真相总结器 | 70% | 待测试 | 🔴 |
| 检索器 | 60% | 待测试 | 🔴 |
| 缓存管理 | 80% | 待测试 | 🔴 |
| **总体** | **60%** | **待测试** | 🔴 |

### 测试用例统计

| 类别 | 计划 | 已完成 | 进度 |
|------|------|--------|------|
| 单元测试 | 150 | 50 | 33% |
| 集成测试 | 30 | 0 | 0% |
| 端到端测试 | 10 | 0 | 0% |
| **总计** | **190** | **50** | **26%** |

## 📝 编写测试

### 测试模板

```python
"""模块测试文档字符串"""
import pytest
from unittest.mock import Mock, patch

class TestFeature:
    """功能测试"""

    @pytest.fixture
    def setup_data(self):
        """测试数据fixture"""
        return {"key": "value"}

    def test_function_success(self, setup_data):
        """测试成功情况"""
        # Arrange
        input_data = setup_data

        # Act
        result = function_to_test(input_data)

        # Assert
        assert result is not None
        assert result.status == "success"

    def test_function_failure(self):
        """测试失败情况"""
        with pytest.raises(Exception):
            function_to_test(invalid_input)

    @pytest.mark.slow
    def test_slow_operation(self):
        """测试慢速操作"""
        # 这个测试会被标记为慢速测试
        pass
```

### 测试最佳实践

#### 1. 使用描述性名称

```python
# ✅ 好的命名
def test_cache_returns_null_for_missed_query():
    pass

# ❌ 不好的命名
def test_cache_1():
    pass
```

#### 2. 遵循AAA模式

```python
def test_user_authentication():
    # Arrange - 准备测试数据
    user = create_test_user(username="test")
    login_data = {"username": "test", "password": "pass"}

    # Act - 执行被测试的操作
    result = authenticate_user(login_data)

    # Assert - 验证结果
    assert result.is_authenticated is True
    assert result.user.username == "test"
```

#### 3. 使用fixtures

```python
@pytest.fixture
def mock_engine():
    """创建mock引擎"""
    engine = Mock()
    engine.run = Mock(return_value=test_result)
    return engine

def test_with_mock(mock_engine):
    result = mock_engine.run("query")
    assert result is not None
```

#### 4. 测试边界条件

```python
def test_edge_cases():
    # 测试空值
    result = function(None)

    # 测试空字符串
    result = function("")

    # 测试极大值
    result = function(999999)

    # 测试极小值
    result = function(-999999)
```

#### 5. Mock外部依赖

```python
@patch('src.core.pipeline.openai_call')
def test_with_mocked_api(mock_openai):
    # 设置mock返回值
    mock_openai.return_value = {"result": "test"}

    # 测试代码不会真正调用API
    result = function_that_calls_openai()

    assert result == "test"
```

## 🔧 常用命令

### 查看测试输出

```bash
# 详细输出
pytest tests/unit/test_engine.py -vv

# 只显示失败测试的详细信息
pytest tests/unit/test_engine.py -tb=short

# 显示print语句输出
pytest tests/unit/test_engine.py -s
```

### 运行特定标记的测试

```bash
# 只运行快速测试
pytest -m "not slow"

# 只运行单元测试
pytest -m unit

# 运行需要API的测试
pytest -m requires_api --run-api-tests
```

### 调试测试

```bash
# 在第一个失败时停止
pytest -x

# 进入调试器
pytest --pdb

# 在失败时进入调试器
pytest --pdb-failures
```

### 并行运行测试

```bash
# 安装pytest-xdist
pip install pytest-xdist

# 使用多进程运行
pytest -n auto
```

## 📊 持续集成

### CI/CD集成

在CI/CD流程中运行测试：

```yaml
# .github/workflows/test.yml 示例
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 🐛 调试技巧

### 1. 使用pdb断点

```python
def test_complex_logic():
    result = complex_function()
    import pdb; pdb.set_trace()  # 设置断点
    assert result == expected
```

### 2. 使用pytest的断言重写

```python
# pytest会提供详细的断言失败信息
def test_dict_comparison():
    result = {"a": 1, "b": 2}
    expected = {"a": 1, "b": 3}
    assert result == expected
    # 输出会显示具体哪个键值不匹配
```

### 3. 使用capsys捕获输出

```python
def test_output(capsys):
    print("test message")
    captured = capsys.readouterr()
    assert "test message" in captured.out
```

## 📚 参考资源

- [pytest文档](https://docs.pytest.org/)
- [pytest-cov文档](https://pytest-cov.readthedocs.io/)
- [Python测试最佳实践](https://docs.python-guide.org/writing/tests/)

---

**最后更新**：2026-02-07 (v0.4.0)
**维护者**：Claude (守门员)
