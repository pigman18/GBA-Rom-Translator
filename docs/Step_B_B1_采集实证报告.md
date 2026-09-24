# Step B · B1 采集实证报告（Wokann 落点取证）v2

> 日期：2026-09-20（v2 修订：同日第二轮，修掉 v1 的 3 个误读）
> 目的：写汇编前取三条硬事实 —— 钩内能否取当前字 / 官方落点推进规律 / 钩点完备性。
> 结论：**(a) 钩内拿不到 window，但拿得到 `idx`（字模序号）+ `r1`（官方算好的 VRAM 落点）——
> 对中文显示已足够；(b) 落点严格线性、无相位；(c) 钩点完备（4 处调用点全在 `DrawGlyphTiles` 汇聚）**。
>
> 数据：
> - `.tmp/dgt_b1_v9.log`（**主数据** v9，DGT 命中 791 / 含游戏内场景）
> - `.tmp/dgt_b1_v3_keeplog.log`（v3 备份，DGT 256 / 全在图集装载路径）
> - 反汇编工具：`scripts/jp_dis.py`；BL 扫描：`scripts/scan_bl_sites.py`（**本轮新建**）

---

## 0. v1 → v2 修订摘要（3 个误读）

| # | v1 的说法 | v2 修正 | 根因 |
|---|---|---|---|
| 1 | 跳转表「font3 → `0x08002AAC`」 | **font3 → `0x08002A8C`（= DrawGlyphTiles）** | 池子基址读偏 2 字节 |
| 2 | 「fontNum 读值(3) 与 LR 归属分支(0/4) 矛盾，未定论」 | **不矛盾，已完全解释** | 同 1，修正表后实测吻合 |
| 3 | 「按键注入点 = `0x0800047E`」 | **注入点应为 `0x0800043E`** | `0x0800047E` 改 `r3` 太晚，`newKeys` 早在 `0x08000442` 算完 ⇒ 游戏收不到「刚按下」 |

**★ 修订 3 是本轮最大突破** —— 它是 v7/v8「按键数 365 但 0 命中」的根因。

---

## 1. 本会话破掉的五个工程阻塞（供复用）

| # | 阻塞 | 根因 | 解法 |
|---|---|---|---|
| 1 | mGBA 起不来 | `bash &` / `DETACHED_PROCESS` 起的子进程随父 shell 死 | **脚本内全程持有 `Popen` 引用**，采集与模拟器同生命周期 |
| 2 | 磁盘被写爆 | `config.ini` `logLevel=71` + `logToFile=1`，`mgba.log` 涨到 **5.5 GB** | 改 `logToFile=0 logStdout=0 logLevel=15`；**旧 5.5GB 日志已删**（本轮句柄终于释放，磁盘回收） |
| 3 | 写 `REG_KEYINPUT` 无效 | **`0x04000130` 是只读硬件寄存器**，`M` 包写进去被硬件覆盖 | 改在 `ReadKeys` 内下断点 + `P` 包改寄存器 |
| 4 | 按键注入了但游戏无响应 | **注入点 `0x0800047E` 太晚**：`newKeys`（`+0x2E`）在 `0x08000442` 已算完，改 `r3` 只影响 `heldKeys` | **注入点改 `0x0800043E`，同时写 `r3`(key) 与 `r2`(=0，清 heldKeysRaw)** |
| 5 | BL 调用点扫描扫出 0 处 | ①判据写成 `(hw2>>11)==0b11111` 只匹配 J1=1；②目标地址漏加 `0x08000000` | 见 `scripts/scan_bl_sites.py`（已修，注释写明两坑） |

### 1.1 按键注入（最终方案，已实证）

`ReadKeys = 0x0800042C`（全 ROM `0x04000130` 字面量仅 1 处 ⇒ 唯一读取点）：

```asm
ReadKeys:
 800042c: b500        push {lr}
 800042e: 480e        ldr r0,[pc,#56] → 0x04000130   ; REG_KEYINPUT（0=按下，空闲 0x03FF）
 8000430: 8801        ldrh r1,[r0]
 8000432: 4a0e        ldr r2,[pc,#56] → 0x030016E0   ; ★ gMain
 8000434: 1c10        adds r0,r2,#0
 8000436: 1c03        adds r3,r0,#0
 8000438: 404b        eors r3,r1        ; r3 = 0x03FF ^ keyinput = 按下的键
 800043c: 8d0a        ldrh r2,[r1,#0x28]; r2 = gMain.heldKeysRaw ← ★ 上一帧的值
 800043e: 1c18        adds r0,r3,#0
 8000440: 4390        bics r0,r2        ; r0 = newKeys = r3 & ~heldKeysRaw
 8000442: 8548        strh r0,[r1,#0x2a]; newKeysRaw = r0
 8000444: 85c8        strh r0,[r1,#0x2e]; newKeys
 8000446: 8608        strh r0,[r1,#0x30]; newAndRepeatedKeys
 ...
 800047e: 8513        strh r3,[r2,#0x28]; heldKeysRaw = r3   ← ✗ 旧注入点（太晚）
 8000480: 8593        strh r3,[r2,#0x2c]; heldKeys
```

**★ 注入点 = `0x0800043E`**（`bics` 之前）：
```
P3=<key_le>     ; r3 = 键值
P2=00000000     ; r2 = 0 ⇒ newKeys = r3 & ~0 = r3
```
然后 **摘断点 → `cont` 跑掉这一帧**（否则 `cont` 立刻被同一断点再次命中 ⇒ 游戏没跑，v1 的
`t_inject2` 就死在这）。

**⇒ 单次「刚按下」必须跨 2 帧**：第 1 帧种 `heldKeysRaw`，第 2 帧 `newKeys` 才出现。
注入序列 `[key,key,key,0,0]` 已验证足够。

### 1.2 `gMain` 结构（运行期实测）

```
gMain = 0x030016E0    ← 反汇编立即数 + 运行期 r2 实测（489/489、60/60，三重确证）
  +0x00 (dummy/patched)  +0x04 callback1      +0x08 (pad)   +0x0C callback2
  +0x28 heldKeysRaw      +0x2A newKeysRaw     +0x2C heldKeys   +0x2E newKeys
  +0x30 newAndRepeatedKeys  +0x32 keyRepeatCounter  +0x36 watchedKeysMask
```
实测样本（跑到游戏内后）：
```
+0x04 = 0x0813668D → 0x08079419 → 0x08051619 → 0x080A1595 → 0x0809F6DD → 0x08140F75 → 0x080A1BC9
       （标题）        （标题动）    （存档菜单）   （游戏内 …）
```
**⇒ `gMain+4` 可作为「游戏走到哪」的可靠判据**（比 I/O 寄存器可靠）。

> 🔴 **I/O 寄存器不可靠**：`DISPCNT` 偶发读成 `0x-001`；BG `hofs=25702`/`vofs=60329` 超范围。
> 用 BG scroll 渲染 PNG 全黑 ⇒ **「用 BG 验证画面」的方案作废**，只用 `gMain` + `pc` + `callback`。

---

## 2. 三条判据的实测答案（v2 终版）

### (a) 钩内能否取到「当前正在画的字」→ ⚠️ **拿不到 window，但拿到了更直接的东西**

**`DrawGlyphTiles (0x08003630)` 真实全貌（本轮完整反汇编）：**

```c
void DrawGlyphTiles(u16 idx, u16 tileBase, u8 fontNum, u8 w, u8 a6, u8 a7) {
    // 8003630: push {r4,r5,r6,r7,lr} / mov r7,r9 / mov r6,r8 / push {r6,r7} / sub sp,#12
    r5 = fontNum;              // lsls r2,#24 / lsrs r5,r2,#24    (u8)
    r7 = w;                    // lsls r3,#24 / lsrs r7,r3,#24    (u8)
    r6 = a6;                   // 来自 [sp+0x28]
    r9 = a7;                   // 来自 [sp+0x2C]
    r4 = idx & 0xFFFF;         // lsls r4,#16 / lsrs r4,#16

    GetGlyphTilePointers(fontNum, idx, &sp4, &sp8);   // bl 0x08003730 @ 0x08003660
    if (fontNum > 6) goto ret;
    switch (fontNum) {                                 // 跳转表 @0x08003678（7 项）
      case 0,1,2,6:                                    // → 0x08003694
          DrawGlyphTile_Unshadowed(sp4, tileBase,      w, a6);
          DrawGlyphTile_Unshadowed(sp8, tileBase+0x20, w, a6);
          break;
      case 3,4,5:                                      // → 0x080036B0
          DrawGlyphTile_Shadowed(sp4, tileBase,        w, a6, a7);
          DrawGlyphTile_Shadowed(sp8, tileBase+0x20,  w, a6, a7);
          break;
    }
}
```

**⇒ 结论（关键）：**
1. **钩内没有 window 指针** —— `win[0x10]+win[0x14]` 取不到。
2. **但 `r0 = idx` 就是字模序号（= 字符在字体表里的身份）**，`r1 = tileBase` 是**官方算好的绝对 VRAM 落点**。
3. **一次 `DrawGlyphTiles` 调用 = 一个字的完整上下两半**（`tileBase` 与 `tileBase+0x20`）。

**⇒ 对中文显示，`(idx, r1)` 这对信息已经完备**：
- 落点 `r1` 天然避让 UI（官方自己算的，满足验收判据「任何场景不撞 UI」）
- `idx` 标识「这个位置要画哪个字」⇒ 用 idx 反查中文字模即可

### (b) 官方落点/砖号推进规律 → ✅ **严格线性、无相位**

实测 256 拍（`template@0x081BB544`，`tileData=0x06008000`，`font=3`）：

```
idx : 0x000 0x001 0x002 ... 0x0FF      ← 严格 +1
dst : 0x06008020 0x06008060 ... 0x0600BFE0  ← 严格 +0x40
砖号: 0x001  0x003  ... 0x1FF          ← 严格 +2
```

**推进算式的出处（`InitWindowTileData` font 0/3 分支 `0x08002A8C`，已反汇编）：**
```
8002a8c: 0159   lsls r1, r3, #5     ; r1 = arg1 << 5   （arg1 = 起始砖号）
8002a8e: 68e0   ldr  r0, [r4, #12]   ; r0 = template->tileData
8002a90: 1840   adds r0, r0, r1      ; r0 = tileData + arg1*32
8002a92: 01b1   lsls r1, r6, #6      ; r1 = idx << 6
8002a94: 1845   adds r5, r0, r1      ; ★ dst = tileData + arg1*32 + idx*64
```
- 步进 64 字节 = **2 tile** = 一个字的上下两半（对应 `DrawGlyphTiles` 内两次 `bl DrawGlyphTile_*`，第二次 `+0x20`）。
- 起点 `tileData+0x20` = 跳过 0 号砖（留给窗口框）。
- 终点 `0x0600BFE0` ⇒ 覆盖 cb2 全部 512 砖（= `charBase=2` 容量）。

### (b') 逐字渲染的推进（新发现，`sub_0800338C`）

```c
// 0x0800338C —— 真正的「逐字渲染」包装（tm2 家族）
void sub_0800338C(void *a /*r5*/, u32 src) {
    r0 = src;                    // 字模来源（外部传入）
    r1 = a->[0x20];              // ★ 游标（绝对 VRAM 地址）
    r2 = a->[11]; r3 = a->[12];  // w, h
    [sp+0] = a->[13]; [sp+4] = a->[14];
    DrawGlyphTiles(r0, r1, r2, r3);
    a->[0x20] += 64;             // ★★ 每次严格 +0x40 ——— 与 (b) 的步进完全一致
}
```
> 该函数**无直接 `bl` 调用者**（0 处）⇒ 经**函数指针表**调用（tm2 家族 = `0x0800338C/…`）。
> 这解释了 v1「tm2 路径 0 命中」：它不被 `bl`，而在跳转表里。

### (c) 钩点完备性 → ✅ **完备（唯一汇聚点）**

**全 ROM BL 调用点扫描结果（`scripts/scan_bl_sites.py`，本轮新建并双验证）：**

| 函数 | 调用点数 | 调用点 |
|---|---|---|
| **DrawGlyphTiles** `0x08003630` | **4** | `0x08002AA6` / `0x08002B16` / `0x080033A2` / `0x08003542` |
| InitWindowTileData `0x08002A50` | 1 | `0x08002A14`（在 `MultistepLoadFont` 内） |
| GetCursorTileNum `0x08003708` | 3 | `0x080036EC` / `0x08003AC8` / `0x08003C12` |
| GetGlyphTilePointers `0x08003730` | 2 | `0x080033E4` / `0x08003660` |
| MultistepLoadFont `0x080029E0` | 2 | `0x080685E0`（领航员链）/ `0x08006F01C→0x0806F01C`（菜单链） |
| GetBlankTileNum `0x080041BC` | 3 | `0x08003ABC` / `0x08003C22` / `0x08004196` |
| DrawGlyphTile_Unshadowed `0x08003830` | 10 | （见脚本输出） |
| DrawGlyphTile_Shadowed `0x080038A0` | 12 | （见脚本输出） |

**⇒ 关键：`DrawGlyphTile_Unshadowed` / `Shadowed` 虽有 10+12 处调用，但它们全部**
**①由 `DrawGlyphTiles` 内部调用（2 处/次），②或由 `InitWindowTileData` 的分支直调。**
**只要钩 `DrawGlyphTiles`（4 个调用点全汇聚于此）+ `InitWindowTileData` 的 `0x08002AAC`/`0x08002ACC` 两个直调分支，就覆盖全集。**

**★ 三张跳转表（池子基址 = **池的第一个字**，即 `ldr rX,[pc,#8]` 后 `bx` 落在的地址+0；
实测 `0x08003674` 处第一字 = `0x08003678` ⇒ 表基址 `0x08003674`）：**

| 表 | 基址 | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|---|
| **InitWindowTileData** `0x08002A50` | `0x08002A70` | `2A74`(池外) | `2A8C` | `2AAC` | `2AAC` | `2A8C` | `2ACC` | `2ACC` |
| **DrawGlyphTiles** `0x08003630` | `0x08003674` | **`3678`** | `3694` | `3694` | `3694` | `36B0` | `36B0` | `36B0` |
| **GetGlyphTilePointers** `0x08003730` | `0x0800374C` | `3750`(池外) | `376C` | `377C` | `3794` | `37AC` | `37D0` | `37F0` |

> 🔴 **读表坑（已犯过两次）**：`ldr r1,[pc,#8]` 的池 = **对齐后 `(指令地址+4)+8`**。
> 表里第 0 项在**该地址之前 4 字节**（因为 `mov pc,r0` 那条 2 字节指令 + `movs r0,r0`
> 填充占了 4 字节）。**必须从原始字节确认第一个字的位置，不能靠算。**
> `DrawGlyphTiles` 的池字节流：`46 87 | 00 00 | 78 36 00 08 | 94 36 00 08 | ...`
> ⇒ 有效表项 = `0x08003678 / 0x08003694 / 0x08003694 / 0x08003694 / 0x080036B0 ×3`

**⇒ 实测 `font=3` 与 LR=`0x08002AAA` 的推导链（font 部分待实测确认）：**
```
font3 → InitWindowTileData 表[3] = 0x08002A8C
      → 0x08002A8C 内 bl 0x08003630 @ 0x08002AA6
      → LR = 0x08002AAA          ✅ 与 v3/v9 实测 506/508 次一致
      → GetGlyphTilePointers 表[3] = 0x080037AC（位域拆分分支）
      ⚠️ DrawGlyphTiles 表[3] = 0x08003694（Unshadowed）—— 与 font3「4bpp 阴影字」的
         直觉不符，**待实测**：在 0x08003694/0x080036B0 各下断点看哪个被命中。
```
**v1 的「矛盾」彻底消解 —— 纯粹是池子读偏 2 字节。**

### ★★ (d) 决定性发现：`DrawGlyphTiles` 有双胞胎，**钩它不够**

**全 ROM 特征扫描（`.tmp/scan_glyph_family.py`，特征 = `f0b5 4f46 4646 c0b4 83b0 041c 8846`）**
**只找到 2 个成员，前 32 字节逐字节相同：**

| 函数 | BL 调用点数 | 调用点 |
|---|---|---|
| `0x080033B4` | **1** | `0x08003482` |
| `0x08003630` | **4** | `0x08002AA6` / `0x08002B16` / `0x080033A2` / `0x08003542` |

**两个函数各自的内部跳转表也不同：**

| 函数 | 表基址 | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|---|
| `0x08003630` | `0x08003678` | `3694` | `3694` | `3694` | `36B0` | `36B0` | `36B0` | `3694` |
| `0x080033B4` | `0x080033F8` | `33FC` | `3418` | `3418` | `3418` | `3436` | `3436` | `3436` |

**⇒ 🔴 只钩 `0x08003630` 会漏掉 `0x08003482` 那一条路径（tm2 家族）。**
**总覆盖点 = 5 处。**

### ★★★ 最终方案：改钩 `GetGlyphTilePointers (0x08003730)`

**它是两个双胞胎的【唯一公共前置】**（`DrawGlyphTiles` 在 `0x08003660` 调它，
`0x080033B4` 在 `0x080033E4` 调它，**两处各一份，正好对应两个成员**）
⇒ **钩一处 = 覆盖全部 5 条渲染路径。**

**完整反汇编（已实证）：**
```asm
GetGlyphTilePointers:                 ; ABI: r0=fontNum(u8) r1=idx(u16) r2=&out0 r3=&out1
 8003730: b510        push {r4, lr}
 8003732: 1c14        adds r4, r2, #0            ; r4 = out0 指针
 8003734: 0600        lsls r0, r0, #24
 8003736: 0e00        lsrs r0, r0, #24           ; r0 = fontNum
 8003738: 0409        lsls r1, r1, #16
 800373a: 0c0a        lsrs r2, r1, #16           ; r2 = idx
 800373c: 2806        cmp  r0, #6
 800373e: d86f        bhi  0x8003820             ; fontNum>6 ⇒ 直接返回
 8003740: 0080        lsls r0, r0, #2
 8003742: 4902        ldr  r1, [pc, #8] @0x0800374C → 0x08003750
 8003744: 1840        adds r0, r0, r1
 8003746: 6800        ldr  r0, [r0, #0]
 8003748: 4687        mov  pc, r0               ; 跳转表分派（7 项）
 ...
 8003816: 6020        str  r0, [r4, #0]         ; *out0 = r0
 800381e: 6018        str  r0, [r3, #0]         ; *out1 = r0
 8003820: bc10        pop  {r4}
 8003822: bc01        pop  {r0}                 ; pop 出 lr
 8003824: 4700        bx   r0                   ; ★ 叶函数（push 只有 {r4,lr}）
```

**⇒ 桩设计（12 字节尾跳型，铁律 4 已核）**

```asm
; 桩 @0x08003730，覆盖 0x08003730..0x08003739（5 条指令 / 10 字节）
08003730:  b510        push {r4, lr}       ; ← 重放原体第 1 条
08003732:  4c00        ldr  r4, [pc, #0]   ; pc(对齐)=0x08003734 → 池 @0x08003736
08003734:  4720        bx   r4
08003736:  <tramp|1>   .word               ; 4B
; 剩余 0x0800373A..0x0800373F 由原体保留（不动）
```

**被覆盖的 5 条 = `push {r4,lr}` / `adds r4,r2,#0` / `lsls r0,#24` / `lsrs r0,#24` / `lsls r1,#16`**
⇒ **跳板须重放后 4 条，然后跳回 `0x0800373A`（`lsrs r2,r1,#16`）。**

**栈净额**：桩 `push {r4,lr}` = −8；原体被覆盖部分含同一条 `push {r4,lr}` = −8 ⇒ **净额相等 ✅**

**跳板逻辑（伪码）**：
```
push {r0,r1,r2,r3, lr}           ; 保存入参
r_game = 原体逻辑(r0,r1)          ; 得到 fontNum / idx
if (idx 属于中文字区) {
    *out0 = 中文字模_上半地址
    *out1 = 中文字模_下半地址
    pop  {r0,r1,r2,r3,lr}
    ; 直接跳到函数尾（0x08003820）——或照常跳到 0x0800373A 但让官方逻辑被跳过
    跳 0x08003820                 ; pop {r4} / pop {r0} / bx r0
} else {
    pop  {r0,r1,r2,r3,lr}
    跳 0x0800373A                 ; 走官方逻辑
}
```

**⇒ 相比钩 `DrawGlyphTiles` 的优势：**
1. **覆盖完整**（5 条路径 vs 4 条，且不分双胞胎）
2. **改的是指针，不是像素** ⇒ 无需知道 VRAM 布局、无需关心 `tileBase` 步进
3. **`*out0`/`*out1` 就是字模源** ⇒ 直接替换成中文点阵，官方渲染代码照常跑

---

## 3. 字模来源（GetGlyphTilePointers 分支体，`0x08003750` 表）

```c
// 0x08003730 GetGlyphTilePointers(u8 fontNum, u16 idx, u16 **out0, u16 **out1)
//   r4 = out0 (r2 入参), r2 = idx (r1 入参 >> 16), 返回：*out0 / *out1
font 0 → 0x0800376C:
    *out0 = 0x081B3AAC + idx*16;      // ★ 每字 16 字节 ROM 常量
    *out1 = *out0 + 8;                // ★ 下半 = 上半 + 8
font 1 → 0x0800377C:
    *out0 = 0x081B34A8[idx*4]; <<3 ... // 变址表 + 基址 0x081B49AC
font 2 → 0x08003794: 固定 0x081B504C + idx*8
font 3 → 0x080037AC: 位域拆分
    *out0 = ((idx & 0xF0) << 6 | (idx & 0x0F) << 5) + 0x081B6D2C
    *out1 = *out0 + 0x200
font 4 → 0x080037D0: 0x081B34A8[idx*4] <<5 + 0x081B51AC
font 5 → 0x080037F0: 固定基址 + idx*32
font 6 → 0x08003808
```

**⇒ 印证 MEMORY.md 的铁律：「字体图集不走 LZ77，源是 ROM 裸常量数组」。**
`0x081B34A8`（变址表）、`0x081B3AAC` / `0x081B49AC` / `0x081B51AC` / `0x081B6D2C` 全是常量池 ⇒
**v20 的 LZ77 门控碰不到文字**，两个系统完全隔离。

---

## 4. 采集覆盖情况

| 场景 | 是否覆盖 | 证据 |
|---|---|---|
| 标题画面 | ✅ | cb1 `0x0813634D`/`0x08079419` |
| 继续游戏菜单 | ✅ | cb1 `0x08051619` |
| **游戏内**（地图/菜单） | ✅ | cb1 `0x080A1595`/`0x0809F6DD`/`0x08140F75`/`0x080A1BC9` |
| 图集整装路径（`0x08002AA6`） | ✅ | DGT LR `0x08002AAA` ×506 |
| `MultistepLoadFont` 路径 | ✅ | DGT LR `0x08002A18` ×508 |
| 逐字渲染（`0x080033A2`/`0x08003542`） | ❌ | 需专门触发（对话/背包重绘） |
| `GetCursorTileNum` 3 个调用点 | ⚠️ 计数有（GCTN=929）但未按调用点分流 | 下轮按 LR 分流 |

**下轮若需补采**：把断点按 4 个调用点各自下，按 LR 分流统计；或在 `0x0800338C` 下断点
（该函数是逐字渲染包装）。

---

## 5. 对 Step B 方案的影响 —— 路线已可定

**原 Wokann 方案（美版）前提**：`DrawGlyphTiles+2` 处从 `win[0x10]+win[0x14]` 取当前字。

**日版实测：钩内无 window，但有 `(idx, r1)`。**

### ⇒ **已决定：钩 `GetGlyphTilePointers (0x08003730)`**（理由见 §2(d)）

**原 Wokann 方案（美版）前提**：`DrawGlyphTiles+2` 处从 `win[0x10]+win[0x14]` 取当前字。
**日版实测：钩内无 window，但有 `(idx, 指向字模指针的 out0/out1)`。**

**路线对比（B1 完成后收敛）：**

| 路线 | 做法 | 判定 |
|---|---|---|
| ~~B-1 上移钩点~~ | 钩 `InitWindowTileData` / `MultistepLoadFont` | ❌ **不可行**：`MultistepLoadFont` 是「整字库图集装载」，不是逐字渲染 |
| ~~B-2 钩 `DrawGlyphTiles`~~ | 钩 `0x08003630`，用 `r0`(idx)+`r1`(dst) | ⚠️ **覆盖不全**：漏 `0x080033B4`/`0x08003482` 那条路径；且要自己算 VRAM 落点 |
| ~~B-3 回到 `GetCursorTileNum`~~ | 在逐字路径取 window | ❌ 覆盖更窄（3 个调用点） |
| **★ B-4 钩 `GetGlyphTilePointers`** | 钩 `0x08003730`，**改 `*out0`/`*out1` 指向中文字模** | ✅ **唯一充分且干净** |

**B-4 的三条硬保证：**
1. **覆盖完备** —— 5 条渲染路径（两个双胞胎的 1+4 个调用点）全部经此
2. **改指针不改像素** —— 无需感知 VRAM 布局 / charBase / tileBase 步进
3. **官方渲染代码照常执行** —— 阴影/非阴影分支、宽度、调色全由官方处理，**零重实现**

**B-4 仍需在 B2 定的两件事（属于设计输入，不是 B1 缺口）：**

#### 1. 中文字区占哪段 `idx`？—— 已有实测 + 代数依据

**实测（`.tmp/b1_5_ggtp.py` / `ggtp_b1_5.log`，39 次采样，游戏内对话+菜单）：**

| font | 不同 idx 数 | idx 范围 | `idx>>12` |
|---|---|---|---|
| **3** | 11 | `0x000` .. `0x0F0` | 全 `0x0` |
| **4** | 8 | `0x000` .. `0x0B6` | 全 `0x0` |

样本 idx：`000 003 0A2 0A3 0A4 0A6 0A8 0AA 0AB 0EF 0F0`（font3）／
`000 0A2 0A4 0A6 0A7 0A8 0B5 0B6`（font4）

**★ 代数依据（比样本更硬）—— 重解 font3 的字模索引公式 `0x080037AC`：**
```c
r0 = (idx & 0xFFF0);   // 高 12 位
r0 <<= 6;              // × 64 字节
r1 = (idx & 0x000F);   // 低 4 位
r1 <<= 5;              // × 32 字节
*out0 = (idx & 0xFFF0)*64 + (idx & 0xF)*32 + 0x081B6D2C;
*out1 = *out0 + 0x200;
```
⇒ **`idx` 是 u16，语义是「字符号 << 4 | 字内子砖号」**：
- **`idx >> 4` = 字符号**（0 .. 0xFFF）
- **`idx & 0xF` = 字内子砖**（0 .. 15）

实测 `0x0A2` ⇒ 字符号 `0xA`、子砖 `2`；`0x0EF` ⇒ 字符号 `0xE`、子砖 `0xF`。

**⇒ 中文字区建议（待 B2 最终确认）：**
```
字符号 < 0x800   （idx < 0x8000）→ 官方
字符号 >= 0x800  （idx >= 0x8000）→ 中文
```
让出 32768 个字符号给官方（实际日文表仅数百个），**留出 8 倍以上余量**，且
`idx >= 0x8000` 时 `(idx&0xFFF0)*64` 会溢出 16 位乘法？—— **需在 B2 里用 32 位算术验证**，
必要时把中文字模改成「查表法」（在跳板里不套官方公式，直接查自己的表）。

> ⚠️ **本次采样仅 39 次，样本偏小。** 建议 B2 开工前，用同一脚本跑一遍**全流程**
>（含图鉴/背包/战斗/领奖台），把 `idx` 上界坐实。**但注意：样本只能证明「上界 ≥ 观测值」，
> 不能证明「官方不用」——判死必须靠静态：查每张字体表的实际长度。**

#### 2. 「哪个字该显示中文」由谁决定 —— 走文本解析层（B3 的 `PrintNextChar_hook`）

`GetGlyphTilePointers` **只负责「按 idx 渲染」，不负责「决定画什么字」**。
⇒ **中文注入通道 = B3 的任务**，两者职责清晰分离：

```
[文本解析层 B3]  PrintNextChar → 遇到中文 → 生成 idx >= 0x8000 的伪字序号
                                          → 写进 tilemap / 字符流
[渲染层 B4]      GetGlyphTilePointers(idx >= 0x8000) → 改 *out0/*out1 指向中文字模
```

---

## 6. 本次新增/修改的工具与文件

| 文件 | 用途 | 状态 |
|---|---|---|
| **`.tmp/b1_collect9.py`** | **主采集器 v9**（注入点 `0x0800043E` + 摘断点式 cont） | ✅ 有效，DGT 791 |
| `.tmp/b1_collect3.py` | v3（有效但注入点旧，运气成分） | ⚠️ 备查 |
| `.tmp/dgt_b1_v9.log` | v9 数据（主） | ✅ |
| `.tmp/dgt_b1_v3_keeplog.log` | v3 数据备份 | ✅ |
| **`scripts/scan_bl_sites.py`** | **全 ROM BL 调用点扫描**（含两坑注释） | ✅ 本轮新建 |
| `.tmp/b1_probe_screen.py` | 画面探测（pc 直方图 + gMain + callback） | ✅ |
| `.tmp/t_min2.py` | 断点命中/内存可读性最小诊断 | ✅ |
| `.tmp/t_p3.py` | `P3=` 寄存器写入验证 | ✅ |
| `.tmp/t_inject3.py` | 摘断点式注入尝试（`cont` 语义坑） | ⚠️ 部分 |
| `.tmp/t_inject2.py` | 新注入点尝试（死在 `c` 立刻重命中） | ❌ 已废 |
| `.tmp/b1_collect4~8.py` | savestate / 从开机导航尝试 | ❌ 均废 |
| `tools/mGBA-0.10.5-win32/config.ini` | `logToFile=0` 等（备份 `config.ini.b1bak`） | ✅ |
| `tools/mGBA-0.10.5-win32/mgba.log` | 5.5GB 垃圾日志 | ✅ **已删** |
