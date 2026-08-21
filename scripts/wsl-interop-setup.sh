#!/bin/sh
# 一键恢复 WSL→Windows 互操作（binfmt WSLInterop 注册）。
# 适用：WSL2 + systemd=true（systemd 启动时会刷掉 binfmt 注册项），
#       或本仓库容器环境（/etc、/usr 只读，无法用 binfmt.d 持久化）。
#
# 用法:  scripts/wsl-interop-setup.sh [--check]
# 说明:  注册为内核级，容器重启不丢；整个 WSL 关闭(wsl --shutdown/重启电脑)
#        后重跑本脚本即可。想彻底持久化见文件末尾注释。

set -e

REG=/proc/sys/fs/binfmt_misc/register
STATUS=/proc/sys/fs/binfmt_misc/WSLInterop

if [ -f "$STATUS" ] && grep -q enabled "$STATUS" 2>/dev/null; then
    echo "[wsl-interop] already registered:"
    sed 's/^/    /' "$STATUS"
    exit 0
fi

if [ "$(cat /proc/sys/fs/binfmt_misc/status 2>/dev/null)" != "enabled" ]; then
    modprobe binfmt_misc 2>/dev/null || mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc 2>/dev/null || {
        echo "[wsl-interop] ERROR: binfmt_misc unavailable" >&2; exit 1; }
fi

[ -x /init ] || { echo "[wsl-interop] ERROR: /init missing (not WSL2?)" >&2; exit 1; }

echo ':WSLInterop:M::MZ::/init:PF' > "$REG"
echo "[wsl-interop] registered OK"
sed 's/^/    /' "$STATUS"

# 验证：调用 Windows 侧工具链
TC=/mnt/c/soft/env/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi/bin/arm-none-eabi-gcc.exe
[ -x "$TC" ] && "$TC" --version >/dev/null 2>&1 && echo "[wsl-interop] windows gcc.exe OK" \
    || echo "[wsl-interop] WARN: cannot run $TC"

exit 0

# ---------------------------------------------------------------------------
# 彻底持久化（在真正的 WSL 发行版里，非本容器）：
#   方案 A（推荐, systemd）：
#     sudo sh -c 'printf ":WSLInterop:M::MZ::/init:PF\n" > /usr/lib/binfmt.d/WSLInterop.conf'
#     sudo systemctl enable systemd-binfmt.service
#   方案 B（无 systemd）：把本脚本加进 ~/.profile 或 /etc/rc.local
#   改完建议: wsl --shutdown 后重进验证 `scripts/wsl-interop-setup.sh --check`
# ---------------------------------------------------------------------------
