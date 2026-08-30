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
REM   Text engine: PrintNextChar_hook / text_render (bak/text_original skeleton,
REM   see bak/text_original/) + text_scene (declarative per-window CONFIG data)
REM   + text_layout (ALGORITHM: lookup / zones / tile placement, split out of
REM   text_scene.c 2026-08-30).

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

echo === Assembling text/entry.s ===
%CC% %ASFLAGS% %TEXT%\entry.s -o %BUILD%\text_entry.o
if errorlevel 1 exit /b 1

echo === Compiling text/PrintNextChar_hook.c (JP takeover engine) ===
%CC% %CFLAGS% %TEXT%\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_translater.c (F9 protocol layer) ===
%CC% %CFLAGS% %TEXT%\text_translater.c -o %BUILD%\text_translater.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_render.c (pixel prims + pitch slots) ===
%CC% %CFLAGS% %TEXT%\text_render.c -o %BUILD%\text_render.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_scene.c (declarative per-window layout CONFIG: data only) ===
%CC% %CFLAGS% %TEXT%\text_scene.c -o %BUILD%\text_scene.o
if errorlevel 1 exit /b 1

echo === Compiling text/text_layout.c (layout ALGORITHM: lookup/zones/tiles) ===
%CC% %CFLAGS% %TEXT%\text_layout.c -o %BUILD%\text_layout.o
if errorlevel 1 exit /b 1

echo === Compiling text/tile_alloc.c (tm1 unregistered-window row allocator) ===
%CC% %CFLAGS% %TEXT%\tile_alloc.c -o %BUILD%\tile_alloc.o
if errorlevel 1 exit /b 1

echo === Compiling reference/pokeemerald (vendored GLYPH_COPY) ===
%CC% %CFLAGS% -Ireference reference\pokeemerald\copy_glyph_to_tiles.c -o %BUILD%\ref_pokeemerald.o
if errorlevel 1 exit /b 1

echo === Compiling reference/pokeruby (vendored DrawGlyphTile prims) ===
%CC% %CFLAGS% -Ireference reference\pokeruby\draw_glyph_tile.c -o %BUILD%\ref_pokeruby.o
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
@rem text_entry.o must be FIRST: main.asm GameBinAddresses = bin start.
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/text_entry.o ^
  %BUILD%/PrintNextChar_hook.o ^
  %BUILD%/text_translater.o ^
  %BUILD%/text_render.o ^
  %BUILD%/text_scene.o ^
  %BUILD%/text_layout.o ^
  %BUILD%/tile_alloc.o ^
  %BUILD%/ref_pokeemerald.o ^
  %BUILD%/ref_pokeruby.o ^
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
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook EngineIwtdEntry) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
