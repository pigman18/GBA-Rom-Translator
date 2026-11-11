# AXVJ 中文绘制：12px 度量 + 8×16 硬件容器

## 硬件 vs 度量（不要再搞混）

| 概念 | 值 | 说明 |
|------|-----|------|
| **Tile 容器** | **8×16**（上下两块 8×8）/ 字槽 **16×16** | Gen3 文本固定；官方/成熟汉化同此 |
| 字库存储 | **128 B/字**，4bpp，序 **TL→BL→TR→BR** | 与 Font_Patch pokeRS 一致 |
| **12px** | 墨水约 12、字高 12、`CHS_GLYPH_ADVANCE_PX=12`、行距 14 | **不是**改掉 tile 高度 |
| 竖直留白 | 通常上下各约 2px（墨水落在 16 高槽内） | `build_chinese_font.py` `PAD_TOP=2` |

「真 12×12 @ 18B 1bpp 取代 16 高容器」已证伪：认不出笔画。禁止再当产品路径。

## 绘制（现行 · 2026-11-07 · 官方落址重接）

- **入口**：`PrintNextChar_Hook` 全面接管（`F7 00` 内联汉字 / `F9` 兼容旁载 / 其余 JP PCS 同池 8px）；
  `SLT2` 空表桩仍会先查一次（待删，见 `docs/PROTOCOL_CURRENT.md` §4）。
- **汉字**：`PrintGlyph` → `DecompressGlyph_Chinese` + `DrawGlyphTile_refpr`（`CopyGlyph(C,E,D)` ink-only）。
- **落址（窗体 tm0/1/3）**：与 FontFunc[0] 同构  
  `abs = TILE_BASE + OFFSET + 2*xOff + yOff`；每画完一列 8px → `OFFSET += 2`；map 走官方 `UpdateTilemap`（**不**改 `textMode`）。  
  跨 Print 按 `TILE_BASE` 记 pool 游标（EWRAM `0x0203FF8C/8E`；tm1 列表 Init 会清 OFFSET）；新 base 且 OFFSET&lt;`0x100` 时跳过 IWTD/UI 符号低段（`0x180` 实测更差，勿抬）。
- **12px**：固定 **8+4** 两趟 + pitch 相位（`ChsPitchCtrl`@`0x0203FF80` / `slots[8]`@`0x0203FF90`）。
- **tm2**：只写 `win+0x20` 缓冲，每列 `dst += 0x40`（对齐 FontFunc[2]/`BlitGlyphTiles`）。
- **已删**：Mode2 `y*30` 自算、`LINEAR_FLOOR` / bag sticky、`map_at` 暂切 tm0、IWTD 弹窗 skip、cx≥14 强制 Linear。
- **保留**：`scene_remap_tile` 仅避让图鉴/PSS/菜单 ▶ 图标段 `0x1E8..`→`0x3E8..`（战斗窗禁止 remap）。
- **打包**：`font_patch._burn_plan_table_blobs` / `_burn_patch_table_redirects` — armips 高址常写丢，表须烙入（缺则道具名全空）。
- **禁止**：抬水位躲撞字、为躲裁切改 lexicon、改字库容器为真 12×12 tile、默认 `CHS_GLYPH_ADVANCE_PX→16`。
- **F7 路由**：`F7 00 hi lo` = 单汉字 4 字节，自由长度（`append_stream` 按 4 字节组消费）。
  `F9 00` 旁载仅作兼容残留；`F9 80` 短语表**已废弃**（别再按它改宽度/左移）。
- **等 A 箭头**：`TILE_X = base_tx + ceil(chs_px/8)`；半列未齐时 `TILE_OFFSET+=2`。
- **地图名弹窗**：钩 `0x0809F67E` 跳过 pad/二次 GetMapName。

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
