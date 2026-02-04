#!/bin/bash

# =================================================================
# Internet Rumors Judge - 服务器部署脚本 v2.1
# 智能构建策略：只在必要时重新构建，避免重复下载依赖
# =================================================================

set -e  # 遇到错误立即退出

# 全局变量
FORCE_BUILD=false
FORCE_RECREATE=false

# 检测终端是否支持颜色
if [ -t 1 ] && [ "$(tput colors 2>/dev/null)" -ge 8 ]; then
    # 终端支持颜色
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m' # No Color
else
    # 终端不支持颜色或输出被重定向，使用空字符串
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

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

print_info() {
    echo -e "${CYAN}[信息] $1${NC}"
}

# 显示使用帮助
show_help() {
    cat << EOF
用法: $0 [选项] [命令]

选项:
    --build, -b      强制重新构建镜像（即使镜像已存在）
    --recreate, -r   强制重新创建容器
    --help, -h       显示此帮助信息

命令:
    deploy      完整部署（默认，智能判断是否需要构建）
    start       启动服务（使用现有镜像）
    stop        停止服务
    restart     重启服务
    rebuild     强制重新构建并部署
    clean       清理所有容器、镜像和卷
    status      查看服务状态
    logs        查看服务日志

示例:
    $0 deploy              # 智能部署（镜像存在则跳过构建）
    $0 deploy --build      # 强制重新构建并部署
    $0 rebuild             # 强制重新构建并部署
    $0 start               # 快速启动（使用现有镜像）
    $0 status              # 查看状态

构建策略:
    • 首次部署: 自动构建镜像
    • 代码更新: 自动重建镜像（利用 Docker 层缓存）
    • 依赖更新: 需要使用 --build 强制重新安装
    • 快速启动: 使用 start 命令，跳过构建
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

# 检查镜像是否已存在
check_image_exists() {
    docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^internet-rumors-judge:latest"
}

# 强制清理旧容器和镜像
force_cleanup() {
    print_step "清理旧容器..."

    # 强制删除可能存在的旧容器（无论是否由 docker-compose 创建）
    for container in rumor-api rumor-web; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo "  删除容器: $container"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done

    # 使用 docker compose down 清理
    $DOCKER_COMPOSE_CMD down --remove-orphans 2>/dev/null || true

    echo -e "${GREEN}✅ 清理完成${NC}"
}

# 智能构建镜像
smart_build() {
    local build_needed=$1

    if [ "$FORCE_BUILD" = true ]; then
        print_step "强制重新构建镜像..."
        $DOCKER_COMPOSE_CMD build --no-cache
        return
    fi

    if [ "$build_needed" = true ]; then
        if check_image_exists; then
            print_info "镜像已存在，使用缓存重建..."
            $DOCKER_COMPOSE_CMD build
        else
            print_step "首次构建镜像（可能需要几分钟）..."
            $DOCKER_COMPOSE_CMD build
        fi
    else
        print_info "镜像已存在，跳过构建（使用 --build 强制重建）"
    fi
}

# 完整部署
do_deploy() {
    print_header "🚀 开始部署 AI 谣言粉碎机"

    check_docker
    setup_compose_cmd
    check_env_file

    # 检查镜像是否存在
    local image_exists=false
    if check_image_exists; then
        image_exists=true
        print_info "检测到已存在的镜像"
    fi

    # 判断是否需要构建
    local build_needed=false
    if [ "$image_exists" = false ] || [ "$FORCE_BUILD" = true ]; then
        build_needed=true
    fi

    # 清理旧容器
    force_cleanup

    # 智能构建
    if [ "$build_needed" = true ]; then
        smart_build true
    else
        smart_build false
    fi

    # 启动服务
    print_step "启动服务..."
    if [ "$FORCE_RECREATE" = true ]; then
        $DOCKER_COMPOSE_CMD up -d --force-recreate
    else
        $DOCKER_COMPOSE_CMD up -d
    fi

    # 等待服务启动
    print_step "等待服务启动..."
    sleep 5

    # 检查服务状态
    check_services_status
}

# 强制重新构建并部署
do_rebuild() {
    print_header "🔨 强制重新构建并部署"

    check_docker
    setup_compose_cmd
    check_env_file

    force_cleanup

    print_step "重新构建镜像（不使用缓存）..."
    $DOCKER_COMPOSE_CMD build --no-cache

    print_step "启动服务..."
    $DOCKER_COMPOSE_CMD up -d --force-recreate

    sleep 5
    check_services_status
}

# 快速启动（使用现有镜像）
do_start() {
    print_header "▶️  快速启动服务"

    setup_compose_cmd

    if ! check_image_exists; then
        print_warning "镜像不存在，将自动构建..."
        $DOCKER_COMPOSE_CMD build
    fi

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
    docker images | grep -E 'REPOSITORY|internet-rumors-judge' | awk 'NR>1 {print $3}' | xargs -r docker rmi -f || true

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

    echo -e "\n镜像信息："
    docker images | grep -E 'REPOSITORY|internet-rumors-judge' || echo "无相关镜像"

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

    echo -e "${GREEN}服务访问地址：${NC}"
    echo "  • Web 界面:  http://localhost:7860"
    echo "  • API 文档:  http://localhost:8000/docs"
    echo "  • 健康检查:  http://localhost:8000/health"
    echo ""
    echo -e "${GREEN}常用命令：${NC}"
    echo "  • 快速启动:  $0 start"
    echo "  • 查看状态:  $0 status"
    echo "  • 查看日志:  $0 logs"
    echo "  • 停止服务:  $0 stop"
    echo "  • 重启服务:  $0 restart"
    echo ""
    echo -e "${GREEN}更新代码后：${NC}"
    echo "  • 代码更新:  $0 deploy              # 智能重建（利用缓存，快）"
    echo "  • 依赖更新:  $0 deploy --build       # 强制重新安装依赖"
    echo ""
    echo -e "${GREEN}Docker 命令：${NC}"
    echo "  • API 日志:  docker logs rumor-api -f"
    echo "  • Web 日志:  docker logs rumor-web -f"
    echo "  • 容器状态:  docker ps"
    echo ""
    echo -e "${YELLOW}构建说明：${NC}"
    echo "  • 首次部署或依赖更新: 使用 --build 选项"
    echo "  • 代码更新: 直接 deploy，利用 Docker 层缓存"
    echo "  • 快速启动: 使用 start 命令，跳过构建"
    echo ""
    echo -e "${YELLOW}注意：${NC}"
    echo "  如果服务器启用了防火墙，请确保已开放 8000 和 7860 端口"
}

# 主函数
main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --build|-b)
                FORCE_BUILD=true
                shift
                ;;
            --recreate|-r)
                FORCE_RECREATE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                break
                ;;
        esac
    done

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
        rebuild)
            do_rebuild
            show_success_info
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
