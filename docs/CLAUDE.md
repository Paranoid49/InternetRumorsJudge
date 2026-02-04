# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概览

**Internet Rumors Judge (AI 谣言粉碎机)** 是一个基于 RAG 的智能谣言核查系统，具备实时互联网搜索能力。系统采用混合检索方式（本地向量数据库 + 网络搜索），通过语义缓存优化性能，并支持自我进化的知识集成。

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 构建或重建向量知识库
python -m src.retrievers.evidence_retriever build --force

# 增量更新知识库（仅处理新文档）
python -m src.retrievers.evidence_retriever build

# 测试检索
python -m src.retrievers.evidence_retriever search "测试查询" -k 3

# 运行命令行核查
python scripts/main.py "待核查的查询"

# 运行 API 服务器
python -m uvicorn src.services.api_service:app --host 0.0.0.0 --port 8000

# 运行 Web 界面
python src/services/web_interface.py

# Docker 部署
cd deployment && ./deploy.sh
# 或: docker compose up -d --build
```

## 架构概览

系统采用由 `pipeline.py` 中 `RumorJudgeEngine`（单例模式）编排的**流水线架构**：

### 流水线流程

```
查询输入
    ↓
1. 缓存管理器（精确匹配 + 语义缓存，相似度 > 0.96）
    ↓ (未命中)
2. 查询解析器（提取实体、主张、分类）- 与本地检索并行执行
    ↓
3. 混合检索器（本地 RAG + 网络搜索兜底）
    ↓
4. 证据分析器（多角度评估，Top-3 证据）
    ↓
5. 真相总结器（生成最终裁决）
    ↓
6. 知识集成器（后台异步更新向量库）
```

### 关键设计模式

- **单例引擎**: `RumorJudgeEngine` 确保全局唯一实例，组件延迟初始化
- **双层缓存**: 精确匹配（MD5）+ 语义向量缓存（ChromaDB）
- **模型分级**: 不同任务使用不同 LLM（解析/分析用 qwen-plus，最终裁决用 qwen-max）
- **异步后台学习**: 知识集成在守护线程中运行，不阻塞用户响应
- **混合检索**: 优先本地向量搜索，相似度低于阈值（0.4）时触发网络搜索

### 核心组件

| 模块 | 路径 | 用途 | 关键细节 |
|------|------|------|----------|
| RumorJudgeEngine | src/core/pipeline.py | 编排引擎 | 单例、延迟初始化、线程安全 |
| HybridRetriever | src/retrievers/hybrid_retriever.py | 本地 + 网络搜索 | 基于阈值的网络兜底（0.4），结果去重 |
| CacheManager | src/core/cache_manager.py | 语义缓存 | 双层（精确 + 向量），0.96 相似度阈值 |
| EvidenceKnowledgeBase | src/retrievers/evidence_retriever.py | 向量知识库 | ChromaDB + text-embedding-v4，支持增量更新 |
| EvidenceAnalyzer | src/analyzers/evidence_analyzer.py | 证据评估 | Top-3 并行分析 |
| TruthSummarizer | src/analyzers/truth_summarizer.py | 裁决生成 | 使用 qwen-max 生成最终结论 |
| KnowledgeIntegrator | src/knowledge/knowledge_integrator.py | 后台学习 | 异步线程，自动生成知识文件 |

### 数据流要点

- **并行执行**: 查询解析与本地检索并行运行（`ThreadPoolExecutor`）
- **语义缓存性能**: 命中耗时 < 5ms（完整流水线约 25s）
- **自动集成条件**: 裁决必须为"真"/"假"，置信度 >= 90，证据数量 >= 3
- **加权评分**: AUTO_GEN_* 文档在相似度计算中按 90% 权重处理

## 配置说明

`.env` 环境变量：
```env
DASHSCOPE_API_KEY=your_key  # 必填：通义千问 API
TAVILY_API_KEY=your_key     # 可选：高质量网络搜索
```

`config.py` 关键设置：
- `MODEL_PARSER`: qwen-plus（意图解析）
- `MODEL_ANALYZER`: qwen-plus（证据分析）
- `MODEL_SUMMARIZER`: qwen-max（最终裁决）
- `EMBEDDING_MODEL`: text-embedding-v4
- `SIMILARITY_THRESHOLD`: 0.25

## 文件结构

```
src/                      # 源代码目录
├── core/                 # 核心引擎
│   ├── pipeline.py       # RumorJudgeEngine
│   └── cache_manager.py  # 缓存管理
├── retrievers/           # 检索模块
│   ├── evidence_retriever.py
│   ├── hybrid_retriever.py
│   └── web_search_tool.py
├── analyzers/            # 分析模块
│   ├── query_parser.py
│   ├── evidence_analyzer.py
│   └── truth_summarizer.py
├── knowledge/            # 知识管理
│   └── knowledge_integrator.py
└── services/             # 服务接口
    ├── api_service.py
    └── web_interface.py

tests/                    # 测试代码
scripts/                  # 工具脚本（main.py 等）
storage/                  # 运行时数据
├── vector_db/            # ChromaDB 持久化存储
├── cache/                # 精确匹配缓存
└── semantic_cache/       # 语义缓存

data/                     # 源数据
└── rumors/               # 知识源文档（.txt 文件）

docs/                     # 文档
deployment/               # 部署配置
```

## 重要实现细节

1. **嵌入模型**: 使用 DashScope 的 `text-embedding-v4`，通过 OpenAI 兼容 API 调用
2. **向量相似度**: ChromaDB 余弦距离，转换为相似度（1 - distance）
3. **线程安全**: `_integration_lock` 防止并发后台知识集成
4. **错误处理**: 未找到证据时回退到 LLM 内部知识进行兜底
5. **去重机制**: 基于内容哈希（前 100 字符）进行证据去重
