# POKEMON_RUBY_AXVJ00 — 窗口系统静态分析

> 分析对象：`roms/origin/POKEMON_RUBY_AXVJ00.gba`（日版红宝石，8MB，SHA1 `5C5E5467…`）
> 方法：**纯静态反汇编**（capstone THUMB），不启动模拟器
> 工具：`src/util/ruby_disasm.py`、`scripts/scan_window_templates.py`
> 起始日期：2026-11-03

---

## 0. 可靠性声明（先读这一节）

本文件的结论分三档，每条都标注依据：

| 标记 | 含义 |
|---|---|
| **【实证】** | 有本文件列出的反汇编片段直接支撑，可复现 |
| **【推断】** | 由实证片段推得，但缺少独立验证 |
| **【待动态】** | 静态分析无法确定，需要模拟器/gdb 现场实测 |

### ⚠️ 符号表可信度

`configs/POKEMON_RUBY_AXVJ00/symbols/pokeruby_jp.sym` 由美版符号 + 段内偏移推算而来。
**文本域（`0x08002C00`–`0x08005000`）85 个 `g` 符号中，只有 18 个地址真的是函数头**
（THUMB `push {.., lr}`，即 `0xB5xx` 开头），其余 67 个指向函数内部偏移。

已实测的错例：

| 符号表标称 | 实测真实起点 | 偏差 |
|---|---|---|
| `PrintGlyph_TextMode0 @ 0x08003B08` | `0x08003B10` | -8（符号指向上一个函数的尾部） |
| `PrintGlyph_TextMode1 @ 0x08003B5C` | `0x08003B10` | -0x4C（是 TextMode0 函数内部的分支，不是独立函数） |
| `GetCursorTilemapPointer @ 0x08003708` | `0x080036DC` | -0x2C（是 `UpdateTilemap` 内部） |
| `Text_PrintWindowSimple @ 0x08003730` | `0x08003730` = **`GetGlyphTilePointers`** | 符号名错位（该地址实为字形取址函数，`cmp #6` 查 7 项表跳转） |
| `gWindowTemplate_81E6C3C`…（54 个连续） | 非模板 | 实测为图块数据（`00 ef 00 00 f0 ff fe 0e`…） |

**函数头校验结果【实证】**：

```asm
; GetGlyphTilePointers @ 0x08003730（不是 Text_PrintWindowSimple）
0x08003730  push {r4, lr}
0x0800373C  cmp  r0, #6          ; r0 = fontNum，7 项
0x0800373E  bhi  #0x08003820     ; 越界
0x08003742  ldr  r1, [pc, #8]    ; 分发表
0x08003746  ldr  r0, [r0]
0x08003748  mov  pc, r0          ; 按 fontNum 跳转
```

**因此：本文件所有地址均按「ROM 原始字节 = THUMB 函数头/指令」重新核对过，
不直接采信符号表。** 每个关键结论都附反汇编片段，可自行复验：

```powershell
C:\Python314\python.exe src\util\ruby_disasm.py --sym PrintNextChar --count 60
C:\Python314\python.exe src\util\ruby_disasm.py 0x080036DC --count 20
```

---

## 0.5 美版权威结构 vs 日版反汇编（联网核对，2026-11-03）

> 来源：`pret/pokeruby` 仓库 `include/text.h`（美版红宝石反编译工程）
> 抓取：`https://api.github.com/repos/pret/pokeruby/contents/include/text.h?ref=master`

### 0.5.1 `struct WindowTemplate`（美版权威，28 字节）

```c
struct WindowTemplate
{
    u8 bgNum;              // +0x00
    u8 charBaseBlock;      // +0x01
    u8 screenBaseBlock;    // +0x02
    u8 priority;           // +0x03
    u8 paletteNum;         // +0x04
    u8 foregroundColor;    // +0x05
    u8 backgroundColor;    // +0x06
    u8 shadowColor;        // +0x07
    u8 fontNum;            // +0x08
    u8 textMode;           // +0x09
    u8 spacing;            // +0x0A
    u8 tilemapLeft;        // +0x0B
    u8 tilemapTop;         // +0x0C
    u8 width;              // +0x0D
    u8 height;             // +0x0E
    u8 *tileData;          // +0x10（1 字节 padding 后 4 字节对齐）
    u16 *tilemap;          // +0x14
    u32 maybeUnused;       // +0x18
};                         // 总大小 0x1C = 28
```

### 0.5.2 与日版反汇编逐字段对照（**完全一致**）

日版 `Text_InitWindow @ 0x08002C68` 的读取顺序（见 §2.1 反汇编）与美版字段逐一吻合：

| 日版反汇编 | 读取的模板偏移 | 美版字段 | 结论 |
|---|---|---|---|
| `win[0x0A] = tpl[9]` | `+0x09` | `textMode` | ✅ 一致 |
| `win[0x0B] = tpl[8]` | `+0x08` | `fontNum` | ✅ 一致 |
| `win[0x0C] = tpl[5]` | `+0x05` | `foregroundColor` | ✅ 一致 |
| `win[0x0D] = tpl[6]` | `+0x06` | `backgroundColor` | ✅ 一致 |
| `win[0x0E] = tpl[7]` | `+0x07` | `shadowColor` | ✅ 一致 |
| `win[0x0F] = tpl[4]` | `+0x04` | `paletteNum` | ✅ 一致 |

**结论【实证】**：日版 `WindowTemplate` 的布局与美版**相同**。这否定了本文件
§2.2 早前"本作自定义模板"的推断 —— 那就是标准 `WindowTemplate`，
只是 `Text_InitWindow` 只读了其中 6 个字段。

### 0.5.3 `struct Window`（美版）与日版 `win` 的差异

美版 `struct Window`（`text.h`）：

```c
struct Window {
 /*0x00*/ u8 textMode;      /*0x01*/ u8 fontNum;
 /*0x02*/ u8 language;      /*0x03*/ u8 foregroundColor;
 /*0x04*/ u8 backgroundColor; /*0x05*/ u8 shadowColor;
 /*0x06*/ u8 paletteNum;    /*0x07*/ u8 tilemapLeft;
 /*0x08*/ u8 tilemapTop;    /*0x09*/ u8 width;
 /*0x0A*/ u8 height;        /*0x0B*/ u8 win_field_B;
 /*0x0C*/ u8 win_field_C;   /*0x0D*/ u8 delayCounter;
 /*0x0E*/ u8 spacing;       /*0x0F*/ u8 win_field_F;
 /*0x10*/ u8 cursorX;       /*0x11*/ u8 cursorY;
 /*0x12*/ u8 left;          /*0x14*/ u16 top;
 /*0x16*/ u16 state;        /*0x18*/ u16 downArrowCounter;
 /*0x1A*/ u16 tileDataStartOffset; /*0x1C*/ u16 tileDataOffset;
 /*0x1E*/ u16 textIndex;    /*0x20*/ const u8 *text;
 /*0x24*/ u8 *tileData;     /*0x28*/ u16 *tilemap;
 /*0x2C*/ const struct WindowTemplate *template;
};
```

**日版实测（§2.1 反汇编）与美版的关键差异【实证】**：

| 项 | 美版 | 日版实测 | 差异 |
|---|---|---|---|
| `win[0x00]` | `textMode` | **`template` 指针**（`ldr r5,[r0]`） | **布局不同** |
| `win[0x0A]` | `height` | **`textMode`** | 偏移不同 |
| `win[0x0B]` | `win_field_B` | **`fontNum`** | 偏移不同 |
| `win[0x04]` | `backgroundColor` | **`state`**（u16） | 偏移不同 |
| 模板位置 | `win[0x2C]` | `win[0x00]` | 偏移不同 |

> **⚠️ 重要**：日版 `struct Window` 与美版**不是同一套布局**。
> 日版把 `template` 放在 `+0x00`，`textMode`/`fontNum` 放在 `+0x0A`/`+0x0B`。
> 移植美版代码到日版时**不能直接套用 `win` 偏移**，必须按 §2.1 的日版实测表。

### 0.5.4 `SaveBlock1` 队伍字段（顺带确认）

美版 `include/global.h`：

```c
struct SaveBlock1 {
    /*0x234*/ u8 playerPartyCount;
    /*0x238*/ struct Pokemon playerParty[6];
    ...
};
```

这解释了此前诊断火红存档时的现象：`SaveBlock1` 缺失 → `+0x234` 读不到队伍数量。
（注：此处为**红宝石**的布局，与火绿的偏移不同，不可混用。）

---

```
RunTextPrinter (0x08002DE8)
  └─ 循环 { 取字符 → PrintNextChar (0x080032F8) } 直到 win[0x04]==0
        │
        ├─ 控制码 FA..FF → 跳表 @0x08003324（6 项）
        │
        └─ 可印字符 → FontFuncTable[win[0x0A]=textMode] @0x081BB3AC
                          │
                          └─ textMode==1 时再查 FontSubTable[win[0x0B]=fontNum] @0x081BB3BC
                                │
                                └─ 画好后 UpdateTilemap(0x080036DC)
                                      └─ GetCursorTilemapPointer：y*32+x 落址
```

---

## 2. 数据结构（反汇编实证）

### 2.1 TextPrinter（win）字段布局

**依据**：`Text_InitWindow @ 0x08002C68`（VERIFIED，函数头 `push {r4,r5,r6,lr}` = `b570`）

```asm
Text_InitWindow(win=r0, textPtr=r1, lineWidth=r2, cursorX=r3, [sp+0x18]=cursorY)
0x08002C84  ldr  r5, [r0]        ; r5 = win[0x00] = template 指针
0x08002C86  ldrb r4, [r5, #9]    ; tpl[9]
0x08002C88  strb r4, [r0, #0x0A] ; win[0x0A] = textMode   ← 来自 tpl[9]
0x08002C8A  ldrb r4, [r5, #8]    ; tpl[8]
0x08002C8C  strb r4, [r0, #0x0B] ; win[0x0B] = fontNum    ← 来自 tpl[8]
0x08002C8E  ldrb r4, [r5, #5]    ; tpl[5]
0x08002C90  strb r4, [r0, #0x0C] ; win[0x0C] = colorC (前景)
0x08002C92  ldrb r4, [r5, #6]    ; tpl[6]
0x08002C94  strb r4, [r0, #0x0D] ; win[0x0D] = colorD (背景)
0x08002C96  ldrb r4, [r5, #7]    ; tpl[7]
0x08002C98  strb r4, [r0, #0x0E] ; win[0x0E] = colorE (阴影)
0x08002C9A  ldrb r4, [r5, #4]    ; tpl[4]
0x08002C9C  strb r4, [r0, #0x0F] ; win[0x0F] = paletteNum
0x08002C9E  str  r1, [r0, #0x10] ; win[0x10] = text 指针
0x08002CA0  strh r6, [r0, #0x14] ; win[0x14] = textIndex = 0
0x08002CA2  strh r2, [r0, #0x16] ; win[0x16] = lineWidth (像素)
0x08002CA4  strh r6, [r0, #0x18] ; win[0x18] = tileDataOffset = 0
0x08002CA6  strb r3, [r0, #0x1A] ; win[0x1A] = cursorX (像素)
0x08002CA8  strb r1, [r0, #0x1B] ; win[0x1B] = cursorTileX = 0
0x08002CAC  strb r4, [r0, #0x1C] ; win[0x1C] = cursorY
0x08002CB2  strb r1, [r0, #0x09] ; win[0x09] = 0
0x08002C7C  strh r4, [r0, #0x04] ; win[0x04] = 1  (state, 初值 1)
0x08002C7E  strh r6, [r0, #0x06] ; win[0x06] = 0
0x08002C82  strb r4, [r0, #0x08] ; win[0x08] = 0
```

| 偏移 | 名称 | 来源 | 说明 |
|---|---|---|---|
| `0x00` | `template` | 调用者传入 | 指向模板；其 `+0x10` 是 tilemap 指针 |
| `0x04` | `state` | 初值 1 | 文本状态机（见 §4） |
| `0x06` | `delayCounter` | 0 | FC 08 暂停节拍 【推断】 |
| `0x08` | — | 0 | 【待动态】 |
| `0x09` | — | 0 | 【待动态】 |
| `0x0A` | **textMode** | `tpl[9]` | 0..7，决定绘制函数（见 §5） |
| `0x0B` | **fontNum** | `tpl[8]` | 0..6，textMode==1 时决定子处理器 |
| `0x0C` | `colorC` | `tpl[5]` | 前景色 |
| `0x0D` | `colorD` | `tpl[6]` | 背景色 |
| `0x0E` | `colorE` | `tpl[7]` | 阴影色 |
| `0x0F` | `paletteNum` | `tpl[4]` | 调色板号（写入 tilemap entry bit12-15） |
| `0x10` | `text` | 参数 | 指向 PCS 字符串 |
| `0x14` | `textIndex` | 0 | 当前字符下标（u16） |
| `0x16` | `lineWidth` | 参数 | 换行宽度（像素） |
| `0x18` | `tileDataOffset` | 0 | tile 偏移（fontNum 0/4/6 每次 += 2） |
| `0x1A` | `cursorX` | 参数 | 像素游标 |
| `0x1B` | `cursorTileX` | 0 | **tile 列游标**（本作特有） |
| `0x1C` | `cursorY` | 参数 | 行游标（像素） |
| `0x1D` | `cursorTileY` | 0 | tile 行游标 |
| `0x20` | 字形缓冲指针 | — | FontFunc[2] 使用（`ldr r1,[r5,#0x20]`） |

### 2.2 TextWindowTemplate 字段

**依据**：同上反汇编（`tpl[4]`–`tpl[9]` 被逐个 `ldrb` 后存入 win）

| 偏移 | 字段 | 映射到 |
|---|---|---|
| `+0x04` | `paletteNum` | `win[0x0F]` |
| `+0x05` | `colorC`（前景） | `win[0x0C]` |
| `+0x06` | `colorD`（背景） | `win[0x0D]` |
| `+0x07` | `colorE`（阴影） | `win[0x0E]` |
| `+0x08` | **fontNum** | `win[0x0B]` |
| `+0x09` | **textMode** | `win[0x0A]` |

> **⚠️ 注意**：`Text_InitWindow` 只读 `+0x04`–`+0x09` 六个字节，
> `+0x00`–`+0x03` 与 `+0x0A` 以后**它不读**。
>
> 与美版 `include/text.h` 的 `struct WindowTemplate` 对照（见 §0.5.1）：
> `+0x04`–`+0x09` 六个字段名与顺序**与美版完全一致**
> （paletteNum / foregroundColor / backgroundColor / shadowColor / fontNum / textMode）。
>
> 但 `tilemap` 的偏移日版是 `+0x10`、美版是 `+0x14`（见 §2.3.1），
> 说明日版模板在后半段做了压缩。因此**前半段可套美版，后半段不可**。

### 2.3 win[0x00] 指向的模板（tilemap 来源）

**依据**：`GetCursorTilemapPointer @ 0x080036DC` 内（偏移 +0x2C），实测指令

```asm
; GetCursorTilemapPointer(win)
0x08003708  ldrb r2, [r0, #0x1b]  ; r2 = win[0x1B] cursorTileX
0x0800370A  ldrb r1, [r0, #0x1a]  ; r1 = win[0x1A] cursorX
0x0800370C  adds r2, r2, r1       ; r2 = tileX + cursorX
0x08003712  ldrb r1, [r0, #0x1d]  ; r1 = win[0x1D] cursorTileY
0x08003714  ldrb r3, [r0, #0x1c]  ; r3 = win[0x1C] cursorY
0x08003716  adds r1, r1, r3       ; r1 = tileY + cursorY
0x0800371A  ldr  r0, [r0]         ; r0 = win[0x00] = 模板
0x0800371C  lsrs r1, r1, #0x13    ; r1 = (y<<8)>>19 → y*32 （★ 关键）
0x0800371E  adds r1, r1, r2       ; idx = y*32 + x
0x08003720  lsls r1, r1, #1       ; idx *= 2 （u16 字节偏移）
0x08003722  ldr  r0, [r0, #0x10]  ; r0 = 模板+0x10 = tilemap 基址
0x08003724  adds r0, r0, r1       ; 返回 tilemap + idx*2
```

**结论【实证】**：落址公式为

```
tileX = win[0x1B] + win[0x1A]
tileY = win[0x1D] + win[0x1C]
index = tileY * 32 + tileX          ← 32 是硬编码的 tilemap 宽度
address = *(u32*)(win[0x00] + 0x10) + index * 2
```

### 2.3.1 ⚠️ 日版模板 `tilemap` 偏移与美版**不同**

逐条核对了 `0x0800371A` / `0x08003722` 的机器码：

```asm
0x0800371A  6800   ldr r0, [r0, #0x0]    ; r0 = win[0x00]（模板指针本身）
0x08003722  6900   ldr r0, [r0, #0x10]   ; r0 = 模板 + 0x10  ← ★
```

| | 美版 `text.h` | 日版实测 |
|---|---|---|
| `tilemap` 字段偏移 | `+0x14` | **`+0x10`** |

这说明**日版模板不是美版 `WindowTemplate` 的原样**：日版在 `+0x10` 直接放 `tilemap`
（美版 `+0x10` 是 `tileData`、`+0x14` 才是 `tilemap`）。

【推断】日版模板可能是更紧凑的变体（省掉 `tileData` 指针，或 `tileData` 与
`tilemap` 合并）。**因此：`+0x00`–`+0x03` 与 `+0x0F`–`+0x18` 的日版含义
不能按美版套用**，需另做实证 → 标【待动态】。

`lsrs r1, r1, #0x13` 等价于 `(v << 8) >> 19 == v * 32 / 256` 的位运算技巧，
展开后正是 `tileY * 32`。**tilemap 宽度 32 tile = 256 像素**。

---

## 3. 文本状态机（win[0x04]）

### 3.1 RunTextPrinter 主循环

**依据**：`RunTextPrinter @ 0x08002DE8`（函数头 `push {r4, lr}` = `b510`）

```asm
0x08002DE8  push {r4, lr}
0x08002DEA  adds r4, r0, #0
0x08002DEC  b    #0x08002E28
; --- 循环体 ---
0x08002E28  ldrh r0, [r4, #4]     ; r0 = win[0x04] state
0x08002E2A  cmp  r0, #0
0x08002E2C  bne  #0x08002DEE      ; state != 0 → 继续处理
0x08002E2E  movs r0, #1
0x08002E30  pop  {r4}
0x08002E32  pop  {r1}
0x08002E34  bx   r1               ; 返回 1（文本结束）
; --- state == 6 ---
0x08002DEE  cmp  r0, #6
0x08002DF0  bne  #0x08002E02
0x08002DF2  movs r0, #0
0x08002DF4  strb r0, [r4, #0x1b]  ; win[0x1B] = 0
0x08002DF6  ldrb r0, [r4, #0x1d]
0x08002DF8  adds r0, #2
0x08002DFA  strb r0, [r4, #0x1d]  ; win[0x1D] += 2
0x08002DFC  movs r0, #2
0x08002DFE  strh r0, [r4, #4]     ; win[0x04] = 2
; --- state == 7 ---
0x08002E02  cmp  r0, #7
0x08002E04  bne  #0x08002E22
0x08002E06  ldrh r1, [r4, #0x14]  ; textIndex
0x08002E08  adds r0, r1, #1
0x08002E0A  strh r0, [r4, #0x14]  ; textIndex++
0x08002E10  ldr  r0, [r4, #0x10]  ; text
0x08002E12  adds r0, r0, r1
0x08002E14  ldrb r0, [r0]
0x08002E16  bl   #0x080046D4      ; GetExpandedPlaceholder
0x08002E1E  bl   #0x08002DB4      ; 展开占位符后处理
; --- 调 PrintNextChar ---
0x08002E22  adds r0, r4, #0
0x08002E24  bl   #0x080032F8      ; PrintNextChar(win)
0x08002E28  ...（回到循环头）
```

### 3.2 PrintNextChar 的 FA..FF 跳表

**依据**：`PrintNextChar @ 0x080032F8`，跳表在 `0x08003324`（6 个 u32）

```asm
0x080032F8  push {r4, lr}
0x080032FC  ldrh r0, [r4, #0x14]  ; textIndex
0x080032FE  adds r1, r0, #1
0x08003300  strh r1, [r4, #0x14]  ; textIndex++
0x08003306  ldr  r1, [r4, #0x10]  ; text
0x08003308  adds r1, r1, r0
0x0800330A  ldrb r3, [r1]         ; r3 = 当前字符
0x0800330C  adds r0, r3, #0
0x0800330E  subs r0, #0xfa        ; c -= 0xFA
0x08003310  cmp  r0, #5
0x08003312  bhi  #0x0800336E     ; > 0xFF → 可印字符，走 FontFunc
0x08003314  lsls r0, r0, #2
0x08003316  ldr  r1, [pc, #8]     ; [0x08003320] = 0x08003324 (跳表基址)
0x08003318  adds r0, r0, r1
0x0800331A  ldr  r0, [r0]
0x0800331C  mov  pc, r0           ; 跳转
```

跳表内容（`0x08003324`，实测）：

| 字符 | 目标 | 行为【实证】 |
|---|---|---|
| `0xFA` | `0x08003354` | 调 `DrawInitialDownArrow(0x08003F4C)`，然后 `win[0x04] = 9` |
| `0xFB` | `0x0800334A` | 调 `DrawInitialDownArrow`，然后 `win[0x04] = 8` |
| `0xFC` | `0x08003362` | 调 `0x08003110`（FC 子处理器，16 种类型，见 §6），返回值截断 u8 后作为 PrintNextChar 返回值 |
| `0xFD` | `0x08003342` | `win[0x04] = 7`（等待声音） |
| `0xFE` | `0x08003346` | `win[0x04] = 6`（等待按键 / 换行） |
| `0xFF` | `0x0800333C` | `win[0x04] = 0`（字符串结束），返回 0 |

其余分支：

```asm
0x0800333C  movs r0, #0
0x0800333E  strh r0, [r4, #4]     ; FF → state=0
0x08003340  b    #0x08003382
...
0x08003342  movs r0, #7           ; FD → state=7
0x08003346  movs r0, #6           ; FE → state=6
0x0800335C  strh r0, [r4, #4]
0x0800335E  movs r0, #2           ; 返回 2（控制码已消费）
```

### 3.3 状态取值汇总

| `win[0x04]` | 含义 | 依据 |
|---|---|---|
| `0` | 文本结束 | `0x0800333C`（FF）/ `0x08002E2C` 退出循环 |
| `1` | 初始 | `Text_InitWindow` `0x08002C7C` |
| `2` | 正常绘制中 | `0x0800335E`、`0x08002DFE` |
| `6` | 等待按键 | `0x08003346`（FE）；`RunTextPrinter` 处理为「换行」`win[0x1B]=0; win[0x1D]+=2` |
| `7` | 等待声音 | `0x08003342`（FD）；解占位符 |
| `8` | 画了下箭头等待（B） | `0x0800334A`（FB） |
| `9` | 画了下箭头等待（A） | `0x08003354`（FA） |

> 【待动态】`state == 8 / 9` 在 `RunTextPrinter` 中如何处理（本文件只解到主循环的 6/7 分支），
> 需要继续反汇编 `0x08002E38` 之后的片段确认。

---

## 4. textMode：7 项分发表

**依据**：`PrintNextChar` 尾部

```asm
0x0800336E  ldr  r0, [pc, #0x18]  ; [0x08003388] = 0x081BB3AC
0x08003370  ldrb r1, [r4, #0xa]   ; r1 = win[0x0A] = textMode
0x08003372  lsls r1, r1, #2       ; *4
0x08003374  adds r1, r1, r0
0x08003376  ldr  r2, [r1]         ; r2 = FontFuncTable[textMode]
0x08003378  adds r0, r4, #0
0x0800337A  adds r1, r3, #0       ; r1 = 字符码
0x0800337C  bl   #0x081B12DC      ; call_via_r2
0x08003380  movs r0, #1           ; 返回 1（可印字符已画）
```

`FontFuncTable @ 0x081BB3AC` 实测内容（7 项，全部为合法函数头）：

| textMode | 入口 | 首字节 | 函数头 |
|---|---|---|---|
| 0 | `0x08003569` → `0x08003568` | `b510` | ✅ |
| 1 | `0x0800360D` → `0x0800360C` | `b510` | ✅ |
| 2 | `0x0800338D` → `0x0800338C` | `b530` | ✅ |
| 3 | `0x08003495` → `0x08003494` | `b510` | ✅ |
| 4 | `0x08003585` → `0x08003584` | `b500` | ✅ |
| 5 | `0x080035A1` → `0x080035A0` | `b500` | ✅ |
| 6 | `0x080035C9` → `0x080035C8` | `b500` | ✅ |

> 表中地址是 `|1`（THUMB 位）后的值，实际函数起点要 `& ~1`。

### 4.1 各 textMode 的实现（逐个反汇编）

#### textMode 0 — `0x08003568`

```asm
0x08003568  push {r4, lr}
0x0800356A  adds r4, r0, #0
0x0800356C  bl   #0x08003520      ; 画字形（像素）
0x08003570  ldrh r0, [r4, #0x18]
0x08003572  adds r0, #2
0x08003574  strh r0, [r4, #0x18]  ; tileDataOffset += 2
0x08003576  ldrb r0, [r4, #0x1b]
0x08003578  adds r0, #1
0x0800357A  strb r0, [r4, #0x1b]  ; cursorTileX += 1
```

**行为**：调 `0x08003520` 做像素绘制，然后 **tileDataOffset += 2、cursorTileX += 1**
（每字占 2 个 tile 高：upper + lower）。

#### textMode 1 — `0x0800360C`

```asm
0x0800360C  push {r4, lr}
0x08003610  ldr  r2, [pc, #0x18]  ; FontSubTable = 0x081BB3BC
0x08003612  ldrb r0, [r4, #0xb]   ; win[0x0B] = fontNum
0x08003614  lsls r0, r0, #2
0x08003616  adds r0, r0, r2
0x08003618  ldr  r2, [r0]         ; r2 = FontSubTable[fontNum]
0x0800361C  bl   #0x081B12DC      ; call_via_r2 → 二级分发
0x08003620  ldrb r0, [r4, #0x1b]
0x08003622  adds r0, #1
0x08003624  strb r0, [r4, #0x1b]  ; cursorTileX += 1
```

**行为**：**二级分发**。按 `fontNum` 查 `FontSubTable`，再 `call_via_r2`。

`FontSubTable @ 0x081BB3BC` 实测 4 项：

| fontNum | 目标 | 等价于 |
|---|---|---|
| 0 | `0x08003585` | FontFunc[4] |
| 1 | `0x080035A1` | FontFunc[5] |
| 2 | `0x080035C9` | FontFunc[6] |
| 3 | `0x08003585` | FontFunc[4] |

#### textMode 2 — `0x0800338C`

```asm
0x0800338C  push {r4, r5, lr}
0x08003390  adds r5, r0, #0
0x08003392  adds r0, r1, #0       ; r0 = 字符码
0x08003394  ldr  r1, [r5, #0x20]  ; r1 = win[0x20] 字形缓冲
0x08003396  ldrb r2, [r5, #0xb]   ; fontNum
0x08003398  ldrb r3, [r5, #0xc]   ; colorC
0x0800339A  ldrb r4, [r5, #0xd]   ; colorD
0x0800339C  str  r4, [sp]         ; 参数
0x0800339E  ldrb r4, [r5, #0xe]   ; colorE
0x080033A0  str  r4, [sp, #4]     ; 参数
0x080033A2  bl   #0x08003630      ; 绘制
```

**行为**：把 `win[0x20]` 缓冲、`fontNum`、三色作为参数传给 `0x08003630`。
**这是唯一带颜色参数的绘制路径**（其他走 `ApplyColors`）。

> 【待动态】`win[0x20]` 缓冲由谁分配、生命周期几何 → 需现场观察。

#### textMode 3 — `0x08003494`

```asm
0x08003494  push {r4, lr}
0x08003498  bl   #0x08003464      ; 绘制
0x0800349C  ldrb r0, [r4, #0x1b]
0x0800349E  adds r0, #1
0x080034A0  strb r0, [r4, #0x1b]  ; cursorTileX += 1
```

**行为**：调 `0x08003464` 绘制，`cursorTileX += 1`。

#### textMode 4 — `0x08003584`

```asm
0x08003584  push {lr}
0x08003586  lsls r2, r1, #1       ; r2 = 字符码 * 2
0x08003588  ldrh r1, [r0, #0x16]  ; r1 = win[0x16] lineWidth
0x0800358A  adds r2, r2, r1       ; upper = lineWidth + c*2
0x08003590  movs r3, #0x80
0x08003592  lsls r3, r3, #9       ; r3 = 0x10000
0x08003594  adds r2, r2, r3       ; lower = upper + 0x10000
0x08003598  bl   #0x080036DC      ; UpdateTilemap(win, upper, lower)
```

**行为**：**直接写 tilemap**。upper tile = `lineWidth + c*2`，lower tile = upper + `0x10000`
（即 tile 索引 +0x100，表示下半字库区）。

#### textMode 5 — `0x080035A0`

```asm
0x080035A0  push {lr}
0x080035A2  adds r3, r1, #0       ; r3 = 字符码
0x080035A4  ldr  r1, [pc, #0x1c]  ; 宽度表
0x080035A6  lsls r3, r3, #2
0x080035A8  adds r3, r3, r1       ; r3 = 表 + c*4
0x080035AA  ldrb r1, [r3]         ; t[0]
0x080035AC  ldrh r2, [r0, #0x16]  ; lineWidth
0x080035AE  adds r1, r2, r1       ; upper = lineWidth + t[0]
0x080035B4  ldrb r3, [r3, #1]     ; t[1]
0x080035B6  adds r2, r2, r3       ; lower = lineWidth + t[1]
```

**行为**：查 4 字节/项的表取 `(t[0], t[1])` 作为 upper/lower tile 偏移。

#### textMode 6 — `0x080035C8`

```asm
0x080035C8  push {lr}
0x080035CA  adds r3, r1, #0       ; 字符码
0x080035CC  ldrh r2, [r0, #0x16]  ; lineWidth
0x080035CE  adds r1, r2, #0
0x080035D0  adds r1, #0xd4        ; upper = lineWidth + 0xD4
0x080035D6  adds r2, r2, r3       ; lower = lineWidth + c
0x080035DC  bl   #0x080036DC      ; UpdateTilemap
```

**行为**：upper 固定偏移 `0xD4`，lower = `lineWidth + c`。

---

## 5. 落址：UpdateTilemap 与调色板拼接

**依据**：`UpdateTilemap @ 0x080036DC`（函数头 `push {r4,r5,r6,lr}` = `b570`）

```asm
0x080036DC  push {r4, r5, r6, lr}
0x080036DE  adds r6, r0, #0       ; r6 = win
0x080036E0  adds r4, r1, #0       ; r4 = upperTile
0x080036E2  adds r5, r2, #0       ; r5 = lowerTile
0x080036EC  bl   #0x08003708      ; GetCursorTilemapPointer(win)
0x080036F0  ldrb r1, [r6, #0xf]   ; r1 = win[0x0F] paletteNum
0x080036F2  lsls r1, r1, #0xc     ; r1 <<= 12
0x080036F4  orrs r4, r1           ; upper |= (pal << 12)
0x080036F6  strh r4, [r0]         ; tilemap[idx] = upper
0x080036F8  adds r0, #0x40        ; ptr += 0x40  ← ★ 32 项 × 2 字节
0x080036FA  ldrb r1, [r6, #0xf]
0x080036FC  ...                   ; 同样拼调色板
0x080036FE  strh r4, [r0]         ; tilemap[idx + 32] = lower
```

**结论【实证】**：

1. tilemap entry 格式 = `tileIndex | (paletteNum << 12)`
2. **lower tile 写在 `idx + 32`**，即下一行（tilemap 宽 32）
3. 因此一个"字符"占 tilemap 中**竖直相邻的两个格子**（upper=字上半，lower=字下半）

这与 §2.3 的 `y*32+x` 完全一致，互相印证。

---

## 6. FC 子处理器（16 种控制码）

**依据**：`PrintNextChar` 的 FC 分支跳到 `0x08003362` → `bl 0x08003110`

```asm
; FC 子处理器 @ 0x08003110（函数头 push {r4, lr} = b510）
0x08003110  push {r4, lr}
0x08003112  adds r3, r0, #0
0x08003114  ldrh r1, [r3, #0x14]   ; textIndex
0x08003116  adds r0, r1, #1
0x08003118  strh r0, [r3, #0x14]   ; textIndex++
0x0800311E  ldr  r0, [r3, #0x10]   ; text
0x08003120  adds r0, r0, r1
0x08003122  ldrb r0, [r0]          ; r0 = FC 的子类型字节
0x08003124  subs r0, #1            ; 1..16 → 0..15
0x08003126  cmp  r0, #0xf
0x08003128  bls  #0x0800312C       ; 合法
0x0800312A  b    #0x080032EE       ; 越界 → 走收尾
0x0800312C  lsls r0, r0, #2
0x0800312E  ldr  r1, [pc, #8]      ; [0x08003138] = 0x0800313C 跳表
0x08003130  adds r0, r0, r1
0x08003132  ldr  r0, [r0]
0x08003134  mov  pc, r0
```

跳表 @ `0x0800313C`（16 项，实测）与各分支行为：

| 子类型 | 目标 | 字段写入【实证】 | 语义【推断】 |
|---|---|---|---|
| `FC 01` | `0x0800317C` | `win[0x0C]` | 设前景色 C |
| `FC 02` | `0x08003190` | `win[0x0D]` | 设背景色 D |
| `FC 03` | `0x080031A4` | `win[0x0E]` | 设阴影色 E |
| `FC 04` | `0x080031B8` | `win[0x0C]`, `win[0x0D]`, `win[0x0E]` | 三色一次设 |
| `FC 05` | `0x080031E8` | `win[0x0F]` | 设调色板号 |
| `FC 06` | `0x080031FC` | `win[0x0B]` | 设 fontNum |
| `FC 07` | `0x08003210` | `win[0x0B] = (*(u8**)win)[8]` | **恢复模板默认 fontNum** |
| `FC 08` | `0x08003218` | `win[0x04]=4`, `win[0x09]` | 状态 4 + 参数 |
| `FC 09` | `0x08003230` | `win[0x04]=5` | 状态 5 |
| `FC 0A` | `0x08003236` | `win[0x04]=0xA` | 状态 10 |
| `FC 0B` | `0x0800323C` | `bl 0x080724AC`（PlayBGM） | **播放 BGM** |
| `FC 0C` | `0x0800328C` | `bl call_via_r2`（查 FontFuncTable） | 按 textMode 调用字体函数 |
| `FC 0D` | `0x080032B4` | `win[0x1B]` | 设 cursorTileX |
| `FC 0E` | `0x080032CE` | `win[0x1D]` | 设 cursorTileY |
| `FC 0F` | `0x080032E8` | `bl 0x08003BA8`（清窗口） | **清空窗口** |
| `FC 10` | `0x08003264` | `bl 0x080724CC`（PlaySE） | **播放音效** |

> 所有分支的共同点：先 `textIndex++` 读 1 字节参数（`FC 04` 读 3 字节、`FC 0B/10` 读 2 字节），
> 最后汇合到 `0x080032EE` 返回 **2**（表示「控制码已消费，本帧不打印字符」）。

收尾（所有分支汇合）：

```asm
0x080032EE  movs r0, #2       ; 返回 2（控制码已消费）
0x080032F0  pop  {r4}
0x080032F2  pop  {r1}
0x080032F4  bx   r1
```

**对照 hook 层的 `FC_*` 常量**（`hook/src/text/PrintNextChar_hook.c`）：

C 层已实现的 FC 处理与上表一致（`FC_FOREGROUNDCOLOR`/`FC_BACKGROUNDCOLOR`/
`FC_SHADOWCOLOR`/`FC_ALLCOLORS`/`FC_PALETTE`/`FC_FONT`/`FC_DEFAULTFONT`/
`FC_PAUSE`/`FC_WAITBUTTON`/`FC_WAITSOUND` 等），说明 hook 的 FC 分派
与原版 `0x08003110` 的分支一一对应 —— **两套实现可互为佐证**。

---

## 7. 窗口清单

### 7.1 为什么这份文件没有「53 个窗口」的清单

用户曾提到"窗口有 53 个"，但经实测**无法证实**，且找到了更准确的替代答案：

1. 符号表里 `gWindowTemplate_81E6C3C` ～ `gWindowTemplate_81E7294` 共 54 个"连续模板"，
   **实测 `0x081B76E4`（首个）被代码字面量引用 0 次** —— 它不是真模板。
2. 按美版权威 `WindowTemplate` 结构（§0.5.1）+「被引用」+「tilemap 指向 EWRAM/VRAM」
   三重约束扫全 ROM，只剩 22 个候选，且全部是**重复模式数据**
   （`tmap=0x06010601`、`0x02020202`），显然不是模板。
3. 结论：**日版把窗口模板内联在代码里**，由 `Text_InitWindowWithTemplate` 在栈上
   临时构造（见 §7.2.1 的反汇编），ROM 中没有 53 个静态模板数组。

**因此 53 这个数字来源不可靠，本文件改用「窗口实例 = 初始化调用点」来枚举。**

### 7.2 全部窗口实例：37 个函数 / 45 处初始化【实证】

**依据**：`scripts/analyze_text_callers.py` 思路 + `find_callers(0x080030A8)`

`0x080030A8` = `Text_InitWindowWithTemplate`（实测函数头 `push {r4,lr}`），
它做「在栈上建 2 字节临时模板 → `Text_InitWindow` → `PrintNextChar`」。

| # | 函数 | 调用点 | 场景【推断】 |
|---|---|---|---|
| 1 | `CB2_EggHatch_1+0x220` | `0x08040918` | **蛋孵化**提示 |
| 2 | `sub_8049E9C+0x12` | `0x0804759A` | 交换场景（1/N）|
| 3 | `sub_8049ED4+0x14` | `0x080475D4` | 交换场景（2/N）|
| 4 | `sub_8049ED4+0x32` | `0x080475F2` | 交换场景（3/N）|
| 5 | `sub_8049ED4+0x29C` | `0x0804785C` | 交换场景（4/N）|
| 6 | `sub_804A51C+0x1A4` | `0x08047DAC` | 交换场景（5/N）|
| 7 | `SetTradeSceneStrings+0xC4` | `0x08049958` | **交换场景文字** |
| 8 | `sub_804C29C+0x6C` | `0x080499F4` | 交换子流程 a |
| 9 | `sub_804C29C+0xCBC` | `0x0804A644` | 交换子流程 b |
| 10 | `sub_804C29C+0xD34` | `0x0804A6BC` | 交换子流程 c |
| 11 | `_CreateInGameTradePokemon+0x152` | `0x0804B186` | **游戏内交换宝可梦** |
| 12 | `sub_805123C+0xB8` | `0x0804E9E0` | 未知场景（1）【待动态】|
| 13 | `sub_805123C+0xFC` | `0x0804EA24` | 未知场景（2）【待动态】|
| 14 | **`Menu_PrintText`** | `0x0806F16C` | **菜单文本打印**（通用）|
| 15 | `RemoveBagItem+0xA0` | `0x080A5B4C`（3 处）| **背包移除道具** |
| 16 | `CheckPCHasItem+0x34` | `0x080A5CC0`（2 处）| **PC 道具检查** |
| 17 | `RemovePCItem+0x18` | `0x080A5D80` | PC 移除道具 |
| 18 | `CompactPCItems+0x28` | `0x080A5DC8` | PC 道具整理 |
| 19 | `SwapRegisteredBike+0x18` | `0x080A5E10` | 注册自行车交换 |
| 20 | `ItemId_GetName+0x10` | `0x080A5E58` | **道具名** |
| 21 | `ItemId_GetPrice+0x14` | `0x080A5EA0` | 道具价格 |
| 22 | `ItemId_GetHoldEffectParam+0x14` | `0x080A5EE8` | 持有效果参数 |
| 23 | `ItemId_CopyDescription+0x14` | `0x080A5F30`（2 处）| **道具说明** |
| 24 | `ItemId_GetType+0x10` | `0x080A5FF8` | 道具类型 |
| 25 | `ItemId_GetFieldFunc+0x18` | `0x080A6024` | 野外使用函数 |
| 26 | `ItemId_GetBattleUsage+0x20` | `0x080A6050` | 战斗使用方式 |
| 27 | `sub_80AA4F0+0x60` | `0x080A6AC4` | 未知场景（3）【待动态】|
| 28 | `CB2_CrashIdle+0x10` | `0x080A7708`（2 处）| 崩溃/异常画面 |
| 29 | `InitContestResources+0x34` | `0x080A78F8` | **华丽大赛初始化** |
| 30 | `Task_ReadyUpdateHeartSliders+0x8` | `0x080A9F98` | 大赛心跳条 |
| 31 | `Task_UpdateHeartSliders+0x68` | `0x080AA028` | 大赛心跳条更新 |
| 32 | `Task_EndCommunicateFinalStandings+0x2C` | `0x080AA538`（2 处）| 大赛最终名次 |
| 33 | `PrintContestantTrainerName` | `0x080AAB30` | **大赛选手训练家名** |
| 34 | `PrintContestMoveDescription+0x40` | `0x080AB1A0` | **大赛招式说明** |
| 35 | `unref_sub_80B011C+0x2C` | `0x080AC6BC`（2 处）| 未知场景（4）【待动态】|
| 36 | `ContestDebugDoPrint+0x20` | `0x080AD310` | 大赛调试打印 |
| 37 | `DoTVShowTodaysSmartShopper+0x128` | `0x080BD49C`（2 处）| **TV 节目：今日精明买家** |

### 7.2.1 窗口模板的真实构造方式【实证】

**依据**：`0x080030A8` 反汇编

```asm
; Text_InitWindowWithTemplate(win=r0, 模板首字节=r1, lineWidth=r2, cursorX=r3, [sp+0x0C]=cursorY)
0x080030A8  push {r4, lr}
0x080030AA  sub  sp, #4
0x080030AC  adds r4, r0, #0
0x080030AE  ldr  r0, [sp, #0xc]    ; cursorY
0x080030B0  lsls r2, r2, #0x10
0x080030B2  lsrs r2, r2, #0x10     ; lineWidth 截断 u16
0x080030B4  lsls r3, r3, #0x18
0x080030B6  lsrs r3, r3, #0x18     ; cursorX 截断 u8
0x080030B8  lsls r0, r0, #0x18
0x080030BA  lsrs r0, r0, #0x18
0x080030BC  str  r0, [sp]          ; 参数就位
0x080030BE  adds r0, r4, #0
0x080030C0  bl   #0x08002CFC      ; Text_InitWindow8002E4C —— 真正的窗口初始化
0x080030C4  adds r0, r4, #0
0x080030C6  bl   #0x08002DE8      ; RunTextPrinter
```

而 `0x08002CFC` 内部（见 §3 前）在**栈上构造 2 字节模板**：

```asm
0x080030EC  add  r0, sp, #4        ; tpl = &sp[4]
0x080030EE  strb r1, [r0]          ; tpl[0] = 参数1
0x080030F2  movs r0, #0xff
0x080030F4  strb r0, [r1, #1]      ; tpl[1] = 0xFF
```

**结论【实证】**：日版的"窗口配置"不来自 ROM 常量表，而是**调用时用一个字节**
（`r1`，通常是 `fontNum` 或 `textMode` 编码值）在栈上拼出来。

> ⚠️ 因此 `tpl[4..9]`（palette/fg/bg/shadow/fontNum/textMode）在这些栈模板里
> 是**未初始化**的 —— `Text_InitWindow` 会把它们从栈上读到 `win[0x0A..0x0F]`。
> 实际生效值取决于调用者之前栈上的残留 → **必须动态确认**（§8.2）。

---

### 7.2 全部 40 个 RunTextPrinter 调用点（逐个反汇编 + 文本解码）

**方法【实证】**：`scripts/dump_text_strings.py --from-callers`
对每个调用点：回溯函数头 → 扫 `ldr rX,=...` 字面量 → 用 `meowth.jp_pcs.decode_pcs`
解码，得到窗口实际显示的文字。**文字内容即窗口用途的直接证据。**

26 个宿主函数，40 个调用点：

#### A. 文本引擎内部（3 个，非 UI 场景）

| 函数 | 调用点 | 用途 |
|---|---|---|
| `0x08002CC0` | `0x08002CEA` | 窗口初始化后立即打印（`UpdateBGRegs` 路径） |
| `0x08002DB4` | `0x08002DCE` | 字库预渲染完成后打印（`InitWindowTileData` 路径） |
| `0x080030A8` | `0x080030C6` | 模板驱动通用打印（`Text_InitWindowWithTemplate` 路径） |

字面量证据：`0x08002D5C -> 0x081B3A84`（字库数据，非文本）。

#### B. 战斗胜负 / 通信对战（2 个函数，13 个调用点）

| 函数 | 调用点 | 解码出的文本【实证】 |
|---|---|---|
| `0x0800B140` | `0x0800B1CC` `0x0800B238` `0x0800B284` `0x0800B2D8` `0x0800B2EC` `0x0800B320` `0x0800B334` | `\CC0200かち`（胜利）<br>`\CC0200まけ`（失败）<br>`\CC0200ひきわけ`（平局） |
| `0x0800B34C` | `0x0800B3E0` `0x0800B406` `0x0800B42E` `0x0800B456` `0x0800B4B6` `0x0800B4DC` | 通信对战胜负（文本由参数传入，函数内无字面量） |

**窗口用途**：战斗结果横幅（胜/负/平），对战双方各一份。

#### C. 战斗中确认框（5 个函数，5 个调用点）

公共字面量：`0x083DCA1B` = `\CC0505\CC040D0E0Fはい\nいいえ`（是/否）

| 函数 | 调用点 | 附加文本【实证】 | 场景 |
|---|---|---|---|
| `0x08020D58` | `0x08020DD2` | `はい\nいいえ` | 招式 52 效果切换确认 |
| `0x08021118` | `0x0802115C` | `はい\nいいえ` | 招式 59 学新招确认 |
| `0x080218D4` | `0x08021910` | `\CC0202サファリボール` | 招式 5E + 狩猎球提示 |
| `0x08028EEC` | `0x08028F52` | `はい\nいいえ` | 投球动作确认 |
| `0x0802B658` | `0x0802B71E` | `\CC0810つうしんたいきちゅう‥‥` | **通信待机中**提示 |

#### D. 招式选择 / 遗忘（4 个函数，5 个调用点）

| 函数 | 调用点 | 解码文本【实证】 |
|---|---|---|
| `0x0802B4F8` | `0x0802B592` | `\CC0505\CC040D0E0Fどの わざを\nわすれさせたい？`<br>`ノーマル`（属性名） |
| `0x0802B5BC` | `0x0802B62E` | 同上 |
| `0x0802B658` | `0x0802B71E` | 同上 + `つうしんたいきちゅう` |
| `0x0802A25A` | `0x0802A25A` | `\CC0505\CC040D0E0FＰＰ\nわざタイプ／` |
| `0x0802A2C6` | `0x0802A2C6` | 同上 |

**窗口用途**：招式遗忘确认（"要忘记哪个招式？"）、招式属性显示（"PP / 招式类型"）。

#### E. 战斗主菜单（2 个函数，3 个调用点）★ 关键

| 函数 | 调用点 | 解码文本【实证】 |
|---|---|---|
| `0x0802D7C8` | `0x0802D824` | `\CC0505\CC040D0E0Fたたかう  バッグ\nポケモン  にげる` |
| `0x0802D7C8` | `0x0802D864` | `\0Fは どうする？` |
| `0x0802D8C0` | `0x0802D914` | `\CC0505\CC040D0E0FＰＰ\nわざタイプ／` |

**窗口用途**：
- **战斗四键菜单**：たたかう（战斗）/ バッグ（背包）/ ポケモン（宝可梦）/ にげる（逃跑）
- **行动提示**：「（宝可梦名）要怎么做？」
- 招式详情：PP + 属性

> 这是文本化实现的战斗菜单 —— 说明屏上四格菜单**走 PCS 文本**，不是纯图块。

#### F. 队伍 / 背包 UI（2 个函数，2 个调用点）

| 函数 | 调用点 | 解码文本【实证】 | 用途 |
|---|---|---|---|
| `0x0806B288` | `0x0806B2B4` | （无字面量） | 携带物品图标 |
| `0x0806B764` | `0x0806B7AC` | `／`（全角斜杠） | **队伍菜单昵称行**（`PrintPartyMenuMonNickname`），斜杠用于「名字/等级」分隔 |

#### G. 图鉴 / 地区图 / 通信进化（4 个函数，4 个调用点）

| 函数 | 调用点 | 用途【推断】 |
|---|---|---|
| `0x0810DAF6` | `0x0810DAF6` | 图鉴地区分布画面（`Task_PokedexAreaScreen_1`） |
| `0x0810E608` | `0x0810E608` | 通信进化场景加载（`CB2_TradeEvolutionSceneLoadGraphics`） |
| `0x0810FFF4` | `0x08110030` | 通信进化场景任务（`Task_TradeEvolutionScene`） |
| `0x0811004C` | `0x0811007C` | 同上（另一分支） |

解码文本：`0x0811029E -> 0x083D4BE4`、`0x0810D169`、`0x0810D189`（含控制码，需进一步解析）。

#### H. 华丽大赛（2 个函数，3 个调用点）

| 函数 | 调用点 | 用途【推断】 |
|---|---|---|
| `0x08126948` | `0x081269A6` `0x081269E6` | 大赛 AI 指令 5E（`ContestAICmd_unk_5E`） |
| `0x08133F34` | `0x08133F92` `0x08133FCA` | Wally 战斗塔缓冲（`WallyBufferExecCompleted`） |

#### I. 招式动画辅助（2 个函数，2 个调用点）

| 函数 | 调用点 | 用途【推断】 |
|---|---|---|
| `0x08021E2E` | `0x08021E2E` | 招式 69 调整伤害（`atk69_adjustsetdamage`） |
| `0x08029C8A` | `0x08029C8A` | 战斗动作流程（`sub_802C2EC`） |

### 7.3 小结：窗口的 9 大类

| 类 | 函数数 | 调用点数 | 代表文本 |
|---|---|---|---|
| 文本引擎内部 | 3 | 3 | — |
| 战斗胜负 | 2 | 13 | `かち`/`まけ`/`ひきわけ` |
| 战斗中确认框 | 5 | 5 | `はい`/`いいえ` |
| 招式选择/遗忘 | 4 | 5 | `どの わざを わすれさせたい？` |
| 战斗主菜单 | 2 | 3 | `たたかう バッグ ポケモン にげる` |
| 队伍/背包 | 2 | 2 | `／` |
| 图鉴/进化 | 4 | 4 | — |
| 华丽大赛 | 2 | 3 | — |
| 招式动画 | 2 | 2 | — |

> **【待动态】** 上表覆盖的是「会调用 RunTextPrinter 的窗口」。
> 有些 UI（如开始菜单、商店）如果走 `Text_PrintWindowSimple` 等其他入口，
> 不在这 40 个里。下一步应同样扫 `Text_PrintWindowSimple` / `Text_InitWindowAndPrintText` 的调用者。

---

## 8. 待动态清单（静态分析无法确定）

| 项 | 说明 |
|---|---|
| `win[0x08]`、`win[0x09]` 用途 | `Text_InitWindow` 置 0，静态扫描未见读取点 |
| 模板 `+0x00`–`+0x03` 字段 | `Text_InitWindow` 不读，含义未知 |
| `win[0x20]` 缓冲分配者 | textMode 2 使用，分配点在静态扫描中未定位 |
| `state == 8 / 9` 的后续处理 | `RunTextPrinter` 主循环只解到 6/7 分支 |
| FC 子处理器 16 种类型 | `0x08003110` 的 switch 表未完整解出 |
| 场景 → 窗口模板映射 | 模板地址多为动态计算（`add rX,=base+off`），静态未能全部解算 |
| BG 层与窗口的绑定关系 | 模板 `+0x10` 的 tilemap 指针如何生成未追踪 |
| 各窗口的**坐标/尺寸** | 需读模板 `+0x00`–`+0x03`，而该区域含义未确认 |

### 8.1 静态分析未覆盖的文本入口

`RunTextPrinter` 的 40 个调用点已全部追完（§7.2）。另两个候选入口实测调用点极少：

| 入口 | 调用点数 |
|---|---|
| `Text_PrintWindowSimple`（符号标称 `0x08003730`） | 2（但该地址实为 `GetGlyphTilePointers`，符号名错位） |
| `Text_InitWindowAndPrintText` | 0 |
| `Text_UpdateWindow` | 0 |

**推断**：绝大多数窗口文本经 `RunTextPrinter` 打印，§7.2 已覆盖主要场景。
若要覆盖 100%，还需扫 `PrintNextChar` 的直接调用者（4 个，见 §3.2 前的实测）。

### 8.2 建议的动态验证点

| 想确认的事 | 动态做法 |
|---|---|
| **栈模板的实际字段值** | 在 `Text_InitWindow @ 0x08002C68` 的 `0x08002C8A`（读 `tpl[8]`=fontNum）下断点，读 `win[0x00]` 指向的栈地址内容 |
| 某个窗口的 textMode/fontNum | 在 `PrintNextChar @ 0x080032F8` 下断点，读 `win[0x0A]`/`win[0x0B]` |
| 窗口的 tilemap 落址 | 在 `UpdateTilemap @ 0x080036DC` 下断点，看返回值与写入地址 |
| `win[0x20]` 缓冲生命周期 | 在 textMode==2 路径下断点，观察分配/释放 |
| state 8/9 的推进 | 在 `RunTextPrinter` 循环内断点，记录 `win[0x04]` 序列 |
| FC 子处理器分支 | 在 `0x08003110` 下断点，记录子类型字节 |
| 各窗口的坐标/尺寸 | 在 `GetCursorTilemapPointer` 断点，反算 `(tileX,tileY)` 与窗口边界 |

### 8.3 与美版的差异汇总（移植时必读）

| 项 | 美版 | 日版 | 依据 |
|---|---|---|---|
| `WindowTemplate` `+0x04`–`+0x09` | pal/fg/bg/shadow/fontNum/textMode | **相同** | §0.5.2 |
| `WindowTemplate` `tilemap` | `+0x14` | **`+0x10`** | §2.3.1 |
| `struct Window` `+0x00` | `textMode` | **`template` 指针** | §0.5.3 |
| `struct Window` `textMode` | `+0x00` | **`+0x0A`** | §0.5.3 |
| `struct Window` `fontNum` | `+0x01` | **`+0x0B`** | §0.5.3 |
| `struct Window` `state` | `+0x16` | **`+0x04`** | §0.5.3 |
| `SaveBlock1` 队伍数 | `+0x234` | 需另测（红宝石与火绿不同）| §0.5.4 |

---

## 9. 复现命令

```powershell
# 反汇编任意函数
C:\Python314\python.exe src\util\ruby_disasm.py --sym PrintNextChar --count 60
C:\Python314\python.exe src\util\ruby_disasm.py 0x080036DC --count 20

# 查调用者
C:\Python314\python.exe src\util\ruby_disasm.py --sym RunTextPrinter --find-callers

# 扫窗口模板候选
C:\Python314\python.exe scripts\scan_window_templates.py
```

---

## 9.1 全角标点渲染缺陷（2026-11-03 动态发现，**未修**）

> 这是把 bot 扩到「战斗全界面」之后才暴露出来的**真实缺陷**，不是分析结论。

**现象**：战斗开场台词 `啊！野生的雷电球跳出来了！` 里，
两个「！」都渲染成畸形叠字，且把后面的字挤开。

**量化证据**（`scripts/measure_text_row.py`，同一帧的文字行）：

| 侧 | 字形段宽度序列 |
|---|---|
| origin | 12, **8**, 5, 8, 23 … （「！」= 8px，与原版半角一致） |
| translated | 12, **11**, **19**, 11, 11, 11, 9, 11, **7**, **3**, 9 … |

- 原版「！」占 **8px**（半角槽）；
- 译文里出现 **19px** 与 **11px** 的异常段，以及 3px 碎片 ⇒ 标点被按全角画，
  并把相邻字推挤重叠。

**根因**（代码依据）：

1. `configs/POKEMON_RUBY_AXVJ00/charmap.txt` 把 `3C=！`、`3D=？`、`37=。`、
   `3A=、`、`3B=，`、`3E=：` 全部映射到**日文单字节 PCS**（第 84/161/164-168 行），
   注释也写明「Sentence punct … use JP PCS single-bytes」。
2. 但这几个码位在**原版字库里是半角 8px**（上面实测）。
3. `hook/src/text/text_render.c` 的 `GetChineseFontWidthFunc()`（第 85–112 行）
   **只按 fontId 返回固定步进**（Small=8 / 其余=12），完全不看字符。
   于是标点也被按 12px 排，一个 8px 的字形被塞进 12px 的步进里 ⇒ 挤压/叠字。

**影响面**：`translate/texts_translated.json` 里 **3316 / 14572** 条译文含全角「！」。

**待决策的修法**（都还没做，不能猜着改）：

- 方案 A：让 `GetChineseFontWidthFunc()` 对这几个单字节标点返回 8；
  风险：单字节字符走的是原版字体路径，可能根本不进这个函数。
- 方案 B：把标点映射到中文 BDF 里的全角槽（需要 BDF 真有该字形 ——
  实测三套 BDF 里 `！？。，、：；` **全部缺失**，只覆盖 `（）「」『』—～·`）。
- 方案 C：译文层面把全角标点换成原版用的半角，或换成全角但补字模。

> 复现命令：`python scripts/measure_text_row.py <png> --y0 126 --y1 134`

---

## 10. 版本记录

| 日期 | 内容 |
|---|---|
| 2026-11-03 | 初版：textMode/fontNum 分发、落址算法、状态机、FontFuncTable 7 项 |
| 2026-11-03 | 补：FC 子处理器 16 种控制码全部解出（含字段写入映射）|
| 2026-11-03 | 补：全部 40 个 RunTextPrinter 调用点，26 个宿主函数，逐个解码窗口文本 |
| 2026-11-03 | 修：符号表 5 处错位实证（`TextMode0/1`、`GetCursorTilemapPointer`、`Text_PrintWindowSimple`、54 个假模板）|
| 2026-11-03 | 联网核对美版 `pokeruby/include/text.h`：确认 `WindowTemplate` 前 6 字段与日版一致；发现 `tilemap` 偏移日版 `+0x10` vs 美版 `+0x14`；发现 `struct Window` 日美布局不同（§0.5）|
| 2026-11-03 | 补：窗口实例真实枚举 —— 37 个函数 / 45 处 `Text_InitWindowWithTemplate` 调用（§7.2）；证实日版无静态模板数组（§7.2.1）|
| 2026-11-03 | **补 §9.1**：动态采到战斗全界面后，实测发现全角标点渲染畸形（原版 8px / 译文 19px），影响 3316 条译文；三个修法待决策 |
| 2026-11-03 | 补：`gWildMonHeaders @0x0839D454` 实测**不是**简单 (mapGroup,mapNum) 索引表，28 字节表项混着地形行为表与外部指针，结构未定死，**不可据此改 ROM** |
