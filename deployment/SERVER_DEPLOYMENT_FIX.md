# 服务器部署问题解决方案

## 问题现象

在服务器上执行 `./deploy.sh` 时出现容器名称冲突：

```bash
ERROR: for rumor-api  Cannot create container for service rumor-api: Conflict.
The container name "/rumor-api" is already in use by container "40af98a50d536cc090579d94c17124043ef9b3159d1614c1b7d316784450637a".
You have to remove (or rename) that container to be able to reuse that name.
```

## 问题根本原因

### 1. 容器名冲突的来源

该错误表明名为 `rumor-api` 的容器已经存在，可能的原因：

- **之前手动创建了容器**：使用 `docker run` 而非 `docker-compose` 启动
- **之前的 docker-compose.yml 配置不同**：容器名定义发生了变化
- **容器异常停止**：`docker-compose down` 未正确执行
- **僵尸容器**：容器已停止但未删除

### 2. 为什么 `docker-compose down` 没有效果

原来的 deploy.sh 中只有 `docker-compose down`，这个命令**只能清理通过当前 docker-compose.yml 创建的容器**。如果容器是通过其他方式创建的（如之前的 docker run 或不同版本的 docker-compose.yml），则不会被清理。

## 解决方案

### 方案 1：使用改进的 deploy.sh（推荐）

已更新 `deployment/deploy.sh` 为 v2.0 版本，新增功能：

- ✅ **强制清理**：自动检测并删除所有名为 `rumor-api` 和 `rumor-web` 的容器
- ✅ **完整诊断**：显示 Docker 版本、容器状态、健康检查
- ✅ **多命令支持**：deploy、start、stop、restart、status、logs、clean
- ✅ **健康检查**：自动测试 API 和 Web 界面是否可访问

#### 使用方法：

```bash
# SSH 登录到服务器
cd deployment

# 方式 1：完整部署（自动清理旧容器）
./deploy.sh deploy

# 方式 2：如果仍有问题，先手动清理再部署
./deploy.sh clean    # 深度清理
./deploy.sh deploy   # 重新部署

# 方式 3：查看当前状态
./deploy.sh status   # 查看容器和日志
./deploy.sh logs     # 查看实时日志
```

### 方案 2：手动清理（备用方案）

如果自动脚本仍无法解决问题，可手动执行：

```bash
# 1. 查看所有 rumor 相关容器
docker ps -a | grep rumor

# 2. 强制停止并删除冲突的容器
docker stop rumor-api rumor-web 2>/dev/null || true
docker rm rumor-api rumor-web 2>/dev/null || true

# 3. 清理网络
docker network rm rumor-network 2>/dev/null || true

# 4. 重新部署
cd deployment
./deploy.sh deploy
```

### 方案 3：终极清理（彻底重置）

```bash
# 停止所有 rumor 容器
docker stop $(docker ps -a -q --filter "name=rumor-") 2>/dev/null || true

# 删除所有 rumor 容器
docker rm $(docker ps -a -q --filter "name=rumor-") 2>/dev/null || true

# 删除相关镜像
docker images | grep rumor | awk '{print $3}' | xargs docker rmi -f 2>/dev/null || true

# 清理悬空资源
docker system prune -f

# 重新部署
cd deployment && ./deploy.sh deploy
```

## 服务器部署完整流程

### 1. 准备工作

```bash
# SSH 登录服务器
ssh user@your-server-ip

# 进入项目目录
cd /path/to/internet_rumors_judge/deployment
```

### 2. 配置环境变量

```bash
# 检查 .env 文件是否存在
ls -la .env

# 如果不存在，从模板创建
cp .env.example .env  # 或直接编辑 .env

# 编辑 .env 文件，填入真实 API Key
nano .env
```

`.env` 文件内容示例：

```env
# 阿里云 DashScope API Key（必需）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Tavily 搜索 API Key（必需，用于联网核查）
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# HuggingFace 镜像（可选，用于加速模型下载）
HF_ENDPOINT=https://hf-mirror.com
```

### 3. 执行部署

```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行部署
./deploy.sh deploy
```

部署脚本会自动执行以下步骤：

1. ✅ 检查 Docker 环境
2. ✅ 检查 Docker Compose 版本
3. ✅ 检查 .env 文件配置
4. ✅ **强制清理旧的 rumor-api 和 rumor-web 容器**
5. ✅ 构建镜像并启动服务
6. ✅ 等待服务启动
7. ✅ 健康检查（测试 /health 接口）

### 4. 验证部署

```bash
# 查看容器状态
docker ps

# 查看服务状态
./deploy.sh status

# 测试 API 健康检查
curl http://localhost:8000/health

# 测试 Web 界面（需要浏览器访问）
curl http://localhost:7860
```

### 5. 配置防火墙（如果需要）

如果服务器启用了防火墙，需要开放端口：

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 8000/tcp
sudo ufw allow 7860/tcp

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=7860/tcp
sudo firewall-cmd --reload

# 验证端口开放
sudo netstat -tlnp | grep -E '8000|7860'
```

### 6. 配置反向代理（可选）

如果需要通过域名访问，推荐使用 Nginx 反向代理：

```nginx
# /etc/nginx/sites-available/rumor-judge

server {
    listen 80;
    server_name your-domain.com;

    # API 服务
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Web 界面
    location / {
        proxy_pass http://localhost:7860/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Gradio 需要 WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 常用运维命令

### 服务管理

```bash
# 启动服务（不清理）
./deploy.sh start

# 停止服务
./deploy.sh stop

# 重启服务
./deploy.sh restart

# 查看状态
./deploy.sh status

# 查看日志
./deploy.sh logs                # 所有服务日志
./deploy.sh logs rumor-api      # API 服务日志
./deploy.sh logs rumor-web      # Web 界面日志

# 深度清理（删除容器、镜像、卷）
./deploy.sh clean
```

### Docker 原生命令

```bash
# 查看所有容器
docker ps -a

# 查看容器资源使用
docker stats

# 查看容器详细信息
docker inspect rumor-api

# 进入容器调试
docker exec -it rumor-api bash

# 查看容器日志
docker logs rumor-api -f --tail 100

# 复制文件到容器
docker cp local_file.txt rumor-api:/app/path/

# 从容器复制文件
docker cp rumor-api:/app/file.txt ./
```

## 故障排查

### 问题 1：容器启动失败

```bash
# 查看容器日志
docker logs rumor-api

# 常见原因：
# - API Key 配置错误 → 检查 .env 文件
# - 端口被占用 → lsof -i:8000 检查占用
# - 依赖安装失败 → docker logs 查看具体错误
```

### 问题 2：健康检查失败

```bash
# 测试容器内部服务
docker exec rumor-api curl http://localhost:8000/health

# 如果内部正常但外部无法访问，检查：
# - 防火墙规则
# - docker-compose.yml 中的端口映射
```

### 问题 3：内存不足

```bash
# 查看容器资源限制
docker stats rumor-api

# 调整内存限制（在 docker-compose.yml 中添加）
services:
  rumor-api:
    mem_limit: 2g
    memswap_limit: 2g
```

### 问题 4：磁盘空间不足

```bash
# 清理 Docker 悬空资源
docker system prune -a --volumes

# 查看磁盘使用
docker system df
```

## 生产环境建议

1. **使用进程管理器**：推荐使用 systemd 管理 Docker 容器
2. **配置日志轮转**：避免日志文件无限增长
3. **设置资源限制**：在 docker-compose.yml 中配置 mem_limit、cpu_quota
4. **定期备份**：备份 storage/ 和 data/ 目录
5. **监控告警**：使用 Prometheus + Grafana 监控容器状态
6. **安全加固**：
   - 不要在 .env 中硬编码敏感信息
   - 使用 secrets 管理工具（如 Docker Secrets）
   - 定期更新基础镜像

## 改进的 deploy.sh 核心代码

关键改进点：

```bash
# 强制清理旧容器（无论是否由 docker-compose 创建）
force_cleanup() {
    for container in rumor-api rumor-web; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "删除容器: $container"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done

    # 使用 docker compose down 清理
    $DOCKER_COMPOSE_CMD down --remove-orphans 2>/dev/null || true
}

# 健康检查
check_services_status() {
    # 检查 rumor-api
    if docker ps --format '{{.Names}}' | grep -q "^rumor-api$"; then
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ rumor-api 运行正常"
        else
            echo "⚠️  rumor-api 容器已启动，但健康检查失败"
        fi
    fi
}
```

## 总结

部署失败的根源是**容器名称冲突**，而旧的 `docker-compose down` 无法处理非当前配置创建的容器。

**核心解决方案**：
1. 使用改进的 `deploy.sh`（v2.0）自动强制清理
2. 手动删除冲突容器：`docker rm -f rumor-api rumor-web`
3. 重新部署：`./deploy.sh deploy`

这样可以在服务器上顺利部署，避免容器冲突问题。
