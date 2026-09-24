# -*- coding: utf-8 -*-
"""v18：加一个 UI 总开关（「模仿文字的开关」），先置 0 打包测「UI 是否全部输出为空」。

文字侧现成的开关语义：`v8_alloc_tile` 从 `v8_alloc_core` 拿不到号 ⇒ 返 0
⇒ 调用方放弃绘制 ⇒ **文字输出为空**。

UI 的号只有两个出口，把它们一起关掉 ⇒ **UI 全部输出为空**：
  ① 框号  `v8_alloc_ui`            → ⑤ 返 0 ⇒ 0x03000514 = 0 ⇒ ⑥ 收 0
                                      ⇒ 0x03000516 = 0 ⇒ 框图形不装载、框 tilemap 擦成 0
  ② 底色  `v17_blank_tile_C`（GetBlankTileNum）⇒ 内容区填 0 号砖

开关 = `V18_UI_ON`（编译期）。0 = 关（UI 全空，文字不受影响）；1 = 正常。
"""
import io
import os

HDR = r'configs/POKEMON_RUBY_AXVJ00/hook/include/tile_alloc.h'
C = r'configs/POKEMON_RUBY_AXVJ00/hook/src/text/tile_alloc.c'


def load(path):
    raw = io.open(path, 'rb').read()
    return raw.decode('utf-8').replace('\r\n', '\n'), (b'\r\n' in raw)


def save(path, text, crlf):
    out = text.replace('\n', '\r\n') if crlf else text
    io.open(path, 'wb').write(out.encode('utf-8'))


def rep(s, old, new, tag):
    n = s.count(old)
    assert n == 1, '[%s] count=%d (want 1)' % (tag, n)
    return s.replace(old, new)


SWITCH = '''/* ============================================================================
 * [v18] UI 总开关（2026-09-11）—— 「模仿文字的开关，给 UI 加一个」。
 *
 *   文字的开关是**现成的**：`v8_alloc_tile` 从 `v8_alloc_core` 拿不到号就返 0
 *   ⇒ 调用方放弃这次字形 ⇒ **文字输出为空**。
 *
 *   UI 的号也只有**两个**出口，把这两个出口一起关掉 ⇒ **UI 全部输出为空**：
 *     ① 框号  `v8_alloc_ui`        → ⑤ 返 0 ⇒ `0x03000514 = 0` ⇒ ⑥ 收到 0
 *                                     ⇒ `0x03000516 = 0`
 *                                     ⇒ 框图形不装载（⑦/A/B/C/⑧ 读 0 即跳过）、
 *                                        框 tilemap 擦成 0 号砖（⑨b / dlg 包装）；
 *     ② 底色  `v17_blank_tile_C`（= GetBlankTileNum）⇒ 内容区填 0 号砖。
 *
 *   0 = 关闭（UI 全部输出为空，**文字完全不受影响**）；
 *   1 = 正常（UI 与文字同权，走同一个 v8_alloc_core）。
 *
 *   用法：先置 0 打包，看「关掉 UI 后画面是不是真的全空」——
 *   若仍有粉框 / 底色残留，那就说明还有**第三个号出口**没接上，那才是漏点。
 * ==========================================================================*/
#define V18_UI_ON   0

'''

edits = []

# ---------------- tile_alloc.h ----------------
s, crlf = load(HDR)
assert '#include "tile_alloc.h"' not in s
s = rep(s,
        '/* ② UI 分配：窗框等 UI 占位领 n 个 tile ——**与文本走同一个 v8_alloc_core**。',
        SWITCH + '/* ② UI 分配：窗框等 UI 占位领 n 个 tile ——**与文本走同一个 v8_alloc_core**。',
        'hdr 开关')
# 在 ② 的说明里点名开关
s = rep(s,
        'uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n);',
        'uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n);   /* V18_UI_ON == 0 时恒返 0 */',
        'hdr v8_alloc_ui 注释')
# v17 的声明也点名
s = rep(s,
        'int v17_blank_tile_C(uint8_t *win);',
        'int v17_blank_tile_C(uint8_t *win);      /* V18_UI_ON == 0 时恒返 0 */',
        'hdr v17 注释')
edits.append((HDR, s, crlf))

# ---------------- tile_alloc.c ----------------
s, crlf = load(C)
assert '#include "tile_alloc.h"' in s, 'tile_alloc.c 竟然没 include tile_alloc.h'

s = rep(s,
"""/* ② UI 分配：与文本完全同一条路径（同一个 v8_alloc_core）。 */
uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n)
{
    return v8_alloc_core(tpl, n);
}""",
"""/* ② UI 分配：与文本完全同一条路径（同一个 v8_alloc_core）。
 *
 * [v18] 头上先过 **UI 总开关**（tile_alloc.h 的 `V18_UI_ON`）：
 *   关掉 ⇒ 恒返 0 ⇒ ⑤ 把 `0x03000514` 写 0 并返回 0 ⇒ ⑥ 收到 0 ⇒ `0x03000516 = 0`
 *   ⇒ 框图形不装载、框 tilemap 擦成 0。**文字不走这里，不受影响**。 */
uint16_t v8_alloc_ui(uint8_t *tpl, uint16_t n)
{
    if (!V18_UI_ON)
        return 0u;                  /* [v18] UI 开关关闭 ⇒ 框号 0 ⇒ 框全部输出为空 */

    return v8_alloc_core(tpl, n);
}""",
        'c v8_alloc_ui')

s = rep(s,
"""int v17_blank_tile_C(uint8_t *win)
{
    uint8_t *tpl;
    const void *vram;
    uint16_t lo, hi;

    if (!win)""",
"""int v17_blank_tile_C(uint8_t *win)
{
    uint8_t *tpl;
    const void *vram;
    uint16_t lo, hi;

    if (!V18_UI_ON)
        return 0;                       /* [v18] UI 开关关闭 ⇒ 底色也填 0 号砖 */

    if (!win)""",
        'c v17 开关')

edits.append((C, s, crlf))

for path, text, crlf in edits:
    save(path, text, crlf)
    print('WROTE %-70s %d B  (CRLF=%s)' % (path, os.path.getsize(path), crlf))
print('OK')
