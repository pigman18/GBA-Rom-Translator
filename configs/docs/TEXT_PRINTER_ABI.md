# AXVJ TextPrinter / Hook 入口 ABI

对照：[`game.h`](../POKEMON_RUBY_AXVJ00/patch/src/game.h)、[`entry.s`](../POKEMON_RUBY_AXVJ00/patch/src/text/PrintNextChar/entry.s)、origin `FontFuncTable` @ `0x081BB3AC`。  
挂载总览：[`HOOKS.md`](HOOKS.md)。双链路：[`技术文档.md`](../../技术文档.md) BUG-02。

**注意（日版 ≠ 美版）**：AXVJ 打印机布局里 `+0x0A` = **textMode**（FontFunc 下标），`+0x0B` = **fontNum**；`+0x20` = **tileData**。美版 pokeruby `Window` 常把 text 放在 `+0x20`、tileData 在 `+0x24`——勿照抄。`game_addrs.asm` 里旧名 `WIN_COLOR_B=0x0B` 已废弃，以 `game.h` 的 `WIN_FONTNUM_REAL` 为准。

---

## 1. textMode（`win[+0x0A]`）有多少种？

`entry.s` 回落原版时：`FontFuncTable[textMode]`，表基址 **`0x081BB3AC`**。  
origin 只读：下标 **0..10** 为合法 Thumb 函数指针（共 **11 种**）；`[11]` 起不是代码指针（表结束）。

| textMode | FontFunc 入口（origin，含 Thumb 位） | 本仓用途 / 备注 |
|----------|--------------------------------------|-----------------|
| **0** | `0x08003569`（≈ `DrawGlyph_Font0_Wrapper`） | 常规窗格字形；统一中文链路（CHS）覆盖可印字 |
| **1** | `0x0800360D` | 常规变体；CHS 覆盖可印字 |
| **2** | `0x0800338D` | **对战 bold / healthbox**：读 `win+0x20` blit → `eBattleInterfaceGfxBuffer`。产品闸：**整钩子交回 FontFunc，禁止 CHS** |
| **3** | `0x08003495`（≈ `DrawGlyph_Font3_Wrapper`） | 阴影系；CHS 覆盖可印字 |
| **4** | `0x08003585` | 与 7 同址 |
| **5** | `0x080035A1` | 与 8 同址 |
| **6** | `0x080035C9` | 与 9 同址 |
| **7** | `0x08003585` | = mode 4 |
| **8** | `0x080035A1` | = mode 5 |
| **9** | `0x080035C9` | = mode 6 |
| **10** | `0x080035E5` | 末槽 |
| ≥11 | （非指针） | **禁止**当作 textMode |

`RenderTextHandleBold`（`0x08002CC0`）在打印前 `strb #2,[win,#0x0A]`，故 healthbox 稳定为 mode **2**。

产品分流（已落地；扩掩码仅诊断）：

| textMode | 通道 |
|----------|------|
| `== 2`（产品） | 原版日文 FontFunc[2] |
| 其余 | 统一中文（F9 12px + JP-via-CHS 8px） |

产品闸代码为 `textMode == 2`。编译掩码 `CHS_FONTFUNC_TEXTMODE_MASK` 仅供 `tools/batch_textmode_roms.py` A/B；**扩旁路不能修详情**（已证伪）。详见 [`技术文档.md`](../../技术文档.md) 详情对照表。

---

## 2. 通道入口处可读属性（TextPrinter + Template）

钩子拿到的是 **TextPrinter**（`r4` / C 的 `win`）。字段按偏移：

### 2.1 TextPrinter（`win`）

| 偏移 | 宏（`game.h`） | 宽 | 含义 |
|------|----------------|----|------|
| `+0x00` | `WIN_TEMPLATE` | u32 | → WindowTemplate* |
| `+0x04` | `WIN_STATE` | — | 打印机状态 |
| `+0x0A` | `WIN_TEXTMODE` | u8 | **FontFunc 下标**（上表） |
| `+0x0B` | `WIN_FONTNUM_REAL` | u8 | **字库号** → `GetGlyphTilePointers` |
| `+0x0C` | `WIN_COLOR_C` | u8 | 前景色 |
| `+0x0D` | `WIN_COLOR_D` | u8 | 阴影色 |
| `+0x0E` | `WIN_COLOR_E` | u8 | 背景色 |
| `+0x0F` | `WIN_PALETTE` | u8 | 调色板相关 |
| `+0x10` | `WIN_TEXT_PTR` | u32 | 当前字符串 |
| `+0x14` | `WIN_TEXT_INDEX` | u16 | 串内游标（F9 会 +3） |
| `+0x16` | `WIN_TILE_BASE` | u16 | BG tile 基；战斗菜单常 `≥0x280` |
| `+0x18` | `WIN_TILE_OFFSET` | u16 | 线性分配游标 |
| `+0x1A` | `WIN_CURSOR_X` | u8 | 窗内像素/格 X（场景判定用） |
| `+0x1B` | `WIN_CURSOR_TILE_X` | u8 | tile 列光标 |
| `+0x1C` | `WIN_CURSOR_Y` | u8 | 窗内 Y |
| `+0x1D` | `WIN_CURSOR_TILE_Y` | u8 | tile 行光标 |
| `+0x20` | `WIN_TILE_DATA` | u32 | **blit 目标**；mode2 时为 battle buffer（如 `0x02020004`） |

旧别名：`WIN_FONTNUM`（= `0x0A`）易与 textMode 混淆，**新代码只用 `WIN_TEXTMODE` / `WIN_FONTNUM_REAL`**。

### 2.2 WindowTemplate（`*win_template(win)`）

CHS / Linear 实际写 VRAM 时用模板，不是 `win+0x20`：

| 偏移 | 用途（本仓） |
|------|----------------|
| `+0x01` | `charBaseBlock`（Mode2 / 场景指纹） |
| `+0x0C` | **tileData** → VRAM 基（`draw_glyph.c` `vram_tile`） |

healthbox：模板 `+0x0C` 常为 OBJ_VRAM；真正字墨在 `win+0x20` 的 IWRAM buffer——故 mode2 禁止 CHS。

### 2.3 fontNum（`+0x0B`，与 textMode 独立）

| fontNum | 字模形态（JP-via-CHS） |
|---------|-------------------------|
| 0 / 1 / 2 / 6 | 1bpp → 扩成 0xF 再 CopyGlyph2bpp |
| 3 / 4 / 5 | 32B 阴影（0/E/F）→ TL/BL |
| `FONT_NORMAL_UNSHADOWED=0` / `FONT_NORMAL_SHADOWED=3` | 宽度计算常用 |

`GetGlyphTilePointers(font, glyph, &u, &l)`：**4 参**，无 language。

### 2.4 旁路状态 `ChineseTileState`（`0x0203FFF8`，非 win 字段）

| 偏移 | 字段 | 含义 |
|------|------|------|
| +0 | `char_base` | 上次 template charBase |
| +1 | `write_op` | F9 op / sticky（02 footer / 03 linear / 04 slot） |
| +2 | `base_tx` | pitch 起点 CURSOR_TILE_X |
| +3 | `last_adv` | 上次步进（8 / 12） |
| +4 | `pitch_key` | 窗指纹 |
| +6 | `chs_px` | 当前 pitch 像素 X |

---

## 3. Hook 函数：参数 / 返回值

### 3.1 `PrintNextChar`（asm，`game.bin` 入口）

| 项 | 说明 |
|----|------|
| 挂载 | `ProcessCurrentChar_RegularGlyph` `0x0800336E` → `PrintNextChar\|1` @ `0x08800000` |
| 入（调用约定） | **`r4`** = TextPrinter*；**`r3`** = 当前 PCS 字节（已取出的 cur_char）；栈上有原函数保存的 r4 / 返回地址 |
| 内部 | `r0=r4`, `r1=r3` → `bl PrintNextChar_C` |
| 出 | 见下：最终对调用方表现为「已消耗一字」路径（与原版一致 pop） |

### 3.2 `PrintNextChar_C`

```c
int PrintNextChar_C(TextPrinter *win, uint32_t cur_char);
```

| 返回值 | `entry.s` 行为 |
|--------|----------------|
| **非 0** | 视为已由中文路径画完；`movs r0,#1` 后 pop 返回调用方 |
| **0** | `Pnc_original`：`FontFuncTable[win[+0x0A]](win, cur_char)` via `CallViaR2` |

入口闸（产品）：`textMode==2` → **立即 return 0**（含 F9/sym，整钩交 FontFunc）。

非 2 时大致：

| `cur_char` | 行为 | 返回 |
|------------|------|------|
| Sym 标点窗 | `draw_sym_punct` → CHS Adv 8 | 1 |
| `≠ F9` 可印 PCS | `draw_jp_via_chs`（取 JP 字模 → CHS Adv 8） | 1 成功 / 0 交 FontFunc |
| `≠ F9` 控制码等 | `draw_jp_via_chs` 早退 | 0 |
| `F9` | 解析 op / phrase → `DrawGlyph_Chinese`（12px） | 1（非法 lead 等可 0） |

### 3.3 原版 FontFunc（回落）

| 项 | 说明 |
|----|------|
| 调用 | `r0=win`, `r1=cur_char`, `r2=FontFuncTable[textMode]`，`CallViaR2` |
| 返回 | asm 固定再 `movs r0,#1` 后返回（对 ProcessCurrentChar：字已处理） |

### 3.4 `GetStringWidthChinese` / `_Full`

| 项 | 说明 |
|----|------|
| 挂载 | `GetStringWidth` `0x08004CC0` → 薄壳 → `GetStringWidthChinese` |
| asm | `r0=win`, `r1=str` → `GetStringWidthChinese_Full` → **`r0=width`（u8）** |
| C | `uint8_t GetStringWidthChinese_Full(TextPrinter *win, const uint8_t *s);` |
| 规则 | F9 → 按字/短语累加 12px（部分 font 变体 10/8）；普通 PCS → +8；`FA..FE` 跳过；`FF` 结束 |

辅助：`GetStringWidth_Chinese(win, s, &index, &width)` 只处理当前位置的 F9；成功返回 1 并推进 index。

### 3.5 相关（非 PrintNextChar，同 bin）

| 符号 | 角色 |
|------|------|
| `UpdateNickInHealthbox` 三池 | armips 改 CpuSet 字数 8→6；不经 textMode 闸 |
| `DrawGlyph_Chinese` / `_Adv` | CHS 写 `template+0x0C`；`adv_px` 12 或 8 |

---

## 4. 入口处「决策用」属性一览（排障用）

在 `PrintNextChar_C` 开头实际会读、或场景层会读的信号：

| 属性 | 来源 | 用途 |
|------|------|------|
| `textMode` | `win+0x0A` | **双链路主闸**（==2 → 日文） |
| `cur_char` | 参数 | F9 / PCS / Sym |
| `fontNum` | `win+0x0B` | 取模、宽度 |
| `text` / `index` | `+0x10` / `+0x14` | F9 解析 |
| `tileBase` / `tileOffset` | `+0x16` / `+0x18` | Linear 地板、战斗固定基 |
| `cursor X/Y/tile` | `+0x1A..1D` | Mode2 / 商店 / 队伍场景 |
| `tileData` | `win+0x20` | 文档对照；**现行主闸不用**（曾未兑现） |
| `charBase` | template `+1` | Mode2 / pitch_key |
| `write_op` | ChineseTileState | F9 op 几何 |
| 颜色 C/D/E | `+0x0C..0E` | CopyGlyph 调色 |

---

## 5. 修订记录

| 日期 | 内容 |
|------|------|
| 2026-07-29 | 初版：origin 核 FontFunc 0..10；挂钩 ABI；与双链路定案对齐 |
