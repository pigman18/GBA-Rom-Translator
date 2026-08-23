# pokeruby `src/text.c` 文本渲染系统分析（textMode / fontNum 分发）

> 来源：`tools/pokeruby/src/text.c`（pokeruby 伪源码，共 4393 行）
> 说明：本文梳理该文件中 **textMode（3 种）** 与 **fontNum（7 种）** 的定义、含义及全部分发点，行号均指向 `tools/pokeruby/src/text.c`。

---

## 一、textMode：共 3 种

定义于 text.c:26-31：

```c
enum
{
    TEXT_MODE_UNKNOWN0,   // 0：变宽（比例）字体，像素级写入 tile，支持亚字节裁剪
    TEXT_MODE_MONOSPACE,  // 1：等宽字体——初始化时预加载 256 个字形到 VRAM，打印时只写 tilemap
    TEXT_MODE_UNKNOWN2,   // 2：变宽字体 + 连续 tile 分配（原注释标 "variable width?"）
};
```

### textMode 的分发点（按 `win->textMode` 查表 / switch）

| # | 分发点 | 行号 | 说明 |
|---|--------|------|------|
| 1 | `sPrintGlyphFuncs[win->textMode]` | 359-364 | **打印主入口**，3 个处理函数（见下） |
| 2 | `InitWindowTileData` / `MultistepInitWindowTileData` | 1770 / 1869 | 窗口 tile 数据初始化：mode2 → 变宽布局；mode1 → 再按 fontNum 分发预加载 |
| 3 | `ScrollWindowTextLines` | 2982 | 滚动三分支（TextMode0 / Monospace / TextMode2） |
| 4 | `Text_ClearWindow` | 3119 | 清屏三分支 |
| 5 | `EraseAtCursor` | 2828 | 擦除光标处内容 |
| 6 | `GetBlankTileNum` | 3376 | 空白 tile 编号计算 |
| 7 | `GetCursorTileNum` | 4380 | mode2 用连续 tile 编号公式，其余用简单偏移 |
| 8 | `ClipLeft` / `ClipRight` | 2840 / 2873 | 亚字节裁剪，mode1（等宽）跳过 |
| 9 | `AddToCursorX` / `SetCursorX` / `AddToCursorY` | 2797-2824 | 仅 mode0 需维护 `tileDataOffset`（跨 tile 时 +2） |

### 三种模式的打印函数（sPrintGlyphFuncs 表项）

调用点：`PrintNextChar`（text.c:2116）、`ExtCtrlCode_Escape`（text.c:2208）、`DrawSpace`（text.c:2242）。

| 函数 | 行号 | 行为 |
|------|------|------|
| `PrintGlyph_TextMode0` | 2571 | `DrawGlyph_TextMode0`：按字宽画像素 → 推进 cursorX（=字宽）→ 可 `ClipRight` 裁剪 |
| `PrintGlyph_TextMode1` | 2586 | 只调 `sWriteGlyphTilemapFuncs[fontNum]` 写 tilemap 表项；cursorX 固定 +8 |
| `PrintGlyph_TextMode2` | 2624 | 同 mode0 的画法，但走连续 tile 分配的 `GetCursorTileNum` 公式 |

---

## 二、fontNum：共 7 种（0–6）

fontNum 不是本文件的枚举，而是 **`sFonts[]` 表索引**。该表按语言分两半共 14 项（日文偏移 0 / 西文偏移 7），见 text.c:417-435：

| fontNum | 字形来源 | type | glyphSize | 说明 |
|---------|----------|------|-----------|------|
| 0 | font0_jpn/lat (.1bpp) | 0 | 16 | 大号双 tile 字体（lowerTileOffset=8/512） |
| 1 | font1_jpn/lat (.1bpp) | 1 | 8 | 经 `sFontType1Map` 映射上下 tile |
| 2 | 同 font1 字形 | 2 | 8 | 上半 tile 固定取第 212 项 |
| 3 | gFont3_jpn/lat (4bpp) | 日版 4 / 美版 0 | 64 | 带阴影大字体（双 tile，日版 lowerTileOffset=512） |
| 4 | gFont4_jpn/lat (4bpp) | 1 | 32 | 带阴影小字体 |
| 5 | 同 font4 | 2 | 32 | 同上变体 |
| 6 | sBrailleGlyphs (.1bpp) | 3 | 8 | 盲文 |

注意：`type` 是 `struct Font` 内部的寻址方式字段（5 种：0-4），与 fontNum 正交；`GetGlyphTilePointers` 按 type switch 计算上/下 tile 地址（text.c:2676-2715）。

### fontNum 的分发点

| # | 分发点 | 行号 | 分组逻辑 |
|---|--------|------|----------|
| 1 | `sWriteGlyphTilemapFuncs[win->fontNum]` | 368-377 | 7 项按 type 归并为 4 个实现：`Font0_Font3`(type0) / `Font1_Font4`(type1) / `Font2_Font5`(type2) / `Font6`(type3)；调用点在 `PrintGlyph_TextMode1` 与 `EraseAtCursor` |
| 2 | `GetGlyphTilePointers` | 2676 | `sFonts[language + fontNum]` → 再按 `font->type` 计算地址 |
| 3 | `LoadFixedWidthGlyph`（预加载单字） | 2647 | 0/1/2/6 → 无阴影 `ApplyColors_UnshadowedFont`；3/4/5 → 有阴影 `ApplyColors_ShadowedFont` |
| 4 | `DrawGlyphTiles`（运行时绘制） | 3336 | 同上分组：0/1/2/6 vs 3/4/5 |
| 5 | `InitWindowTileData` 等宽分支 | 1776-1793 | 0/3 → `LoadFixedWidthFont`（双倍 tile）；1/2 → Font1Latin 无阴影；4/5 → Font4Latin 有阴影；6 → 盲文 |
| 6 | `MultistepLoadFont_LoadGlyph`（分步预加载） | 1909-1935 | 同样按 0/3、1/2、4/5 分组 |
| 7 | `GetGlyphWidth`（字宽表） | 3410-3449 | 按 fontNum 查 `sFont0Widths` / `sFont1Widths`(经 map) / `sFont3Widths` / `sFont4Widths`(经 map)；盲文固定 8 |
| 8 | `GetBlankTileNum` 等宽分支 | 3383-3398 | fontNum 1/2/4/5 时基址 +212（共享空白字形）；0/3/6 直接用基址 |
| 9 | `DrawDownArrow` 等宽分支 | 3185 | fontNum 为 0 或 3 时 tile 编号 ×2（大字体） |

---

## 三、整体分发链路

```
WindowTemplate{fontNum, textMode}          （text.c 内大量模板定义，如 text.c:496 起）
        │ Text_InitWindow 复制到 win->fontNum / win->textMode（text.c:1942-1960）
        ▼
PrintNextChar ──控制码──► HandleExtCtrlCode（0xFC 后跟功能码，
        │                  查 sExtCtrlCodeFuncs 共 23 个函数，text.c:383-408）
        │                     └─ 功能码 6/7 可在文本中途改写/还原 fontNum；
        │                        功能码 21/22 切换日文/西文语言（影响 sFonts 半区）
        ▼ 普通字符
sPrintGlyphFuncs[win->textMode]            ← 第一次分发：决定"怎么画"
        │
        ├─ mode0/2: GetGlyphTilePointers(fontNum, language, …) ← 第二次分发：决定"画哪套字形"
        │           └─ DrawGlyphTiles 按 fontNum 选 Shadowed / Unshadowed 绘制路径
        │              （宽度 0-8 各有专门的 ShiftGlyphTile_*_WidthN 移位函数）
        └─ mode1:  sWriteGlyphTilemapFuncs[win->fontNum]       ← 直接按 fontNum 查表
```

### 核心要点

1. **textMode 决定"怎么画"**：
   - mode0/mode2 = 像素直绘（逐像素移位写入 tile 缓冲，支持任意像素起点与变宽）；
   - mode1 = 预载 256 字形进 VRAM，打印时只写 tilemap 条目（快但固定 8px 宽）。
2. **fontNum + language 决定"画哪套字形"**：`sFonts[]` 表 + `type` 寻址方式。
3. **两者正交**，可自由组合；且均可被 0xFC 扩展控制码在文本流中动态改写（fontNum 由功能码 6/7，language 由功能码 21/22）。
4. 0xFC 控制码长度表在 text.c:439-464（`sExtCtrlCodeLengths`），合法范围 0x00–0x16（23 种）。

---

## 附：相关数据表速查

| 表 | 行号 | 用途 |
|----|------|------|
| `sPrintGlyphFuncs[3]` | 359 | 按 textMode 选打印函数 |
| `sWriteGlyphTilemapFuncs[7]` | 368 | 按 fontNum 选 tilemap 写法（仅 mode1 使用） |
| `sExtCtrlCodeFuncs[23]` | 383 | 0xFC 扩展控制码处理函数表 |
| `sFonts[14]` | 417 | 7 种字体 × 2 语言 |
| `sTextSpeedDelays[3]` | 437 | 文本速度：慢/中/快 |
| `sExtCtrlCodeLengths[23]` | 439 | 各控制码字节长度 |
| `sShiftGlyphTileUnshadowedFuncs[9]` | 468 | 无阴影字形按宽度 0-8 移位绘制 |
| `sShiftGlyphTileShadowedFuncs[9]` | 483 | 有阴影字形按宽度 0-8 移位绘制 |
| `sFonts` 引用的宽度表 | 240-243 | `font0/1/3/4_widths.h` |
| `sFontType1Map` / `sFontType3Map` | 238-239 | type1/type3 字形的上下 tile 映射 |

---

# 二、日版汉化入口分析：`hook/src/text/PrintNextChar_hook.c`

> 分析对象：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c` 及其委托链
> （`DrawGlyph_CHS_hook.c` / `DrawGlyphTiles_hook.c` / `GetGlyphTilePointers_hook.c`，
> 汇编跳板 `src/text/entry.s`，订址桩 `src/text/hooks_origin.s`，地址唯一事实来源 `game_addrs.asm`）

## 1. Hook 了原版的哪些函数（订钉清单）

| ID | ROM 位点 | 原版函数（pokeruby 对应） | 接管方式 |
|----|----------|---------------------------|----------|
| P01 | `0x0800336E` `PrintNextChar_RegularGlyph` | `PrintNextChar()` 常规字形分支（≈pokeruby `sPrintGlyphFuncs[textMode]` 调用处） | 桩 `ldr r0,=(PrintNextChar_C\|1); bx r0` → `entry.s PrintNextChar` 跳板 → C `PrintNextChar_C`。**返回非 0=已消费；返回 0=回落原版** |
| P02 | `0x08003730` `GetGlyphTilePointers` | `GetGlyphTilePointers()`（Hook3，字模取址分发） | 8B 桩 far-jump → `entry.s GetGlyphTilePointers_Hook` → C 分发器：glyph bit15=1 → CHS 解析（FontChsNormal @0x09000000）；bit15=0 → 原函数重定位副本（entry.s `.incbin baserom 0x3730..0x382F`） |
| P04 | `0x0809F67E` `DrawMapNamePopup` 内 StringLength 位点 | 居中语义 ≈ pokeruby `Text_InitWindow_Centered` | → `entry.s MapName_DisplayCellLength` → C 按 CHS 真实步进算居中留白，落点 `0x0809F6CE` |
| P05 | `0x08003F4C` `DrawInitialDownArrow` | 等 A 箭头绘制段（FA/FB 不经 PrintNextChar） | 先同步 CHS 游标相位（`WaitArrow_Prepare_C`），再回落原版主体 `0x08003DAD` |

**回落路径**：`entry.s Pnc_original` 读 `win[0x0A]` 作索引查 `FontFuncTable @0x081BB3AC`，经 `CallViaR2 @0x081B12DC` 调原版处理器——这是 AXVJ 版的「sPrintGlyphFuncs 分发」。

## 2. AXVJ 与 pokeruby 美版的字段差异

- `win+0x0A` = **textMode = FontFuncTable 索引**（日版无 0xFC 控制码 switch、无三分打印表；打印步进由各 FontFunc 硬编码，如 FontFunc[0]@0x08003568 画后 `[win+0x18]+=2`）。game_addrs.asm 已定论：日版无原生 GetGlyphWidth/GetStringWidth。
- `win+0x0B` = **真 fontNum**（`WIN_FONTNUM_REAL`）。⚠️ game.h 中旧宏 `WIN_FONTNUM`(=0x0A) 是遗留别名=textMode，勿混用。
- AXVJ 的 `GetGlyphTilePointers` 是 4 参（无 language 形参，语言烘焙进 `sFonts[fontNum]`）——严禁按美版签名传 LANGUAGE_JAPANESE。

## 3. textMode 的处理（仅两处消费）

1. **缓冲型打印机门控**（`PrintNextChar_C` 第一行 → `scene_is_buffer_printer`，DrawGlyphTiles_hook.c:768）：
   - `textMode==2`：血条 TextPrintBattleInterface 缓冲（dest=win[0x20]，之后 CpuSet 刷走）；
   - `textMode==1 && fontNum==4`：RenderTextHandleBold（JP 0x08002CC0，共享静态窗）。
   - 命中即返回 0 → 整体交回原版 FontFunc（CHS 引擎的 template 寻址对它们是错误语义）。
2. **CHS 绘制引擎内部不读 win->textMode**：`info.textMode` 恒填 0（像素级合成语义，对齐官方 `DrawGlyphTile_*`）；tile 编号改为自选两套公式——`GetCursorTileNum_Linear`（tileBase+offset+2*x+y，对应官方非 mode2 分支）与 `GetCursorTileNum_Mode2`（y*30+x+band+base+origin，对应官方 UNKNOWN2 分支），由 `DrawGlyph_ShouldUseLinear` 按场景决定。

## 4. fontNum 的处理

- `DrawGlyph_JP_ViaCHS`（DrawGlyph_CHS_hook.c:61）：读 `win[0x0B]`，**>6 钳到 3**；shadowed（3/4/5）直接拷 32B 4bpp tile；unshadowed（0/1/2/6）经官方 `CopyGlyph1bppTo4bpp` 展开（fg=15/bg=0）。日文 PCS 也强制走 CHS 同池（禁 FontFunc 双路径）。
- 场景门控多处以 `fontNum==3` 为前提才启用 Mode2/特殊布局：`scene_menu_wants_mode2`、`scene_is_shop_desc`、`scene_is_shop_bag_list`、`scene_is_party_footer`。
- `GetGlyphTilePointers_CHS` 忽略 fontNum（CHS 字库单 bank：TL@+0 BL@+0x20 TR@+0x40 BR@+0x60，128B/glyph）。

## 5. `PrintNextChar_C` 主分流顺序

```
PrintNextChar_C(win, cur_char)
 ├─ scene_is_buffer_printer?        → return 0（原版 FontFunc 接管）
 ├─ cur_char==0xEF                  → DrawMenuCursorEF（菜单 ▶ 固定 tile 对）
 ├─ cur_char==0xF9 (CHS_ESCAPE):
 │   ├─ op==00 ll tt                → pack_glyph_index → PrintGlyph_CHS（内联汉字 12px）
 │   └─ op!=00 hi lo                → PhraseTable：父串未结束且短语流无等待控制码
 │                                    → inline_phrase_no_controls 内联绘制；
 │                                      否则 redirect_phrase_stream 切流
 ├─ slot_lookup_and_draw            → SlotTable（'SLT2' 分桶 O(桶) / legacy 平铺线性）
 │                                    命中 → slot_draw_chinese 画中文并推进 INDEX
 └─ 其余可印 JP PCS                 → DrawGlyph_CHS（Sym 带 0x36..3E / 空白 / 经官方
                                      取址展开后 CHS 同池 8px 步进）
```

要点：汉化引擎是**在 P01 单点截获全部常规字形**，textMode 只用来识别并放行两类缓冲型打印机；fontNum 决定日文字模的取址/展开方式与部分场景的 tile 编号公式；中文一律走自绘 CHS 引擎（12px 双趟 8+4 spill），原版函数仅在回落与重定位副本中被复用。

---

# 三、字形尺寸控制机制（text.c 无缩放代码的真相）

> 结论：text.c 不存在任何放大/缩小运算（ShiftGlyphTile_* 仅水平移位）。"字大字小"
> 由三个正交机制的静态组合决定。

## 机制一：字模数据固有尺寸（struct Font.glyphSize）

| fontNum | glyphSize | 形状 | 说明 |
|---|---|---|---|
| 0 | 16B | 1bpp 8×16 整高 | 对话主字体 |
| 1/2 | 8B | 1bpp 8×8 | 小字/变体 |
| 3 | 64B | 4bpp 8×16 大字（带阴影） | 战斗台词 |
| 4/5 | 32B | 4bpp **8×8 单 tile** | 血条/队伍名"小字"数据源 |
| 6 | 8B | 1bpp 8×8 | 盲文 |

## 机制二：上下 tile 配对＝视觉高度的另一半

打印层永远写两个表项拼 8×16 格（WriteGlyphTilemap: buffer[0]=upper、buffer[32]=lower）。
GetGlyphTilePointers 五种 type 决定配对：

- type0：lower=upper+lowerTileOffset（同记录拆半）
- type1（font1/2/4/5）：sFontType1Map[2g]/[2g+1] 任选两块
- type2（font2）：upper 固定第 212 项（全块规范空白槽）、lower 为字形

铁证：GetBlankTileNum 给 font∈{1,2,4,5} 统一返回 startOffset+212。
**日版实测**（SubTable[4] 映射表 @0x081B34A8，步长 4B/字符）：char0=双 212（空格）；
其余「上格恒 212 空白、下格=递增 tile 号」→ 墨水只占格内下半 8px，基线对齐式小字。

## 机制三：水平步进

- mode0/2：spacing 覆盖 > 各字体宽度表（font1/2/4/5 经 sFontType1Map[2g+1] 二次
  索引——map 第二槽兼任宽度等级选择子）> 默认 8
- mode1：恒 cursorX+=8
- FC 0x14 可流内改 spacing

## 「队伍名比别处小」成因链

美版：RenderTextHandleBold→font4（8×8 数据）+sFont4Widths 变宽，像素直绘缓冲；
日版：mode1+font4→上格配 212 空白→墨水仅下半 8px＋等宽 8px。

## 对 CHS 引擎的扩展点（已预留，未启用）

1. 字库源：GetGlyphTilePointers_CHS 可按 fontNum 分支到小号汉卡 bank
2. 步进/高度：CHS_GLYPH_ADVANCE_PX 可按分发行查表（mode1→小号值）
3. 绘制趟数：高度≤8px 时单趟（省 BL）；宽度>8 仍保留右溢出
当前所有 BG 文本统一 12px 高，在 mode1 小字窗不串行（16px 格）但风格偏大、基线不齐。
