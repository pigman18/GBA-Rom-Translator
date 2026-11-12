@echo off
REM build.bat - compile src/ -> out/game.bin (VMA 0x08800000)
REM Naming: src/{domain}/{Method}_hook.c + entry.s + hooks_origin.s (armips side)
REM Requires arm-none-eabi-gcc in PATH.

set PREFIX=arm-none-eabi-
set CC=%PREFIX%gcc
set OBJCOPY=%PREFIX%objcopy

set SRC_ROOT=src
set MAP_POPUP=%SRC_ROOT%\map_name_popup
set BATTLE=%SRC_ROOT%\battle
set POKEDEX=%SRC_ROOT%\pokedex
set OPTION=%SRC_ROOT%\option
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I%SRC_ROOT% -nostdlib -c %EXTRA_CFLAGS%
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if not exist %BUILD% mkdir %BUILD%

echo === Assembling entry.s ===
%CC% %ASFLAGS% %SRC_ROOT%\text\entry.s -o %BUILD%\text_entry.o
if errorlevel 1 exit /b 1

echo === Compiling PrintNextChar_hook.c (JP takeover engine) ===
%CC% %CFLAGS% %SRC_ROOT%\text\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o
if errorlevel 1 exit /b 1


rem 2026-11-11 晚：串页方案（页表 / PHYS 池 / 列内容池）整体退役。
rem 运行时逻辑全部收进 PrintNextChar_hook.c + include/text_grid.h：
rem tile 号是屏幕行列的纯函数，字库 0x09000000 由 font_patch 装入，
rem 构建期不再生成任何页表，engine.run_full() 不再后置烙入 0x09500000。
rem reference/ 已于 2026-11-02 移除：5 个 ref* 符号无调用者（原占约 8KB）。

echo === Assembling map_name_popup\entry.s ===
%CC% %ASFLAGS% %MAP_POPUP%\entry.s -o %BUILD%\MapNamePopup_entry.o

echo === Compiling map_name_popup\MapNamePopup_hook.c ===
%CC% %CFLAGS% %MAP_POPUP%\MapNamePopup_hook.c -o %BUILD%\MapNamePopup_hook.o
if errorlevel 1 exit /b 1

echo === Assembling battle\UpdateNickInHealthbox_entry.s ===
%CC% %ASFLAGS% %BATTLE%\UpdateNickInHealthbox_entry.s -o %BUILD%\UpdateNickInHealthbox_entry.o
if errorlevel 1 exit /b 1

echo === Compiling battle\UpdateNickInHealthbox_hook.c ===
%CC% %CFLAGS% %BATTLE%\UpdateNickInHealthbox_hook.c -o %BUILD%\UpdateNickInHealthbox_hook.o
if errorlevel 1 exit /b 1

echo === Assembling pokedex\UnusedPrintMonName_entry.s ===
%CC% %ASFLAGS% %POKEDEX%\UnusedPrintMonName_entry.s -o %BUILD%\UnusedPrintMonName_entry.o
if errorlevel 1 exit /b 1

echo === Compiling pokedex\UnusedPrintMonName_hook.c ===
%CC% %CFLAGS% %POKEDEX%\UnusedPrintMonName_hook.c -o %BUILD%\UnusedPrintMonName_hook.o
if errorlevel 1 exit /b 1

echo === Assembling option\DrawOptionMenuChoice_entry.s ===
%CC% %ASFLAGS% %OPTION%\DrawOptionMenuChoice_entry.s -o %BUILD%\DrawOptionMenuChoice_entry.o
if errorlevel 1 exit /b 1

echo === Compiling option\DrawOptionMenuChoice_hook.c ===
%CC% %CFLAGS% %OPTION%\DrawOptionMenuChoice_hook.c -o %BUILD%\DrawOptionMenuChoice_hook.o
if errorlevel 1 exit /b 1

echo === Linking game.elf ===
@rem text_entry.o must be FIRST: main.asm JP2CHS_Entry = GameBinAddresses = bin start.
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/text_entry.o ^
  %BUILD%/PrintNextChar_hook.o ^
  %BUILD%/MapNamePopup_entry.o ^
  %BUILD%/MapNamePopup_hook.o ^
  %BUILD%/UpdateNickInHealthbox_entry.o ^
  %BUILD%/UpdateNickInHealthbox_hook.o ^
  %BUILD%/UnusedPrintMonName_entry.o ^
  %BUILD%/UnusedPrintMonName_hook.o ^
  %BUILD%/DrawOptionMenuChoice_entry.o ^
  %BUILD%/DrawOptionMenuChoice_hook.o
if errorlevel 1 exit /b 1

echo === Generating game.bin ===
%OBJCOPY% -O binary %OUT%/game.elf %OUT%/game.bin
if errorlevel 1 exit /b 1

echo === Generating game_syms.asm ===
rem Stream emit: no copy-vars, no silent fallback. Missing symbol -> no line ->
rem armips errors at use site (loud failure beats jumping to 0x08800000).
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
