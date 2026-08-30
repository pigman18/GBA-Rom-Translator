# 需求文档：官方绘制委托化重构（PrintNextChar / GetGlyphTilePointers / GetGlyphWidth）

> 目的：把 `hook/src/text` 从“全自绘”收敛为“三钩 + 半自绘”，其余 `tile 索引 / tilemap / 颜色重映射` 全部委托官方。仅保留 `12px 8+4 spill` 与 `F9 4字节消费` 必须自实现的部分。

## 1. 背景与现状

当前 `configs/POKEMON_RUBY_AXVJ00/hook` 在 `main.asm:16` 劫 `PrintNextChar_RegularGlyph@0x0800336E`，`PrintNextChar_hook.c:319` 判定 `F9 00` 后全程自绘 `DrawGlyphTiles_hook.c:260 draw_glyph_tile_12` + 自算 `vram_tile/linear_cursor_tile/compute_mode2_pair`，官方仅复用最底层 `CopyGlyph2bpp@0x080038A0` / `UpdateTilemap@0x080036DC`。

已验证官方链路（`AXVJ_TEXT_PIPELINE.md` + capstone 反汇编实证）：

```
PrintNextChar@0x080032F8 --bhi--> RegularGlyph@0x0800336E --ldr FontFuncTable@0x081BB3AC--> CallViaR2@0x081B12DC --> FontFunc[0..6]
FontFunc --call--> GetGlyphTilePointers@0x08003730 --call--> CopyGlyph1/2bpp@0x08003830/0x080038A0 --call--> UpdateTilemap@0x080036DC
```

用户诉求：`PrintNextChar` 读 `F900`、`GetGlyphTilePointers` 给地址、`GetGlyphWidth` 给 `12` 后理论可全委托。

## 2. 已解析地址（AXVJ 日版 ROM 实测，非美版符号推测）

| 类别 | 符号 | 地址 | 备注 |
|------|------|------|------|
| 引擎入口 | `PrintNextChar` | `0x080032F8` | `win=r0, text@0x10, index@0x14, state@0x04, textMode@0x0A, fontNum@0x0B` |
| 分流点 | `PrintNextChar_RegularGlyph` | `0x0800336E` | `ldrb r1,[r4,#0x0A]` 取 `textMode` 查 `FontFuncTable` |
| 函数表 | `FontFuncTable` | `0x081BB3AC` | 7 项 `[0]=0x08003569 [1]=0x0800360D [2]=0x0800338D [3]=0x08003495 [4]=0x08003585 [5]=0x080035A1 [6]=0x080035C9` |
| 间接调用桩 | `CallViaR2` | `0x081B12DC` | `bx r2` 桩，`FontFunc(win,char)` |
| 字库寻址 | `GetGlyphTilePointers` | `0x08003730` | `r0=fontNum,r1=glyph,r2=&upper,r3=&lower`，4参（无 language，美版 5参） |
| 索引计算 | `GetCursorTilemapPointer` | `0x08003708` | `r0=win -> r0=&tilemap[(CY+TY)*32+(CX+TX)]` |
|  | `GetCursorTileNum` 内联于 `FontFunc` | `0x08003500 / 0x080034A8` | `x=CX+TX+TILE_BASE, y=CY+TY, idx=x+y*30` |
| 调色 | `CopyGlyph1bppTo4bpp` | `0x08003830` | `1bpp 8B -> 4bpp 32B`，font0/1/2/6 |
|  | `CopyGlyph2bppTo4bpp` | `0x080038A0` | `15->C,14->E,0->D`，font3/4/5 |
| 贴图 | `UpdateTilemap` | `0x080036DC` | `r0=win,r1=upperTile,r2=lowerTile` |
| 箭头 | `DrawInitialDownArrow` | `0x08003F4C` | `FA/FB` 不经 `PrintNextChar` |
| 宽度 | `GetGlyphWidth` | `0x08004228` | 已有 `GetGlyphWidthHook` 汇编钩（`PrintNextChar_entry.s:101`） |
| 宽度 | `GetStringWidth` | `0x08004530` | 125 调用方，`0x08004CC0` 为误判勿用 |
| 字库 | `FontChsNormal` | `0x09000000` | `gidx<<7`, 128B `TL/BL/TR/BR` 各32B |
| 符号 | `PokeRSFontChsSymAddress` | `0x091E0000` | `9*64B` |
| 状态 | `ChsPitchCtrl` | `0x0203FF80` | 16B `cur/gen/age[8]` |
|  | `ChsPitchSlots` | `0x0203FF90` | 64B `slots[8]` |

> 校验：`arm-none-eabi-objdump` / capstone 对 `baserom.gba` 反汇编，`FontFuncTable` 指针与 `GetGlyphTilePointers` 跳表 `cmp r0,#6; bhi` 吻合。

## 3. 为何不能“零自实现”

* **width 12 越界**：官方 `DrawGlyphTile:3877` 用 `sGlyphMasks[9][8]` 与 `sShiftFuncs[9]`，索引 `width` 仅 `0..8`，`12` 直接越界。`GetGlyphWidth=12` 裸交官方即崩。
* **F9 4字节消费**：官方 `ProcessCurrentChar` 每次 `index++` 取 `1B`，`F9 00 ll tt` 需一次消费 `4B` 并 `index+=3`，不钩 `PrintNextChar` 会把 `ll/tt` 当独立 PCS 查 `Type1Map` 乱码。
* **12px=8+4 spill**：官方单趟只写一列 `8px`，`startPixel+width>8` 的 `mask` 清列会把下字左 4 列擦掉。中文 `128B` 需拆 `TL/BL + TR/BR` 两趟 `spill`，且 `chs_px &7` 相位需跨字累积，官方 `CURSOR_X/TILE_OFFSET` 无此累积。

结论：可委托的是“取址/算索引/贴图/调色”，必须自留的是“4字节消费 + 8+4 两趟调度 + 相位累积”。

## 4. 最小自实现范围（半自绘）

保留 `DrawGlyphTiles_hook.c` 中：
* `chs_bind_pitch_slot` / `pitch_reset` / `ChineseTileState` 相位管理
* `drawGlyph_Adv` 的 `8+4` 两趟调度 + `spill` 判断 + `chs_px` 累积
* `IWRAM copy_tile32`（GBA VRAM 禁 `byte` 写，`copy_tile32` 8×32bit 为硬件约束）

委托化（改为官方调用）：
* `vram_tile` / `linear_cursor_tile` / `compute_mode2_pair` / `avoid_dex_ui_tile` → 改调官方 `GetCursorTileNum` 逻辑（`0x08003500` 段）与 `UpdateTilemap@0x080036DC`（已委托）
* `put_px/get_px` 的颜色重映射 → 改调官方 `CopyGlyph1/2bpp@0x08003830/0x080038A0`（已委托，需补齐 `font 0/1/2/6` 的 1bpp 路径）

## 5. 实现方案

### 5.1 Hook1: PrintNextChar（必留）

* 位置：`main.asm:16 .org PrintNextChar_RegularGlyph` / `PrintNextChar_entry.s:33`
* 逻辑：`r4=win, r3=cur_char`；若 `textMode==2`（战斗血条缓冲，`game.h:320`）直接 `return 0` 交官方；若 `cur_char==0xF9` 按 `op` 分流：`F9 00 ll tt` → `pack_glyph_index` → `gidx` → `WIN_TEXT_INDEX+=3` → 入 Hook2/3/4 委托路径并 `return 1`；`F9 80`/slot 同理；否则 `return 0` 交官方 `FontFunc`。
* 验收：`WIN_TEXT_PTR@0x10` 与 `WIN_TEXT_INDEX@0x14` 推进正确，无悬空 `F9`。

### 5.2 Hook2: GetGlyphWidth / GetStringWidth

* 位置：`GetGlyphWidth@0x08004228`（6 调用方）、`GetStringWidth@0x08004530`（125 调用方）
* 逻辑：`GetGlyphWidthHook@PrintNextChar_entry.s:101` 已实现 `F9->12/10, JP PCS 0x01..0x1E except 06/1B ->4, else 8`，保留；`GetStringWidth_hook.c` 需同步按 `F9` 展开算 `12/8` 并处理 `slot` 命中流（当前 `game.h:304` 声明）。
* 验收：对话框换行、居中、地图名弹窗按 `12` 排版，无提前换行。

### 5.3 Hook3: GetGlyphTilePointers（新增 IWRAM 摆渡）

* 位置：`0x08003730`
* 逻辑：`if glyph>=0x100`（`PrintNextChar` 注入的伪 glyph）则 `*upper = iwrap_tmp; *lower = iwrap_tmp+32;` 将 `FontChsNormal + (gidx<<7)` 的 `TL/BL` 展开为官方 `32B/tile` 格式后返回；否则 `bx 原函数`。
* 关键：官方 4参，勿传 `language`（`game.h:327` 注释：传 `1` 会使 `r1=glyph=1, r2` 被当指针）。

### 5.4 半自绘：DrawGlyphTiles 8+4 调度

* 位置：`DrawGlyphTiles_hook.c:342 drawGlyph_Adv`
* 改动：第一趟 `8px TL/BL` 与第二趟 `4px TR/BR` 的 `dest` 取址改调官方 `GetCursorTileNum` 公式（`x=CX+TX+TILE_BASE, y=CY+TY, idx=x+y*30`）或直接 `bl 0x08003708`，`UpdateTilemap` 保持 `chs_update_tilemap` 委托，`CopyGlyph` 保持 `chs_copy_glyph_*` 委托。保留 `chs_px/base_tx` 相位与 `spill` 合并。
* 验收：`TILE_OFFSET@0x18` 与 `CURSOR_TILE_X@0x1B` 与官方 `Mode2/Linear` 一致，无 `12px lag` 导致的 `双▼`（`WaitArrow_Prepare_C:110` 依赖）。

## 6. 数据流（委托后）

```
F9 00 ll tt --PrintNextChar--> gidx --GetGlyphTilePointers(IWRAM摆渡)--> upper/lower(32B)
                |
                +--GetGlyphWidth=12--> width
                |
                +--drawGlyph_Adv(8+4) --官方GetCursorTileNum--> abs_u/l --官方CopyGlyph--> IWRAM temp --copy_tile32--> VRAM --官方UpdateTilemap--> tilemap
```

## 7. 验收

1. `hook/build.bat` + `armips main.asm` 通过，`out/game.bin` 正常生成。
2. 执行仓库根 `build.bat` 打包 `roms/outputs`，`translate.build.json` 无 `width` 异常。
   （不要手抄 `meowth full` 命令，模块清单以根 `build.bat` 为准，见 `docs/PACK_ROM.md`）
3. 真机/mGBA：对话框/商店/队伍/图鉴/战斗 对话按 `12` 排版，无切半、无 `双▼`、无黑条（`CHS_UI_ICON 0x1E8..0x1FF` 未被踩）。
4. 原日文 `00..FF` 假名/数字仍走官方 `FontFunc`，纹理正确。

## 8. 风险与不做事项

* 不改 `FontFuncTable` 表项，仅在上游 `PrintNextChar` 分流；不引入 `JP→FontFunc` 双路径（会踩 `ChineseTileState`）。
* 不假设 `width 12` 可裸交官方 `sGlyphMasks`。
* `BattleIfGfx@0x02020004` 的 `textMode==2` 窗口永不接管。
