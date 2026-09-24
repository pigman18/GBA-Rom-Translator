"""端到端静态证明：Middle（领航员 9×11）字库链路逐位比对。

链路：Middle.bdf 真值 → pack_1bpp(9×11@row2, 13B/字) → ROM @0x09700000
      → chs_cell_from_1bpp(9, 11, row_off=2) 解回 → 与 BDF 真值逐位比

🔴 槽位映射（2026-09-20 实测得出，勿想当然）：
   C 侧读的是 `code & 0x1FFF`，但字库 bin 只按**有效 lead 页**压实存放
   （`font.config.json` 的 chinese_leads = [1..5][7..26][28..30]）。
   缺页（lead 0 / 6 / 27 …）不占空间 ⇒
       slot = code - 0x100 * (小于 lead 的无效 lead 个数)
   实测 5 字（文/道/号/路/名）与 14 字随机抽样全部命中。

用法：
  python scripts/verify_middle_e2e.py
"""
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BDF = ROOT / "fonts" / "default" / "Middle.bdf"
CMAP = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "charmap.txt"

ROM_BASE = 0x08000000
MIDDLE_ADDR = 0x09700000
W, H, X0, Y0 = 9, 11, 0, 2
STRIDE = (W * H + 7) // 8          # 13
VALID_LEADS = set(range(1, 6)) | set(range(7, 27)) | set(range(28, 31))
FIXED_CHARS = "文道号路名"


def load_bdf():
    txt = BDF.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(
            r"ENCODING\s+(\d+)\s*\n(?:.*?\n)*?BITMAP\s*\n((?:[0-9A-Fa-f]+\s*\n)+)ENDCHAR", txt):
        out[int(m.group(1))] = [int(l, 16) for l in m.group(2).split()]
    return out


def load_cmap():
    ent = []
    for line in CMAP.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            if len(v.strip()) == 1:
                ent.append((int(k, 16), v.strip()))
    return ent


def slot_of(code):
    lead = code >> 8
    skipped = sum(1 for L in range(0x40) if L < lead and L not in VALID_LEADS)
    return (code - 0x100 * skipped) & 0x1FFF


def pack(rows):
    out = bytearray(STRIDE)
    bit = 0
    for r in range(H):
        y = Y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        for c in range(W):
            if (row >> (15 - (X0 + c))) & 1:
                out[bit >> 3] |= 0x80 >> (bit & 7)
            bit += 1
    return bytes(out)


def unpack(buf):
    """复刻 chs_cell_from_1bpp：9 列 × 11 行连续位流（MSB-first，行间无填充）"""
    g = [[0] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            bit = r * W + c
            g[r][c] = (buf[bit >> 3] >> (7 - (bit & 7))) & 1
    return g


def bdf_ink(rows):
    g = [[0] * W for _ in range(H)]
    for r in range(H):
        y = Y0 + r
        row = rows[y] if 0 <= y < len(rows) else 0
        for c in range(W):
            g[r][c] = (row >> (15 - (X0 + c))) & 1
    return g


def main():
    bdf = load_bdf()
    ent = load_cmap()
    rom = ROM.read_bytes()
    off = MIDDLE_ADDR - ROM_BASE
    seg = rom[off:off + STRIDE * 7168]
    nz = sum(1 for b in seg if b)
    print("ROM   :", ROM.name)
    print("字库段: 0x%08X  %d B  非零 %.1f%%  按 %dB = %d 槽"
          % (MIDDLE_ADDR, len(seg), 100.0 * nz / len(seg), STRIDE, len(seg) // STRIDE))
    print("几何  : %dx%d @row%d stride=%dB row_off=%d" % (W, H, Y0, STRIDE, Y0))

    pool = [(c, ch) for c, ch in ent if ord(ch) in bdf and ch in FIXED_CHARS]
    rest = [(c, ch) for c, ch in ent if ord(ch) in bdf and ch not in FIXED_CHARS]
    random.seed(7)
    random.shuffle(rest)
    tests = pool + rest[:20]
    print("抽样  : %d 字（固定 %d + 随机 %d）\n" % (len(tests), len(pool), len(tests) - len(pool)))

    ok = fail = 0
    for code, ch in tests:
        slot = slot_of(code)
        raw = seg[slot * STRIDE: slot * STRIDE + STRIDE]
        got, want = unpack(raw), bdf_ink(bdf[ord(ch)])
        diff = sum(got[r][c] ^ want[r][c] for r in range(H) for c in range(W))
        if diff == 0:
            ok += 1
            print("  OK  %s  code=0x%04X slot=0x%04X" % (ch, code, slot))
        else:
            fail += 1
            print("  !!  %s  code=0x%04X slot=0x%04X  差异 %d" % (ch, code, slot, diff))
            if fail <= 1:
                for r in range(H):
                    print("        want " + "".join('#' if want[r][c] else '.'
                                                   for c in range(W)))
                    print("        got  " + "".join('#' if got[r][c] else '.'
                                                   for c in range(W)))
    print("\n逐位一致 %d / 不一致 %d" % (ok, fail))
    print("RESULT:", "PASS —— Middle 链路 BDF→ROM→解包 逐位一致"
          if fail == 0 and ok else "FAIL")
    return 0 if fail == 0 and ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
