# 放技能黑块 — 诊断记录（2026-08-15）

## 症状

- 战斗中放**带背景动画的招式**（冲浪/怪力/迷昏拳/潜水等，含 `loadbg` 命令）后，
  底部战斗文本对话框出现**纯黑块**，盖住文字。
- 黑块特征：与文本框边框对齐、内部均匀纯黑、左上角有一个 **L 形缺口**（疑似残留字形笔画）。
- 普通招式（伏特攻击等，无背景动画）不复现。
- 原版日文 ROM 不复现。
- 证据截图：`bug/20260815/1.PNG`。

## 已确认的证据链（逐个排除）

按「屏蔽 A → 看黑块是否消失」的二分法，逐步定位到根因层：

| 实验 | 结果 | 结论 |
|------|------|------|
| 移除 tiles stage（无 tiles） | 仍黑块 | **tiles 无关** |
| 原始 JP ROM | 不黑 | 汉化引入 |
| 屏蔽**所有** hook（main.asm 三个 `.org` 全部注释） | 文字乱码，**黑块消失** | **根因在 hook 层**，非字体/文本注入/tiles |
| 只保留**文本 hook**（屏蔽血条+地图名） | 黑块出现 | **根因 = 文本 hook**（PrintNextChar/DrawGlyphTiles） |
| 屏蔽文本 hook 内 `chs_update_tilemap`（只画字不写 tilemap） | 文字消失，**黑块消失** | 黑块与 **tilemap 写入**直接相关 |

### 排除的假设（均被实验证伪）

1. ~~BG0CNT priority 遮挡~~：原版也是 `0x009802` 且正常，priority 与黑块无关。
   在 `DrawGlyph_Chinese_Adv` / `PrintNextChar_C` 加 priority 钳制均无效。
2. ~~字模 tile 号溢出 charblock 0~~：把 `linear_cursor_tile` 钳到 `0x1FF` 后黑块仍在
   （且技能文字乱码，说明文字确实用了很多 tile，但溢出不是黑块直接原因）。
3. ~~blank tile(0x190) 被字模覆盖~~：`ensure_linear_dest_floor` 对战斗文本设 floor=2
   避开 0x190，黑块仍在。

## 最可能的机制（未最终证实）

黑块是 **FillWindow / ClearWindow 的残留**，机制链条如下：

1. 放技能 → 动画脚本 `loadbg` → `LoadMoveBg` 加载背景，同时**背景切换会重绘战斗文本窗口**。
2. 重绘前 **`Text_ClearWindow`（0x08003BA8）** 用 **`GetBlankTileNum()`（0x080041BC）**
   返回的「空白 tile」填充整窗 tilemap。
3. `GetBlankTileNum` 对 textMode==0 返回 **`TILE_BASE`（0x190）**；对 textMode==1+
   特定 fontNum 返回 `TILE_BASE+0xD4`（落在 charblock 1 动画区）。
4. 中文 hook 把字模画到 `TILE_BASE`（0x190）起的 tile，可能**污染了 blank tile 的空白状态**。
5. 于是 ClearWindow 填充时把「被污染的 tile」当空白填满 → 纯黑块。

**遗留缺口**：floor=2 避开 0x190 的实验无效，说明对「blank tile 的精确值 /
FillWindow 填充时机 / 字模到底污染了哪个 tile」的理解仍有缺漏。

## 关键代码/地址参照

- 文本 hook 入口：`ProcessCurrentChar_RegularGlyph = 0x0800336E` → `PrintNextChar`(game.bin)
- 字模绘制：`DrawGlyphTiles_hook.c` `drawGlyph_Adv` / `draw_glyph_tile_12` / `linear_cursor_tile`
- tilemap 写入：`chs_update_tilemap` → ROM `UpdateTilemap = 0x080036DC`
  → `GetCursorTilemapPointer = 0x08003708`（tilemap 基址取自 `template[0x10]`）
- 字模写入：`vram_tile` → `template[0x0C]`（tileData 基址）`+ tile*32`
- 清屏：`Text_ClearWindow = 0x08003BA8` → `0x08003C00`（用 `GetBlankTileNum` 填充）
- 空白 tile：`GetBlankTileNum = 0x080041BC`
  - textMode==0 → `TILE_BASE`（win[0x16]）
  - textMode==1 → 按 fontNum 分表，部分返回 `TILE_BASE+0xD4`
- 战斗文本窗口：dialogue `TILE_BASE=0x190`（`0x2d812`）、command `TILE_BASE=0x1B8`
  （`0x2d852`）
- 战斗环境背景动画：`LoadMoveBg` 写 `VRAM+0x8000`(charblock 2) + `VRAM+0xD000`(tilemap)
- `MoveBattlerSpriteToBG`：写 `VRAM+0x4000`(charblock 1)/`VRAM+0x6000` + tilemap `0xE000`/`0xF000`

## 下一步建议

要最终定位，最可能有效的方向（按优先级）：

1. **运行时抓战斗文本窗口基址**：mGBA Memory viewer 看
   `TextPrinter=0x03004170`，`template=[0x03004170]`，
   `tileData=template[0x0C]`、`tilemap=template[0x10]`，
   以及战斗中 `GetBlankTileNum` 实际返回值和 ClearWindow 填充的 tile 号。
   这能一锤定音确认真实的 blank tile 值。
2. 确认战斗文本窗口**真实的 textMode/fontNum**（决定 `GetBlankTileNum` 返回 0x190 还是 0x264）。
3. 修复方向（假设确认后）：让中文 hook 的字模**避开 `GetBlankTileNum` 返回的 blank tile**，
   或画字后把 blank tile 恢复为空白。

## hook 改动状态

- 所有 hook 源文件（`main.asm`、`game.h`、`*.c`）在当前记录时**已全部回退到 git HEAD 干净基线**。
- 未提交改动仅剩：`src/meowth/policy.py`（之前 move-use crash 的 4 字节对齐修复）、
  `src/meowth/table_patch.py`（之前遗留），与本次黑块无关。
- 修复尝试 1（按 pitch 强制回填 TILE_OFFSET）**已撤回**：会导致汉化文本消失。
- trace_final.py 已加 textMode!=0 过滤：跳过战斗中血条/命令条打印机，只留正文打印机。
