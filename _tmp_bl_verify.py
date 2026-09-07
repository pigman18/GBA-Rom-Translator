# -*- coding: utf-8 -*-
"""一次性脚本：扫全 ROM 的 BL 调用点，验证调研文档§3 的咽喉点日版地址。"""
import sys

ROM = open("roms/origin/POKEMON_RUBY_AXVJ00.gba", "rb").read()
BASE = 0x08000000


def find_bl_callers(target):
    callers = []
    for i in range(0, len(ROM) - 4, 2):
        hw1 = ROM[i] | (ROM[i + 1] << 8)
        if (hw1 & 0xF800) != 0xF000:
            continue
        hw2 = ROM[i + 2] | (ROM[i + 3] << 8)
        if (hw2 & 0xF800) != 0xF800:
            continue
        off = ((hw1 & 0x7FF) << 12) | (hw2 & 0x7FF)
        if off & 0x200000:  # 22 位有符号
            off -= 0x400000
        pc = BASE + i + 4
        if pc + (off << 1) == target:
            callers.append(BASE + i)
    return callers


def func_start(addr):
    """向后扫到 push {...,lr}（0xB5xx）。"""
    off = addr - BASE
    for back in range(0, 0x600, 2):
        a = off - back
        if a < 0x100:
            break
        hw = ROM[a] | (ROM[a + 1] << 8)
        if (hw & 0xFF00) == 0xB500:
            return BASE + a
    return None


def prologue_ok(addr):
    """函数头特征：B5xx push（含 lr）。"""
    a = addr - BASE
    hw = ROM[a] | (ROM[a + 1] << 8)
    return (hw & 0xFF00) == 0xB500


TARGETS = [
    ("InitWindowTileData(yaml已实证)", 0x08002A50),
    ("doc:InitWindowTileData(疑错)", 0x08002D68),
    ("doc:Text_LoadWindowTemplate", 0x08002D4C),
    ("doc:TextWindow_SetBaseTileNum", 0x080625E0),
    ("doc:TextWindow_LoadStdFrameGraphics", 0x080625F4),
    ("doc:TextWindow_SetDlgFrameBaseTileNum", 0x080628B4),
    ("doc:Menu_DrawStdWindowFrame", 0x0806F224),
    ("doc:Menu_LoadStdFrameGraphics", 0x0806F504),
]

for name, tgt in TARGETS:
    cs = find_bl_callers(tgt)
    head = "push{lr}✓" if prologue_ok(tgt) else "非push头✗"
    print(f"{name} @0x{tgt:08X}: {head}  BL调用点 {len(cs)} 个")
    for c in cs[:12]:
        fs = func_start(c)
        print(f"   call@0x{c:08X}  函数头≈"
              + (f"0x{fs:08X}" if fs is not None else "?"))

# 0x08002D4C 附近反汇编概貌：看它是谁（是否调 0x08002A50 / CpuFastFill）
print("\n0x08002D4C 处 8 条半字:", ROM[0x2D4C:0x2D5C].hex(" "))
print("0x08002A50 处 8 条半字:", ROM[0x2A50:0x2A60].hex(" "))
