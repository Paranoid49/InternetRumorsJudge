# Internet Rumors Judge (AI 谣言粉碎机)

这是一个基于 **RAG (Retrieval-Augmented Generation)** 和 **实时互联网搜索** 的智能谣言核查系统。它不仅能检索本地高质量知识库，还能自动通过互联网获取最新事实，并具备“自我进化”的学习能力。

## ✨ 主要功能

- **🚀 混合检索系统 (Hybrid Retrieval)**：
  - **本地 RAG**：优先检索本地构建的高质量谣言知识库 (`data/rumors/`)，确保核心数据的权威性。
  - **实时联网搜索**：集成 **Tavily AI** (首选) 和 **DuckDuckGo**。当本地相似度不足时，自动触发全网搜索，获取最新事实。
  - **智能触发逻辑**：基于向量相似度阈值自动决定是否需要“向外求助”。
- **🧠 深度证据分析**：
  - 采用多角度分析模型，识别证据的立场（支持/反对）、权威性及复杂情况（如夸大其词、断章取义、过时信息等）。
- **🔄 自我进化闭环 (Self-Learning)**：
  - **自动补齐**：当系统通过联网搜索获得高置信度结论时，会自动将其结构化并回填至本地知识库。
  - **反馈学习**：支持用户反馈，通过人工审核后自动转化为本地知识。
- **📊 透明化处理流程**：
  - 详尽的阶段性日志记录，支持查看每一步的耗时、相似度分值、证据来源等，便于调试和审计。
- **🌐 多端支持**：
  - **Web 界面**：使用 Gradio 构建，支持交互式核查与历史记录。
  - **API 服务**：基于 FastAPI 提供 REST 接口，支持流式输出 (NDJSON)。
  - **Docker 支持**：一键部署，环境隔离。

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
# 必填：通义千问 API Key (或其他 OpenAI 兼容 API)
DASHSCOPE_API_KEY=your_dashscope_key

# 建议：Tavily AI API Key (用于高质量联网搜索)
TAVILY_API_KEY=your_tavily_key

# 可选：配置其它模型参数
```

## 🚀 部署方式

### 方式 A：Docker 部署 (推荐)
```bash
# 一键启动 API 和 Web 服务
docker-compose up -d
```
- **Web 界面**: `http://localhost:7860`
- **API 服务**: `http://localhost:8000`
- **API 文档**: `http://localhost:8000/docs`

### 方式 B：本地开发模式
```bash
# 启动 Web 界面
python web_interface.py

# 启动 API 服务
python api_service.py
```

## 📂 核心模块说明

- [pipeline.py](file:///app/pipeline.py): **系统大脑**，负责编排解析、检索、分析和总结的全流程。
- [hybrid_retriever.py](file:///app/hybrid_retriever.py): **智能检索器**，基于相似度阈值自动切换本地 RAG 和 Web 搜索。
- [web_search_tool.py](file:///app/web_search_tool.py): **联网工具**，封装了 LangChain 版 Tavily 和 DDG 搜索。
- [evidence_analyzer.py](file:///app/evidence_analyzer.py): **证据分析师**，对搜集到的多来源证据进行交叉验证。
- [knowledge_integrator.py](file:///app/knowledge_integrator.py): **知识集成器**，负责将新发现的真相沉淀到本地向量库。

## 🔍 调试与日志

系统在运行过程中会输出详细的日志。你可以通过日志观察：
- 本地检索的最高相似度分值。
- 是否触发了联网搜索及其原因。
- 检索到的证据数量（本地 vs 联网）。
- 自动知识集成的触发状态。

```bash
# Docker 环境下查看实时日志
docker logs rumor-api -f
```

## 📝 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
