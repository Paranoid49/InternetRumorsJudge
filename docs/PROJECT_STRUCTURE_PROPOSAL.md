# 项目结构重构方案

## 当前问题
- 根目录堆满 25+ 个 .py 文件
- 测试文件与业务代码混在一起
- 数据、缓存、向量库目录无统一规划
- 缺少按功能模块的分层组织

## 推荐结构

```
internet_rumors_judge/
│
├── src/                          # 源代码目录
│   ├── __init__.py
│   ├── config.py                 # 配置文件
│   │
│   ├── core/                     # 核心引擎
│   │   ├── __init__.py
│   │   ├── pipeline.py           # RumorJudgeEngine 主编排
│   │   └── cache_manager.py      # 缓存管理
│   │
│   ├── retrievers/               # 检索模块
│   │   ├── __init__.py
│   │   ├── evidence_retriever.py # 向量知识库
│   │   ├── hybrid_retriever.py   # 混合检索
│   │   └── web_search_tool.py    # 联网搜索
│   │
│   ├── analyzers/                # 分析模块
│   │   ├── __init__.py
│   │   ├── query_parser.py       # 查询意图解析
│   │   ├── evidence_analyzer.py  # 证据分析
│   │   └── truth_summarizer.py   # 真相总结
│   │
│   ├── knowledge/                # 知识管理
│   │   ├── __init__.py
│   │   └── knowledge_integrator.py
│   │
│   ├── services/                 # 服务接口
│   │   ├── __init__.py
│   │   ├── api_service.py        # FastAPI 服务
│   │   └── web_interface.py      # Gradio Web UI
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       └── ...
│
├── tests/                        # 测试代码
│   ├── __init__.py
│   ├── test_retrievers.py
│   ├── test_analyzers.py
│   ├── test_pipeline.py
│   └── benchmarks/
│       ├── run_benchmark.py
│       └── benchmark_dataset.json
│
├── scripts/                      # 脚本工具
│   ├── main.py                   # CLI 入口
│   ├── evaluation.py             # 评估脚本
│   ├── rumor_collector.py        # 谣言收集
│   └── prepare_data/
│       └── create_data.py
│
├── data/                         # 数据目录
│   ├── rumors/                   # 谣言知识库源文件
│   ├── reviewed/                 # 已审核数据
│   └── optimization/             # 优化相关数据
│
├── storage/                      # 存储目录（运行时生成）
│   ├── vector_db/                # 向量数据库
│   ├── cache/                    # 精确缓存
│   ├── semantic_cache/           # 语义缓存
│   └── reports/                  # 测试报告
│
├── docs/                         # 文档
│   ├── README.md
│   ├── CLAUDE.md
│   ├── OPTIMIZATION_REPORT.md
│   └── architecture.md
│
├── deployment/                   # 部署相关
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── deploy.sh
│
├── requirements.txt
├── .gitignore
├── .dockerignore
└── LICENSE
```

## 重构步骤

### 第一步：创建新目录结构
```bash
mkdir -p src/{core,retrievers,analyzers,knowledge,services,utils}
mkdir -p tests/benchmarks
mkdir -p scripts/prepare_data
mkdir -p storage/{vector_db,cache,semantic_cache,reports}
mkdir -p docs deployment
```

### 第二步：移动文件到新位置

**核心引擎 → src/core/**
```bash
mv pipeline.py src/core/
mv cache_manager.py src/core/
```

**检索模块 → src/retrievers/**
```bash
mv evidence_retriever.py src/retrievers/
mv hybrid_retriever.py src/retrievers/
mv web_search_tool.py src/retrievers/
```

**分析模块 → src/analyzers/**
```bash
mv query_parser.py src/analyzers/
mv evidence_analyzer.py src/analyzers/
mv truth_summarizer.py src/analyzers/
```

**知识管理 → src/knowledge/**
```bash
mv knowledge_integrator.py src/knowledge/
```

**服务接口 → src/services/**
```bash
mv api_service.py src/services/
mv web_interface.py src/services/
```

**配置 → src/**
```bash
mv config.py src/
```

**测试文件 → tests/**
```bash
mv test_*.py tests/
mv run_benchmark.py tests/benchmarks/
mv benchmark_dataset.json tests/benchmarks/
```

**脚本工具 → scripts/**
```bash
mv main.py scripts/
mv evaluation.py scripts/
mv rumor_collector.py scripts/
mv prepare_data/* scripts/prepare_data/
```

**数据整理**
```bash
mv data/rumors/* data/
mv reviewed_data/* data/reviewed/
mv optimization_data/* data/optimization/
```

**存储整理**
```bash
mv vector_db storage/
mv .cache storage/cache
mv vector_cache storage/semantic_cache
mv *.json storage/reports/ 2>/dev/null || true
```

**文档 → docs/**
```bash
mv README.md docs/
mv CLAUDE.md docs/
mv *.md docs/ 2>/dev/null || true
```

**部署相关 → deployment/**
```bash
mv Dockerfile deployment/
mv docker-compose.yml deployment/
mv deploy.sh deployment/
```

### 第三步：更新导入路径

创建 `src/__init__.py`:
```python
# 自动导入各模块，简化使用
from src.core.pipeline import RumorJudgeEngine
from src.config import config

__all__ = ['RumorJudgeEngine', 'config']
```

更新各模块的导入，例如在 `src/core/pipeline.py`:
```python
# 旧: from evidence_retriever import EvidenceKnowledgeBase
# 新: from src.retrievers.evidence_retriever import EvidenceKnowledgeBase
```

### 第四步：更新运行入口

**scripts/main.py**:
```python
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.pipeline import RumorJudgeEngine

if __name__ == "__main__":
    engine = RumorJudgeEngine()
    # ...
```

### 第五步：更新部署配置

**deployment/Dockerfile**:
```dockerfile
# 更新工作目录和 COPY 路径
WORKDIR /app
COPY src/ src/
COPY requirements.txt .
```

## 迁移清单

| 原路径 | 新路径 | 优先级 |
|--------|--------|--------|
| pipeline.py | src/core/pipeline.py | 高 |
| cache_manager.py | src/core/cache_manager.py | 高 |
| evidence_retriever.py | src/retrievers/evidence_retriever.py | 高 |
| hybrid_retriever.py | src/retrievers/hybrid_retriever.py | 高 |
| query_parser.py | src/analyzers/query_parser.py | 高 |
| evidence_analyzer.py | src/analyzers/evidence_analyzer.py | 高 |
| truth_summarizer.py | src/analyzers/truth_summarizer.py | 高 |
| web_search_tool.py | src/retrievers/web_search_tool.py | 高 |
| knowledge_integrator.py | src/knowledge/knowledge_integrator.py | 中 |
| api_service.py | src/services/api_service.py | 中 |
| web_interface.py | src/services/web_interface.py | 中 |
| config.py | src/config.py | 高 |
| test_*.py | tests/ | 中 |
| main.py | scripts/main.py | 中 |
| *.json 报告 | storage/reports/ | 低 |
| vector_db, .cache, vector_cache | storage/ | 低 |

## 优势

### 1. 清晰的职责分离
- `src/core/` - 核心编排逻辑
- `src/retrievers/` - 所有检索相关
- `src/analyzers/` - 所有分析相关
- `src/services/` - 对外服务接口

### 2. 便于测试
- `tests/` 目录独立
- 测试文件与源代码对应清晰

### 3. 数据与代码分离
- `storage/` 存放运行时生成的数据
- `data/` 存放源数据
- 便于 `.gitignore` 管理

### 4. 部署友好
- `deployment/` 集中管理部署文件
- `docs/` 集中管理文档

### 5. 可扩展性
- 新增功能时，有明确的目录归属
- 避免根目录文件爆炸

## 兼容性考虑

### 保留向后兼容（可选）
在项目根目录创建 `__init__.py`:
```python
# 向后兼容的导入 shim
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__)))

from src.core.pipeline import RumorJudgeEngine
# 导出旧 API
pipeline = sys.modules['pipeline']
pipeline.RumorJudgeEngine = RumorJudgeEngine
```

### 渐进式迁移
1. 先创建新目录结构
2. 逐步移动文件（优先级从高到低）
3. 更新导入路径
4. 最后清理旧的导入兼容层

## 注意事项

1. **不要提交到 Git 直到全部迁移完成**
2. **运行完整测试确保迁移无破坏**
3. **更新 README.md 中的所有路径引用**
4. **更新 CLAUDE.md 中的项目结构说明**
5. **更新 Docker 和部署脚本中的路径**
