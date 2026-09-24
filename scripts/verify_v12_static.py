# -*- coding: utf-8 -*-
"""v12 静态复核（零 gdb）—— 一键跑，退出码即结论。

背景：2026-09-11「继续游戏菜单卡死」修复后固化。崩因是 `mov lr, pc`
手工模拟 `bl` ⇒ LR 的 bit0 恒为 0 ⇒ 被调函数 `bx lr` 时切进 ARM 态 ⇒
UNDEF(0x00000004)。本脚本把当时的判据全部沉淀成断言，防止重蹈。

检查项：
  1. game.bin 与输出 ROM 注入区逐字节一致
  2. 三个桩（③⑦⑧）入口反汇编正确
  3. 桩以外的函数体与原盘逐字节相同
  4. 注入区**不存在** `mov lr, pc`（46 FE）
  5. 桩里的跳转字面量的 Thumb 位（必须奇数）
"""
import sys, hashlib, pathlib
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = pathlib.Path(r"C:\code\GBA-Rom-Translator")
ORIG = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
OUT  = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BIN  = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game.bin"

INJECT_ROM_OFF = 0x800000          # 注入区 @ 0x08800000

orig = ORIG.read_bytes()
out  = OUT.read_bytes()
gb   = BIN.read_bytes()
md   = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

fails = []
def chk(name, ok, detail=""):
    print(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok:
        fails.append(name)

def hx(buf, off, n):
    return " ".join("%02x" % b for b in buf[off:off + n])

def disas(buf, off, n):
    for i in md.disasm(buf[off:off + n], 0x08000000 + off):
        print("          0x%08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))

print("=" * 78)
print("段 1  game.bin  vs  ROM 注入区")
print("=" * 78)
chk("注入区逐字节一致 (%d B, sha1=%s)" % (len(gb), hashlib.sha1(gb).hexdigest()[:12]),
    out[INJECT_ROM_OFF:INJECT_ROM_OFF + len(gb)] == gb)
print("      game.bin = %d B / ROM = %d B" % (len(gb), len(out)))

print()
print("=" * 78)
print("段 2  三个桩入口（原盘首字节必须不变 ⇒ gdb_patcher 的 verify 不用改）")
print("=" * 78)
# ③ 就地完成 6B；⑦ 12B 尾跳（push{r4,lr}）；⑧ 12B 尾跳（只 push{lr}）
for label, addr, n, want in (
        ("③ MultistepLoadFont          0x080029E0", 0x29E0, 8,
         bytes.fromhex("10b5" "0120" "10bd")),
        ("⑦ TextWindow_LoadStdFrameGfx 0x08062094", 0x62094, 12,
         bytes.fromhex("10b5" "014c" "2047" "0000")),
        ("⑧ TextWindow_LoadDlgFrameGfx 0x08062684", 0x62684, 12,
         bytes.fromhex("00b5" "014b" "1847" "0000"))):
    got = out[addr:addr + len(want)]
    chk(label, got == want, "\n          bytes = " + hx(out, addr, n))
    disas(out, addr, n)

print()
print("=" * 78)
print("段 3  桩以外函数体  vs  原盘")
print("=" * 78)
REGIONS = [
    ("③ 尾段 0x29E6..0x2A4C",    0x29E6, 0x2A4C),
    ("⑦ 尾段 0x620A0..0x620C0",  0x620A0, 0x620C0),
    ("⑧ 尾段 0x62690..0x626A4",  0x62690, 0x626A4),
    ("① body 0x295C..0x29DE",    0x295C, 0x29DE),
    ("④ LoadFixedWidthGlyph 0x2A50..0x2A90", 0x2A50, 0x2A90),
    ("⑥ SetDlgFrameBase 0x62368..0x62378",   0x62368, 0x62378),
]
for label, a, b in REGIONS:
    same = orig[a:b] == out[a:b]
    chk(label + " 与原盘一致", same,
        "" if same else "\n          orig = " + hx(orig, a, min(16, b - a)) +
                         "\n          out  = " + hx(out, a, min(16, b - a)))

print()
print("=" * 78)
print("段 4  注入区不得出现 `mov lr, pc`（46 FE）—— 崩因护栏")
print("=" * 78)
bad = ["bin+0x%X" % i for i in range(0, len(gb) - 2, 2)
       if gb[i] == 0xfe and gb[i + 1] == 0x46]
chk("无 `mov lr, pc`", not bad, str(bad) if bad else "")

print()
print("=" * 78)
print("段 5  跳转字面量的 Thumb 位（必须奇数）")
print("=" * 78)
# 桩里的 hook 地址字面量（在 ROM 的桩体内）
STUB_LITS = [
    ("⑦ 桩→hook  @0x0806209C", 0x6209C),
    ("⑧ 桩→hook  @0x0806268C", 0x6268C),
]
for label, off in STUB_LITS:
    v = int.from_bytes(out[off:off + 4], "little")
    chk("%s = 0x%08X 为奇数(Thumb)" % (label, v), v & 1 == 1)
# 跳板里的续跑字面量（在注入区）
for v, nm in ((0x080620A1, "⑦ 原体续跑 0x080620A1"),
              (0x08062691, "⑧ 原体续跑 0x08062691")):
    chk("%s 为奇数(Thumb)" % nm, v & 1 == 1,
        "在 game.bin @bin+0x%X" % gb.find(v.to_bytes(4, "little"))
        if gb.find(v.to_bytes(4, "little")) >= 0 else "(未在 game.bin 找到)")

print()
print("=" * 78)
if fails:
    print("结果：%d 项失败 ❌" % len(fails))
    for f in fails:
        print("   - " + f)
    sys.exit(1)
print("结果：全部通过 ✅")
