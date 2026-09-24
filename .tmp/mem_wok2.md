## ✅ 方案 = Wokann（2026-09-12 定案）
字库常驻 ROM、按需把当前字混写进 VRAM ⇒ **无容量限制**。
🔴 我们**早已是** Wokann 结构：`GetGlyph()` 直接从 ROM 取字；charmap 是 Wokann
`PMRSEFRLG_charmap.txt` 的**严格超集且零冲突**（6931 项逐字节相同 + 多 44 项）。
⇒ **容量从来不是瓶颈**（8192 槽）。瓶颈是我们自造的 `v8/v9` 分配器 + 12px 相位层。

### 🔴 日版地址表（逐指令反汇编实证；`symbols/pokeruby_jp.sym` 是错的）
`DrawGlyphTiles` **0x08003630**（跳转表 @0x08003678）｜`GGTP` **0x08003730**（表 @0x08003750）｜
`GetCursorTilemapPointer` **0x08003708**（出 tilemap 项地址；**不是 GGTP**）｜`UpdateTilemap` **0x080036DC**｜
blit 非阴影 `0x08003830`｜blit 阴影 `0x080038A0`。
- ❌ 曾把 `0x08003708` 当 GGTP（差 0x28）。**地址必须逐指令反汇编核，不得按「锚点+偏移」推算。**
- 🔴 **日版 Window 布局 ≠ 美版**（`+0x0F=pal/+0x16=tileDataStart/+0x18=tileDataOff/+0x1A=cursorX/+0x1B=cursorTileX`；
  `+0x0B=fontNum`）⇒ **Wokann 汇编不能照抄**。
- 蹦床区 `0x081B1290..A7` = `svc 0x0C/0x0B/0x12/0x11/0x0F/0x15`（含 CpuFastSet/CpuSet）—— **不要吃**。
- 🛠 反汇编：`arm-none-eabi-objdump -D -b binary -m armv4t -M force-thumb --adjust-vma=0x08000000`。
- 官方链的三个硬约束、`InitWindowTileData` font 分派表、`tm1` 链路 ⇒ **见 `docs/MEMORY_附录_逆向实证.md`**。

