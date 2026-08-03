# AXVJ 中文绘制：12px 度量 + 8×16 硬件容器

## 硬件 vs 度量（不要再搞混）

| 概念 | 值 | 说明 |
|------|-----|------|
| **Tile 容器** | **8×16**（上下两块 8×8）/ 字槽 **16×16** | Gen3 文本固定；官方/成熟汉化同此 |
| 字库存储 | **128 B/字**，4bpp，序 **TL→BL→TR→BR** | 与 Font_Patch pokeRS 一致 |
| **12px** | 墨水约 12、字高 12、`CHS_GLYPH_ADVANCE_PX=12`、行距 14 | **不是**改掉 tile 高度 |
| 竖直留白 | 通常上下各约 2px（墨水落在 16 高槽内） | `build_chinese_font.py` `PAD_TOP=2` |

「真 12×12 @ 18B 1bpp 取代 16 高容器」已证伪：认不出笔画。禁止再当产品路径。

## 绘制（现行）

- 入口：`drawGlyph12()` ← Font_Patch **8+4** + ROM `CopyGlyph2bppTo4bpp`（IWRAM 拼好再 32-bit 拷 VRAM；禁止对 VRAM 字节写，否则半字镜像→重影）
- 取字：`base + (index << 7)`
- 步进：`CHS_GLYPH_ADVANCE_PX = 12`
- 落点：[`draw_glyph.c`](../configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar/draw_glyph.c)
- **Linear 地板**：野外/说明 `0x100`，商店说明 `0x228`（见 `CHS_TILE_LAYOUT.md`）；无 `next_abs` sticky
- **调色**：`CopyGlyph(C,E,D)` → `15→C` / `14→E` / `0→D`；右缘填 D，不碰左缘
- **Mode2**：vanilla `origin+2`；`MENU_BAND` 仅 left≥20 **且** y≥13（存档屏禁止误进）

`scene_keep_linear_16` 仍硬关。

## bug/ 症状 ↔ 根因（2026-07）

| 现象（`bug/*.PNG`） | 根因 |
|---------------------|------|
| 对话黑噪 + **绿地板方块**，`!`/心正常 | 自造 `alloc_linear_tile` / `next_abs` 把 BG tile 索引写进窗 tilemap |
| 菜单中文色块/横纹，假名数字正常 | 同上中文分支；调色曾 `15→E`/`14→C` 加重脏色 |
| 字库槽离线可认 | **不是** 128B 打包主因；离线 PNG 复现不了错 abs |

对照成熟路径：`Pokemon_GBA_Font_Patch/pokeRS/.../DrawGlyphTilesChinese.s`（`GetCursorTileNum` + ShadowedFont）。本仓库仍 **ink-only**（见下），不接 ShadowedFont+bg OR。

## 已证伪

| 尝试 | 结论 |
|------|------|
| 18B 1bpp + 逐像素乱写 VRAM | 色块/竖条纹 |
| 18B + 自造相位、当「无 16 槽」 | 只能看出约 12 高，无笔画 |
| ShadowedFont `colors[0]=bg`+OR | 像 16 / 糊影 / 重字 — **仍禁止**（`DONT.md` §9） |
| `next_abs` / menu floor 劫持 Linear 偏移 | 对话绿块 — **已旁路** |
| `15→E` / `14→C` 调色 | 与 ROM CopyGlyph 相反 — **已改为 15→C / 14→E** |
| 空像素写 0 或 D | 实心莫名背景（存档蓝块/对话黑块）— **已改为 skip** |
| shop_desc top==13 → Linear16 | 标题变 16 |
| 用 classic16 **度量**冒充交付 | 禁止；容器仍是 16 高 |

## 验收

1. 商店/中心对话：中文可辨笔画，**无绿地板方块**；`!`/心仍正常。
2. 菜单：中文非实心色块；假名数字不被带坏。
3. 间距约 12（非突然变 16）。
4. 代理不自开 mGBA；用户 `start_gui.bat` 自测 ROM。

## 相关

- 规则：`.cursor/rules/axvj-font-12px-only.mdc`
- [`DONT.md`](DONT.md) §9
- 参考：`tools/Pokemon_GBA_Font_Patch/pokeRS/src/HackFunction/DrawGlyphTilesChinese.s`、`tools/pokeruby/src/text.c` `GetCursorTileNum`
