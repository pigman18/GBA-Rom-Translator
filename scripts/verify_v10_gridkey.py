#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v10「按格子定号」复用安全性判据（v2，2026-09-20 实机成片重复后重写）

为什么要有 v2
-------------
v1（旧版本脚本）的 J1–J5 全 PASS，但实机**成片重复**。根因不在实现细节，而在
**判据前提错了**：v1 让所有格子初始为空（`cell_tile` 返回 0）⇒ 每个字都走「领新号」
分支，复用逻辑根本没被真正行使，自然也看不见「所有格子返回同一个号」的塌缩。

真实屏幕的初始状态是：**窗口文本区每一格都指向同一个「底纹/背景 tile」**
（`BLANK`）。于是只要 `v8_ours_has(BLANK)` 为真，`chs_claim_tile` 就会对**每一格**
返回同一个 BLANK ⇒ 所有汉字叠进同一个 tile ⇒ 实机成片重复片段。

本判据因此把前提修正为「格子预铺 BLANK」，并同时模拟三套判定：

  * `alloc_mode='v10.0'` / `reuse_gate='v10.0'` —— 实机挂掉的那一版
      alloc : ① `ours(t)` ⇒ 无条件可用（**绕过活引用检查**）
              ④ 非空 + 无引用 ⇒ 认领进 ours（把 BLANK 拖进 ours 的入口）
      reuse : `ours(cell)` ⇒ 直接复用该号
  * `alloc_mode='v10.1'` / `reuse_gate='v10.1'` —— 本次修法
      alloc : 只保留「活引用 ⇒ 不可写」，删掉 ① 与 ④
      reuse : `ours(cell) && ours(cell+1) && cell_lower == cell+1`
              （**竖直对一致性**：底纹是 (BLANK, BLANK)，竖直对不成立 ⇒ 天然排除）

判据
----
  A1 复现：v10.0 + BLANK∈ours ⇒ 画面塌缩（**必须与参照不同**）。这是 bug 的见证。
  A2 修正：v10.1 + BLANK∈ours（**最坏情况：账本已被污染**）⇒ 画面与参照逐像素相同。
  A3 零消耗：v10.1 重画期领号增量 == 0。
  A4 幂等：v10.1 多轮重画后 tilemap 一字不变。
  A5 区分力：关掉复用（= 旧 v9）重画增量必须 > 0（否则 A3 是空断言）。
  A6 有界：v10.1 画 20 轮，池占用不随轮数增长（上界 = 用过的格子数）。
  A7 单射：`ours` 里的号，被引用它的格子数必须 == 1（两个格子共用一个号 = 覆盖）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_plan4 as v4            # noqa: E402  （复用 blend / bdf / extract 原语）

ARENA_LO, ARENA_HI = 256, 1024
LOWER_DELTA = 1
INK, ADVANCE = 11, 12
BLANK = 300                 # 窗口文本区底纹 tile（落在池区间内 —— 实机就是这样）
W_COLS = 12                 # 窗口文本区宽度（格）
ROWS = 2                    # 文本区高度（格）＝ 一个 8×16 字形带


# ---------------------------------------------------------------- 池
class Pool:
    """`v8_alloc_n` 的行为模型。alloc_mode 决定「可用性判定」。"""

    def __init__(self, alloc_mode):
        self.mode = alloc_mode
        self.ours = set()
        self.cursor = ARENA_LO
        self.calls = 0
        self.fail = 0

    def live(self, sc):
        return {v & 0x3FF for v in sc.tmap.values()}

    def _usable(self, sc, t):
        if t < ARENA_LO or t >= ARENA_HI:
            return False
        live = self.live(sc)
        if self.mode == 'v10.0':
            # ① ours ⇒ 无条件可用（不看活引用）—— 实机塌缩的第一入口
            if t in self.ours:
                return True
            # ② 活引用 ⇒ 受保护
            if t in live:
                return False
            # ④ 非空 + 无引用 ⇒ 认领（第二入口）
            if self._nonempty(t):
                self.ours.add(t)
            return True
        # v10.1：只留活引用保护
        if t in live:
            return False
        return True

    @staticmethod
    def _nonempty(t):
        """模型里「VRAM 非空」等价于该号已被写过字形/底纹（BLANK 与池内已发号）。"""
        return t in _NONEMPTY

    def alloc(self, sc):
        self.calls += 1
        for base in (self.cursor, ARENA_LO):
            t = base if base >= ARENA_LO else ARENA_LO
            while t + LOWER_DELTA < ARENA_HI:
                if self._usable(sc, t) and self._usable(sc, t + LOWER_DELTA):
                    self.ours.add(t)
                    self.ours.add(t + LOWER_DELTA)
                    self.cursor = t + 2
                    return t
                t += 1
        self.fail += 1
        return 0


_NONEMPTY = {BLANK}          # 底纹 tile 是「非空」的（实心色）


class Screen(v4.Screen):
    def cell(self, cx, cy):
        return self.tmap.get((cx, cy), 0) & 0x3FF

    def pair(self, cx, cy):
        """引擎 UpdateTilemap 的竖直对：本格 + 本格下方一格（实机 = 表项 +32）。"""
        return self.cell(cx, cy), self.cell(cx, cy + 1)


def prefill(sc):
    for cy in range(ROWS):
        for cx in range(W_COLS):
            sc.tmap[(cx, cy)] = BLANK


# ---------------------------------------------------------------- 渲染复刻
def one_glyph(sc, win, g128, pool, reuse, gate):
    colors = v4.COLORS
    px = win['phase']
    phase = px & 7
    w0 = (8 - phase) if (8 - phase) < INK else INK
    w1 = INK - w0
    adv = (phase + ADVANCE) >> 3
    if adv < 1:
        adv = 1
    tx0, row = win['cx'], win['row']

    def claim(dx):
        """chs_claim_tile 的共池分支。"""
        if reuse:
            r = sc.cell(tx0 + dx, row)
            if gate == 'v10.0':
                if r in pool.ours:
                    return r
            else:
                if (r >= ARENA_LO and r in pool.ours
                        and (r + LOWER_DELTA) in pool.ours
                        and sc.cell(tx0 + dx, row + 1) == r + LOWER_DELTA):
                    return r
        return pool.alloc(sc)

    if phase == 0:
        t0 = claim(0)
    else:
        t0 = claim(0) if win['last_tile'] == 0 else win['last_tile']
    if t0 == 0:
        return adv

    if w1 != 0:
        t1 = claim(1)
        if t1 == t0 or t1 == t0 + LOWER_DELTA:
            t1 = pool.alloc(sc)          # 复用撞车 ⇒ 改领新号（不得与左半重合）
        if t1 == 0:
            w1 = 0
    else:
        t1 = 0

    up, lo = v4.extract_cols(g128, 0, w0)
    v4.blend_glyph_4bpp(v4.list_view(sc.tile(t0)), up, w0, phase, colors)
    v4.blend_glyph_4bpp(v4.list_view(sc.tile(t0 + LOWER_DELTA)), lo, w0, phase,
                        colors)

    if w1 != 0:
        up, lo = v4.extract_cols(g128, w0, w1)
        v4.blend_glyph_4bpp(v4.list_view(sc.tile(t1)), up, w1, 0, colors)
        v4.blend_glyph_4bpp(v4.list_view(sc.tile(t1 + LOWER_DELTA)), lo, w1, 0,
                            colors)
        zero = bytes(32)
        v4.blend_glyph_4bpp(v4.list_view(sc.tile(t1)), zero, 8 - w1, w1, colors)
        v4.blend_glyph_4bpp(v4.list_view(sc.tile(t1 + LOWER_DELTA)), zero,
                            8 - w1, w1, colors)

    sc.utm(tx0, row, t0, t0 + LOWER_DELTA)
    if w1 != 0:
        win['cx'] = tx0 + 1
        sc.utm(win['cx'], row, t1, t1 + LOWER_DELTA)
    win['cx'] = tx0 + adv

    win['phase'] = px + ADVANCE
    win['last_tile'] = t1 if w1 != 0 else t0
    return adv


def new_win():
    """一次新的打印：相位/列游标复位，**tilemap 与账本不动**（= 引擎再打印一次）。"""
    return {'phase': 0, 'cx': 0, 'row': 0, 'last_tile': 0}


def run(fonts, alloc_mode, gate, blank_in_ours, reuse, rounds):
    sc = Screen()
    prefill(sc)
    global _NONEMPTY
    _NONEMPTY = {BLANK}
    pool = Pool(alloc_mode)
    if blank_in_ours:
        pool.ours.add(BLANK)
        pool.ours.add(BLANK + LOWER_DELTA)
    growth = []
    tm_after = []
    for _ in range(rounds):
        before = pool.calls
        win = new_win()
        for g in fonts:
            one_glyph(sc, win, g, pool, reuse, gate)
        growth.append(pool.calls - before)
        tm_after.append(dict(sc.tmap))
    return {
        'sc': sc,
        'pool': pool,
        'growth': growth,
        'tmap': dict(sc.tmap),
        'tm_after': tm_after,
        'pixels': render(sc),
    }


def render(sc):
    return [[(sc.render(W_COLS * 8, ROWS * 8)[y][x] or 0)
             for x in range(W_COLS * 8)] for y in range(ROWS * 8)]


def max_refs(tmap):
    """单个 tile 号被多少个格子引用（>1 = 两个格子共用 ⇒ 会互相覆盖）。"""
    cnt = {}
    for t in tmap.values():
        cnt[t & 0x3FF] = cnt.get(t & 0x3FF, 0) + 1
    return cnt


def row_distinct(tmap, cy):
    return len({(tmap.get((cx, cy), 0) & 0x3FF) for cx in range(W_COLS)})


def shared_cells(tmap, tile):
    """有多少个格子指向同一个 tile 号（>1 = 该 tile 的内容会被多处显示）。"""
    return sum(1 for v in tmap.values() if (v & 0x3FF) == (tile & 0x3FF))


# ---------------------------------------------------------------- 主流程
def main():
    idx = v4.parse_bdf(v4.ROOT + r'\fonts\default\Normal.bdf')
    chars = '啊的一了你好中文'
    # 与 verify_plan4 同链路：BDF 行 → pack_1bpp（连续位流）→ chs_cell_from_1bpp
    # → 128 B 单元（[TL@0][BL@0x20][TR@0x40][BR@0x60]），即 print_glyph_px 的入参。
    missing = [c for c in chars if ord(c) not in idx]
    if missing:
        raise SystemExit('BDF 缺字符: %r' % (missing,))
    fonts = [v4.chs_cell_from_1bpp(v4.pack_1bpp(idx[ord(c)]), v4.W, v4.H,
                                   v4.ROW_OFF_BIG)
             for c in chars][:8]

    ref = run(fonts, 'v10.1', 'v10.1', False, False, 1)
    v100 = run(fonts, 'v10.0', 'v10.0', True, True, 3)
    v101 = run(fonts, 'v10.1', 'v10.1', True, True, 3)
    off = run(fonts, 'v10.1', 'v10.1', True, False, 3)
    long = run(fonts, 'v10.1', 'v10.1', True, True, 20)

    res = []
    print('=' * 74)
    print('前提：窗口文本区 %d×%d 格**全部预铺底纹 tile BLANK=%d**（v1 判据漏掉的真实前提）'
          % (W_COLS, ROWS, BLANK))
    print('=' * 74)

    # A1 复现
    same = v100['pixels'] == ref['pixels']
    d1 = row_distinct(v100['tmap'], 0)
    shared1 = shared_cells(v100['tmap'], BLANK)
    print('【A1】v10.0 + BLANK∈ours（实机那一版）')
    print('      底纹号 %d 被 %d 个格子共用（>1 即「整块面板显示同一 tile」）'
          % (BLANK, shared1))
    print('      第 0 行不同 tile 号 = %d  （%d 个字画下去只留下 %d 个不同号）'
          % (d1, len(fonts), d1))
    print('      画面 == 参照 ? %s' % ('是' if same else '否 ← 塌缩，bug 复现'))
    res.append(('A1 复现 v10.0 塌缩（画面必须与参照不同）',
                (not same) and shared1 > 1 and d1 < len(fonts)))

    # A2 修正（最坏情况：账本已被污染）
    same2 = v101['pixels'] == ref['pixels']
    same2b = v101['tmap'] == ref['tmap']
    shared2 = shared_cells(v101['tmap'], BLANK)
    print('【A2】v10.1 + BLANK∈ours（账本已污染的最坏情况）')
    print('      底纹号 %d 被 %d 个格子共用（必须 == 0：底纹零写入）'
          % (BLANK, shared2))
    print('      画面逐像素 == 参照 ? %s   tilemap 一字不变 ? %s'
          % ('是' if same2 else '否', '是' if same2b else '否'))
    res.append(('A2 v10.1 在账本污染下仍与参照一致',
                same2 and same2b and shared2 == 0))

    # A3 零消耗
    print('【A3】v10.1 三轮领号增量 = %s' % (v101['growth'],))
    res.append(('A3 重画零消耗（第 2 轮起增量 0）',
                v101['growth'][1:] == [0] * (len(v101['growth']) - 1)
                and v101['growth'][0] > 0))

    # A4 幂等
    idem = all(t == v101['tm_after'][0] for t in v101['tm_after'])
    print('【A4】v10.1 多轮重画后 tilemap 一字不变 ? %s' % ('是' if idem else '否'))
    res.append(('A4 重画幂等（映射）', idem))

    # A5 区分力
    print('【A5】对照：关掉复用（旧 v9）三轮增量 = %s' % (off['growth'],))
    res.append(('A5 判据有区分力（对照增量必须 >0）', off['growth'][1] > 0))

    # A6 有界
    tail = long['growth'][1:]
    print('【A6】v10.1 画 20 轮：总领号 = %d，第 2 轮起增量全 0 ? %s，池占用 = %d'
          % (long['pool'].calls, '是' if set(tail) == {0} else '否',
             len(long['pool'].ours)))
    res.append(('A6 池占用不随轮数增长', set(tail) == {0}))

    # A7 单射
    cnt = max_refs(v101['tmap'])
    bad = {t: n for t, n in cnt.items() if t in v101['pool'].ours and n != 1}
    print('【A7】ours 号被多格共用的情况 = %s' % (bad if bad else '无（每号恰好 1 格）'))
    res.append(('A7 单射（无两格共用一个号）', not bad))

    print('-' * 74)
    ok = True
    for name, good in res:
        print('   %-34s %s' % (name, 'PASS' if good else 'FAIL'))
        ok = ok and good
    print('=' * 74)
    print('结论: %s' % ('PASS —— 复用安全（账本被污染也不塌缩），且重画零消耗'
                        if ok else 'FAIL —— 见上面 FAIL 项'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
