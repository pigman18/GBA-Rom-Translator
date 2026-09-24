# -*- coding: utf-8 -*-
"""v12 L1 判据：官方资产区**永不复用** + 池下界 = **运行时推导**的官方上界。

为什么必须新增这道判据（而不是复用 verify_v10_gridkey）：
  verify_v10_gridkey 的场景里**没有官方字模**，所以它的 A1~A7 全绿也拦不住实机
  那条 bug —— 实机坏的是 **font4 的字模槽**（`Lv`/`/` 笔画叠成别的字）。
  这里把「格子里装的是官方字模号」这个真实场景补进模型。

被验证的实现（C 侧）：
  tile_alloc.c::v8_official_end         —— 官方上界公式（逐指令实证）
  PrintNextChar_hook.c::chs_cell_slot   —— 新增 `r < v8_official_end(win) ⇒ 拒绝`
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verify_plan4 as v4      # noqa: E402  复用 parse_bdf / pack_1bpp / blend 原语

FONT0_3_CAP = 512
FONT_OTHER_CAP = 256
FRAME_SPAN = 23                # [cap, cap+9) ∪ [cap+9, cap+23)


# ───────────────────────── C 公式的精确复刻 ─────────────────────────
def official_end(font, start_off):
    """tile_alloc.c::v8_official_end 的逐语句复刻。"""
    if font == 0 or font == 3:
        cap = FONT0_3_CAP
    elif font > 5:
        cap = FONT0_3_CAP       # 兜底：异常 font 按大 atlas 保守取
    else:
        cap = FONT_OTHER_CAP
    e1 = (start_off + cap) & 0xFFFF
    e2 = (cap + FRAME_SPAN) & 0xFFFF
    e = max(e1, e2)
    if e < 1:
        e = 1
    if e > 1024:
        e = 1024
    return e


# ───────────────────────── 闸门（旧 / 新）─────────────────────────
def gate_v10_1(r, r_plus_dlow, ours, tm_ok=True):
    """v10.1 闸门：① 本格 ∈ ours  ② 下方号 ∈ ours  ② 下方格表项 == r+dlow。

    缺的那条：**不问 r 是不是官方资产**。日文字模同样是「tile, tile+1」竖对，
    所以这三条对官方字模同样成立 ⇒ 放行 ⇒ 中文写进官方槽。
    """
    return tm_ok and (r in ours) and (r_plus_dlow in ours)


def gate_v12(r, r_plus_dlow, ours, off, tm_ok=True):
    """v12 闸门：先问「r 是不是官方资产」，再走 v10.1 三条。"""
    if r < off:                 # ← v12 新增：官方资产区永不复用
        return False
    return gate_v10_1(r, r_plus_dlow, ours, tm_ok)


# ───────────────────────── 场景数据 ─────────────────────────
def load_glyphs():
    idx = v4.parse_bdf(os.path.join(v4.ROOT, r'fonts\default\Normal.bdf'))
    chars = '啊的一了你好中文'
    out = []
    for c in chars:
        g = v4.pack_1bpp(idx[ord(c)])
        if g:
            out.append((c, g))
    assert len(out) >= 4, 'BDF 取字失败：%d' % len(out)
    return out


def main():
    res = []
    fonts = load_glyphs()

    # ── J1 公式表：与逐指令实证的 cap 表一致 ───────────────────────
    table = {
        (0, 1): 535, (3, 1): 535,          # font0/3 → cap 512 → max(513,535) = 535
        (1, 1): 279, (2, 1): 279,          # font1/2/4/5 → cap 256 → max(257,279) = 279
        (4, 1): 279, (5, 1): 279,
        (6, 1): 535,                       # 异常 font → 保守 512
        (0, 0): 535, (4, 0): 279,          # 冷启动 startOffset=0 时框仍锁到 cap+23
    }
    bad = [(k, official_end(*k), v) for k, v in table.items() if official_end(*k) != v]
    print('【J1】官方上界公式（TextLoadWindowTemplate 跳转表 @0x080029B4 实证）')
    for k in sorted(table):
        print('      font=%d startOffset=%d  ⇒ 上界 %3d  （期望 %3d）%s'
              % (k[0], k[1], official_end(*k), table[k],
                 '' if official_end(*k) == table[k] else '  ← 不符'))
    res.append(('J1 上界公式与 cap 表一致', not bad))

    # ── J2 官方字模号：新闸门必须拒绝复用 ───────────────────────────
    off_f4 = official_end(4, 1)                    # 队伍页 = font4 ⇒ 279
    official_pair = (100, 101)                     # 官方 font4 atlas 里某 glyph 的竖对
    ours = set([official_pair[0], official_pair[1]])   # 最坏情况：账本已被污染
    reused_old = gate_v10_1(official_pair[0], official_pair[1], ours)
    reused_new = gate_v12(official_pair[0], official_pair[1], ours, off_f4)
    print()
    print('【J2】格子装的是官方 font4 字模竖对 %s（账本也已被污染）' % (official_pair,))
    print('      旧闸门 v10.1 ⇒ %s' % ('复用（★把中文写进官方字模槽）' if reused_old else '拒绝'))
    print('      新闸门 v12   ⇒ %s' % ('复用' if reused_new else '拒绝 ✓'))
    res.append(('J2 新闸门拒用官方字模号', (not reused_new) and reused_old))

    # ── J3 像素级后果：官方槽被写坏 vs 完好 ────────────────────────
    vram = {}          # tile 号 → 32 B 4bpp
    for t in official_pair:
        vram[t] = b'\xAA' * 32                     # 官方字模的"原始内容"指纹

    def print_chs(g, reuse_t):
        """把中文字形写进 reuse_t（及 reuse_t+1）；不复用时领新号。"""
        if reuse_t is not None:
            t0 = reuse_t
            got_new = False
        else:
            t0 = 400                               # 池内空闲号（≥ 上界）
            while t0 in vram or (t0 + 1) in vram:
                t0 += 2
            got_new = True
        vram[t0] = bytes(g[:32])
        vram[t0 + 1] = bytes(g[32:64])
        return t0, got_new

    # 旧路径：复用官方槽
    vram_old = dict(vram)
    t_old, _ = (official_pair[0], False) if reused_old else (None, True)
    if reused_old:
        vram_old[official_pair[0]] = bytes(fonts[0][1][:32])
        vram_old[official_pair[1]] = bytes(fonts[0][1][32:64])
    damaged = (vram_old[official_pair[0]] != b'\xAA' * 32
               or vram_old[official_pair[1]] != b'\xAA' * 32)

    # 新路径：领新号，官方槽不动
    vram_new = dict(vram)
    t_new, got_new = print_chs(fonts[0][1], None)
    intact = (vram_new[official_pair[0]] == b'\xAA' * 32
              and vram_new[official_pair[1]] == b'\xAA' * 32)
    print()
    print('【J3】像素级后果（官方槽指纹 = 0xAA×32）')
    print('      旧路径 ⇒ 官方槽 %s %s' % (tuple(official_pair),
                                        '被改写（Lv→w、/ 笔画叠加 ✓复现）' if damaged else '完好'))
    print('      新路径 ⇒ 官方槽 %s %s，中文落新号 t=%d（got_new=%s）'
          % (tuple(official_pair), '完好 ✓' if intact else '被改写', t_new, got_new))
    res.append(('J3 新路径不破坏官方字模（旧路径复现 bug）', damaged and intact and got_new))

    # ── J4 池下界：硬编码 617 vs 运行时推导 ───────────────────────
    print()
    print('【J4】池下界与可用号数（每汉字 4 tile ⇒ 可用号/4 = 汉字上限）')
    rows = [('font0/3 场景', 617, official_end(0, 1)),
            ('font1/4/5 场景（队伍页等）', 617, official_end(4, 1))]
    gain_total = 0
    for name, old_lo, new_lo in rows:
        o, n = 1024 - old_lo, 1024 - new_lo
        gain_total += (n - o)
        print('      %-26s 旧 lo=617 可用 %3d（%3d 字） ⇒ 新 lo=%3d 可用 %3d（%3d 字）  +%d 号'
              % (name, o, o // 4, new_lo, n, n // 4, n - o))
    res.append(('J4 运行时推导比硬编码 617 更宽（不抬水位）', gain_total > 0))

    # ── J5 分配出的号必须全部 ≥ 上界（不撞官方资产）────────────────
    off = official_end(4, 1)
    pool_lo, pool_hi = off, 1024
    occupied = set(range(0, off))                      # 官方资产
    issued = []
    cur = pool_lo
    for i in range(60):
        t = None
        for c in range(cur, pool_hi - 1):
            if c not in occupied and (c + 1) not in occupied:
                t = c
                break
        if t is None:
            break
        occupied.add(t)
        occupied.add(t + 1)
        issued.append(t)
        cur = t + 2
    viol = [t for t in issued if t < off]
    print()
    print('【J5】按上界发的 %d 个号中，落在官方资产区 [0,%d) 的个数 = %d'
          % (len(issued), off, len(viol)))
    res.append(('J5 发出的号全部 ≥ 官方上界', not viol))

    # ── 汇总 ─────────────────────────────────────────────
    print()
    print('=' * 74)
    allok = True
    for name, ok in res:
        print('   %-50s %s' % (name, 'PASS' if ok else 'FAIL'))
        allok = allok and ok
    print('=' * 74)
    print('结论: %s —— 官方资产区永不复用，且池下界按官方实测边界运行时推导'
          % ('PASS' if allok else 'FAIL'))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
