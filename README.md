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
# 赋予权限并运行部署脚本（自动适配 Docker V1/V2）
chmod +x deploy.sh
./deploy.sh
```

### 方式 B：手动 Docker 部署
```bash
# 如果你的系统支持 Docker V2 (推荐)
docker compose up -d --build

# 如果你还在使用旧版 V1
docker-compose up -d --build
```

## 📂 核心模块说明

- [pipeline.py](file:///d:/projects/python/learn/internet_rumors_judge/pipeline.py): **系统大脑**，负责异步任务管理与全流程编排。
- [cache_manager.py](file:///d:/projects/python/learn/internet_rumors_judge/cache_manager.py): **语义缓存中心**，管理精确匹配与向量相似度缓存。
- [hybrid_retriever.py](file:///d:/projects/python/learn/internet_rumors_judge/hybrid_retriever.py): **智能检索器**，执行本地与联网的混合调度。
- [evidence_retriever.py](file:///d:/projects/python/learn/internet_rumors_judge/evidence_retriever.py): **向量库专家**，基于 text-embedding-v4 实现增量索引。
- [knowledge_integrator.py](file:///d:/projects/python/learn/internet_rumors_judge/knowledge_integrator.py): **知识沉淀器**，负责后台异步构建辟谣档案。

## 📝 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。
