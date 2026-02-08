# 互联网谣言粉碎机 - 模块工作流程详解

> **面向新手的完整指南**：本文档详细说明了系统中每个模块的工作流程、关键代码位置和数据流向，帮助新手快速理解项目架构。

**目录**：
1. [整体系统架构](#1-整体系统架构)
2. [核心引擎流程](#2-核心引擎流程)
3. [查询处理流程](#3-查询处理流程)
4. [检索协调流程](#4-检索协调流程)
5. [证据分析流程](#5-证据分析流程)
6. [裁决生成流程](#6-裁决生成流程)
7. [缓存系统流程](#7-缓存系统流程)
8. [知识库管理流程](#8-知识库管理流程)
9. [知识集成流程](#9-知识集成流程)
10. [可观测性模块流程](#10-可观测性模块流程)
11. [工具函数流程](#11-工具函数流程)
12. [基础设施流程](#12-基础设施流程)

---

## 1. 整体系统架构

### 1.1 系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     服务层 (Services)                        │
│  ┌────────────────┐           ┌──────────────────┐          │
│  │  API Service   │           │  Web Interface   │          │
│  │  (FastAPI)     │           │  (Gradio)        │          │
│  └────────┬───────┘           └────────┬─────────┘          │
└───────────┼───────────────────────────┼────────────────────┘
            │                           │
            └───────────┬───────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│                  核心引擎层 (Core Engine)                     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │           RumorJudgeEngine (单例模式)                  │   │
│  │  - 统一入口：run(query)                               │   │
│  │  - 编排所有协调器                                     │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│                  协调器层 (Coordinators)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Query      │  │  Retrieval   │  │  Analysis    │        │
│  │  Processor   │  │ Coordinator  │  │ Coordinator  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│  ┌──────────────────────────────────┐                      │
│  │     Verdict Generator           │                      │
│  └──────────────────────────────────┘                      │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│                  服务层 (Analyzers & Retrievers)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Query       │  │  Evidence    │  │   Truth      │        │
│  │  Parser      │  │  Analyzer    │  │  Summarizer  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │   Hybrid     │  │   Evidence   │                          │
│  │  Retriever   │  │ KnowledgeBase │                          │
│  └──────────────┘  └──────────────┘                          │
└───────────────────────┬───────────────────────────────────────┘
                        │
┌───────────────────────▼───────────────────────────────────────┐
│              基础设施层 (Infrastructure)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  Cache   │  │Knowledge │  │   LLM    │  │   Web    │     │
│  │ Manager  │  │Integrator│  │ Factory  │  │  Search  │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Metrics  │  │   API    │  │  Logger  │                   │
│  │Collector │  │ Monitor  │  │ Config  │                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└───────────────────────────────────────────────────────────────┘
```

**代码位置**：
- 核心引擎：`src/core/pipeline.py:RumorJudgeEngine` (596行)
- 协调器层：`src/core/coordinators/`
- 分析器：`src/analyzers/`
- 检索器：`src/retrievers/`
- 基础设施：`src/core/cache_manager.py`, `src/observability/`

---

## 2. 核心引擎流程

### 2.1 RumorJudgeEngine 整体流程

```
用户查询 "喝隔夜水会致癌吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  1. 获取引擎实例（单例模式）         │
│  RumorJudgeEngine.get_instance()    │
│  位置：pipeline.py:138-156          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  2. 检查缓存                        │
│  cache_manager.get_verdict(query)   │
│  位置：pipeline.py:193-199          │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │             │
    缓存命中     缓存未命中
        │             │
        ▼             ▼
   直接返回    ┌──────────────────────┐
              │ 3. 查询处理           │
              │ - 解析意图            │
              │ - 并行检索本地库      │
              │ 位置：pipeline.py:202 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 4. 证据检索           │
              │ - 混合检索策略        │
              │ - 去重和排序         │
              │ 位置：pipeline.py:210 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 5. 证据分析           │
              │ - 预过滤证据          │
              │ - 批量分析           │
              │ 位置：pipeline.py:219 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 6. 裁决生成           │
              │ - 综合证据评估       │
              │ - 生成最终裁决       │
              │ 位置：pipeline.py:226 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 7. 缓存结果          │
              │ cache_manager.set_   │
              │   verdict(query, ...) │
              │ 位置：pipeline.py:235 │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ 8. 自动知识集成       │
              │ (后台异步)            │
              │ - 检查条件            │
              │ - 生成知识文件        │
              │ - 重建向量库          │
              │ 位置：pipeline.py:242 │
              └──────────┬───────────┘
                         │
                         ▼
                   返回 UnifiedVerificationResult
```

**关键代码位置**：
- 主入口：`src/core/pipeline.py:186-294` (RumorJudgeEngine.run)
- 单例创建：`src/core/pipeline.py:138-156`
- 缓存检查：`src/core/pipeline.py:193-199`
- 查询处理：`src/core/pipeline.py:202-207`
- 证据检索：`src/core/pipeline.py:210-216`
- 证据分析：`src/core/pipeline.py:219-224`
- 裁决生成：`src/core/pipeline.py:226-233`
- 结果缓存：`src/core/pipeline.py:235-240`
- 知识集成：`src/core/pipeline.py:242-250`

---

## 3. 查询处理流程

### 3.1 QueryProcessor 工作流程

```
原始查询："喝隔夜水会致癌吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：检查缓存                    │
│  check_cache(query)                 │
│  位置：query_processor.py:70-88     │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       │               │
   缓存命中       缓存未命中
       │               │
       ▼               ▼
  返回缓存结果   ┌──────────────────────┐
                │ 步骤2：并行执行        │
                │ ┌────────────────┐   │
                │ │ LLM解析意图     │   │
                │ │ - 提取实体      │   │
                │ │ - 提取主张      │   │
                │ │ - 分类查询      │   │
                │ │ 位置：          │   │
                │ │ query_processor │   │
                │ │ .py:90-139     │   │
                │ └────────────────┘   │
                │           │          │
                │ ┌────────────────┐   │
                │ │ 本地向量检索    │   │
                │ │ (抢跑策略)      │   │
                │ │ - 原始词检索    │   │
                │ │ - 获取初步结果  │   │
                │ └────────────────┘   │
                └─────────┬────────────┘
                          │
                          ▼
              ┌──────────────────────────┐
              │ 步骤3：返回解析结果      │
              │ - QueryAnalysis 对象    │
              │ - 本地文档列表          │
              │ 位置：query_processor    │
              │ .py:141-176            │
              └──────────────────────────┘
```

**关键代码位置**：
- 类定义：`src/core/coordinators/query_processor.py:24-176`
- 缓存检查：`src/core/coordinators/query_processor.py:70-88`
- 查询解析：`src/core/coordinators/query_processor.py:48-68`
- 并行处理：`src/core/coordinators/query_processor.py:90-139`
- 流程编排：`src/core/coordinators/query_processor.py:141-176`

### 3.2 查询解析详细流程

```
查询："喝隔夜水会致癌吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  QueryParser.parse_query()          │
│  位置：analyzers/query_parser.py    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  LLM 链式调用                       │
│  1. 构建提示词                      │
│     "分析以下查询的实体、主张..."    │
│  2. 调用 LLM (qwen-plus)            │
│  3. 解析返回的 JSON                 │
│  位置：query_parser.py:39-64        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  返回 QueryAnalysis 对象            │
│  {                                 │
│    entity: "隔夜水",               │
│    claim: "会致癌",                 │
│    category: "健康养生"            │
│  }                                 │
└─────────────────────────────────────┘
```

---

## 4. 检索协调流程

### 4.1 RetrievalCoordinator 工作流程

```
输入：query + parsed_info + local_docs
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：检查是否需要补测            │
│  解析词与原始词不同？               │
│  位置：retrieval_coordinator.py:74  │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
    是（不同）      否（相同）
       │                │
       ▼                │
┌──────────────────┐    │
│ 补测本地检索      │    │
│ 用解析词再查一次  │    │
│ 位置：            │    │
│ retrieval_       │    │
│ coordinator.py:  │    │
│ 92-100           │    │
└─────────┬────────┘    │
          │             │
          └──────┬──────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  步骤2：文档去重                    │
│  _deduplicate_docs(local_docs)      │
│  位置：retrieval_coordinator.py:102 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤3：混合检索                    │
│  hybrid_retriever.search_hybrid()   │
│  - 本地检索（已有文档）              │
│  - 网络搜索（需要时）               │
│  位置：retrieval_coordinator.py:106 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤4：格式转换                    │
│  _convert_to_dict_format(documents) │
│  - LangChain Document → 字典       │
│  - 统一字段结构                    │
│  位置：retrieval_coordinator.py:110 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤5：验证证据                    │
│  validate_evidence(evidence_list)    │
│  - 检查必需字段                    │
│  - 过滤无效数据                    │
│  位置：retrieval_coordinator.py:114 │
└──────────────┬──────────────────────┘
               │
               ▼
         返回证据列表
```

**关键代码位置**：
- 类定义：`src/core/coordinators/retrieval_coordinator.py:15-257`
- 主检索方法：`src/core/coordinators/retrieval_coordinator.py:37-72`
- 解析词检索：`src/core/coordinators/retrieval_coordinator.py:74-117`
- 仅本地检索：`src/core/coordinators/retrieval_coordinator.py:119-148`
- 格式转换：`src/core/coordinators/retrieval_coordinator.py:178-215`
- 证据验证：`src/core/coordinators/retrieval_coordinator.py:217-236`

### 4.2 HybridRetriever 工作流程

```
输入：query + existing_local_docs + use_web_search
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：检查是否需要网络搜索        │
│  条件：                            │
│  - use_web_search = True           │
│  - 本地相似度 < 0.6                │
│  - 或本地证据不足                   │
│  位置：hybrid_retriever.py:56-76   │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
    不需要网络       需要网络
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────────┐
│ 直接返回本地  │  │ 步骤2：网络搜索   │
│ 证据         │  │ WebSearchTool    │
└──────────────┘  │ - 调用搜索API    │
                  │ - 获取网页内容   │
                  │ - 提取正文       │
                  │ 位置：           │
                  │ hybrid_retriever │
                  │ .py:78-151      │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ 步骤3：合并结果   │
                  │ - 本地证据       │
                  │ - 网络证据       │
                  │ - 去重排序       │
                  │ 位置：           │
                  │ hybrid_retriever │
                  │ .py:100-150     │
                  └────────┬─────────┘
                           │
                           ▼
                     返回合并证据列表
```

**关键代码位置**：
- 类定义：`src/retrievers/hybrid_retriever.py:15-201`
- 混合检索：`src/retrievers/hybrid_retriever.py:56-151`
- 本地检索：`src/retrievers/hybrid_retriever.py:18-54`

---

## 5. 证据分析流程

### 5.1 AnalysisCoordinator 工作流程

```
输入：claim + evidence_list
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：预过滤证据                  │
│  检查条件：                        │
│  - ENABLE_EVIDENCE_PREFILTER = True│
│  - 证据数量 > PREFILTER_MAX_EVIDENCE│
│  位置：analyzers/evidence_analyzer.py│
│      :89-110                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤2：确定并行策略                │
│  ┌────────────────────────────────┐│
│  │ 2-5 个证据：单证据并行分析     ││
│  │ - 每个 LLM 调用分析一条证据    ││
│  │ - ThreadPoolExecutor 并行     ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ >5 个证据：分片并行分析       ││
│  │ - 按批次分组                  ││
│  │ - 每批并行分析                ││
│  └────────────────────────────────┘│
│  位置：evidence_analyzer.py:30-86  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤3：LLM 批量分析               │
│  分析维度：                        │
│  - 相关性（与主张的关系）          │
│  - 权威性（来源可信度）            │
│  - 准确性（内容准确性）            │
│  - 立场（支持/反对/中立）          │
│  位置：evidence_analyzer.py:112-150│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤4：解析评估结果                │
│  - 提取 JSON 数据                  │
│  - 创建 EvidenceAssessment 对象   │
│  - 位置：evidence_analyzer.py:152- │
│          180                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤5：汇总分析                    │
│  summarize_assessments(assessments)  │
│  - 统计支持/反对/中立数量          │
│  - 计算平均置信度                  │
│  - 位置：analysis_coordinator.py:   │
│         64-102                     │
└──────────────┬──────────────────────┘
               │
               ▼
         返回评估列表
```

**关键代码位置**：
- 协调器：`src/core/coordinators/analysis_coordinator.py:15-129`
- 证据分析器：`src/analyzers/evidence_analyzer.py:28-311`
- 并行策略：`src/analyzers/evidence_analyzer.py:30-86`
- LLM 调用：`src/analyzers/evidence_analyzer.py:112-150`

---

## 6. 裁决生成流程

### 6.1 VerdictGenerator 工作流程

```
输入：query + entity + claim + evidence_list + assessments
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：判断裁决策略                │
│  ┌────────────────────────────────┐│
│  │ 有 assessments？               ││
│  │  YES → 正常裁决流程           ││
│  │  NO  → 兜底裁决流程           ││
│  └────────────────────────────────┘│
│  位置：verdict_generator.py:56-62  │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   正常流程        兜底流程
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────────┐
│ summarize_   │  │ summarize_with_   │
│ truth()      │  │ fallback()        │
│ - 综合证据   │  │ - 仅基于主张     │
│ - 评估真伪   │  │ - 使用常识规则   │
│ - 给出理由   │  │ - 标记低置信度   │
│ 位置：        │  │ 位置：           │
│ truth_       │  │ truth_           │
│ summarizer.  │  │ summarizer.      │
│ py:48-104    │  │ py:106-145       │
└──────┬───────┘  └────────┬─────────┘
       │                    │
       └────────┬───────────┘
                │
                ▼
┌─────────────────────────────────────┐
│  步骤2：生成 FinalVerdict 对象      │
│  {                                 │
│    verdict: "假" / "真" / "不确定",  │
│    confidence: 85,                  │
│    risk_level: "低" / "中" / "高",  │
│    summary: "详细说明..."           │
│  }                                 │
│  位置：verdict_generator.py:64-73   │
└──────────────┬──────────────────────┘
               │
               ▼
         返回 FinalVerdict
```

**关键代码位置**：
- 裁决生成器：`src/core/coordinators/verdict_generator.py:14-107`
- 真相总结器：`src/analyzers/truth_summarizer.py:25-257`
- 正常裁决：`src/analyzers/truth_summarizer.py:48-104`
- 兜底裁决：`src/analyzers/truth_summarizer.py:106-145`

---

## 7. 缓存系统流程

### 7.1 CacheManager 双层缓存架构

```
查询："维生素C可以预防感冒吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  第一层：精确匹配缓存               │
│  ┌────────────────────────────────┐│
│  │ 检查方式：MD5(query)            ││
│  │ 存储位置：storage/cache/        ││
│  │ 响应时间：<1ms                 ││
│  │ 命中率：~10%                   ││
│  │ 位置：cache_manager.py:91-120  ││
│  └────────────────────────────────┘│
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
    命中            未命中
       │                │
       ▼                ▼
  返回结果   ┌──────────────────────────┐
             │ 第二层：语义向量缓存      │
             │ ┌────────────────────────┐│
             │ │ 检查方式：向量相似度    ││
             │ │ 相似度阈值：≥0.96      ││
             │ │ 存储位置：storage/     ││
             │ │   semantic_cache/      ││
             │ │ 响应时间：<5ms         ││
             │ │ 命中率：~30%           ││
             │ │ 位置：cache_manager.py │
             │ │     :122-168          ││
             │ └────────────────────────┘│
             └──────────┬───────────────┘
                        │
                ┌───────┴────────┐
                │                │
             命中            未命中
                │                │
                ▼                ▼
           返回相似结果    执行完整流程
                              │
                              ▼
                      ┌──────────────────┐
                      │ 缓存新结果        │
                      │ set_verdict()     │
                      │ 位置：            │
                      │ cache_manager.py │
                      │ :170-193         │
                      └────────┬─────────┘
                               │
                               ▼
                        同时写入两层缓存
```

**关键代码位置**：
- 类定义：`src/core/cache_manager.py:23-317`
- 精确缓存：`src/core/cache_manager.py:91-120`
- 语义缓存：`src/core/cache_manager.py:122-168`
- 写入缓存：`src/core/cache_manager.py:170-193`
- 版本失效：`src/core/cache_manager.py:195-231`

### 7.2 缓存版本感知失效

```
知识库版本更新
    │
    ▼
┌─────────────────────────────────────┐
│  VersionManager 通知新版本          │
│  version = "20260208_2000"          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  CacheManager 检测版本变化          │
│  get_kb_version() != current_version│
│  位置：cache_manager.py:58-89       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  清理旧版本缓存                    │
│  clear_version_cache(old_version)   │
│  - 删除精确缓存                    │
│  - 删除语义缓存                    │
│  位置：cache_manager.py:233-274     │
└──────────────┬──────────────────────┘
               │
               ▼
         更新当前版本号
```

---

## 8. 知识库管理流程

### 8.1 EvidenceKnowledgeBase 构建流程

```
知识源文件 (data/rumors/*.txt)
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：读取所有文本文件            │
│  glob("data/rumors/*.txt")          │
│  位置：evidence_retriever.py:59-74  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤2：文本分块                    │
│  - 按标题分割                      │
│  - 每块 500-1000 字               │
│  - 保留元数据（来源、标题）        │
│  位置：evidence_retriever.py:76-88  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤3：批量 Embedding              │
│  BatchEmbedder.embed_chunks()       │
│  - 并行处理                        │
│  - 每批 10 个文本                  │
│  - 调用通义千问 Embedding API      │
│  位置：evidence_retriever.py:90-105│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤4：双缓冲构建                  │
│  ┌────────────────────────────────┐│
│  │ 1. 在临时目录构建新版本        ││
│  │    vector_db_staging/          ││
│  │ 位置：evidence_retriever.py:   ││
│  │       246-256                 ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ 2. 添加文档到 ChromaDB         ││
│  │    - 存储 embedding            ││
│  │    - 存储元数据               ││
│  │    位置：evidence_retriever.py:│
│  │         258-272               ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ 3. 原子性切换版本              ││
│  │    - 重命名：staging → v_YYYY ││
│  │    - 更新符号链接             ││
│  │    位置：evidence_retriever.py:│
│  │         274-296               ││
│  └────────────────────────────────┘│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤5：清理旧版本                  │
│  - 保留最近 3 个版本               │
│  - 删除其他版本                    │
│  位置：evidence_retriever.py:298-306│
└──────────────┬──────────────────────┘
               │
               ▼
         知识库构建完成
```

**关键代码位置**：
- 类定义：`src/retrievers/evidence_retriever.py:19-404`
- 构建入口：`src/retrievers/evidence_retriever.py:94-133`
- 双缓冲策略：`src/retrievers/evidence_retriever.py:246-296`
- 向量检索：`src/retrievers/evidence_retriever.py:141-234`

### 8.2 向量检索流程

```
查询："喝隔夜水会致癌吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：查询 Embedding              │
│  embeddings.embed_query(query)      │
│  - 调用通义千问 API                │
│  - 返回 1024 维向量                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤2：ChromaDB 相似度检索         │
│  collection.query(                  │
│    query_embeddings=[vector],       │
│    n_results=5,                     │
│    where={"type": "local"}          │
│  )                                 │
│  位置：evidence_retriever.py:161-176│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤3：过滤结果                    │
│  - 相似度 ≥ 0.25 (SIMILARITY_     │
│                 THRESHOLD)        │
│  - 位置：evidence_retriever.py:178- │
│            189                      │
└──────────────┬──────────────────────┘
               │
               ▼
         返回匹配文档列表
```

---

## 9. 知识集成流程

### 9.1 KnowledgeIntegrator 自动集成流程

```
裁决完成
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：检查集成条件                │
│  ┌────────────────────────────────┐│
│  │ 1. verdict in ["真", "假"]     ││
│  │    (结论必须明确)             ││
│  │                                ││
│  │ 2. confidence >= 90            ││
│  │    (置信度足够高)             ││
│  │                                ││
│  │ 3. evidence_count >= 3         ││
│  │    (有足够证据支持)           ││
│  └────────────────────────────────┘│
│  位置：knowledge_integrator.py:51-62│
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
   满足条件        不满足
       │                │
       ▼                │
┌──────────────────┐      │
│ 步骤2：生成知识   │      │
│ 文件内容          │      │
│ ┌────────────────┐│      │
│ │ # 标题         ││      │
│ │ claim         ││      │
│ │               ││      │
│ │ ## 裁决       ││      │
│ │ verdict +     ││      │
│ │ 理由          ││      │
│ │               ││      │
│ │ ## 证据       ││      │
│ │ 关键证据摘要  ││      │
│ └────────────────┘│      │
│ 位置：knowledge   │      │
│ _integrator.py:  │      │
│ 64-89            │      │
└────────┬─────────┘      │
         │                │
         ▼                │
┌──────────────────┐      │
│ 步骤3：保存知识   │      │
│ 文件              │      │
│ 文件名：AUTO_GEN_ │      │
│   {timestamp}_    │      │
│   {title}.txt     │      │
│ 位置：data/rumors/│      │
│ 位置：knowledge   │      │
│ _integrator.py:  │      │
│ 91-101           │      │
└────────┬─────────┘      │
         │                │
         ▼                │
┌──────────────────┐      │
│ 步骤4：后台重建    │      │
│ 向量库            │      │
│ rebuild_kb()      │      │
│ - 双缓冲策略      │      │
│ - 不阻塞查询      │      │
│ 位置：knowledge   │      │
│ _integrator.py:  │      │
│ 101-161          │      │
└────────┬─────────┘      │
         │                │
         └────────────────┘
               │
               ▼
         集成完成（后台）
```

**关键代码位置**：
- 类定义：`src/knowledge/knowledge_integrator.py:18-192`
- 条件检查：`src/knowledge/knowledge_integrator.py:51-62`
- 内容生成：`src/knowledge/knowledge_integrator.py:64-101`
- 后台重建：`src/knowledge/knowledge_integrator.py:101-161`

---

## 10. 可观测性模块流程

### 10.1 APIMonitor 工作流程

```
LLM 调用开始
    │
    ▼
┌─────────────────────────────────────┐
│  APIMonitorCallbackHandler          │
│  on_llm_start()                    │
│  - 记录开始时间                    │
│  位置：api_monitor_callback.py:44  │
└──────────────┬──────────────────────┘
               │
               ▼
         LLM 执行中...
               │
               ▼
┌─────────────────────────────────────┐
│  APIMonitorCallbackHandler          │
│  on_llm_end(response)              │
│  位置：api_monitor_callback.py:44- │
│            106                     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  提取 Token 使用量                  │
│  ┌────────────────────────────────┐│
│  │ input_tokens =                 ││
│  │   prompt_tokens ||             ││
│  │   input_tokens ||              ││
│  │   prompt_count                 ││
│  │                                ││
│  │ output_tokens =                ││
│  │   completion_tokens ||         ││
│  │   output_tokens ||             ││
│  │   completion_count             ││
│  └────────────────────────────────┘│
│  位置：api_monitor_callback.py:57- │
│            77                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  记录到 APIMonitor                  │
│  monitor.record_api_call(           │
│    provider='dashscope',            │
│    model='qwen-plus',              │
│    endpoint='chat',                │
│    input_tokens=100,               │
│    output_tokens=50                │
│  )                                 │
│  位置：api_monitor_callback.py:91- │
│            97                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  APIMonitor 更新统计                │
│  - 累计 token 使用量                │
│  - 计算成本                         │
│  - 检查预算告警                     │
│  位置：api_monitor.py:204-254       │
└──────────────┬──────────────────────┘
               │
               ▼
         监控数据已更新
```

**关键代码位置**：
- API 监控：`src/observability/api_monitor.py:33-574`
- 回调处理器：`src/observability/api_monitor_callback.py:16-123`
- Token 记录：`src/observability/api_monitor_callback.py:57-103`

### 10.2 MetricsCollector 工作流程

```
系统事件发生
    │
    ▼
┌─────────────────────────────────────┐
│  根据事件类型记录指标               │
│  ┌────────────────────────────────┐│
│  │ record_request(endpoint, status)││
│  │ - 记录请求计数                ││
│  │ - 更新 Prometheus Counter     ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ record_duration(stage, duration)││
│  │ - 记录阶段耗时                ││
│  │ - 更新 Prometheus Histogram   ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ record_cache_hit(cache_type)   ││
│  │ - 记录缓存命中                ││
│  └────────────────────────────────┘│
│  位置：metrics.py:94-142           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  同时更新内存统计                  │
│  _stats[key]["count"] += 1         │
│  _stats[key]["total_duration"] += d│
│  _stats[key]["last_update"] = now  │
│  位置：metrics.py:43-48, 99-142     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  可导出 Prometheus 格式             │
│  export_metrics() → bytes           │
│  - 调用 generate_latest(REGISTRY)  │
│  - 供 Prometheus 抓取              │
│  位置：metrics.py:168-172           │
└──────────────┬──────────────────────┘
               │
               ▼
         指标已记录
```

**关键代码位置**：
- 指标采集器：`src/observability/metrics.py:28-240`
- Prometheus 集成：`src/observability/metrics.py:50-92`
- 指标记录：`src/observability/metrics.py:94-142`
- 导出功能：`src/observability/metrics.py:168-172

### 10.3 结构化日志流程

```
日志记录调用
    │
    ▼
┌─────────────────────────────────────┐
│  get_logger(name)                   │
│  - 返回 structlog 或 logging logger │
│  位置：logger_config.py:80-95       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  绑定上下文                        │
│  log_with_context(logger,           │
│    trace_id="xxx",                  │
│    user_id="123")                   │
│  位置：logger_config.py:146-160     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  记录日志                          │
│  logger.info("处理完成",             │
│    duration=1.5,                    │
│    cache_hit=True)                  │
│                                   │
│  输出（JSON 格式）：                 │
│  {                                 │
│    "event": "处理完成",             │
│    "trace_id": "xxx",              │
│    "duration": 1.5,                │
│    "cache_hit": true,              │
│    "timestamp": "2026-02-08T..."   │
│  }                                 │
└──────────────┬──────────────────────┘
               │
               ▼
         日志已输出
```

**关键代码位置**：
- 日志配置：`src/observability/logger_config.py:28-77`
- 日志获取：`src/observability/logger_config.py:80-95`
- 上下文绑定：`src/observability/logger_config.py:146-160`
- Trace ID：`src/observability/logger_config.py:98-113`

---

## 11. 工具函数流程

### 11.1 LLMFactory 工作流程

```
请求创建 LLM
    │
    ▼
┌─────────────────────────────────────┐
│  get_llm(model_type)                │
│  位置：llm_factory.py:52-80         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  根据类型选择模型                  │
│  ┌────────────────────────────────┐│
│  │ MODEL_PARSER = "qwen-plus"     ││
│  │ → 用于查询解析                ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ MODEL_ANALYZER = "qwen-plus"   ││
│  │ → 用于证据分析                ││
│  └────────────────────────────────┘│
│  ┌────────────────────────────────┐│
│  │ MODEL_SUMMARIZER = "qwen-max"  ││
│  │ → 用于裁决生成（最强模型）   ││
│  └────────────────────────────────┘│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  创建 ChatTonghua 实例             │
│  ChatTonghua(                      │
│    model=model_type,               │
│    api_key=DASHSCOPE_API_KEY,      │
│    temperature=0.7                 │
│  )                                 │
└──────────────┬──────────────────────┘
               │
               ▼
         返回 LLM 实例
```

**关键代码位置**：
- LLM 工厂：`src/utils/llm_factory.py:17-80`
- 模型配置：`src/config.py:20-27`

### 11.2 BatchEmbedder 工作流程

```
文本列表：["文本1", "文本2", ..., "文本100"]
    │
    ▼
┌─────────────────────────────────────┐
│  embed_texts(texts)                 │
│  位置：batch_embedder.py:54-65      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  分批处理                          │
│  batch_size = 10                    │
│  总批次数 = ceil(100 / 10) = 10     │
│  位置：batch_embedder.py:78-92      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  每批并行处理                      │
│  ThreadPoolExecutor(               │
│    max_workers=并行度              │
│  )                                 │
│  位置：batch_embedder.py:113-180   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  调用通义千问 Embedding API        │
│  DashScopeEmbeddings()             │
│  - 每次最多 25 个文本              │
│  - 返回 1024 维向量                │
│  位置：batch_embedder.py:194-202   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  收集结果                          │
│  embeddings = [vec1, vec2, ...]    │
│  位置：batch_embedder.py:204-211   │
└──────────────┬──────────────────────┘
               │
               ▼
         返回向量列表
```

**关键代码位置**：
- 批量嵌入：`src/utils/batch_embedder.py:54-253`
- 并行处理：`src/utils/batch_embedder.py:113-180`
- API 调用：`src/utils/batch_embedder.py:194-202`

---

## 12. 基础设施流程

### 12.1 并行度配置流程

```
系统启动
    │
    ▼
┌─────────────────────────────────────┐
│  ParallelismConfig 初始化           │
│  位置：parallelism_config.py:23-41  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  检测 CPU 核心数                   │
│  cpu_count = os.cpu_count()         │
│  例如：16 核                        │
│  位置：parallelism_config.py:33-34  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  计算默认并行度                    │
│  default_parallelism =              │
│    min(cpu_count * 0.625, 20)       │
│  例如：min(16 * 0.625, 20) = 10     │
│  位置：parallelism_config.py:37-40  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  设置各模块并行度                  │
│  ┌────────────────────────────────┐│
│  │ evidence_analyzer:             ││
│  │   15 (IO 密集型)               ││
│  │ retrieval: 12 (IO 密集型)      ││
│  │ embedding: 8 (CPU 密集型)      ││
│  └────────────────────────────────┘│
│  位置：parallelism_config.py:60-74  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  运行时动态调整                    │
│  get_adaptive_workers(             │
│    task_count=20,                  │
│    task_type='evidence_analyzer'    │
│  ) → min(20, 15) = 15              │
│  位置：parallelism_config.py:95-115│
└──────────────┬──────────────────────┘
               │
               ▼
         返回最优并行度
```

**关键代码位置**：
- 并行度配置：`src/core/parallelism_config.py:17-176`
- 动态调整：`src/core/parallelism_config.py:95-152`

### 12.2 熔断器流程

```
API 调用
    │
    ▼
┌─────────────────────────────────────┐
│  CircuitBreaker 检查状态            │
│  位置：circuit_breaker.py:83-122   │
└──────────────┬──────────────────────┘
               │
      ┌────────┼────────┐
      │        │        │
   关闭     打开     半开
      │        │        │
      │        │        ▼
      │        │   ┌──────────────┐
      │        │   │ 尝试恢复     │
      │        │   │ 允许一次调用 │
      │        │   └──────────────┘
      │        │
      ▼        ▼
┌──────────────┐ ┌──────────────┐
│ 正常调用     │ │ 直接拒绝     │
│ 记录结果     │ │ 抛出异常     │
└──────┬───────┘ └──────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  更新状态                          │
│  - 成功：重置失败计数              │
│  - 失败：增加失败计数              │
│  - 失败率 > 50%：打开熔断器       │
│  位置：circuit_breaker.py:124-142 │
└──────────────┬──────────────────────┘
               │
               ▼
         返回调用结果
```

**关键代码位置**：
- 熔断器：`src/core/circuit_breaker.py:23-187`

### 12.3 重试策略流程

```
API 调用失败
    │
    ▼
┌─────────────────────────────────────┐
│  RetryPolicy 重试                   │
│  位置：retry_policy.py:19-90        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  检查重试条件                      │
│  - 是否可重试的异常？              │
│  - 未达到最大重试次数？            │
│  max_attempts = 3                  │
│  位置：retry_policy.py:45-58        │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
    可以重试        不可重试
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ 计算等待时间  │  │ 直接抛出异常 │
│ exponential  │  └──────────────┘
│ _backoff()   │
│ 位置：        │
│ retry_policy  │
│ .py:60-73    │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────┐
│  等待后重试                        │
│  wait(2^attempt seconds)            │
└──────────────┬──────────────────────┘
               │
               ▼
         重新调用 API
```

**关键代码位置**：
- 重试策略：`src/core/retry_policy.py:19-122`

---

## 13. 数据流向总览

### 13.1 完整查询处理数据流

```
用户输入
  "喝隔夜水会致癌吗？"
    │
    ├─→ [FastAPI/Gradio] 服务层
    │   位置：services/api_service.py
    │
    ├─→ [RumorJudgeEngine] 核心引擎
    │   位置：core/pipeline.py:186-294
    │
    ├─→ [QueryProcessor] 查询处理
    │   ├─→ CacheManager.get_verdict()
    │   │   位置：core/cache_manager.py:59-89
    │   │
    │   ├─→ QueryParser.parse_query()
    │   │   ↓ LLM (qwen-plus)
    │   │   位置：analyzers/query_parser.py:28-91
    │   │
    │   └─→ HybridRetriever.search_local() [并行]
    │       ↓ EvidenceKnowledgeBase
    │       位置：retrievers/hybrid_retriever.py:18-54
    │
    ├─→ [RetrievalCoordinator] 检索协调
    │   ├─→ HybridRetriever.search_hybrid()
    │   │   ├─→ 本地检索
    │   │   │   ↓ ChromaDB
    │   │   │   位置：retrievers/evidence_retriever.py:141-234
    │   │   │
    │   │   └─→ 网络检索 [需要时]
    │   │       ↓ WebSearchTool
    │   │       ↓ DuckDuckGo API
    │   │       位置：retrievers/web_search_tool.py:24-160
    │   │
    │   └─→ _deduplicate_docs()
    │       位置：coordinators/retrieval_coordinator.py:150-176
    │
    ├─→ [AnalysisCoordinator] 分析协调
    │   └─→ EvidenceAnalyzer.analyze_evidence()
    │       ├─→ 预过滤
    │       │   位置：analyzers/evidence_analyzer.py:89-110
    │       │
    │       ├─→ 并行策略选择
    │       │   位置：analyzers/evidence_analyzer.py:30-86
    │       │
    │       └─→ LLM 批量分析
    │           ↓ LLM (qwen-plus)
    │           位置：analyzers/evidence_analyzer.py:112-180
    │
    ├─→ [VerdictGenerator] 裁决生成
    │   └─→ TruthSummarizer.summarize_truth()
    │       ↓ LLM (qwen-max)
    │       位置：analyzers/truth_summarizer.py:48-104
    │
    ├─→ [CacheManager] 结果缓存
    │   ├─→ set_verdict() [精确匹配]
    │   │   位置：core/cache_manager.py:170-193
    │   │
    │   └─→ set_semantic_cache() [语义缓存]
    │       位置：core/cache_manager.py:195-231
    │
    ├─→ [KnowledgeIntegrator] 知识集成 [后台]
    │   ├─→ 检查条件
    │   │   位置：knowledge/knowledge_integrator.py:51-62
    │   │
    │   ├─→ 生成知识文件
    │   │   位置：knowledge/knowledge_integrator.py:64-101
    │   │
    │   └─→ rebuild_kb() [双缓冲]
    │       位置：retrievers/evidence_retriever.py:94-133
    │
    └─→ [APIMonitor] 监控记录
        └─→ record_api_call()
            位置：observability/api_monitor.py:204-254
                  ↓
        返回 UnifiedVerificationResult
        {
          verdict: "假",
          confidence: 85,
          risk_level: "低",
          summary_report: "...",
          retrieved_evidence: [...],
          is_cached: false,
          is_web_search: true
        }
```

---

## 14. 快速定位指南

### 14.1 按功能查找代码

| 功能 | 文件位置 | 关键方法/类 |
|------|----------|-------------|
| **入口** | | |
| 主引擎 | `src/core/pipeline.py` | `RumorJudgeEngine.run()` |
| API 服务 | `src/services/api_service.py` | `app.post("/verify")` |
| Web 界面 | `src/services/web_interface.py` | `create_interface()` |
| **查询处理** | | |
| 查询解析 | `src/analyzers/query_parser.py` | `QueryAnalysis` |
| 查询协调 | `src/core/coordinators/query_processor.py` | `QueryProcessor` |
| **检索** | | |
| 知识库 | `src/retrievers/evidence_retriever.py` | `EvidenceKnowledgeBase` |
| 混合检索 | `src/retrievers/hybrid_retriever.py` | `HybridRetriever` |
| 网络搜索 | `src/retrievers/web_search_tool.py` | `WebSearchTool` |
| 检索协调 | `src/core/coordinators/retrieval_coordinator.py` | `RetrievalCoordinator` |
| **分析** | | |
| 证据分析 | `src/analyzers/evidence_analyzer.py` | `analyze_evidence()` |
| 裁决生成 | `src/analyzers/truth_summarizer.py` | `summarize_truth()` |
| 分析协调 | `src/core/coordinators/analysis_coordinator.py` | `AnalysisCoordinator` |
| 裁决协调 | `src/core/coordinators/verdict_generator.py` | `VerdictGenerator` |
| **缓存** | | |
| 缓存管理 | `src/core/cache_manager.py` | `CacheManager` |
| **知识管理** | | |
| 知识集成 | `src/knowledge/knowledge_integrator.py` | `KnowledgeIntegrator` |
| 版本管理 | `src/core/version_manager.py` | `VersionManager` |
| **基础设施** | | |
| LLM 工厂 | `src/utils/llm_factory.py` | `get_llm()` |
| 批量嵌入 | `src/utils/batch_embedder.py` | `BatchEmbedder` |
| 并行度配置 | `src/core/parallelism_config.py` | `get_parallelism_config()` |
| 熔断器 | `src/core/circuit_breaker.py` | `CircuitBreaker` |
| 重试策略 | `src/core/retry_policy.py` | `RetryPolicy` |
| **可观测性** | | |
| API 监控 | `src/observability/api_monitor.py` | `APIMonitor` |
| 日志配置 | `src/observability/logger_config.py` | `configure_logging()` |
| 指标采集 | `src/observability/metrics.py` | `MetricsCollector` |

### 14.2 按模块查看调用链

**查询处理调用链**：
```
RumorJudgeEngine.run()
  → QueryProcessor.process()
    → QueryProcessor.check_cache()
      → CacheManager.get_verdict()
    → QueryProcessor.parse_with_parallel_retrieval()
      → QueryProcessor.parse_query()
        → QueryParser (LLM)
      → QueryProcessor.hybrid_retriever.search_local()
        → HybridRetriever.search_local()
          → EvidenceKnowledgeBase.search()
```

**检索调用链**：
```
RumorJudgeEngine.run()
  → RetrievalCoordinator.retrieve_with_parsed_query()
    → RetrievalCoordinator._deduplicate_docs()
    → HybridRetriever.search_hybrid()
      → HybridRetriever.search_local()
        → EvidenceKnowledgeBase.search()
      → HybridRetriever.web_search_tool.search() [需要时]
        → WebSearchTool.search()
          → DuckDuckGo API
    → RetrievalCoordinator._convert_to_dict_format()
    → RetrievalCoordinator.validate_evidence()
```

**分析调用链**：
```
RumorJudgeEngine.run()
  → AnalysisCoordinator.analyze()
    → EvidenceAnalyzer.analyze_evidence()
      → EvidenceAnalyzer._prefilter_evidence()
      → EvidenceAnalyzer._get_parallel_strategy()
      → EvidenceAnalyzer._analyze_single_evidence_batch() [并行]
        → LLM (qwen-plus)
    → AnalysisCoordinator.summarize_assessments()
```

**裁决调用链**：
```
RumorJudgeEngine.run()
  → VerdictGenerator.generate()
    → TruthSummarizer.summarize_truth() [有评估]
      → LLM (qwen-max)
    → TruthSummarizer.summarize_with_fallback() [无评估]
      → LLM (qwen-max)
```

---

## 15. 新手学习路径

### 15.1 推荐阅读顺序

**第 1 步：理解整体架构**（30 分钟）
1. 阅读本文档的 [整体系统架构](#1-整体系统架构)
2. 查看 `docs/ARCHITECTURE.md`
3. 运行 `python scripts/main.py` 体验系统

**第 2 步：理解核心流程**（1 小时）
1. 阅读 [核心引擎流程](#2-核心引擎流程)
2. 阅读代码：`src/core/pipeline.py:186-294`
3. 使用调试器跟踪一次完整查询

**第 3 步：深入各模块**（2 小时）
1. 查询处理：[查询处理流程](#3-查询处理流程)
2. 检索协调：[检索协调流程](#4-检索协调流程)
3. 证据分析：[证据分析流程](#5-证据分析流程)
4. 裁决生成：[裁决生成流程](#6-裁决生成流程)

**第 4 步：理解基础设施**（1 小时）
1. 缓存系统：[缓存系统流程](#7-缓存系统流程)
2. 知识库管理：[知识库管理流程](#8-知识库管理流程)
3. 可观测性：[可观测性模块流程](#10-可观测性模块流程)

**第 5 步：动手实践**（2 小时）
1. 修改提示词模板
2. 调整缓存阈值
3. 添加自定义知识文件
4. 查看监控数据

### 15.2 常见问题快速查找

| 问题 | 查看章节 |
|------|----------|
| 查询如何解析？ | [3.2 查询解析详细流程](#32-查询解析详细流程) |
| 证据从哪来？ | [4.2 HybridRetriever 工作流程](#42-hybridretriever-工作流程) |
| 如何判断真假？ | [6.1 VerdictGenerator 工作流程](#61-verdictgenerator-工作流程) |
| 缓存如何工作？ | [7.1 CacheManager 双层缓存架构](#71-cachemanager-双层缓存架构) |
| 知识库如何更新？ | [8.1 EvidenceKnowledgeBase 构建流程](#81-evidenceknowledgebase-构建流程) |
| API 成本如何监控？ | [10.1 APIMonitor 工作流程](#101-apimonitor-工作流程) |
| 如何并行处理？ | [12.1 并行度配置流程](#121-并行度配置流程) |
| 错误如何处理？ | [v0.8.2 统一错误处理](project_logs/optimization/2026-02-08.md) |

---

## 16. 附录：关键概念解释

### 16.1 核心概念

| 概念 | 说明 | 代码位置 |
|------|------|----------|
| **单例模式** | RumorJudgeEngine 全局唯一实例 | `pipeline.py:138-156` |
| **协调器模式** | 分离流程编排和业务逻辑 | `coordinators/` |
| **双缓冲策略** | 知识库原子性切换，不阻塞查询 | `version_manager.py` |
| **抢跑策略** | 并行执行解析和本地检索 | `query_processor.py:90-139` |
| **预过滤** | 在 LLM 分析前过滤低质量证据 | `evidence_analyzer.py:89-110` |
| **兜底机制** | 无证据时使用通用裁决逻辑 | `truth_summarizer.py:106-145` |

### 16.2 重要配置参数

| 参数 | 默认值 | 说明 | 配置位置 |
|------|--------|------|----------|
| `SIMILARITY_THRESHOLD` | 0.25 | 向量检索相似度阈值 | `config.py:33` |
| `SEMANTIC_CACHE_THRESHOLD` | 0.96 | 语义缓存相似度阈值 | `config.py:36` |
| `PREFILTER_MAX_EVIDENCE` | 5 | 预过滤最大证据数 | `config.py:39` |
| `AUTO_INTEGRATE_MIN_CONFIDENCE` | 90 | 自动集成最低置信度 | `config.py:42` |
| `AUTO_INTEGRATE_MIN_EVIDENCE` | 3 | 自动集成最少证据数 | `config.py:43` |

---

**文档维护**：本文档应与代码保持同步，每次重大修改后更新。

**最后更新**：2026-02-08
**文档版本**：v1.0
**项目版本**：v0.8.3
