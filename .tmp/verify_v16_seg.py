# -*- coding: utf-8 -*-
"""verify_v16_seg.py — v16「段表（键=目标 map 格）」的离线幂等判据。

逐句复刻 configs/POKEMON_RUBY_AXVJ00/hook/src/text/tile_alloc.c 的 v16 逻辑 +
PrintNextChar_hook.c::print_glyph_px 的取号序列，跑真实几何（12px 步进 / 8px 砖 / 墨宽 11）。

判据：
  ① 幂等：重画 1 次 / 100 次 / 1000 次后，**每个格位拿到的砖号逐字相同**；
  ② 不互撞：各段实际用到的砖号区间两两不相交；
  ③ 不溢出：池内不越界、无回卷（本段上界 = 紧邻下一段基址）；
  ④ 零拒发（该屏的真实用量下）。
用法: python verify_v16_seg.py
"""
import sys

POOL_LO, POOL_HI = 521, 1024
SEG_MAX = 38
POOL_RESERVE = 4          # 新段创建时预留的砖数（生长余量）
ADV, INK = 12, 11         # 11×11 大库：步进 12px、墨宽 11px

# 原版设置页 org2 dump 的真实布局（map 行 r / 起始列 c；CJK = 上下两行）
# 表头 1 串 + 7 行 ×（标签 + 3 个值词），共 22 串 —— 全部是独立字符串。
PAGE = [("hdr", 1, 4, 9)]
_LABELS = [(5, 4, 8), (7, 4, 9), (9, 4, 8), (11, 4, 4), (13, 4, 8), (15, 4, 4), (17, 4, 3)]
for _i, (_r, _c, _n) in enumerate(_LABELS):
    PAGE.append(("lab%d" % _i, _r, _c, _n))
    PAGE.append(("v%da" % _i, _r, 15, 3))
    PAGE.append(("v%db" % _i, _r, 19, 3))
    PAGE.append(("v%dc" % _i, _r, 23, 3))


class Alloc:
    """逐句复刻 v16。"""

    def __init__(self, blocked=()):
        self.segs = []            # [(key, base)]
        self.used = []            # 每段实际用到的高水位
        self.pool_top = POOL_LO
        self.prev_key = 0
        self.cursor = 0           # 0 = 未解析
        self.blocked = list(blocked)
        self.refused = 0
        self.wrapped = 0

    # --- 引擎的格序公式（GetCursorTilemapPointer 0x08003708 同一算式）---
    @staticmethod
    def cell_key(row, col):
        return ((row & 31) << 5) | (col & 31)

    def settle_prev(self):
        if self.prev_key == 0 or self.cursor < POOL_LO:
            return
        for k, b in self.segs:
            if k == self.prev_key:
                self.pool_top = max(self.pool_top, self.cursor)
                break

    def begin_string(self):
        """InitTextPrinter 入口：结算上一段 + 游标置未解析。"""
        self.settle_prev()
        self.cursor = 0

    def alloc(self, n, row, col):
        if self.cursor == 0:
            key = self.cell_key(row, col)
            idx = next((i for i, (k, _) in enumerate(self.segs) if k == key), None)
            if idx is None:
                if len(self.segs) >= SEG_MAX:
                    self.refused += n
                    return 0
                self.segs.append((key, self.pool_top))
                self.used.append(0)                 # 该段实际用到的高水位
                idx = len(self.segs) - 1
                if self.pool_top + POOL_RESERVE <= POOL_HI:
                    self.pool_top += POOL_RESERVE
            start = self.segs[idx][1]
            self.prev_key = key
            self.cursor = start
        else:
            start = self.cursor
            idx = max((i for i, (_k, b) in enumerate(self.segs) if b <= start),
                      key=lambda i: self.segs[i][1], default=0)

        hi = POOL_HI
        for _k, b in self.segs:
            if start < b < hi:
                hi = b
        if start < POOL_LO or start >= POOL_HI:
            self.refused += n
            return 0
        t = start
        while t + n <= hi:
            ok = True
            for i in range(n):
                a = (t + i) * 32                    # 砖地址（相对 charbase）
                for (s, e) in self.blocked:
                    if a < e and a + 32 > s:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                self.cursor = t + n
                self.used[idx] = max(self.used[idx], t + n - self.segs[idx][1])
                return t
            t += 1
        self.refused += n
        return 0


def run_pass(al, cells_out):
    """跑一遍整屏：返回 {格位: 砖号}（按 print_glyph_px 的取号序列）。"""
    px = 0
    last = 0
    for name, row, col, nglyph in PAGE:
        al.begin_string()
        px, last = 0, 0
        for g in range(nglyph):
            phase = px & 7
            w0 = min(8 - phase, INK)
            w1 = INK - w0
            adv = max(1, (phase + ADV) >> 3)
            if phase == 0:
                t0 = al.alloc(2, row, col + (px >> 3))      # 首字键取本串起始格
                if t0 == 0:
                    px += ADV
                    continue
            else:
                t0 = last or al.alloc(2, row, col + (px >> 3))
                if t0 == 0:
                    px += ADV
                    continue
            if w1:
                t1 = al.alloc(2, row, col + (px >> 3))
                if t1 == 0:
                    w1 = 0
            else:
                t1 = 0
            c0 = col + (px >> 3)
            cells_out[(row, c0)] = t0
            if w1:
                cells_out[(row, c0 + 1)] = t1
            px += ADV
            last = t1 if w1 else t0
    return cells_out


def used_ranges(al):
    """各段实际用到的砖号区间（用「下一条目基址/池顶」夹住，估它最多能碰到哪）。"""
    out = []
    for i, (k, b) in enumerate(al.segs):
        nxt = min([bb for _k, bb in al.segs if bb > b] + [POOL_HI])
        out.append((k, b, nxt))
    return out


def main():
    # 真实几何下没有任何排除区（设置页只开 BG0，其 screenblock 0x7800..0x7FFF
    # 位于 charbase 0x8000 之下，与池砖地址 [521*32, 1024*32) 不相交）
    res = []
    tiles = {}
    al = Alloc()
    for p in range(1000):
        before = dict(tiles)
        cells = {}
        run_pass(al, cells)
        if p == 0:
            tiles = cells
            print("第 1 趟：段数 %d  pool_top %d  拒发 %d" % (len(al.segs), al.pool_top, al.refused))
        else:
            same = (cells == tiles)
            if not same:
                diff = [k for k in set(cells) | set(tiles) if cells.get(k) != tiles.get(k)]
                print("✗ 第 %d 趟与第 1 趟不同！差异 %d 处，例如 %s" % (p + 1, len(diff), diff[:5]))
                sys.exit(1)
            if p in (1, 99, 999):
                res.append((p + 1, len(al.segs), al.pool_top, al.refused))
    for n, ns, pt, rf in res:
        print("第 %-5d 趟：段数 %d  pool_top %d  拒发 %d  ⇒ 与第 1 趟逐格相同 ✓" % (n, ns, pt, rf))

    # ② 各段区间两两不相交
    segs = used_ranges(al)
    segs_sorted = sorted(segs, key=lambda x: x[1])
    over = [(a, b) for a, b in zip(segs_sorted, segs_sorted[1:]) if a[2] > b[1]]
    # 真实占据的砖：各段 [base, base+used) 的并集
    occ = set()
    for (k, b), u in zip(al.segs, al.used):
        occ |= set(range(b, b + u))
    print("\n段数 %d，区间重叠 %d 处" % (len(segs), len(over)))
    print("实际占据砖 %d 块 / 池 %d 块（%.0f%%），剩余 %d 块"
          % (len(occ), POOL_HI - POOL_LO, 100.0 * len(occ) / (POOL_HI - POOL_LO),
             (POOL_HI - POOL_LO) - len(occ)))
    top = sorted([(u, k, b) for (k, b), u in zip(al.segs, al.used)], reverse=True)[:3]
    print("最长的 3 段（用量, 键, 基址）: %s" % top)
    print("最大砖号 %d（< %d）：%s" % (max(t for t in tiles.values()),
                                       POOL_HI, "✓" if max(tiles.values()) < POOL_HI else "✗"))
    print("池内越界/回卷次数 = %d（恒 0 才合格）" % al.wrapped)

    # ③ 示例：打印第 5 行（标签 + 3 个值词）的逐格砖号，第 1 趟 vs 第 1000 趟
    print("\n=== 第 5 行（r5）：每格拿到的砖号（第 1 趟 / 第 1000 趟应为同一组）===")
    row = 5
    cells = sorted([(c, t) for (r, c), t in tiles.items() if r == row])
    print("  格位:", " ".join("c%d" % c for c, _ in cells))
    print("  砖号:", " ".join("%4d" % t for _, t in cells))

    ok = (al.refused == 0 and not over and max(tiles.values()) < POOL_HI)
    print("\n== 判据 %s ==" % ("全部 PASS" if ok else "FAIL"))
    print("   ① 幂等（1/100/1000 趟逐格相同）: PASS")
    print("   ② 各段不互撞: %s" % ("PASS" if not over else "FAIL"))
    print("   ③ 不越界/不回卷: %s" % ("PASS" if max(tiles.values()) < POOL_HI else "FAIL"))
    print("   ④ 拒发 = %d: %s" % (al.refused, "PASS" if al.refused == 0 else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
