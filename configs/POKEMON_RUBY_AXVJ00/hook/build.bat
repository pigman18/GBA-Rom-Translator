@echo off
REM build.bat - compile src/ -> out/game.bin (VMA 0x08800000)
REM Usage: cd patch\ && build.bat
REM Requires arm-none-eabi-gcc in PATH.

set PREFIX=arm-none-eabi-
set CC=%PREFIX%gcc
set OBJCOPY=%PREFIX%objcopy

set SRC_ROOT=src
set PNC=%SRC_ROOT%\text\PrintNextChar
set NICK=%SRC_ROOT%\battle\UpdateNickInHealthbox
set FSTR=%SRC_ROOT%\ui\fixed_string
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -I%SRC_ROOT% -I%FSTR% -nostdlib -c
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if not exist %BUILD% mkdir %BUILD%

echo === Assembling entry.s ===
%CC% %ASFLAGS% %PNC%\entry.s -o %BUILD%\entry.o
if errorlevel 1 exit /b 1

echo === Compiling print_next_char.c ===
%CC% %CFLAGS% %PNC%\print_next_char.c -o %BUILD%\print_next_char.o
if errorlevel 1 exit /b 1

echo === Compiling draw_glyph.c ===
%CC% %CFLAGS% %PNC%\draw_glyph.c -o %BUILD%\draw_glyph.o
if errorlevel 1 exit /b 1

echo === Compiling draw_scene.c ===
%CC% %CFLAGS% %PNC%\draw_scene.c -o %BUILD%\draw_scene.o
if errorlevel 1 exit /b 1

echo === Compiling get_string_width.c ===
%CC% %CFLAGS% %PNC%\get_string_width.c -o %BUILD%\get_string_width.o
if errorlevel 1 exit /b 1

echo === Assembling nick_entry.s ===
%CC% %ASFLAGS% %NICK%\entry.s -o %BUILD%\nick_entry.o
if errorlevel 1 exit /b 1

echo === Compiling update_nick_in_healthbox.c ===
%CC% %CFLAGS% %NICK%\update_nick_in_healthbox.c -o %BUILD%\update_nick_in_healthbox.o
if errorlevel 1 exit /b 1

echo === Assembling fixed_string entry.s ===
%CC% %ASFLAGS% %FSTR%\entry.s -o %BUILD%\fixed_string_entry.o
if errorlevel 1 exit /b 1

echo === Compiling fixed_string.c ===
%CC% %CFLAGS% %FSTR%\fixed_string.c -o %BUILD%\fixed_string.o
if errorlevel 1 exit /b 1

echo === Linking game.elf ===
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/entry.o ^
  %BUILD%/print_next_char.o ^
  %BUILD%/draw_glyph.o ^
  %BUILD%/draw_scene.o ^
  %BUILD%/get_string_width.o ^
  %BUILD%/nick_entry.o ^
  %BUILD%/update_nick_in_healthbox.o ^
  %BUILD%/fixed_string_entry.o ^
  %BUILD%/fixed_string.o
if errorlevel 1 exit /b 1

echo === Generating game.bin ===
%OBJCOPY% -O binary %OUT%/game.elf %OUT%/game.bin
if errorlevel 1 exit /b 1

echo === Generating game_syms.asm ===
set GSW_ADDR=0x08800000
set MAPLEN_ADDR=0x08800000
set FSTR_POKEDEX_HOOK=0x08800000
for /f "tokens=1" %%a in ('findstr /R "GetStringWidthChinese$" %OUT%\game.map') do set GSW_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "MapName_DisplayCellLength$" %OUT%\game.map') do set MAPLEN_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "ContinuePokedexUnit_Hook$" %OUT%\game.map') do set FSTR_POKEDEX_HOOK=%%a
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    echo GetStringWidthChinese                   equ %GSW_ADDR%
    echo MapName_DisplayCellLength               equ %MAPLEN_ADDR%
    echo ContinuePokedexUnit_Hook                equ %FSTR_POKEDEX_HOOK%
)

echo Build OK: %OUT%\game.bin
