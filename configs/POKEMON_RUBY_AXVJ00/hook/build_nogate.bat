@echo off
setlocal
cd /d C:\code\GBA-Rom-Translator\configs\POKEMON_RUBY_AXVJ00\hook
set PREFIX=arm-none-eabi-
set CC=%PREFIX%gcc
set OBJCOPY=%PREFIX%objcopy
set SRC_ROOT=src
set MAP_POPUP=%SRC_ROOT%\map_name_popup
set BATTLE=%SRC_ROOT%\battle
set POKEDEX=%SRC_ROOT%\pokedex
set SUMMARY=%SRC_ROOT%\summary
set OPTION=%SRC_ROOT%\option
set POKENAV=%SRC_ROOT%\pokenav
set OUT=out
set BUILD=%OUT%\obj
set LINK_DIR=link
set CFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I%SRC_ROOT% -nostdlib -c %EXTRA_CFLAGS%
set ASFLAGS=-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
set LDFLAGS=-mthumb -mcpu=arm7tdmi -nostdlib -T %LINK_DIR%/game.ld -Wl,-Map=%OUT%/game.map

%CC% %ASFLAGS% %SRC_ROOT%\text\entry.s -o %BUILD%\text_entry.o || exit /b 1
%CC% %CFLAGS% %SRC_ROOT%\text\PrintNextChar_hook.c -o %BUILD%\PrintNextChar_hook.o || exit /b 1
%CC% %ASFLAGS% %MAP_POPUP%\entry.s -o %BUILD%\MapNamePopup_entry.o || exit /b 1
%CC% %CFLAGS% %MAP_POPUP%\MapNamePopup_hook.c -o %BUILD%\MapNamePopup_hook.o || exit /b 1
%CC% %ASFLAGS% %BATTLE%\UpdateNickInHealthbox_entry.s -o %BUILD%\UpdateNickInHealthbox_entry.o || exit /b 1
%CC% %ASFLAGS% %BATTLE%\NickSlot_entry.s -o %BUILD%\NickSlot_entry.o || exit /b 1


%CC% %CFLAGS% %BATTLE%\UpdateNickInHealthbox_hook.c -o %BUILD%\UpdateNickInHealthbox_hook.o || exit /b 1
%CC% %ASFLAGS% %POKEDEX%\UnusedPrintMonName_entry.s -o %BUILD%\UnusedPrintMonName_entry.o || exit /b 1
%CC% %CFLAGS% %POKEDEX%\UnusedPrintMonName_hook.c -o %BUILD%\UnusedPrintMonName_hook.o || exit /b 1
%CC% %ASFLAGS% %POKEDEX%\UnusedPrintDecimalNum_entry.s -o %BUILD%\UnusedPrintDecimalNum_entry.o || exit /b 1
%CC% %CFLAGS% %POKEDEX%\UnusedPrintDecimalNum_hook.c -o %BUILD%\UnusedPrintDecimalNum_hook.o || exit /b 1
%CC% %ASFLAGS% %SUMMARY%\SummaryScreen_PrintTrainerMemo_entry.s -o %BUILD%\SummaryScreen_PrintTrainerMemo_entry.o || exit /b 1
%CC% %CFLAGS% -O1 %SUMMARY%\SummaryScreen_PrintTrainerMemo_hook.c -o %BUILD%\SummaryScreen_PrintTrainerMemo_hook.o || exit /b 1
%CC% %ASFLAGS% %SUMMARY%\SummaryScreen_PrintNicknameGender_entry.s -o %BUILD%\SummaryScreen_PrintNicknameGender_entry.o || exit /b 1
%CC% %CFLAGS% %SUMMARY%\SummaryScreen_PrintNicknameGender_hook.c -o %BUILD%\SummaryScreen_PrintNicknameGender_hook.o || exit /b 1
%CC% %ASFLAGS% %OPTION%\DrawOptionMenuChoice_entry.s -o %BUILD%\DrawOptionMenuChoice_entry.o || exit /b 1
%CC% %CFLAGS% %OPTION%\DrawOptionMenuChoice_hook.c -o %BUILD%\DrawOptionMenuChoice_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_PrintMenuTip_entry.s -o %BUILD%\PokeNav_PrintMenuTip_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_PrintMenuTip_hook.c -o %BUILD%\PokeNav_PrintMenuTip_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_FormatListLine_entry.s -o %BUILD%\PokeNav_TrainerEye_FormatListLine_entry.o || exit /b 1
%CC% %CFLAGS% -O1 %POKENAV%\PokeNav_TrainerEye_FormatListLine_hook.c -o %BUILD%\PokeNav_TrainerEye_FormatListLine_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_DetailEnter_entry.s -o %BUILD%\PokeNav_TrainerEye_DetailEnter_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_TrainerEye_DetailEnter_hook.c -o %BUILD%\PokeNav_TrainerEye_DetailEnter_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_PrintTitle_entry.s -o %BUILD%\PokeNav_TrainerEye_PrintTitle_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_TrainerEye_PrintTitle_hook.c -o %BUILD%\PokeNav_TrainerEye_PrintTitle_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_TitleBlit_entry.s -o %BUILD%\PokeNav_TrainerEye_TitleBlit_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_TrainerEye_TitleBlit_hook.c -o %BUILD%\PokeNav_TrainerEye_TitleBlit_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_PrintTitleSprite_entry.s -o %BUILD%\PokeNav_TrainerEye_PrintTitleSprite_entry.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_SkipListRow_entry.s -o %BUILD%\PokeNav_TrainerEye_SkipListRow_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_TrainerEye_SkipListRow_hook.c -o %BUILD%\PokeNav_TrainerEye_SkipListRow_hook.o || exit /b 1
%CC% %ASFLAGS% %POKENAV%\PokeNav_TrainerEye_ListRedraw_entry.s -o %BUILD%\PokeNav_TrainerEye_ListRedraw_entry.o || exit /b 1
%CC% %CFLAGS% %POKENAV%\PokeNav_TrainerEye_ListRedraw_hook.c -o %BUILD%\PokeNav_TrainerEye_ListRedraw_hook.o || exit /b 1


%CC% %LDFLAGS% -o %OUT%/game.elf %BUILD%/text_entry.o %BUILD%/PrintNextChar_hook.o %BUILD%/MapNamePopup_entry.o %BUILD%/MapNamePopup_hook.o %BUILD%/UpdateNickInHealthbox_entry.o %BUILD%/UpdateNickInHealthbox_hook.o %BUILD%/NickSlot_entry.o %BUILD%/UnusedPrintMonName_entry.o %BUILD%/UnusedPrintMonName_hook.o %BUILD%/UnusedPrintDecimalNum_entry.o %BUILD%/UnusedPrintDecimalNum_hook.o %BUILD%/SummaryScreen_PrintTrainerMemo_entry.o %BUILD%/SummaryScreen_PrintTrainerMemo_hook.o %BUILD%/SummaryScreen_PrintNicknameGender_entry.o %BUILD%/SummaryScreen_PrintNicknameGender_hook.o %BUILD%/DrawOptionMenuChoice_entry.o %BUILD%/DrawOptionMenuChoice_hook.o %BUILD%/PokeNav_PrintMenuTip_entry.o %BUILD%/PokeNav_PrintMenuTip_hook.o %BUILD%/PokeNav_TrainerEye_FormatListLine_entry.o %BUILD%/PokeNav_TrainerEye_FormatListLine_hook.o %BUILD%/PokeNav_TrainerEye_DetailEnter_entry.o %BUILD%/PokeNav_TrainerEye_DetailEnter_hook.o %BUILD%/PokeNav_TrainerEye_PrintTitle_entry.o %BUILD%/PokeNav_TrainerEye_PrintTitle_hook.o %BUILD%/PokeNav_TrainerEye_TitleBlit_entry.o %BUILD%/PokeNav_TrainerEye_TitleBlit_hook.o %BUILD%/PokeNav_TrainerEye_PrintTitleSprite_entry.o %BUILD%/PokeNav_TrainerEye_SkipListRow_entry.o %BUILD%/PokeNav_TrainerEye_SkipListRow_hook.o %BUILD%/PokeNav_TrainerEye_ListRedraw_entry.o %BUILD%/PokeNav_TrainerEye_ListRedraw_hook.o || exit /b 1
%OBJCOPY% -O binary %OUT%/game.elf %OUT%/game.bin || exit /b 1

rem === 生成 game_syms.asm（与 build.bat 同白名单）===
> %OUT%\game_syms.asm (
    echo ; Auto-generated from out/game.map - do not edit
    for %%S in (MapName_DisplayCellLength UnusedPrintMonName_Hook UnusedPrintDecimalNum_Hook SummaryScreen_PrintTrainerMemo_Hook SummaryScreen_NameLayoutTiles_Hook DrawOptionMenuChoice_Hook PokeNav_PrintMenuTip_Hook PokeNav_TrainerEye_FormatListLine_Hook PokeNav_TrainerEye_DetailEnter_Hook PokeNav_TrainerEye_PrintTitle_Hook PokeNav_TrainerEye_PrintTitleSprite_Hook PokeNav_TrainerEye_TitleBlit_Hook PokeNav_TrainerEye_SkipListRow_Hook PokeNav_TrainerEye_ListRedraw_Hook NickSlot_Hook) do (
        for /f "tokens=1" %%a in ('findstr /R "%%S$" %OUT%\game.map') do @echo %%S equ %%a
    )
)

echo BUILD_OK
for %%F in (%OUT%\game.bin) do echo Size: %%~zF bytes
