# 🤖 互联网谣言粉碎机 (Internet Rumors Judge)

> 基于RAG和LLM的智能谣言核查系统，具备实时互联网搜索和自我进化能力

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-green.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 特性

- 🔍 **智能核查**：基于RAG的语义检索，准确评估谣言真伪
- 🌐 **实时搜索**：集成互联网搜索，获取最新信息
- 🧠 **多模型协作**：解析、分析、裁决使用不同LLM模型
- ⚡ **高性能**：并行处理、动态并行度调整、语义缓存
- 📊 **API监控**：实时追踪API使用和成本
- 🔄 **自我进化**：自动将高置信度结果转化为本地知识
- 🛡️ **线程安全**：完整的并发安全保护

## 🏗️ 架构

```
查询输入
    ↓
1. 缓存检查（精确匹配 + 语义缓存）
    ↓ (未命中)
2. 查询解析（实体、主张、分类）+ 并行本地检索
    ↓
3. 混合检索（本地向量库 + 互联网搜索）
    ↓
4. 证据分析（多角度评估，并行处理）
    ↓
5. 裁决生成（综合证据，给出结论）
    ↓
6. 知识集成（后台异步更新向量库）
```

## 📦 核心模块

### 引擎层
- **RumorJudgeEngine** (`src/core/pipeline.py`): 单例引擎，编排整个核查流程
- **QueryProcessor** (`src/core/coordinators/query_processor.py`): 查询处理协调器
- **RetrievalCoordinator** (`src/core/coordinators/retrieval_coordinator.py`): 检索协调器
- **AnalysisCoordinator** (`src/core/coordinators/analysis_coordinator.py`): 分析协调器
- **VerdictGenerator** (`src/core/coordinators/verdict_generator.py`): 裁决生成器

### 检索层
- **EvidenceKnowledgeBase** (`src/retrievers/evidence_retriever.py`): 向量知识库
- **HybridRetriever** (`src/retrievers/hybrid_retriever.py`): 混合检索器（本地+网络）
- **WebSearchTool** (`src/retrievers/web_search_tool.py`): 互联网搜索工具

### 分析层
- **QueryParser** (`src/analyzers/query_parser.py`): 查询意图解析
- **EvidenceAnalyzer** (`src/analyzers/evidence_analyzer.py`): 证据评估分析
- **TruthSummarizer** (`src/analyzers/truth_summarizer.py`): 真相总结器

### 基础设施
- **CacheManager** (`src/core/cache_manager.py`): 双层缓存管理
- **ParallelismConfig** (`src/core/parallelism_config.py`): 动态并行度配置
- **APIMonitor** (`src/observability/api_monitor.py`): API使用监控

## 🚀 快速开始

### 环境要求

- Python 3.11+
- DashScope API Key ([获取地址](https://dashscope.aliyun.com/))
- Tavily API Key (可选，用于高质量网络搜索)

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/internet_rumors_judge.git
cd internet_rumors_judge

# 安装依赖
pip install -r requirements.txt

# 配置API密钥
export DASHSCOPE_API_KEY=your_dashscope_api_key
export TAVILY_API_KEY=your_tavily_api_key  # 可选
```

### 构建知识库

```bash
python -m src.retrievers.evidence_retriever build --force
```

### 命令行使用

```bash
# 单条核查
python scripts/main.py "喝隔夜水会致癌吗？"

# 查看帮助
python scripts/main.py --help
```

### Python API使用

```python
from src.core.pipeline import RumorJudgeEngine

# 创建引擎实例（单例）
engine = RumorJudgeEngine()

# 执行核查
result = engine.run("维生素C可以预防感冒吗？")

# 查看结果
print(f"裁决: {result.final_verdict}")
print(f"置信度: {result.confidence_score}%")
print(f"风险等级: {result.risk_level}")
print(f"摘要: {result.summary_report}")
print(f"证据数: {len(result.retrieved_evidence)}")
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行特定测试
pytest tests/unit/test_engine.py -v

# 查看测试覆盖率
pytest --cov=src --cov-report=html
```

## 📊 API监控

### 环境变量配置

```bash
# 设置每日预算（元）
export API_DAILY_BUDGET=10.0

# 设置每日token限制
export API_DAILY_TOKEN_LIMIT=100000

# 设置告警阈值（0-1之间）
export API_ALERT_THRESHOLD=0.8
```

### 使用监控

```python
from src.observability.api_monitor import get_api_monitor

# 获取监控器
monitor = get_api_monitor()

# 获取每日汇总
summary = monitor.get_daily_summary()
print(f"今日成本: {summary['total_cost']:.4f}元")
print(f"今日tokens: {summary['total_tokens']:,}")

# 生成报告
report = monitor.generate_report(days=7)
print(report)
```

## ⚙️ 配置

### 并行度配置

```bash
# 全局并行度
export MAX_WORKERS=20

# 任务特定并行度
export EVIDENCE_ANALYZER_WORKERS=15
export RETRIEVAL_WORKERS=12
```

### 缓存配置

```bash
# 语义缓存相似度阈值（默认0.96）
export SEMANTIC_CACHE_THRESHOLD=0.95

# 缓存TTL（秒）
export CACHE_TTL=86400  # 24小时
```

## 📖 文档

完整的文档请查看 [docs/INDEX.md](docs/INDEX.md)

### 快速链接

**入门**
- [快速开始](learn_doc/QUICK_START.md) - 5分钟上手
- [项目学习指南](learn_doc/PROJECT_LEARNING_GUIDE.md) - 完整学习路径

**架构**
- [系统架构](docs/ARCHITECTURE.md) - 架构设计详解
- [模块工作流程](docs/MODULE_WORKFLOWS.md) - 流程图和代码位置
- [架构图解](learn_doc/ARCHITECTURE_DIAGRAMS.md) - 可视化架构

**开发**
- [测试指南](docs/TESTING.md) - 测试规范和覆盖率
- [API 参考](docs/API_REFERENCE.md) - API 接口文档
- [Claude 开发指南](docs/CLAUDE.md) - Claude Code 工作指南

**部署**
- [部署指南](deployment/DEPLOY_GUIDE.md) - Docker 部署
- [部署检查清单](docs/DEPLOYMENT_CHECKLIST.md) - 上线前检查

## 📁 项目结构

```
internet_rumors_judge/
├── src/                          # 源代码
│   ├── core/                     # 核心引擎
│   │   ├── pipeline.py           # 主引擎
│   │   ├── coordinators/         # 协调器
│   │   ├── cache_manager.py      # 缓存管理
│   │   └── parallelism_config.py # 并行度配置
│   ├── retrievers/               # 检索模块
│   ├── analyzers/                # 分析模块
│   ├── knowledge/                # 知识管理
│   ├── observability/            # 可观测性
│   └── utils/                    # 工具函数
├── tests/                        # 测试代码
│   ├── unit/                     # 单元测试
│   └── integration/              # 集成测试
├── data/                         # 数据目录
│   └── rumors/                   # 谣言知识源
├── docs/                         # 文档
├── scripts/                      # 工具脚本
├── storage/                      # 运行时数据
├── requirements.txt              # 依赖列表
├── requirements.lock             # 锁定的依赖版本

[//]: # (└── OPTIMIZATION_LOG.md           # 优化日志)
```

## 🎯 核心功能

### 1. 查询解析

自动提取查询中的关键信息：
- **实体**: 谣言涉及的对象
- **主张**: 谣言声称的内容
- **分类**: 谣言类型（健康养生、食品安全、科技网络等）

### 2. 混合检索

结合本地知识和互联网搜索：
- **本地向量库**: ChromaDB + text-embedding-v4
- **语义相似度**: 余弦相似度匹配
- **网络兜底**: 本地相似度 < 0.4 时触发联网搜索
- **结果去重**: 基于内容哈希自动去重

### 3. 证据分析

多角度评估每条证据：
- **相关性**: 证据与主张的关联程度
- **立场**: 支持/反对/中立
- **权威性**: 来源的可信度评分（1-5分）
- **复杂性**: 识别夸大其词、断章取义等情况

### 4. 裁决生成

综合所有证据给出结论：
- **裁决类型**: 真/假/存在争议/证据不足
- **置信度**: 0-100%
- **风险等级**: 低/中/高
- **摘要报告**: 详细的推理过程

### 5. 自动知识沉淀

高置信度结果自动转化为本地知识：
- **触发条件**: 裁决为"真"或"假"，置信度 ≥ 90%，证据数 ≥ 3
- **后台处理**: 异步执行，不阻塞用户查询
- **版本管理**: 支持向量库的增量更新

## 📈 性能优化

### v0.6.0 引入的优化

- **动态并行度**: 根据CPU核心数自动调整（16核机器：5→15线程）
- **自适应调整**: 根据任务数量动态调整并行度
- **场景优化**: 不同任务类型使用不同策略

### 缓存策略

- **精确匹配缓存**: 基于MD5的精确缓存
- **语义向量缓存**: 相似度 > 0.96 时命中
- **版本感知**: 缓存带知识库版本信息

### 并行处理

- **查询解析 + 本地检索**: 并行执行（抢跑策略）
- **证据分析**: 批量并行分析
- **动态并行度**: 根据任务数自动调整

## 🔒 安全性

### 并发安全

- **单例模式**: 线程安全的单例创建
- **细粒度锁**: 使用LockManager统一管理锁
- **线程安全组件**: 所有共享状态都有锁保护

### API配额监控

- **成本追踪**: 实时记录API调用成本
- **配额告警**: 达到阈值时自动告警
- **数据持久化**: 历史数据永久保存

## 🐛 故障排查

### 常见问题

**Q: 向量库构建失败**
```bash
A: 确保data/rumors/目录下有.txt文件
   检查DASHSCOPE_API_KEY是否正确配置
```

**Q: API调用失败**
```bash
A: 检查API密钥是否有效
   查看配额是否用完
   检查网络连接
```

**Q: 结果不准确**
```bash
A: 尝试添加更多相关知识到data/rumors/
   调整相似度阈值
   启用联网搜索
```

## 📚 文档

- [COORDINATORS.md](docs/COORDINATORS.md) - 协调器模块文档
- [DEPENDENCY_MANAGEMENT.md](docs/DEPENDENCY_MANAGEMENT.md) - 依赖管理文档
- [TESTING.md](docs/TESTING.md) - 测试文档

[//]: # (- [OPTIMIZATION_LOG.md]&#40;OPTIMIZATION_LOG.md&#41; - 优化日志)

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👥 作者

Claude (守门员)

## 🙏 致谢

- [LangChain](https://python.langchain.com/) - 强大的LLM应用框架
- [DashScope](https://dashscope.aliyun.com/) - 通义千问API
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [Tavily](https://tavily.com/) - AI搜索API

---

**最后更新**: 2026-02-07

**当前版本**: v0.7.0
