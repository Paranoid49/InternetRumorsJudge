# 快速入门指南

> 互联网谣言粉碎机 - 5分钟快速上手
>
> 生成时间: 2026-02-09

---

## 目录

1. [环境准备](#1-环境准备)
2. [安装步骤](#2-安装步骤)
3. [快速测试](#3-快速测试)
4. [核心概念](#4-核心概念)
5. [常见用例](#5-常见用例)
6. [故障排查](#6-故障排查)
7. [进阶配置](#7-进阶配置)

---

## 1. 环境准备

### 1.1 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10+, Linux, macOS | 任意 |
| Python | 3.11+ | 3.11+ |
| 内存 | 4GB | 8GB+ |
| 磁盘 | 2GB 可用空间 | 5GB+ |

### 1.2 API密钥准备

**必需：**
- [DashScope API Key](https://dashscope.aliyun.com/) - 通义千问API

**可选：**
- [Tavily API Key](https://tavily.com/) - 高质量联网搜索

---

## 2. 安装步骤

### 2.1 克隆项目

```bash
git clone https://github.com/yourusername/internet_rumors_judge.git
cd internet_rumors_judge
```

### 2.2 创建虚拟环境

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2.3 安装依赖

```bash
pip install -r requirements.txt
```

### 2.4 配置API密钥

**方式1：环境变量（推荐）**

**Windows:**
```cmd
set DASHSCOPE_API_KEY=your_api_key_here
set TAVILY_API_KEY=your_tavily_key_here
```

**Linux/Mac:**
```bash
export DASHSCOPE_API_KEY=your_api_key_here
export TAVILY_API_KEY=your_tavily_key_here
```

**方式2：.env文件**

创建 `.env` 文件：
```bash
DASHSCOPE_API_KEY=your_api_key_here
TAVILY_API_KEY=your_tavily_key_here
```

### 2.5 构建知识库

```bash
python -m src.retrievers.evidence_retriever build
```

**预期输出：**
```
正在加载谣言知识库...
知识库构建完成！
- 文档数量: XXX
- 向量维度: XXX
```

---

## 3. 快速测试

### 3.1 命令行测试

```bash
python scripts/main.py "喝隔夜水会致癌吗？"
```

**预期输出：**
```
开始核查请求: 喝隔夜水会致癌吗？
意图解析完成: 实体='隔夜水', 主张='致癌'
检索完成: 获得3条证据
证据分析完成: 3条
生成裁决完成...

裁决: 假
置信度: 95%
风险等级: 低
摘要: 隔夜水不会致癌...
```

### 3.2 Python代码测试

创建测试文件 `test_demo.py`：

```python
from src.core.pipeline import RumorJudgeEngine

# 创建引擎（单例）
engine = RumorJudgeEngine()

# 执行核查
result = engine.run("维生素C可以预防感冒吗？")

# 查看结果
print(f"裁决: {result.final_verdict}")
print(f"置信度: {result.confidence_score}%")
print(f"风险等级: {result.risk_level}")
print(f"摘要: {result.summary_report}")
print(f"证据数: {len(result.retrieved_evidence)}")
print(f"来自缓存: {result.is_cached}")
print(f"使用联网: {result.is_web_search}")
```

运行测试：
```bash
python test_demo.py
```

---

## 4. 核心概念

### 4.1 系统架构

```
查询输入
    ↓
1. 缓存检查（精确 + 语义）
    ↓ (未命中)
2. 查询解析（实体、主张、分类）
    ↓
3. 混合检索（本地 + 联网）
    ↓
4. 证据分析（多角度并行）
    ↓
5. 裁决生成（综合证据）
    ↓
6. 知识集成（高置信度自动沉淀）
```

### 4.2 核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| **引擎** | src/core/pipeline.py | 总编排 |
| **查询处理** | src/core/coordinators/query_processor.py | 解析+缓存 |
| **检索协调** | src/core/coordinators/retrieval_coordinator.py | 混合检索 |
| **分析协调** | src/core/coordinators/analysis_coordinator.py | 并行分析 |
| **裁决生成** | src/core/coordinators/verdict_generator.py | 生成裁决 |
| **缓存管理** | src/core/cache_manager.py | 双层缓存 |
| **向量知识库** | src/retrievers/evidence_retriever.py | 本地知识 |

### 4.3 数据模型

**UnifiedVerificationResult**
```python
{
    "query": "喝隔夜水会致癌吗？",
    "final_verdict": "假",
    "confidence_score": 95,
    "risk_level": "低",
    "summary_report": "...",
    "retrieved_evidence": [...],
    "evidence_assessments": [...],
    "is_cached": false,
    "is_web_search": true
}
```

---

## 5. 常见用例

### 5.1 基本核查

```python
from src.core.pipeline import RumorJudgeEngine

engine = RumorJudgeEngine()
result = engine.run("微波炉加热食物会产生辐射吗？")
```

### 5.2 禁用缓存

```python
# 强制重新查询，不使用缓存
result = engine.run("某个谣言", use_cache=False)
```

### 5.3 查看处理元数据

```python
result = engine.run("某个谣言")

# 查看各阶段处理情况
for metadata in result.metadata:
    print(f"阶段: {metadata.stage}")
    print(f"成功: {metadata.success}")
    print(f"耗时: {metadata.duration_ms}ms")
    if metadata.error_message:
        print(f"错误: {metadata.error_message}")
```

### 5.4 查看证据详情

```python
result = engine.run("某个谣言")

# 遍历证据
for i, evidence in enumerate(result.retrieved_evidence, 1):
    print(f"\n证据 #{i}:")
    print(f"内容: {evidence['text']}")
    print(f"来源: {evidence['metadata']['source']}")
    print(f"相似度: {evidence['metadata'].get('similarity', 'N/A')}")

# 查看证据评估
if result.evidence_assessments:
    for assessment in result.evidence_assessments:
        print(f"\n评估 #{assessment.id}:")
        print(f"相关性: {assessment.relevance}")
        print(f"立场: {assessment.stance}")
        print(f"复杂情况: {assessment.complexity_label}")
        print(f"权威性: {assessment.authority_score}/5")
```

### 5.5 API监控

```python
from src.observability.api_monitor import get_api_monitor

monitor = get_api_monitor()

# 获取今日使用情况
summary = monitor.get_daily_summary()
print(f"今日成本: {summary['total_cost']:.2f}元")
print(f"今日tokens: {summary['total_tokens']:,}")
print(f"调用次数: {summary['call_count']}")
print(f"剩余预算: {summary['remaining_budget']:.2f}元")

# 生成7日报告
report = monitor.generate_report(days=7)
print(report)
```

---

## 6. 故障排查

### 6.1 向量库构建失败

**症状：**
```
Error: Unable to connect to ChromaDB
```

**解决方案：**
1. 检查API密钥是否正确
```bash
echo $DASHSCOPE_API_KEY
```

2. 检查网络连接
```bash
ping dashscope.aliyuncs.com
```

3. 清理缓存重试
```bash
rm -rf storage/vectors
python -m src.retrievers.evidence_retriever build --force
```

### 6.2 API调用失败

**症状：**
```
Error: Invalid API key
```

**解决方案：**
1. 重新设置API密钥
```bash
export DASHSCOPE_API_KEY=your_new_key
```

2. 测试API连接
```python
from src.utils.llm_factory import create_parser_llm
llm = create_parser_llm()
print(llm.invoke("测试"))
```

### 6.3 结果不准确

**症状：**
裁决与事实不符

**解决方案：**

1. 添加更多相关知识到 `data/rumors/`

2. 调整相似度阈值
```bash
export MIN_LOCAL_SIMILARITY=0.5  # 降低阈值，更容易触发联网
```

3. 启用联网搜索
```bash
export TAVILY_API_KEY=your_key
```

### 6.4 性能慢

**症状：**
单次查询超过30秒

**解决方案：**

1. 启用缓存（默认已启用）
```python
result = engine.run("query", use_cache=True)
```

2. 调整并行度
```bash
export MAX_WORKERS=20  # 增加并行度
```

3. 启用快速模式
```bash
export ENABLE_FAST_MODE=True  # 降低temperature
```

---

## 7. 进阶配置

### 7.1 调整缓存策略

```bash
# 语义缓存相似度阈值（默认0.96）
export SEMANTIC_CACHE_THRESHOLD=0.95

# 缓存过期时间（默认24小时）
export CACHE_TTL=86400
```

### 7.2 调整检索策略

```bash
# 本地检索相似度阈值（默认0.6）
export MIN_LOCAL_SIMILARITY=0.5

# 最大返回证据数（默认3）
export MAX_RESULTS=5
```

### 7.3 调整自动知识集成

```bash
# 最小置信度（默认90）
export AUTO_INTEGRATE_MIN_CONFIDENCE=85

# 最小证据数（默认3）
export AUTO_INTEGRATE_MIN_EVIDENCE=2
```

### 7.4 调整并行度

```bash
# 全局最大并行度（默认CPU核心数*2）
export MAX_WORKERS=20

# 证据分析并行度
export EVIDENCE_ANALYZER_WORKERS=15

# 检索并行度
export RETRIEVAL_WORKERS=12
```

### 7.5 调整API预算

```bash
# 每日预算（元）
export API_DAILY_BUDGET=10.0

# 每日token限制
export API_DAILY_TOKEN_LIMIT=100000

# 告警阈值（0-1）
export API_ALERT_THRESHOLD=0.8
```

---

## 8. 开发模式

### 8.1 启用调试日志

```python
from src.observability import configure_logging
configure_logging(log_level="DEBUG", json_output=False)
```

### 8.2 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 查看覆盖率
pytest --cov=src --cov-report=html
```

### 8.3 性能测试

```bash
python scripts/run_tests.py --benchmark
```

### 8.4 健康检查

```bash
python scripts/health_check_report.py
```

---

## 9. 下一步

- 📖 阅读 [完整学习指南](PROJECT_LEARNING_GUIDE.md)
- 📊 查看 [架构流程图](ARCHITECTURE_DIAGRAMS.md)
- 🔗 了解 [模块关系](MODULE_RELATIONSHIPS.md)
- 🧪 运行 [测试用例](../tests/)

---

## 10. 常见问题

### Q1: 如何添加新的知识？

**A:** 将文本文件放入 `data/rumors/` 目录，然后重建知识库：
```bash
python -m src.retrievers.evidence_retriever build --force
```

### Q2: 如何更换LLM模型？

**A:** 修改 `src/config.py`:
```python
MODEL_PARSER = "qwen-plus"
MODEL_ANALYZER = "qwen-plus"
MODEL_SUMMARIZER = "qwen-max"
```

### Q3: 如何禁用联网搜索？

**A:** 设置环境变量：
```bash
export TAVILY_API_KEY=""  # 留空
```

或在代码中：
```python
evidence_list = retrieval_coordinator.retrieve(
    query=query,
    use_web_search=False
)
```

### Q4: 如何查看系统日志？

**A:** 日志文件位置：
```
project_logs/
├── api_usage.log
├── engine.log
├── retriever.log
└── analyzer.log
```

### Q5: 如何清空缓存？

**A:**
```python
from src.core.pipeline import RumorJudgeEngine

engine = RumorJudgeEngine()
engine.cache_manager.clear()
```

---

**文档版本**: v1.0
**最后更新**: 2026-02-09
**维护者**: Claude (守门员)
