# 常规 UI 绘制路径普查（pokeruby 源码级）

> 触发：用户实测 v18（`V18_UI_ON=0`，UI 两个号出口全关）后反馈 ——「接管的 UI 目前好像只有对话框那种 UI，常规 UI 都没接管到」。
> 本文回答：**常规 UI 到底在哪画、为什么池子满/开关关对它无效、要接管只能在哪些落点下手。**
> 证据来源：`tools/pokeruby/src/*`（该树已含本项目的 24B `WindowTemplate` 改动）、`scripts/gen_pokeruby_jp.py`。

---

## 0. 结论（三句）

1. **能「接管」的只有窗口体系**：文字、窗框（`Menu_DrawStdWindowFrame` / 对话框架）、内容区底色（`GetBlankTileNum`）。它们**有号可发**（`sTextWindowBaseTileNum` / `sDialogueFrameBaseTileNum`），所以能被分配器控制。✅ v12~v18 已接。
2. **常规 UI（队伍、宝可梦信息页、领航员、PC 箱子、简易聊天）是「静态 BG 层」**：tileset 用 `LZDecompressVram` 解压到**固定 VRAM 地址**，tilemap 是**编译期常量表 / 静态 blob**，直接写进 VRAM 或 `gBGTilemapBuffers[]`。
3. ⇒ **它们从不申请号。池子满、`V18_UI_ON=0`，对它们没有任何影响。**
   这不是「漏了一个 hook 点」，而是**结构上不在分配器体系内**。不存在单一 hook 点；要它们也空，只能在**各自的输出落点**加门。

---

## 1. 两套体系对照

| | A. 窗口体系（走分配器） | B. 静态 BG 层（不走分配器） |
|---|---|---|
| 谁 | 文字 / 窗框 / 内容区底色 | 队伍菜单 / 信息页 / 领航员 / PC 箱子 / 简易聊天 |
| 号来源 | `sTextWindowBaseTileNum(0x03000514)`、`sDialogueFrameBaseTileNum(0x03000516)` ← ⑤/⑥ ← 分配器 | **编译期常量**（`static const u8 …[]`）或静态 tilemap blob |
| 美术来源 | `LoadTextWindowTiles` → `win->template->tileData + 32*号` | `LZDecompressVram(<blob>, <固定 VRAM 地址>)` |
| 铺 tilemap | `DrawStandardFrame(win->template->tilemap, 号, …)`（⑨b） | `gBGTilemapBuffers[bg][…] = 常量` + `DmaCopy16Defvars` / `sub_8095C8C`（`CpuCopy16`）/ `LZDecompressVram(blob, VRAM+…)` |
| 能否被分配器控制 | ✅ 能 | ❌ 不能（没有号） |

关键常量：`BG_VRAM == VRAM`（`tools/pokeruby/include/gba/defines.h:36`）⇒ `BG_CHAR_ADDR(n)=n*0x4000`、`BG_SCREEN_ADDR(n)=n*0x800`。

---

## 2. 逐家族落点（可挂钩点）

### 2.1 队伍菜单（截图 1 的蓝色槽位框）

`tools/pokeruby/src/party_menu.c`

| 步 | 代码 | 落点 |
|---|---|---|
| 美术 | `LoadPartyMenuGraphics()`（:2202）<br>`LZDecompressVram(gPartyMenuMisc_Gfx, BG_VRAM)` | VRAM+0x0000 |
| 美术 | `LZDecompressVram(gPartyMenuMisc_Tilemap, BG_VRAM + 0x3800)` | VRAM+0x3800 |
| 美术 | `gPartyMenuHpBar_Gfx → +0x6000`、`gPartyMenuOrderText_Gfx → +0x6180`、`gStatusGfx_Icons → +0x7180` | |
| 号 | 常量表 `gUnknown_083769D8[]`（:332）= **0x24/0x25/0x27、0x34…0x37、0x44…0x47、0x54…0x57** | 写死 |
| 铺图 | `DrawPartyMonBackground()`（:1013/:1033/:1062/:1086）`gBGTilemapBuffers[2][…] = (c<<12) \| 常量`；`case 0` 先 `memset(&gBGTilemapBuffers[2],0,0x800)` | |
| 落盘 | `ReDrawPartyMonBackgrounds()`（:767）`DmaCopy16Defvars(3, gBGTilemapBuffers[2], BG_VRAM+0x3000, 0x800)` | VRAM+0x3000 |
| 其它 | `PartyMenuWriteTilemap(0x40/0x42/0x44, …)`（:2639）| |

- 现状：底部提示框（`Menu_DrawStdWindowFrame(0,16,23,19)`，:2881）**已接管**（截图 1 里它已无粉框），蓝色槽位框**未接管**。
- 可加门的落点：`ReDrawPartyMonBackgrounds` 的 DMA 调用点（改成填 0 号砖）、或 `LZDecompressVram(gPartyMenuMisc_Tilemap, …)` 调用点。

### 2.2 宝可梦信息页（截图 2）

`tools/pokeruby/src/pokemon_summary_screen.c` —— **整页是一块静态 tilemap blob**，全文件没有 `Menu_DrawStdWindowFrame` / `FillBgTilemapBuffer` / `CopyToBgTilemapBuffer`。

| 步 | 代码（:854/:860/:863，在 `LoadPokemonSummaryScreenGraphics`） | 落点 |
|---|---|---|
| 美术 | `LZDecompressVram(gStatusScreen_Gfx, VRAM + 0)` | VRAM+0x0000 |
| 美术 | `LZDecompressVram(gUnknown_08E74E88, VRAM + 0xE800)` | VRAM+0xE800 |
| 铺图 | `LZDecompressVram(gStatusScreen_Tilemap, VRAM + 0x4800)` | VRAM+0x4800 |

- 文字部分仍走窗口（`Menu_PrintText` → 分配器），所以**字能空、框不能空** —— 与截图 2 完全吻合。
- 可加门的落点：`LZDecompressVram(gStatusScreen_Tilemap, VRAM+0x4800)` 这一条（改成填 0 号砖）。

### 2.3 领航员 / PC 箱子 / 简易聊天（截图 3）

`sub_8095C8C(dest, dest_left, dest_top, src, …, dest_width, dest_height, src_width)`（`pokemon_storage_system.c:166`）

```c
dest_width *= 2;
dest += dest_top * 0x20 + dest_left;
for (i = 0; i < dest_height; i++) { CpuCopy16(src, dest, dest_width); dest += 0x20; src += src_width; }
```

- 就是一个**把静态 tilemap 的若干行 `CpuCopy16` 进 VRAM** 的函数，**没有号**。
- 调用点（全部是 UI）：`pokenav.c:670/790/803/809/903/1045/1049`（`VRAM+0xE800/0xF000/0xF800`）、
  `pokemon_storage_system*.c`（PC 箱子）、`easy_chat_2.c:1275`（`VRAM+0x7000`）。
- **这是这一族里唯一的单点**：门在 `sub_8095C8C` 函数入口即可覆盖 领航员 + PC 箱子 + 简易聊天。

### 2.4 开始菜单 / 对话框 / 地图名（截图 4）—— **已接管**

- `Menu_DrawStdWindowFrame(l,t,r,b)`（`menu.c:174`）→ `TextWindow_DrawStdFrame(gMenuWindowPtr, …)`（`text_window.c:131`）
  → `DrawStandardFrame(win->template->tilemap, sTextWindowBaseTileNum, l, t, r, b)`（`text_window.c:158`）= ⑨b `0x0806212C`，**已门控**。
- 呼叫者：开始菜单 `start_menu.c:304/337`、队伍菜单提示框 `party_menu.c:2881`、地图名 `map_name_popup.c`、选项菜单 `option_menu.c`、领航员 `pokenav.c`。

---

## 3. 为什么不能「抬水位」式地绕开它们（重申）

队伍菜单的槽位框号 **0x24–0x57** 与窗口池（`charBase=2`，池 = 该 charblock 起至 OBJ 区之前）**在数值空间上重叠**，
但二者**用的是不同的 charblock**（队伍菜单美术在 `VRAM+0` = cb0；队伍菜单窗口模板 `gWindowTemplate_81E6CC8` 的
`charBase=2` → `BG_CHAR_ADDR(2)=0x8000` = cb2）。⇒ 不冲突，**也不需要**设不可用区。
（若强行把「UI 静态美术区」登记为禁区，就是被禁止的「登记表/不可用区」。）

---

## 4. 要「接管」它们，可选的三条路

| 路 | 做法 | 代价 / 风险 |
|---|---|---|
| **① 落点加门（推荐）** | 在每个落点加「UI 关 ⇒ 把目标 tilemap 区填 0 号砖」：<br>· `ReDrawPartyMonBackgrounds` 的 DMA（队伍）<br>· `LZDecompressVram(gStatusScreen_Tilemap, VRAM+0x4800)`（信息页）<br>· `sub_8095C8C` 入口（领航员/箱子/聊天） | N 个门（≈3~4 个），每处 8B/12B 桩 + 一个 C 判定；**风险可控，画面效果 100% 可见** |
| ② 一次 LZ 总闸 | 门 `LZDecompressVram`，`dest` 落在屏幕块区就填 0 | **不要**：会把地图/其它 LZ 资源一起关掉 |
| ③ 真正「接入分配器」 | 把各 UI 的 tileset 搬进池子、tilemap 号改成动态 | 等于重写每个 UI 的资源系统；工作量与风险都远超收益 |

### 门判据用哪个触发？

- **与框/底色同源**：问同一个问题「池子现在还能给出一个砖吗」（复用 `v8_scan_find` 那条判定）。
  好处：语义与用户模型一致（「同一个池子，给不出就全空」），并且**不要新的开关变量**。
- 或直接用现成的 `V18_UI_ON` 开关做实验（`0` ⇒ 这些门也一起关）。

---

## 5. 未验证项（动手前必须先做）

1. 上表所有 pokeruby 名称 → **日版 AXVJ00 地址**的映射：
   `LZDecompressVram`、`sub_8095C8C`、`ReDrawPartyMonBackgrounds`、`LoadPokemonSummaryScreenGraphics`。
   `scripts/gen_pokeruby_jp.py` 目前只覆盖少数 VERIFIED 锚点（`GetBlankTileNum` / `Text_ClearWindow` / `Menu_PrintText` 等），
   其余是**偏移推算**，**不可直接拿来打桩**——必须先反汇编核对函数体指纹（例如 `sub_8095C8C` 的
   `dest += dest_top*0x20 + dest_left` + `CpuCopy16` 循环、`LZDecompressVram` 的 LZ77 头解析）。
2. `sub_8095C8C` 的调用点全表是否确实只服务 UI（若有战斗/地图路径也要调用，就不能整函数门控）。
3. 队伍菜单 `gBGTilemapBuffers[2]` 最终落到哪个屏幕块（`+0x3000` 还是模板 `screenBase=15 → +0x7800`）——
   门要填对地址，否则填了不生效或填坏别的东西。
