@echo off
REM Docker 容器清理脚本 - Windows 版本

echo ======================================
echo Docker 容器清理脚本
echo ======================================

REM 检查 Docker 是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: Docker 守护进程未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

echo 📋 检查现有容器...
docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"

echo.
echo 🛑 停止并删除 rumor-api 容器...
docker ps -a --format "{{.Names}}" | findstr /b /c:"rumor-api" >nul
if not errorlevel 1 (
    docker stop rumor-api 2>nul
    docker rm rumor-api
    echo ✅ rumor-api 已删除
) else (
    echo ℹ️  rumor-api 容器不存在
)

echo.
echo 🛑 停止并删除 rumor-web 容器...
docker ps -a --format "{{.Names}}" | findstr /b /c:"rumor-web" >nul
if not errorlevel 1 (
    docker stop rumor-web 2>nul
    docker rm rumor-web
    echo ✅ rumor-web 已删除
) else (
    echo ℹ️  rumor-web 容器不存在
)

echo.
echo 🧹 清理悬空镜像...
docker image prune -f

echo.
echo 📋 清理完成，当前容器状态：
docker ps -a --filter "name=rumor-" --format "table {{.Names}}\t{{.Status}}"

echo.
echo ✅ 清理完成！现在可以运行 deploy.bat 进行部署
pause
