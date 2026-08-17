# AXVJ hook → out/game.bin (VMA 0x08800000)
# Prefer build.bat on Windows.

PREFIX   ?= arm-none-eabi-
CC       := $(PREFIX)gcc
OBJCOPY  := $(PREFIX)objcopy

SRC_ROOT := src
TEXT     := $(SRC_ROOT)/text
BATTLE   := $(SRC_ROOT)/battle
POKEDEX  := $(SRC_ROOT)/pokedex
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
	$(BUILD)/UpdateNickInHealthbox_hook.o \
	$(BUILD)/UnusedPrintMonName_entry.o \
	$(BUILD)/UnusedPrintMonName_hook.o

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

$(BUILD)/%.o: $(POKEDEX)/%.s | $(BUILD)
	$(CC) $(ASFLAGS) $< -o $@

$(BUILD)/%.o: $(POKEDEX)/%.c | $(BUILD)
	$(CC) $(CFLAGS) $< -o $@

$(OUT)/game.elf: $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)

$(OUT)/game.bin: $(OUT)/game.elf
	$(OBJCOPY) -O binary $< $@

$(OUT)/game_syms.asm: $(OUT)/game.map
	@GSW=$$(grep -E 'GetStringWidthChinese$$' $(OUT)/game.map | awk '{print $$1}'); \
	MPN=$$(grep -E 'MapName_DisplayCellLength$$' $(OUT)/game.map | awk '{print $$1}'); \
	WTA=$$(grep -E 'WaitArrow_Prepare$$' $(OUT)/game.map | awk '{print $$1}'); \
	UPMN=$$(grep -E 'UnusedPrintMonName_Hook$$' $(OUT)/game.map | awk '{print $$1}'); \
	printf '; Auto-generated from out/game.map - do not edit\nGetStringWidthChinese                   equ %s\nMapName_DisplayCellLength               equ %s\nWaitArrow_Prepare                       equ %s\nUnusedPrintMonName_Hook                 equ %s\n' "$${GSW:-0x08800000}" "$${MPN:-0x08800000}" "$${WTA:-0x08800000}" "$${UPMN:-0x08800000}" > $@

clean:
	rm -rf $(OUT)/obj $(OUT)/game.elf $(OUT)/game.bin $(OUT)/game.map $(OUT)/game_syms.asm
