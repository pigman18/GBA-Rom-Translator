# AXVJ hook → out/game.bin (VMA 0x08800000)
# Prefer build.bat on Windows.

PREFIX   ?= arm-none-eabi-
CC       := $(PREFIX)gcc
OBJCOPY  := $(PREFIX)objcopy

SRC_ROOT := src
TEXT     := $(SRC_ROOT)/text
BATTLE   := $(SRC_ROOT)/battle
OUT      := out
BUILD    := $(OUT)/obj

CFLAGS  := -mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin -Wall -I$(SRC_ROOT) -nostdlib -c
ASFLAGS := -mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp -c
LDFLAGS := -mthumb -mcpu=arm7tdmi -nostdlib -T link/game.ld -Wl,-Map=$(OUT)/game.map

OBJS := \
	$(BUILD)/PrintNextChar_entry.o \
	$(BUILD)/PrintNextChar_hook.o \
	$(BUILD)/DrawGlyphTiles_hook.o \
	$(BUILD)/DrawGlyphTiles_scene.o \
	$(BUILD)/GetStringWidth_hook.o \
	$(BUILD)/GetGlyphWidth_hook.o \
	$(BUILD)/UpdateNickInHealthbox_entry.o \
	$(BUILD)/UpdateNickInHealthbox_hook.o

.PHONY: all clean

all: $(OUT)/game.bin $(OUT)/game_syms.asm

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: $(TEXT)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(TEXT)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(BUILD)/%.o: $(BATTLE)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(BATTLE)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(OUT)/game.elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)

$(OUT)/game.bin: $(OUT)/game.elf
	$(OBJCOPY) -O binary $< $@

$(OUT)/game_syms.asm: $(OUT)/game.map
	@GSW=$$(grep -E 'GetStringWidthChinese$$' $(OUT)/game.map | awk '{print $$1}'); \
	printf '; Auto-generated from out/game.map - do not edit\nGetStringWidthChinese                   equ %s\n' "$${GSW:-0x08800000}" > $@

clean:
	rm -rf $(OUT)/obj $(OUT)/game.elf $(OUT)/game.bin $(OUT)/game.map $(OUT)/game_syms.asm
