# 路线纠偏：字库已在 ROM，问题不在容量 —— 在 VRAM 落点

> 2026-09-11。用户纠偏原话：
> 「尝试接入 ui 分配的目的，是为了能够：1、不撞 UI 2、最大利用 cb 区空间。
>  如果有其他手段，那没必要搞 UI 的，你好像钻牛角尖一定要碰 UI 了，
>  全网搜索一下是否有更好的方式来显示中文，最好是不通过 cb 区，没有容量限制」

---

## 0. 先认错

我把任务读成了「怎么让 UI 也走分配器 / 怎么让 UI 空白」，
于是花了 v12~v20 九个版本围剿「UI 的 tile 不走分配器」。

| 用户真正要的 | 我做的 |
|---|---|
| ① 不撞 UI | ❌ 反过来去改 UI 的分配 |
| ② **最大利用 cb 区空间** | ❌ 在研究怎么让 UI 也来抢 cb |
| ③ 显示中文，**没有容量限制** | ❌ 没碰这个方向 |

**「接入 UI 分配」是手段，不是目的。** 目的只有两条：不撞 + 容量最大化。
有别的路能同时给到，**UI 就完全不用碰**。

---

## 1. 搜索结果 → 关键发现：**我们其实已经在用那套方案了**

搜索命中 `Wokann/Pokemon_GBA_Font_Patch`（宝可梦 3 代汉字字库补丁）。
**该仓库已 vendored 在本项目 `tools/Pokemon_GBA_Font_Patch/`。**

它的做法（读源码实证）：

```asm
; pokeRS/include/hack_R.s（美版红宝石）
PokeRSFontChsNormal     equ 0x09000000     ; 896 KB 字库，放 ROM 尾部
PokeRSFontChsSmall      equ 0x09100000
```

```asm
; pokeRS/src/HookInOrigin/DrawGlyphTiles.s —— 全部改动就这一句
.org DrawGlyphTiles + 2
    bl DrawGlyphTilesChinese
```

```asm
; pokeRS/src/HackFunction/DrawGlyphTilesChinese.s
loadfontglyph:
    lsl r1, r1, 7              ; 字索引 × 128B = 该字在 ROM 字库里的地址
    add r0, r0, r1
    ...
    bl GetCursorTileNum        ; 问引擎当前光标在第几号砖（官方槽位！）
    lsl r0, r0, 5              ; × 32B
    ldr r1, [r6, 0x24]         ; win->tileData
    add r1, r1, r0             ; 目标 VRAM 地址
    bl DrawGlyphTile_ShadowedFont  ; 现场把 ROM 字形混写进那个砖
```

**机制 = 字库常驻 ROM，打印时按需把「当前这个字」从 ROM 混写进 VRAM。**
⇒ VRAM 只承担「屏幕当前显示的字数」，**与字库总量无关** ⇒ **没有容量限制**。
⇒ 目标砖号来自官方 `GetCursorTileNum` ⇒ **天然不撞 UI**。

### 🔴 而我们的项目**已经**是这套结构

`configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm:90-99`：

```asm
FontChsNormal          equ 0x09000000    ; 与 Wokann 完全同址
FontChsSmall           equ 0x09100000
FontChsMiddle          equ 0x09400000
FontChs1BppBig         equ 0x09500000    ; 1bpp 位流库，16 B/字
FontChs1BppSmall       equ 0x09600000    ; 1bpp 位流库，11 B/字
```

ROM 实测（`_translated.gba`）：这些地址**都有内容**（前 64KB 非零字节
20106 / 15462 / 16557 / 60473 / 60623）。

`src/text/text_translater.c:82-105` 的 `GetGlyph`：

```c
if (font_lib == CHS_FONT_LIB_1BPP_BIG) {
    chs_cell_from_1bpp(
        (const uint8_t *)ADDR_FONT_1BPP_BIG
            + ((uint32_t)((uint16_t)code & 0x1FFFu)) * 16u,   /* ← 直接从 ROM 取字 */
        11u, 11u, CHS_1BPP_ROW_OFF_BIG, out128);
    ...
}
```

**⇒ 我们已经在「从 ROM 按需取字」了。** 字库容量 ≈ 8192 字（`code & 0x1FFF`），
足够，**容量根本不是瓶颈**。

---

## 2. 所以真正的瓶颈是什么？

不是字库容量，是 **「算出来的字形写进 VRAM 的哪个砖」**。

看 `PrintNextChar_hook.c:305`（对应 Wokann 的 `DrawGlyphTilesChinese`）：

```c
win_set_u32(win, WIN_TILE_DATA, dst + (uint32_t)adv * 0x40u);
```

我们的 `dst` 来自 **`win[WIN_TILE_DATA]`（= `win+0x24`，官方字段）**，
**和 Wokann 用的是同一个字段**。

差别在这里：

| | Wokann | 我们（v6~v20） |
|---|---|---|
| 字形来源 | ROM 字库 | ROM 字库（**一样**） |
| 目标砖 | `GetCursorTileNum(win,0,0)` = **官方光标** | `win+0x24` 累计推进（**近似**） |
| 额外分层 | **没有** | **有** —— `v8_alloc_tile` / `v8_phase_*` 一整套 |
| 钩点数 | `DrawGlyphTiles` **1 个** | 2 个（PrintNextChar + InitTextPrinter） |
| 有没有 9 个版本的麻烦 | **没有** | 有 |

**⇒ 我们自造的 `v8/v9` 分配器 + 相位层，是问题的来源，不是解法。**
Wokann 用一个官方字段就解决了，我们却在它旁边又搭了一个分配器，
然后为了让 UI 也进这个分配器，折腾了 v12~v20。

---

## 3. 结论：**停止 UI 方向，回到 Wokann 的极简结构**

### 3.1 立即停止

- ❌ 不再推进「UI 接入分配器」
- ❌ 不再推进「screenBase 藏 UI」（`docs/S2_不通过cb_screenBase通道方案.md` **降级为备选**）
- ❌ 不再增加任何分配器逻辑

### 3.2 建议的下一步（待确认）

**Step A — 核对我们与 Wokann 的结构差异（只读，不改码）**

1. 查 `GetCursorTileNum` 日版地址（美版 `0x080069D8`），确认日版存在且语义相同。
2. 对比 `win+0x24` 的推进方式：Wokann 由引擎推，我们手推 + 相位。
   ⇒ 我们的**相位层**（`v8_phase_*`）是不是在补引擎本来就有的行为？
3. 核对日版 `DrawGlyphTiles` 位置（我们已知 `FontFunc[0]@0x08003568`）。

**Step B — 若 Step A 确认 Wokann 结构可用，则做「减法」**

- 试删 `v8_alloc_tile` / 相位层，改走官方 `GetCursorTileNum`
- **一次只动一处，逐场景验**（对话 → 图鉴 → 战斗 → 队伍 → 领航员）
- 验收：跑 v18 干净树 + 单点改动，看是否**不再需要分配器**

**Step C — 若 Step B 成立，则 UI 问题自动消失**

因为不再有分配器，也就没有「谁抢 cb」的问题。
「满池 UI 文字一起空白」这个验收判据**本身可能就不再需要**
（要跟用户确认：这个判据还成立吗，还是改用「中文正常显示 + 不撞 UI」）。

---

## 4. 需要跟用户确认的三件事

1. **验收判据是否改变**：原判据「满池 ⇒ UI 和文字一起空白」是**为了证明同池**。
   如果不再需要同池（UI 本来就不该抢 cb），这个判据还成立吗？
   还是改成「中文正常显示，且任何场景都不撞 UI」？

2. **是否愿意做「减法」**：删掉 v8/v9 分配器 + 相位层是**大动作**，
   但按 Wokann 的样本，本来就不需要这些。是否按 Step A→B→C 走？

3. **字库编码方案**：我们现有的 `charmap.txt`（69473 B）+ meowth 管线，
   是否要与 Wokann 的 `PMRSEFRLG_charmap.txt` 对齐？（影响字库生成与索引）

---

## 5. 参考

- **`tools/Pokemon_GBA_Font_Patch/`**（本项目内，最权威）
  - `pokeRS/include/hack_R.s` / `OriginSymbols_R.s` —— 字库地址 + 美版符号表
  - `pokeRS/src/HackFunction/DrawGlyphTilesChinese.s` —— 中文绘制核心
  - `pokeRS/src/HookInOrigin/DrawGlyphTiles.s` —— **唯一钩点**
  - `pokeRS/graphic/fonts/` —— 896 KB × 2 字库
- 我们自己的对应物：`hook/game_addrs.asm:90-99`（字库地址）、
  `hook/src/text/text_translater.c:55-108`（`GetGlyph`）、
  `hook/src/text/PrintNextChar_hook.c:305`（落点推进）
- GitHub `Wokann/Pokemon_GBA_Font_Patch`（上游）
- `rh-hideout-chinese/pokeemerald-expansion`（绿宝石中文活样本）
- `docs/S2_不通过cb_screenBase通道方案.md`（screenBase 通道，**降级为备选**）
