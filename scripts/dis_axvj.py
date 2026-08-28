#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AXVJ00 日版 ROM Thumb 反汇编小工具（静态分析，不启动模拟器）。

用法:
    python scripts/dis_axvj.py 0x08002D50 0x0800338D ...
    python scripts/dis_axvj.py 0x08002D50 --len 0x120

特性:
  - 自动判定 Thumb 函数体边界（遇 bx lr / pop{pc} / b <外部> 即止）
  - 把已知地址替换成符号名（表在 SYMS / 由 game_addrs.asm 自动抽取）
  - 标注 BL 目标、literal pool 取值、call via register
"""
import sys, os, re, struct
import capstone

ROM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "roms", "origin", "POKEMON_RUBY_AXVJ00.gba")
BASE = 0x08000000

# ---- 已知符号（人工标定，见 docs/） ----
SYMS = {
    0x08002A50: "InitWindowTileData",
    0x08003520: "sub_8003520(tm0_core)",
    0x0800304C: "DrawInitialDownArrow",
    0x08003110: "HandleExtCtrlCode",
    0x080032F8: "PrintNextChar",
    0x0800338D: "FontFunc_tm2",
    0x08003495: "FontFunc_tm3",
    0x08003569: "FontFunc_tm0",
    0x08003585: "FontSub_f0_f3",
    0x080035A1: "FontSub_f1_f4",
    0x080035C9: "FontSub_f2_f5",
    0x080035E5: "FontSub_f6_braille",
    0x0800360C: "PrintGlyph_TextMode1",
    0x080036DC: "UpdateTilemap",
    0x08003730: "GetGlyphTilePointers",
    0x08003830: "CopyGlyph1bppTo4bpp",
    0x080038A0: "CopyGlyph2bppTo4bpp",
    0x08003BA8: "Text_ClearWindow",
    0x08003DAC: "DrawInitialDownArrow_Body",
    0x08003F4C: "DownArrowStub",
    0x081B12DC: "CALL_VIA_R2",
    0x081BB3AC: "FontFuncTable",
    0x081BB3BC: "FontSubTable",
    0x081B34A8: "FontType1Map",
}


def load_game_addrs(path):
    """从 hook/game_addrs.asm 抽取 `Name equ 0x...` 补进 SYMS。"""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*([A-Za-z_]\w*)\s+equ\s+(0x[0-9A-Fa-f]+)", line)
        if m:
            SYMS.setdefault(int(m.group(2), 16), m.group(1))


def rd32(d, addr):
    o = addr - BASE
    if 0 <= o + 4 <= len(d):
        return struct.unpack_from("<I", d, o)[0]
    return None


def sym(a):
    return SYMS.get(a)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ln = 0x200
    if "--len" in sys.argv:
        ln = int(sys.argv[sys.argv.index("--len") + 1], 16)

    load_game_addrs(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "configs", "POKEMON_RUBY_AXVJ00",
        "hook", "game_addrs.asm"))

    d = open(ROM, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True

    for a in args:
        addr = int(a, 16)
        start = addr & ~1
        off = start - BASE
        name = sym(start) or sym(start + 1) or "?"
        print("\n=== %s  %s  (Thumb, entry 0x%08X) ===" % (a, name, addr))
        code = d[off:off + ln]
        last = None
        for ins in md.disasm(code, start):
            last = ins
            txt = "%-4s %s" % (ins.mnemonic, ins.op_str)
            note = ""
            if ins.mnemonic in ("bl", "blx"):
                m = re.search(r"#?0x([0-9a-f]+)", ins.op_str)
                if m:
                    t = int(m.group(1), 16)
                    note = "  ; -> %s" % (sym(t) or sym(t + 1) or hex(t))
            elif ins.mnemonic == "ldr" and "[pc" in ins.op_str:
                m = re.search(r"#(-?0x[0-9a-f]+)", ins.op_str)
                if m:
                    lit = (ins.address + 4) & ~3
                    lit += int(m.group(1), 16)
                    v = rd32(d, lit)
                    if v is not None:
                        note = "  ; [0x%08X] = 0x%08X %s" % (
                            lit, v, sym(v) or sym(v & ~1) or "")
            print("  %08X: %-22s %-9s%s" % (ins.address, ins.bytes.hex(), txt, note))
            if ins.mnemonic == "bx" and ins.op_str == "lr":
                break
            if ins.mnemonic == "pop" and "pc" in ins.op_str:
                break
            if ins.mnemonic == "b" and ins.address > start + 4:
                break
        if last:
            print("  --- end 0x%08X  size=%d bytes" % (last.address, last.address - start))


if __name__ == "__main__":
    main()
