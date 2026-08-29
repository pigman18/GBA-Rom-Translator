# -*- coding: utf-8 -*-
"""校验「成品 ROM 里的 hook 是否与刚编出来的 game.bin 一致」。

为什么需要它
------------
2026-08-29 排查设置菜单时，一度以为"源码全对但运行不对"，怀疑 text_scene
的布局对设置菜单空转。最后的真相是两类问题混在一起：
  · 有时是 ROM 里打的确实是旧 game.bin（打完必须验一次）
  · 有时是代码本身的 BUG
先跑本脚本排除第一类，再谈第二类 —— 否则会在错误的方向上打转几小时。

用法（仓库根）::
    python scripts/check_rom_hook.py [ROM 路径, 可多个]

判定标准：game.bin 的**全部字节**必须逐字节出现在 ROM 中。
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "configs", "POKEMON_RUBY_AXVJ00", "hook")
GAME_BIN = os.path.join(HOOK, "out", "game.bin")
TEXT_DIR = os.path.join(HOOK, "src", "text")

MODES = {0: "PARTITION", 1: "GRID", 2: "PTR", 3: "MIX"}

# 与 text_scene.c kOptGlyphAvoid 一致（各占 2 tile：t 与 t+1）
GLYPH_AVOID = [
    0x001, 0x021, 0x031, 0x06F, 0x077, 0x08B, 0x0FF,
    0x143, 0x145, 0x147, 0x149, 0x14B, 0x14D, 0x14F,
    0x151, 0x153, 0x159, 0x15D, 0x171, 0x18D, 0x199,
    0x1B7, 0x1BF, 0x1C3, 0x1DF, 0x1E1,
]


def parse_inc(path):
    txt = open(path, encoding="utf-8").read()
    pat = re.compile(r"\{\s*0x([0-9A-Fa-f]{4})u,\s*0x([0-9A-Fa-f]{4})u\s*\}")
    return [(int(g, 16), int(s, 16)) for g, s in pat.findall(txt)]


def find_mode(b):
    """在 game.bin 里定位 kOptWindow 的 mode 字段（tpl 0x081BB874 之后）。"""
    pat = struct.pack("<I", 0x081BB874)
    for i in range(len(b) - 4):
        if b[i:i + 4] == pat:
            m = b[i + 4]
            # mode 只可能是 0..3（PARTITION/GRID/PTR/MIX），其后是 3 字节对齐填充
            if m <= 3 and b[i + 5:i + 8] == b"\x00\x00\x00":
                return i, m
    return None, None


def main():
    roms = sys.argv[1:] or [
        os.path.join(ROOT, "roms", "outputs",
                     "POKEMON_RUBY_AXVJ00_translated.gba"),
    ]

    b = open(GAME_BIN, "rb").read()
    print("game.bin  %d 字节" % len(b))

    off, mode = find_mode(b)
    print("  kOptWindow.mode @ 0x%X = %s"
          % (off, MODES.get(mode, mode)) if off else "  ⚠ 未定位到 mode")
    if mode == 3:
        print("  （MIX：分区规则在 text_scene.c 的 kOptZones）")

    nrm = parse_inc(os.path.join(TEXT_DIR, "chs_slots.inc"))
    sel_path = os.path.join(TEXT_DIR, "chs_slots_sel.inc")
    sel = parse_inc(sel_path) if os.path.exists(sel_path) else []

    def table_at(pairs):
        sig = struct.pack("<%dH" % (len(pairs) * 2),
                          *[v for p in pairs for v in p])
        return b.find(sig)

    print("  kOptChsSlots    @ 0x%X (%d 条)" % (table_at(nrm[:6]), len(nrm))
          if table_at(nrm[:6]) >= 0 else "  ⚠ kOptChsSlots 缺失")
    if sel:
        print("  kOptChsSelSlots @ 0x%X (%d 条)" % (table_at(sel[:6]), len(sel))
              if table_at(sel[:6]) >= 0 else "  ⚠ kOptChsSelSlots 缺失")

        # 空表 = 1 条哨兵（glyph 0xFFFF），这是 MIX 模式的预期状态：
        # PTR 段（标签列）不吃高亮，DYN 段靠重画出选中色，都不需要红字镜像槽。
        if len(sel) == 1 and sel[0][0] == 0xFFFF:
            print("  选中槽: 空表（MIX 模式预期：标签不吃高亮、DYN 靠重画出红字）")
        else:
            blocked = set()
            for t in GLYPH_AVOID:
                blocked.add(t)
                blocked.add(t + 1)
            for _g, s in nrm:
                blocked |= {s + k for k in range(4)}
            bad = [(s, sorted({s + k for k in range(4)} & blocked))
                   for _g, s in sel if {s + k for k in range(4)} & blocked]
            ok_order = [g for g, _ in nrm] == [g for g, _ in sel]
            print("  选中槽: 顺序一致=%s 冲突=%s tile %d..%d"
                  % (ok_order, bad if bad else "无",
                     min(s for _, s in sel), max(s for _, s in sel) + 3))

    rc = 0
    for rp in roms:
        if not os.path.exists(rp):
            print("%s: 不存在" % rp)
            continue
        r = open(rp, "rb").read()
        k = r.find(b[:64])
        same = k >= 0 and r[k:k + len(b)] == b
        print("%s\n  game.bin @ %s  逐字节一致 = %s"
              % (os.path.basename(rp), hex(k) if k >= 0 else "未找到", same))
        if not same:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
