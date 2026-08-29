@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================================
echo  OpenCode 代理启动器  (OpenAI-compatible proxy + 公网隧道)
echo ==================================================
set OPENCODE_SERVER_PASSWORD=fixed-pass-6
python opencode_openai_proxy.py
echo.
echo 代理已退出。按任意键关闭窗口...
pause >nul
