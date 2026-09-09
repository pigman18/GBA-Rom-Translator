@echo off
REM W0 预算勘测 — 日版 Ruby（AXVJ）原盘（2026-09-08 handler 修正后）
REM 见 docs/开发_20260908_日美文本划界移植可行性.md §11
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=src
echo mGBA: 打开 roms\origin\POKEMON_RUBY_AXVJ00.gba （日版原盘，非汉化成品）
echo       Tools - Start GDB stub - Pause
echo 场景建议: 对话 -^> 开始菜单 -^> 设置 -^> 队伍 -^> 起名（与美版同一路径）
echo 日志标签: [W0-TPL] [W0-MULTI] [W0-IWTD-JP] [W0-SPAN-JP] [W0-FRAME] [W0-ITP]
echo   FRAME= left/top/right/bottom -^> w×h （已修正，勿看旧 height?[sp]）
echo   TPL  = MultistepInit@0x08002950（win→tpl）；勿再用 0x080029E0 当模板入口
echo.
C:\Python314\python.exe -m util.gdb_patcher log --preset w0-jp
echo.
echo 日志: src\util\work\POKEMON_RUBY_AXVJ00\gdb_patcher_log.log
pause
