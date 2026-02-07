# 依赖管理指南

## 📋 概述

本系统使用两级依赖管理机制，确保开发、测试和生产环境的一致性。

## 🔧 依赖文件说明

### 1. `requirements.txt`
**用途**：定义依赖的允许版本范围
**特点**：
- 使用语义化版本约束（如 `>=1.0.0,<2.0.0`）
- 允许补丁和次版本更新
- 锁定主版本，避免breaking changes

**使用场景**：
- 开发环境安装：`pip install -r requirements.txt`
- 允许小版本升级以获取bug修复

### 2. `requirements.lock`
**用途**：记录所有依赖的精确版本
**特点**：
- 完全锁定版本号（如 `==1.2.6`）
- 确保跨环境完全一致
- 包含所有间接依赖

**使用场景**：
- 生产环境部署：`pip install -r requirements.lock`
- CI/CD流程：确保可重现构建
- 问题复现：精确匹配生产环境

## 📊 版本约束策略

### 核心框架（LangChain生态）
```txt
langchain-core>=0.1.0,<2.0.0
langchain>=0.1.0,<2.0.0
```
**策略**：允许次版本更新
**原因**：LangChain向后兼容性好，频繁发布bug修复

### LangChain集成
```txt
langchain-openai>=0.1.0,<2.0.0
langchain-community>=0.1.0,<1.0.0
```
**策略**：锁定主版本
**原因**：API变化较快，避免breaking changes

### Web框架
```txt
fastapi>=0.100.0,<0.200.0
gradio>=4.0.0,<7.0.0
```
**策略**：锁定主版本，允许较大次版本范围
**原因**：快速演进中，需要一定的灵活性

### 数据处理
```txt
pydantic>=2.0.0,<3.0.0
pandas>=2.0.0,<3.0.0
```
**策略**：锁定主版本
**原因**：重大版本变化显著（如Pydantic v1→v2）

## 🚀 安装依赖

### 开发环境
```bash
# 安装允许版本范围内的最新版本
pip install -r requirements.txt
```

### 生产环境
```bash
# 安装精确版本，确保完全一致
pip install -r requirements.lock
```

### 开发特定依赖
```bash
# 安装单个依赖（允许版本范围）
pip install -r requirements.txt --no-deps
pip install langchain-core

# 安装单个依赖（精确版本）
pip install langchain-core==1.2.7
```

## 🔄 更新依赖流程

### 安全更新小版本
```bash
# 1. 检查可用更新
pip list --outdated

# 2. 更新特定依赖
pip install --upgrade langchain-core

# 3. 测试功能是否正常
pytest tests/

# 4. 更新lock文件
pip freeze > requirements.lock

# 5. 提交变更
git add requirements.txt requirements.lock
git commit -m "chore: upgrade langchain-core to 1.2.8"
```

### 主版本升级（需谨慎）
```bash
# 1. 查看变更日志
# https://github.com/langchain-ai/langchain/releases

# 2. 创建新分支
git checkout -b upgrade/langchain-v2

# 3. 更新版本约束
# 编辑 requirements.txt: langchain>=2.0.0,<3.0.0

# 4. 安装并测试
pip install -r requirements.txt
pytest tests/

# 5. 更新lock文件
pip freeze > requirements.lock

# 6. 提交并审查
git add requirements.txt requirements.lock
git commit -m "feat: upgrade langchain to v2.0.0"
```

## ⚠️ 注意事项

### 1. 不要手动编辑 `requirements.lock`
- `requirements.lock` 应该由 `pip freeze` 自动生成
- 手动编辑可能导致依赖冲突

### 2. 提交前检查
```bash
# 检查依赖是否一致
pip install -r requirements.lock
pytest tests/
```

### 3. 定期审计依赖
```bash
# 检查安全漏洞
pip install safety
safety check

# 检查过期依赖
pip list --outdated
```

### 4. 生产部署
- **必须**使用 `requirements.lock`
- **禁止**直接使用 `requirements.txt`
- **验证**环境一致后再部署

## 🔍 故障排查

### 依赖冲突
```bash
# 查看依赖树
pip install pipdeptree
pipdeptree

# 查找冲突
pipdeptree --warn conflict
```

### 版本不匹配
```bash
# 强制重装
pip install --force-reinstall -r requirements.lock

# 清理缓存
pip cache purge
```

### 虚拟环境问题
```bash
# 创建干净的虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
pip install -r requirements.lock
```

## 📚 相关资源

- [语义化版本规范](https://semver.org/lang/zh-CN/)
- [Python打包用户指南](https://packaging.python.org/guides/)
- [依赖管理最佳实践](https://www.python.org/dev/peps/pep-0621/)

---

**最后更新**：2026-02-07 (v0.2.0)
**维护者**：Claude (守门员)
