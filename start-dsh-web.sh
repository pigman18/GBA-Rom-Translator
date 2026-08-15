#!/usr/bin/env bash
# dsh web 启动脚本 —— 供 Windows NSSM 服务调用（经 wsl.exe 进入真实 WSL）
set -u
export HOME=/root
LOG=/root/.dsh-web-service.log
echo "[$(date '+%F %T')] start-dsh-web.sh invoked" >> "$LOG"

# 若已有 dsh web 进程在跑则直接退出成功（避免重复启动）
if pgrep -f "node /usr/bin/dsh web" >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] dsh web already running (pid $(pgrep -f 'node /usr/bin/dsh web' | head -1))" >> "$LOG"
    exit 0
fi

# 前台运行，由 NSSM 作为服务进程托管
echo "[$(date '+%F %T')] launching dsh web" >> "$LOG"
exec node /usr/bin/dsh web >> "$LOG" 2>&1
