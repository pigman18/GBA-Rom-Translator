# tm3 文本窗 tile 布局：master 与当前分支的差异（BUG-9）

> 2026-11-20 实跑对照。**不是看代码推断，是两边各自打包 ROM 跑同一场景截图对比。**

## 1. 现象

存档框（tm3）第 1 行「118号道路」被对话框内容覆盖成「?吗?号道路」，
用户实测「刚打开正常，话打完就乱，每次乱的都不太一样」。

## 2. 对照环境

| | master | 当前分支 |
|---|---|---|
| 工作区 | `C:/code/GBA-master`（worktree，分支 master） | `C:/code/GBA-Rom-Translator` |
| hook 产物 | `out/game.bin` 8812 B | `out/hook.bin` 9668 B |
| 场景 | `_probe_save_dialog --save Route118_68-7.sav` | 同 |
| 打包 | `python -m meowth full <rom> --seed-only` | 同 |

master 侧需先补齐（原工作区缺这些）：
```bash
cp roms/origin/POKEMON_RUBY_AXVJ00.gba  C:/code/GBA-master/roms/origin/
mkdir -p C:/code/GBA-master/tools && cp tools/armips.exe C:/code/GBA-master/tools/
cp bot/scenes/POKEMON_RUBY_AXVJ00/_probe_save_dialog.lua  C:/code/GBA-master/bot/scenes/POKEMON_RUBY_AXVJ00/
cp bot/scenes/POKEMON_RUBY_AXVJ00/saves/*.sav  C:/code/GBA-master/bot/scenes/POKEMON_RUBY_AXVJ00/saves/
```

## 3. master 实测：完全正常

```
118号道路
玩家    祐树
徽章    5こ
图鉴    55只
时间    16:41
[对话框] 要把至今为止的活跃表现
         记录到宝可梦报告里吗？
[是否]
```

**8px 数字与 12px 汉字混排也正确**（「5こ」「55只」「16:41」）。

### master 的 tilemap（018 帧，`0x0F800` 文本图块表）

```
row1: 25E 022 023 024 025 026 027 028 029 25F ...
row2: 25E 040 041 042 043 044 045 046 047 25F ...
row3: 25E 05E 05F 060 ... 065 066 067 25F ...   ← 玩家 / 祐树
row4: 25E 07C 07D 07E ... 083 084 085 25F ...
row5: 25E 09A 09B 09C ... 0A3 0A4 25F ...       ← 徽章 / 5こ
row6: 25E 0B8 0B9 0BA ... 0C1 0C2 25F ...
row7: 25E 0D6 0D7 0D8 ... 0DE 0DF 0E0 0E1 260   ← 图鉴 / 55只
row8: 25E 0F4 0F5 0F6 ... 0FC 0FD 0FE 0FF 260
row9: 25E 112 113 114 ... 119 11A 11B 11C 11D   ← 时间 / 16:41
```

**规律：**
- 行距 = `0x3C = 60`（`022 → 05E → 09A → 0D6 → 112`）
- **列间距 = 1**（不是 2）
- 上下半 = 30（`022 → 040`）

⇒ 完全吻合 origin 反汇编公式 `tile = TB + 2 + col + 30*cy`（`docs/AXVJ_TEXT_PIPELINE.md` §0 已记录 `upper = x + y*30`）。

## 4. 根本差异

| | master | 当前分支 |
|---|---|---|
| tile 公式 | `TB + 2 + col + 30*cy` | `TB + 2 + (row&7)*62 + 2*col` |
| **12px 字占 tilemap 列** | **1 列**（像素流） | **2 列**（固定占两列） |
| 行距 | 30 | 62（band 内） |
| band 压缩 | **无** | `row & 7` |
| 上限检查 | **无** | `GRID_TILE_LIMIT = 0x1F0` |

### 4.1 master 为什么 12px 只占 1 列

`text_render.c::DrawGlyphTiles_core`：

```c
startPixel = st->chs_px & 7u;
map_tx     = st->base_tx + (st->chs_px >> 3);
abs_u = GetCursorTileNum_Linear(win, 0, 0);     /* xOff = 0 */
if (startPixel + 8u > 8u)                        /* 只有半列相位才溢出 */
    su = GetCursorTileNum_Linear(win, 1, 0);
...
map_at(win, map_tx, abs_u, abs_l);
st->chs_px += 8u;
```

**12px 字是「8px 主块 + 4px 溢出」，不是占两个整列。**
`chs_px` 是**连续像素流**（0, 12, 24, 36, …），`chs_px >> 3` 就是 tilemap 列。
所以 12px 字只让 `chs_px` 前进 12，tilemap 列只前进 1~2（按需）。

### 4.2 当前分支为什么必然撞

用 `2*col` 让 12px 字**固定占 2 列**：
- 每行最宽 31 字 × 2 列 = 62 tile
- 20 行 × 62 = 1240 tile
- 但字库段只有 `0x1F0 = 496` tile
- ⇒ 只能靠 `row & 7` 把 20 行压成 8 个 band
- ⇒ **row0 与 row8 落到同一 band**
- ⇒ 存档框（cy=1, row=0）与对话框（cy=17, row=8）必撞

### 4.3 master 为什么装得下

12px 占 1 列（像素流）→ 每行最多 31 tile
`30 * 15 + 2 = 452 < 496` ✓
**master 连上限都不检查**（`scene_remap_tile` 只避开图标/光标，直接返回）。

## 5. 已排除的方案（都实测失败）

| 方案 | 失败原因 |
|---|---|
| band 永久映射 `row & 7` | row0 与 row8 同 band，必撞 |
| 全局游标 `TB + TILE_OFFSET` + EWRAM 记忆 | EWRAM 末尾被覆盖 → 「每次乱得都不一样」 |
| 纯函数 `TB+2+2*前缀列` | 不含行信息，多行全串 |
| `62*ridx`（`cy>>1`） | 8px/12px 混排时 cy 奇偶交替，相邻字同 ridx |
| `30*cy` + `2*col` | 4 行正确，但 12px 占 2 列 → 超上限被越界保护吃掉 |
| `col>=16 不翻转` | 图鉴列表全乱（图鉴右半区靠 `col^16` 折回左半） |
| 行槽（`win[0x1E]` 存 slot） | ▶ 光标重绘把 8 槽耗尽后回绕，覆盖存档框 |
| 按 `textptr` 推进槽位 | 游戏复用同一 textptr 缓冲，无法当字段身份 |

## 6. 结论：正确修法

**tm3 改成 master 的「连续像素流」模型：**

1. `tile = TB + 2 + (cx + px/8) + 30*cy`，其中 `px` 是本字段已绘像素
2. `px` 按每字实际字宽累加（8px 字 +8，12px 字 +12）
3. `px` 存 `win[0x1E]`（已反汇编确认空闲：`InitTextPrinter@0x08002C68`
   只初始化到 `[r0,#29]`=0x1D，`0x1E/0x1F` 从未被写；文本引擎区
   `0x08002C00-0x08003C00` 无任何指令读它们；GDB 230 次采样恒为 0）
4. 字段首字（`col == cx`）时 `px` 归零
5. **去掉 band 压缩和 `2*col`**，`grid_store_col` 只对 `row < 8` 生效
   （row >= 8 的旧路径保留给 tm0/tm1，不参与 tm3）
6. `grid_tile_resolved` 对 tm3 直接返回（不做冲突规避，
   否则 8px 字会被 `find_free` 搬到别的行的地盘）

**改动面**：`grid_tile` 的 tm3 分支 + `grid_emit` 的推进逻辑 + `grid_draw_chs`
把 `t->rel` 设为 `px>>3`（这样 `UpdateTilemap` 的 `curTX` 也正确）。
