#!/bin/bash
# Docker 容器清理脚本 - 解决容器名称冲突问题

echo "======================================"
echo "Docker 容器清理脚本"
echo "======================================"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ 错误: Docker 守护进程未运行，请先启动 Docker Desktop"
    exit 1
fi

echo "📋 检查现有容器..."
docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"

# 停止并删除 rumor-api 容器
echo ""
echo "🛑 停止并删除 rumor-api 容器..."
if docker ps -a --format '{{.Names}}' | grep -q '^rumor-api$'; then
    docker stop rumor-api 2>/dev/null
    docker rm rumor-api
    echo "✅ rumor-api 已删除"
else
    echo "ℹ️  rumor-api 容器不存在"
fi

# 停止并删除 rumor-web 容器
echo ""
echo "🛑 停止并删除 rumor-web 容器..."
if docker ps -a --format '{{.Names}}' | grep -q '^rumor-web$'; then
    docker stop rumor-web 2>/dev/null
    docker rm rumor-web
    echo "✅ rumor-web 已删除"
else
    echo "ℹ️  rumor-web 容器不存在"
fi

# 清理悬空镜像（可选）
echo ""
echo "🧹 清理悬空镜像..."
docker image prune -f

# 显示清理后的容器状态
echo ""
echo "📋 清理完成，当前容器状态："
docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}" || echo "(无 rumor 相关容器)"

echo ""
echo "✅ 清理完成！现在可以运行 ./deploy.sh 进行部署"
