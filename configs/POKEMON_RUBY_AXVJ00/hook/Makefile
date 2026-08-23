# AXVJ hook → out/game.bin (VMA 0x08800000)
# Windows: build.bat
# WSL:     scripts/wsl-interop-setup.sh 一次后
#          PATH="$REPO/tools/wsl-bin:$PATH" make
#          （tools/wsl-bin 内是 Windows 工具链包装器，含 armips）
# 注意: out/game.map 由 Windows ld.exe 写出为 CRLF，game_syms 配方已剥 \r。

PREFIX   ?= arm-none-eabi-
CC       := $(PREFIX)gcc
OBJCOPY  := $(PREFIX)objcopy

SRC_ROOT := src
TEXT     := $(SRC_ROOT)/text
BATTLE   := $(SRC_ROOT)/battle
POKEDEX  := $(SRC_ROOT)/pokedex
OPTION   := $(SRC_ROOT)/option
OUT      := out
BUILD    := $(OUT)/obj

CFLAGS  := -mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -I$(SRC_ROOT) -nostdlib -c
ASFLAGS := -mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
LDFLAGS := -mthumb -mcpu=arm7tdmi -nostdlib -T link/game.ld -Wl,-Map=$(OUT)/game.map

OBJS := \
	$(BUILD)/text_entry.o \
	$(BUILD)/text_jp2chs.o \
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

# text/entry.s 是跳板合集，链接必须排第一：
# main.asm 的 JP2CHS_Entry 标签 = GameBinAddresses = game.bin 起点（EngineEntry）。
$(BUILD)/text_entry.o: $(TEXT)/entry.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/text_jp2chs.o: $(SRC_ROOT)/text_jp2chs.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/%.o: $(TEXT)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(TEXT)/%.c | $(BUILD)
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

# 与 build.bat 对齐：5 个符号（含 MapName_DisplayCellLength，地名居中钩跳板）
$(OUT)/game_syms.asm: $(OUT)/game.map
	@MPN=$$(tr -d '\r' < $(OUT)/game.map | grep -E 'MapName_DisplayCellLength$$' | awk '{print $$1}'); \
	WTA=$$(tr -d '\r' < $(OUT)/game.map | grep -E 'WaitArrow_Prepare$$' | awk '{print $$1}'); \
	UPMN=$$(tr -d '\r' < $(OUT)/game.map | grep -E 'UnusedPrintMonName_Hook$$' | awk '{print $$1}'); \
	DOMC=$$(tr -d '\r' < $(OUT)/game.map | grep -E 'DrawOptionMenuChoice_Hook$$' | awk '{print $$1}'); \
	GGTPH=$$(tr -d '\r' < $(OUT)/game.map | grep -E 'GetGlyphTilePointers_Hook$$' | awk '{print $$1}'); \
	printf '; Auto-generated from out/game.map - do not edit\nMapName_DisplayCellLength               equ %s\nWaitArrow_Prepare                       equ %s\nUnusedPrintMonName_Hook                 equ %s\nDrawOptionMenuChoice_Hook               equ %s\nGetGlyphTilePointers_Hook               equ %s\n' "$${MPN:-0x08800000}" "$${WTA:-0x08800000}" "$${UPMN:-0x08800000}" "$${DOMC:-0x08800000}" "$${GGTPH:-0x08800000}" > $@

clean:
	rm -rf $(OUT)/obj $(OUT)/game.elf $(OUT)/game.bin $(OUT)/game.map $(OUT)/game_syms.asm
