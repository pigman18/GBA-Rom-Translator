@echo off
REM build.bat - compile src/ -> out/game.bin (VMA 0x08800000)
REM Naming: src/{domain}/{Method}_hook.c + entry.s + hooks_origin.s (armips side)
REM Requires arm-none-eabi-gcc in PATH.
REM
REM 2026-08-30 build-consistency fixes (comments kept ASCII: cmd.exe mangles
REM   UTF-8 CJK in REM lines and may execute the fragments):
REM   1) battle/pokedex/option objects were linked but NEVER compiled -- stale
REM      .o silently shipped. Now compiled.
REM   2) wipe %BUILD% first so orphan .o of deleted sources are never linked.
REM   2026-08-31 REWRITE v5 (mixed-write architecture, see repo docs dir,
REM   REWRITE_DESIGN md): v4 engine (PrintNextChar_hook / text_render /
REM   text_scene / text_layout / tile_alloc) moved to bak/text-v4.
REM   New text engine starts from blend_glyph (pure primitive, offline-tested
REM   via tests/test_blend_glyph.py). Vendored reference/ no longer compiled.

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

REM --- wipe stale objects so nothing old can be linked by accident ---
if exist %BUILD% rmdir /s /q %BUILD%
if not exist %BUILD% mkdir %BUILD%

echo === Compiling text/blend_glyph.c (mixed-write pixel primitive) ===
%CC% %CFLAGS% %TEXT%\blend_glyph.c -o %BUILD%\blend_glyph.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_translater.c (F9 protocol layer, kept from v4) ===
%CC% %CFLAGS% %TEXT%\text_translater.c -o %BUILD%\text_translater.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_render.c (v5 renderer: PrintGlyph/DrawGlyph) ===
%CC% %CFLAGS% %TEXT%\text_render.c -o %BUILD%\text_render.o
if errorlevel 1 exit /b 1

echo === Compiling text/fontfunc_hook.c (v5 FontFuncTable redirect thunks) ===
%CC% %CFLAGS% %TEXT%\fontfunc_hook.c -o %BUILD%\fontfunc_hook.o
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
@rem text objs first (historical convention; no entry.o constraint in v5 --
@rem FontFuncTable redirect only needs the 4 thunk symbols via game_syms.asm).
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/blend_glyph.o ^
  %BUILD%/text_translater.o ^
  %BUILD%/text_render.o ^
  %BUILD%/fontfunc_hook.o ^
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
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook FontFuncTm0_Hook FontFuncTm1_Hook FontFuncTm2_Hook FontFuncTm3_Hook) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
