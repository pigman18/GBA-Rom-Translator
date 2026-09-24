# -*- coding: utf-8 -*-
"""v11 第一批改动：把池下界抬出官方固定占用区 + 修相位行键 + 修扫描范围。

背景（逐指令反汇编 + docs/UI分配函数登记_20260910.md §7.1 实测）：
  官方在 cb0 低段是固定占用的：
    [1, 513)   tm1 日文字模 atlas（InitWindowTileData 铺满 256 槽 x 2 tile）
    [512, 521) 窗口框 9 tile  （ChsAllocFrame9  base = 512）
    [603, 617) 对话框框 14 tile（ChsAllocDlg14  base = 603）
  旧池下界 lo = 0x100(256) 直接压在 atlas 后半与两种框上 => 分配器发出去的号
  会落进官方框（框表项那一刻不在活引用位图里，拦不住）
  => 实机「背包移动光标一会再开菜单撞 UI」。

自证：每处替换前断言唯一匹配；写回保持原换行风格。
"""
import io
import sys

P = r'configs/POKEMON_RUBY_AXVJ00/hook/src/text/tile_alloc.c'
raw = open(P, 'rb').read()
crlf = b'\r\n' in raw
src = raw.decode('utf-8').replace('\r\n', '\n')
orig_len = len(src)

LOG = []


def rep(old, new, tag):
    global src
    n = src.count(old)
    if n != 1:
        print('FAIL[%s]: 匹配 %d 次（要求恰好 1）' % (tag, n))
        sys.exit(2)
    src = src.replace(old, new)
    LOG.append(tag)
    print('OK  [%s]' % tag)


# ---------------------------------------------------------------- 1) 池下界
rep(
    "    lo = 0x100u;                  /* 起点避开官方 atlas 主体；越界部分由 VRAM 校验兜底 */",
    """    /* 🔴 2026-09-20（v11）：下界从 0x100(256) 抬到 617。
     * 官方在 cb0 低段是**固定占用**的（逐指令 + 文档 UI分配函数登记 §7.1 实测）：
     *   [1, 513)    tm1 日文字模 atlas（InitWindowTileData 铺满 256 槽 × 2 tile）
     *   [512, 521)  窗口框 9 tile   （ChsAllocFrame9  base = 512）
     *   [603, 617)  对话框框 14 tile（ChsAllocDlg14  base = 603）
     * 旧值 256 压在 atlas 后半与两种框之上 ⇒ 发出去的号会落进官方框
     * （框的表项那一刻不在活引用位图里，bm 拦不住）⇒ 实机「背包移动光标
     * 一会再开菜单撞 UI」。617 = 官方最高占用 617 之后的第一个空位。
     * 可用区 [617,1024) = 407 tile ≈ 101 个汉字（每字 4 tile）。 */
    lo = 617u;""",
    'lo=617',
)

# ---------------------------------------------------------------- 2) 相位行键
rep(
    """    uint16_t row = tpl
        ? (uint16_t)((uintptr_t)tpl
                     ^ ((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
                     ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y))
        : 0u;""",
    """    /* 🔴🔴 2026-09-20（v11）：行键必须含 **win 实例**，不能只用 tpl。
     * 同场景里多个窗口共用同一模板是常态（实测 7 个模板服务几十个窗口）⇒
     * 只用 tpl 时，两个窗口在同一行打印会得到相同行键 ⇒ 相位**不复位** ⇒
     * 第二个窗口的第一个字走 phase!=0 分支，复用 v8_phase_last_tile()
     * （= 第一个窗口行尾字的尾列 tile）⇒ 它的字形写进**第一个窗口的格子** ⇒
     * 实机「右侧面板顶部出现左侧面板内容」（2026-09-20 用户截图）。
     * win 指针唯一标识窗口实例，把它并进行键即消除这条路径。 */
    uint16_t row = 0u;
    if (tpl)
        row = (uint16_t)(((uintptr_t)win >> 2) ^ ((uintptr_t)tpl >> 3))
            ^ (uint16_t)((uint16_t)win_u8(win, WIN_CURSOR_Y) << 8)
            ^ (uint16_t)win_u8(win, WIN_CURSOR_TILE_Y);""",
    'phase-row-key',
)

# ------------------------------------------------- 3) 带 charBase 换算的位图标记
rep(
    """/* 表项扫描（活引用收集）：优先 u32 读（VRAM 32-bit 总线，一次取 2 表项，
 * 成本减半）；n 为表项数。地址非 4 对齐时退回 u16 逐项。 */
static void v8_scan_entries(const uint16_t *sb, unsigned n, volatile uint8_t *bm)
{
    unsigned i;

    if ((((uintptr_t)sb) & 3u) == 0u) {
        const volatile uint32_t *p = (const volatile uint32_t *)(const void *)sb;
        for (i = 0; i + 1u < n; i += 2u) {
            uint32_t w = p[i >> 1];
            uint16_t t0 = (uint16_t)(w & 0x3FFu);
            uint16_t t1 = (uint16_t)((w >> 16) & 0x3FFu);
            if (t0 != 0u)
                v8_bit_set(bm, t0);
            if (t1 != 0u)
                v8_bit_set(bm, t1);
        }
        if (i < n) {              /* n 为奇数时的收尾（实际 n 恒偶） */
            uint16_t t = sb[i] & 0x3FFu;
            if (t != 0u)
                v8_bit_set(bm, t);
        }
    } else {
        for (i = 0; i < n; i++) {
            uint16_t t = sb[i] & 0x3FFu;
            if (t != 0u)
                v8_bit_set(bm, t);
        }
    }
}""",
    """/* 带 charBase 换算的位图标记。
 * tilemap 表项里的号是**相对该 BG 自己的 charBase** 的；本窗位图用「相对本窗
 * charBase」的号 ⇒ 需要加 (bgCB - winCB)*512 才能比较。换算后落在 [1,1024)
 * 之外（属于别的 charBlock，与本窗分配区无关）⇒ 直接忽略。 */
static void v8_bit_set_delta(volatile uint8_t *bm, int t, int delta)
{
    int v = t + delta;

    if (v > 0 && v < 1024)
        v8_bit_set(bm, (uint16_t)v);
}

/* 表项扫描（活引用收集）：优先 u32 读（VRAM 32-bit 总线，一次取 2 表项，
 * 成本减半）；n 为表项数。地址非 4 对齐时退回 u16 逐项。
 * delta = (该 BG 的 charBase - 本窗 charBase) * 512（v11 新增，见调用点）。 */
static void v8_scan_entries(const uint16_t *sb, unsigned n, int delta,
                            volatile uint8_t *bm)
{
    unsigned i;

    if ((((uintptr_t)sb) & 3u) == 0u) {
        const volatile uint32_t *p = (const volatile uint32_t *)(const void *)sb;
        for (i = 0; i + 1u < n; i += 2u) {
            uint32_t w = p[i >> 1];
            v8_bit_set_delta(bm, (int)(w & 0x3FFu), delta);
            v8_bit_set_delta(bm, (int)((w >> 16) & 0x3FFu), delta);
        }
        if (i < n)                /* n 为奇数时的收尾（实际 n 恒偶） */
            v8_bit_set_delta(bm, (int)(sb[i] & 0x3FFu), delta);
    } else {
        for (i = 0; i < n; i++)
            v8_bit_set_delta(bm, (int)(sb[i] & 0x3FFu), delta);
    }
}""",
    'scan-entries+delta',
)

# ---------------------------------------------------------------- 4) ① 调用点
rep(
    """        if (tilemap)
            v8_scan_entries(tilemap, 1024u, bm);""",
    """        if (tilemap)
            v8_scan_entries(tilemap, 1024u, 0, bm);   /* 本窗自己的 tilemap：delta=0 */""",
    'call-site-1',
)

# ---------------------------------------------------------------- 5) ② 扫描循环
rep(
    """            cnt = REG_V8_BGxCNT((uint8_t)bg);
            if (((cnt >> 2) & 3u) != cb)
                continue;
            sb = (const uint16_t *)(uintptr_t)
                 (0x06000000u + (unsigned)((cnt >> 8) & 0x1Fu) * 0x800u);
            size = (unsigned)(cnt >> 14) & 3u;
            n = (size == 0u) ? 1024u : (size == 3u) ? 4096u : 2048u;
            v8_scan_entries(sb, n, bm);""",
    """            /* 🔴 v11：不再用 `charBase != cb ⇒ continue` 跳过。
             * 本窗分配区相对 cb0 是 [lo,1024)，它**跨越 cb0 尾部与 cb1** ⇒
             * 落在别的 charBlock 的 BG 引用同样可能与分配区重叠（实测本场景
             * BG 用 cb0/cb2/cb3，但那是**逐场景**观测，不能当常数）。
             * 表项号是相对该 BG 自己 charBase 的 ⇒ 按 (bgCB - winCB)*512 换算
             * 到本窗号空间再标记；越界的由 v8_bit_set_delta 丢弃。 */
            cnt = REG_V8_BGxCNT((uint8_t)bg);
            {
                int delta = ((int)((cnt >> 2) & 3u) - (int)cb) * 512;

                sb = (const uint16_t *)(uintptr_t)
                     (0x06000000u + (unsigned)((cnt >> 8) & 0x1Fu) * 0x800u);
                size = (unsigned)(cnt >> 14) & 3u;
                n = (size == 0u) ? 1024u : (size == 3u) ? 4096u : 2048u;
                v8_scan_entries(sb, n, delta, bm);
            }""",
    'call-site-2+delta',
)

out = src if not crlf else src.replace('\n', '\r\n')
io.open(P, 'w', encoding='utf-8', newline='').write(out)

# ---------------------------------------------------------------- 自证
chk = io.open(P, encoding='utf-8').read()
assert 'lo = 617u;' in chk, 'lo 未落盘'
assert 'v8_bit_set_delta(bm, (int)(w & 0x3FFu), delta)' in chk, '位图换算未落盘'
assert '(uintptr_t)win >> 2' in chk, '行键未落盘'
assert chk.count('v8_scan_entries(') == 3, '调用点数量异常: %d' % chk.count('v8_scan_entries(')
assert '0x100u' not in chk, '仍有 0x100 残留'

print()
print('换行风格      : %s' % ('CRLF' if crlf else 'LF'))
print('改动处        : %d  %s' % (len(LOG), ', '.join(LOG)))
print('文件长度      : %d -> %d 字符' % (orig_len, len(src)))
print('自证          : 全部通过')
