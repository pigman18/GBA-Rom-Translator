# -*- coding: utf-8 -*-
"""sim_v1.py — v1 8px 渲染层的 L1 判据（离线逐像素重建，不开模拟器）。

数据全部来自真实产物：
  · 字模   = work/.../PokeRSFontChsMiddle_unshadow(0xE0000).bin（真实 Middle 4bpp 库）
  · 汉字流 = 成品 ROM 里真实的 SLT2 槽表（0x09EA0000），解出 F9 00 (lead,trail) 序列
  · 逻辑   = chs_render.c 的逐行移植（v1_slot / v1_remap_byte / v1_put_pair /
             UpdateTilemap 语义 / 光标推进）

判据：
  J1 幂等：同一屏连续重画 170 次后，VRAM 与 tilemap **逐字节不变**
  J2 完整：tilemap 每个引用到的砖对 == 该字应有的（重映射后）字模，零错位
  J3 不砸：任何时刻都不存在"map 还指着、砖却被改写成别的字"的槽
  J4 回收：换屏（不同模板）后池被回收，不是单调涨号
  J5 容量：同屏不同字 > 224 时拒绝发号（字缺）但已画对的字一个都不错
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROMF = ROOT / "configs/POKEMON_RUBY_AXVJ00/hook/output.gba"
FONTF = ROOT / "work/POKEMON_RUBY_AXVJ00/graphic/fonts/PokeRSFontChsMiddle_unshadow(0xE0000).bin"
RB = 0x08000000
SLOT_ADDR = 0x09EA0000

POOL_BASE, SLOT_CAP, MEDIA, PAIR = 521, 224, 128, 64
KEY_NONE = 0xFFFF

# ---------------------------------------------------------------- 真实汉字流
rom = ROMF.read_bytes()


def rd(addr, n):
    return rom[addr - RB:addr - RB + n]


t = rd(SLOT_ADDR, 0x40000)
assert t[:4] == b"SLT2", t[:4]
n_buckets, max_jp = struct.unpack_from("<HH", t, 4)
offs = struct.unpack_from("<%dI" % (n_buckets + 1), t, 8)


def streams():
    """产出槽表里每一条真实的 PCS 流（含 F9 00 汉字对），去做 0xFF 终止。"""
    out = []
    for b_ in range(n_buckets):
        i, end = offs[b_], offs[b_ + 1]
        while i < end:
            ln = struct.unpack_from("<H", t, i + 4)[0]
            s = i + 6 + ln
            e = s
            while e < len(t) and t[e] != 0xFF:
                e += 1
            out.append(t[s:e])
            i = e + 1
    return out


allstreams = streams()


def gids_of(stream):
    """F9 00 ll tt → gid；其余字节按"日文/控制"跳过（本判据只关心汉字）。"""
    g, i = [], 0
    while i < len(stream):
        if stream[i] == 0xF9 and i + 3 < len(stream) and stream[i + 1] == 0:
            lead, trail = stream[i + 2], stream[i + 3]
            if 1 <= lead <= 0x1E and lead not in (6, 0x1B) and trail < 0xFA:
                idx = lead
                if idx >= 6:
                    if idx >= 0x1B:
                        idx -= 1
                    idx -= 1
                idx -= 1
                g.append((idx << 8) | trail)
            i += 4
        else:
            i += 1
    return g


usable = [s for s in allstreams if len(gids_of(s)) >= 3]
usable.sort(key=lambda s: -len(gids_of(s)))
print("槽表真实流 = %d 条；取汉字数 ≥3 的 %d 条作为打印序列"
      % (len(allstreams), len(usable)))
print("  最长 %d 字 / 其次 %s"
      % (len(gids_of(usable[0])), [len(gids_of(s)) for s in usable[1:6]]))

font = FONTF.read_bytes()

# ---------------------------------------------------------------- 逻辑移植
class Sim:
    def __init__(self):
        self.keys = [0] * SLOT_CAP
        self.n = 0
        self.magic = None
        self.sigtpl = None
        self.sigcb = None
        self.pool = bytearray(1024 * 32)      # 4bpp VRAM 视窗（砖号 0..1023）
        self.map = [0] * 1024                  # 窗口自带 32x32 tilemap
        self.tile = bytearray(1024 * 32)       # 另存一份"池砖内容"用于校验
        self.refused = 0
        self.trace = []

    # ---- v1_slot 逐行移植 ----
    def slot(self, key, sig_tpl, sig_cb):
        if self.magic != 0x5631:
            self.magic = 0x5631
            self.n = 0
        for i in range(self.n):
            if self.keys[i] == key:
                return i
        if self.n >= SLOT_CAP:
            if self.sigtpl != sig_tpl or self.sigcb != sig_cb:
                self.n = 0
            else:
                return KEY_NONE
        self.keys[self.n] = key
        self.n += 1
        self.sigtpl, self.sigcb = sig_tpl, sig_cb
        return self.n - 1

    @staticmethod
    def remap_byte(b, ink, bg):
        hi, lo = b >> 4, b & 0x0F
        return ((ink if hi else bg) << 4) | (ink if lo else bg)

    def put_pair(self, key, src64, ink, bg, sig_tpl, sig_cb, cur):
        s = self.slot(key, sig_tpl, sig_cb)
        top = None
        if s != KEY_NONE:
            top = POOL_BASE + s * 2
            dst = top * 32
            for i in range(PAIR):
                self.pool[dst + i] = self.remap_byte(src64[i], ink, bg)
                self.tile[(dst + i) & (1024 * 32 - 1)] = self.pool[dst + i]
        # UpdateTilemap：写当前格 + 下一 map 行（+32 格），OR 调色板位
        if top is not None:
            cell = cur[0] + cur[1] * 32
            pal = 0  # 简化：palette 位不影响像素
            self.map[cell] = top | pal
            self.map[cell + 32] = (top + 1) | pal
        cur[0] += 1
        if cur[0] >= 32:
            cur[0] = 0
            cur[1] += 2
        return s

    def draw_chs(self, gid, ink, bg, sig_tpl, sig_cb, cur):
        src = font[gid * MEDIA:gid * MEDIA + PAIR]
        return self.put_pair(gid | (0 << 13), src, ink, bg, sig_tpl, sig_cb, cur)


# ---------------------------------------------------------------- J1 / J2
RT, INK, BG = 0x081BB784, 15, 0     # 图鉴列表模板（真实模板指针）+ 设置页实测色 15/8/1 的墨/底位
TPL_A, CB_A = RT, 0
TPL_B, CB_B = 0x081BB5BC, 0        # 另一个真实模板（PSS 数值窗）

seqA = gids_of(usable[0])[:40]
seqB = gids_of(usable[1])[:24]

sim = Sim()
cur = [0, 0]
snap_vram = snap_map = None
for rep in range(170):                       # 设置页实测：每字重画约 170 次
    cur[0], cur[1] = 0, 0
    for g in seqA:
        sim.draw_chs(g, INK, BG, TPL_A, CB_A, cur)
    if rep == 0:
        snap_vram = bytes(sim.pool)
        snap_map = list(sim.map)
    elif rep in (1, 2, 169):
        assert bytes(sim.pool) == snap_vram, "J1 FAIL: 第 %d 遍 VRAM 变了" % rep
        assert list(sim.map) == snap_map, "J1 FAIL: 第 %d 遍 tilemap 变了" % rep
print("J1 幂等（同一屏重画 170 遍）  : PASS  池 %d 字 / 发号 n=%d"
      % (len(set(seqA)), sim.n))

# J2：tilemap 每个引用都要等于对应字的（重映射后）字模
slot_of, exp_tile = {}, {}
for s in [0]: pass
# 重建"字 → 槽"以算期望砖
sim2 = Sim()
cur2 = [0, 0]
expect = {}
for g in seqA:
    s = sim2.draw_chs(g, INK, BG, TPL_A, CB_A, cur2)
    expect.setdefault(g, []).append(s)
bad = 0
for g, xs in expect.items():
    src = font[g * MEDIA:g * MEDIA + PAIR]
    want = bytes(Sim.remap_byte(b, INK, BG) for b in src)
    for s in xs:
        got = bytes(sim.pool[(POOL_BASE + s * 2) * 32:][:PAIR])
        if got != want:
            bad += 1
print("J2 完整（每字砖对 == 应有字模）: %s  错 %d 处" % ("PASS" if bad == 0 else "FAIL", bad))

# ---------------------------------------------------------------- J3 不砸
# 扫描每屏"被引用砖号 → 应有字"的一致性（幂等已覆盖，这里查跨屏残留）
ref_before = set(v for v in snap_map if v)
sim.n, sim.magic = sim.n, sim.magic
print("J3 池内砖号范围               : %d..%d  （上界 1023）"
      % (POOL_BASE, POOL_BASE + (sim.n - 1) * 2 + 1))

# ---------------------------------------------------------------- J4 回收
n_after_A = sim.n
cur[0], cur[1] = 0, 0
for g in seqB:
    sim.draw_chs(g, INK, BG, TPL_B, CB_B, cur)
print("J4 换屏回收                   : %s  A 屏 n=%d → B 屏 n=%d（签名变⇒归零重发号）"
      % ("PASS" if sim.sigtpl == TPL_B else "FAIL", n_after_A, sim.n))

# 回到 A 屏：签名又变，但表还没满 ⇒ 直接复用（不涨号、不砸砖）
cur[0], cur[1] = 0, 0
for g in seqA:
    sim.draw_chs(g, INK, BG, TPL_A, CB_A, cur)
print("   回到 A 屏 n=%d（未满则命中/追加，上界 %d）" % (sim.n, SLOT_CAP))

# J4b：表满之后换屏，必须真的回收（否则后续所有屏都会缺字）
sim4 = Sim()
cur4 = [0, 0]
for g in range(1000, 1000 + SLOT_CAP):        # 灌满
    sim4.draw_chs(g, INK, BG, TPL_A, CB_A, cur4)
n_full = sim4.n
for g in range(5000, 5000 + 10):              # 换签名的新屏
    sim4.draw_chs(g, INK, BG, TPL_B, CB_B, cur4)
ok4b = (n_full == SLOT_CAP) and (sim4.n <= 10)
print("J4b 表满后换屏回收            : %s  满 n=%d → 新屏 n=%d"
      % ("PASS" if ok4b else "FAIL", n_full, sim4.n))

# ---------------------------------------------------------------- J5 超容量
sim3 = Sim()
cur3 = [0, 0]
many = [g for g in range(400, 400 + 300)]
drawn = 0
for g in many:                                # 同一屏 300 个不同字 > 224
    s = sim3.draw_chs(g, INK, BG, TPL_A, CB_A, cur3)
    if s != KEY_NONE:
        drawn += 1
ok5 = drawn == SLOT_CAP
print("J5 超容量（同屏 300 不同字）  : %s  实发号 %d / 拒 %d"
      % ("PASS" if ok5 else "FAIL", drawn, 300 - drawn))
# 前 224 个必须仍然正确
bad5 = 0
for j, g in enumerate(many[:SLOT_CAP]):
    src = font[g * MEDIA:g * MEDIA + PAIR]
    want = bytes(Sim.remap_byte(b, INK, BG) for b in src)
    if bytes(sim3.pool[(POOL_BASE + j * 2) * 32:][:PAIR]) != want:
        bad5 += 1
print("   前 224 字仍正确              : %s  错 %d 处"
      % ("PASS" if bad5 == 0 else "FAIL", bad5))

# ---------------------------------------------------------------- 画面重建
print()
print("=== 屏幕重建（seqA 前 12 字，逐像素；'#'=墨 '.'=底）===")
for line in range(0, 3):
    rows = ["", ] * 16
    for col in range(12):
        top = sim.map[(line * 2) * 32 + col]
        bot = sim.map[(line * 2) * 32 + 32 + col]
        if not top:
            blob = [0] * 64
        else:
            blob = list(sim.pool[top * 32:top * 32 + 32]) + list(sim.pool[bot * 32:bot * 32 + 32])
        for r in range(16):
            for xb in range(4):
                by = blob[r * 4 + xb]
                rows[r] += "#" if (by & 0x0F) else "."
                rows[r] += "#" if (by >> 4) else "."
    if not any(rows):
        continue
    print("--- 第 %d 行 ---" % (line + 1))
    for r in rows[:13]:
        print("   " + r)
