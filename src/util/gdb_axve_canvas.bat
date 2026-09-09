@echo off
REM 美版 Ruby 1.0（AXVE）文本画布对照采集——勿用日版 AXVJ yaml
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=src
echo mGBA: 打开 roms\origin\Pokemon Ruby Version(US).gba （必须 1.0 / AXVE）
echo       Tools - Start GDB stub - Pause
echo.
C:\Python314\python.exe -m util.gdb_patcher log --preset us-canvas
echo.
echo 日志: src\util\work\POKEMON_RUBY_AXVE\gdb_patcher_log.log
pause
