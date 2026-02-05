# Internet Rumors Judge - 生产级系统改造路线图（已审查版本）

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 将 Internet Rumors Judge (AI 谣言粉碎机) 从原型系统升级为真正专业、健壮且高效的生产级系统

**架构原则:**
- 性能优先：通过监控和优化降低延迟与成本
- 健壮为本：完善错误处理、降级策略和并发安全
- 可观测性：全面日志、指标和链路追踪
- 测试保障：单元测试、集成测试和压力测试全覆盖

**技术栈:** Python 3.11+, FastAPI, ChromaDB, LangChain, DashScope/通义千问, Pytest

**审查日期:** 2026-02-05
**审查人:** Claude (AI 技术守门员)

---

## 📋 当前系统健康度评估（已验证）

### ✅ 已实现的基础设施

#### 1. Docker 容器化 ✅
**状态:** 已完成
**位置:** `deployment/Dockerfile`, `deployment/docker-compose.yml`

**实现内容:**
- ✅ FastAPI 和 Gradio 双服务分离
- ✅ 环境变量配置（.env 传递敏感信息）
- ✅ 数据持久化（volumes 挂载 data 和 storage）
- ✅ 自定义网络隔离（rumor-network）
- ✅ 重启策略（restart: always）

**质量评估:** 良好，架构合理
**优先级:** 🟢 P3（可选优化：多阶段构建、healthcheck、资源限制）

---

#### 2. API 服务与健康检查 ✅
**状态:** 已完成（基础版本）
**位置:** `src/services/api_service.py`

**实现内容:**
- ✅ FastAPI 框架，支持 RESTful 接口
- ✅ `/verify` - 单条核查
- ✅ `/verify-stream` - 流式核查（NDJSON）
- ✅ `/batch-verify` - 批量并发核查
- ✅ `/health` - 基础健康检查
- ✅ CORS 中间件配置
- ✅ 线程池异步执行（max_workers=10）

**质量评估:** 功能完整，但缺少深度健康检查
**优先级:** 🟡 P2（增强健康检查：LLM/ChromaDB 连接性）

---

#### 3. 基础测试 ✅
**状态:** 部分完成
**位置:** `tests/`

**已实现:**
- ✅ API 集成测试（`test_api.py`）
- ✅ 去重算法测试（`test_deduplication_detailed.py`）
- ✅ 优化验证测试（`test_optimizations.py`）

**缺失:**
- ❌ 核心业务逻辑单元测试（evidence_analyzer, truth_summarizer）
- ❌ 端到端场景测试
- ❌ 并发压力测试

**优先级:** 🟡 P1（补充核心单元测试）

---

### 🔴 关键风险（未解决）

#### 1. 线程安全隐患 (Critical - P0)
**位置:** `src/core/pipeline.py:103`, `src/knowledge/knowledge_integrator.py:163-169`

**问题:**
- 知识集成时的 `build()` 操作与并发查询可能冲突
- ChromaDB 的持久化操作在写入时可能阻塞读取
- 单例的 `_lock` 用于延迟初始化，但知识库重构没有读锁保护

**影响:** 高并发下可能返回不一致的结果或查询失败

**证据:**
```python
# src/knowledge/knowledge_integrator.py:163-169
def rebuild_knowledge_base(self):
    print("🔄 Rebuilding Knowledge Base...")
    try:
        kb = EvidenceKnowledgeBase()
        kb.build()  # ⚠️ 阻塞式重构，可能与并发查询冲突
        print("✅ Knowledge Base rebuilt successfully!")
```

**优先级:** 🔴 P0 (立即修复)

---

#### 2. 缓存一致性问题 (High - P1)
**位置:** `src/core/cache_manager.py:94-131`

**问题:**
- 知识库更新后，旧缓存依然有效
- 没有缓存失效机制（版本号、TTL 触发等）
- 语义缓存与精确缓存可能不同步

**影响:** 用户可能获得过时的核查结果

**证据:**
```python
# src/core/cache_manager.py - 无版本检查
def get_verdict(self, query: str) -> Optional[FinalVerdict]:
    # 直接返回缓存，未验证知识库版本
    data = self.cache.get(key)
    if data:
        return self._to_verdict(data)
```

**优先级:** 🟡 P1 (本周内修复)

---

#### 3. API 成本不可控 (High - P1)
**位置:** `src/analyzers/evidence_analyzer.py:109-142`

**问题:**
- 证据分析对每个证据都调用 LLM，当证据 >10 时成本线性增长
- 并行分析（chunk_size=4）加剧成本压力
- 没有成本预算和告警机制

**影响:** 高流量下 API 费用可能失控

**当前缓解:** Top-3 证据限制（`config.py`）

**证据:**
```python
# src/analyzers/evidence_analyzer.py:109-142
def analyze(self, claim: str, evidence_list: List[Dict], chunk_size: int = 4):
    # 所有证据都会被 LLM 分析，无预过滤
    chunks = [evidence_list[i:i + chunk_size] for i in range(0, count, chunk_size)]
    # 并行调用 LLM，成本线性增长
```

**优先级:** 🟡 P1 (本周内优化)

---

#### 4. 缺少可观测性 (High - P1)
**问题:**
- 没有结构化日志（只有基础的 `logging.basicConfig`）
- 没有性能指标采集（各阶段耗时、缓存命中率、API 调用次数）
- 没有错误追踪和告警
- 健康检查仅返回固定字符串，无实际探测

**证据:**
```bash
# 检查结果：无 structlog 使用
$ grep -r "structlog" src/
# (无结果)

# 检查结果：无 metrics 模块
$ ls src/observability/
# (目录不存在)
```

**影响:** 无法及时发现和定位生产问题

**优先级:** 🟡 P1 (本周内实施)

---

#### 5. 缺少重试机制 (Medium - P2)
**问题:**
- 所有外部调用（LLM、网络搜索、ChromaDB）无统一重试策略
- 网络抖动会导致请求失败
- 依赖包中虽有 tenacity，但项目未使用

**证据:**
```bash
# 检查结果：未使用 tenacity
$ grep -r "from tenacity" src/
# (无结果)
```

**优先级:** 🟢 P2 (两周内完成)

---

#### 6. 缺少限流与熔断 (Medium - P2)
**问题:**
- API 服务无请求限流，易被恶意请求攻击
- 无熔断机制，下游服务（LLM）故障时会级联
- 并发数仅受线程池限制（max_workers=10）

**证据:**
```bash
# 检查结果：无限流组件
$ grep -r "rate_limit\|circuit_breaker\|slowapi" src/
# (无结果)
```

**优先级:** 🟢 P2 (两周内完成)

---

## 改进路线图（基于实际情况调整）

### 阶段 1: 关键风险修复 (Week 1) - P0/P1

#### 任务 1.1: 修复线程安全问题 ⚠️ **保留**
**目标:** 确保知识库重构不影响并发查询

**方案: 双缓冲策略（读写分离）**
- 创建新的向量库目录（`storage/vectordb_new`）
- 后台线程异步构建新库
- 构建完成后，原子性地切换指向新目录
- 旧库在下次构建时覆盖

**文件:**
- 修改: `src/retrievers/evidence_retriever.py:84-120`
- 修改: `src/knowledge/knowledge_integrator.py:163-171`
- 创建: `src/core/version_manager.py` (版本管理器)

**测试:**
- 创建: `tests/test_concurrent_kb_rebuild.py` (并发重构测试)

**预计时间:** 2.5-3 小时

---

#### 任务 1.2: 实现缓存失效机制 ⚠️ **保留**
**目标:** 知识库更新后自动失效相关缓存

**方案: 知识库版本号机制**
- 为向量库分配版本号（`data/knowledge/.version` 文件）
- 缓存存储时绑定版本号
- 缓存读取时检查版本一致性，过期即失效
- 语义缓存同步更新

**文件:**
- 修改: `src/core/cache_manager.py:60-92, 101-131`
- 修改: `src/retrievers/evidence_retriever.py:40-50` (构建时写入版本号)
- 创建: `src/core/version_manager.py` (版本读写)

**测试:**
- 创建: `tests/test_cache_invalidation.py`

**预计时间:** 1.5 小时

---

#### 任务 1.3: 结构化日志与指标采集 ⚠️ **保留**
**目标:** 完善可观测性，支持问题定位和性能分析

**方案:**
- 使用 `structlog` 替代基础 `logging`，输出 JSON 格式日志
- 添加链路追踪 ID (trace_id) 贯穿整个请求生命周期
- 采集关键指标：
  - 各阶段耗时（解析、检索、分析、裁决）
  - 缓存命中率（精确/语义）
  - API 调用次数和成本
  - 错误率和错误类型

**文件:**
- 创建: `src/observability/__init__.py`
- 创建: `src/observability/logger_config.py` (日志配置)
- 创建: `src/observability/metrics.py` (指标采集)
- 修改: `src/core/pipeline.py:288-475` (埋点)
- 修改: `src/analyzers/evidence_analyzer.py:144-171` (埋点)

**依赖:**
- 安装: `structlog`, `prometheus-client`

**测试:**
- 创建: `tests/test_observability.py`

**预计时间:** 3 小时

---

### 阶段 2: 成本与性能优化 (Week 2) - P1/P2

#### 任务 2.1: 证据预过滤与批量推理 ⚠️ **保留**
**目标:** 降低 API 成本，提升分析效率

**方案:**
1. **快速预过滤**：基于相关性规则（关键词、元数据）快速筛选，只对 Top-5 详细分析
2. **批量推理优化**：将单条 LLM 调用改为批量调用（如果模型支持）
3. **成本预算控制**：配置单请求最大 token 预算，超限自动降级

**文件:**
- 修改: `src/analyzers/evidence_analyzer.py:109-142`
- 修改: `config.py` (添加成本相关配置)

**测试:**
- 修改: `tests/test_optimizations.py` (扩展)

**预计时间:** 2-3 小时

---

#### 任务 2.2: 请求限流与熔断 ⚠️ **保留**
**目标:** 防止突发流量导致成本失控

**方案:**
- 使用 `slowapi` 实现请求限流（IP 维度）
- 实现熔断机制：API 失败率超阈值时暂停新请求
- 成本告警：实时监控 API 成本，超预算时告警

**文件:**
- 修改: `src/services/api_service.py`
- 创建: `src/core/rate_limiter.py` (限流器)
- 创建: `src/core/circuit_breaker.py` (熔断器)

**依赖:**
- 安装: `slowapi`, `redis` (可选，用于分布式限流)

**测试:**
- 创建: `tests/test_rate_limiting.py`

**预计时间:** 2-3 小时

---

### 阶段 3: 测试体系建设 (Week 3) - P1/P2

#### 任务 3.1: 核心业务逻辑单元测试 ⚠️ **保留（高优先级）**
**目标:** 覆盖率 > 80%

**测试范围:**
- 证据分析逻辑（`evidence_analyzer.py`）
- 裁决生成逻辑（`truth_summarizer.py`）
- 缓存管理器（`cache_manager.py`）
- 混合检索器（`hybrid_retriever.py`）

**文件:**
- 创建: `tests/unit/analyzers/test_evidence_analyzer.py`
- 创建: `tests/unit/analyzers/test_truth_summarizer.py`
- 创建: `tests/unit/core/test_cache_manager.py`
- 创建: `tests/unit/retrievers/test_hybrid_retriever.py`

**预计时间:** 4-5 小时

---

#### 任务 3.2: 端到端集成测试 ⚠️ **保留（中优先级）**
**目标:** 覆盖主要用户场景

**场景:**
1. 缓存命中场景（精确/语义）
2. 本地 RAG 场景
3. 网络搜索场景
4. 兜底分析场景
5. 自动知识集成场景

**文件:**
- 创建: `tests/integration/test_e2e_scenarios.py`

**预计时间:** 2 小时

---

#### 任务 3.3: 并发与压力测试 ⚠️ **保留（中优先级）**
**目标:** 验证系统在高并发下的稳定性

**场景:**
- 100 并发请求，查询相同内容（缓存命中率）
- 50 并发请求，查询不同内容（LLM 调用压力）
- 并发查询 + 知识库重构同时进行

**文件:**
- 修改: `tests/benchmarks/run_benchmark.py` (扩展)
- 创建: `tests/stress/test_concurrent_load.py`

**预计时间:** 2-3 小时

---

### 阶段 4: 健壮性增强 (Week 4) - P2

#### 任务 4.1: 完善错误处理与重试机制 ⚠️ **保留**
**目标:** 提升系统容错能力

**方案:**
- 为所有外部调用（LLM、网络搜索、ChromaDB）添加重试机制
- 使用 `tenacity` 库实现指数退避重试
- 明确区分可重试错误（网络超时）和不可重试错误（API Key 无效）

**文件:**
- 修改: `src/analyzers/evidence_analyzer.py:158-171` (添加重试)
- 修改: `src/retrievers/web_search_tool.py` (添加重试)
- 创建: `src/core/retry_policy.py` (统一重试策略)

**依赖:**
- 安装: `tenacity` (已在依赖包中)

**测试:**
- 创建: `tests/test_retry_mechanism.py`

**预计时间:** 2 小时

---

#### 任务 4.2: 降级策略增强 ⚠️ **降级为 P3**
**目标:** LLM 失败时仍能提供基本服务

**现状:** 已有基础兜底机制（`summarize_with_fallback`）

**改进空间:**
- 完善规则引擎
- 添加缓存兜底（返回历史相似查询结果）

**优先级调整原因:** 当前兜底机制已足够应对大部分场景，可延后

**文件:**
- 修改: `src/analyzers/truth_summarizer.py` (扩展降级逻辑)
- 创建: `src/analyzers/rule_based_verdict.py` (规则引擎) - **可选**

**预计时间:** 2-3 小时（如执行）

---

### 阶段 5: 部署与运维 (Week 5) - P2/P3

#### 任务 5.1: Docker 容器化 ✅ **已完成 - 删除**
**状态:** 已完成
**质量评估:** 良好

**可选优化（P3）：**
- [ ] 添加多阶段构建（减小镜像体积）
- [ ] 添加 healthcheck 指令（容器编排）
- [ ] 添加资源限制（防止 OOM）

**建议:** 暂不优化，除非遇到具体问题

---

#### 任务 5.2: 健康检查增强 ⚠️ **保留（降级为 P2）**
**目标:** 更全面的服务状态监控

**方案:**
- 扩展 `/health` 端点，检查：
  - LLM 连接性（简单测试调用）
  - ChromaDB 连接性（查询测试）
  - 向量库状态（是否存在、文档数量）
  - 缓存状态（命中率统计）
- 添加 `/metrics` 端点（Prometheus 格式）

**文件:**
- 修改: `src/services/api_service.py:132-139`

**预计时间:** 1 小时

---

#### 任务 5.3: 文档完善 ⚠️ **保留（降级为 P3）**
**状态:** 已有基础文档（`docs/README.md`, `docs/CLAUDE.md`）

**缺失文档:**
- 部署指南（Docker 启动、环境变量配置）
- 监控指南（日志查看、指标解读）
- 故障排查（常见问题）

**优先级调整原因:** 文档可迭代完善，非阻塞性

**文件:**
- 创建: `docs/DEPLOYMENT.md` (部署指南)
- 创建: `docs/MONITORING.md` (监控指南)
- 创建: `docs/TROUBLESHOOTING.md` (故障排查)
- 更新: 项目根目录 `README.md` (添加架构图)

**预计时间:** 2-3 小时（如执行）

---

## 实施原则

### 技术益害评估清单

在每个任务实施前，必须评估：

**✅ 益处检查**
- [ ] 是否提升了系统性能？（延迟降低、吞吐量提升）
- [ ] 是否增强了结论准确度？（误判率降低）
- [ ] 是否优化了用户体验？（错误提示更友好、响应更稳定）
- [ ] 是否提高了代码可维护性？（模块解耦、测试覆盖）

**⚠️ 风险评估**
- [ ] 是否会破坏现有的单例模式？（双缓冲策略需谨慎）
- [ ] 是否会引入线程安全隐患？（锁粒度、死锁风险）
- [ ] 是否会显著增加 API 调用成本？（新增 LLM 调用需评估）
- [ ] 是否会让架构变得过于臃肿？（避免过度工程）

### 开发规范

1. **TDD 驱动**：先写测试，再实现功能
2. **小步提交**：每个子任务完成后立即 commit
3. **代码审查**：P0/P1 任务必须经过代码审查
4. **性能回归**：优化前后运行基准测试对比
5. **文档同步**：代码变更后及时更新文档

---

## 成功指标

### 性能指标
- **缓存命中率**: > 80%（当前未知，需采集）
- **平均响应时间**: < 5s（缓存命中），< 30s（完整流程）
- **P95 响应时间**: < 10s（缓存命中），< 60s（完整流程）
- **并发能力**: 支持 50 QPS

### 成本指标
- **单查询平均 API 成本**: 降低 30%（通过预过滤）
- **月度 API 成本**: 可预测且在预算内

### 质量指标
- **测试覆盖率**: > 80%（当前 < 20%）
- **P0/P1 级 Bug 数**: 0
- **系统可用性**: > 99.5%

---

## 时间估算（AI 执行）

### 📊 纯工作时间

| 场景 | 原估算 | **修正后** | 节省时间 | 说明 |
|-----|--------|-----------|---------|------|
| 理想情况 | 15-20 小时 | **13-17 小时** | -2-3 小时 | 删除 Docker + 降级部分任务 |
| 现实情况 | 25-35 小时 | **22-30 小时** | -3-5 小时 | 包含调试迭代 |
| 保守估计 | 40-50 小时 | **35-45 小时** | -5 小时 | 包含架构调整 |

### 📅 分阶段耗时

| 阶段 | 任务数 | 预计耗时 | 累计耗时 |
|------|-------|---------|---------|
| **阶段 1** | 3 个任务 | 6-8 小时 | 6-8 小时 |
| **阶段 2** | 2 个任务 | 4-6 小时 | 10-14 小时 |
| **阶段 3** | 3 个任务 | 8-10 小时 | 18-24 小时 |
| **阶段 4** | 1-2 个任务 | 2-5 小时 | 20-29 小时 |
| **阶段 5** | 2 个任务 | 3-4 小时 | **23-33 小时** |

### ⚡ 执行模式建议

#### **模式 A: 3天冲刺（MVP 核心）**
- Day 1: 阶段 1 全部（线程安全 + 缓存失效 + 基础日志）
- Day 2: 阶段 2.1（证据预过滤）
- Day 3: 阶段 3.1 + 5.2（核心测试 + 健康检查）

**完成后你会得到：**
- ✅ 线程安全的稳定系统
- ✅ API 成本降低 30%+
- ✅ 基础测试覆盖
- ✅ 可观测性基础

**跳过：** 阶段 2.2、3.2、3.3、4、5.3（第二迭代再做）

---

#### **模式 B: 1周渐进（推荐）**
- Day 1-2: 阶段 1（关键风险）
- Day 3-4: 阶段 2 + 阶段 3.1（成本优化 + 核心测试）
- Day 5: 阶段 5.2 + 文档更新（部署完善）

**完成后你会得到：**
- ✅ 所有 P0/P1 风险修复
- ✅ 成本和性能优化
- ✅ 核心测试覆盖
- ✅ 可部署到生产环境

**跳过：** 阶段 3.2、3.3、4（低优先级）

---

#### **模式 C: 2-3周完整执行（生产级）**
- Week 1: 阶段 1 + 阶段 2
- Week 2: 阶段 3（全面测试）
- Week 3: 阶段 4 + 阶段 5（健壮性 + 文档）

**完成后你会得到：**
- ✅ 生产级系统
- ✅ 80%+ 测试覆盖
- ✅ 完善可观测性
- ✅ 面向未来的扩展性

---

## 附录: 文件结构规划（已调整）

```
internet_rumors_judge/
├── src/
│   ├── core/
│   │   ├── pipeline.py              # [修改] 添加埋点
│   │   ├── cache_manager.py         # [修改] 版本感知
│   │   ├── version_manager.py       # [新增] 版本管理
│   │   ├── rate_limiter.py          # [新增] 限流器 (P2)
│   │   └── circuit_breaker.py       # [新增] 熔断器 (P2)
│   ├── retrievers/
│   │   ├── evidence_retriever.py    # [修改] 双缓冲支持
│   │   └── hybrid_retriever.py      # [修改] 添加埋点
│   ├── analyzers/
│   │   ├── evidence_analyzer.py     # [修改] 预过滤 + 重试
│   │   ├── truth_summarizer.py      # [修改] 降级增强 (P3)
│   │   └── rule_based_verdict.py    # [新增] 规则引擎 (P3 可选)
│   ├── observability/               # [新增] 可观测性模块
│   │   ├── __init__.py
│   │   ├── logger_config.py
│   │   └── metrics.py
│   └── services/
│       └── api_service.py           # [修改] 限流 + 健康检查
├── tests/
│   ├── unit/                        # [新增] 单元测试
│   │   ├── analyzers/
│   │   ├── core/
│   │   └── retrievers/
│   ├── integration/                 # [新增] 集成测试
│   │   └── test_e2e_scenarios.py
│   ├── stress/                      # [新增] 压力测试
│   │   └── test_concurrent_load.py
│   ├── test_api.py                  # [已有] ✓
│   ├── test_optimizations.py        # [已有] ✓
│   └── benchmarks/
│       └── run_benchmark.py         # [修改] 扩展
├── docs/
│   ├── DEPLOYMENT.md                # [新增] P3
│   ├── MONITORING.md                # [新增] P3
│   ├── TROUBLESHOOTING.md           # [新增] P3
│   ├── README.md                    # [已有] ✓
│   ├── CLAUDE.md                    # [已有] ✓
│   └── plans/
│       └── 2026-02-05-production-readiness-roadmap-v2.md
├── deployment/
│   ├── Dockerfile                   # [已有] ✓
│   └── docker-compose.yml           # [已有] ✓
└── requirements.txt                 # [修改] 添加新依赖
```

---

## 下一步行动

**请选择执行模式:**

**A) 3天冲刺模式 (MVP)** 🚀
- 集中精力完成 P0/P1 风险修复
- 最快见效，立即提升稳定性

**B) 1周渐进模式 (推荐)** 📊
- 稳扎稳打，覆盖主要风险
- 可部署到生产环境

**C) 2-3周完整模式 (生产级)** 🌱
- 全面执行，质量最高
- 面向未来的扩展性

**D) 定制模式** ⚙️
- 告诉我你的时间预算和优先级
- 我针对性调整计划

---

## 审查总结

### ✅ 已发现并移除的重复工作
1. Docker 容器化（已完成，质量良好）
2. 基础 API 测试（已存在）
3. 基础健康检查（已实现）

### ⚠️ 确认的关键风险
1. **P0** 线程安全（知识库重构并发冲突）
2. **P1** 缓存一致性（知识库更新后缓存未失效）
3. **P1** API 成本（证据分析无预过滤）
4. **P1** 可观测性（无结构化日志和指标）
5. **P2** 重试机制（外部调用无统一策略）
6. **P2** 限流熔断（无流量保护）

### 📊 调整后的工作量
- **原计划**: 25-35 小时
- **修正后**: 22-30 小时
- **节省**: 约 15% （移除已实现的任务）

---

**感谢你的耐心审查！这份计划现在基于实际代码状态，更加务实和高效。**

**你希望采用哪种执行模式？** 🎯
