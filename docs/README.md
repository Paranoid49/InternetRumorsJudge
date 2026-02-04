# Internet Rumors Judge (AI 谣言粉碎机)

这是一个基于 **RAG (Retrieval-Augmented Generation)** 和 **实时互联网搜索** 的智能谣言核查系统。它不仅能检索本地高质量知识库，还能自动通过互联网获取最新事实，并具备“自我进化”的学习能力。

## ✨ 主要功能

- **🚀 混合检索系统 (Hybrid Retrieval)**：
  - **本地 RAG**：优先检索本地构建的高质量谣言知识库 (`data/rumors/`)。
  - **实时联网搜索**：集成 **Tavily AI**。当本地相似度不足时，自动触发全网搜索，获取最新事实。
  - **智能补测逻辑**：自动识别解析词与原始词，确保本地库命中率最大化，同时严格控制联网次数（单次核查仅限 1 次联网）。
- **⚡ 语义缓存 (Semantic Cache)**：
  - 基于 **text-embedding-v4** 的向量缓存机制。
  - 自动识别意思相近但表述不同的问题（相似度 > 0.96）。
  - **性能飞跃**：命中缓存时，响应时间从 25s 降至 **1ms**。
- **🧠 深度证据分析**：
  - 采用多角度分析模型，识别证据立场、权威性及复杂情况。
  - **性能优化**：精选 Top-3 核心证据进行并行/深度分析，大幅缩减 LLM 处理耗时。
- **🔄 后台自我进化 (Async Self-Learning)**：
  - **异步集成**：核查完成后，系统在后台自动生成知识档案并更新向量库，完全不占用用户等待时间。
  - **增量构建**：向量库支持增量更新，秒级处理新加入的知识。
- **☁️ 云端原生架构**：
  - 全面采用 **DashScope (通义千问)** 云端向量模型，无需下载庞大的本地模型（如 Torch），镜像体积缩减 80%。

## ⏱️ 性能指标

| 场景 | 响应耗时 | 备注 |
| :--- | :--- | :--- |
| **精确/语义命中缓存** | **< 5ms** | 极速响应，无需任何计算 |
| **本地库命中 (RAG)** | **~5-8s** | 包含解析、检索与总结 |
| **全流程核查 (含联网)** | **~25s** | 包含实时搜索与多证据深度分析 |

## 🔧 最近优化 (2026-02-04)

### 1. 超时控制机制
- 为所有 LLM 调用添加 30 秒超时限制
- 防止请求挂死，提升系统稳定性
- 可在 `config.py` 中配置 `LLM_REQUEST_TIMEOUT`

### 2. 统一配置管理
- 将所有阈值参数集中到 `config.py`
- 便于 A/B 测试和生产环境调优
- 新增配置项：
  - `MIN_LOCAL_SIMILARITY`: 本地检索相似度阈值
  - `MAX_RESULTS`: 检索返回的最大证据数量
  - `SEMANTIC_CACHE_THRESHOLD`: 语义缓存相似度阈值
  - `DEFAULT_CACHE_TTL`: 默认缓存过期时间
  - `AUTO_INTEGRATE_MIN_CONFIDENCE`: 自动知识集成最小置信度
  - `AUTO_INTEGRATE_MIN_EVIDENCE`: 自动知识集成最小证据数量
  - `AUTO_GEN_WEIGHT`: AUTO_GEN_* 文档的相似度加权系数

### 3. 智能去重算法
- 改进证据去重逻辑，使用两阶段去重策略：
  1. 精确哈希去重（基于前 500 字符）
  2. 内容相似度模糊去重（SequenceMatcher，阈值 0.85）
- 减少证据遗漏，提升准确率
- 添加去重统计日志，便于监控

## 🛠️ 安装说明

### 1. 克隆与环境准备
```bash
git clone https://github.com/yourusername/internet-rumors-judge.git
cd internet-rumors-judge
pip install -r requirements.txt
```

### 2. 配置环境变量
在项目根目录创建 `.env` 文件：
```env
# 必填：通义千问 API Key
DASHSCOPE_API_KEY=your_dashscope_key

# 建议：Tavily AI API Key (用于高质量联网搜索)
TAVILY_API_KEY=your_tavily_key
```

## 🚀 部署方式

### 方式 A：一键自动化部署 (推荐)
```bash
# 赋予权限并运行部署脚本
chmod +x deployment/deploy.sh
cd deployment
./deploy.sh
```

### 方式 B：手动 Docker 部署
```bash
cd deployment
# 如果你的系统支持 Docker V2 (推荐)
docker compose up -d --build

# 如果你还在使用旧版 V1
docker-compose up -d --build
```

## 🎯 快速开始

### 命令行模式
```bash
# 运行核查
python scripts/main.py "吸烟有害健康"
```

### API 服务模式
```bash
# 启动 FastAPI 服务
python -m uvicorn src.services.api_service:app --host 0.0.0.0 --port 8000
```

### Web 界面模式
```bash
# 启动 Gradio Web UI
python src/services/web_interface.py
```

### 构建向量库
```bash
# 完整重建
python -m src.retrievers.evidence_retriever build --force

# 增量更新
python -m src.retrievers.evidence_retriever build
```

## 📂 项目结构

```
src/                    # 源代码
├── core/              # 核心引擎（pipeline, cache_manager）
├── retrievers/        # 检索模块
├── analyzers/         # 分析模块
├── knowledge/         # 知识管理
└── services/          # API 和 Web 服务

tests/                  # 测试代码
scripts/                # 工具脚本（main.py 等）
storage/                # 运行时数据（vector_db, cache）
data/                   # 源数据（rumors/）
docs/                   # 文档
deployment/             # 部署配置
```

## 📂 核心模块说明

**目录结构**:
```
src/
├── core/
│   ├── pipeline.py          # 系统大脑，全流程编排
│   └── cache_manager.py     # 语义缓存中心
├── retrievers/
│   ├── hybrid_retriever.py  # 智能检索器
│   ├── evidence_retriever.py # 向量库专家
│   └── web_search_tool.py   # 联网搜索工具
├── analyzers/
│   ├── query_parser.py      # 查询意图解析
│   ├── evidence_analyzer.py # 证据分析
│   └── truth_summarizer.py  # 真相总结
├── knowledge/
│   └── knowledge_integrator.py # 知识沉淀器
└── services/
    ├── api_service.py       # FastAPI 服务
    └── web_interface.py     # Gradio Web UI
```

## 📝 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
