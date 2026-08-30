# -*- coding: utf-8 -*-
"""诊断：设置菜单标签列的汉字，是否都登记在 PTR 固定槽表（chs_slots.inc）里。

PTR 区（左 16px）只在 `chs_ptr_base()` 查到槽时才生效；查不到就静默回退 DYN
（12px，与右侧候选列一样）⇒ 屏幕上表现为"左 16 右 12"失效且不报错。
本脚本从成品 ROM 里把标签短语流解出字形号，与槽表逐条比对。

布局常量与 hook 侧保持一致（game.h / text_translater.c）：
  ADDR_PHRASE_OFFSETS 0x08810000  → ROM 文件偏移 = addr - 0x08000000
  ADDR_PHRASE_TABLE   0x08820000
  pack_glyph_index(lead, trail)

用法（仓库根）：
  python scripts/check_opt_slots.py [ROM 路径]
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(ROOT, "roms", "outputs",
                           "POKEMON_RUBY_AXVJ00_translated.gba")
SLOTS_INC = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook",
                         "src", "text", "chs_slots.inc")

ROM_BASE = 0x08000000
ADDR_PHRASE_OFFSETS = 0x08810000
ADDR_PHRASE_TABLE = 0x08820000
SENTINEL = 0x01000000

CHS_ESCAPE = 0xF9

# 设置菜单 7 行标签：短语码（translate.build.json 的 phrase_code）→ 译文
# 数据来源：work/POKEMON_RUBY_AXVJ00/translate.build.json 的 UI界面 模块
LABELS = [
    (4821, "对话速度"),
    (4823, "战斗动画"),
    (4820, "对战规则"),
    (4741, "声音"),
    (4825, "按键模式"),
    (4744, "窗口"),
    (4739, "关闭"),
]


def pack_glyph_index(lead, trail):
    """与 text_translater.c pack_glyph_index 同式。"""
    idx = lead
    if idx >= 6:
        if idx >= 0x1B:
            idx -= 1
        idx -= 1
    idx -= 1
    return (idx << 8) | trail


def read_slots(path):
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]{4})u,\s*0x([0-9A-Fa-f]{4})u\s*\}")
    return [int(g, 16) for g, _s in pat.findall(txt)]


def phrase_stream(rom, code):
    off_offs = ADDR_PHRASE_OFFSETS - ROM_BASE
    off_tbl = ADDR_PHRASE_TABLE - ROM_BASE
    off = struct.unpack_from("<I", rom, off_offs + code * 4)[0]
    if off >= SENTINEL:
        return None
    start = off_tbl + off
    end = rom.index(b"\xff", start)
    return rom[start:end]


def decode(stream):
    """解短语流：F9 00 ll tt → 字形号；其余按原生/控制字节跳过。"""
    out = []
    i = 0
    while i < len(stream):
        b = stream[i]
        if b == CHS_ESCAPE and i + 3 < len(stream) and stream[i + 1] == 0x00:
            out.append(pack_glyph_index(stream[i + 2], stream[i + 3]))
            i += 4
        else:
            i += 1
    return out


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROM
    rom = open(rom_path, "rb").read()
    slots = set(read_slots(SLOTS_INC))

    print("ROM        : %s (%d B)" % (rom_path, len(rom)))
    print("槽表汉字   : %d 个，范围 0x%04X..0x%04X"
          % (len(slots), min(slots), max(slots)) if slots else "槽表为空")
    print("")
    print("%-8s %-10s %-28s %s" % ("短语码", "译文", "字形号", "命中的槽"))
    print("-" * 78)

    missing = []
    total = 0
    for code, zh in LABELS:
        st = phrase_stream(rom, code)
        if st is None:
            print("%-8d %-10s  <短语流缺失>" % (code, zh))
            continue
        gs = decode(st)
        total += len(gs)
        hit = []
        for g in gs:
            if g in slots:
                hit.append("0x%04X" % g)
            else:
                hit.append("0x%04X✗缺失" % g)
                missing.append((zh, g))
        print("%-8d %-10s %-28s %s"
              % (code, zh, " ".join("0x%04X" % g for g in gs), " ".join(hit)))

    print("-" * 78)
    print("标签汉字共 %d 个，缺失 %d 个" % (total, len(missing)))
    if missing:
        print("")
        print("⚠ 以下汉字查不到固定槽 ⇒ PTR 静默回退 DYN ⇒ 标签列不是 16px：")
        for zh, g in missing:
            print("   %s  0x%04X" % (zh, g))
        print("")
        print("修法：把这批字形号补进 %s 的汉字集合，重跑" % os.path.basename(SLOTS_INC))
        print("      python scripts/gen_tm1_slots.py")
        print("     （该脚本从 chs_slots.inc 自身读汉字集合，只重排槽位，不采集汉字）")
        return 1
    print("✓ 全部命中固定槽，PTR 区应当生效（左 16px）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
