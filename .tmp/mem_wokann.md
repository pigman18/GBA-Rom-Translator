## ✅ 方案 = Wokann（2026-09-12 定案）
字库常驻 ROM、按需把当前字混写进 VRAM ⇒ 无容量限制。
🔴 我们**早已是** Wokann 结构：`GetGlyph()` 直接从 ROM 取字；charmap 是 Wokann
`PMRSEFRLG_charmap.txt` 的**严格超集且零冲突**（6931 项逐字节相同 + 多 44 项）。
⇒ **容量从来不是瓶颈**（8192 槽）。瓶颈是我们自造的 `v8/v9` 分配器 + 12px 相位层。

### 🔴 日版地址表（逐指令反汇编实证；`symbols/pokeruby_jp.sym` 是错的）
`DrawGlyphTiles` **0x08003630**（跳转表 @0x08003678）｜`GGTP` **0x08003730**（表 @0x08003750）｜
`GetCursorTilemapPointer` **0x08003708**（5 行小函数，出 tilemap 项地址；**不是 GGTP**）｜
`UpdateTilemap` **0x080036DC**｜blit 非阴影 `0x08003830`｜blit 阴影 `0x080038A0`。
- ❌ 曾把 `0x08003708` 当 GGTP 入口（差 0x28）。**地址必须逐指令反汇编核，不得按「锚点+偏移」推算。**
- 🔴 **日版 Window 布局 ≠ 美版**（`+0x0F=pal/+0x16=tileDataStart/+0x18=tileDataOff/+0x1A=cursorX/+0x1B=cursorTileX`；
  `+0x0B=fontNum/+0x0C/+0x0D/+0x0E` = `DrawGlyphTiles` 的 a3/a4/a5）⇒ **Wokann 汇编不能照抄**。
- 蹦床区 `0x081B1290..A7` = `svc 0x0C/0x0B/0x12/0x11/0x0F/0x15`（含 CpuFastSet/CpuSet）—— **不要吃**。
- 🛠 反汇编：`arm-none-eabi-objdump -D -b binary -m armv4t -M force-thumb --adjust-vma=0x08000000`；
  `scripts/jp_dis.py` 的 start 参数被忽略（有 bug，慎用）。

### 🔴🔴 `InitWindowTileData 0x08002A50` = font 分派器（表 @0x08002A74）
| font | 分支体 | 怎么画 | 字模源 |
|---|---|---|---|
| 1 / 4 | 0x08002A8C | `bl DrawGlyphTiles` | 经 GGTP |
| **2 / 3** | 0x08002AAC | 直调 `bl 0x08003830` | 硬编码 `0x081B49AC + idx*8` |
| **5 / 6** | 0x08002ACC | 直调 `bl 0x080038A0` | 硬编码 `0x081B51AC + idx*32` |
⇒ font 2/3/5/6 **不经 GGTP**。`DrawGlyphTiles` 表：`[1..3]=0x08003694`(4参)/`[4..6]=0x080036B0`(5参)。

### 🔴 官方链的三个硬约束（= 方案 4 的来源，别再回头试「借道官方」）
1. **官方字模画布 = 8 宽 × 16 高（纵向 2 tile）**：`blit(out0,tileBase)` + `blit(out1,tileBase+0x20)`；
   `UpdateTilemap` 首项后 `adds r0,#64`（=一行）再写次项；`FontFunc[0]`：`win[+0x18]+=2` + `win[+0x1B]+=1`。
   🔴 `GGTP` font0 分支 `0x08003770: adds r0,#8` ⇒ **`out1 = out0 + 8`**（上/下 8 行）；
   `+0x20` 是 **blit 的 VRAM 落点**偏移，曾被误当成字模偏移。原生印证：font0 idx=1「あ」= 8×16、1bpp、16 B/字。
2. **`CopyGlyph1bppTo4bpp 0x08003830` 每行取 1 字节（8 位）**：`cmp r1,#7` 8 行 / `cmp r2,#7` 8 像素 /
   `str r4,[r0,#0]` 整 u32 覆盖写。而中文 `Big1Bpp` 打的是**行间无填充连续位流**（`bits[r*11+c]`）
   ⇒ **每行累积错位 3 位 ⇒ 齐整散架**。这才是「失真」的真机理，**不是宽度裁切**。
   （`CopyGlyph2bppTo4bpp 0x080038A0`：`cmp r4,#31` = 固定 32 B = 1 个 8×8 tile，经 IWRAM `0x03000330`。）
3. 🔴 **日版 `UpdateTilemap` 只写 2 项**，无美版 `if(tilesWidth==2)` 写右列分支 ⇒ 结构性不支持「一字占 2 列」。
   **这才是「必须 8 宽」的真正来源**（不是 blit 的 `cmp #7`）。日版亦无相位、无掩码表（美版 `sGlyphMasks` 搜不到）。

### tm1 链路
`FontFuncTable @0x081BB3AC`（4 项）= tm0 `0x08003569`/tm1 `0x0800360D`/tm2 `0x0800338D`/tm3 `0x08003495`。
🔴 `FontSubTable @0x081BB3BC`（7 项）是 tm1 的**逐字落砖函数表**（不是字体表）。
tm1 处理器：`r2 = FontSubTable[win[0x0B]]; sub_081B12DC(win,r2); win[0x1B] += 1;`
**四个子处理器全部只调 `bl UpdateTilemap`，自身不碰 VRAM、不推进游标。**
⇒ 🎯 **官方只给「格子位置」，不给「tile 号」**。
