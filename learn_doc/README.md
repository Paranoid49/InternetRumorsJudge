# 互联网谣言粉碎机 - 学习文档目录

> 本目录包含项目的完整学习文档，帮助新人快速理解项目架构和实现细节
>
> 生成时间: 2026-02-09
> 项目版本: v0.7.0

---

## 📚 文档导航

### 🚀 快速入门

**推荐阅读顺序：**

1. **[快速入门指南](QUICK_START.md)** ⭐ 从这里开始
   - 环境准备
   - 安装步骤
   - 快速测试
   - 常见问题
   - **预计阅读时间：10分钟**

2. **[项目学习指南](PROJECT_LEARNING_GUIDE.md)** ⭐ 核心文档
   - 项目概览
   - 核心模块详解
   - 基础设施
   - 设计模式
   - 开发指南
   - **预计阅读时间：60分钟**

3. **[架构流程图](ARCHITECTURE_DIAGRAMS.md)** 📊 可视化理解
   - 整体数据流
   - 查询处理流程
   - 混合检索流程
   - 缓存系统流程
   - 知识集成流程
   - **预计阅读时间：30分钟**

4. **[模块关系](MODULE_RELATIONSHIPS.md)** 🔗 深度理解
   - 模块依赖层次
   - 核心模块详解
   - 依赖关系矩阵
   - 数据流图
   - **预计阅读时间：40分钟**

---

## 📖 文档结构

```
learn_doc/
├── README.md                    # 本文件 - 文档导航
├── QUICK_START.md               # 快速入门指南
├── PROJECT_LEARNING_GUIDE.md    # 项目学习指南（核心）
├── ARCHITECTURE_DIAGRAMS.md     # 架构流程图
└── MODULE_RELATIONSHIPS.md      # 模块关系与依赖
```

---

## 🎯 按角色阅读

### 👨‍💻 开发者

**目标：** 理解系统架构，准备开发新功能

**阅读路径：**
```
QUICK_START.md (5分钟)
    ↓
PROJECT_LEARNING_GUIDE.md 第一、二部分 (30分钟)
    ↓
ARCHITECTURE_DIAGRAMS.md (15分钟)
    ↓
MODULE_RELATIONSHIPS.md (20分钟)
```

**重点章节：**
- 核心模块详解（引擎层、协调器模式）
- 设计模式与最佳实践
- 模块依赖层次

---

### 🧪 测试工程师

**目标：** 理解系统流程，准备测试用例

**阅读路径：**
```
QUICK_START.md 快速测试部分 (10分钟)
    ↓
ARCHITECTURE_DIAGRAMS.md 所有流程图 (30分钟)
    ↓
PROJECT_LEARNING_GUIDE.md 第五部分 开发指南 (10分钟)
```

**重点章节：**
- 主要工作流程
- 错误处理流程
- 开发指南-测试部分

---

### 📝 技术写作者

**目标：** 理解系统设计，准备撰写文档

**阅读路径：**
```
PROJECT_LEARNING_GUIDE.md 全文 (60分钟)
    ↓
MODULE_RELATIONSHIPS.md (40分钟)
    ↓
ARCHITECTURE_DIAGRAMS.md (30分钟)
```

**重点章节：**
- 项目概览
- 核心模块详解（背景与目标、设计理由）
- 模块关系与依赖

---

### 🎓 学生/学习者

**目标：** 学习系统设计，理解架构模式

**阅读路径：**
```
QUICK_START.md (10分钟)
    ↓
PROJECT_LEARNING_GUIDE.md 第一部分 (15分钟)
    ↓
ARCHITECTURE_DIAGRAMS.md (30分钟)
    ↓
PROJECT_LEARNING_GUIDE.md 第二部分 (30分钟)
```

**重点章节：**
- 整体架构
- 主要工作流程
- 核心模块详解
- 设计模式与最佳实践

---

## 📋 核心概念速查

### 系统架构关键词

| 关键词 | 说明 | 相关文档 |
|--------|------|---------|
| **单例模式** | 引擎全局唯一实例 | 学习指南 2.1 |
| **协调器模式** | 分离关注点，提高可维护性 | 学习指南 2.2 |
| **双层缓存** | 精确匹配 + 语义相似度 | 学习指南 2.3 |
| **混合检索** | 本地向量库 + 联网搜索 | 学习指南 2.4 |
| **并行分析** | 动态并行度调整 | 学习指南 2.5 |
| **版本感知** | 知识库更新后缓存失效 | 学习指南 3.2 |
| **自我进化** | 高置信度结果自动沉淀 | 架构图 6 |

### 核心模块速查

| 模块 | 文件 | 核心职责 |
|------|------|---------|
| **RumorJudgeEngine** | src/core/pipeline.py | 总编排，单例模式 |
| **QueryProcessor** | src/core/coordinators/query_processor.py | 查询解析 + 缓存 + 并行检索 |
| **RetrievalCoordinator** | src/core/coordinators/retrieval_coordinator.py | 混合检索协调 |
| **AnalysisCoordinator** | src/core/coordinators/analysis_coordinator.py | 并行分析调度 |
| **VerdictGenerator** | src/core/coordinators/verdict_generator.py | 裁决生成 |
| **CacheManager** | src/core/cache_manager.py | 双层缓存 + 版本感知 |
| **HybridRetriever** | src/retrievers/hybrid_retriever.py | 混合检索策略 |
| **EvidenceAnalyzer** | src/analyzers/evidence_analyzer.py | 多角度证据分析 |

---

## 🔍 常见问题索引

### 安装与环境

- Q: 如何安装项目？
  - A: 见 [快速入门指南 - 安装步骤](QUICK_START.md#2-安装步骤)

- Q: 系统要求是什么？
  - A: 见 [快速入门指南 - 系统要求](QUICK_START.md#11-系统要求)

- Q: 如何获取API密钥？
  - A: 见 [快速入门指南 - API密钥准备](QUICK_START.md#12-api密钥准备)

### 使用与配置

- Q: 如何进行基本核查？
  - A: 见 [快速入门指南 - 快速测试](QUICK_START.md#3-快速测试)

- Q: 如何调整缓存策略？
  - A: 见 [快速入门指南 - 进阶配置](QUICK_START.md#71-调整缓存策略)

- Q: 如何更换LLM模型？
  - A: 见 [快速入门指南 - 常见问题](QUICK_START.md#10-常见问题)

### 架构与设计

- Q: 系统整体架构是怎样的？
  - A: 见 [项目学习指南 - 整体架构](PROJECT_LEARNING_GUIDE.md#12-整体架构)

- Q: 查询处理的完整流程是什么？
  - A: 见 [架构流程图 - 查询处理流程](ARCHITECTURE_DIAGRAMS.md#2-查询处理流程)

- Q: 模块之间如何依赖？
  - A: 见 [模块关系 - 依赖关系矩阵](MODULE_RELATIONSHIPS.md#3-依赖关系矩阵)

### 故障排查

- Q: 向量库构建失败怎么办？
  - A: 见 [快速入门指南 - 故障排查](QUICK_START.md#6-故障排查)

- Q: API调用失败怎么办？
  - A: 见 [快速入门指南 - 故障排查](QUICK_START.md#6-故障排查)

- Q: 如何启用调试日志？
  - A: 见 [快速入门指南 - 开发模式](QUICK_START.md#8-开发模式)

---

## 📊 文档统计

| 文档 | 字数 | 页面数（预估） | 图表数 |
|------|------|---------------|--------|
| 快速入门指南 | ~8,000 | ~20 | 0 |
| 项目学习指南 | ~25,000 | ~60 | 10 |
| 架构流程图 | ~6,000 | ~15 | 15 |
| 模块关系 | ~10,000 | ~25 | 8 |
| **总计** | **~49,000** | **~120** | **33** |

---

## 🛠️ 贡献文档

### 如何改进文档？

1. **发现错误**
   - 提交Issue描述问题
   - 指出具体位置和期望内容

2. **补充内容**
   - Fork项目
   - 修改对应文档
   - 提交Pull Request

3. **建议改进**
   - 提交Issue说明改进点
   - 讨论后实施

### 文档风格指南

- **语言**：简体中文
- **术语**：技术术语保持英文
- **格式**：使用Markdown
- **图表**：使用Mermaid语法
- **示例**：提供代码示例

---

## 📞 获取帮助

### 文档相关问题

如果您对文档有任何疑问：

1. 📖 先查看文档的常见问题部分
2. 🔍 使用文档搜索功能（Ctrl+F）
3. 💬 在项目中提交Issue

### 技术相关问题

- 📧 提交GitHub Issue
- 💬 加入讨论组（如有）
- 📚 查看项目README.md

---

## 📅 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-02-09 | v1.0 | 初始版本，创建完整学习文档 |

---

## 🎓 学习路径建议

### 路径1：快速上手（1小时）

```
1. QUICK_START.md (10分钟)
   - 了解项目
   - 安装运行
   - 快速测试

2. PROJECT_LEARNING_GUIDE.md - 第一部分 (15分钟)
   - 项目概览
   - 整体架构

3. ARCHITECTURE_DIAGRAMS.md - 主要工作流程 (10分钟)
   - 理解数据流

4. 实践：运行自己的查询 (25分钟)
```

### 路径2：深入学习（4小时）

```
1. QUICK_START.md (20分钟)
   - 完整阅读

2. PROJECT_LEARNING_GUIDE.md (90分钟)
   - 第一部分：项目概览
   - 第二部分：核心模块详解
   - 第三部分：基础设施

3. ARCHITECTURE_DIAGRAMS.md (60分钟)
   - 所有流程图
   - 理解交互细节

4. MODULE_RELATIONSHIPS.md (60分钟)
   - 模块依赖
   - 数据流

5. 实践：阅读源码 (10分钟)
   - 对照文档看代码
```

### 路径3：专家级（8小时+）

```
1. 完整阅读所有文档 (3小时)

2. 阅读源码 (3小时)
   - src/core/pipeline.py
   - src/core/coordinators/
   - src/retrievers/
   - src/analyzers/

3. 运行测试 (1小时)
   - tests/unit/
   - tests/integration/

4. 实践：添加新功能 (1小时+)
   - 添加新的分析维度
   - 调整检索策略
   - 优化性能
```

---

**开始学习：** [快速入门指南](QUICK_START.md) 🚀

---

**文档版本**: v1.0
**最后更新**: 2026-02-09
**维护者**: Claude (守门员)
