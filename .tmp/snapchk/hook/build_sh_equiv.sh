#!/usr/bin/env bash
# build_sh_equiv.sh — build.bat 的等价 bash 版本（cmd.exe 被安全策略拦截时使用）。
# 参数与 build.bat 完全一致；不引入任何新编译选项。
# 用法： bash build_sh_equiv.sh
set -e
cd "$(dirname "$0")"

CC=arm-none-eabi-gcc
OBJCOPY=arm-none-eabi-objcopy

SRC_ROOT=src
TEXT=$SRC_ROOT/text
MAP_POPUP=$SRC_ROOT/map_name_popup
BATTLE=$SRC_ROOT/battle
POKEDEX=$SRC_ROOT/pokedex
OPTION=$SRC_ROOT/option
OUT=out
BUILD=$OUT/obj
LINK_DIR=link

CFLAGS="-mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I$SRC_ROOT -nostdlib -c"
ASFLAGS="-mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c"
LDFLAGS="-mthumb -mcpu=arm7tdmi -nostdlib -T $LINK_DIR/game.ld -Wl,-Map=$OUT/game.map"

rm -rf "$BUILD"; mkdir -p "$BUILD"

$CC $ASFLAGS $TEXT/entry.s                       -o $BUILD/text_entry.o
$CC $CFLAGS  $TEXT/InitTextPrinter_hook.c        -o $BUILD/InitTextPrinter_hook.o
$CC $CFLAGS  $TEXT/PrintNextChar_hook.c          -o $BUILD/PrintNextChar_hook.o
$CC $CFLAGS  $TEXT/blend_glyph.c                 -o $BUILD/blend_glyph.o
$CC $CFLAGS  $TEXT/tile_alloc.c                  -o $BUILD/tile_alloc.o
$CC $CFLAGS  $TEXT/chs_canvas.c                  -o $BUILD/chs_canvas.o
$CC $CFLAGS  $TEXT/diag_log.c                    -o $BUILD/diag_log.o
$CC $CFLAGS  $TEXT/chinese_glyph.c               -o $BUILD/chinese_glyph.o
$CC $CFLAGS  $TEXT/text_translater.c             -o $BUILD/text_translater.o
$CC $CFLAGS  $TEXT/scene_cfg.c                   -o $BUILD/scene_cfg.o
$CC $ASFLAGS $MAP_POPUP/entry.s                  -o $BUILD/MapNamePopup_entry.o
$CC $CFLAGS  $MAP_POPUP/MapNamePopup_hook.c      -o $BUILD/MapNamePopup_hook.o
$CC $ASFLAGS $BATTLE/UpdateNickInHealthbox_entry.s -o $BUILD/UpdateNickInHealthbox_entry.o
$CC $CFLAGS  $BATTLE/UpdateNickInHealthbox_hook.c  -o $BUILD/UpdateNickInHealthbox_hook.o
$CC $ASFLAGS $POKEDEX/UnusedPrintMonName_entry.s -o $BUILD/UnusedPrintMonName_entry.o
$CC $CFLAGS  $POKEDEX/UnusedPrintMonName_hook.c  -o $BUILD/UnusedPrintMonName_hook.o
$CC $ASFLAGS $OPTION/DrawOptionMenuChoice_entry.s -o $BUILD/DrawOptionMenuChoice_entry.o
$CC $CFLAGS  $OPTION/DrawOptionMenuChoice_hook.c  -o $BUILD/DrawOptionMenuChoice_hook.o

$CC $LDFLAGS -o $OUT/game.elf \
  $BUILD/text_entry.o \
  $BUILD/InitTextPrinter_hook.o \
  $BUILD/PrintNextChar_hook.o \
  $BUILD/blend_glyph.o \
  $BUILD/tile_alloc.o \
  $BUILD/chs_canvas.o \
  $BUILD/diag_log.o \
  $BUILD/chinese_glyph.o \
  $BUILD/text_translater.o \
  $BUILD/scene_cfg.o \
  $BUILD/MapNamePopup_entry.o \
  $BUILD/MapNamePopup_hook.o \
  $BUILD/UpdateNickInHealthbox_entry.o \
  $BUILD/UpdateNickInHealthbox_hook.o \
  $BUILD/UnusedPrintMonName_entry.o \
  $BUILD/UnusedPrintMonName_hook.o \
  $BUILD/DrawOptionMenuChoice_entry.o \
  $BUILD/DrawOptionMenuChoice_hook.o

$OBJCOPY -O binary $OUT/game.elf $OUT/game.bin

{
  echo "; Auto-generated from out/game.map - do not edit"
  for S in MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook \
           UpdateNickInHealthbox_Hook UpdateNickInHealthbox_Hook_Other UpdateTilemap_Origin \
           InitTextPrinter_Hook SetWindowTileCache_Hook; do
    A=$(tr -d '\r' < $OUT/game.map | grep -E "(^|[[:space:]])$S\$" | awk '{print $1}' | head -1)
    [ -n "$A" ] && echo "$S equ $A"
  done
} > $OUT/game_syms.asm

echo "Build OK: $OUT/game.bin"
wc -c < $OUT/game.bin
cat $OUT/game_syms.asm
