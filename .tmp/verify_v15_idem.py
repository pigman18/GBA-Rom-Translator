# -*- coding: utf-8 -*-
"""verify_v15_idem.py —— v15「幂等发号」离线判据。

照 tile_alloc.c::v8_alloc_begin / v8_alloc_n 的逻辑**逐句复刻**成 Python 模型，
然后模拟「同一屏被连续重画 N 趟」，检查三件事：

  A. 幂等：第 2..N 趟拿到的砖号序列与第 1 趟**逐字相同**。
     （这是「疯狂跳字」的直接判据 —— 不同 = 会把 map 还指着的砖盖掉）
  B. 不回卷：任何砖号都不越出 [521, 1024)。
  C. 不互撞：同一时刻不同「行段」占用的砖区间两两不相交。

用法: python .tmp/verify_v15_idem.py
"""
import sys

POOL_LO, POOL_HI = 521, 1024
ROWS_MAX = 16
TPL_LOW = 0x0C          # 模板 0x081BB874 的低 4 位


def row_key(x, y, tpl_low=TPL_LOW):
    return (0x8000
            | (((y >> 3) & 0x1F) << 10)
            | (((x >> 2) & 0x3F) << 4)
            | (tpl_low & 0x0F))


class Alloc:
    """对应 ADDR_V15_* 那一小撮 EWRAM 状态 + 两个函数。"""

    def __init__(self):
        self.rows = []          # [ [key, base], ... ]
        self.pooltop = POOL_LO
        self.prevkey = 0
        self.cursor = 0
        self.log = []           # 每次 alloc 的返回号
        self.refused = 0

    def begin(self, x, y):
        k = row_key(x, y)
        if k == self.prevkey:
            return
        # ① 结算上一行
        if self.prevkey != 0:
            for kk, b in self.rows:
                if kk == self.prevkey:
                    cur = self.cursor
                    if cur > b and (b + (cur - b)) > self.pooltop:
                        self.pooltop = b + (cur - b)
                    break
        # ② 取回/登记本行段基址
        idx = None
        for i, (kk, b) in enumerate(self.rows):
            if kk == k:
                idx = i
                break
        if idx is None:
            if len(self.rows) >= ROWS_MAX:
                self.cursor = POOL_LO
                self.prevkey = 0
                return
            self.rows.append([k, self.pooltop])
            idx = len(self.rows) - 1
            if self.pooltop + 2 <= POOL_HI:
                self.pooltop += 2
        self.cursor = self.rows[idx][1]
        self.prevkey = k

    def alloc(self, n):
        t = self.cursor
        if t < POOL_LO or t >= POOL_HI:
            self.refused += 1
            return 0
        if t + n > POOL_HI:
            self.refused += 1
            return 0
        self.cursor = t + n
        self.log.append(t)
        return t


def settings_screen():
    """设置页模型：7 行 × 16px 行距，每行「标签 run + 数值 run」。
    标签/数值都是独立字符串 ⇒ 各自一次 begin。每字 2 砖（12px 两段式 adv=2）。"""
    seq = []                      # [(x, y, 该 run 的字数)]
    labels = [5, 5, 5, 4, 5, 3, 4]     # 各行标签字数
    values = [3, 3, 3, 3, 3, 3, 3]     # 各行数值字数（普通/快/慢…）
    for r in range(7):
        y = 8 + r * 16
        seq.append((8, y, labels[r]))
        seq.append((104, y, values[r]))
    return seq


def run_pass(al):
    """走一趟整屏；返回本趟每个 run 拿到的砖号列表。"""
    per_run = []
    for (x, y, nc) in settings_screen():
        al.begin(x, y)
        got = []
        for _ in range(nc):
            got.append(al.alloc(2))     # 每字领 2 砖
        per_run.append(got)
    return per_run


def main():
    al = Alloc()
    passes = [run_pass(al) for _ in range(4)]

    ok = True

    # A. 幂等
    for i in range(1, len(passes)):
        if passes[i] != passes[0]:
            ok = False
            print("FAIL A: 第 %d 趟与第 1 趟砖号不同" % (i + 1))
            for r, (a, b) in enumerate(zip(passes[0], passes[i])):
                if a != b:
                    print("   run%-3d 趟1=%s" % (r, a))
                    print("          趟%d=%s" % (i + 1, b))
            break
    if ok:
        print("PASS A 幂等：4 趟重画的砖号序列逐字相同")
        print("        第 1 趟 run0 = %s% s" % (passes[0][0], ""))
        print("        第 4 趟 run0 = %s" % (passes[3][0],))

    # B. 不回卷
    allt = [t for p in passes for r in p for t in r if t]
    bad = [t for t in allt if not (POOL_LO <= t < POOL_HI)]
    if bad:
        ok = False
        print("FAIL B: 越界砖号 %s" % bad[:8])
    else:
        print("PASS B 不回卷：全部砖号落在 [%d, %d)，max=%d" % (POOL_LO, POOL_HI, max(allt)))

    # C. 不同行段不互撞（按行段分组比较占用区间）
    segs = []
    for (x, y, nc), got in zip(settings_screen(), passes[0]):
        k = row_key(x, y)
        lo, hi = got[0], got[-1] + 2
        segs.append((k, lo, hi, (x, y)))
    segs.sort(key=lambda s: s[1])
    ov = []
    for i in range(1, len(segs)):
        if segs[i][1] < segs[i - 1][2]:
            ov.append((segs[i - 1], segs[i]))
    if ov:
        ok = False
        print("FAIL C: %d 处行段重叠" % len(ov))
        for a, b in ov[:5]:
            print("   %s@%s 与 %s@%s 重叠" % (a[3], (a[1], a[2]), b[3], (b[1], b[2])))
    else:
        print("PASS C 不互撞：%d 个行段占用区间两两不相交" % len(segs))

    print("\n行段表（key, base, 实际占用）:")
    for k, b in al.rows:
        print("   key=%04X base=%d" % (k, b))
    print("pool_top = %d / %d（余 %d 砖）" % (al.pooltop, POOL_HI, POOL_HI - al.pooltop))
    print("拒发次数 = %d" % al.refused)

    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
