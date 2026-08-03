# src/ → out/game.bin（产物只进 out/）
PREFIX   ?= arm-none-eabi-
CC       := $(PREFIX)gcc
AS       := $(PREFIX)gcc
OBJCOPY  := $(PREFIX)objcopy

SRC_ROOT := src
PNC      := $(SRC_ROOT)/text/PrintNextChar
NICK     := $(SRC_ROOT)/battle/UpdateNickInHealthbox
OUT      := out
BUILD    := $(OUT)/obj
LINK_DIR := link

OBJS     := $(BUILD)/entry.o \
            $(BUILD)/print_next_char.o \
            $(BUILD)/draw_glyph.o \
            $(BUILD)/draw_scene.o \
            $(BUILD)/get_string_width.o \
            $(BUILD)/nick_entry.o \
            $(BUILD)/update_nick_in_healthbox.o

CFLAGS   := -mthumb -mcpu=arm7tdmi -ffreestanding -O2 -fno-builtin \
            -Wall -Wextra -I$(SRC_ROOT) -nostdlib
ASFLAGS  := -mthumb -mcpu=arm7tdmi -ffreestanding -x assembler-with-cpp
LDFLAGS  := -mthumb -mcpu=arm7tdmi -nostdlib \
            -T $(LINK_DIR)/game.ld -Wl,-Map=$(OUT)/game.map

.PHONY: all clean

all: $(OUT)/game.bin

$(OUT) $(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/entry.o: $(PNC)/entry.s | $(BUILD)
	$(AS) $(ASFLAGS) -c $< -o $@

$(BUILD)/print_next_char.o: $(PNC)/print_next_char.c $(SRC_ROOT)/game.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/draw_glyph.o: $(PNC)/draw_glyph.c $(SRC_ROOT)/game.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/draw_scene.o: $(PNC)/draw_scene.c $(SRC_ROOT)/game.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/get_string_width.o: $(PNC)/get_string_width.c $(SRC_ROOT)/game.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/nick_entry.o: $(NICK)/entry.s | $(BUILD)
	$(AS) $(ASFLAGS) -c $< -o $@

$(BUILD)/update_nick_in_healthbox.o: $(NICK)/update_nick_in_healthbox.c $(SRC_ROOT)/game.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(OUT)/game.elf: $(OBJS) $(LINK_DIR)/game.ld | $(OUT)
	$(CC) $(LDFLAGS) -o $@ $(OBJS)

$(OUT)/game.bin: $(OUT)/game.elf
	$(OBJCOPY) -O binary $< $@

clean:
	rm -rf $(OUT)
