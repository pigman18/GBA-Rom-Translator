# 背包列表撞字 / TM 超框：调研（先不改代码）

日期：2026-11-15  
范围：**研究 only**；未改 `PrintNextChar` / 未加背包 hook。  
约束：日版 AXVJ 为底；协议只加不改；禁止改译文凑布局。

---

## 1. 现象（用户截图 + bot）

| 口袋 | 汉化 | origin |
|------|------|--------|
| 道具 `どうぐ` | 「学习装置」与数量之间多一字（用户认作「剂」），× 消失 | 干净：`がくしゅうそうち × 2` |
| 技能 `わざマシン` | No. 与招式名叠字；行间撞字（如「钢翼机关枪」）；底行渗出黄框 | 日文 No.+名间距正常 |

bot：`_probe_bag_tm`  
- 复现 run：`work/POKEMON_RUBY_AXVJ00/bot/_probe_bag_tm/20261115T142807_847864/`  
- 对照帧：`014`（bag_items）、后续 `bag_tm*`  
- `_analysis/line1_T.png` vs `line1_O.png`：仅 T 侧数量区有残墨

---

## 2. 全网 / pret 对照

美版 `pokeruby` `src/item_menu.c`（对照用，非交付基座）：

| 口袋 | 绘制 |
|------|------|
| Items / Balls `sub_80A4380` | `AlignStringInMenuWindow(name, 0x66)` + `CHAR_MULT` + `AlignInt(…, 0x78)` → **一次** `Menu_PrintText(..., 14, y)`；**无** 行前 Blank |
| Key items | AlignString only |
| TM/HM `sub_80A4548` | BG2 写 No. 图块（0x59/0x69…）后，`sub_80A41E0` 用 `FC 13` 清宽 + AlignString 招式名；Print 仍在 **left=14** |

日版 AXVJ 反汇编（符号 `pokeruby_jp.sym`，函数体起点以 push 为准）：

| 日版入口 | 行为 |
|----------|------|
| `0x080A0874`（道具/球，带数量） | 每行 `Menu_BlankWindowRect(0xF, y, 0x1E, y\|1)` → `ItemId_GetName` → `Menu_PrintText(name, 0xF, y)` → `0x080A071C` 在 **left=0x1A** 打数量 |
| `0x080A0904`（重要道具） | Blank + 只打名字 + Select 图标 |
| `0x080A09A4`（TM/HM） | BG 写 No. 图块 @ col 0xF → Blank → `0x080A0770`（名，宽参 0x10）→ 数量；名 Print **left≈0x11** |
| 总派发 `0x080A0BF4` | 按口袋跳转上述抽屉 |

要点：日版**已经**在每行前 Blank(15..30)；道具名与 × 数量是**两次** Print，不是美版那条 Align 串。  
撞字**不是**「忘了 Blank」，而是 Blank 之后中文网格又把 tile 写穿。

---

## 3. VRAM 铁证（短盖长表象的真因）

BG0：`charBase=2` → tiles `@0x06008000`，tilemap `@0x0600F800`。

道具列表 `014` translated 行 tile 号（cols 14–29）：

```
y=2:  05d 05f … 069  001×5  15b  001  165   ← 学习装置 + ×位 + 数字
y=4:  … 0ad 0af … 0b3 …                 ← PP单项小补剂（剂 @0xad）
y=10: … 157 159 15b 15d …               ← 先制之爪名区
```

跨行**共用同一 tile 号**：

| tile | 格子 A | 格子 B |
|------|--------|--------|
| `0x15b`/`0x15c` | (26,2) 第 0 行 × 位 | (17,10) 第 4 行名字 |
| `0x171`/`0x172` | (16,4) 第 1 行名字 | (28,10) 第 4 行数量 |

因此第 0 行 × 的 VRAM 被第 4 行汉字墨迹覆盖，tilemap 仍指 `0x15b` → 看起来像「学习装置 …（残字） 2」、× 消失。  
残字与「PP…补剂」的 `0xad` **不是**同一 tile；视觉上像「剂」来自笔画巧合/误认，机制是 **tile 号互踩**，不是短串没清长串的 blank 失败。

origin 同路径无上述跨行 duplicate（字少、8px 槽，不触发同一碰撞）。

---

## 4. 引擎根因（`PrintNextChar_hook.c`）

### 4.1 纯函数网格

```
tile = TILE_BASE + 2 + (grid_row & 7) * 62 + 2 * col
```

背包窗实测 `TILE_BASE ≈ 1`（首字 col15 → `0x5f` 等与公式闭合）。

### 4.2 8px 规避 vs 12px 不规避

`grid_tile_resolved`（队伍菜单躲「麻痹」椭圆引入，2026-11-13）：

- `ncols == 1`（Small / × 等）：若本征 tile 已被占用或 VRAM 非空 → **扫空闲 tile 迁移**
- `ncols != 1`（**12px 中文**）或 `textMode==2`：直接 `return t0`，**不查占用**

复现链：

1. 第 0 行数量 `×`（8px）本征 tile `0x75` 不可用 → 规避迁到空闲 `0x15b`，tilemap (26,2)→`0x15b`
2. 第 4 行「先制之爪」12px 在 col17 的本征 tile 恰为 `TB+2+5*62+2*17 = 0x15b`
3. 12px 不规避 → 覆写 `0x15b` 墨迹；第 0 行仍显示该 tile → 撞字

注释已写明：「ncols>1 … 不迁移」——背包列表正是 12px 名 + 8px 数量同窗。

### 4.3 与「之前修改」的关系

| 改动 | 与背包关系 |
|------|------------|
| 开始菜单：arena 从 `TB+2` 起、勿踩 blank | 缩小可用本征槽，**更容易**逼 8px 走规避迁址 |
| `grid_tile_resolved` 躲预载图 | 8px 迁到「看似空闲」tile，随后被 12px 本征公式踩爆 |
| 训练家之眼 P33/P36 Blank+scrub | **场景钩**，不改网格公式；非本 bug 直接作者，但同属「残墨/清屏」一族 |

用户感知「改 TE 后背包坏了」：时间线上网格规避与 TE 邻近；**本 bug 的充分条件是 8px 迁移 + 12px 不迁移**，用当前 ROM 的 tilemap 即可复现，不依赖 TE hook。

### 4.4 `row&7` 与底行

`grid_cell_own` / 本征 band 用 `(row & 7) * 2` 当 tilemap Y。  
列表 `y=16` → `grid_row=8` → `8&7=0`，与顶带 band0 别名 → TM/底行「渗出框外 / 闭背包乱字」的同类风险。

---

## 5. TM 超框 / 撞 No.（第二问题）

日版 TM 抽屉：

1. 在 **BG 装饰层** col15 写 No. 图块（0x59/0x69 等）
2. 招式名从 **left≈17**（或美版等价 14 + 内部控制宽）打 12px 中文  
3. 中文 12px 起步即与 No. 图块列重叠 → 「No46碎岩」叠字  
4. 长名 + 同上 tile 互踩 → 「钢翼」+「机关枪」类合并  
5. 末行 `y` 近框底 + band 别名 → 字渗出黄列表区

origin 假名短、8px，No. 旁仍够空；不是 Blank 矩形左右差一格能单独解释的。

---

## 6. GDB（已跑）

命令：

```text
python bot/run.py POKEMON_RUBY_AXVJ00 _probe_bag_tm --gdb InitTextPrinter --gdb-side translated
```

run：`work/POKEMON_RUBY_AXVJ00/bot/_probe_bag_tm/20261115T143845_676577/`  
命中：116 次 → `translated/gdb_probe.log`

背包列表条目（抽样）：

| 字段 | 值 |
|------|-----|
| 模板 | `0x081BB544`（CHS_BAG） |
| textMode | **1**（非 2） |
| fontNum | 3 |
| TILE_BASE | **0x0001**（与 §3 公式闭合） |
| tileData / tilemap | `0x06008000` / `0x0600F800` |
| 学习装置 | cur 起步后名 @ left≈15；栈含 `0x080A08C7` |
| 数量 | 内容 `×\02` 等；栈含 `0x080A0751`；curX≈26 |

TM 侧同窗：串如 `０５吼叫` / `４７钢翼`（编号进文本）；`curY` 见 18/20/22… → 与底行渗出一致。

结论：§4 的 TB=1、8px×走规避、12px 名走本征公式，全部被 GDB 钉死。

---

## 7. 拟修复方案（**尚未动手**；待确认后只挑一条）

| # | 层 | 做法 | 风险 |
|---|----|------|------|
| **A** | 引擎 | 12px（`ncols>1`）也走占用检测；迁移时处理 phase=4 共享列（先整字迁或先 blank 再打） | 动 `PrintNextChar`；需回归队伍/图鉴/开始菜单/TE |
| **B** | 引擎 | 8px 规避禁止迁入「其它行 band 的本征 tile」（扩展 `grid_tile_is_other_col_natural` → 全 band） | 改动面小于 A；可能规避失败回退本征仍撞预载图 |
| **B** | 引擎 | **已实施**：① `grid_tile_is_other_col_natural` 全 8 band；② `grid_cell_own`/`points_to` 用真实光标 Y（禁 `(row&7)*2`）；③ 12px 若本征 tile 已被其它格占用则跳过写入（防 y=18 别名踩 y=2） | 动 `PrintNextChar` |
| **C** | 场景钩 | **已撤 P37**：scrub 同 charBase → 切页撞 UI、空列表。P38 仍撤 | 单点补丁证实有害 |
| **D** | 场景钩 | 数量改回与名同一 Align 串（贴近美版）并加宽 | 改日版流程/串布局，偏重；且不消 tile 公式碰撞 |
| **E** | 禁止 | 改「学习装置」等译文缩短；改 `0x00` 全局铺背景；关 12px | 违规 |

推荐优先论证：**B（限制 8px 迁址范围）或 A（12px 也避让）**；TM No. 叠字另用场景钩把名起点右移 / 打名前 blank No. 旁列——**不加字段、不改 F7 协议**。

验收 bot（修复后必跑）：

1. `_probe_bag_tm`：道具首页无残字、× 在；TM 无叠 No.、底行不渗框  
2. `start_menu` 开→关→开→上下（防 blank 残墨回归）  
3. 队伍菜单状态图标（防椭圆再被踩）  
4. 训练家之眼 list↔detail（防 TE 回归）

---

## 8. 结论（一句话）

背包首页「学习装置…剂/残字」是 **8px 数量规避迁 tile 后被 12px 道具名本征公式踩爆**；TM 乱是 **No. 图块列 + 中文 12px 起点重叠**，再叠加同一网格互踩与 `row&7` 底行别名。日版已有行前 Blank，再 blank 不够；应改网格避让策略或加背包场景钩，**不要改译文**。
