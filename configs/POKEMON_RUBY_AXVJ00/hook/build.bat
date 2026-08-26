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

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I%SRC_ROOT% -nostdlib -c
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if not exist %BUILD% mkdir %BUILD%

echo === Assembling entry.s ===
%CC% %ASFLAGS% %SRC_ROOT%\text\entry.s -o %BUILD%\text_entry.o
if errorlevel 1 exit /b 1

echo === Compiling PrintNextChar_hook.c (JP takeover engine) ===
%CC% %CFLAGS% %SRC_ROOT%\text\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o
if errorlevel 1 exit /b 1


echo === Compiling text_translter.c (F9 protocol layer) ===
%CC% %CFLAGS% %SRC_ROOT%\text\text_translter.c -o %BUILD%\text_translter.o
if errorlevel 1 exit /b 1

echo === Compiling text_render.c (shared render primitives) ===
%CC% %CFLAGS% %SRC_ROOT%\text\text_render.c -o %BUILD%\text_render.o
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

echo === Linking game.elf ===
@rem text_entry.o must be FIRST: main.asm JP2CHS_Entry = GameBinAddresses = bin start.
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/text_entry.o ^
  %BUILD%/PrintNextChar_hook.o ^
  %BUILD%/text_translter.o ^
  %BUILD%/text_render.o ^
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
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
