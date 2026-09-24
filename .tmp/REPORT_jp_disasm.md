# GBA 日版红宝石 AXVJ00 静态反汇编验证报告

ROM: `roms/origin/POKEMON_RUBY_AXVJ00.gba`
**实际大小 = 8,388,608 字节（8MB）**，非 32MB。映射 `地址 = 0x08000000 + 文件偏移`。
方法：`scripts/jp_dis.py`（objdump force-thumb + 真实地址）+ 一次性脚本 `.tmp/v2_bounds.py`、`v3_tables.py`、`v6_us_jp.py`。仅静态分析。

---

## 🔴 首要结论：任务书里的地址表有 2 处严重错误

用 `push {...,lr}` 入口 + 跳转表指纹逐一核验后：

| 任务书声称 | 实际 | 判定 |
|---|---|---|
| `0x08003630` DrawGlyphTiles | 是入口，函数体至 `0x080036DA` | ✅ |
| `0x08003674` 跳转表基址 | 是 `0x08003630` 体内 `+0x44` 的池，8 项表 | ✅ |
| `0x080036DC` UpdateTilemap | 是入口，函数体至 `0x08003706` | ✅ |
| `0x08003708` GetCursorTileNum | **不是入口**，是 `0x080036DC` 的体内局部子程序（`+0x2C`） | ⚠️ 地址对，但归属描述错 |
| `0x08003728` | `0x080036DC` 的第二个局部子程序，`svc 11` 包装 | ✅ |
| `0x08003730` GetGlyphTilePointers | 是入口，8 项跳转表 `@0x0800374C` | ✅ |
| `0x08003830` **DrawGlyphTile_Unshadowed** | **❌ 完全是另一个函数**：8×8 字形解压器，写 `dst[i]` | 🔴 **错** |
| `0x080038A0` **DrawGlyphTile_Shadowed** | **❌ 不是像素混合器**：1bpp→4bpp 带阴影展开器，写死到 `0x03000330` | 🔴 **错** |

**这两个函数根本不是「逐像素 RMW 混合写入」。** 详见问题 1。

---

## 问题 1：`0x08003830` / `0x080038A0` 真实身份

### 结论
两者都是**字形解压/色彩展开器，整块覆盖写**，**没有 width 查表，没有跨 tile 分支**。任务书关于「日版也有 `sGlyphMasks` 式 width 查表」的假设**在日版完全不成立**。

### 反汇编证据

**`0x08003830` —— 8×8 像素解压器（整块覆盖写）**

```
8003830: push  {r4,r5,r6,r7,lr}
8003832: mov   r7,r9 / mov r6,r8 / mov r5,r8 / push {r5,r6,r7}   ; 7 参函数
800383a: mov   sl,r0            ; r0 = dst（输出字节指针）
800383c: mov   r9,r1            ; r1 = dst 高半? (见后)
800383e: lsls  r2,r2,#24 / lsrs r2,r2,#24 / mov ip,r2   ; r2 = color0（取低 8 位）
8003844: lsls  r3,r3,#24 / lsrs r7,r3,#24               ; r3 = color1
8003848: movs  r1,#0            ; i = 0
800384a: movs  r0,#128 / mov r8,r0                      ; r8 = 0x80（位掩码）
800384e: movs  r4,#0            ; out = 0
8003850: mov   r2,sl / adds r0,r2,r1                    ; r0 = dst + row
8003854: ldrb  r3,[r0,#0]       ; b = src[row]
8003858: lsls  r5,r1,#2         ; row*4  <- 目的步进 = 4 字节/行
800385c: adds  r0,r3,#0 / mov r1,r8 / ands r0,r1        ; b & 0x80
8003860: cmp   r0,#0 / beq 0x800386c
8003866: lsls  r1,r2,#2 / mov r0,ip                     ; bit=1 -> color0
800386c: lsls  r1,r2,#2 / adds r0,r7                    ; bit=0 -> color1
8003870: lsls  r0,r1             ; << (col*4)           ; 每像素 4bpp
8003872: orrs  r4,r0
8003874: lsls  r0,r3,#25 / lsrs r3,r0,#24               ; b <<= 1
800387e: cmp   r2,#7 / bls 0x800385c                    ; 8 列循环
8003882: mov   r2,r9 / adds r0,r5,r2 / str r4,[r0,#0]    ; ★整字覆盖写 dst[row*4]
800388c: cmp   r1,#7 / bls 0x800384e                    ; 8 行循环
```

要点：
- 循环体是 `str r4,[r0,#0]`（`0x08003886`），**整 32-bit 覆盖**，无任何 `ldr`+`and`+`orr` 的 RMW。
- 每行 4 字节（`lsls r5,r1,#2`，`0x08003858`），8 行 = 32 字节 = 1 个 4bpp tile。
- 色彩映射是 `bit ? color0 : color1`，来自 `r2`/`r3` 入参，**不是查表**。
- 全函数 0 条 `ldr [pc,#n]` 字面量（脚本 `v8_lit.py` 输出：`0x08003830` 池为空）⇒ **无表地址、无跳转表**。

**`0x080038A0` —— 1bpp 字形带阴影展开器（覆盖写到固定缓冲）**

```
80038a0: push {r4,r5,r6,r7,lr}
80038a8: mov  r9,r1
80038aa: ldr  r1,[sp,#28]        ; 第 6 参（栈上）
80038ba: ldr  r1,[pc,#24] -> 0x080038D4 = 0x03000330   ; ★固定目标 IWRAM
80038bc: mov  r8,r1
80038be: movs r1,#240 / mov ip,r1                      ; ip = 0xF0
80038c2: adds r3,r0,#0 / ldrb r0,[r3,#0]
80038c6: mov  r1,ip / ands r1,r0 / cmp r1,#0 / bne 0x80038d8
80038ce: lsls r0,r5,#28 / lsrs r2,r0,#24               ; 高半字节==0 -> color[3]
80038d8: cmp  r1,#240 / bne 0x80038e2
80038dc: lsls r0,r7,#28 / lsrs r2,r0,#24               ; 高半字节==0xF -> color[0]
80038e2: cmp  r1,#224 / bne 0x80038ec
80038e6: lsls r0,r6,#28 / lsrs r2,r0,#24               ; 高半字节==0xE -> color[1]
80038ec: mov  r2,ip / ands r2,r1                       ; 其它 -> 原值
80038f0: ldrb r0,[r3,#0] / movs r1,#15 / ands r1,r0    ; 低半字节
80038fa: orrs r2,r5  /  0x08003902: orrs r2,r7  /  0x0800390a: orrs r2,r6
8003910: mov  r1,r8 / adds r0,r4,r1 / strb r2,[r0,#0]  ; ★逐字节覆盖写缓冲
8003916: adds r3,#1 / adds r4,#1 / cmp r4,#31 / ble 0x80038c4
```

要点：
- 入参（r0=src, r1, r2, r3, r5/6/7=三色）→ 输出到**硬编码 **`0x03000330`（IWRAM 全局 `sGlyphBuffer` 类缓冲），**不是调用者给的 dst**。
- `strb r2,[r0,#0]`（`0x08003914`）逐字节覆盖写，共 32 字节（`cmp r4,#31`）。
- 4 个 `cmp` 分支的值域是 `0x00 / 0xF / 0xE / 其它` —— 典型的 **1bpp 字形三色替换**，与像素位移无关。
- 同样**无 width 查表**、无越界读问题（无下标计算）。

### 「width > 8 会怎样」
**不存在这个问题** —— 这两个函数里根本没有 width 参数，也没有 `[base + width*N]` 形式的下标寻址。任务书担心的「越界读」在日版这两个函数中**不适用**。

### 对本项目影响
- 🔴 **推翻**「日版有 `sGlyphMasks[9][8][3]`、width≤8 限制、需处理 width>8」这一整条假设链。
- 日版红宝石的字形渲染架构与美版**根本不同**：美版是「掩码 + 移位 + RMW 混合」，日版是「预展开到 4bpp 缓冲 + `CpuFastSet` 拷贝」。
- **Wokann 美版 patch 的 `DrawGlyphTile_ShadowedFont` 调用点在日版不存在同名同构函数**，不能直接对照。

---

## 问题 2：`GetCursorTileNum`（`0x08003708`）ABI

### 结论
日版确有 `GetCursorTileNum`，但它**不是独立入口函数**，而是 `0x080036DC`（UpdateTilemap）内部 `+0x2C` 的局部子程序。**返回值 = 指向 tilemap 项的地址（`&tilemap[...]`），不是砖号。** 调用方必须 `strh` 写入。任务书的描述 ✅ 正确。

### 反汇编证据

```
8003708: ldrb r2,[r0,#27]       ; win->+0x1B
800370a: ldrb r1,[r0,#26]       ; win->+0x1A
800370c: adds r2,r2,r1          ; y = win[0x1B] + win[0x1A]
800370e: lsls r2,r2,#24 / lsrs r2,r2,#24
8003712: ldrb r1,[r0,#29]       ; win->+0x1D
8003714: ldrb r3,[r0,#28]       ; win->+0x1C
8003716: adds r1,r1,r3          ; x = win[0x1D] + win[0x1C]
8003718: lsls r1,r1,#24
800371a: ldr  r0,[r0,#0]        ; win->tilemap 基址
800371c: lsrs r1,r1,#19         ; x<<5  (= x * 32)
800371e: adds r1,r1,r2          ; x*32 + y
8003720: lsls r1,r1,#1          ; * 2   (u16 步长)
8003722: ldr  r0,[r0,#16]       ; r0 = *(win->tilemap + 16)  <- tilemap 数据指针
8003724: adds r0,r0,r1          ; ★返回值 = &tilemap[x*32+y]
8003726: bx   lr
```

**注意 `0x0800371C` 的 `lsrs r1,r1,#19`**：把 `x` 左移 5 位（`x*32`），这是 tilemap 行宽 32 项；再 `lsls #1` 得到字节偏移 —— **返回的是内存地址**。

调用点用法（`0x08003C00` 内，脚本扫出 3 处调用之一 `0x08003C12`）：

```
8003c10: adds r0,r5,#0
8003c12: bl   0x8003708        ; r0 = GetCursorTileNum(win)
8003c16: adds r7,r0,#0         ; r7 = &tilemap[...]   ★保存地址
8003c18: adds r0,r5,#0
8003c1a: bl   0x8003728        ; r0 = 第二子程序
...
8003c36: lsls r2,r0,#5         ; row*32
8003c38: adds r0,r2,r1         ; row*32+col
8003c3a: lsls r0,r0,#1
8003c3c: adds r0,r0,r7         ; ★ 地址 + 偏移
8003c3e: strh r4,[r0,#0]       ; ★ 把砖号 r4 写进去
```

**这是决定性证据**：`r7` 被当作**基址**加偏移，然后 `strh` 存入砖号。若 `r7` 是砖号，`strh` 写内存就毫无意义。⇒ **日版返回 `&tilemap[...]`，不是砖号。**

调用点 3 处，与任务书完全一致：`0x080036EC` / `0x08003AC8` / `0x08003C12`。

### 对本项目影响
🔴 **Wokann 的 `DrawGlyphTilesChinese.s` 第 90 行 `bl GetCursorTileNum` 后接 `lsls r0,r0,#5` 的做法（把返回值当砖号再乘 32）在日版会彻底失效** —— 日版返回值已是地址，再乘 32 得到的是垃圾指针。**照抄必崩。**

---

## 问题 3：日版 `DrawGlyphTiles`（`0x08003630`）

### 结论
`r1` **不是字形**，而是**上层 tile 的目标地址指针**（`upperTile`，指向 `tileData + 偏移`）。函数按 `fontNum`（`r0`）8 路分派，**每路都调用 `0x08003830`（非阴影）或 `0x080038A0`（阴影）各两次（上/下半），下半地址 = `r1 + 0x20`**。

### 反汇编证据

**入口 / 参数**
```
8003630: push {r4,r5,r6,r7,lr}
8003636: push {r6,r7}
8003638: sub  sp,#12
800363a: adds r4,r0,#0          ; r4 = r0 = fontNum
800363c: mov  r8,r1             ; ★r8 = r1 = upperTile 指针
800363e: ldr  r0,[sp,#40]       ; 第 6 参
8003640: ldr  r1,[sp,#44]       ; 第 7 参
8003642: lsls r2,#24 / lsrs r5,#24   ; r5 = r2 (低 8 位)
8003646: lsls r3,#24 / lsrs r7,#24   ; r7 = r3 (低 8 位)
8003654: lsls r4,r4,#16 / lsrs r4,r4,#16   ; r4 = (u16)fontNum
```

**跳转表分派（8 项，`@0x08003674`）**
```
8003664: cmp  r5,#6 / bhi 0x80036ce   ; 注意：这里判的是 r5（r2 低8位），非 fontNum
8003668: lsls r0,r5,#2 / ldr r1,[pc,#8] -> 0x08003674
800366c: adds r0,r0,r1 / ldr r0,[r0,#0] / mov pc,r0
```
表内容（脚本 `v3_tables.py`）：
```
[0]=0x08003678  [1]=0x08003694  [2]=0x08003694  [3]=0x08003694
[4]=0x080036B0  [5]=0x080036B0  [6]=0x080036B0  [7]=0x08003694
```

**非阴影分支（`0x08003694`）—— 上/下半各一次**
```
8003694: ldr  r0,[sp,#4]        ; 第 6 参
8003696: mov  r1,r8             ; r1 = upperTile
8003698: adds r2,r7,#0          ; r2 = 色索引
800369a: adds r3,r6,#0          ; r3 = 另一色
800369c: bl   0x8003830         ; ★上半：Blit(src=r0, dst=r1, ...)
80036a0: ldr  r0,[sp,#8]        ; 第 7 参 = lowerTile 源
80036a2: mov  r1,r8
80036a4: adds r1,#32  ; ★★★ 0x20 !!!  下半目标 = upperTile + 0x20
80036a6: adds r2,r7,#0
80036a8: adds r3,r6,#0
80036aa: bl   0x8003830         ; ★下半
```
⇒ **下半 tile 地址 = `tileBase + 0x20`，确认为 32 字节（= 1 个 4bpp tile）**。

**阴影分支（`0x080036B0`）** 同样结构，改调 `0x080038A0`，且把第 6 参压栈（`str r6,[sp,#0]`）作为第 6 个实参：
```
80036b0: ldr  r0,[sp,#4]
80036b2: str  r6,[sp,#0]        ; 第 6 参入栈
80036b6: mov  r1,r8 / adds r2,r7 / mov r3,r9
80036ba: bl   0x80038A0         ; 上半
80036be: ldr  r0,[sp,#8]
80036c0: mov  r1,r8 / adds r1,#32    ; +0x20 下半
80036c4: str  r6,[sp,#0]
80036ca: bl   0x80038A0         ; 下半
```

### `r1` 的来源
`r1` 由**调用者**传入。`InitWindowTileData`（`0x08002A50`）的 `font0/3` 分支（`0x08002A8C`）里：
```
8002a8e: ldr  r0,[r4,#12]       ; win->tileData
8002a90: adds r0,r0,r1          ; + arg1*32
8002a94: adds r5,r0,r1(<<6)     ; + idx*64
...
8002aa4: adds r1,r5,#0          ; ★r1 = 算好的目标指针，传给 0x08003630
8002aa6: bl   0x80003630
```
⇒ `r1` = **`tileData + arg1*32 + idx*64`**，是**目标 VRAM 缓冲指针**，绝不是字形。

### 与双胞胎 `0x080033B4` 的差异
两者**逐指令同构**（长度均 ~0xB0，控制流完全一致），仅两处不同：
1. **跳转表内容**（`v3_tables.py`）：
   - `0x08003630`: `[0]=3678, [1-3]=3694, [4-6]=36B0, [7]=3694`
   - `0x080033B4`: `[0]=33FC, [1-3]=3418, [4-6]=3436, [7]=3418`
   即 **font 7 走「非阴影」还是「阴影」** 的差异（`0x08003630` 把 7 归入非阴影 3694；`0x080033B4` 把 7 归入 3418）。
2. 目标函数不同：`0x080033B4` 的分支调用 `0x08003830`/`0x080038A0`（同）；但 `0x08003630` 的分支调用 `0x08003830`/`0x080038A0`（同）。
   ⇒ **实质差异仅在 font 6/7 的归类与字模源偏移**，二者是「不同字号（Normal/Small）」的一对重载。

### 对本项目影响
- ✅ 确认 `r1` = upperTile 指针（支持任务书假设）。
- ✅ 确认 `+0x20` 下半 tile。
- ⚠️ **传入的不是字形数据，而是已算好的目标地址** ⇒ hook `DrawGlyphTiles` 拿不到字形 ID，拿不到 `win`。Wokann patch 的逻辑在这里**对不上日版**。

---

## 问题 4：`sGlyphMasks` 在日版 ROM 的定位

### 结论
**日版 ROM 里不存在 `sGlyphMasks`（9×8×3 = 216 个 u32）这张表，一个字节都不存在。** 日版也不使用这种掩码机制。

### 证据

**步骤 1：从美版源码提取真表** — `tools/pokeruby/src/text.c:251` `static const u32 sGlyphMasks[9][8][3]`，正则提取得 **216 个常量**，`struct.pack("<216I")` 得字节模式。

**步骤 2：在美版 ROM 验证该模式可定位**（证明模式有效）：
```
US Pokemon Ruby Version 1.1(US).gba : 命中 1 处 -> 0x081E66F4
```
表头实测：
```
+000: FFFFFFFF FFFFFFFF 00000000 FFFFFFFF FFFFFFFF 00000000 FFFFFFFF FFFFFFFF
+048: FFFFFFFF FFFFFFFF 00000000 FFFFFFFF FFFFFFFF 00000000 00000000 FFFFFFFF
+0D0: FFFFFFFF FFFFF000 000000FF FFFFFFFF FFFF0000 00000FFF FFFFFFFF FFF00000
```
与源码逐项吻合（0x081E66F4 + 216*4 = 0x081E6A54 为表尾）。**美版表确认存在。**

**步骤 3：在日版 ROM 搜索同一模式**：
```
前   4 个 u32: JP 命中 1 处
前   5 个 u32: JP 命中 0 处   ← 从第 5 个 u32 起彻底断裂
前 216 个 u32: JP 命中 0 处
```
⇒ **JP 不存在 216-u32 版本。**

**步骤 4：唯一的「相似候选」是伪命中**。`0x082F1FC4` / `0x082F27C4` 两处只匹配前 4 个 u32，实际是**另一种按行 3 项的短表**：
```
0x082F1FC4: 00000000 FFFFFFFF FFFFFFF0 FFFFF000 FF000000 F0000000 00000000 00000000
0x082F1FE4: 00000000 FFFFFFFF FFFFFFFF 00FFFFFF 00000FFF 000000FF 00000000 00000000
```
这是「像素区间掩码」的**退化/局部**形式，仅 6 行后归零，**维度不是 [9][8][3]**，且尺寸远小于 0x360 字节。**无法判定其用途**（无引用点可追），且**不是** `sGlyphMasks`。

### 报告
| 项 | 值 |
|---|---|
| 美版 `sGlyphMasks` | `0x081E66F4`，216×4 = **0x360 字节**，维度 [9][8][3] |
| 日版对应表 | **不存在** |
| 日版近似物 `0x082F1FC4` | 尺寸 <0x60 字节，维度非 [9][8][3]，**用途无法判定** |

### 对本项目影响
🔴 **推翻**「日版有 width 查表，只是地址未知」的假设。日版走的是完全不同的渲染路径（见问题 1/3），**必须按日版自身架构重写**，不能移植美版的掩码机制。

---

## 问题 5：`InitWindowTileData`（`0x08002A50`）三分支

### 结论
跳转表 `@0x08002A74` 与任务书**完全一致**。三个分支的字模大小分别为 **64 字节/字（font 0/3，Normal+阴影）**、**64 字节/字（font 1/2，Small）**、**128 字节/字（font 4/5，双 tile）**。`font 0/3` 的 `dst = tileData + arg1*32 + idx*64` ✅ 确认「步进 64 字节 = 2 tile」。

### 反汇编证据

**跳转表（`0x08002A74`，脚本实测）**
```
8002a60: cmp  r0,#5 / bhi 0x8002ae8
8002a64: lsls r0,r0,#2 / ldr r1,[pc,#8] -> 0x08002A70
8002a6a: ldr  r0,[r0,#0] / mov pc,r0
表: [0]=0x08002A8C [1]=0x08002AAC [2]=0x08002AAC
    [3]=0x08002A8C [4]=0x08002ACC [5]=0x08002ACC
```
⇒ font 0/3 → `0x08002A8C`；font 1/2 → `0x08002AAC`；font 4/5 → `0x08002ACC`。**与任务书逐项吻合。**

**分支 A：font 0/3 → `0x08002A8C`（Normal 字模，步进 64）**
```
8002a8c: lsls r1,r3,#5          ; arg1 * 32
8002a8e: ldr  r0,[r4,#12]       ; win->tileData
8002a90: adds r0,r0,r1          ; tileData + arg1*32
8002a92: lsls r1,r6,#6          ; idx * 64      ★ 64 字节 = 2 tile
8002a94: adds r5,r0,r1          ; ★dst = tileData + arg1*32 + idx*64
8002a96: ldrb r2,[r4,#8]        ; 色
8002a98: ldrb r3,[r4,#5]
8002a9c: str  r0,[sp,#0]        ; 栈传参
8002aa2: adds r0,r6,#0          ; r0 = idx
8002aa4: adds r1,r5,#0          ; ★r1 = dst
8002aa6: bl   0x80003630        ; DrawGlyphTiles
```
源码源地址：无 `ldr [pc]` 加载字模基址 —— **字模源在 `0x08003630` 内部经 `r0`/栈参获得**（`GetGlyphTilePointers` 系列），本分支只传目标。

**分支 B：font 1/2 → `0x08002AAC`（Small 字模）**
```
8002aac: adds r0,r6,r3          ; idx + arg1
8002aae: lsls r0,r0,#5          ; (idx+arg1)*32   ★步进 32 字节
8002ab0: ldr  r1,[r4,#12] / adds r5,r1,r0   ; dst
8002ab4: lsls r0,r6,#3          ; idx * 8
8002ab6: ldr  r1,[pc,#16] -> 0x08002AC8 = 0x081B49AC   ; ★字模源 = 0x081B49AC
8002ab8: adds r0,r0,r1          ; src = 0x081B49AC + idx*8
8002aba: ldrb r2,[r4,#5] / ldrb r3,[r4,#6]
8002ac0: bl   0x8003830         ; ★直接调 8×8 解压器（不是 DrawGlyphTiles）
```
⇒ **步进 8 字节/字 ⇒ 单 4bpp tile 高度 8 行 × 4bpp × 8 列 / 2 = 32 字节？** 实测为 **8 字节源**（`idx*8`），配合 `0x08003830` 的 8×8 解压：这是**每字 8 字节的 1bpp 紧凑字形**。

**分支 C：font 4/5 → `0x08002ACC`（双 tile 字模）**
```
8002acc: adds r0,r6,r3 / lsls r0,r0,#5      ; (idx+arg1)*32
8002ad0: ldr  r1,[r4,#12] / adds r5,r1,r0    ; dst
8002ad4: lsls r0,r6,#5           ; idx * 32
8002ad6: ldr  r1,[pc,#24] -> 0x08002AF0 = 0x081B51AC   ; ★字模源 = 0x081B51AC
8002ad8: adds r0,r0,r1           ; src = 0x081B51AC + idx*32
8002ada: ldrb r2,[r4,#5] / ldrb r3,[r4,#7]
8002ade: ldrb r1,[r4,#6] / str r1,[sp,#0]   ; 第 6 参
8002ae4: bl   0x80038A0          ; ★调 1bpp→4bpp 阴影展开器
```

### 汇总表

| 分支 | font | 字模源地址 | 源步进 | 目标步进 | 调用 |
|---|---|---|---|---|---|
| `0x08002A8C` | 0 / 3 | 由 `0x08003630` 内部解析 | **64 B/字**（`idx*64`） | `tileData + arg1*32 + idx*64` | `DrawGlyphTiles` |
| `0x08002AAC` | 1 / 2 | **`0x081B49AC`** | **8 B/字**（`idx*8`） | `tileData + (idx+arg1)*32` | `0x08003830` |
| `0x08002ACC` | 4 / 5 | **`0x081B51AC`** | **32 B/字**（`idx*32`） | `tileData + (idx+arg1)*32` | `0x080038A0` |

### 对本项目影响
- ✅ 确认 `dst = tileData + arg1*32 + idx*64`，「步进 64 = 2 tile = 上下两半」**成立**（仅 font 0/3）。
- ⚠️ 但 **font 1/2 与 font 4/5 的步进是 32 字节**（单 tile），**不是 64**。任务书把 64 字节的结论推广到全部分支是**错误的**。
- ✅ 三个分支的字模源：`0x081B49AC`（font1/2, 8B/字）、`0x081B51AC`（font4/5, 32B/字）；font 0/3 的源在 `DrawGlyphTiles` 内部经 `GetGlyphTilePointers` 解析。

---

## 总览：对方案可行性的净影响

| # | 任务书假设 | 验证结果 |
|---|---|---|
| 1 | `0x08003830/38A0` 是 RMW 混合 + width 查表 | 🔴 **否**：是整块覆盖式解压/展开器，无 width、无表、无跨 tile |
| 2 | `GetCursorTileNum` 返回 `&tilemap[...]` | ✅ **是**（`0x0800371C-24` 决定性证据） |
| 3 | `DrawGlyphTiles` 的 `r1` 是 upperTile 指针，下半 `+0x20` | ✅ **是** |
| 4 | 日版有 `sGlyphMasks` 类表 | 🔴 **否**：日版无此表（美版 `0x081E66F4`） |
| 5 | `dst=...+arg1*32+idx*64`，步进 64 = 2 tile | ⚠️ **仅 font 0/3 成立**；font1/2、4/5 步进为 32 |

**核心结论：日版红宝石的字形渲染架构与美版根本不同 —— 日版不用掩码 RMW，而是「解压到 4bpp 缓冲 + BIOS `svc 11`(CpuFastSet) 搬运」。Wokann 的美版 patch 无法照抄。**

**唯一可直接复用的事实**：`GetCursorTileNum` 返回地址（非砖号），且日版调用方以 `strh` 写入 —— Wokann 代码中的 `lsls r0,r0,#5` 必须删除并改为直接使用返回地址。
