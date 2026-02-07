# API参考文档

本文档提供互联网谣言粉碎机系统的完整API参考。

## 目录

- [核心引擎API](#核心引擎api)
- [协调器API](#协调器api)
- [查询处理API](#查询处理api)
- [检索API](#检索api)
- [分析API](#分析api)
- [监控API](#监控api)

---

## 核心引擎API

### RumorJudgeEngine

主引擎类，采用单例模式，是系统的入口点。

```python
from src.core.pipeline import RumorJudgeEngine
```

#### 方法

##### `run(query: str, use_cache: bool = True) -> UnifiedVerificationResult`

执行完整的谣言核查流程。

**参数**:
- `query` (str): 待核查的查询文本
- `use_cache` (bool): 是否使用缓存，默认True

**返回**:
- `UnifiedVerificationResult`: 核查结果对象

**示例**:
```python
engine = RumorJudgeEngine()
result = engine.run("喝隔夜水会致癌吗？")

print(f"裁决: {result.final_verdict}")
print(f"置信度: {result.confidence_score}%")
```

**返回字段**:
```python
class UnifiedVerificationResult(BaseModel):
    query: str                              # 原始查询
    is_cached: bool                         # 是否使用缓存
    is_fallback: bool                        # 是否使用兜底机制
    is_web_search: bool                      # 是否使用联网搜索
    saved_to_cache: bool                     # 是否保存到缓存

    # 解析阶段
    entity: Optional[str]                     # 实体
    claim: Optional[str]                      # 主张
    category: Optional[str]                   # 分类

    # 检索阶段
    retrieved_evidence: List[Dict]           # 检索到的证据

    # 分析阶段
    evidence_assessments: List               # 证据评估结果

    # 结论阶段
    final_verdict: Optional[str]             # 最终裁决
    confidence_score: int                     # 置信度 (0-100)
    risk_level: Optional[str]                 # 风险等级
    summary_report: Optional[str]             # 摘要报告

    # 元数据
    metadata: List[ProcessingMetadata]        # 处理过程元数据
```

---

## 协调器API

### QueryProcessor

查询处理协调器，负责查询解析和缓存检查。

#### 方法

##### `parse_query(query: str) -> Optional[QueryAnalysis]`

解析查询，提取实体、主张和分类。

**参数**:
- `query` (str): 查询文本

**返回**:
- `QueryAnalysis`: 解析结果对象

**示例**:
```python
from src.core.coordinators import QueryProcessor

processor = QueryProcessor(
    parser_chain=parser_chain,
    cache_manager=cache_manager,
    hybrid_retriever=retriever
)

analysis = processor.parse_query("维生素C能预防感冒吗？")
print(f"实体: {analysis.entity}")  # 维生素C
print(f"主张: {analysis.claim}")   # 维生素C能预防感冒
print(f"分类: {analysis.category}") # 健康养生
```

##### `parse_with_parallel_retrieval(query: str) -> Tuple[QueryAnalysis, List]`

并行执行查询解析和本地检索（抢跑策略）。

**参数**:
- `query` (str): 查询文本

**返回**:
- `(QueryAnalysis, List)`: (解析结果, 本地文档列表)

**示例**:
```python
parsed, local_docs = processor.parse_with_parallel_retrieval("查询")
```

##### `check_cache(query: str) -> Optional[FinalVerdict]`

检查缓存。

**参数**:
- `query` (str): 查询文本

**返回**:
- `FinalVerdict`: 缓存的裁决结果，如果未命中返回None

---

### RetrievalCoordinator

检索协调器，负责证据检索和去重。

#### 方法

##### `retrieve(query: str, use_web_search: bool = True) -> List[Dict]`

执行检索（本地 + 网络）。

**参数**:
- `query` (str): 查询文本
- `use_web_search` (bool): 是否使用网络搜索，默认True

**返回**:
- `List[Dict]`: 证据列表（字典格式）

**示例**:
```python
from src.core.coordinators import RetrievalCoordinator

coordinator = RetrievalCoordinator(
    hybrid_retriever=retriever,
    kb=knowledge_base
)

evidence_list = coordinator.retrieve("查询")
print(f"检索到 {len(evidence_list)} 条证据")
```

##### `retrieve_with_parsed_query(query: str, parsed_info: QueryAnalysis, local_docs: List = None) -> List[Dict]`

使用解析后的查询进行检索。

**参数**:
- `query` (str): 原始查询
- `parsed_info` (QueryAnalysis): 解析后的查询信息
- `local_docs` (List): 已有的本地文档

**返回**:
- `List[Dict]`: 证据列表

##### `get_retrieval_stats(evidence_list: List[Dict]) -> dict`

获取检索统计信息。

**返回**:
```python
{
    'total': 3,      # 总证据数
    'local': 3,      # 本地证据数
    'web': 0,        # 网络证据数
    'is_web_search': False
}
```

---

### AnalysisCoordinator

分析协调器，负责证据分析。

#### 方法

##### `analyze(claim: str, evidence_list: List[Dict]) -> List[EvidenceAssessment]`

分析证据列表。

**参数**:
- `claim` (str): 主张
- `evidence_list` (List[Dict]): 证据列表

**返回**:
- `List[EvidenceAssessment]`: 评估结果列表

**示例**:
```python
from src.core.coordinators import AnalysisCoordinator

coordinator = AnalysisCoordinator()

assessments = coordinator.analyze(
    claim="喝隔夜水会致癌",
    evidence_list=evidence_list
)

for assessment in assessments:
    print(f"相关性: {assessment.relevance}")
    print(f"立场: {assessment.stance}")
    print(f"理由: {assessment.reason}")
```

##### `summarize_assessments(assessments: List[EvidenceAssessment]) -> dict`

汇总评估结果。

**返回**:
```python
{
    'total': 5,
    'supporting': 2,
    'opposing': 3,
    'neutral': 0,
    'high_relevance': 4
}
```

---

### VerdictGenerator

裁决生成器，负责生成最终裁决。

#### 方法

##### `generate(query: str, entity: str, claim: str, evidence_list: List, assessments: List) -> FinalVerdict`

生成最终裁决。

**参数**:
- `query` (str): 原始查询
- `entity` (str): 实体
- `claim` (str): 主张
- `evidence_list` (List): 证据列表
- `assessments` (List): 评估结果列表

**返回**:
- `FinalVerdict`: 裁决对象

**示例**:
```python
from src.core.coordinators import VerdictGenerator

generator = VerdictGenerator()

verdict = generator.generate(
    query="喝隔夜水会致癌吗？",
    entity="隔夜水",
    claim="喝隔夜水会致癌",
    evidence_list=evidence_list,
    assessments=assessments
)

print(f"裁决: {verdict.verdict}")      # VerdictType.FALSE
print(f"置信度: {verdict.confidence}%") # 95
print(f"摘要: {verdict.summary}")
```

---

## 查询处理API

### QueryAnalysis

查询分析结果对象。

```python
from src.analyzers.query_parser import QueryAnalysis

class QueryAnalysis(BaseModel):
    entity: str                  # 实体
    claim: str                   # 主张
    category: str                 # 分类
    original_query: str          # 原始查询
```

---

## 检索API

### HybridRetriever

混合检索器，结合本地向量库和网络搜索。

#### 方法

##### `search_hybrid(query: str, existing_local_docs: List = None, use_web_search: bool = True) -> List[Document]`

混合检索。

**参数**:
- `query` (str): 查询文本
- `existing_local_docs` (List): 已有的本地文档
- `use_web_search` (bool): 是否使用网络搜索

**返回**:
- `List[Document]`: 文档对象列表

**检索策略**:
1. 本地相似度 >= 0.4: 仅使用本地结果
2. 本地相似度 < 0.4: 触发网络搜索

---

## 分析API

### EvidenceAssessment

证据评估结果。

```python
class EvidenceAssessment(BaseModel):
    id: int                     # 证据ID
    relevance: str              # 相关性（高/中/低）
    stance: str                 # 立场（支持/反对/中立）
    reason: str                 # 判断依据
    supporting_quote: str        # 支持性引用
    confidence: float            # 置信度 (0.0-1.0)
    authority_score: int         # 权威性评分 (1-5)
```

### FinalVerdict

最终裁决对象。

```python
class FinalVerdict(BaseModel):
    verdict: VerdictType         # 裁决类型
    confidence: int              # 置信度 (0-100)
    summary: str                 # 摘要报告
    risk_level: str              # 风险等级（低/中/高）
```

**VerdictType 枚举**:
- `TRUE`: 真
- `FALSE`: 假
- `CONTROVERSIAL`: 存在争议
- `INSUFFICIENT`: 证据不足

---

## 监控API

### APIMonitor

API监控器，追踪API使用和成本。

```python
from src.observability.api_monitor import get_api_monitor, QuotaConfig
```

#### 方法

##### `record_api_call(provider, model, endpoint, input_tokens=0, output_tokens=0, total_tokens=None) -> float`

记录API调用。

**参数**:
- `provider` (str): 提供商 (dashscope, tavily)
- `model` (str): 模型名称
- `endpoint` (str): 端点/操作
- `input_tokens` (int): 输入token数
- `output_tokens` (int): 输出token数
- `total_tokens` (int): 总token数（可选）

**返回**:
- `float`: 成本（元）

**示例**:
```python
monitor = get_api_monitor()

cost = monitor.record_api_call(
    provider='dashscope',
    model='qwen-plus',
    endpoint='chat',
    input_tokens=1000,
    output_tokens=500
)
```

##### `get_daily_summary(date: Optional[datetime] = None) -> Dict`

获取每日汇总。

**返回**:
```python
{
    'date': '2026-02-07',
    'total_cost': 0.0078,
    'total_tokens': 3500,
    'api_calls': 3,
    'by_model': {
        'qwen-plus': {
            'cost': 0.0014,
            'tokens': 1500,
            'calls': 1
        }
    }
}
```

##### `generate_report(days: int = 7) -> str`

生成监控报告。

**参数**:
- `days` (int): 报告天数

**返回**:
- `str`: 报告文本

---

### ParallelismConfig

并行度配置，根据系统资源自动调整。

```python
from src.core.parallelism_config import get_parallelism_config
```

#### 方法

##### `get_max_workers(task_type: str = 'default') -> int`

获取最大并行度。

**参数**:
- `task_type` (str): 任务类型
  - `default`: 通用任务
  - `evidence_analyzer`: 证据分析
  - `retrieval`: 检索
  - `embedding`: 嵌入计算

**返回**:
- `int`: 最大并行度

**示例**:
```python
config = get_parallelism_config()

# 获取证据分析的并行度
workers = config.get_max_workers('evidence_analyzer')
print(f"证据分析最大并行度: {workers}")  # 15 (16核机器)
```

##### `get_adaptive_workers(task_count, task_type, min_workers=1) -> int`

获取自适应并行度。

**参数**:
- `task_count` (int): 任务数量
- `task_type` (str): 任务类型
- `min_workers` (int): 最小并行度

**返回**:
- `int`: 建议的并行度

**示例**:
```python
# 3个任务，使用3个worker
workers = config.get_adaptive_workers(3, 'evidence_analyzer')
print(f"并行度: {workers}")  # 3

# 20个任务，使用15个worker（受限于最大值）
workers = config.get_adaptive_workers(20, 'evidence_analyzer')
print(f"并行度: {workers}")  # 15
```

---

## 配置

### 环境变量

```bash
# API密钥
export DASHSCOPE_API_KEY=your_key
export TAVILY_API_KEY=your_key

# 缓存配置
export SEMANTIC_CACHE_THRESHOLD=0.96
export CACHE_TTL=86400

# 并行度配置
export MAX_WORKERS=20
export EVIDENCE_ANALYZER_WORKERS=15
export RETRIEVAL_WORKERS=12

# API监控配置
export API_DAILY_BUDGET=10.0
export API_DAILY_TOKEN_LIMIT=100000
export API_ALERT_THRESHOLD=0.8

# 数据目录
export RUMOR_DATA_DIR=data/rumors
export STORAGE_DIR=storage
```

---

## 错误处理

### 异常类型

#### PipelineError

流程错误基类。

```python
class PipelineError(Exception):
    """流程错误"""
    pass
```

#### CacheError

缓存错误。

```python
class CacheError(Exception):
    """缓存操作失败"""
    pass
```

---

## 完整示例

### 基本使用

```python
from src.core.pipeline import RumorJudgeEngine

# 创建引擎
engine = RumorJudgeEngine()

# 执行核查
result = engine.run("维生素C可以预防感冒吗？")

# 查看结果
if result.is_cached:
    print("使用缓存结果")
else:
    print("执行完整核查")

print(f"裁决: {result.final_verdict}")
print(f"置信度: {result.confidence_score}%")
print(f"摘要: {result.summary_report}")
print(f"证据数: {len(result.retrieved_evidence)}")
```

### 高级使用 - 自定义配置

```python
from src.core.pipeline import RumorJudgeEngine
from src.observability.api_monitor import get_api_monitor, QuotaConfig
from src.core.parallelism_config import get_parallelism_config

# 配置API监控
quota_config = QuotaConfig(
    daily_budget=10.0,
    daily_token_limit=100000
)
monitor = get_api_monitor(quota_config)

# 查看并行度配置
config = get_parallelism_config()
print(f"默认并行度: {config.get_max_workers()}")

# 执行核查
engine = RumorJudgeEngine()
result = engine.run("查询", use_cache=False)

# 查看API使用情况
summary = monitor.get_daily_summary()
print(f"今日成本: {summary['total_cost']:.4f}元")
```

---

**API版本**: v0.8.0
**最后更新**: 2026-02-07
**维护者**: Claude (守门员)
