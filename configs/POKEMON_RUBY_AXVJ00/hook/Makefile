# AXVJ hook → out/game.bin (VMA 0x08800000)
#
# Windows 权威构建：build.bat（本 Makefile 与之逐项对齐，2026-11-02 校正）
# WSL:  scripts/wsl-interop-setup.sh 一次后
#       PATH="$REPO/tools/wsl-bin:$PATH" make
#       （tools/wsl-bin 内是 Windows 工具链包装器）
# 注意: out/game.map 由 Windows ld.exe 写出为 CRLF，game_syms 配方已剥 \r。

PREFIX   ?= arm-none-eabi-
CC       := $(PREFIX)gcc
OBJCOPY  := $(PREFIX)objcopy

SRC_ROOT := src
TEXT     := $(SRC_ROOT)/text
MAP_POPUP := $(SRC_ROOT)/map_name_popup
BATTLE   := $(SRC_ROOT)/battle
POKEDEX  := $(SRC_ROOT)/pokedex
OPTION   := $(SRC_ROOT)/option
OUT      := out
BUILD    := $(OUT)/obj
REF      := reference

CFLAGS  := -mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I$(SRC_ROOT) -nostdlib -c
ASFLAGS := -mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
LDFLAGS := -mthumb -mcpu=arm7tdmi -nostdlib -T link/game.ld -Wl,-Map=$(OUT)/game.map

# 顺序即链接顺序；text_entry.o（src/text/entry.s 的 EngineEntry）必须排第一。
OBJS := \
	$(BUILD)/text_entry.o \
	$(BUILD)/PrintNextChar_hook.o \
	$(BUILD)/MapNamePopup_entry.o \
	$(BUILD)/MapNamePopup_hook.o \
	$(BUILD)/UpdateNickInHealthbox_entry.o \
	$(BUILD)/UpdateNickInHealthbox_hook.o \
	$(BUILD)/UnusedPrintMonName_entry.o \
	$(BUILD)/UnusedPrintMonName_hook.o \
	$(BUILD)/DrawOptionMenuChoice_entry.o \
	$(BUILD)/DrawOptionMenuChoice_hook.o

.PHONY: all clean

all: $(OUT)/game.bin $(OUT)/game_syms.asm

$(BUILD):
	mkdir -p $(BUILD)

# --- 文本引擎（src/text/）---
# entry.s 是引擎入口跳板，链接必须排第一：
# main.asm 的 JP2CHS_Entry 标签 = GameBinAddresses = game.bin 起点（EngineEntry）。
$(BUILD)/text_entry.o: $(TEXT)/entry.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/PrintNextChar_hook.o: $(TEXT)/PrintNextChar_hook.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

# --- 页表（构建期数据，不进 gcc）---
# src/meowth/text_page.py → gen/page_data.asm + page_data.bin，由 armips
# 按固定 VMA .incbin 装入 ROM 扩展区；link/game.ld 的 ROM LENGTH 仅 0x10000，
# 不参与链接，C 侧用 text_page.h 的 PAGE_TABLE_VMA 常量只读访问（设计 §5.1 B）。

# --- 旧模块（已删除，勿复建）---
# reference/ 5 个 ref* 符号 2026-11-02 移除；
# text_render.c / text_scene.c / text_translter.c 2026-11-11 随串页重构删除，
# 运行时逻辑全部收进 PrintNextChar_hook.c（F7 00 统一协议、零运行时状态）。

# --- 域钩（map_name_popup / battle / pokedex / option）---
$(BUILD)/MapNamePopup_entry.o: $(MAP_POPUP)/entry.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/MapNamePopup_hook.o: $(MAP_POPUP)/MapNamePopup_hook.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/%.o: $(BATTLE)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(BATTLE)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/%.o: $(POKEDEX)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(POKEDEX)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/%.o: $(OPTION)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(OPTION)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(OUT)/game.elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)

$(OUT)/game.bin: $(OUT)/game.elf
	$(OBJCOPY) -O binary $< $@

# game_syms 流式生成（与 build.bat 对齐）：符号表内联、无拷贝变量、无默认回填——
# 缺失符号该行不生成，armips 在使用处直接报错。
$(OUT)/game_syms.asm: $(OUT)/game.map
	@printf '; Auto-generated from out/game.map - do not edit\n' > $@; \
	for s in MapName_DisplayCellLength UnusedPrintMonName_Hook DrawOptionMenuChoice_Hook; do \
		addr=`tr -d '\r' < $(OUT)/game.map | grep -E "$$s$$" | awk '{print $$1}'`; \
		if [ -n "$$addr" ]; then printf '%s equ %s\n' "$$s" "$$addr" >> $@; fi; \
	done

clean:
	rm -rf $(OUT)/obj $(OUT)/game.elf $(OUT)/game.bin $(OUT)/game.map $(OUT)/game_syms.asm
