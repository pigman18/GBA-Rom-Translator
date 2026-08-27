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
MAP_POPUP := $(SRC_ROOT)/map_name_popup
BATTLE   := $(SRC_ROOT)/battle
POKEDEX  := $(SRC_ROOT)/pokedex
OPTION   := $(SRC_ROOT)/option
OUT      := out
BUILD    := $(OUT)/obj

CFLAGS  := -mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -Iinclude -I$(SRC_ROOT) -nostdlib -c
ASFLAGS := -mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
LDFLAGS := -mthumb -mcpu=arm7tdmi -nostdlib -T link/game.ld -Wl,-Map=$(OUT)/game.map

OBJS := \
	$(BUILD)/text_entry.o \
	$(BUILD)/text.o \
	$(BUILD)/chinese_text.o \
	$(BUILD)/text_translate.o \
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

# src/entry.s 是引擎入口跳板，链接必须排第一：
# main.asm 的 JP2CHS_Entry 标签 = GameBinAddresses = game.bin 起点（EngineEntry）。
$(BUILD)/text_entry.o: $(SRC_ROOT)/entry.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/text.o: $(SRC_ROOT)/text.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/chinese_text.o: $(SRC_ROOT)/chinese_text.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/text_translate.o: $(SRC_ROOT)/text_translate.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

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
