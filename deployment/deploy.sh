#!/bin/bash

# =================================================================
# Internet Rumors Judge - 一键部署脚本
# 自动适配 docker compose (V2) 和 docker-compose (V1)
# =================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 开始部署 AI 谣言粉碎机...${NC}"

# 1. 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 错误: 未检测到 Docker，请先安装 Docker。${NC}"
    exit 1
fi

# 2. 自动检测 Compose 命令
DOCKER_COMPOSE_CMD=""

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo -e "${GREEN}✅ 检测到现代版 Docker Compose (V2)${NC}"
elif docker-compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    echo -e "${YELLOW}⚠️  检测到旧版 docker-compose (V1)${NC}"
    echo -e "${YELLOW}提示: 如果遇到 'ContainerConfig' 错误，请参考 README 升级到 V2。${NC}"
else
    echo -e "${RED}❌ 错误: 未检测到任何版本的 Docker Compose。${NC}"
    exit 1
fi

# 3. 检查 .env 文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  未发现 .env 文件，正在从模板创建...${NC}"
    echo "DASHSCOPE_API_KEY=your_key_here" > .env
    echo "TAVILY_API_KEY=your_key_here" >> .env
    echo -e "${RED}请编辑 .env 文件并填入真实的 API Key 后重新运行此脚本。${NC}"
    exit 1
fi

# 4. 执行部署流程
echo -e "${GREEN}正在清理旧容器...${NC}"
$DOCKER_COMPOSE_CMD down

echo -e "${GREEN}正在构建镜像并启动服务...${NC}"
$DOCKER_COMPOSE_CMD up -d --build

# 5. 结果检查
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}==================================================${NC}"
    echo -e "${GREEN}🎉 部署成功！${NC}"
    echo -e "${GREEN}Web 界面: http://localhost:7860${NC}"
    echo -e "${GREEN}API 服务: http://localhost:8000${NC}"
    echo -e "${GREEN}查看日志: docker logs rumor-web -f${NC}"
    echo -e "${GREEN}==================================================${NC}"
else
    echo -e "${RED}❌ 部署过程中出现错误，请查看上方日志。${NC}"
fi
