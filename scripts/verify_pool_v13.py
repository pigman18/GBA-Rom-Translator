#!/usr/bin/env python3
"""verify_pool_v13.py — v13 池分配规则的离线自证（纯几何，不读 ROM/不读 dump）。

规则（= tile_alloc.c::v8_alloc_begin / v8_alloc_n 的语义）：
  · 池 = [521, 1024)（层内砖号；521 起是因为引擎字形缓存区 = [TB, TB+2*slots)，
    fn2/3/5 ⇒ [1,513)，窗口九宫格边框 = 512..520）
  · 游标单调向上推进；**只有模板（= 换屏）变化才置首**；到顶回卷到池首
  · 每个中文字占 4 砖（t0, t0+1, t1, t1+1），但 12px 步进 + 8px 格的两段式
    让相邻两字共享一个边界砖对 ⇒ 摊到每个字 ~3 砖

本脚本要证的两件事：
  ① 同一屏的 7 行（每行 14 字）拿到**互不重叠**的砖段（修 v11 的「撞自己」）
  ② 一整趟（7 行）< 池容量 ⇒ 一趟之内不会回卷 ⇒ 不会自我覆盖
"""

POOL_LO = 521
POOL_HI = 1024
CAP = POOL_HI - POOL_LO


class Pool:
    def __init__(self):
        self.cur = POOL_LO
        self.wraps = 0

    def reset(self):
        self.cur = POOL_LO

    def alloc(self, n):
        """领连续 n 砖；到顶回卷到池首（FIFO）。"""
        if self.cur + n > POOL_HI:
            self.cur = POOL_LO
            self.wraps += 1
        t = self.cur
        self.cur += n
        return t


def draw_row(pool, nchars):
    """模拟一行文本，严格照 print_glyph_px 的两段式领号：
         phase == 0  → t0 = 新领一对（alloc 2）
         phase != 0  → t0 = 复用上一字的尾对（不领）
         w1 != 0     → t1 = 新领一对（alloc 2）
       返回本行用到的砖列表。"""
    phase = 0
    last = None
    used = []
    for _ in range(nchars):
        w0 = min(8 - phase, 11)
        w1 = 11 - w0
        if phase == 0:
            t0 = pool.alloc(2)
        else:
            t0 = last
        used.append(t0)
        t1 = None
        if w1:
            t1 = pool.alloc(2)
            used.append(t1)
        last = t1 if w1 else t0
        phase = (phase + 12) & 7
    return used


def main():
    ROWS, CHARS = 7, 14
    print("池 = [%d, %d)  容量 %d 砖" % (POOL_LO, POOL_HI, CAP))
    print("设置页模型：%d 行 × %d 字（照 print_glyph_px 两段式领号）\n" % (ROWS, CHARS))

    def one_pass(pool, label):
        print("── %s ──" % label)
        rows = []
        for r in range(ROWS):
            used = draw_row(pool, CHARS)
            cur = set()
            for t in used:                      # t 是砖对首砖：占 (t, t+1)
                cur.add(t)
                cur.add(t + 1)
            rows.append(cur)
            print("  行 %d : 用 %d 砖，范围 [%d, %d]"
                  % (r + 1, len(cur), min(cur), max(cur)))
        return rows

    def disjoint(rows):
        bad = []
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[i] & rows[j]:
                    bad.append((i + 1, j + 1, sorted(rows[i] & rows[j])[:6]))
        return (not bad), bad

    pool = Pool()
    s1 = one_pass(pool, "第 1 趟（首次进屏）")
    ok1, bad1 = disjoint(s1)
    print("\n① 第 1 趟各行两两不共用砖:", ok1, bad1 or "")
    used1 = set().union(*s1)
    print("② 整趟共用 %d 砖 ≤ 容量 %d ⇒ 一趟之内不回卷: %s"
          % (len(used1), CAP, len(used1) <= CAP))
    print("   池容量换算：%d 砖 ≈ 每趟可画 %d 字（本屏只需 %d 字）"
          % (CAP, CAP // 3, ROWS * CHARS))

    s2 = one_pass(pool, "第 2 趟（再重绘一次；游标不复位）")
    ok2, bad2 = disjoint(s2)
    print("\n③ 第 2 趟各行两两不共用砖:", ok2, bad2 or "")
    print("④ 回卷次数 =", pool.wraps, "（回卷覆盖到的是上一趟已重画过的旧砖）")

    allok = ok1 and ok2 and len(used1) <= CAP
    print("\n结论:", "PASS —— 一趟之内各行独立、整屏不自我覆盖" if allok else "FAIL")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
