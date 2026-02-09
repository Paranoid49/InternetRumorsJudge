# 系统架构流程图详解

> 本文档包含互联网谣言粉碎机系统的核心流程图和架构图
>
> 生成时间: 2026-02-09

---

## 目录

1. [整体数据流](#1-整体数据流)
2. [查询处理流程](#2-查询处理流程)
3. [混合检索流程](#3-混合检索流程)
4. [证据分析流程](#4-证据分析流程)
5. [缓存系统流程](#5-缓存系统流程)
6. [知识集成流程](#6-知识集成流程)
7. [错误处理流程](#7-错误处理流程)

---

## 1. 整体数据流

```mermaid
flowchart TD
    subgraph "用户层"
        A[用户输入查询]
    end

    subgraph "接口层"
        B[RumorJudgeEngine.run]
    end

    subgraph "协调层"
        C[QueryProcessor]
        D[RetrievalCoordinator]
        E[AnalysisCoordinator]
        F[VerdictGenerator]
    end

    subgraph "执行层"
        G[QueryParser LLM]
        H[HybridRetriever]
        I[EvidenceAnalyzer LLM]
        J[TruthSummarizer LLM]
    end

    subgraph "存储层"
        K[CacheManager]
        L[EvidenceKnowledgeBase]
        M[WebSearchTool]
    end

    A --> B
    B --> C
    C --> K
    C --> G
    C -.->|并行抢跑| L
    D --> H
    H --> L
    H --> M
    E --> I
    F --> J
    D -.->|去重格式化| E
    E -.->|分析结果| F
    F --> K
    C -.->|缓存未命中| D

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style K fill:#e8f5e9
    style L fill:#e8f5e9
    style M fill:#e8f5e9
```

**数据流说明：**

1. **用户层 → 接口层**：用户查询传入引擎
2. **接口层 → 协调层**：引擎调度各协调器
3. **协调层 → 执行层**：协调器调用具体执行器
4. **执行层 → 存储层**：执行器访问缓存和知识库
5. **存储层 → 执行层**：返回数据
6. **执行层 → 协调层**：返回处理结果
7. **协调层 → 接口层**：汇总结果
8. **接口层 → 用户层**：返回最终裁决

---

## 2. 查询处理流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Engine as RumorJudgeEngine
    participant QP as QueryProcessor
    participant Parser as QueryParser
    participant Cache as CacheManager
    participant KB as 知识库

    User->>Engine: run(query)
    Engine->>Engine: _lazy_init()

    rect rgb(200, 230, 255)
        Note over Engine,KB: 阶段1: 并行解析和检索
        Engine->>QP: parse_with_parallel_retrieval(query)
        par 并行执行
            QP->>Parser: invoke(query)
            QP->>KB: search_local(query)
        end
        Parser-->>QP: QueryAnalysis
        KB-->>QP: local_docs
        QP-->>Engine: (analysis, local_docs)
    end

    rect rgb(200, 255, 200)
        Note over Engine,Cache: 阶段2: 缓存检查
        Engine->>QP: check_cache(query)
        QP->>Cache: get_verdict(query)

        alt 精确缓存命中
            Cache-->>QP: cached_result
            QP-->>Engine: cached_result
            Engine-->>User: 返回缓存结果
        else 精确未命中，检查语义
            Cache->>Cache: vector_cache.similarity_search()
            alt 语义缓存命中
                Cache-->>QP: cached_result
                QP-->>Engine: cached_result
                Engine-->>User: 返回缓存结果
            else 语义未命中
                Cache-->>QP: None
                QP-->>Engine: None
                Note over Engine: 继续执行后续流程
            end
        end
    end

    rect rgb(255, 230, 200)
        Note over Engine: 返回解析结果
        Engine-->>User: 继续检索流程
    end
```

**流程说明：**

1. **并行执行**：查询解析和本地检索同时进行，节省时间
2. **抢跑策略**：用原始词提前检索，即使解析后词不同，结果也有价值
3. **双层缓存**：先精确匹配（O(1)），再语义匹配（向量检索）
4. **缓存学习**：语义命中后，将查询加入精确缓存

---

## 3. 混合检索流程

```mermaid
flowchart TD
    A[开始混合检索] --> B{已有本地<br/>文档?}
    B -->|否| C[本地向量检索]
    B -->|是| D[使用已有文档]

    C --> E[计算最大相似度]
    D --> E

    E --> F{对自动生成<br/>内容降权}
    F --> G[应用AUTO_GEN_WEIGHT<br/>加权系数]

    G --> H{相似度达标?}
    H -->|相似度 >= 0.6<br/>且有结果| I[跳过联网搜索]
    H -->|无结果或<br/>相似度 < 0.6| J[触发联网搜索]

    J --> K[调用WebSearchTool]
    K --> L[获取网络结果]
    L --> M[转换为Document格式]

    I --> N[合并本地+网络]
    M --> N

    N --> O[第一阶段:<br/>哈希精确去重]
    O --> P[第二阶段:<br/>内容相似度模糊去重]

    P --> Q[排序策略]
    Q --> R[本地证据 +0.5权重]
    Q --> S[联网证据 原始分数]
    Q --> T[AUTO_GEN文档 -0.1降权]

    R --> U[按分数降序排序]
    S --> U
    T --> U

    U --> V[返回Top-N结果<br/>默认N=3]

    style J fill:#ffcccc
    style I fill:#ccffcc
    style V fill:#e1f5ff
```

**决策逻辑说明：**

| 条件 | 动作 | 原因 |
|------|------|------|
| 无本地结果 | 联网搜索 | 本地知识不足 |
| 相似度 < 0.6 | 联网搜索 | 本地质量不足 |
| 相似度 ≥ 0.6 | 跳过联网 | 本地质量足够 |

**降权策略：**

- **自动生成内容**：乘以 `AUTO_GEN_WEIGHT`（默认0.9）
- **排序时再降权**：减去0.1，确保排在人工内容后

---

## 4. 证据分析流程

```mermaid
flowchart TD
    A[接收证据列表] --> B{证据数量?}

    B -->|1条| C[单次批量分析]
    B -->|2-5条| D[单证据并行分析]
    B -->|>5条| E[分片并行分析]

    rect rgb(200, 230, 255)
        D --> F[为每个证据<br/>创建独立任务]
        F --> G[动态计算并行度]
        G --> H[ThreadPoolExecutor]
        H --> I[并行调用LLM]
        I --> J[汇总结果]
    end

    rect rgb(255, 230, 200)
        E --> K[分片 chunk_size=2]
        K --> L[创建分片任务]
        L --> M[动态计算并行度]
        M --> N[ThreadPoolExecutor]
        N --> O[并行处理分片]
        O --> P[汇总所有分片结果]
    end

    rect rgb(200, 255, 200)
        C --> Q[单次LLM调用]
        Q --> R[返回结果]
    end

    J --> S[按ID排序]
    P --> S
    R --> S

    S --> T[返回分析结果]

    style D fill:#e1f5ff
    style E fill:#ffe1f5
    style C fill:#e1ffe1
```

**并行策略选择：**

| 证据数 | 策略 | 原因 |
|--------|------|------|
| 1 | 单次调用 | 无需并行 |
| 2-5 | 单证据并行 | 每个证据独立，粒度细，容错好 |
| >5 | 分片并行 | 避免创建过多线程，降低开销 |

**动态并行度计算：**

```python
max_workers = get_parallelism_config().get_adaptive_workers(
    task_count=len(evidence_list),
    task_type='evidence_analyzer',
    min_workers=1
)
```

---

## 5. 缓存系统流程

```mermaid
flowchart TD
    A[查询缓存] --> B{版本已变化?}

    B -->|是| C[返回None<br/>触发重新查询]
    B -->|否| D[精确缓存检查]

    D --> E{精确命中?}
    E -->|是| F{版本有效?}
    E -->|否| G[语义缓存检查]

    F -->|是| H[返回缓存结果]
    F -->|否| I[删除过期缓存]
    I --> G

    G --> J{语义命中?}
    J -->|是| K{版本有效?}
    J -->|否| L[返回None]

    K -->|是| M[获取语义缓存数据]
    M --> N[更新精确缓存<br/>加速下次查询]
    N --> H

    K -->|否| O[删除过期语义缓存]
    O --> L

    H --> P[记录日志]
    P --> Q[返回FinalVerdict]

    style C fill:#ffcccc
    style H fill:#ccffcc
    style L fill:#ffffcc
```

**版本检查逻辑：**

```mermaid
flowchart TD
    A[检查版本] --> B{缓存有版本号?}
    B -->|否| C{当前有版本?}
    B -->|是| D{版本匹配?}

    C -->|否| E[有效<br/>首次构建前]
    C -->|是| F[无效<br/>首次构建后的旧缓存]

    D -->|是| E
    D -->|否| F

    E --> G[返回缓存]
    F --> H[返回None<br/>缓存失效]
```

**缓存写入流程：**

```mermaid
sequenceDiagram
    participant Writer as CacheManager.set_verdict
    participant Exact as 精确缓存
    participant Vector as 语义缓存
    participant VM as VersionManager

    Writer->>VM: 获取当前版本
    VM-->>Writer: version_id

    Writer->>Writer: 构造缓存数据<br/>附加版本信息
    Writer->>Exact: 存入精确缓存
    Writer->>Vector: 检查是否有极相似查询
    alt 无极相似查询
        Writer->>Vector: 添加向量索引
    end
```

---

## 6. 知识集成流程

```mermaid
flowchart TD
    A[核查完成] --> B{满足自动<br/>集成条件?}

    B -->|否| C[跳过集成]
    B -->|是| D[检查准入门槛]

    D --> E{裁决为"真"或"假"?}
    E -->|否| C
    E -->|是| F{置信度 >= 90%?}

    F -->|否| C
    F -->|是| G{证据数 >= 3?}

    G -->|否| C
    G -->|是| H[启动后台集成线程]

    H --> I[获取知识集成锁]
    I --> J{获取成功?}
    J -->|否| K[跳过<br/>已有任务运行]
    J -->|是| L[生成知识内容]

    L --> M[构造AUTO_GEN<br/>文件名]
    M --> N[写入知识文件]

    N --> O[增量重构向量库]
    O --> P[更新版本号]

    P --> Q[释放锁]
    Q --> R[日志记录完成]

    style H fill:#e1f5ff
    style K fill:#ffcccc
    style R fill:#ccffcc
```

**准入门槛（严格模式）：**

| 条件 | 阈值 | 原因 |
|------|------|------|
| 裁决类型 | "真"或"假" | 避免模糊内容 |
| 置信度 | ≥ 90% | 确保高可靠性 |
| 证据数 | ≥ 3 | 确保有充分证据 |
| 是否联网 | 是 | 确保是新知识 |

**文件命名规范：**

```
AUTO_GEN_{timestamp}_{safe_title}.txt

示例：
AUTO_GEN_1707521234维生素C防感冒.txt
```

**版本更新：**

```mermaid
sequenceDiagram
    participant KI as KnowledgeIntegrator
    participant VM as VersionManager
    participant KB as EvidenceKnowledgeBase

    KI->>VM: 创建新版本
    VM->>VM: 生成版本ID<br/>格式: YYYYMMDD_HHMMSS
    VM->>VM: 保存版本文件
    VM-->>KI: 新版本对象

    KI->>KB: 增量重构向量库
    KB->>KB: 加载所有文档
    KB->>KB: 重新向量化
    KB->>KB: 持久化
    KB-->>KI: 构建完成

    KI->>VM: 更新版本信息
    VM->>VM: 记录文档数量
    VM->>VM: 记录来源
```

---

## 7. 错误处理流程

```mermaid
flowchart TD
    A[执行操作] --> B{发生异常?}

    B -->|否| C[正常返回]
    B -->|是| D[异常类型判断]

    D --> E[TimeoutError]
    D --> F[ImportError]
    D --> G[ValueError]
    D --> H[其他异常]

    E --> I[记录超时日志]
    I --> J[返回降级结果]

    F --> K[记录导入失败日志]
    K --> L[回退到默认实现]

    G --> M[记录参数错误日志]
    M --> N[返回错误信息]

    H --> O[记录异常日志]
    O --> P[返回兜底结果]

    J --> Q[添加错误元数据]
    L --> Q
    N --> Q
    P --> Q

    Q --> R[返回UnifiedVerificationResult<br/>标记为is_fallback=True]

    style E fill:#ffe1e1
    style F fill:#fff4e1
    style G fill:#f5e1ff
    style H fill:#e1f5ff
```

**错误处理策略：**

| 异常类型 | 处理策略 | 示例 |
|---------|---------|------|
| `TimeoutError` | 记录日志，返回降级结果 | 获取锁超时，跳过操作 |
| `ImportError` | 回退到默认实现 | 协调器不可用，使用legacy代码 |
| `ValueError` | 返回错误信息 | 参数验证失败 |
| 其他异常 | 返回兜底结果 | LLM调用失败，使用兜底裁决 |

**兜底裁决示例：**

```python
# 无证据时的兜底机制
if not evidence_list:
    verdict = summarize_with_fallback(full_claim)
    result.is_fallback = True
```

**元数据记录：**

```python
result.add_metadata(
    PipelineStage.ANALYSIS,
    False,  # success=False
    error="证据分析失败",
    duration=0
)
```

---

## 附录：图表使用指南

### Mermaid语法说明

本文档使用Mermaid图表，支持的查看器：

1. **GitHub/GitLab**：原生支持
2. **VS Code**：安装 Markdown Preview Mermaid Support 插件
3. **在线查看**：https://mermaid.live/

### 颜色方案说明

| 颜色 | 含义 |
|------|------|
| 🔵 浅蓝 | 用户接口层 |
| 🟡 浅黄 | 引擎/协调层 |
| 🟢 浅绿 | 存储层/成功路径 |
| 🔴 浅红 | 错误/警告 |
| ⚪ 灰色 | 兜底/降级 |

---

**文档版本**: v1.0
**最后更新**: 2026-02-09
