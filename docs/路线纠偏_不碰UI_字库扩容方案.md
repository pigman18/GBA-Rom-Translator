# 路线纠偏：不碰 UI，走「字库扩容 + 按需搬运」

> 2026-09-11。用户纠偏原话：
> 「尝试接入 ui 分配的目的，是为了能够：1、不撞 UI 2、最大利用 cb 区空间。
>  如果有其他手段，那没必要搞 UI 的，你好像钻牛角尖一定要碰 UI 了，
>  全网搜索一下是否有更好的方式来显示中文，最好是不通过 cb 区，没有容量限制」

---

## 0. 我错在哪（先认错）

我把任务读成了「**怎么让 UI 也走分配器 / 怎么让 UI 空白**」，
于是花了 v12~v20 九个版本去围剿「UI 的 tile 不走分配器」这件事。

但用户的真实目标是：

| 用户要的 | 我做的 |
|---|---|
| ① 不撞 UI | ❌ 反过来去改 UI 的分配 |
| ② **最大利用 cb 区空间** | ❌ 在研究怎么让 UI 也来抢 cb |
| ③ 显示中文，**没有容量限制** | ❌ 完全没碰这个方向 |

**「接入 UI 分配」是手段，不是目的。** 目的只有两条：不撞 + 容量最大化。
如果有别的手段能同时给到这两条，**UI 就完全不用碰**。

---

## 1. 搜索找到的答案：`Wokann/Pokemon_GBA_Font_Patch`

（该仓库**已经 vendored 在本项目 `tools/Pokemon_GBA_Font_Patch/`**，一直没细读。）

这是宝可梦 3 代 GBA **汉字字库补丁（增益优化版）**，红蓝宝石已完成，
火红叶绿 / 绿宝石待更新。**它就是「同问题已解决」的活样本。**

### 1.1 核心机制（读源码实证）

**a) 字库放 ROM，不放 VRAM —— 这就是「不通过 cb」**

`pokeRS/include/hack_R.s`：

```asm
PokeRSFontChsNormal     equ 0x09000000     ; 正常字库，917504 B = 896 KB
PokeRSFontChsSmall      equ 0x09100000     ; 小号字库，917504 B = 896 KB
```

- `0x09000000` = **16MB 边界**。美版 ROM 只有 16MB ⇒ 这两块**在 ROM 尾部之外**。
- ⇒ 手法是 **ROM 扩容到 32MB**，字库落在 `0x09000000` / `0x09100000`。
- 每个字库 **896 KB = 14336 个 4bpp 32B 砖** ⇒ 容纳 **7168 个 16×16 汉字**（每字 2 砖）
  或 **14336 个 8×16 字符**。
- **我们的 ROM 已经是 32MB**（`0x2000000`）—— 扩容空间早就有，一直没用上。

**b) 绘制时才搬进 VRAM，且只搬当前要显示的那几个字**

`src/HackFunction/DrawGlyphTilesChinese.s` 的核心（逐行读出的语义）：

```asm
getgylphid:
    lsl r1, r1, 8              ; id << 8
    add r1, r1, r0             ; + 低字节（第二字节）
    ...
    ldr r0, =PokeRSFontChsSmall   ; 选字库（Small / Normal）
loadfontglyph:
    lsl r1, r1, 7              ; × 128 = 2 砖 × 64B
    add r0, r0, r1             ; 算出该字在**字库里的 ROM 地址**
    ...
    bl GetCursorTileNum        ; 问引擎「当前光标在第几号砖」
    lsl r0, r0, 5              ; × 32B
    ldr r1, [r6, 0x24]         ; win->tileData
    add r1, r1, r0             ; 目标 VRAM 地址
    bl DrawGlyphTile_ShadowedFont  ; 把 ROM 里的字形**现场混写**进那个砖
```

**关键点：**
1. 字库常驻 **ROM**，VRAM 里**没有**字库（省掉 896 KB × 2 的 VRAM 占用）。
2. 每个字的字形是**按需**从 ROM 地址算出来的，只在该字要显示时写进 VRAM。
3. **VRAM 用量 = 屏幕上同时显示的字数**，与字库总量**无关**
   ⇒ **这就是「没有容量限制」**。
4. 目标砖号来自 `GetCursorTileNum` = **官方自己的光标，不是我们的分配器**
   ⇒ 天然「不撞 UI」（用的是官方认可的槽位）。

**c) 钩点极小：一句话**

`src/HookInOrigin/DrawGlyphTiles.s`：

```asm
.org DrawGlyphTiles + 2       ; 0x08006876
    bl DrawGlyphTilesChinese
```

**整个中文支持只改了 DrawGlyphTiles 一处**（外加 GetGlyphWidth /
GetStringWidth 处理宽度）。**没有动分配器、没有动 charblock、没有动 UI。**

**d) 配套的宽度函数**

- `GetGlyphWidthChinese.s` —— 让引擎知道汉字占多宽
- `GetStringWidthChinese.s` —— 让居中/右对齐算得对

（README 明说「增添 GetStringWidth 函数对汉字的兼容」+「调整部分场景汉字显示不完全」。）

---

## 2. 这套方案如何同时满足用户的两条目的

| 用户目的 | 本方案如何满足 |
|---|---|
| **① 不撞 UI** | 目标砖号来自官方 `GetCursorTileNum`，与 UI 用的是**同一套官方槽位语义**；不需要新开池子，不需要抢 cb |
| **② 最大利用 cb 区空间** | VRAM 里**不常驻字库** ⇒ 那 896 KB × 2 的常驻占用**还给 cb 区**；VRAM 只承担「屏幕当前字数」 |
| **③ 没有容量限制** | 字库在 ROM，容量 = ROM 大小。**32MB ROM ⇒ 字库可任意扩**，上限与 VRAM 无关 |

**⇒ UI 完全不用碰。这正是用户说的「如果有其他手段，那没必要搞 UI 的」。**

---

## 3. 我们当前方案 vs Wokann 方案

| | 我们（v6~v20） | Wokann |
|---|---|---|
| 字库存放 | VRAM 图集（512 砖常驻） | **ROM**（`0x09000000` 起，896 KB × 2） |
| VRAM 占用 | 固定 512 砖 | **只占屏幕当前字数** |
| 容量上限 | **512 汉字**（VRAM 硬上限） | **7168 汉字 / 字库；ROM 允许还可再扩** |
| 撞 UI 风险 | 高（抢 cb 号） | **低**（用官方光标槽位） |
| 改动面 | 分配器 + 8 个钩点 + 9 个版本反复 | **DrawGlyphTiles 一处** |
| 为什么我们没这么做 | —— | **一直没读 `tools/` 里那个现成仓库** |

🔴 **`tools/Pokemon_GBA_Font_Patch/` 从项目早期就在仓库里**（`readme.md` 的
credit 甚至就是 armips + pret），我们的 v6 却从零造了一套 VRAM 图集方案。
**这是一次典型的「没读现成资料就动手」。**

---

## 4. 日版适配要解决的三件事

Wokann 的是**美版**（`pokeRS` = 红蓝宝石美版）。我们要适配**日版 AXVJ**：

1. **地址映射**：`DrawGlyphTiles` / `GetGlyphWidth` / `GetStringWidth`
   在日版的位置要重新定位（`hack_R.s` 里的 `OriginSymbols_R.s` 有美版地址可对照）。
2. **字库生成**：我们的 `charmap.txt` 是 69473 B，汉字的编码方案要核对
   （Wokann 用 `PMRSEFRLG_charmap.txt`）。
3. **窗口结构偏移**：`win->fontNum` 在偏移 `+1`、`win->language` 在 `+2`、
   `win->textMode` 在 `+0`、`win->*text` 在 `+0x20`……
   要与日版 `TextPrinter` / `Window` 结构核对。

**风险**：我们是日版，结构与美版可能有差异。但**机制本身与版本无关**。

---

## 5. 建议的下一步（待用户确认）

**不是**继续搞 UI 分配。而是：

1. **读透 `tools/Pokemon_GBA_Font_Patch/pokeRS/`**（尤其 `OriginSymbols_R.s` 的地址表），
   把「美版地址 → 日版地址」映射出来。
2. **定位日版 `DrawGlyphTiles`**（我们在 v6 时代查过 `print_glyph` / `PrintNextChar`，
   有基础）。核对 `Window` 结构偏移是否与美版一致。
3. **决定字库编码方案**：沿用现有 `charmap.txt` 还是对齐 Wokann 的。
4. 只在确有必要时才动分配器。**默认不碰 UI、不碰 cb。**

---

## 6. 参考

- **`tools/Pokemon_GBA_Font_Patch/`**（本项目内，最权威）
  - `pokeRS/include/hack_R.s` —— 字库地址定义
  - `pokeRS/src/HackFunction/DrawGlyphTilesChinese.s` —— 中文绘制核心
  - `pokeRS/src/HookInOrigin/DrawGlyphTiles.s` —— 唯一钩点
  - `pokeRS/graphic/fonts/` —— 896 KB × 2 字库
- GitHub `Wokann/Pokemon_GBA_Font_Patch`（上游）
- `rh-hideout-chinese/pokeemerald-expansion`（绿宝石中文，另一活样本）
- pret wiki **How Menus Work** Part 2（VRAM 预算规则，见
  `docs/S2_不通过cb_screenBase通道方案.md`）
