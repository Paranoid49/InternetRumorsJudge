# 文档结构说明

## 目录组织

```
docs/
├── INDEX.md                      # 📑 文档总索引（入口）
├── STRUCTURE.md                  # 📁 本文件（文档结构说明）
│
├── 📚 核心文档
│   ├── ARCHITECTURE.md           # 系统架构设计
│   ├── MODULE_WORKFLOWS.md       # 模块工作流程图
│   ├── COORDINATORS.md           # 协调器模式详解
│   ├── API_REFERENCE.md          # API 接口文档
│   ├── CLAUDE.md                 # Claude Code 工作指南
│   ├── TESTING.md                # 测试文档
│   ├── DEPENDENCY_MANAGEMENT.md  # 依赖管理
│   └── CACHE_VERSIONING.md       # 缓存版本管理
│
├── 📋 历史文档
│   ├── REFACTORING_REPORT.md     # 项目重构报告（2026-02-04）
│   └── plans/                    # 历史计划文档
│       ├── 2026-02-05-production-readiness-roadmap.md
│       └── 2026-02-05-production-readiness-roadmap-v2.md
│
├── 🚀 部署
│   ├── DEPLOYMENT_CHECKLIST.md   # 部署检查清单
│   └── (DEPLOY_GUIDE.md 位于 deployment/ 目录)
│
└── 📖 学习文档（与 learn_doc/ 内容相同）
    ├── QUICK_START.md             # 快速开始
    ├── PROJECT_LEARNING_GUIDE.md  # 学习指南
    ├── ARCHITECTURE_DIAGRAMS.md   # 架构图解
    └── MODULE_RELATIONSHIPS.md    # 模块关系

deployment/
├── DEPLOY_GUIDE.md               # 完整部署指南
├── Dockerfile                    # Docker 镜像
├── docker-compose.yml            # Docker Compose 配置
├── deploy.sh                     # 部署脚本
└── cleanup_containers.sh         # 清理脚本

learn_doc/
├── README.md                     # 学习文档入口
├── QUICK_START.md                # 快速开始
├── PROJECT_LEARNING_GUIDE.md     # 学习指南
├── ARCHITECTURE_DIAGRAMS.md      # 架构图解
└── MODULE_RELATIONSHIPS.md       # 模块关系

project_logs/
└── optimization/                # 优化日志
    ├── 2026-02-08.md
    └── 2026-02-09.md

project-analysis/
├── 互联网谣言粉碎机_变更历史.md
├── 互联网谣言粉碎机_重难点专题.md
└── sources/                     # 原始数据
```

## 文档分类

### 按受众分类

**新手入门**
1. README.md（根目录）
2. learn_doc/QUICK_START.md
3. learn_doc/PROJECT_LEARNING_GUIDE.md

**开发者**
1. docs/ARCHITECTURE.md
2. docs/MODULE_WORKFLOWS.md
3. docs/API_REFERENCE.md
4. docs/TESTING.md
5. docs/CLAUDE.md

**运维/部署**
1. deployment/DEPLOY_GUIDE.md
2. docs/DEPLOYMENT_CHECKLIST.md

**项目经理/历史**
1. docs/REFACTORING_REPORT.md
2. project_logs/optimization/
3. project-analysis/

### 按更新频率分类

**经常更新**
- API_REFERENCE.md
- TESTING.md
- CLAUDE.md

**偶尔更新**
- ARCHITECTURE.md
- MODULE_WORKFLOWS.md
- DEPLOYMENT_CHECKLIST.md

**历史存档**
- REFACTORING_REPORT.md
- plans/
- project_logs/
- project-analysis/

## 文档规范

### 命名规范

- 使用大写蛇形命名：`API_REFERENCE.md`
- 日期格式：`YYYY-MM-DD`（如 `2026-02-08.md`）
- 文档后缀统一使用 `.md`

### 文档结构

每个文档应包含：
1. 标题和概述
2. 目录（可选，长文档需要）
3. 正文内容
4. 相关链接

### 更新日志

重要文档更新时，应在文档顶部添加更新记录：

```markdown
---
**文档版本**: v1.0
**最后更新**: 2026-02-11
**维护者**: xxx
---
```

## 清理记录

**2026-02-11 文档整理**

删除的文档（重复或过时）：
- docs/README.md（与根目录重复）
- docs/PROJECT_STRUCTURE_PROPOSAL.md（重构后过时）
- deployment/DEPLOYMENT_FIX.md（临时修复文档）
- deployment/SERVER_DEPLOYMENT_FIX.md（临时修复文档）
- deployment/README_DEPLOYMENT.md（与 DEPLOY_GUIDE 重复）
- docs/optimization_report_truth_summarizer.md（已整合到 project_logs）

新增的文档：
- docs/INDEX.md（文档索引）
- docs/STRUCTURE.md（本文档）
