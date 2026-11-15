# 存档确认界面（レポート）乱码 / 右屏铺砖：调研

日期：2026-11-15  
范围：**研究 only**（未改 hook / C / ROM / lexicon / configs）  
游戏：日版红宝石 `POKEMON_RUBY_AXVJ00`（AXVJ）  
分类（`docs/START_HERE.md`）：UI 行为 → 先读 hook/docs + 符号；数据写坏表象 → 辅以 origin-vs-translated 指针/字节比对。

---

## 0. 用户现象（截图）

| 区域 | 观察 |
|------|------|
| 左上信息框 · 地点 | **正常**（紫堇市） |
| 左上 · 玩家/徽章/图鉴/时间标签 | **乱码**：夹杂假名 `あ` / `ちけくえ`；可见「徽章5**こ**」「图鉴あ」「时鉴け」等 |
| 右侧大片 | **严重铺砖**：白底字块反复盖住野外地图（VRAM/tilemap 渗漏） |
| 底部确认句 | P40 后仍缺字；§9 定为 band 别名 + 12px skip（已修） |
| 是/否 | 中文可读；略扁（NOTE） |

已有 bot 场景：`bot/scenes/POKEMON_RUBY_AXVJ00/save.lua`  
路径：野外 → START → 第 6 项「レポート」→ A → `save_confirm` 截图 → 选「否」退出。  
默认存档：`saves/scene_saves.json` → `"save": "Route118_68-7.sav"`。

**本轮已跑**（产物 `_translated_new.gba`）：  
`work/POKEMON_RUBY_AXVJ00/bot/save/20261115T164434_765595/`  
`020.png` = `save_confirm`：translated 复现左上乱码 + 右屏白字铺砖；origin 正常；底框/是否大致正常。

---

## 1. A. Origin 绘制路径

### 1.1 调用链（对照美版 `pret/pokeruby` `src/start_menu.c` + `src/save_menu_util.c`；日版为底）

```
StartMenu_SaveCallback
  → SaveGame / SaveCallback*
  → SaveDialogCB_DisplayConfirmMessage
       Menu_EraseScreen（或等价清屏）
       HandleDrawSaveWindowInfo(0, 0)     ← 左上信息框
       DisplaySaveMessageWithCallback(确认句) ← 底框
  → SaveDialogCB_DisplayConfirmYesNoMenu  ← 是/否
```

日版符号（`symbols/pokeruby_jp.sym`，部分 size/入口 UNVERIFIED，以反汇编为准）：

| 符号 | JP 地址 | 角色 |
|------|---------|------|
| `SaveDialogCB_DisplayConfirmMessage` | `0x0806EE80` | 确认阶段入口 |
| `HandleDrawSaveWindowInfo` | 标 `0x0809101C`（size `0x108`） | 信息框总控；**符号入口可能偏进函数中段**，见下 |
| `HandleCloseSaveWindow` | `0x08091124` | 关框擦除 |
| `IsResizeSaveWindowEnabled` | `0x08091198` | 窗宽 12↔13 |
| `PrintSavePlayerName` 等 | `0x0809119C`… | 行绘制（符号 size 亦有偏差） |
| `Menu_DrawStdWindowFrame` | `0x0806F224` | 标准窗框 |
| `Menu_PrintText` | `0x0806F16C` | 印字 |
| `memcpy` | `0x081B31A4` | **标签拷进栈**（见 §1.3） |

美版逻辑摘要（对照用，非交付基座）：

```c
// save_menu_util.c
void HandleDrawSaveWindowInfo(s16 left, s16 top) {
    u32 width = IsResizeSaveWindowEnabled() ? 13 : 12;
    if (FlagGet(FLAG_SYS_POKEDEX_GET)) {
        Menu_DrawStdWindowFrame(left, top, left + width, top + 11);
        PrintSaveMapName(++left, ++top);          // y+0 地名
        PrintSavePlayerName(left, top + 2);       // y+2 玩家
        PrintSaveBadges(left, top + 4);           // y+4 徽章
        PrintSavePokedexCount(left, top + 6);     // y+6 图鉴
        PrintSavePlayTime(left, top + 8);         // y+8 时间
    } else { /* 无图鉴行，高 9 */ }
}
```

打印几何：

- 窗宽 **12 或 13** tile（`IsResizeSaveWindowEnabled` 恒真时多为 13）。
- 标签：`Menu_PrintText(label, x, y)`，左缘 ≈ `left+1`。
- 数值：美版 `MenuPrint_RightAligned(..., x + 12, y)`；日版对应 `bl` 到 `0x08090E5C` / `0x08090F70` / `0x0809104C` / `0x080910E4` 一类右对齐/格式化辅助。

地名 `PrintSaveMapName`：栈上较长缓冲 + `CopyMapName` → **不走**下面的 8 字节标签 memcpy → 与「紫堇市正常」一致。

### 1.2 标签字符串簇（与训练卡共用）

ROM 静态串（file `0x389DEA`…，总线 `0x08389DEA`…），模块名虽叫 **`UI-训练卡`**，但 **存档信息框与训练卡正面共用同一池**：

| 地址 | 原文 | 译文（texts） | 字面池指针 |
|------|------|---------------|------------|
| `0x08389DEA` | しゅじんこう | 玩家 | `0x08091358` |
| `0x08389DF1` | もっているバッジ | 徽章 | `0x08091400` |
| `0x08389DFA` | こ | （未归模块） | `0x08091404` |
| `0x08389DFC` | ポケモンずかん | 图鉴 | `0x08091450` |
| `0x08389E04` | プレイじかん | 时间 | `0x0809149C` |

`texts.json` 模块说明原文：垃圾单字「こ」**不归** `UI-训练卡` → 存档侧徽章数后缀仍为日文「こ」。

确认句：`0x081978E9`「ここまでの かつやくを…」→ 中文；指针站 `0x0806EAE8`。走常规打印，**无** 8 字节栈截断。

### 1.3 日版与美版关键差异：标签先 `memcpy` 进小栈再印

反汇编（origin）——玩家标签构造（`PrintSavePlayerName_SubSp` @ `0x08091312` 一带）：

```
push {r4,r5,lr}
sub  sp, #8              ; 仅 8 字节栈窗
ldr  r1, =0x08389DEA     ; しゅじんこう
mov  r0, sp
movs r2, #7              ; ★ CopyLen = 7
bl   memcpy              ; @0x081B31A4  定长拷，不认 FF
mov  r0, sp
bl   Menu_PrintText      ; 从栈印标签
…                        ; 再右对齐玩家名
add  sp, #8
```

| 行 | SubSp | CopyLen（`movs r2,#N`） | 原文长度（含 FF） | 译文 F7 长度（含 FF） |
|----|-------|-------------------------|------------------|----------------------|
| 玩家 | `#8` @ `0x08091312` | **7** @ `0x08091324` | 7 | **9** |
| 徽章 | `#0x10`（16B） | **9** @ `0x080913AC` | 9 | **9** |
| 图鉴 | `#8` @ `0x0809140A` | **8** @ `0x0809141C` | 8 | **9** |
| 时间 | `#8` @ `0x08091456` | **7** @ `0x08091468` | 7 | **9** |

`game_addrs` / sym 已标 `PrintSave*_SubSp` / `*_CopyLen` / `*_AddSp`，用意就是给这类定长窗留扩展点。

徽章另：把「こ」(`0x08389DFA`) 拷到栈侧再与数字一起印 → 用户所见「徽章5**こ**」。

### 1.4 窗 / tile 基址

- 标准菜单窗：`gMenuWindow` / `Menu_DrawStdWindowFrame` → 与开始菜单同一套 textMode 网格。
- 中文引擎：`PrintNextChar_hook.c` 网格  
  `tile = TILE_BASE + 2 + (row&7)*62 + 2*col`（见 `docs/research/BAG_LIST_TILE_COLLISION.md`、`START_MENU_RESIDUAL.md`）。
- **无** 存档专用 hook；`hooks_origin.s` 各域均无 SaveMenu 订址。

`hook/reference/`：本仓当前 **无** 该目录文件；对照用的是上游 pret 源码 URL + 本地反汇编。

---

## 2. B. 汉化路径改动了什么（可能相关）

### 2.1 字符串注入（已证实）

对 `roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba` vs origin：

| 池 | origin 指针 | translated 指针 | 译文字节（含 FF） |
|----|-------------|-----------------|-------------------|
| 玩家 | `0x08389DEA` | `0x0941E520` RELOC | `f7 00 0d 4e f7 00 05 bd ff`（9） |
| 徽章 | `0x08389DF1` | `0x0941E544` RELOC | 9 |
| こ | `0x08389DFA` | **未改** | `0a ff` |
| 图鉴 | `0x08389DFC` | `0x0941E568` RELOC | 9 |
| 时间 | `0x08389E04` | `0x0941E58C` RELOC | 9 |
| 确认句 | RELOC | 完整 F7 链 + FF | 正常路径 |

### 2.2 `write_plan` CopyLen / name_window：**未**打到这些点

同产物 ROM 上 `PrintSave*` 的 SubSp/CopyLen/AddSp 与 origin **逐半字相同**（例如 `0x08091324` 仍为 `movs r2,#7`）。  
即：图鉴名表那套 `_copy_limit_patches` / `_name_window_patches` **没有**扩大存档标签 memcpy 窗；`game_addrs` 预留符号尚未落地。

历史教训（相关但非本 bug 作者）：`_copy_limit_patches` 曾误扩背包 TM `cmp #7`→`#0x1F`（P39 钉回）；破折号填充曾被误扩（`AXVJ_UI_ISSUES` §10）。说明「扩 cmp/len」工具链危险，且 **存档这组还没扩**。

### 2.3 P16「个」vs 存档「こ」

| 项 | 地址 | 作用 |
|----|------|------|
| P16 | `0x080077A0` → `SuffixGe`「个$」；清空 `0x081BC164` | **标题继续游戏摘要** 徽章后缀 |
| 存档徽章 | 池 `0x08091404` → `0x08389DFA`「こ」 | **未**被 P16 重定向 |

故「徽章5こ」与现状补丁范围一致，不是偶然。

### 2.4 P13–P15「只」

`start_menu.asm` 在 `0x08090EF0` / `0x08090F3C` / `0x08090FAA` 把训练卡背面「ひき」改成 Append「只」。  
属 **TrainerCard_Back_*** 一带，不是存档 `PrintSavePokedexCount` 主标签 memcpy；与左上「图鉴」乱码无直接因果。

### 2.5 `PrintNextChar` 网格 / 背包 Y·col 裁切

- 全局：12px 网格、`grid_tile_resolved`、全 band 本征保留、超 `GRID_TILE_LIMIT` 不写等（P01）。
- 背包专用：`grid_is_bag_list`（模板 `0x081BB544`）才启用 Y≥18 / col≥26 不写。
- 存档窗 **不是** bag list 模板 → 背包裁切 **不会** 保护存档/野外 tilemap。
- 开始菜单残墨修复（arena 从 `TB+2`）：缩小可用本征槽，可能放大「跑飞打印」时的踩踏面，但是 **第二阶** 放大器，不是标签截断的根因。

### 2.6 无存档专用 hook

`PATCHES_INVENTORY` / 各 `hooks_origin.s`：**无** SaveMenu / HandleDrawSave* JMP。  
问题出在「通用引擎 + 定长 memcpy 标签 + 重定位 F7」的组合。

---

## 3. D. `ちけくえ` 类拖尾像什么？

| 机制 | 是否像 | 理由 |
|------|--------|------|
| **定长 memcpy 截断 F7、栈上无 FF** | **最像（主因）** | 译文 9B，CopyLen 7/8；拷贝体无终止符 → `Menu_PrintText`→`PrintNextChar` 读穿栈/邻接字节 → 假名拖尾 |
| 错误长度 / 未终止 PCS | **是**（同上） | memcpy 不按 FF 停，只按 N |
| F7 解码协议本身坏了 | **否（对本屏）** | 底框长句、是/否、地名、徽章标签（CopyLen=9 刚好装下）均能出合法汉字 |
| 纯窗宽不够 | **次要** | 短标签「玩家/图鉴/时间」两字通常装得下；拖尾更像读穿而非裁切 |
| Tile stomping / VRAM 铺砖 | **像后果** | 无 FF 时引擎继续 `grid_emit`/`UpdateTilemap`，把垃圾字形写进菜单/野外共享 BG → 右侧白块反复铺砖 |
| 改 lexicon 凑布局 | 不适用 | 本轮未改；规则也禁止为此改译 |

PCS 对照：`あ=0x01`、`ち=0x11`、`け=0x09`、`く=0x0B`、`え=0x04` —— 与「栈上残字节当假名」相符，而非完整词。

「时鉴け」：时间串前 7 字节 ≈ `F7 00 0b ed F7 00 05`，缺第二字低字节与 FF → 首字「时」可出，后续错码/邻接串（图鉴池在旁）渗入，呈「鉴け」类混合物。

---

## 4. C. 假说排序 + 可证伪测试

| 秩 | 假说 | 预期证据 | 证伪条件 |
|----|------|----------|----------|
| **H1** | 玩家/图鉴/时间：`memcpy` N&lt;译文长 → 无 FF → 打印跑飞 → 乱码+铺砖 | bot `save`：三行乱、徽章较稳；GDB 在 `Menu_PrintText` 看栈前 N 字节无 `FF`；tilemap 右侧大量非空白 | 栈上已有 FF 且仍乱/仍铺砖 |
| **H2** | 右侧铺砖 = H1 跑飞的 VRAM 后果（非独立根因） | 先修/绕过截断后铺砖应明显消退 | 标签已正确终止仍大面积铺砖 |
| **H3** | 徽章「こ」= 未译后缀 + P16 未覆盖存档池 | 静态：`0x08091404` 仍指 `0x08389DFA` | 该池已指「个」仍显示こ |
| **H4** | 网格 band/TB+2 放大踩踏（背包/开始菜单同源） | 仅影响踩哪些 tile；GDB `TILE_BASE`/template ≠ bag | 截断已灭但仍系统性撞字 |
| **H5** | `write_plan` 误扩了存档 CopyLen | 产物 CopyLen 已变 | **已静态证伪**：产物与 origin 相同 |
| **H6** | 确认句/是/否注入坏 | 底框应乱 | **已证伪**（用户截图底框/是否正常） |

### 建议验证手段（本轮不跑 mGBA；脚本已存在）

1. **bot（首选）**  
   ```text
   python bot/run.py POKEMON_RUBY_AXVJ00 save
   ```  
   对照 `save_confirm`：origin vs translated。验收像素：左上四标签、右侧野外是否被白字砖覆盖。

2. **GDB（可选，`--gdb-side translated`）**  
   - 断 `memcpy` @ `0x081B31A4`，过滤 `lr` 回落在 `0x08091326` / `0x0809141E` / `0x0809146A`。  
   - 读 `r0=dst,r1=src,r2=len` 与 dst 前 16 字节是否含 `FF`。  
   - 再断 `Menu_PrintText`，确认 text 指针落在 sp 且无终止。

3. **Tilemap dump**  
   在 `save_confirm` 帧 dump BG0 charBase/tilemap（可参考 `gdb_patcher` cb3 勘验）。H1 真则 translated 侧窗外区出现大量文字 tile 引用；origin 无。

4. **静态（已做一部分）**  
   指针 RELOC + 译文长 9 vs CopyLen 7/8 — 已闭合 H1 的「必要性」；bot/GDB 闭合「充分性」。

---

## 5. E. 仅下一步调查（不改代码）

1. 跑已有 `save` 场景，归档 `work/.../bot/save/<stamp>/` 的 `save_confirm` O/T 对照。  
2. 同一 run 加 GDB：验证三条标签 memcpy 的 `len` 与 dst 无 `FF`（H1）。  
3. 可选：同一帧 tilemap 直方图，量化右侧铺砖（H2）。  
4. 查清 `HandleDrawSaveWindowInfo` **真实函数头**（符号 `0x0809101C` 像中段；`0x08090FCC` 一带有 `push` + 串池 `0x08389D83`）——便于日后补丁订址，本轮只记疑点。  
5. 若 H1 成立，**修复方向候选**（仍勿在本调研轮动手）：  
   - 扩大对应 `sub sp` + `movs r2,#N` + `add sp`（`game_addrs` 已点名的 CopyLen 站），使 N≥译文最长且含 FF；或  
   - 改为美版式 **直接** `Menu_PrintText(重定位指针)`，跳过栈拷；或  
   - 场景钩只包这四条 PrintSave*（协议只加不改）。  
   - 「こ」→「个」：另改存档池指针（或纳入模块），**勿**靠改短译文凑；与 P16 标题路径分开。  
6. **回归面**（修复后）：`save` + `trainer_card`（同串簇）+ `start_menu` 残墨 + `_probe_bag_tm`（防网格回归）。

### 与近期背包 PrintNextChar / write_plan 的关系

| 项 | 关系 |
|----|------|
| 背包 Y≥18 / col≥26 裁切 | **不直接覆盖**存档窗；模板不同 |
| `grid_tile_is_other_col_natural` 全 band | 可能改变跑飞时踩哪些 tile（H4），**不解释**无 FF |
| `write_plan` cmp 误扩 | 历史类比；对本屏 CopyLen **未改**（H5 已证伪） |
| 根因归因 | **优先 H1（存档标签定长 memcpy × F7 变长）**；网格是放大铺砖的下游 |

---

## 6. 结论（一句话）

存档确认左上乱码与右屏铺砖，静态证据强烈指向：**日版用 7/8 字节 `memcpy` 把已重定位的 9 字节 F7 标签拷进 8 字节栈，截断后无 `FF`，打印跑飞**；徽章因 CopyLen=9 刚好装下「徽章」故标签可读，但「こ」后缀故意未译；底框/是/否走正常长串路径故基本完好。

## 7. 参考

- `bot/scenes/POKEMON_RUBY_AXVJ00/save.lua`  
- `docs/START_HERE.md`、`docs/PATCHES_INVENTORY.md`（P13–P16、P37–P40）  
- `docs/research/BAG_LIST_TILE_COLLISION.md`、`docs/research/START_MENU_RESIDUAL.md`  
- `docs/MODULE_BANDS.md`（`UI-训练卡` `0x389D6C–0x389E0B`）  
- `configs/.../hook/patches/save_menu.asm`、`start_menu.asm`  
- pret：`src/save_menu_util.c`、`src/start_menu.c`（对照）  
- 产物抽检：`roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba`

## 8. 修复记录（2026-11-15）

**已做（用户指定）**：`patches/save_menu.asm` **P40** — 玩家/图鉴/时间三处 `sub sp,#8→#16`、`CopyLen→#16`、`add sp,#16`。徽章不动。时间订址：`0x08091456/468/492`（曾偏 +2 已纠）。  
**未做**：「こ」→「个」、数值右对齐间距。  
**验收 bot**：`work/.../bot/save/20261115T165747_569810/` `020.png` — 标签「玩家/徽章/图鉴/时间」可读，右屏铺砖消失；底框仍见「…的活 / …可梦报告」断行。

## 9. 底框缺字 / YesNo（2026-11-15 续）

### 9.1 Origin 路径（符号 + pret 对照 + 反汇编）

| 项 | JP | 备注 |
|----|-----|------|
| `DisplaySaveMessageWithCallback` | 符号 `0x0806ED70` **UNVERIFIED**（该址像 DMA 清屏中段） | 真入口需经 `SaveDialogCB_DisplayConfirmMessage` 链追；美版逻辑见 pret |
| 确认句打印 | `Menu_DisplayDialogueFrame` @ `0x0806F318` → `MenuPrintMessageDefaultCoords` @ `0x0806F360` | 坐标 **(4, 15)**（`mov r3,#4` / `str #0xF`） |
| YesNo | pret：`DisplayYesNoMenu(20, 8, 1)` → 框 `(20,8)–(26,13)` | `HideSaveDialog` = `Menu_EraseWindowRect(20,8,26,13)` |
| FE 换行 | `RunTextPrinter`：`win[0x1B]=0`；`win[0x1D]+=2` | 与 hook `WIN_CURSOR_TILE_X/Y` 一致 |

ROM 译文完整（确认句 11+10 个 F7 + `3D`？ + FF；指针站 `0x0806EAE8` → reloc）。

### 9.2 根因（bot `020` tilemap + VRAM）

**不是** YesNo 地理盖住底框正文（YesNo 行 8–13，正文行 15–18）。  
**是** 12px 网格 `tile = TB+2+(row&7)*62+2*col` 的 **band 别名**：

1. 信息框地名印在 screen **y=1** → `grid_row=0` → **band0**，本征 tile `0x05..0x13`。  
2. 对话 L2 在 y=15+2 → `grid_row=8` → **band0**，同号本征。  
3. `grid_emit` 对 `ncols>1`：本征已被其它格引用 → **只推进游标、不写** → L2 前段「记录到宝」全 skip；L1 末段则因邻列预清占住 `t0+1` 同样 skip。  
4. 屏上表现为「…的活 / ……可梦报告里吗？」（缺 FE 两侧一段）。

Saving 句无 YesNo 也缺字 → 进一步证明主因是 **FE/band 别名 + 12px skip**，不是 YesNo 擦窗。

YesNo「是/否」略压扁：2 行菜单行距按 8px 格，12px 墨水偏紧；次要。

### 9.3 修复（未改 lexicon）

`PrintNextChar_hook.c`：

1. **`grid_band`**：对话区（`cursor_ty ≥ 14` 且 `CURSOR_X<20`）的 band0 **改映 band5**（信息框 band0–4；曾误用 band6，与图鉴说明 L1@y=13 相撞，见 `GLOBAL_12PX_MISSING_GLYPHS.md`）。  
2. **12px 占用**：优先 `find_free` 迁移；对话区迁不到则 **回退写本征**（与 Small 一致），避免再整段 skip。  
3. **`grid_load` phase>0**：从 **tilemap 实指** 读共享列左 4px（迁移后不能再信公式本征号）。

### 9.4 验收

| run | 结论 |
|-----|------|
| `.../bot/save/20261115T173227_179887/` `020.png` | 底框全文「要把至今为止的活跃表现 / 记录到宝可梦报告里吗？」**可读**；信息框标签仍正常 |
| 残留（旧） | 底框右上角偶发碎点；是/否仍略扁 — 未改 YesNo 坐标 / 未改译 |
| 碎点修复 | 对话 FE/FF：`left=cx+ceil(本行px/8)` → `BlankWindowRect(..,26,..)`（禁 CURSOR_TILE_X / right=28） |

**bot verdict（confirm 帧，§9）**：缺字 **PASS**；右缘碎点当时 **NOTE**（见 blank_rest 后复验）。

## 10. 开始菜单「保存→退出」+ band 收窄（2026-11-15）

### 10.1 打印路径

```
BuildStartMenuActions_Normal → 表 @0x0835089C {text,cb}×N
InitStartMenuMultistep → Menu_DrawStdWindowFrame(22,1,…)
Menu_PrintItems(23, 2, n, table)   @0x0806FBBC
  → 每项 Menu_PrintText(str, 23, 2+2*i)
```

| 项 | y | grid_row | band(自然) |
|----|---|----------|------------|
| レポート/保存 | 12 | 6 | 6 |
| とじる/退出 | 16 | 8 | **0** |

指针/译文均正确（保存 `0x0941D378` ≠ 退出 `0x0941D3C0`）。

### 10.2 根因

§9 `grid_band`：`band==0 && cursor_ty≥14` → **一律**映 band6。  
退出在 y=16 被映到 band6，与保存本征撞车 → 保存行显示「退出」。

### 10.3 修复

`PrintNextChar_hook.c`：

1. **band0→band6** 仅当 `CURSOR_X < 20`（对话左缘≈4；开始菜单 x≈23；YesNo≈20）。
2. 对话 `find_free` 失败回退写本征：同样限 `CURSOR_X < 20`。
3. 对话 FE/FF：按本行像素宽起 `Menu_BlankWindowRect` 到 x=26（抑行尾预载假名；勿 CURSOR_TILE_X / 勿 28）。

**P41**：徽章后缀 CopyLen 2→5、栈 16→24、池→`SuffixGe`「个」。

### 10.4 「图鉴左偏」

- 开始菜单：光标在首项时 ▶ 墨迹被误当成字起点；光标移走后与其它项 **同 x**（origin 同）。
- 存档信息框：四标签 first_ink_x 相同；「图」左边竖墨更重，观感偏左（字形，非错位）。

### 10.5 验收 bot

| run | 结论 |
|-----|------|
| `.../bot/start_menu/20261115T180834_491109/` `042.png` | **保存**≠退出；八项可读 |
| `.../bot/save/20261115T180817_609007/` `020.png` | 徽章 **5个**；底框全文可读；右缘碎点仍 **NOTE**（旧） |
| `.../bot/save/20261115T212019_564984/` `020.png` | 徽章 **5个**；底框全文；L1 右缘假名碎点 **已清**（tile21–25） |
