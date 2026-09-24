# Step A 只读核对：日版地址与结构映射

> 2026-09-11。按用户三条指令执行：
> 1. 验收判据改成「中文正常显示 + 任何场景不撞 UI」
> 2. 按 Wokann 走
> 3. 字库编码对齐
>
> 本文 = **Step A（只读核对，未改任何代码）** 的结论。

---

## 1. 关键地址映射表（日版 AXVJ ⇄ 美版 pokeruby）

| 函数 | 美版地址 | **日版地址** | 状态 |
|---|---|---|---|
| `PrintNextChar` / `ProcessCurrentChar` | `0x08002FE0` | `0x080032F8` | ✅ 已知锚点 |
| `DrawGlyphTiles` | `0x08006874` | **`0x08003630`** | ✅ **本次实证** |
| `GetCursorTileNum` | `0x080069D8` | **`0x08003708`** | ✅ **本次实证** |
| `GetGlyphTilePointers` | — | `0x08003730` | ✅ 已知 |
| `DrawGlyphTile_UnshadowedFont` | `0x080050AC` | **`0x08003830`** | ✅ **本次实证** |
| `DrawGlyphTile_ShadowedFont` | `0x08005680` | **`0x080038A0`** | ✅ **本次实证** |
| `UpdateTilemap` | `0x08006954` | `0x080036DC` | ✅ 已知（**签名不同**，见 §3） |
| `GetGlyphWidth` | `0x080048E8` | **不存在** | ⛔ 已判死（2026-08-22） |
| `GetStringWidth` | `0x08004BCC` | **不存在** | ⛔ 已判死 |

⚠ **`pokeruby_jp.sym` 里的 `DrawGlyphTiles=0x08005178` / `GetCursorTileNum=0x08003760`
是错的**（该文件自己标了 `UNVERIFIED`）。本次反汇编核对后修正为
`0x08003630` / `0x08003708`。**旧的 UNVERIFIED 地址不要再用。**

---

## 2. 日版 `DrawGlyphTiles @0x08003630` 结构还原（实证）

```
08003630: push {r4,r5,r6,r7,lr} ; mov r7,r9 ; mov r6,r8 ; push {r6,r7} ; sub sp,#12
0800363A: r4 = r0                     ; win
0800363C: r8 = r1                     ; glyph
0800363E: r0 = [sp,#40]               ; 第5参（栈传）
08003640: r1 = [sp,#44]               ; 第6参（栈传）
08003642-52: r5/r7/r6/r9 = 各字节参（fontNum 等）
08003654: r4 = win & 0xFFFF
08003658-60: bl 0x08003730            ; GetGlyphTilePointers(fontNum, glyph, &upper, &lower)
08003664: cmp r5,#6 ; bhi 0x080036CE  ; fontNum > 6 ⇒ 直接返回
08003668-70: 按 fontNum 跳转表分派
             表 @0x08003678 = [3694, 3694, 3694, 36B0, 36B0, 36B0, 3694]
             ⇒ fontNum 0/1/2/6 → 0x08003694（Unshadowed）
             ⇒ fontNum 3/4/5   → 0x080036B0（Shadowed）
08003694: ldr r0,[sp,#4] ; ... ; bl 0x08003830      ; 上半砖
080036A0: ldr r0,[sp,#8] ; adds r1,#32 ; bl 0x08003830  ; 下半砖（upper+32B）
080036B0: ldr r0,[sp,#4] ; ... ; bl 0x080038A0      ; Shadowed 版
080036BE: ldr r0,[sp,#8] ; adds r1,#32 ; bl 0x080038A0
```

**与 pokeruby 源（Wokann 注释里贴的原函数）逐条对应：**
`GetGlyphTilePointers` → `switch(fontNum)` → 两次 `DrawGlyphTile_*`（第二次 `src = lowerTile`）。
⇒ **结构一致，可以放心在这点挂钩。**

### 2.1 `GetCursorTileNum @0x08003708` 语义（实证）

```
08003708: ldrb r2,[r0,#27]   ; win+0x1B cursorTileX
0800370A: ldrb r1,[r0,#26]   ; win+0x1A left
0800370C: adds r2,r2,r1      ; left + cursorTileX
0800370E-10: 截 8 位
08003712: ldrb r1,[r0,#29]   ; win+0x1D cursorTileY
08003714: ldrb r3,[r0,#28]   ; win+0x1C top
08003716: adds r1,r1,r3      ; top + cursorTileY
0800371A: ldr r0,[r0,#0]     ; win+0x00 = template ptr
0800371C: (top+cursorTileY) << 5   ; *32
0800371E: + (left+cursorTileX)
08003720: << 1                     ; *2（半字）
08003722: ldr r0,[r0,#16]    ; tpl+0x10 = tilemap 基址
08003724: adds r0,r0,r1      ; => tilemap 项地址
08003726: bx lr
```

⇒ 返回 **tilemap 里当前光标的项地址**（半字指针）。
**注意：它返回 tilemap 地址，不是 tile 号** —— Wokann 用它做 `UpdateTilemap` 的目标。

---

## 3. 🔴 重要差异：日版 Window 结构与美版**不同**

**Wokann 读的美版 `win` 布局：**

| 偏移 | 字段 |
|---|---|
| `+0x00` | template ptr |
| `+0x01` | fontNum |
| `+0x02` | language |
| `+0x10` | cursorX（相对 *text 基址）|
| `+0x12` | left |
| `+0x1E` | textIndex |
| `+0x20` | ***text** |
| `+0x24` | **tileData** |

**我们的日版布局（`game.h`，多轮实证）：**

| 偏移 | 字段 |
|---|---|
| `+0x00` | template ptr |
| `+0x10` | text ptr |
| `+0x14` | textIndex |
| `+0x16` | tileBase |
| `+0x18` | tileOffset |
| `+0x1A` | cursorX |
| `+0x1B` | cursorTileX |
| `+0x1C` | cursorY |
| `+0x1D` | cursorTileY |
| `+0x20` | **tileData** |

**⇒ 完全对不上。Wokann 的汇编体不能照抄，必须按日版字段重写。**

`DrawGlyphTiles` 里日版**不读** `win->fontNum` / `win->language`
（美版读），fontNum 是从**栈上传参**拿的（5 参函数）。

---

## 4. `DrawGlyphTiles` 的调用点（全盘 4 处）

```
0x08002AA6  在 0x08002A50 体内  → InitWindowTileData 分区器
0x08002B16  在 0x08002A50 体内  → InitWindowTileData 分区器
0x080033A2  在 0x0800338C 体内  → FontFunc[tm2] 处理器
0x08003542  在 0x08003568 附近  → FontFunc[tm0] 处理器
```

⇒ 全是「字形落砖」路径。**钩 `0x08003630` 一处即可覆盖全部字体落砖。**

---

## 5. 结论与 Step B 的具体方案

### 5.1 可以确认的

1. **日版 `DrawGlyphTiles = 0x08003630`**，结构与美版一致，**是可用的单钩点**。
2. **日版字体落砖路径收敛在这一个函数**（4 个调用点全在此）。
3. 日版 `Window` 结构**比美版紧凑**，字段偏移必须按日版重写。
4. **日版没有 `GetGlyphWidth` / `GetStringWidth`** ⇒ 宽度由我们自己管（现在已如此）。

### 5.2 Step B 的做法（去掉分配器，改走官方光标）

**核心思路**：不再用 `v8_alloc_tile` 给字找砖；改用
**「官方给的当前光标砖 + 顺序推进」**，字形从 ROM 按需混写。

具体：
1. 在 `0x08003630` 挂钩（`bl DrawGlyphTilesChinese`，与 Wokann 同型）。
2. 在钩内：
   - 判定是否中文（走我们现有的 F9 协议：lead/trail 合法性）；
   - 从 ROM 字库（`0x09500000/09400000/09600000`，已就位）+ `code & 0x1FFF` 取字形；
   - **目标砖 = 官方 `win->tileData + 32 * 官方当前砖号`**，不再自己发号；
   - 落砖后**交还给原函数**或自行推进 `win+0x1B cursorTileX`。
3. **删除** `v8_alloc_tile` / `v8_ui_alloc` / `v8_phase_*` / ours 段表 / 活引用位图。

### 5.3 仍需在 Step B 前确认的一点

日版 `DrawGlyphTiles` 是**被 FontFunc 处理器调用**的，
我们要在钩内**取代**它的落砖行为 —— 需要确定：
- 我们是**完全接管**（不返回原函数），还是**挂钩后放行**（补画中文再让原函数跑）？
- `win->tileData + 32 * 官方砖号` 这个砖，日版引擎是**怎么推**的？
  （我们已知：`tm1 writer 只推 win[0x1B]`，不推像素相位 —— 这正是我们当年加相位层的原因）

**⇒ 这一步需要先做一次 gdb 采集（L3）确认「官方砖号推进的真实行为」，
再决定是「沿用官方推进 + 自己补相位」还是「全接管」。**

---

## 6. ⚠ 与现有 v6 实现的冲突点（必须正视）

我们现在的 `PrintNextChar_hook.c` 已经在做「取字 → 混写 → 落砖」，
**钩点是 `PrintNextChar`（`0x080032F8`），不是 `DrawGlyphTiles`**。

两条路的区别：

| | 钩 PrintNextChar（现在） | 钩 DrawGlyphTiles（Wokann） |
|---|---|---|
| 层级 | 字符级（早） | 字形落砖级（晚） |
| 目标砖来源 | 自己推 (`win+0x20`) | 官方 `GetCursorTileNum` |
| 是否需分配器 | **是**（v8） | **否** |
| 相位处理 | 自己扛 | 官方已算好 `startPixel` |

⇒ **Step B 本质上 = 把钩点从 `PrintNextChar` 下移到 `DrawGlyphTiles`。**
这是**架构级改动**，不是小修。但方向是**去掉代码**。

---

## 7. 参考

- `tools/Pokemon_GBA_Font_Patch/pokeRS/`（Wokann 美版源）
  - `include/hack_R.s` / `OriginSymbols_R.s`
  - `src/HackFunction/DrawGlyphTilesChinese.s`
  - `src/HookInOrigin/DrawGlyphTiles.s`
- 本项目 `hook/game_addrs.asm`（地址）、`hook/include/game.h`（结构）
- `scripts/jp_dis.py`（本次核对用的反汇编工具）
- `docs/路线纠偏_字库已在ROM_问题在VRAM落点.md`（上一轮结论）
