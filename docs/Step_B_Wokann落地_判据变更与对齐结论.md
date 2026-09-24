# Step B — Wokann 落地：判据变更、架构决策、对齐结论

> 2026-09-12。承接 `docs/Step_A_日版地址与结构映射.md`。
> 对应指令：「① 验收判据改成『中文正常显示 + 任何场景不撞 UI』② 按 Wokann 走 ③ 对齐」

---

## 0. 一句话结论

**判据已改；对齐已完成（零冲突，我们已是 Wokann 的超集）；Step B 的架构决策已被反汇编
锁死 —— 钩点从 `PrintNextChar` 下移到 `DrawGlyphTiles+2`，恢复官方 5 参 ABI，删掉
12px 相位层与 tile 分配器。**

---

## 1. 验收判据变更（指令 ①）

| | 旧判据（已废） | 新判据 |
|---|---|---|
| 内容 | 满池后**文字与 UI 一起空白** = 接入成功 | **中文正常显示 + 任何场景不撞 UI** |
| 性质 | 面向机制（证明「走了同一个分配器」） | 面向结果（游戏能玩、字能看） |
| 验证层 | L1 静态为主 | **L2 画面为主**（进背包 / 领航员 / 对话框 / 战斗 / 图鉴） |

🔴 旧判据是 v20 灾难的根源：它奖励「把 UI 一起搞空」这个行为，于是我们一路在
**拆 UI**，越走越远。新判据要求的是**加法**：字出来、UI 还在。

「不撞 UI」的机制保证（Wokann 天然提供，无需我们写门控）：

> 砖号来自官方 `GetCursorTileNum(win, 0, 0/1)` ⇒ 引擎**已经**把这个窗口该用的砖
> 算好了，我们只是往那块砖写中文字形。**引擎自己不会和自己撞。**

---

## 2. 对齐（指令 ③）—— 已完成，且零冲突

### 2.1 charmap 逐字节比对

```
ours  entries = 6975        wokann entries = 6931
common codes  = 6931        identical     = 6931        differ = 0
汉字段(≥0x100): ours=6809   wokann=6765   common=6765    identical=6765  differ=0
only-ours CN  = 44          only-wokann CN = 0
```

**结论：我们的 `configs/POKEMON_RUBY_AXVJ00/charmap.txt` 是 Wokann
`PMRSEFRLG_charmap.txt` 的严格超集，且前 6931 项逐字节相同、零冲突。**
多出的 44 个是我们额外补的（`1E8D ’`、`1E8E “`、`1E8F ”`、`1E90 ・`、`1E91 祐` 等）。

⇒ **不需要做任何搬移或重排。** 「对齐」这条已经天然满足。

### 2.2 编码方案（已解码，两侧一致）

```
槽号   = (lead << 8) | trail
ROM 址 = base + (槽号 & 0x1FFF) * stride
```

- ASCII 段 `< 0x100`：直用官方 charmap 单字节，**不占汉字槽**（90 个空槽 = 控制码，正常）。
- 汉字段 `0x100..0x1BFF`：27 个块 × 256 槽 = 6912 槽。
- **每块末 9 个槽 `0x?F7..0x?FF` 恒空**（escape 保留位，与我们
  `font.config.json` 的 `chinese_leads: [[1,5],[7,26],[28,30]]`
  + `ideospace_bytes: [1,247]` 一致）。
- 实测缺口 737 = `27 × 27.3`，**缺口偏移分布 = 27 个块各自的 `0xF7..0xFF`**
  + 2 个块（`0x?F0..0xF6`）⇒ 完全落在 escape 预留区，**无意外空洞**。

### 2.3 字库容器（`font.config.json`，已自洽）

| label | addr | 几何 | 步进 | 槽数 |
|---|---|---|---|---|
| Big1Bpp | `0x09500000` | `11x11+0+2` | 16 B | 7168 |
| Small1Bpp | `0x09600000` | `9x9+0+5` | 11 B | 7168 |
| Middle1Bpp | `0x09400000` | `9x11+0+2` | 13 B | 7168 |

生成器 `scripts/build_font_1bpp.py` 校验 `bytes_per_glyph == ceil(W*H/8)`，
与 `addr` 指向一致 ⇒ **自洽，无需改动**。

---

## 3. Step A 补完：日版 `DrawGlyphTiles` 全结构实证

### 3.1 地址（全部反汇编实证）

| 符号 | 日版 | 美版 | 备注 |
|---|---|---|---|
| `DrawGlyphTiles` | **`0x08003630`** | `0x08006874` | 🔴 本次补入 `game_addrs.asm` |
| `GetGlyphTilePointers` | `0x08003730` | — | 已存在 |
| `GetCursorTileNum` | `0x08003708` | `0x080069D8` | 已存在（命名 `GetCursorTilemapPointer`） |
| `DrawGlyphTile_UnshadowedFont` | `0x08003830` | — | 已存在（命名 `CopyGlyph1bppTo4bpp`） |
| `DrawGlyphTile_ShadowedFont` | `0x080038A0` | — | 已存在（命名 `CopyGlyph2bppTo4bpp`） |
| `UpdateTilemap` | `0x080036DC` | `0x08006954` | 已存在 |

⚠️ `symbols/pokeruby_jp.sym` 里的 `DrawGlyphTiles=0x08005178` / `GetCursorTileNum=0x08003760`
**是错的**（落在别的函数中间），勿采信。

### 3.2 `DrawGlyphTiles` 签名与序言（`0x08003630`）

```asm
08003630  push {r4,r5,r6,r7,lr}     ; ← 函数入口
08003632  mov  r7, r9
08003634  mov  r6, r8
08003636  push {r6,r7}
08003638  sub  sp, #12
0800363a  adds r4, r0, #0           ; r4 = win
0800363c  mov  r8, r1               ; r8 = upperTile  (参数1 = tile 源指针)
0800363e  ldr  r0, [sp, #40]        ; 从栈读第 3 个参数
08003640  ldr  r1, [sp, #44]        ; 从栈读第 4 个参数
08003642  lsls r2, r2, #24 / lsrs r5, r2, #24   ; r5 = arg1 & 0xFF
08003646  lsls r3, r3, #24 / lsrs r7, r3, #24   ; r7 = arg2 & 0xFF
0800364a  ... r6 = [sp+40] & 0xFF   ; r6 = arg3
08003652  mov  r9, r1               ; r9 = arg4
08003654  lsls r4,r4,#16 / lsrs r4,r4,#16       ; r4 = win & 0xFFFF
08003658  add  r3, sp, #8
0800365a  adds r0, r5, #0
0800365c  adds r1, r4, #0
0800365e  add  r2, sp, #4
08003660  bl   0x8003730            ; GetGlyphTilePointers(r6, win16, &upper, &lower)
```

**⇒ 签名 = `DrawGlyphTiles(win, src?, glyph?, ...)` 共 6 参**（4 寄存器 + 2 栈）。
与美版 `DrawGlyphTiles(win, glyph, glyphWidth)` **不同**。

`GetGlyphTilePointers`（`0x08003730`）入参：`r0 = 字型枚举(0..6)`、`r1 = win`、
`r2 = &upperTile`、`r3 = &lowerTile` ⇒ 与我们已实证的
`fontNum 跳转表分派` 一致。

### 3.3 落砖主体（`0x08003664` 起，跳转表 @`0x08003674`）

```
0x08003674 表: 08003678 / 08003694 ×4 / 080036B0 ×3 / 08003694
⇒ 0..6 项：{0:3678, 1:3694, 2:3694, 3:3694, 4:36B0, 5:36B0, 6:36B0}

0x08003694 分支（fontNum 0..3 = 不阴影路径之一）:
    ldr r0,[sp,#4]      ; upper 指针
    mov r1,r8
    adds r2,r7,#0
    adds r3,r6,#0
    bl  0x8003830       ; DrawGlyphTile_UnshadowedFont(...)
    ldr r0,[sp,#8]      ; lower 指针
    mov r1,r8
    adds r1,#32         ; ← +32 = 下半砖（16×16 cell = 4 砖）
    ...
    bl  0x8003830       ; 第二趟：下半

0x080036B0 分支（fontNum 4..6 = 阴影路径）:
    同上，改 bl 0x80038A0  ; DrawGlyphTile_ShadowedFont，两次
```

尾：
```
080036CE  add sp,#12
080036D0  pop {r3,r4} / mov r8,r3 / mov r9,r4 / pop {r4,r5,r6,r7} / pop {r0} / bx r0
```
⇒ **标准 Thumb 序言/尾声，栈净额为 0**（`push {r4,r5,r6,r7,lr}` + `push {r6,r7}` 配平
`pop {r3,r4}`+`pop {r4,r5,r6,r7}`+`pop {r0}`）。

### 3.4 四个调用点（BL 目标全部解码确认 = `0x08003630`）

| 调用点 | 所在函数 | 原始字节 | 解码目标 | 场景 |
|---|---|---|---|---|
| `0x08002AA6` | `InitWindowTileData` `0x08002A50` | `F000 FDC3` | `0x08003630` | tm1 图集装载分区器（每帧 16 次） |
| `0x08002B16` | `0x08002AF4` | `F000 FD8B` | `0x08003630` | 同族第二分区器（循环 0..255） |
| `0x080033A2` | `FontFuncTm2_Origin` `0x0800338C` | `F000 F945` | `0x08003630` | tm2（2D 30 列布局） |
| `0x08003542` | tm0 处理器 `0x08003520` | `F000 F875` | `0x08003630` | tm0 线性打印 |

⚠️ 修正 Step A 文档的笔误：调用点 3 所在函数是 **`0x0800338C`（tm2）**，
不是 tm3（`tm3 = 0x08003494`）。

### 3.5 🔴 决定性发现：日版「连 tint 都走 `DrawGlyphTiles`」

`InitWindowTileData`（`0x08002A50`）是 `fontNum` 跳转表（6 项），
**三个分支的落砖全部经 `DrawGlyphTiles` 完成**：

```
fontNum 0/4 → 0x08002A8C:  bl DrawGlyphTiles   ; 常规字形
fontNum 1/3 → 0x08002AAC:  bl CopyGlyph1bppTo4bpp(0x08003830)  ; 1bpp 直拷，不经 DrawGlyphTiles
fontNum 2/5 → 0x08002ACC:  bl CopyGlyph2bppTo4bpp(0x080038A0)  ; 2bpp 直拷，不经 DrawGlyphTiles
```

**含义**：`DrawGlyphTiles` 是**日版唯一的变宽字形落砖入口**（美版同构）。
⇒ 挂 `DrawGlyphTiles+2` 能覆盖 tm0/tm1/tm2 三条打印路径，**是完备钩点**。

---

## 4. 🔴 架构决策：Step B 怎么做

### 4.1 关键判断 —— 钩点必须下移，但不能换签名

Wokann 钩 `DrawGlyphTiles+2` 后会：

```
bl DrawGlyphTilesChinese     ; 2 字节 BL 覆盖 original +2
...
; DrawGlyphTilesChinese 内:
mov r6, r0                   ; 保留 win
...
pop r4-r7 / pop r1 / bx r1   ; ← 直接返回调用者，不跑原体
```

它对**美版 ABI**（`r0=win, r1=glyph, r2=glyphWidth`）写的，`[r0,#0x20]` = `*text`、
`[r0,#0x24]` = `tileData`。

**日版 ABI 不同**：`r0=win`（进函数后立刻 `r4 = win & 0xFFFF`）、
`r1 = upperTile**（不是 glyph！）`、`r2..r3 = 两个 byte 参数`、`[sp+40]/[sp+44] = 另两参`。
且日版 `win` 布局：

| 字段 | 日版偏移 | 我们的宏 |
|---|---|---|
| `*text` | `+0x10` | `WIN_TEXT_PTR` |
| `textIndex` | `+0x14` | `WIN_TEXT_INDEX` |
| `tileData` | `+0x20` | `WIN_TILE_DATA` |
| `cursorTileX` | `+0x1B` | `WIN_CURSOR_TILE_X` |
| `cursorX` | `+0x1A` | `WIN_CURSOR_X` |

⇒ **Wokann 的 `DrawGlyphTilesChinese.s` 一个字都不能照抄。**

### 4.2 日版 ABI 下无法从 `r1` 拿到字形

日版进 `DrawGlyphTiles` 时 `r1` 是 `upperTile` 指针，字形码在 `GetGlyphTilePointers`
内部才被解出来。所以**在 `+2` 处我们拿不到「这是哪个字」**。

两条出路：

| 方案 | 做法 | 评价 |
|---|---|---|
| **B1（推荐）** | 钩 `DrawGlyphTiles+2` → 从 `win[0x10]` + `win[0x14]` 自取当前字 | Wokann 同款；只需自己解 charmap lead/trail 推进 `textIndex` |
| B2 | 钩在 4 个调用点附近 | 侵入 4 处，且 tm0/tm1/tm2 三份 ABI 各异 ⇒ 更多分支 |

`textIndex` 是 `uint16`（日版 `strh r2,[r6,0x1E]` 实证在 Wokann 里；我们 `WIN_TEXT_INDEX=0x14`）。
⇒ **B1 可行**：`ch = *(uint8_t*)(win[0x10] + win[0x14])`。

### 4.3 落砖只需两趟 —— 且两趟目标砖由引擎算好

```c
u16 砖号_TL = GetCursorTileNum(win, 0, 0);   /* 0x08003708 */
u16 砖号_BL = GetCursorTileNum(win, 0, 1);
void *dst_TL = (void*)(win[0x20] + 32 * 砖号_TL);
void *dst_BL = (void*)(win[0x20] + 32 * 砖号_BL);
```

`GetCursorTileNum`（`0x08003708`）实证语义：

```asm
08003708  ldrb r2,[r0,#27]   ; cursorTileX (0x1B)
0800370a  ldrb r1,[r0,#26]   ; cursorX     (0x1A)
0800370c  adds r2,r2,r1
08003712  ldrb r1,[r0,#29]   ; cursorTileY (0x1D)
08003714  ldrb r3,[r0,#28]   ; cursorY     (0x1C)
08003716  adds r1,r1,r3
08003718  lsls r1,r1,#24 / lsrs r1,r1,#19   ; ×32
0800371c  lsrs r2,r2,#24
0800371e  adds r1,r1,r2
08003720  lsls r1,r1,#1
08003722  ldr  r0,[r0,#16]   ; win[0x10] ... 实为 tilemap 基址字段
08003724  adds r0,r0,r1
08003726  bx   lr
```

⇒ **返回的是 tilemap 项地址**，不是砖号。
砖号 = `*(u16*)GetCursorTileNum(...)`（取该地址内容）。
⚠️ `r0` 在 `0x0800371A` 是 `[r0,#0]`（template 指针）→ `[r0,#16]` = template `+0x10` = `tilemap`。

🔴 **这解释了为什么「引擎自己不会和自己撞」成立**：砖号是引擎在自己的
tilemap 里**已经写好**的值，我们只是把字形画到引擎指定的那块砖上。

### 4.4 要删的东西（Step B 的「去代码」部分）

| 删除项 | 文件 | 理由 |
|---|---|---|
| 12px 相位层（`v8_phase_*` / `CHS_PHASE_*` / `ADDR_CHS_PHASE`） | `tile_alloc.c` / `game.h` | Wokann 模型无相位 —— 引擎每字推进 `cursorTileX`，无半列 |
| tile 分配器（`v8_alloc_n` / `v8_alloc_tile` / `v8_ui_alloc` / ours 位图） | `tile_alloc.c` | 砖号改由官方 `GetCursorTileNum` 提供 |
| `PrintNextChar_hook.c` 的落砖段（`blend_glyph_4bpp` + `win_set_u32(dst + adv*0x40)`） | text/ | 钩点下移到 `DrawGlyphTiles` |
| `V18_UI_ON` / `v20_lz_ui_C` / `lz_ui_sites.h` 白名单 | 多处 | 不再需要「UI 总开关」（判据已改） |

⚠️ **`v8_alloc_*` 可能还有非落砖用途**（如 `Text_ClearWindow` 的清区）。
**删除前必须 grep 调用点**（铁律 10：「没找到调用点」≠「不在路径上」）。

### 4.5 保留的东西

- `GetGlyph(win, code, out128, outWidth, font_lib)` @ `text_translater.c:82`
  —— **它本来就是「从 ROM 按需取字」= Wokann 机制**，直接复用。
- 字库 3 个 1bpp bin + `font.config.json` —— 已对齐，不动。
- `InitTextPrinter` 钩子 —— 若只用于复位相位则可删；若还做别的需保留。
- `PrintNextChar` 钩子 —— 用于 FD 占位符 / SlotTable 拦截（`ADDR_SLOT_TABLE`），
  **与落砖无关，保留**。

---

## 5. 实施顺序（Step B）

```
B0  加 DrawGlyphTiles equ 0x08003630 到 game_addrs.asm            ✅ 已完成
B1  L3 gdb 采集：在 0x08003630 断点，采 win 全字段 + GetCursorTileNum
    返回值，确认（a）win[0x10]/[0x14] 在钩内是当前字
              （b）砖号推进 = +1/字，无相位
              （c）tm0/tm1/tm2 三路都过这里
B2  写 DrawGlyphTilesChinese（Thumb，日版 ABI），
    钩 .org DrawGlyphTiles + 2 → bl
B3  收窄 PrintNextChar_hook：只留 SlotTable/FD 拦截，删落砖段
B4  grep v8_alloc_* 调用点 → 确认无残余依赖后删分配器与相位层
B5  build_sh_equiv.sh → pack_no_llm.py → L2 画面验收（背包/领航员/对话/战斗/图鉴）
```

**B1 是唯一还缺的输入**，且必须在写汇编前做完 —— 否则就是 v17/v20 那种「没自证就动手」。

---

## 6. 与旧方案的关系

| 方案 | 状态 |
|---|---|
| v8/v9/v12 自造分配器 | ❌ 废（本次 Step B 删除对象） |
| v17 `GetBlankTileNum` 门控 | ❌ 废（判据错） |
| v18 `V18_UI_ON` UI 总开关 | ❌ 废（判据已改） |
| v19 LZ 总闸 / v20 LZ 白名单 | ❌ 废（`party_menu.c:623` 整块清 VRAM 打架） |
| `docs/S2_不通过cb_screenBase通道方案.md` | 🟡 备选（若 Wokann 仍不够用再说） |
| **Wokann `DrawGlyphTiles+2`** | ✅ **本方案** |
