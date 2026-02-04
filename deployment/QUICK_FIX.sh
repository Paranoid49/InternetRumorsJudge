#!/bin/bash
# 服务器部署快速修复脚本
# 用于解决容器名称冲突问题

echo "======================================"
echo "容器冲突快速修复"
echo "======================================"

# 检查 Docker
if ! docker info &> /dev/null; then
    echo "❌ Docker 守护进程未运行"
    exit 1
fi

echo "📋 当前 rumor 相关容器："
docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "🛑 开始强制清理..."

# 强制删除容器（无论状态如何）
for container in rumor-api rumor-web; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "  删除 $container ..."
        docker stop "$container" 2>/dev/null || true
        docker rm "$container" 2>/dev/null || true
    else
        echo "  $container 不存在，跳过"
    fi
done

# 清理网络
docker network ls --filter "name=rumor-" --format "{{.Name}}" | while read net; do
    echo "  删除网络 $net ..."
    docker network rm "$net" 2>/dev/null || true
done

echo ""
echo "✅ 清理完成！"
echo ""
echo "下一步操作："
echo "  cd deployment"
echo "  ./deploy.sh deploy"
echo ""
