# Step B · B2 静态验证与渲染推演（非 8px 字体可行性）

> 日期：2026-09-20（**2026-09-20 修订 v2**）
> 目的：回答用户「非 8px 字模在日版到底会渲染成什么样」，并把各方案的最终画面推演出来。
> 手段：**纯反汇编 + 算式推演**（未启动模拟器，未改 ROM）。
> 工具：`scripts/jp_dis.py` / `scripts/b2_dis.py`（逐指令反汇编）

---

## 2026-09-20 修订 v2 —— 官方画布与真实失真机理

### 🔴 真正的失真机理

**根因 = 位流步长不匹配，不是宽度裁切。**

```
中文字库 Big1Bpp：16 字节/字，装 11×11 = 121 像素
  打包算法（scripts/build_font_1bpp.py::pack_1bpp）：
     行间无填充的连续位流 bits[r*11 + c]（注释原文）
  官方读取（CopyGlyph1bppTo4bpp 0x08003830）：
     ldrb r3,[r0,#0] —— 每行取 1 字节 = 8 位
后续：每读一行累积错位 3 位
```

**逐字实证（真实数据，非推演）**：

```
【一】槽 0xF0B    ROM = 00 00 00 00 00 00 05 FF C0 00 ...
  真值 11×11            官方按 8 位/行读出
  ...........          ........
  ...........          ........
  ...........          ........
  ...........          ........
  .........#.          ........
  ###########          ........   ← 整横消失
  ...........          .....#.#
  ...........          ########   ← 横跑到第 7 行，且只剩 8 列
```
真值「横在第 5 行」，官方读出「横在第 7 行」⇒ **错位 2 行、10 列变 8 列**。

### ✅ 官方真实画布（重新定案）

| 项 | 值 | 证据 |
|---|---|---|
| 画布 | **8 宽 × 16 高** = 2 个 tile | `blit(out0, tileBase)` + `blit(out1, tileBase+0x20)` @`0x08003694` |
| 排列 | **纵向上下**（同列下一行） | `UpdateTilemap` 写完首项后 `adds r0,#64`（=32 个 u16 = 一行）再写次项 |
| 步进 | `win[+0x18] += 2`（2 tile）· `win[+0x1B] += 1`（**1 列**） | `FontFunc[0] @0x08003568` |
| 字模切分 | `out1 = out0 + **8**`（上 8 行 / 下 8 行） | `GGTP` font0 分支 `0x08003770: adds r0,#8` |
| 原生印证 | font0 idx=1「あ」= 8宽×16高、1bpp、16B | ROM `0x081B3AAC+16` 逐字节 |

### 三条出路（修订后）

| 方案 | 做法 | 结论 |
|---|---|---|
| **A** 换位流步长 | `pack_1bpp` 改成每行 2 字节（22 B/字） | ❌ 步长对了，但 11 列仍塞不进 8 列画布 |
| **B** 缩到 8×16 | `ink_fixed "8x16+0+0"` + 每行补齐 1 字节 | ✅ **零代码改动**，直接走官方 `GGTP`+`DrawGlyphTiles`；代价是字形要压到 8 列 |
| **C** 自写 blit | 展开 11 列 | ❌ 要改 4 处（blit/步进/tilemap/列计数），等于重写渲染链 |

**⇒ 推荐方案 B。需用户决策：8 列够不够？**

> 画面交付物：`docs/b2_render_sim.html`（各方案最终渲染效果横向对比，全部像素来自
> 真实 BDF + 真实打包算法；内置 pack/unpack 往返自证，Node 实跑 4/4 通过）

---

## 📌 以下为 v1 原文（保留作证据链）

---

## 0. 一句话结论

**日版引擎的字符步进是「恒定 2 个 tile（上下两半）」，与字模实际宽度完全无关。**
⇒ 字模宽 8 → 正常；字模宽 11/16 → **必然右溢出/被裁**；
⇒ **要做非 8 宽，唯一出路是自写 blit（`0x08003830`/`0x080038A0` 是 8px 定宽的）。**

---

## 1. 完整算式链（逐指令反汇编实证）

### 1.1 步进源头：`FontFunc` 处理器

**tm0 路径 —— `FontFunc[0] @ 0x08003568`**（这就是 `game_addrs.asm:69` 记的那个）：

```asm
08003568: b510        push {r4, lr}
0800356a: 1c04        adds r4, r0, #0
0800356c: f7ff ffd8   bl   0x8003520          ; ★ 真正的"画一个字"
08003570: 8b20        ldrh r0, [r4, #24]      ; r0 = win[+0x18]   ← u16
08003572: 3002        adds r0, #2             ; ★★★ 恒 +2
08003574: 8320        strh r0, [r4, #24]      ; win[+0x18] += 2
08003576: 7ee0        ldrb r0, [r4, #27]      ; win[+0x1B]
08003578: 3001        adds r0, #1
0800357a: 76e0        strb r0, [r4, #27]      ; win[+0x1B] += 1
0800357c: bc10        pop  {r4}
0800357e: bc01        pop  {r0}
08003580: 4700        bx   r0
```

**★ `win[+0x18] += 2` 是硬编码常量 —— 日版没有 `GetGlyphWidth`，宽度不可配。**

> 印证 `game_addrs.asm:65-70` 的既有注释：
> 「GetGlyphWidth/GetStringWidth：AXVJ 无原生函数，勿再订址……
>   日版打印步进由 FontFuncTable 各处理器硬编码」

### 1.2 `0x08003520` —— tm0 的实际绘制

```asm
08003520: b530        push {r4, r5, lr}
08003522: b082        sub  sp, #8
08003524: 1c05        adds r5, r0, #0
08003526: 1c08        adds r0, r1, #0
08003528: 682b        ldr  r3, [r5, #0]       ; r3 = win[+0x00] → 模板/text 指针
0800352a: 8aea        ldrh r2, [r5, #22]      ; r2 = win[+0x16]  tileDataStartOffset
0800352c: 8b29        ldrh r1, [r5, #24]      ; r1 = win[+0x18]  tileDataOffset
0800352e: 1852        adds r2, r2, r1         ; r2 = start + offset
08003530: 0152        lsls r2, r2, #5         ; ★ ×32 = tile 字节数
08003532: 68d9        ldr  r1, [r3, #12]      ; r1 = 模板[+0xC] = tileData 基址
08003534: 1889        adds r1, r1, r2         ; ★★★ r1 = tileData + (start+offset)*32
08003536: 7aea        ldrb r2, [r5, #11]      ; win[+0x0B]
08003538: 7b2b        ldrb r3, [r5, #12]      ; win[+0x0C]
0800353a: 7b6c        ldrb r4, [r5, #13]      ; win[+0x0D]
0800353c: 9400        str  r4, [sp, #0]       ; 第 5 参
0800353e: 7bac        ldrb r4, [r5, #14]      ; win[+0x0E]
08003540: 9401        str  r4, [sp, #4]       ; 第 6 参
08003542: f000 f875   bl   0x8003630          ; DrawGlyphTiles
08003546: 8b2a        ldrh r2, [r5, #24]
08003548: 8ae8        ldrh r0, [r5, #22]
0800354a: 1812        adds r2, r2, r0
0800354c: 0412        lsls r2, r2, #16
0800354e: 0c11        lsrs r1, r2, #16        ; r1 = 砖号（u16）
08003550: 2080        movs r0, #128
08003552: 0240        lsls r0, r0, #9         ; r0 = 0x10000
08003554: 1812        adds r2, r2, r0
08003556: 0c12        lsrs r2, r2, #16        ; r2 = 砖号 + 1
08003558: 1c28        adds r0, r5, #0
0800355a: f000 f8bf   bl   0x80036DC          ; UpdateTilemap(win, tile, tile+1)
```

**⇒ `DrawGlyphTiles(r0=idx, r1=tileData+(start+offset)*32, r2/r3/r4=色, sp+0=win[0xB], sp+4=win[0xC])`**

### 1.3 🔴 `DrawGlyphTiles @ 0x08003630` 的**真实 ABI**

```asm
08003630: b5f0        push {r4, r5, r6, r7, lr}
08003632: 464f        mov  r7, r9
08003634: 4646        mov  r6, r8
08003636: b4c0        push {r6, r7}
08003638: b083        sub  sp, #12
0800363a: 1c04        adds r4, r0, #0         ; r4 = idx (u16)
0800363c: 4688        mov  r8, r1             ; r8 = tileBase (VRAM 地址)
0800363e: 980a        ldr  r0, [sp, #40]      ; r0 = 第5参 (win[0xB])
08003640: 990b        ldr  r1, [sp, #44]      ; r1 = 第6参 (win[0xC])
08003642: 0612        lsls r2, r2, #24
08003644: 0e15        lsrs r5, r2, #24        ; r5 = fontNum (r2 低8位)
08003646: 061b        lsls r3, r3, #24
08003648: 0e1f        lsrs r7, r3, #24        ; r7 = r3 低8位
0800364a: 0600        lsls r0, r0, #24
0800364c: 0e06        lsrs r6, r0, #24        ; r6 = 第5参 低8位
0800364e: 0609        lsls r1, r1, #24
08003650: 0e09        lsrs r1, r1, #24
08003652: 4689        mov  r9, r1             ; r9 = 第6参 低8位
08003654: 0424        lsls r4, r4, #16
08003656: 0c24        lsrs r4, r4, #16        ; r4 = idx (干净 u16)
08003658: ab02        add  r3, sp, #8         ; r3 = &out1
0800365a: 1c28        adds r0, r5, #0         ; r0 = fontNum
0800365c: 1c21        adds r1, r4, #0         ; r1 = idx
0800365e: aa01        add  r2, sp, #4         ; r2 = &out0
08003660: f000 f866   bl   0x8003730          ; ★ GetGlyphTilePointers(fontNum, idx, &out0, &out1)
08003664: 2d06        cmp  r5, #6
08003666: d832        bhi.n 0x80036ce
08003668: 00a8        lsls r0, r5, #2
0800366a: 4902        ldr  r1, [pc, #8]       ; 池 @0x08003674
0800366c: 1840        adds r0, r0, r1
0800366e: 6800        ldr  r0, [r0, #0]
08003670: 4687        mov  pc, r0             ; 7 项跳转表
08003672: 0000        movs r0, r0
08003674: 3678        ...
```

**修正后的 ABI：**
```c
DrawGlyphTiles(u16 idx,                 // r0
               u8 *tileBase,            // r1  ← VRAM 目标（不是字形！）
               u8 fontNum,              // r2 低8位
               u8 a3,                   // r3 低8位
               u8 a4,                   // sp+40
               u8 a5)                   // sp+44
```

**分支体（`0x08003694`，font 0/1/2/6）：**
```asm
08003694: 9801        ldr  r0, [sp, #4]       ; r0 = out0（上半字模指针）
08003696: 4641        mov  r1, r8             ; r1 = tileBase
08003698: 1c3a        adds r2, r7, #0         ; r2 = a3
0800369a: 1c33        adds r3, r6, #0         ; r3 = a4
0800369c: f000 f8c8   bl   0x8003830          ; ★ CopyGlyph1bppTo4bpp
080036a0: 9802        ldr  r0, [sp, #8]       ; r0 = out1（下半字模指针）
080036a2: 4641        mov  r1, r8
080036a4: 3120        adds r1, #32            ; ★★★ tileBase + 0x20  ← 下半
080036a6: 1c3a        adds r2, r7, #0
080036a8: 1c33        adds r3, r6, #0
080036aa: f000 f8c1   bl   0x8003830
080036ae: e00e        b.n  0x80036ce
```

**⇒ 🔴 落点恒为 `tileBase` 和 `tileBase + 0x20`，即「一个字符 = 2 个 tile」，与字模宽度无关。**

### 1.4 🔴🔴 blit 是「8 像素定宽 + 整字覆盖」

**`0x08003830` = `CopyGlyph1bppTo4bpp`**（`game_addrs.asm:21` 已正名）：

```asm
0803830: b5f0        push {r4, r5, r6, r7, lr}
080383a: 4682        mov  sl, r0          ; r0 = 1bpp 源（8 字节 = 8×8）
080383c: 4689        mov  r9, r1          ; r1 = VRAM 目标
080383e: 0612        lsls r2, r2, #24
0803840: 0e12        lsrs r2, r2, #24
0803842: 4694        mov  ip, r2          ; ip = fg 色
0803844: 061b        lsls r3, r3, #24
0803846: 0e1f        lsrs r7, r3, #24     ; r7 = bg 色
0803848: 2100        movs r1, #0          ; 行计数
080384a: 2080        movs r0, #128
080384c: 4680        mov  r8, r0          ; r8 = 0x80 位掩码
080384e: 2400        movs r4, #0          ; 累积字
0803850: 4652        mov  r2, sl
0803852: 1850        adds r0, r2, r1      ; 源 + 行
0803854: 7803        ldrb r3, [r0, #0]    ; 取 1 字节 = 8 像素
0803856: 2200        movs r2, #0
0803858: 008d        lsls r5, r1, #2      ; 行 × 4 字节
080385a: 1c4e        adds r6, r1, #1
080385c: 1c18        adds r0, r3, #0
080385e: 4641        mov  r1, r8
0803860: 4008        ands r0, r1
0803862: 2800        cmp  r0, #0
0803864: d002        beq.n 0x800386c
0803866: 0091        lsls r1, r2, #2
0803868: 4660        mov  r0, ip          ; 前景位 → fg 色
080386a: e001        b.n  0x8003870
080386c: 0091        lsls r1, r2, #2
080386e: 1c38        adds r0, r7, #0      ; 背景位 → bg 色
0803870: 4088        lsls r0, r1
0803872: 4304        orrs r4, r0
0803874: 0658        lsls r0, r3, #25
0803876: 0e03        lsrs r3, r0, #24     ; 源 <<= 1
0803878: 1c50        adds r0, r2, #1
080387a: 0600        lsls r0, r0, #24
080387c: 0e02        lsrs r2, r0, #24
080387e: 2a07        cmp  r2, #7          ; ★★★ 内层固定 8 像素
0803880: d9ec        bls.n 0x800385c
0803882: 464a        mov  r2, r9
0803884: 18a8        adds r0, r5, r2
0803886: 6004        str  r4, [r0, #0]    ; ★★★ 整 4 字节覆盖写（无 RMW！）
0803888: 0630        lsls r0, r6, #24
080388a: 0e01        lsrs r1, r0, #24
080388c: 2907        cmp  r1, #7          ; ★★★ 外层固定 8 行
080388e: d9de        bls.n 0x800384e
0803890: bc38        pop  {r3, r4, r5}
...
080389c: 4700        bx   r0
```

**`0x080038A0` = `CopyGlyph2bppTo4bpp`**（阴影版，`game_addrs.asm:22` 已正名）：

```asm
08038a0: b5f0        push {r4, r5, r6, r7, lr}
08038aa: 9907        ldr  r1, [sp, #28]      ; 第5参
08038b8: 2400        movs r4, #0             ; 字节计数
08038ba: 4906        ldr  r1, [pc, #24]      ; r1 = 0x03000330（IWRAM 缓冲）
08038bc: 4688        mov  r8, r1
08038be: 21f0        movs r1, #240
08038c0: 468c        mov  ip, r1             ; ip = 0xF0
08038c2: 1c03        adds r3, r0, #0
08038c4: 7818        ldrb r0, [r3, #0]       ; 取 2bpp 字节（4 像素）
08038c6: 4661        mov  r1, ip
08038c8: 4001        ands r1, r0             ; 高 4 位
08038ce: 0728        lsls r0, r5, #28
...
0803910: 4641        mov  r1, r8
0803912: 1860        adds r0, r4, r1
0803914: 7002        strb r2, [r0, #0]       ; 写 IWRAM 缓冲
0803916: 3301        adds r3, #1             ; 源++
0803918: 3401        adds r4, #1
080391a: 2c1f        cmp  r4, #31            ; ★★★ 固定 32 字节 = 8×8 tile
080391c: ddd2        ble.n 0x80038c4
080391e: 4a05        ldr  r2, [pc, #20]
0803920: 4640        mov  r0, r8
0803922: 4649        mov  r1, r9
0803924: f1ad fcb6   bl   0x81b1294          ; ★ CpuSet/CpuFastSet 写回 VRAM
```

**⇒ 🔴 日版官方 blit 的三个硬约束：**
1. **宽度硬编码 8 像素**（`cmp r2,#7` / `cmp r4,#31`）
2. **整字覆盖写**（`str r4,[r0,#0]`，无 RMW、无掩码）
3. **无 `startPixel` 相位**（不像美版有 `sGlyphMasks[9][8][3]` + `sGlyphShiftAmounts`）

> ⚠️ 已按字节模式在日版 ROM 搜过 `sGlyphMasks`（美版 `0x081E66F4`，0x360 字节），**零命中** ⇒ 日版确实没有这张表。

### 1.5 🔴 日版无相位机制 ⇒ 必须 8 对齐

```asm
0803568 (FontFunc tm0): win[+0x18] += 2   ← 砖号步进恒 +2
08033a2 (tm2 尾):       win[+0x20] += 0x40 ← 字节游标恒 +64
```

**`+2` 砖号 ⇒ 每字恒占 2 砖**。若字模宽不是 8，会造成：
- 宽 > 8：右半像素**溢出到下一个字符的 tile**，被后画的字符覆盖
- 宽 < 8：右侧留空，字距变大

---

## 2. `UpdateTilemap @ 0x080036DC` —— 3 参数（≠ 美版）

```asm
08036dc: b570        push {r4, r5, r6, lr}
08036de: 1c06        adds r6, r0, #0
08036e0: 1c0c        adds r4, r1, #0          ; r4 = upperTileNum
08036e2: 1c15        adds r5, r2, #0          ; r5 = lowerTileNum
08036e4: 0424        lsls r4, r4, #16
08036e6: 0c24        lsrs r4, r4, #16
08036e8: 042d        lsls r5, r5, #16
08036ea: 0c2d        lsrs r5, r5, #16
08036ec: f000 f80c   bl   0x8003708          ; GetCursorTilemapPointer(win)
08036f0: 7bf1        ldrb r1, [r6, #15]       ; win[+0x0F] = paletteNum
08036f2: 0309        lsls r1, r1, #12         ; << 12
08036f4: 430c        orrs r4, r1
08036f6: 8004        strh r4, [r0, #0]        ; tilemap[0]        = upper | pal
08036f8: 3040        adds r0, #64             ; ★ +64 字节 = +32 u16 = 下一行
08036fa: 7bf1        ldrb r1, [r6, #15]
08036fc: 0309        lsls r1, r1, #12
08036fe: 430d        orrs r5, r1
0803700: 8005        strh r5, [r0, #0]        ; tilemap[32]       = lower | pal
0803702: bc70        pop  {r4, r5, r6}
0803706: 4700        bx   r0
```

**⇒ 日版 `UpdateTilemap(win, upper, lower)` 只写 2 个 tilemap 项（上下两行），
**没有美版那个 `if (tilesWidth == 2)` 的右半分支！**

**这是本方案最关键的一条：日版**结构性地**不支持"一个字符占 2 列"。**

---

## 3. 🔴 地址表最终核定（推翻我自己上一条结论）

| 函数 | 地址 | 证据 |
|---|---|---|
| `DrawGlyphTiles` | **`0x08003630`** | `bl 0x8003730` @`0x08003660`；表 @`0x08003674` |
| **`GetGlyphTilePointers`** | **`0x08003730`** | `push {r4,lr}` 叶函数；表 @`0x0800374C` |
| `GetCursorTilemapPointer` | **`0x08003708`** | `ldrb r2,[r0,#27]`…；1 调用点 `0x080036EC` |
| `UpdateTilemap` | **`0x080036DC`** | 3 参数；6 调用点 |
| `CopyGlyph1bppTo4bpp` | **`0x08003830`** | 10 调用点；`game_addrs.asm:21` |
| `CopyGlyph2bppTo4bpp` | **`0x080038A0`** | 6 调用点；`game_addrs.asm:22` |
| `DrawGlyphTiles` 双胞胎 | **`0x080033B4`** | 0 BL 调用点（经函数指针表） |

> ✅ **`MEMORY.md` 原表全对**（`GetGlyphTilePointers = 0x08003730`）。
> ❌ 本会话上一次我误改成 `0x08003708` —— 那是 `GetCursorTilemapPointer`，**已纠正**。
> 🔴 教训：**同名函数在美版是两个**（`GetGlyphTilePointers` 6 参 / `GetCursorTilemapPointer` 1 参），
> 日版也各有一份，**不要因为地址相邻就混为一谈**。

### 3.1 调用点统计（修正扫描器后重扫，572644 条 BL）

| 目标 | 调用点数 | 调用点 |
|---|---|---|
| `GetGlyphTilePointers 0x08003730` | **2** | `0x080033E4`(双胞胎) / `0x08003660`(DrawGlyphTiles) |
| `DrawGlyphTiles 0x08003630` | **4** | `0x08002AA6` / `0x08002B16` / `0x080033A2` / `0x08003542` |
| `CopyGlyph1bppTo4bpp 0x08003830` | **10** | `0x08002AC0` / `0x08002B44` / `0x08002BB4` / `0x08002C00` / `0x08002D70` / `0x08002D8A` / `0x08003420` / `0x08003430` / `0x0800369C` / `0x080036AA` |
| `CopyGlyph2bppTo4bpp 0x080038A0` | **6** | `0x08002AE4` / `0x08002B7E` / `0x08003440` / `0x08003452` / `0x080036BA` / `0x080036CA` |
| `GetCursorTilemapPointer 0x08003708` | **1** | `0x080036EC`（在 UpdateTilemap 内） |
| `UpdateTilemap 0x080036DC` | **6** | `0x080034D6` / `0x0800355A` / `0x08003598` / `0x080035BC` / `0x080035DC` / `0x08003600` |

### 3.2 🔴 覆盖完备性重估

**`GetGlyphTilePointers` 只覆盖 2 条路径，不是 5 条！**

```
路径 A: DrawGlyphTiles (0x08003630) → GetGlyphTilePointers (0x08003730) → CopyGlyph*(8px)
路径 B: 双胞胎 0x080033B4 → GetGlyphTilePointers (0x08003730) → CopyGlyph*(8px)
路径 C: InitWindowTileData 分支 0x08002AAC (font1/2) → 直调 CopyGlyph1bpp
路径 D: InitWindowTileData 分支 0x08002ACC (font4/5) → 直调 CopyGlyph2bpp
路径 E: CopyGlyph* 的另外 12 个调用点（0x08002B*, 0x080034*）—— 未归组
```

**⇒ 钩 `GetGlyphTilePointers` 覆盖 A/B 两条；C/D/E 是"图集装载"路径（非逐字渲染），
不走 `GetGlyphTilePointers`，**所以钩它仍然是对的**（逐字渲染只有 A/B）。
但 C/D/E 的存在说明：**直接在 `CopyGlyph*` 上打桩覆盖最全（16 个调用点）。**

---

## 4. 各方案的渲染推演（模拟图见 `docs/b2_render_sim.html`）

### 方案 1：**保持 8×8 字模**（现状，日版原生）

```
字模 [8px] → blit → tile N     (上半)
字模 [8px] → blit → tile N+1   (下半)
步进: +2 砖
结果: ✅ 完美对齐，无溢出，无空隙
代价: 汉字压成 8×8 ⇒ 笔画糊成一团，不可读
```

### 方案 2：**字模做 16×16（占 2 列 × 2 行）**

```
想画的: [16px 宽，需要 4 个 tile: (0,0)(1,0)(0,1)(1,1)]
实际日版能给的: 只有 tile N 和 N+1（同一列的上下两半）
⇒ 右侧 8px 无处安放 ⇒ 被"下一个字符"覆盖，或被裁掉
结果: ❌ 右半丢失。除非改步进（+4 砖）且改 UpdateTilemap 写右半
```

### 方案 3：**字模做 11×11 / 9×11（非 8 倍数）**

```
blit 只读 8 字节（8 像素）⇒ 第 9~11 像素永远读不到
结果: ❌ 右侧 3 像素直接丢失，字变"缺胳膊"
```

### 方案 4：**自写 blit（替换 `CopyGlyph1bppTo4bpp`/`2bpp`）**

```
自写支持: 任意宽度 + RMW 混合 + 相位
但要同时改: FontFunc 步进(+2 → +N)、UpdateTilemap(写右半)、win[+0x18] 语义
结果: ⚠️ 可行，等于重写日版渲染层。工作量大但完全可控
```

### 方案 5：**字模做 8 宽 × 16 高（上下两字块，用满 2 砖）**

```
字模 8×16 = 2 个 tile 的完整内容，正好对上日版"每字 2 砖"
结果: ✅ 无需改步进、无需改 UpdateTilemap
      高度从 8 变 16 ⇒ 笔画清晰度翻倍（8 宽 × 16 高比 8×8 好得多）
      宽度仍 8 ⇒ 字距正常
⇒ ★ 这是"不改任何官方代码"前提下最优解
```

---

## 5. 结论与建议

| 方案 | 改动量 | 效果 | 判定 |
|---|---|---|---|
| 1. 8×8 原样 | 0 | 糊 | ❌ 不可读 |
| 2. 16×16 | 改步进 + UpdateTilemap | 好 | ⚠️ 要改官方逻辑 |
| 3. 11×11 等 | 需自写 blit | 好 | ❌ 官方 blit 画不出 |
| **5. 8×16** | **0**（只用官方 2 砖） | **良**（8 宽 16 高） | ✅ **最稳** |
| 4. 自写 blit | 大 | 最佳 | ⚠️ 作为后续升级 |

**⇒ 建议先做方案 5（8×16），零改官方代码，立刻可验证；成功后再考虑方案 4 升级到 12×12。**

---

## 6. 参考

- 反汇编工具：`scripts/jp_dis.py`
- BL 扫描（本报告用，已修 I1/I2 还原 bug）：见 §7 附录
- `configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm`（`CopyGlyph1bppTo4bpp`/`2bpp` 正名）
- `tools/pokeruby/src/text.c:2676/2717/4321/4360/4380`（美版对照）
- `tools/Pokemon_GBA_Font_Patch/pokeRS/src/HackFunction/DrawGlyphTilesChinese.s`（Wokann 实现）
- `docs/Step_B_B1_采集实证报告.md`（B1 取证）

---

## 7. 附录：BL 扫描器修正

**🔴 新坑（本次发现）**：Thumb BL(T1) 的 `I1`/`I2` 是**由 J1/J2 与 S 取反还原**的，
不能只拼 `imm10<<12 | imm11<<1`：

```python
imm10 = hw1 & 0x3FF
imm11 = hw2 & 0x7FF
S  = (hw1 >> 10) & 1
J1 = (hw2 >> 13) & 1
J2 = (hw2 >> 11) & 1
I1 = ~(J1 ^ S) & 1        # ★ 取反
I2 = ~(J2 ^ S) & 1        # ★ 取反
imm = (S<<24) | (I1<<23) | (I2<<22) | (imm10<<12) | (imm11<<1)
if imm >= 0x800000: imm -= 0x1000000
```

**自证**：`0x08002AA6` 处 `hw1=f000 hw2=fdc3` → `imm=0xb86` → `tgt=0x08003630` ✅
（此前版本漏了 I1/I2 ⇒ 扫出 0 命中）
