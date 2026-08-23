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
set OPTION=%SRC_ROOT%\option
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link

set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -I%SRC_ROOT% -nostdlib -c
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

if not exist %BUILD% mkdir %BUILD%

echo === Assembling text/entry.s ===
%CC% %ASFLAGS% %TEXT%\entry.s -o %BUILD%\text_entry.o
if errorlevel 1 exit /b 1

echo === Compiling text_jp2chs.c (jp2chs 全面接管引擎) ===
%CC% %CFLAGS% %SRC_ROOT%\text_jp2chs.c -o %BUILD%\text_jp2chs.o
if errorlevel 1 exit /b 1

echo === Linking game.elf ===
@rem text/entry.o 必须第一个：main.asm 的 JP2CHS_Entry 标签 = GameBinAddresses
@rem = game.bin 起点 = EngineEntry 跳板（r0=win 直进 ProcessCurrentChar_C）。
%CC% %LDFLAGS% -o %OUT%/game.elf ^
  %BUILD%/text_entry.o ^
  %BUILD%/text_jp2chs.o ^
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
set MPN_ADDR=0x08800000
set WTA_ADDR=0x08800000
set UPMN_ADDR=0x08800000
set DOMC_ADDR=0x08800000
set GGTPH_ADDR=0x08800000
for /f "tokens=1" %%a in ('findstr /R "MapName_DisplayCellLength$" %OUT%\game.map') do set MPN_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "WaitArrow_Prepare$" %OUT%\game.map') do set WTA_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "UnusedPrintMonName_Hook$" %OUT%\game.map') do set UPMN_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "DrawOptionMenuChoice_Hook$" %OUT%\game.map') do set DOMC_ADDR=%%a
for /f "tokens=1" %%a in ('findstr /R "GetGlyphTilePointers_Hook$" %OUT%\game.map') do set GGTPH_ADDR=%%a
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    echo MapName_DisplayCellLength               equ %MPN_ADDR%
    echo WaitArrow_Prepare                       equ %WTA_ADDR%
    echo UnusedPrintMonName_Hook                 equ %UPMN_ADDR%
    echo DrawOptionMenuChoice_Hook               equ %DOMC_ADDR%
    echo GetGlyphTilePointers_Hook               equ %GGTPH_ADDR%
)

echo Build OK: %OUT%\game.bin
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
