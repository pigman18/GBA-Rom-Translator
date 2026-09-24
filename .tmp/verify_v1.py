# -*- coding: utf-8 -*-
"""verify_v1.py — v1 8px 渲染层的静态判据（不开模拟器）。

  A. hook 区：ROM 内嵌 game.bin 与 out/game.bin 逐字节一致
  B. 订址桩：PrintNextChar@0x080032F8 被换成 ldr/bx → game.bin 首地址
  C. 跳板：EngineEntry / PrintNextChar_Origin / UpdateTilemap_Origin 的池字正确
  D. 不该被动的：InitTextPrinter@0x08002C68 保持原版（v1 不再 hook 它）
  E. 数据面：Middle 4bpp 字库 @0x09400000 与 work 产物一致；SLT2 表魔术字在
  F. origin-vs-output 差异分布（确认只动了预期区域）
"""
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "configs/POKEMON_RUBY_AXVJ00/hook"
ROM = Path(sys.argv[1]) if len(sys.argv) > 1 else (HOOK / "output.gba")
ORIG = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
FONTMID = HOOK / "../../../work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
ROMBASE = 0x08000000

fails = []


def off(addr):
    return addr - ROMBASE


def rd(rom, addr, n):
    return rom[off(addr):off(addr) + n]


def u32(b, i=0):
    return struct.unpack_from("<I", b, i)[0]


rom = ROM.read_bytes()
orig = ORIG.read_bytes()
hook = (HOOK / "out/game.bin").read_bytes()

print("ROM   = %s (%d B)" % (ROM, len(rom)))

# ---------------------------------------------------------------- A
seg = rd(rom, 0x08800000, len(hook))
ok = seg == hook
print("A. hook 区内嵌 game.bin 逐字节一致  : %s (len=%d sha1=%s)"
      % ("PASS" if ok else "FAIL", len(hook), hashlib.sha1(hook).hexdigest()[:16]))
if not ok:
    fails.append("A")

# ---------------------------------------------------------------- B
b = rd(rom, 0x080032F8, 8)
hw = struct.unpack_from("<HH", b)
stub_ok = hw[0] == 0x4900 and hw[1] == 0x4708 and u32(b, 4) == 0x08800001
print("B. PrintNextChar 桩 %s  ldr/bx=%04X %04X  pool=0x%08X (期望 0x08800001)"
      % ("PASS" if stub_ok else "FAIL", hw[0], hw[1], u32(b, 4)))
if not stub_ok:
    fails.append("B")

# ---------------------------------------------------------------- C
# EngineEntry @0x08800000 : ldr r1,=PrintNextChar_Hook ; bx r1
e = rom[off(0x08800000):off(0x08800000) + 8]
ehw = struct.unpack_from("<HH", e)
tgt = u32(e, 4)
ent_ok = ehw[0] == 0x4900 and ehw[1] == 0x4708 and (tgt & 1) == 1 \
    and 0x08800000 <= (tgt & ~1) < 0x08800000 + len(hook)
print("C1 EngineEntry            %s  %04X %04X -> 0x%08X"
      % ("PASS" if ent_ok else "FAIL", ehw[0], ehw[1], tgt))
if not ent_ok:
    fails.append("C1")

# PrintNextChar_Origin @0x08800008 : push{r4,lr} adds r4,r0,#0 ldrh r0,[r4,#0x14] adds r1,r0,#1 ldr r2,=.. bx r2
p = rom[off(0x08800008):off(0x08800008) + 16]
exp = bytes([0x10, 0xB5, 0x04, 0x1C, 0xA0, 0x8A, 0x41, 0x1C, 0x00, 0x4A, 0x10, 0x47])
p_ok = p[:12] == exp and u32(p, 12) == 0x08003301
print("C2 PrintNextChar_Origin   %s  -> 0x%08X (期望 0x08003301)"
      % ("PASS" if p_ok else "FAIL", u32(p, 12)))
if not p_ok:
    fails.append("C2")

# UpdateTilemap_Origin @0x08800018 : ldr r3,=.. ; bx r3 -> 0x080036DD
u = rom[off(0x08800018):off(0x08800018) + 8]
uhw = struct.unpack_from("<HH", u)
u_ok = uhw[0] == 0x4B00 and uhw[1] == 0x4718 and u32(u, 4) == 0x080036DD
print("C3 UpdateTilemap_Origin   %s  %04X %04X -> 0x%08X (期望 0x080036DD)"
      % ("PASS" if u_ok else "FAIL", uhw[0], uhw[1], u32(u, 4)))
if not u_ok:
    fails.append("C3")

# ---------------------------------------------------------------- D
# InitTextPrinter 原版头 8B（AXVJ）= b570 464e 4645 b460
d = rd(rom, 0x08002C68, 8)
d_ok = d == bytes([0x70, 0xB5, 0x4E, 0x46, 0x45, 0x46, 0x60, 0xB4]) or d == orig[off(0x08002C68):off(0x08002C68) + 8]
print("D. InitTextPrinter 未被 hook  : %s  %s" % ("PASS" if d_ok else "FAIL", d.hex()))
if not d_ok:
    fails.append("D")

# 关键函数本体也不能被改（v1 不劫任何引擎函数）
for name, addr, n in (("UpdateTilemap", 0x080036DC, 48),
                      ("GetCursorTilemapPointer", 0x08003708, 40),
                      ("FontSubTable", 0x081BB3BC, 32),
                      ("FontFuncTable", 0x081BB3AC, 16)):
    same = rd(rom, addr, n) == rd(orig, addr, n)
    print("   引擎 %-24s %s" % (name, "原样" if same else "**被改**"))
    if not same:
        fails.append("D-" + name)

# ---------------------------------------------------------------- E
fm = FONTMID.resolve()
if fm.exists():
    wb = fm.read_bytes()
    gb = rd(rom, 0x09400000, len(wb))
    fb_ok = wb == gb
    print("E1 Middle 4bpp 字库 @0x09400000 %s (%d 字)"
          % ("PASS" if fb_ok else "FAIL", len(wb) // 128))
    if not fb_ok:
        fails.append("E1")
else:
    print("E1 Middle bin 缺失:", fm)

magic = rd(rom, 0x09EA0000, 4)
print("E2 SlotTable 魔术字 = %s (%s)" % (magic, "PASS" if magic == b"SLT2" else "FAIL"))
if magic != b"SLT2":
    fails.append("E2")

# ---------------------------------------------------------------- F
diff = [i for i in range(min(len(rom), len(orig))) if rom[i] != orig[i]]
print("F. origin-vs-output 差异字节 = %d" % len(diff))
if diff:
    runs = []
    s = prev = diff[0]
    for i in diff[1:]:
        if i == prev + 1:
            prev = i
            continue
        runs.append((s, prev))
        s = prev = i
    runs.append((s, prev))
    big = [r for r in runs if r[1] - r[0] >= 0x100]
    print("   差异段数 = %d（其中 ≥256B 的 %d 段）" % (len(runs), len(big)))
    for a, b2 in sorted(big, key=lambda r: -(r[1] - r[0]))[:14]:
        print("     0x%08X..0x%08X  %8d B" % (a + ROMBASE, b2 + ROMBASE, b2 - a + 1))

print()
print("RESULT: %s" % ("PASS" if not fails else "FAIL -> " + ",".join(fails)))
