# 缓存版本感知失效机制详解

> **深度解析**：本文档详细说明缓存如何感知知识库版本变化并自动失效

## 目录
1. [背景问题](#1-背景问题)
2. [核心设计思想](#2-核心设计思想)
3. [工作机制详解](#3-工作机制详解)
4. [完整流程图](#4-完整流程图)
5. [代码实现分析](#5-代码实现分析)
6. [边界情况处理](#6-边界情况处理)
7. [实际案例演示](#7-实际案例演示)

---

## 1. 背景问题

### 1.1 传统缓存的问题

**场景**：系统使用知识库来回答查询

```
用户查询："维生素C可以预防感冒吗？"
    ↓
检索知识库 → 获得答案
    ↓
缓存结果 → 下次直接返回
```

**问题**：当知识库更新时会发生什么？

```
时间线：
10:00 - 知识库版本 v1，查询"维生素C可以预防感冒吗？"
        → 答案："可以"（基于 v1 的旧知识）
        → 缓存了这个答案

11:00 - 系统学习到新知识，更新知识库到 v2
        → 新知识："维生素C不能预防感冒"

11:05 - 用户再次查询"维生素C可以预防感冒吗？"
        → 从缓存获取 → 返回旧答案"可以" ❌ 错误！
```

**根本原因**：
- 缓存不知道知识库已更新
- 旧缓存仍然有效，返回过时答案
- 用户可能获得错误信息

### 1.2 系统的特点

**互联网谣言粉碎机**具有**自我进化**能力：

1. **自动学习**：高置信度的裁决会自动转化为知识
2. **知识增长**：知识库会不断自动更新
3. **版本变化**：每次更新后知识库版本号会改变

**因此，缓存必须能够**：
- 感知知识库版本变化
- 自动失效旧版本缓存
- 确保用户获得最新知识

---

## 2. 核心设计思想

### 2.1 版本感知缓存

**核心思想**：每个缓存条目都绑定知识库版本号

```
缓存条目结构：
{
  "query": "维生素C可以预防感冒吗？",
  "verdict": "假",
  "confidence": 85,
  "kb_version": "20260208_1000",  ← 关键：绑定知识库版本
  "timestamp": "2026-02-08 10:00:00"
}
```

### 2.2 版本号格式

**知识库版本号**：`YYYYMMDD_HHMMSS`

```
示例：20260208_1000
      ↓     ↓
      日期  时间
（2026年2月8日 10:00:00）
```

**特点**：
- 时间戳格式，天然有序
- 唯一标识每次知识库构建
- 易于比较新旧

### 2.3 三种失效方式

| 方式 | 触发时机 | 清理范围 | 代码位置 |
|------|----------|----------|----------|
| **写入时检查** | 每次查询 | 单个条目 | `cache_manager.py:195-222` |
| **定期清理** | 系统空闲时 | 全部旧缓存 | `cache_manager.py:286-312` |
| **版本切换时** | 知识库更新 | 批量清理 | 自动触发 |

---

## 3. 工作机制详解

### 3.1 缓存写入（绑定版本）

**代码位置**：`src/core/cache_manager.py:224-274`

```python
def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
    """
    缓存裁决结果并存入语义索引

    新增：存储时附带知识库版本信息
    """
    # 1. 准备缓存数据
    data = verdict.model_dump()

    # 2. 绑定当前知识库版本 ← 关键步骤
    if self._current_kb_version:
        data["kb_version"] = self._current_kb_version.version_id
        logger.debug(f"缓存已绑定版本: {self._current_kb_version.version_id}")
    else:
        logger.debug("当前无知识库版本，缓存未绑定版本信息")

    # 3. 写入精确匹配缓存
    self.cache.set(key, data, expire=expire)

    # 4. 写入语义向量缓存（也绑定版本）
    metadata = {
        "cache_key": key,
        "timestamp": datetime.now().isoformat()
    }
    if self._current_kb_version:
        metadata["kb_version"] = self._current_kb_version.version_id

    self.vector_cache.add_texts(texts=[query], metadatas=[metadata])
```

**关键点**：
1. 每个缓存条目都记录当前知识库版本
2. 精确缓存和语义缓存都绑定版本
3. 版本信息存储在 `kb_version` 字段

### 3.2 缓存读取（验证版本）

**代码位置**：`src/core/cache_manager.py:195-222`

```python
def _is_cache_version_valid(self, cached_data: dict) -> bool:
    """
    检查缓存条目的版本是否有效

    返回：
        True: 缓存版本匹配，可以使用
        False: 缓存版本过期，需要重新查询
    """
    # 1. 获取当前知识库版本
    current_version = self._version_manager.get_current_version()
    current_version_id = current_version.version_id if current_version else None

    # 2. 检查缓存是否有版本信息
    if "kb_version" not in cached_data:
        # 情况A：缓存是旧格式（没有版本号）
        if current_version_id:
            # 当前有版本 → 说明知识库已构建过 → 缓存无效
            return False
        # 当前无版本 → 首次构建前 → 缓存有效
        return True

    # 3. 检查版本是否匹配
    cached_version = cached_data.get("kb_version")
    if cached_version != current_version_id:
        # 版本不匹配 → 缓存过期
        logger.debug(f"缓存版本不匹配: cached={cached_version}, current={current_version_id}")
        return False

    # 4. 版本匹配 → 缓存有效
    return True
```

**版本验证逻辑**：

| 缓存版本 | 当前版本 | 判断 | 原因 |
|---------|---------|------|------|
| null | null | ✅ 有效 | 首次构建前，无版本概念 |
| null | v1 | ❌ 无效 | 旧缓存，知识库已更新 |
| v1 | null | ⚠️ 有效 | 理论上不应出现，当作有效 |
| v1 | v1 | ✅ 有效 | 版本匹配 |
| v1 | v2 | ❌ 无效 | 版本不匹配，知识库已更新 |

### 3.3 缓存读取流程（完整版）

**代码位置**：`src/core/cache_manager.py:59-89`

```
用户查询："维生素C可以预防感冒吗？"
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：从精确缓存读取             │
│  cache.get(key) → cached_data        │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤2：验证缓存版本               │
│  _is_cache_version_valid(cached_data)│
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
    有效版本        无效版本
       │                │
       ▼                ▼
  ┌──────────┐    ┌──────────────────┐
  │返回缓存结果 │    │ 缓存标记为未命中 │
  └──────────┘    │ 继续执行查询流程  │
                  └────────┬─────────┘
                           │
                           ▼
                    执行完整查询
```

---

## 4. 完整流程图

### 4.1 缓存生命周期

```
【阶段1：缓存创建】
知识库版本 v1 存在
    │
    ▼
查询："维生素C可以预防感冒吗？"
    │
    ▼
执行完整流程 → 获得答案："假"
    │
    ▼
缓存结果（绑定版本 v1）
{
  "verdict": "假",
  "kb_version": "v1",  ← 绑定版本
  ...
}
    │
    ▼
存储到：
- storage/cache/ (精确缓存)
- storage/semantic_cache/ (语义缓存)

【阶段2：缓存使用】
用户再次查询（知识库仍为 v1）
    │
    ▼
读取缓存 → 版本检查：v1 == v1 ✅
    │
    ▼
直接返回缓存结果（快速响应）

【阶段3：知识库更新】
系统学习新知识 → 重建知识库
    │
    ▼
知识库版本 v1 → v2
    │
    ▼
VersionManager 更新 .version 文件
{
  "version_id": "v2",
  "timestamp": "20260208_1100",
  ...
}
    │
    ▼
【阶段4：缓存失效】
用户再次查询
    │
    ▼
读取缓存 → 版本检查：v1 ≠ v2 ❌
    │
    ▼
缓存失效！标记为未命中
    │
    ▼
执行完整查询（使用知识库 v2）
    │
    ▼
获得新答案："假，理由..."
    │
    ▼
缓存新结果（绑定版本 v2）
{
  "verdict": "假",
  "kb_version": "v2",  ← 新版本
  ...
}
```

### 4.2 版本切换时的清理流程

```
知识库重建完成
    │
    ▼
┌─────────────────────────────────────┐
│  步骤1：更新版本文件                │
│  VersionManager.create_version()    │
│  - 生成新版本号                     │
│  - 更新 .version 文件              │
│  位置：version_manager.py:131-160   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤2：通知 CacheManager           │
│  _update_kb_version()              │
│  - 读取新版本号                     │
│  - 更新 _current_kb_version        │
│  位置：cache_manager.py:58-89       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  步骤3：后续查询自动使用新版本     │
│  - 新缓存绑定新版本号              │
│  - 旧缓存读取时版本检查失败        │
│  - 旧缓存逐渐被新缓存替换          │
└─────────────────────────────────────┘
```

---

## 5. 代码实现分析

### 5.1 关键数据结构

**缓存条目**（精确匹配）：
```python
# storage/cache/ (diskcache 数据库)
key: MD5("维生素C可以预防感冒吗？")
value: {
  "verdict": "假",
  "confidence": 85,
  "summary": "...",
  "kb_version": "20260208_1000",  ← 版本绑定
  "timestamp": "2026-02-08 10:00:00",
  "expires": "2026-02-09 10:00:00"
}
```

**缓存条目**（语义向量）：
```python
# storage/semantic_cache/ (ChromaDB)
{
  "id": "uuid",
  "text": "维生素C可以预防感冒吗？",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "cache_key": "abc123...",
    "kb_version": "20260208_1000",  ← 版本绑定
    "timestamp": "2026-02-08 10:00:00"
  }
}
```

### 5.2 关键方法详解

#### 方法1：`_is_cache_version_valid()`

**作用**：验证缓存版本是否有效

**代码**：`cache_manager.py:195-222`

**逻辑流程**：
```python
def _is_cache_version_valid(self, cached_data: dict) -> bool:
    # 步骤1：获取当前版本
    current_version = self._version_manager.get_current_version()
    current_version_id = current_version.version_id if current_version else None

    # 步骤2：检查缓存是否有版本号
    if "kb_version" not in cached_data:
        # 旧格式缓存（无版本号）
        if current_version_id:
            return False  # 有新版本，旧缓存无效
        return True   # 首次构建前，认为有效

    # 步骤3：比较版本号
    cached_version = cached_data.get("kb_version")
    if cached_version != current_version_id:
        return False  # 版本不匹配

    return True  # 版本匹配
```

#### 方法2：`set_verdict()`

**作用**：缓存结果时绑定版本

**代码**：`cache_manager.py:224-274`

**关键步骤**：
```python
def set_verdict(self, query: str, verdict: FinalVerdict, ttl: Optional[int] = None):
    # 步骤1：准备数据
    data = verdict.model_dump()

    # 步骤2：绑定版本（核心）
    if self._current_kb_version:
        data["kb_version"] = self._current_kb_version.version_id

    # 步骤3：写入精确缓存
    self.cache.set(key, data, expire=expire)

    # 步骤4：写入语义缓存（也绑定版本）
    if self.vector_cache:
        metadata = {
            "cache_key": key,
            "timestamp": datetime.now().isoformat()
        }
        if self._current_kb_version:
            metadata["kb_version"] = self._current_kb_version.version_id

        self.vector_cache.add_texts(texts=[query], metadatas=[metadata])
```

#### 方法3：`clear_stale_cache()`

**作用**：定期清理过期缓存

**代码**：`cache_manager.py:286-312`

**工作流程**：
```python
def clear_stale_cache(self):
    stale_keys = []

    # 步骤1：遍历所有缓存
    for key in self.cache:
        data = self.cache.get(key)

        # 步骤2：检查版本
        if data and not self._is_cache_version_valid(data):
            stale_keys.append(key)

    # 步骤3：删除过期缓存
    for key in stale_keys:
        self.cache.delete(key)

    return len(stale_keys)
```

---

## 6. 边界情况处理

### 6.1 首次构建前（无版本）

**场景**：系统刚启动，知识库还未构建

**处理**：
```python
# 当前无版本
current_version_id = None

# 缓存也无版本
cached_version = None

# 判断：认为有效
# 原因：首次构建前，所有缓存都有效
return True
```

**位置**：`cache_manager.py:209-214`

### 6.2 首次构建后（版本出现）

**场景**：知识库首次构建完成，版本号从 null → v1

**处理**：
```python
# 旧缓存（无版本号）
cached_version = None

# 当前有新版本
current_version_id = "v1"

# 判断：旧缓存无效
# 原因：知识库已更新，旧缓存可能过时
return False
```

**位置**：`cache_manager.py:210-212`

### 6.3 语义缓存的版本检查

**问题**：语义缓存基于向量相似度，如何检查版本？

**解决**：在 metadata 中存储版本号

```python
# 写入时
metadata = {
    "kb_version": "v1"  ← 存储在 metadata
}
vector_cache.add_texts(texts=[query], metadatas=[metadata])

# 读取时
results = vector_cache.similarity_search(query, k=1)
for doc in results:
    metadata = doc.metadata
    cached_version = metadata.get("kb_version")
    if cached_version != current_version:
        # 跳过这个结果（版本不匹配）
        continue
```

**位置**：`cache_manager.py:122-168`, `261-268`

---

## 7. 实际案例演示

### 案例1：正常的缓存失效

```
【10:00】知识库版本 v1
├─ 查询："维生素C能美白吗？"
├─ 调用 LLM → 答案："有争议"
├─ 缓存结果（绑定版本 v1）
└─ 存储：{verdict: "有争议", kb_version: "v1"}

【10:05】用户再次查询
├─ 读取缓存
├─ 版本检查：cached="v1" == current="v1" ✅
└─ 直接返回："有争议"

【10:10】系统学习新知识，重建知识库
├─ 版本 v1 → v2
└─ .version 文件更新

【10:15】用户第三次查询
├─ 读取缓存
├─ 版本检查：cached="v1" != current="v2" ❌
├─ 缓存失效！
├─ 重新查询（使用知识库 v2）
├─ 获得新答案："有一定效果"
└─ 缓存新结果（绑定版本 v2）
```

### 案例2：边界情况处理

**场景A：首次构建前的缓存**

```
【09:55】知识库未构建（version=null）
├─ 查询："喝隔夜水会致癌吗？"
├─ 调用 LLM → 答案："假"
├─ 缓存结果（无版本号）
└─ 存储：{verdict: "假", 无 kb_version}

【10:00】知识库首次构建
├─ version: null → "v1"
└─ 更新 .version 文件

【10:05】用户再次查询
├─ 读取缓存
├─ 版本检查：
│   cached_version = None
│   current_version = "v1"
│   → 判断：无效 ❌
├─ 缓存失效
└─ 重新查询
```

**场景B：批量缓存清理**

```python
# 调用清理方法
stale_count = cache_manager.clear_stale_cache()

# 执行过程
遍历缓存中的所有条目（假设 100 个）
├─ 检查每个条目的版本
├─ 发现 30 个条目版本不匹配
├─ 删除这 30 个过期条目
└─ 返回：清理了 30 个过期缓存
```

---

## 8. 优势与设计亮点

### 8.1 核心优势

| 特性 | 传统缓存 | 版本感知缓存 |
|------|---------|-------------|
| 知识更新 | 需要手动清空缓存 | 自动失效旧缓存 |
| 数据一致性 | 可能返回过时答案 | 始终返回最新答案 |
| 用户体验 | 快速但可能错误 | 快速且准确 |
| 维护成本 | 需要手动管理 | 全自动管理 |

### 8.2 设计亮点

1. **零侵入**：业务代码无需关心版本
   - 缓存读写自动处理版本
   - 对业务层透明

2. **渐进式失效**：旧缓存逐渐被替换
   - 不需要全量清理
   - 按需失效，性能最优

3. **双重保障**：精确缓存 + 语义缓存
   - 两层都绑定版本
   - 确保一致性

4. **边界友好**：处理各种特殊情况
   - 首次构建前
   - 版本缺失
   - 格式兼容

---

## 9. 总结

### 核心机制

```
缓存 = 数据 + 版本号

读取时：
if 缓存.版本号 == 当前.版本号:
    return 缓存.数据  ✅
else:
    return 缓存失效  ❌
```

### 关键代码位置

| 功能 | 文件 | 方法/行号 |
|------|------|-----------|
| 版本验证 | `cache_manager.py` | `195-222` |
| 版本绑定 | `cache_manager.py` | `238-244` |
| 定期清理 | `cache_manager.py` | `286-312` |
| 版本管理 | `version_manager.py` | `68-81` |

### 效果

- ✅ 自动失效旧缓存
- ✅ 确保数据一致性
- ✅ 用户体验优秀（快速 + 准确）
- ✅ 零维护成本

---

**文档版本**：v1.0
**最后更新**：2026-02-08
**相关章节**：MODULE_WORKFLOWS.md 第 7 章
