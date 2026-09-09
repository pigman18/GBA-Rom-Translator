@echo off
REM W0 预算勘测 — 美版 Ruby 1.0（AXVE）
REM FRAME 已改为 left/top/right/bottom→w×h（与 pokeruby 一致）
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=src
echo mGBA: 打开 roms\origin\Pokemon Ruby Version(US).gba （必须 1.0 / AXVE）
echo       Tools - Start GDB stub - Pause
echo 场景建议: 对话 -^> 开始菜单 -^> 设置 -^> 队伍 -^> 起名
echo 日志标签: [W0-TPL] [W0-IWTD-US] [W0-SPAN] [W0-FRAME] [W0-ITP] [W0-GCTN]
echo.
C:\Python314\python.exe -m util.gdb_patcher log --preset w0-us
echo.
echo 日志: src\util\work\POKEMON_RUBY_AXVE\gdb_patcher_log.log
pause
