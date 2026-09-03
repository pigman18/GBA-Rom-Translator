@echo off
REM build.bat - compile src/ -> out/game.bin (VMA 0x08800000)
REM v6: PrintNextChar unique hook (entry.s FIRST) + text_render + blend + translater
REM Requires arm-none-eabi-gcc in PATH.

set PREFIX=arm-none-eabi-
set CC=%PREFIX%gcc
set OBJCOPY=%PREFIX%objcopy

set SRC_ROOT=src
set TEXT=%SRC_ROOT%\text
set MAP_POPUP=%SRC_ROOT%\map_name_popup
set BATTLE=%SRC_ROOT%\battle
set POKEDEX=%SRC_ROOT%\pokedex
set OPTION=%SRC_ROOT%\option
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I%SRC_ROOT% -nostdlib -c
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if exist %BUILD% rmdir /s /q %BUILD%
if not exist %BUILD% mkdir %BUILD%

echo === Assembling text\entry.s (EngineEntry MUST be link-first) ===
%CC% %ASFLAGS% %TEXT%\entry.s -o %BUILD%\text_entry.o
if errorlevel 1 exit /b 1

echo === Compiling text\scene_cfg.c ===
%CC% %CFLAGS% %TEXT%\scene_cfg.c -o %BUILD%\scene_cfg.o
if errorlevel 1 exit /b 1

echo === Compiling text\InitTextPrinter_hook.c ===
%CC% %CFLAGS% %TEXT%\InitTextPrinter_hook.c -o %BUILD%\InitTextPrinter_hook.o
if errorlevel 1 exit /b 1

echo === Compiling text\PrintNextChar_hook.c ===
%CC% %CFLAGS% %TEXT%\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o
if errorlevel 1 exit /b 1

echo === Compiling text\blend_glyph.c ===
%CC% %CFLAGS% %TEXT%\blend_glyph.c -o %BUILD%\blend_glyph.o
if errorlevel 1 exit /b 1

echo === Compiling text\tile_alloc.c ===
%CC% %CFLAGS% %TEXT%\tile_alloc.c -o %BUILD%\tile_alloc.o
if errorlevel 1 exit /b 1

echo === Compiling text\text_translater.c ===
%CC% %CFLAGS% %TEXT%\text_translater.c -o %BUILD%\text_translater.o
if errorlevel 1 exit /b 1

echo === Assembling map_name_popup\entry.s ===
%CC% %ASFLAGS% %MAP_POPUP%\entry.s -o %BUILD%\MapNamePopup_entry.o
if errorlevel 1 exit /b 1

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
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/text_entry.o ^
  %BUILD%/scene_cfg.o ^
  %BUILD%/InitTextPrinter_hook.o ^
  %BUILD%/PrintNextChar_hook.o ^
  %BUILD%/blend_glyph.o ^
  %BUILD%/tile_alloc.o ^
  %BUILD%/text_translater.o ^
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
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook UpdateNickInHealthbox_Hook UpdateNickInHealthbox_Hook_Other UpdateTilemap_Origin InitTextPrinter_Hook) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
