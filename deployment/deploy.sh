#!/bin/bash

# =================================================================
# Internet Rumors Judge - 服务器部署脚本 v2.0
# 适用于生产环境部署，支持强制清理和完整诊断
# =================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 辅助函数
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_step() {
    echo -e "${GREEN}[步骤] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[警告] $1${NC}"
}

print_error() {
    echo -e "${RED}[错误] $1${NC}"
}

# 显示使用帮助
show_help() {
    cat << EOF
用法: $0 [选项]

选项:
    deploy      完整部署（默认，清理旧容器并重新部署）
    start       启动服务（不清理）
    stop        停止服务
    restart     重启服务
    clean       清理所有容器、镜像和卷
    status      查看服务状态
    logs        查看服务日志
    help        显示此帮助信息

示例:
    $0 deploy   # 完整部署
    $0 status   # 查看状态
    $0 logs     # 查看日志
EOF
}

# 检查 Docker 环境
check_docker() {
    print_step "检查 Docker 环境..."

    if ! command -v docker &> /dev/null; then
        print_error "未检测到 Docker，请先安装 Docker"
        exit 1
    fi

    # 检查 Docker 守护进程是否运行
    if ! docker info &> /dev/null; then
        print_error "Docker 守护进程未运行，请启动 Docker 服务"
        exit 1
    fi

    echo -e "${GREEN}✅ Docker 环境正常${NC}"
}

# 自动检测并设置 Docker Compose 命令
setup_compose_cmd() {
    DOCKER_COMPOSE_CMD=""

    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
        echo -e "${GREEN}✅ 使用 Docker Compose V2${NC}"
    elif docker-compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
        echo -e "${YELLOW}⚠️  使用旧版 docker-compose (V1)${NC}"
    else
        print_error "未检测到 Docker Compose"
        exit 1
    fi
}

# 检查 .env 文件
check_env_file() {
    if [ ! -f .env ]; then
        print_warning "未发现 .env 文件，从模板创建..."
        cat > .env << 'ENVEOF'
DASHSCOPE_API_KEY=your_dashscope_key_here
TAVILY_API_KEY=your_tavily_key_here
ENVEOF
        print_error "请编辑 .env 文件并填入真实的 API Key 后重新运行"
        exit 1
    fi

    # 检查是否包含占位符
    if grep -q "your_.*_here" .env; then
        print_warning "检测到 .env 文件中存在占位符"
        print_warning "请确认 API Key 已正确配置"
        read -p "是否继续部署？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    echo -e "${GREEN}✅ .env 文件检查通过${NC}"
}

# 强制清理旧容器和镜像
force_cleanup() {
    print_step "强制清理旧容器和资源..."

    echo "当前所有 rumor 相关容器："
    docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}" || true

    # 强制删除可能存在的旧容器（无论是否由 docker-compose 创建）
    for container in rumor-api rumor-web; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "删除容器: $container"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done

    # 使用 docker compose down 清理
    $DOCKER_COMPOSE_CMD down --remove-orphans 2>/dev/null || true

    echo -e "${GREEN}✅ 清理完成${NC}"
}

# 完整部署
do_deploy() {
    print_header "🚀 开始部署 AI 谣言粉碎机"

    check_docker
    setup_compose_cmd
    check_env_file

    # 强制清理
    force_cleanup

    # 构建并启动
    print_step "构建镜像并启动服务..."
    $DOCKER_COMPOSE_CMD up -d --build --force-recreate

    # 等待服务启动
    print_step "等待服务启动..."
    sleep 5

    # 检查服务状态
    check_services_status
}

# 启动服务
do_start() {
    print_header "▶️  启动服务"
    setup_compose_cmd
    $DOCKER_COMPOSE_CMD up -d
    sleep 3
    check_services_status
}

# 停止服务
do_stop() {
    print_header "⏹  停止服务"
    setup_compose_cmd
    $DOCKER_COMPOSE_CMD down
    echo -e "${GREEN}✅ 服务已停止${NC}"
}

# 重启服务
do_restart() {
    print_header "🔄 重启服务"
    setup_compose_cmd
    $DOCKER_COMPOSE_CMD restart
    sleep 3
    check_services_status
}

# 清理所有资源
do_clean() {
    print_header "🧹 深度清理"

    read -p "确定要删除所有容器、镜像和卷吗？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "取消操作"
        return
    fi

    setup_compose_cmd

    print_step "停止并删除容器..."
    $DOCKER_COMPOSE_CMD down --volumes --remove-orphans

    print_step "删除镜像..."
    docker images | grep rumor | awk '{print $3}' | xargs -r docker rmi -f || true

    print_step "清理悬空资源..."
    docker system prune -f

    echo -e "${GREEN}✅ 深度清理完成${NC}"
}

# 查看服务状态
do_status() {
    print_header "📊 服务状态"
    setup_compose_cmd

    echo -e "\n容器状态："
    $DOCKER_COMPOSE_CMD ps

    echo -e "\n网络信息："
    docker network ls | grep rumor || echo "无 rumor 网络"

    echo -e "\n最近日志（最后 20 行）："
    $DOCKER_COMPOSE_CMD logs --tail=20
}

# 查看日志
do_logs() {
    setup_compose_cmd

    if [ -n "$1" ]; then
        $DOCKER_COMPOSE_CMD logs -f "$1"
    else
        $DOCKER_COMPOSE_CMD logs -f
    fi
}

# 检查服务健康状态
check_services_status() {
    print_step "检查服务健康状态..."

    # 等待容器完全启动
    sleep 3

    # 检查 rumor-api
    if docker ps --format '{{.Names}}' | grep -q "^rumor-api$"; then
        # 尝试调用健康检查接口
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ rumor-api 运行正常 (http://localhost:8000)${NC}"
        else
            echo -e "${YELLOW}⚠️  rumor-api 容器已启动，但健康检查失败${NC}"
            echo "   运行 '$0 logs rumor-api' 查看详细日志"
        fi
    else
        print_error "rumor-api 未运行"
    fi

    # 检查 rumor-web
    if docker ps --format '{{.Names}}' | grep -q "^rumor-web$"; then
        if curl -s http://localhost:7860 > /dev/null 2>&1; then
            echo -e "${GREEN}✅ rumor-web 运行正常 (http://localhost:7860)${NC}"
        else
            echo -e "${YELLOW}⚠️  rumor-web 容器已启动，但健康检查失败${NC}"
            echo "   运行 '$0 logs rumor-web' 查看详细日志"
        fi
    else
        print_error "rumor-web 未运行"
    fi
}

# 显示部署成功信息
show_success_info() {
    print_header "🎉 部署完成"

    cat << EOF
${GREEN}服务访问地址：${NC}
  • Web 界面:  http://localhost:7860
  • API 文档:  http://localhost:8000/docs
  • 健康检查:  http://localhost:8000/health

${GREEN}常用命令：${NC}
  • 查看日志:  $0 logs
  • 查看状态:  $0 status
  • 停止服务:  $0 stop
  • 重启服务:  $0 restart

${GREEN}Docker 命令：${NC}
  • API 日志:  docker logs rumor-api -f
  • Web 日志:  docker logs rumor-web -f
  • 容器状态:  docker ps

${YELLOW}注意：${NC}
  如果服务器启用了防火墙，请确保已开放 8000 和 7860 端口
EOF
}

# 主函数
main() {
    # 获取操作类型
    ACTION=${1:-deploy}

    case "$ACTION" in
        deploy)
            do_deploy
            show_success_info
            ;;
        start)
            do_start
            ;;
        stop)
            do_stop
            ;;
        restart)
            do_restart
            ;;
        clean)
            do_clean
            ;;
        status)
            do_status
            ;;
        logs)
            do_logs "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知操作: $ACTION"
            show_help
            exit 1
            ;;
    esac
}

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 执行主函数
main "$@"
