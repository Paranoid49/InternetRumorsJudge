# Internet Rumors Judge (AI 谣言粉碎机)

这是一个基于 RAG (Retrieval-Augmented Generation) 和 LLM 的智能谣言核查系统。它结合了本地知识库检索和大型语言模型的通用知识，提供准确、有据可依的谣言粉碎服务。

## ✨ 主要功能

- **多模式核查**：
  - **RAG 模式**：优先检索本地构建的高质量谣言知识库（`data/rumors/`），提供可信证据。
  - **LLM 兜底**：当本地库无相关信息时，自动调用大模型通用知识进行初步判断，并给出置信度提示。
- **Web 可视化界面**：使用 Gradio 构建的交互式界面，支持谣言核查、历史记录查看和用户反馈。
- **API 服务化**：提供基于 FastAPI 的标准 REST API，支持流式输出 (SSE/NDJSON)，便于第三方应用集成。
- **智能反馈闭环**：
  - **收集**：通过 Web 界面收集用户反馈（正面/负面）。
  - **分析**：自动清洗、去重、分类反馈数据 (`feedback_analyzer.py`)。
  - **审核**：提供 CLI 工具 (`feedback_reviewer.py`) 人工审核负面反馈。
  - **进化**：自动将有效反馈转化为新的知识条目并更新向量数据库 (`knowledge_integrator.py`)。
- **高性能设计**：
  - **向量检索**：使用 ChromaDB 进行高效语义搜索。
  - **智能缓存**：集成 DiskCache，缓存高频查询结果，降低延迟和 Token 消耗。

## 🛠️ 安装说明

1. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/internet-rumors-judge.git
   cd internet-rumors-judge
   ```

2. **安装依赖**
   建议使用 Python 3.10+ 环境。
   ```bash
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   在项目根目录创建 `.env` 文件（可选）或直接设置环境变量。主要需要 LLM 的 API Key。
   ```bash
   # Linux/Mac
   export DASHSCOPE_API_KEY="your_api_key_here"
   
   # Windows (PowerShell)
   $env:DASHSCOPE_API_KEY="your_api_key_here"
   ```
   *注意：请在 `config.py` 中确认使用的 API Key 环境变量名称（默认为 `DASHSCOPE_API_KEY`，可根据需要修改）。*

## 🚀 快速开始

### 1. Docker 部署 (推荐)
这是最简单的部署方式，只需两步：

1. **设置环境变量**
   在根目录创建 `.env` 文件：
   ```env
   DASHSCOPE_API_KEY=your_api_key_here
   ```

2. **一键启动**
   ```bash
   docker-compose up -d
   ```
   启动后：
   - Web 界面: `http://localhost:7860`
   - API 服务: `http://localhost:8000`
   - API 文档: `http://localhost:8000/docs`

### 2. 命令行模式 (CLI)
直接在终端进行简单的谣言核查。
```bash
python main.py
# 然后根据提示输入谣言内容
```

### 2. 启动 Web 界面
启动 Gradio 界面，在浏览器中交互。
```bash
python web_interface.py
```
访问地址通常为：`http://127.0.0.1:7860`

### 3. 启动 API 服务
启动 FastAPI 服务，提供对外接口。
```bash
python api_service.py
```
- 服务地址：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

#### API 调用示例 (流式)
```python
import requests
import json

url = "http://127.0.0.1:8000/verify-stream"
payload = {"query": "吃洋葱能治感冒吗？", "use_cache": True}

response = requests.post(url, json=payload, stream=True)
for line in response.iter_lines(decode_unicode=True):
    if line:
        print(json.loads(line))
```

## 📂 项目结构

```
internet_rumors_judge/
├── api_service.py          # FastAPI 服务端入口
├── web_interface.py        # Gradio Web 界面入口
├── main.py                 # CLI 入口 & 核心流程调度
├── pipeline.py             # 核心逻辑编排 (RumorJudgeEngine)
├── evidence_retriever.py   # RAG 检索模块 (ChromaDB)
├── evidence_analyzer.py    # 证据分析与合成模块
├── truth_summarizer.py     # 最终真相总结模块
├── feedback_analyzer.py    # 反馈数据分析脚本
├── feedback_reviewer.py    # 反馈人工审核工具
├── knowledge_integrator.py # 知识库自动更新工具
├── config.py               # 项目配置
├── data/
│   └── rumors/             # 本地谣言知识库 (TXT文件)
└── ...
```

## 📝 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
