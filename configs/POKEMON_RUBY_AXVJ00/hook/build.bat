@echo off
REM build.bat - compile src/ -> out/game.bin (VMA 0x08800000)
REM Naming: src/{domain}/{Method}_hook.c
REM Requires arm-none-eabi-gcc in PATH.

set PREFIX=arm-none-eabi-
set CC=%PREFIX%gcc
set OBJCOPY=%PREFIX%objcopy

set SRC_ROOT=src
set TEXT=%SRC_ROOT%\text
set BATTLE=%SRC_ROOT%\battle
set POKEDEX=%SRC_ROOT%\pokedex
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -I%SRC_ROOT% -nostdlib -c
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if not exist %BUILD% mkdir %BUILD%

echo === Assembling PrintNextChar_entry.s ===
%CC% %ASFLAGS% %TEXT%\PrintNextChar_entry.s -o %BUILD%\PrintNextChar_entry.o
if errorlevel 1 exit /b 1

echo === Compiling PrintNextChar_hook.c ===
%CC% %CFLAGS% %TEXT%\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o
if errorlevel 1 exit /b 1

echo === Compiling DrawGlyphTiles_hook.c ===
%CC% %CFLAGS% %TEXT%\DrawGlyphTiles_hook.c -o %BUILD%\DrawGlyphTiles_hook.o
if errorlevel 1 exit /b 1

echo === Compiling DrawGlyphTiles_scene.c ===
%CC% %CFLAGS% %TEXT%\DrawGlyphTiles_scene.c -o %BUILD%\DrawGlyphTiles_scene.o
if errorlevel 1 exit /b 1

echo === Compiling GetStringWidth_hook.c ===
%CC% %CFLAGS% %TEXT%\GetStringWidth_hook.c -o %BUILD%\GetStringWidth_hook.o
if errorlevel 1 exit /b 1

echo === Compiling GetGlyphWidth_hook.c ===
%CC% %CFLAGS% %TEXT%\GetGlyphWidth_hook.c -o %BUILD%\GetGlyphWidth_hook.o
if errorlevel 1 exit /b 1

echo === Assembling UpdateNickInHealthbox_entry.s ===
%CC% %ASFLAGS% %BATTLE%\UpdateNickInHealthbox_entry.s -o %BUILD%\UpdateNickInHealthbox_entry.o
if errorlevel 1 exit /b 1

echo === Compiling UpdateNickInHealthbox_hook.c ===
%CC% %CFLAGS% %BATTLE%\UpdateNickInHealthbox_hook.c -o %BUILD%\UpdateNickInHealthbox_hook.o
if errorlevel 1 exit /b 1

echo === Assembling UnusedPrintMonName_entry.s ===
%CC% %ASFLAGS% %POKEDEX%\UnusedPrintMonName_entry.s -o %BUILD%\UnusedPrintMonName_entry.o
if errorlevel 1 exit /b 1

echo === Compiling UnusedPrintMonName_hook.c ===
%CC% %CFLAGS% %POKEDEX%\UnusedPrintMonName_hook.c -o %BUILD%\UnusedPrintMonName_hook.o
if errorlevel 1 exit /b 1

echo === Linking game.elf ===
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/PrintNextChar_entry.o ^
  %BUILD%/PrintNextChar_hook.o ^
  %BUILD%/DrawGlyphTiles_hook.o ^
  %BUILD%/DrawGlyphTiles_scene.o ^
  %BUILD%/GetStringWidth_hook.o ^
  %BUILD%/GetGlyphWidth_hook.o ^
  %BUILD%/UpdateNickInHealthbox_entry.o ^
  %BUILD%/UpdateNickInHealthbox_hook.o ^
  %BUILD%/UnusedPrintMonName_entry.o ^
  %BUILD%/UnusedPrintMonName_hook.o
if errorlevel 1 exit /b 1

echo === Generating game.bin ===
%OBJCOPY% -O binary %OUT%/game.elf %OUT%/game.bin
if errorlevel 1 exit /b 1

echo === Generating game_syms.asm ===
set GSW_ADDR=0x08800000
set MPN_ADDR=0x08800000
set WTA_ADDR=0x08800000
set UPMN_ADDR=0x08800000
for /f "tokens=1" %%a in ('findstr /R "GetStringWidthChinese$" %OUT%\game.map') do set GSW_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "MapName_DisplayCellLength$" %OUT%\game.map') do set MPN_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "WaitArrow_Prepare$" %OUT%\game.map') do set WTA_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "UnusedPrintMonName_Hook$" %OUT%\game.map') do set UPMN_ADDR=%%a
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    echo GetStringWidthChinese                   equ %GSW_ADDR%
    echo MapName_DisplayCellLength               equ %MPN_ADDR%
    echo WaitArrow_Prepare                       equ %WTA_ADDR%
    echo UnusedPrintMonName_Hook                 equ %UPMN_ADDR%
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
