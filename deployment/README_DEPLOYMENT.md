# 部署文件说明

## 文件清单

| 文件 | 说明 | 用途 |
|------|------|------|
| **deploy.sh** | 主部署脚本（已更新到 v2.0） | 一键部署、启动、停止、重启、查看状态 |
| **Dockerfile** | Docker 镜像构建文件 | 定义容器运行环境 |
| **docker-compose.yml** | 服务编排配置 | 定义 multi-container 应用 |
| **.env** | 环境变量配置 | 存储 API Key 等敏感信息 |
| **.env.example** | 环境变量模板 | 配置参考 |
| **QUICK_FIX.sh** | 快速修复脚本 | 解决容器冲突的独立脚本 |
| **SERVER_DEPLOYMENT_FIX.md** | 服务器部署完整文档 | 详细的问题分析和解决方案 |

## 快速开始

### 服务器部署遇到容器冲突？

```bash
# 方案 1：使用改进的 deploy.sh（推荐）
cd deployment
./deploy.sh deploy    # 自动清理并部署

# 方案 2：使用快速修复脚本
chmod +x QUICK_FIX.sh
./QUICK_FIX.sh
./deploy.sh deploy

# 方案 3：手动清理
docker stop rumor-api rumor-web
docker rm rumor-api rumor-web
./deploy.sh deploy
```

## deploy.sh v2.0 新功能

```bash
./deploy.sh deploy    # 完整部署（自动清理 + 健康检查）
./deploy.sh start     # 启动服务
./deploy.sh stop      # 停止服务
./deploy.sh restart   # 重启服务
./deploy.sh status    # 查看状态和日志
./deploy.sh logs      # 实时日志
./deploy.sh clean     # 深度清理
./deploy.sh help      # 帮助信息
```

## 环境配置

编辑 `.env` 文件：

```env
DASHSCOPE_API_KEY=sk-你的key
TAVILY_API_KEY=tvly-你的key
```

## 服务访问

部署成功后访问：

- **Web 界面**: http://your-server:7860
- **API 文档**: http://your-server:8000/docs
- **健康检查**: http://your-server:8000/health

## 常见问题

详见 [SERVER_DEPLOYMENT_FIX.md](SERVER_DEPLOYMENT_FIX.md)
