# -*- coding: utf-8 -*-
"""v22 方案 H 「块基准位置定号」离线判据（L1 静态）。

真值来源：.tmp/smp2.txt（设置页 22 个文本块的 (CUR_X, CUR_Y) 运行时采样，
win=0x0202E658 tb=1）。不手抄任何字模，只搬采样值。

判据：
  ① 22 块两两不同格 ⇒ 块基准两两不同（单射）
  ② 给定每块字数上界时，任意两块的号段不重叠
  ③ TB + n + 3 ≤ 1023（号不越出 charBase 块）
"""
import re
import sys

SPACE = 1024
ARROW_LO = 0xFE


def block_base(cur_x, cur_y):
    n = (cur_y >> 1) * 64 + cur_x * 2
    if n >= ARROW_LO:
        n += 2
    return n


def claim(tb, cur_x, cur_y, tile_offset):
    n = block_base(cur_x, cur_y) + tile_offset
    room = SPACE - tb
    while n + 3 > room:
        n -= room
    return tb + n


def cols_for(nchars, ink=11, advance=12):
    """nchars 个 11px 字、12px 步进 ⇒ 用到的 tile 列数（相位两段式）。"""
    px = 0
    cols = set()
    for _ in range(nchars):
        phase = px & 7
        w0 = min(8 - phase, ink)
        w1 = ink - w0
        adv = max(1, (phase + advance) >> 3)
        cols.add((px) // 8)
        if w1:
            cols.add((px) // 8 + 1)
        px += advance
    return sorted(cols)


def main():
    # ---- 采样真值 ----
    pairs = []
    seen = set()
    with open('.tmp/smp2.txt', encoding='utf-8') as f:
        for ln in f:
            m = re.match(r'SMP win=(\S+) tb=(\d+) a2=(\d+) a3=(\d+)', ln.strip())
            if not m:
                continue
            key = (int(m.group(3)), int(m.group(4)), int(m.group(2)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((int(m.group(3)), int(m.group(4)), int(m.group(2))))
    print('采样到不同 (CUR_X, CUR_Y, TB) 组合 = %d 个' % len(pairs))
    tb_set = sorted({p[2] for p in pairs})
    print('TB 取值 = %s' % tb_set)
    tb = tb_set[0] if len(tb_set) == 1 else None

    # ---- ① 块基准单射 ----
    base = {}
    for x, y, _ in pairs:
        base[(x, y)] = block_base(x, y)
    inv = {}
    bad = 0
    for k, v in base.items():
        if v in inv:
            print('  ❌ 基准撞车: %s 与 %s 都得 n=%d' % (k, inv[v], v))
            bad += 1
        inv[v] = k
    print('① 块基准两两不同 : %s（%d 个基准，%d 起撞车）'
          % ('✅' if bad == 0 else '❌', len(inv), bad))

    # ---- ② 号段不重叠（每块 1..6 字都试） ----
    print('② 号段重叠检查（按每块字数 1..6 枚举）：')
    worst = None
    for nch in range(1, 7):
        used = {}
        clash = []
        for x, y, _ in pairs:
            b = block_base(x, y)
            for c in cols_for(nch):
                for half in (0, 1):
                    t = b + c * 2 + half
                    if t in used and used[t] != (x, y):
                        clash.append((nch, t, used[t], (x, y)))
                    used[t] = (x, y)
        mark = '✅' if not clash else '❌ %d 处' % len(clash)
        print('   %d 字/块: %-8s 用号 %d 个' % (nch, mark, len(used)))
        if clash:
            for c in clash[:5]:
                print('      撞号 %d: %s vs %s' % (c[1], c[2], c[3]))
        worst = (nch, len(used))

    # ---- ③ 越界检查 ----
    print('③ 越界检查（TB + n + 3 ≤ 1023）：')
    for nch in (1, 3, 6):
        mx = 0
        for x, y, tbv in pairs:
            b = block_base(x, y)
            off = max(cols_for(nch)) * 2 + 1
            t = claim(tbv, x, y, off)
            mx = max(mx, t + 1)
        key = '✅' if mx <= SPACE - 1 else '❌'
        print('   %d 字/块: 最大号 = %d  %s' % (nch, mx, key))

    # ---- 参考：最坏 TB 的展开 ----
    print('④ 各 TB 下的号上界（满屏最坏 n = 9*64 + 29*2 = %d）:' % (9 * 64 + 29 * 2))
    for tbv in (1, 144, 256, 400, 440, 656, 704, 752):
        n_raw = 9 * 64 + 29 * 2
        n = n_raw + (2 if n_raw >= ARROW_LO else 0)
        room = SPACE - tbv
        wraps = 0
        while n + 3 > room:
            n -= room
            wraps += 1
        print('   TB=%-4d room=%-4d 满屏 n=%-4d 折叠 %d 次 ⇒ 落在号 %d（+3 ≤ 1023 %s）'
              % (tbv, room, n_raw + (2 if n_raw >= ARROW_LO else 0), wraps, tbv + n,
                 '✅' if tbv + n + 3 <= 1023 else '❌'))


if __name__ == '__main__':
    main()
