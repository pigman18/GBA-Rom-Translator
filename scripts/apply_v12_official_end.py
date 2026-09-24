# -*- coding: utf-8 -*-
"""v12：把「硬编码池下界 617」换成「运行时推导的官方资产上界」，并给复用闸门加
「官方资产区永不复用」判据。

依据（逐指令实证，见 tile_alloc.c / PrintNextChar_hook.c 内注释）：
  TextLoadWindowTemplate 0x08002950  跳转表 @0x080029B4  → cap（font0/3=512，其余=256）
  InitWindowTileData     0x08002A50  跳转表 @0x08002A74  → 落点公式（用 win[0x08] 选 font）
  文档 UI分配函数登记_20260910 §7.3  → 框 = [cap, cap+9) ∪ [cap+9, cap+23)
⇒ 官方上界 = max(startOffset + cap, cap + 23)
      font0/3        ⇒ max(513, 535) = 535
      font1/2/4/5/6  ⇒ max(257, 279) = 279

每处替换：断言 old 全文恰好出现 1 次 → 替换 → 落盘 → 回读自证。
"""
import io
import os
import sys

ROOT = r'C:\code\GBA-Rom-Translator'
H = os.path.join(ROOT, r'configs\POKEMON_RUBY_AXVJ00\hook')

F_GAME_H = os.path.join(H, r'include\game.h')
F_ALLOC_C = os.path.join(H, r'src\text\tile_alloc.c')
F_ALLOC_H = os.path.join(H, r'include\tile_alloc.h')
F_PNC_C = os.path.join(H, r'src\text\PrintNextChar_hook.c')


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def sub1(text, old, new, tag, crlf_ok=True):
    """要求 old 恰好出现 1 次（CRLF 文件里把 old 的 \\n 视作 \\r?\\n）。"""
    variants = [old]
    if '\r\n' not in old:
        variants.append(old.replace('\n', '\r\n'))
    total = 0
    picked = None
    for v in variants:
        c = text.count(v)
        total += c
        if c == 1 and picked is None:
            picked = v
    if total != 1:
        print('!! [%s] 匹配数 = %d（要求 1）—— 中止' % (tag, total))
        sys.exit(2)
    return text.replace(picked, new if '\r\n' not in picked else new.replace('\n', '\r\n')), picked


def main():
    ok = []

    # ───────────────────────── game.h ─────────────────────────
    s = read(F_GAME_H)

    old = ('#define WIN_TILE_BASE       0x16\n'
           '#define WIN_TILE_OFFSET     0x18\n')
    new = ('#define WIN_TILE_BASE       0x16\n'
           '#define WIN_TILE_OFFSET     0x18\n'
           '/* \U0001F534 v12\uff1afont \u5206\u6d3e\u7d22\u5f15\u3002`InitWindowTileData 0x08002A50` \u5c31\u662f\u62ff\n'
           ' * `win[0x08]` \u67e5\u8df3\u8f6c\u8868 @0x08002A74 \u51b3\u5b9a\u300c\u5b57\u6a21\u843d\u70b9\u600e\u4e48\u7b97\u3001cap \u591a\u5927\u300d\n'
           ' * \uff080x08002A5E \u9010\u6307\u4ee4\u5b9e\u8bc1\uff09\u3002\u4e0e `TextLoadWindowTemplate 0x08002950` \u7528\u7684 `tpl[9]`\n'
           ' * \u662f\u540c\u4e00\u4e2a\u6570\uff08\u7a97\u53e3\u5efa\u65f6\u4ece tpl \u62f7\u5165\uff09\u3002 */\n'
           '#define WIN_FONT_INDEX      0x08\n')
    s, _ = sub1(s, old, new, 'game.h WIN_FONT_INDEX')
    ok.append('game.h WIN_FONT_INDEX')

    old = ('/* --- \u624b\u5de5\u8ffd\u52a0\uff08\u975e\u751f\u6210\u533a\uff09\uff1av9 \u961f\u5217\u5206\u914d\u5668\u72b6\u6001\u5757 0x0203FF4A..0x0203FF55 --- */\n'
           '#define ADDR_V8Q_MAGIC                     0x0203FF4Au\n')
    new = ('/* --- \u624b\u5de5\u8ffd\u52a0\uff08\u975e\u751f\u6210\u533a\uff09\uff1av9 \u961f\u5217\u5206\u914d\u5668\u72b6\u6001\u5757 0x0203FF4A..0x0203FF55 ---\n'
           ' * \U0001F534 v12\uff1a`ADDR_V8Q_HEAD/CURSOR/END`\uff080x0203FF50/52/54\uff09\u5df2**\u96f6\u5f15\u7528** \u21d2\n'
           ' * \u56de\u6536\u5176\u7a7a\u95f4\uff0c\u6539\u653e v12 \u7684\u300c\u5b98\u65b9\u8d44\u4ea7\u4e0a\u754c\u300d\u8bb0\u5f55\uff08\u573a\u666f\u5185\u5355\u8c03\u9012\u589e\uff0c\n'
           ' * `v8_alloc_begin` \u6e05\u96f6\uff09\u3002\u4e0d\u8981\u518d\u542f\u7528\u90a3\u4e09\u4e2a\u65e7\u5b8f\u3002 */\n'
           '#define ADDR_V12_OFF_END                   0x0203FF50u\n'
           '#define ADDR_V8Q_MAGIC                     0x0203FF4Au\n')
    s, _ = sub1(s, old, new, 'game.h ADDR_V12_OFF_END')
    ok.append('game.h ADDR_V12_OFF_END')

    write(F_GAME_H, s)
    assert 'ADDR_V12_OFF_END' in read(F_GAME_H) and 'WIN_FONT_INDEX' in read(F_GAME_H)

    # ───────────────────────── tile_alloc.h ─────────────────────────
    s = read(F_ALLOC_H)
    old = 'int v8_ours_has(uint16_t tile);\n'
    new = ('int v8_ours_has(uint16_t tile);\n'
           '\n'
           '/* ---- v12\u300c\u5b98\u65b9\u8d44\u4ea7\u4e0a\u754c\u300d\uff1a\u672c\u7a97\u53ef\u7528\u7684\u6700\u4f4e\u53f7 ----------------------------\n'
           ' * \u5b98\u65b9\u5728**\u672c\u7a97 charBase \u53f7\u7a7a\u95f4**\u91cc\u5360\u7684\u6700\u540e\u4e00\u6bb5\uff08\u9010\u6307\u4ee4\u5b9e\u8bc1\uff0c\u975e\u4f30\u7b97\uff09\uff1a\n'
           ' *   atlas = [startOffset, startOffset+cap)  cap: font0/3 = 512\uff0c\u5176\u4f59 = 256\n'
           ' *   \u6846    = [cap, cap+23)                   \uff08cap \u662f\u7edd\u5bf9\u503c\uff0c\u4e0e startOffset \u65e0\u5173\uff09\n'
           ' * \u21d2 \u4e0a\u754c = max(startOffset+cap, cap+23)   font0/3 \u21d2 535\uff1bfont1/2/4/5 \u21d2 279\n'
           ' * \U0001F534 \u8bed\u4e49\uff1a`t >= v8_official_end(win)` \u21d2 t \u53ea\u53ef\u80fd\u662f\u300c\u6c60\u91cc\u7684\u53f7\u300d\uff1b\n'
           ' *    `t <  \u4e0a\u754c` \u21d2 t \u4e00\u5b9a\u662f\u5b98\u65b9\u8d44\u4ea7\uff08atlas \u5b57\u6a21 / \u7a97\u53e3\u6846\uff09\uff0c**\u7edd\u4e0d\u53ef\u5199**\u3002\n'
           ' *    \u6e32\u67d3\u5c42\u62ff\u5b83\u5f53\u590d\u7528\u95f8\u95e8\uff1a\u5b98\u65b9\u53f7\u5373\u4f7f\u4e0e t+dlow \u6784\u6210\u7ad6\u5bf9\n'
           ' *    \uff08\u65e5\u6587\u5b57\u6a21\u4e5f\u662f\u7ad6\u5bf9\uff09\uff0c\u4e5f\u4e0d\u4f1a\u88ab\u8bef\u5224\u6210\u300c\u6211\u4eec\u7684\u69fd\u300d\u2014\u2014\n'
           ' *    \u8fd9\u6b63\u662f\u5b9e\u673a font4 \u5b57\u6a21\u88ab\u8986\u76d6\u7684\u6839\u56e0\u3002 */\n'
           'uint16_t v8_official_end(TextPrinter *win);\n')
    s, _ = sub1(s, old, new, 'tile_alloc.h v8_official_end')
    ok.append('tile_alloc.h v8_official_end')
    write(F_ALLOC_H, s)
    assert 'v8_official_end' in read(F_ALLOC_H)

    # ───────────────────────── tile_alloc.c ─────────────────────────
    s = read(F_ALLOC_C)

    # (1) 新增 v8_official_end / v8_official_end_max，插在 v8_alloc_hi 之后
    old = ('static uint16_t v8_alloc_hi(uint8_t char_base)\n'
           '{\n'
           '    unsigned hi = (char_base < 4u) ? (unsigned)(4u - char_base) * 512u : 0u;\n'
           '    if (hi > 1024u)\n'
           '        hi = 1024u;\n'
           '    return (uint16_t)hi;\n'
           '}\n')
    new = old + (
        '\n'
        '/* ============================================================================\n'
        ' * v12\uff1a\u5b98\u65b9\u5728\u672c\u7a97\u53f7\u7a7a\u95f4\u91cc\u7684\u8d44\u4ea7\u4e0a\u754c\uff08**\u9010\u6307\u4ee4\u5b9e\u8bc1**\uff0c\u4e0d\u662f\u4f30\u7b97\uff09\n'
        ' *\n'
        ' * \u4f9d\u636e\uff1a`TextLoadWindowTemplate 0x08002950`\uff08\u8df3\u8f6c\u8868 @0x080029B4\uff09\u9009 cap\uff1b\n'
        ' *      `InitWindowTileData   0x08002A50`\uff08\u8df3\u8f6c\u8868 @0x08002A74\uff09\u51b3\u5b9a\u843d\u70b9\uff1b\n'
        ' *      `SetBaseTileNum cap`      \u2192 \u6846 [cap, cap+9)\uff1b\n'
        ' *      `SetDlgFrameBaseTileNum`  \u2192 \u6846 [cap+9, cap+23)\uff1b\n'
        ' *      \uff08\u6846\u57fa\u5740 = cap\uff0ccap \u662f**\u7edd\u5bf9\u503c**\uff0c\u4e0e startOffset \u65e0\u5173\uff1b\u89c1\u53d6\u8bc1\u6587\u6863 \u00a77.3\uff09\n'
        ' *\n'
        ' *   \u2022 \u56fe\u96c6\uff1a\u8d77\u70b9 = `win[0x16]`\uff08TILE_BASE = startOffset\uff0c\u5b9e\u6d4b\u6052\u4e3a 1\uff09\uff0c\n'
        ' *     \u6bcf\u4e2a glyph \u5360 1\uff5e2 tile\uff0c\u94fa 256 \u4e2a glyph\uff1a\n'
        ' *       font0/3              \u21d2 cap = 512\uff08glyph \u00d7 2 tile\uff0c\u7ad6\u76f4\u5bf9\uff09\n'
        ' *       font1/2/4/5/6        \u21d2 cap = 256\uff08glyph \u00d7 1 tile\uff09\n'
        ' *   \u2022 \u6846\uff1a[cap, cap+23)\u3002\n'
        ' * \u21d2 \u4e0a\u754c = max(startOffset + cap, cap + 23)\n'
        ' *       font0/3 \u21d2 max(513, 535) = 535\n'
        ' *       \u5176\u4f59    \u21d2 max(257, 279) = 279\n'
        ' *\n'
        ' * \U0001F534 \u8fd9**\u4e0d\u662f\u62ac\u6c34\u4f4d**\uff1a\u62ac\u6c34\u4f4d\u662f\u51ed\u611f\u89c9\u628a\u4e00\u6bb5\u5212\u6b7b\uff08\u65e7\u503c\u786c\u7f16\u7801 617\uff0c\n'
        ' *   \u5728 font1/4 \u573a\u666f\u767d\u4e22 [279,617) \u5171 338 \u4e2a\u53f7 = \u7ea6 84 \u4e2a\u6c49\u5b57\uff09\u3002\u8fd9\u91cc\u662f\n'
        ' *   **\u6309\u5b98\u65b9\u9010\u6307\u4ee4\u5b9e\u8bc1\u7684\u8d44\u4ea7\u8fb9\u754c**\u7cbe\u786e\u53d6\u5230\u5b98\u65b9\u6700\u540e\u4e00\u4e2a\u5360\u7528\u53f7\uff1b\n'
        ' *   \u5230\u5e95\u591a\u5c11**\u7531\u8fd0\u884c\u65f6 win \u7684\u771f\u5b9e\u5b57\u6bb5\u7b97\u51fa\u6765**\u3002\n'
        ' * \U0001F534 \u4fdd\u5e95\uff1a\u7b97\u51fa\u7684\u4e0a\u754c\u82e5\u8d85\u51fa [1,1024) \u4e00\u5f8b\u622a\u65ad\u3002\n'
        ' * ==========================================================================*/\n'
        'uint16_t v8_official_end(TextPrinter *win)\n'
        '{\n'
        '    uint8_t font;\n'
        '    uint16_t off, cap, e1, e2;\n'
        '\n'
        '    if (!win)\n'
        '        return 0u;\n'
        '    font = win_u8(win, WIN_FONT_INDEX);\n'
        '    /* \u975e 0/3 \u4e00\u5f8b\u6309 512 \u4fdd\u5b88\u53d6\uff08font \u8d85\u51fa 0..5 \u8bf4\u660e\u5f02\u5e38\uff0c\u5b81\u53ef\u591a\u907f\uff09 */\n'
        '    cap  = (font == 0u || font == 3u) ? 512u : ((font > 5u) ? 512u : 256u);\n'
        '    off  = win_u16(win, WIN_TILE_BASE);\n'
        '    e1   = (uint16_t)(off + cap);       /* \u56fe\u96c6\u5c3e */\n'
        '    e2   = (uint16_t)(cap + 23u);       /* \u6846\u5c3e\uff08\u7edd\u5bf9\u503c\uff09 */\n'
        '    off  = (e1 > e2) ? e1 : e2;\n'
        '    if (off < 1u)\n'
        '        off = 1u;\n'
        '    if (off > 1024u)\n'
        '        off = 1024u;                    /* \u4fdd\u5e95\uff1a\u4e0d\u5f97\u8d8a\u754c */\n'
        '    return off;\n'
        '}\n'
        '\n'
        '/* \u573a\u666f\u5185\u5355\u8c03\u9012\u589e\u7684\u5b98\u65b9\u4e0a\u754c\uff1a\u540c\u4e00\u573a\u666f\u53ef\u80fd\u51fa\u73b0\u591a\u79cd font \u7684\u7a97\u53e3\uff0c\n'
        ' * \u53d6\u5df2\u89c1\u6700\u5927\u503c\uff08\u5b98\u65b9 atlas \u662f\u5168\u5c40\u4e00\u4efd\uff0c\u6700\u540e\u94fa\u7684 font \u51b3\u5b9a\u5360\u7528\uff1b\n'
        ' * \u53d6 max = \u4e0d\u4f1a\u56e0\u540e\u5230\u7684\u5927 atlas \u628a\u5df2\u53d1\u51fa\u53bb\u7684\u53f7\u8986\u76d6\uff09\u3002\n'
        ' * \u6e05\u96f6\u65f6\u673a = `v8_alloc_begin`\uff08\u573a\u666f/\u4f1a\u8bdd\u8fb9\u754c\uff09\u3002 */\n'
        'static uint16_t v8_official_end_max(TextPrinter *win)\n'
        '{\n'
        '    volatile uint16_t *st = (volatile uint16_t *)ADDR_V12_OFF_END;\n'
        '    uint16_t e = v8_official_end(win);\n'
        '\n'
        '    if (e > *st)\n'
        '        *st = e;\n'
        '    return *st;\n'
        '}\n'
        '\n'
        '/* v12\uff1aours \u8d26\u672c\u91cd\u5efa = \u672c\u7a97 tilemap \u91cc\u5f15\u7528\u7684\u300c\u6c60\u5185\u300d\u53f7\u3002\n'
        ' * \U0001F534 \u4e3a\u4ec0\u4e48\u5fc5\u987b\u91cd\u5efa\uff08\u800c\u4e0d\u662f v10 \u7684\u300c\u6301\u4e45\u4e0d\u6e05\u300d\uff09\uff1a\n'
        ' *   v10 \u628a ours \u6539\u6210\u6301\u4e45\u540e\uff0c\u5b83\u7684\u8bed\u4e49\u53d8\u6210\u300c\u672c\u4f1a\u8bdd**\u6240\u6709\u7a97\u53e3**\u53d1\u8fc7\u7684\u53f7\u300d\u5e76\u96c6\u3002\n'
        ' *   \u4e8e\u662f\u53f3\u9762\u677f\u7684\u683c\u5b50\u53ea\u8981\u6b8b\u7559\u7740\u5de6\u9762\u677f\u7528\u8fc7\u7684\u53f7\uff0c`chs_cell_slot` \u4e09\u6761\n'
        ' *   \u5224\u636e\u5168\u8fc7 \u21d2 \u76f4\u63a5\u590d\u7528 \u21d2 **\u4e24\u5757\u9762\u677f\u5171\u7528\u540c\u4e00\u6279 tile** \u21d2 \u5b9e\u673a\n'
        ' *   \u300c\u53f3\u4fa7\u9762\u677f\u9876\u90e8\u51fa\u73b0\u5de6\u4fa7\u9762\u677f\u5185\u5bb9\u300d\u4e0e\u300c118\u53f7\u9053\u8def\u5e76\u6392\u91cd\u590d\u300d\u3002\n'
        ' * \u91cd\u5efa\u540e ours \u53ea\u542b**\u672c\u7a97\u5f53\u524d\u771f\u5728\u663e\u793a**\u7684\u6211\u4eec\u7684\u5b57 \u21d2 \u8de8\u7a97\u53e3\u6c61\u67d3\u6d88\u5931\u3002\n'
        ' * \uff08v9.1 \u90a3\u6b21\u300c\u91cd\u5efa ours \u21d2 \u6c60\u53ea\u51fa\u4e0d\u8fdb\u300d\u7684\u6839\u56e0\u662f\u5f53\u65f6 `v8_tile_usable` \u7b2c\u2463\u6761\n'
        ' *  \u628a\u65e0\u4e3b\u6570\u636e**\u6807\u6b7b\u4e3a\u4e0d\u53ef\u7528**\uff1bv10.1 \u5df2\u5220\u6389\u90a3\u6761\uff0c\u91cd\u5efa\u5df2\u65e0\u6b64\u526f\u4f5c\u7528\u3002\uff09 */\n'
        'static void v8_ours_rebuild(const uint16_t *tm, unsigned n, uint16_t off)\n'
        '{\n'
        '    unsigned i;\n'
        '\n'
        '    for (i = 0; i < n; i++) {\n'
        '        uint16_t t = (uint16_t)(tm[i] & 0x3FFu);\n'
        '        if (t >= off && t < 1024u)\n'
        '            v8_ours_add(t, 1u);\n'
        '    }\n'
        '}\n')
    s, _ = sub1(s, old, new, 'tile_alloc.c v8_official_end')
    ok.append('tile_alloc.c v8_official_end')

    # (2) begin：ours 重建 + 上界清零
    old = ('    v8_bit_clear_all(bm);\n'
           '\n'
           '    /* \u2460 win \u81ea\u8eab tilemap */\n'
           '    {\n'
           '        const uint16_t *tilemap = (const uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);\n'
           '        if (tilemap)\n'
           '            v8_scan_entries(tilemap, 1024u, 0, bm);   /* \u672c\u7a97\u81ea\u5df1\u7684 tilemap\uff1adelta=0 */\n'
           '    }\n')
    new = ('    v8_bit_clear_all(bm);\n'
           '\n'
           '    /* \u2460 win \u81ea\u8eab tilemap\uff08\u6d3b\u5f15\u7528 + ours \u91cd\u5efa\uff09 */\n'
           '    {\n'
           '        const uint16_t *tilemap = (const uint16_t *)(uintptr_t)win_u32(tpl, TPL_TILEMAP);\n'
           '        if (tilemap)\n'
           '            v8_scan_entries(tilemap, 1024u, 0, bm);   /* \u672c\u7a97\u81ea\u5df1\u7684 tilemap\uff1adelta=0 */\n'
           '\n'
           '        /* \U0001F534 v12\uff1aours **\u91cd\u5efa**\uff08\u4e0d\u518d\u8de8\u7a97\u53e3\u6301\u4e45\uff09\u3002\n'
           '         * \u65e7\u884c\u4e3a\uff08v10\uff09\u662f\u300cours \u4e0d\u6e05\u300d\uff0c\u7406\u7531\u662f\u62c5\u5fc3\u91cd\u73b0 v9.1 \u7684\n'
           '         * \u641e\u7a7a\u4e8b\u6545\uff1b\u4f46\u90a3\u6b21\u7684\u526f\u4f5c\u7528\u6765\u81ea\u5f53\u65f6\u5224\u5b9a\u91cc\u7684\n'
           '         * \u300c\u65e0\u4e3b\u6570\u636e\u6807\u6b7b\u300d\uff0c\u90a3\u6761\u5df2\u5728 v10.1 \u5220\u9664\u3002\u800c\u6301\u4e45\u5e26\u6765\u7684\n'
           '         * \u8de8\u7a97\u53e3\u6c61\u67d3\u662f**\u5f53\u524d\u5b9e\u673a\u4e32\u6270\u7684\u76f4\u63a5\u539f\u56e0**\uff0c\u5fc5\u987b\u91cd\u5efa\u3002 */\n'
           '        v8_ours_clear_all();\n'
           '        if (tilemap)\n'
           '            v8_ours_rebuild(tilemap, 1024u, v8_official_end(win));\n'
           '    }\n'
           '\n'
           '    /* v12\uff1a\u5b98\u65b9\u8d44\u4ea7\u4e0a\u754c\u5728\u573a\u666f\u8fb9\u754c\u6e05\u96f6\uff08\u573a\u666f\u5185\u5355\u8c03\u9012\u589e\uff09 */\n'
           '    *(volatile uint16_t *)ADDR_V12_OFF_END = 0u;\n')
    s, _ = sub1(s, old, new, 'tile_alloc.c begin ours rebuild')
    ok.append('tile_alloc.c begin ours rebuild')

    # (3) alloc_n：lo 去硬编码
    old = ('    /* \U0001F534 2026-09-20\uff08v11\uff09\uff1a\u4e0b\u754c\u4ece 0x100(256) \u62ac\u5230 617\u3002\n'
           '     * \u5b98\u65b9\u5728 cb0 \u4f4e\u6bb5\u662f**\u56fa\u5b9a\u5360\u7528**\u7684\uff08\u9010\u6307\u4ee4 + \u6587\u6863 UI\u5206\u914d\u51fd\u6570\u767b\u8bb0 \u00a77.1 \u5b9e\u6d4b\uff09\uff1a\n'
           '     *   [1, 513)    tm1 \u65e5\u6587\u5b57\u6a21 atlas\uff08InitWindowTileData \u94fa\u6ee1 256 \u69fd \u00d7 2 tile\uff09\n'
           '     *   [512, 521)  \u7a97\u53e3\u6846 9 tile   \uff08ChsAllocFrame9  base = 512\uff09\n'
           '     *   [603, 617)  \u5bf9\u8bdd\u6846\u6846 14 tile\uff08ChsAllocDlg14  base = 603\uff09\n'
           '     * \u65e7\u503c 256 \u538b\u5728 atlas \u540e\u534a\u4e0e\u4e24\u79cd\u6846\u4e4b\u4e0a \u21d2 \u53d1\u51fa\u53bb\u7684\u53f7\u4f1a\u843d\u8fdb\u5b98\u65b9\u6846\n'
           '     * \uff08\u6846\u7684\u8868\u9879\u90a3\u4e00\u523b\u4e0d\u5728\u6d3b\u5f15\u7528\u4f4d\u56fe\u91cc\uff0cbm \u62e6\u4e0d\u4f4f\uff09\u21d2 \u5b9e\u673a\u300c\u80cc\u5305\u79fb\u52a8\u5149\u6807\n'
           '     * \u4e00\u4f1a\u518d\u5f00\u83dc\u5355\u649e UI\u300d\u3002617 = \u5b98\u65b9\u6700\u9ad8\u5360\u7528 617 \u4e4b\u540e\u7684\u7b2c\u4e00\u4e2a\u7a7a\u4f4d\u3002\n'
           '     * \u53ef\u7528\u533a [617,1024) = 407 tile \u2248 101 \u4e2a\u6c49\u5b57\uff08\u6bcf\u5b57 4 tile\uff09\u3002 */\n'
           '    lo = 617u;\n')
    new = ('    /* \U0001F534\U0001F534 2026-09-20\uff08v12\uff09\uff1a\u53bb\u6389\u786c\u7f16\u7801\u4e0b\u754c\u3002\n'
           '     * v11 \u7684 `lo = 617u` \u662f**\u62ac\u6c34\u4f4d**\uff1a\u4e0d\u7ba1\u672c\u573a\u666f\u5b98\u65b9\u5230\u5e95\u5360\u4e86\u591a\u5c11\uff0c\n'
           '     * \u4e00\u5f8b\u628a [256,617) \u5212\u6b7b\uff08\u800c 617 \u8fd8\u662f\u6309 tm3 \u7684\u6846\u5c3e\u7b97\u7684\uff0c\u5728\n'
           '     * tm1 \u573a\u666f\u4e0b\u767d\u4e22\u4e86 [535,617) \u5171 82 \u4e2a\u53f7\uff09\u3002\n'
           '     * \u73b0\u5728\u6539\u6210**\u8fd0\u884c\u65f6\u63a8\u5bfc**\uff08`v8_official_end`\uff0c\u9010\u6307\u4ee4\u5b9e\u8bc1\uff09\uff1a\n'
           '     *   font0/3 \u21d2 \u4e0a\u754c 535\uff1bfont1/2/4/5/6 \u21d2 \u4e0a\u754c 279\u3002\n'
           '     * \u573a\u666f\u5185\u53d6\u5df2\u89c1\u6700\u5927\u503c\uff08\u540c\u4e00\u573a\u666f\u53ef\u80fd\u6df7\u7528\u591a\u79cd font\uff09\uff0c\n'
           '     * `v8_alloc_begin` \u6e05\u96f6\u3002 */\n'
           '    lo = v8_official_end_max(win);\n')
    s, _ = sub1(s, old, new, 'tile_alloc.c lo')
    ok.append('tile_alloc.c lo')

    write(F_ALLOC_C, s)
    t = read(F_ALLOC_C)
    assert 'v8_official_end_max(win)' in t and '617u' not in t.split('v8_alloc_n')[-1]
    ok.append('tile_alloc.c 自证：617u 已无残留于 alloc_n')

    # ───────────────────────── PrintNextChar_hook.c ─────────────────────────
    s = read(F_PNC_C)
    old = ('    r = (uint16_t)(p[dx] & 0x3FFu);\n'
           '    if (!v8_ours_has(r))                                   /* \u2460 */\n'
           '        return 0;\n')
    new = ('    r = (uint16_t)(p[dx] & 0x3FFu);\n'
           '    /* \U0001F534\U0001F534 v12 \u65b0\u589e\uff1a\u5b98\u65b9\u8d44\u4ea7\u533a**\u6c38\u4e0d\u590d\u7528**\u3002\n'
           '     * \u5b98\u65b9 atlas\uff08\u5b57\u6a21\uff09\u4e0e\u7a97\u53e3\u6846\u90fd\u5728 [1, \u4e0a\u754c) \u5185\uff1b\u5b83\u4eec\u4e5f\u662f\n'
           '     * \u300ctile, tile+1\u300d\u7ad6\u5bf9\uff0c\u5149\u9760 ① ② \u65e0\u6cd5\u4e0e\u6211\u4eec\u7684\u69fd\u533a\u5206\u3002\n'
           '     * \u5b9e\u673a\u540e\u679c\uff1a\u4e2d\u6587\u88ab\u5199\u8fdb font4 \u5b57\u6a21\u69fd \u21d2 \u961f\u4f0d\u9875\u91cc `Lv`/`/`\n'
           '     * \u7b49\u534a\u89d2\u5b57\u7b26\u7b14\u753b\u53e0\u6210\u53e6\u4e00\u4e2a\u5b57\uff08`Lv36`\u2192`w36`\u3001128/128\u2192128\\128\uff09\u3002\n'
           '     * \u5224\u636e\u662f\u786e\u5b9a\u6027\u7684\uff1a\u6c60\u53ea\u4ece\u4e0a\u754c\u8d77\u53d1\u53f7 \u21d2 r \u4e0d\u5230\u4e0a\u754c\u5c31\u4e00\u5b9a\u4e0d\u662f\u6211\u4eec\u7684\u3002 */\n'
           '    if (r < v8_official_end(win))\n'
           '        return 0;\n'
           '    if (!v8_ours_has(r))                                   /* \u2460 */\n'
           '        return 0;\n')
    s, _ = sub1(s, old, new, 'PNC chs_cell_slot 官方资产判据')
    ok.append('PNC chs_cell_slot 官方资产判据')
    write(F_PNC_C, s)
    assert 'r < v8_official_end(win)' in read(F_PNC_C)

    print('=== 全部替换成功 ===')
    for k in ok:
        print('  OK  ' + k)


if __name__ == '__main__':
    main()
