# 部署问题解决方案

## 问题描述
执行 `./deploy.sh` 时出现容器名称冲突错误：
```
ERROR: for rumor-api  Cannot create container for service rumor-api: Conflict.
The container name "/rumor-api" is already in use
```

## 原因分析
这是由于之前的容器没有被正确清理，可能的原因：
1. 之前使用了 `docker run` 命令直接创建容器
2. 之前的 docker-compose 配置不同
3. 容器停止但未删除

## 解决步骤

### 步骤 1: 清理旧容器

#### Windows 用户：
```cmd
cd deployment
cleanup_containers.bat
```

#### Linux/Mac 用户：
```bash
cd deployment
chmod +x cleanup_containers.sh
./cleanup_containers.sh
```

### 步骤 2: 配置环境变量

编辑 `deployment/.env` 文件，填入真实的 API Key：

```env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxx
```

**获取 API Key：**
- **DASHSCOPE**: 访问 https://dashscope.aliyun.com/ 注册并获取
- **TAVILY**: 访问 https://tavily.com/ 注册并获取

### 步骤 3: 重新部署

#### Windows 用户：
```cmd
deploy.bat
```

#### Linux/Mac 用户：
```bash
chmod +x deploy.sh
./deploy.sh
```

## 手动清理命令（备用方案）

如果自动清理脚本无法运行，可以手动执行以下命令：

```bash
# 查看所有容器
docker ps -a

# 停止并删除冲突的容器
docker stop rumor-api rumor-web
docker rm rumor-api rumor-web

# 重新部署
cd deployment
./deploy.sh
```

## 验证部署成功

部署成功后，你应该能访问：
- **Web 界面**: http://localhost:7860
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 常见问题

### Q1: Docker Desktop 未运行
**错误**: `Cannot connect to the Docker daemon`
**解决**: 启动 Docker Desktop 应用程序

### Q2: 端口被占用
**错误**: `bind: address already in use`
**解决**:
- 修改 `docker-compose.yml` 中的端口映射
- 或停止占用 8000/7860 端口的其他程序

### Q3: API Key 无效
**错误**: `Authentication failed`
**解决**:
- 检查 .env 文件中的 API Key 是否正确
- 确认 API Key 已激活且有足够配额

## 查看日志

```bash
# 查看 API 服务日志
docker logs rumor-api -f

# 查看 Web 界面日志
docker logs rumor-web -f

# 查看所有服务状态
docker compose ps
```
