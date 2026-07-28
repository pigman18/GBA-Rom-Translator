# AXVJ 中文写入分流

实现：`src/text/PrintNextChar/draw_glyph.c` + `draw_scene.c`。  
挂载：[`HOOKS.md`](HOOKS.md)。  
**水平步进与字形算法：真 12px，见 [`../../docs/FONT_12PX_DRAW.md`](../../docs/FONT_12PX_DRAW.md)（禁止退回 16 当方案）。**

| F9 XX | 含义 |
|-------|------|
| `F9 00` | 侧载单字 |
| `F9 7F hi lo` | 默认短语表（auto 几何） |
| `F9 01..7E` | `write.op`（02=footer / 03=linear / 04=slot）——**上层 inject 配置不变** |
| 裸 `FA..FF` | PCS 控制/串尾，禁止作 F9 通道 |

## charBase2 互斥带（512 格内）

| 范围 | 用途 |
|------|------|
| `0x002–0x0FF` | 原版 Mode2 / 商店名单（origin `+2`，无 BAND） |
| `0x100–0x13F` | 野外短 Linear |
| `0x160–0x19C` | 队伍 DoWhat Mode2（`top≈17`；origin `+2`；`y'=y-16`；`PARTY_FOOTER_BAND 0x140`） |
| `~0x19D` | 原版菜单光标手型——中文禁止占用 |
| `0x1B0–0x1FF` | 队伍选项 Mode2（left≥20；`y'=y-13`；`MENU_BAND=0x17A`） |
| `0x228+` | 仅商店说明 Linear |

| 模块 | op | 绘制 |
|------|-----|------|
| charBase2 菜单池（标题续关/商店买·卖·没事/开始菜单/商店列表等） | 不配（或误配 `0x03`） | **Mode2** 网格（防 Print rewind 串台；`scene_menu_wants_mode2` 优先于 inject LINEAR） |
| 队伍 DoWhat（left&lt;14 且 top≈17） | 不配 | **Mode2** origin=`+2` + `PARTY_FOOTER_BAND` |
| 队伍底栏窄带「请选择」等 | `0x02` | Mode2 + footer 带 + origin `0x20` |
| 商店/道具说明（top=`0x68`/`13`） | 不配 | **Linear**，地板 `0x228` |
| 队伍选项（left≥20 且 y≥13） | 不配 | Mode2 + `MENU_BAND 0x17A` + y 重映射 + `x++` |
| 野外/对话 charBase≠2 | 不配 | **Linear**，地板 `0x100` |
| 战斗菜单·提示·报文 | `0x03` | Linear |
| 招式名 | `0x04` | Linear / 固定槽 |

**phrase_auto（F9 7F）只清 sticky（+2），不清 linear HW（+4）。**  
**勿在 `DrawGlyph_Chinese` 预同步 `char_base`。**

## JP via CHS（与 F9 共用落点；禁止回落原版）

详情页昵称·亲代·数字与中文标签曾双通道抢池 →「汉字替换」（**已解**，见根目录 `技术文档.md` §7.1）。

**可印 PCS（1..0xF6）一律**经 `GetGlyphTilePointers` 取原版字模，再走 `DrawGlyph_Chinese_Adv(..., 8)`；**禁止**交回 `FontFuncTable`。

| 项 | 约定 |
|----|------|
| AXVJ ABI | `(font, glyph, &upper, &lower)` 4 参（**无** language；误传 `LANGUAGE_JAPANESE` 会把 glyph 固定成 1 → 全日文空白） |
| font 3/4/5 | 32B 阴影字模（0/E/F）→ TL/BL |
| font 0/1/2/6 | 8B 1bpp → 扩成 0xF 后再走 CopyGlyph2bpp（勿对 1bpp 直接当 32B 拷） |
| 取模失败 | `return 0` 交回原版（禁止空画 `return 1`） |
| 跨窗 | `pitch_key` 复位；**不靠再调 tile 带**修替换 |
