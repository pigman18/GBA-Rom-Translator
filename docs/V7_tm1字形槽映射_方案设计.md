# V7 方案：tm1 字形槽映射（省掉 v6_alloc_tile，日文放回官方）

> 用户拍板方向（2026-09-03）：
> 「在 InitWindowTileData 加 hook，把 v6_alloc_tile 省掉，纯日文通道也不用实现、
> 直接放回官方即可。之前是为了分配 tile 才把日文纳入同通道，实际并不需要。」

---

## 0. 最终定论（2026-09-03 讨论收敛，V7 定稿）

**关键认知：`tile 号来源` 与 `12px 相位` 是两个正交的问题，不该绑在一起。**

| 决策 | 结论 | 依据 |
|---|---|---|
| tile 号来源 | 删 `v6_alloc_tile`，改「字形槽映射」确定性 | 用户拍板 |
| 落址形态 | **方式 A：真复用 tm1 atlas 槽**（`base+2*glyph` 零像素引用） | 用户拍板 |
| 日文通道 | 删 `draw_jp_glyph`/`jp_glyph_to_g128`，放回官方 tm1 | 用户拍板 |
| **按字号分落址** | 16px→方式A(预渲染进 atlas)；12px→原地 blend+相位；8px→1 槽 | 用户拍板（推荐项） |
| 12px 相位 | **保留**（ChsPhase + extract_cols + 两段式 blend） | 12px 无法走零像素引用 |
| **按坐标分区定字号** | **保留**（`zones[]` 按 curX 分区定字号） | 用户新增需求 |
| **分区定字号 = 落址开关 + 兜底** | font_px 同时决定落址方式与槽容量调节 | 用户新增需求 |

**最终形态**：删 `v6_alloc_tile()` 和 `draw_jp_glyph` 族；日文放回官方 tm1；
16px 中文走方式 A（预渲染进 atlas + 零像素引用）；12px/8px 保留原地 blend。
`kV6Scenes` 及 `zones[]` 按坐标分区定字号能力**全部保留**，且 `font_px` 升级为
「落址开关 + 槽容量调节旋钮」。

**🔴 方式 A 的关键语义（落地前必须认清，2026-09-03 定稿）：**

1. **16px 可复用槽、12px 不可复用**：
   - 16px 零相位 → 同 code 字模固定，可预渲染进 atlas 一个槽、同屏复用。
   - 12px 有相位（0/4 两态）→ 同 code 在相位 0 与相位 4 是两套字模，**无法
     复用同一预渲染槽**，退化成「每字领槽」（与 v6_alloc_tile 等价）。
   - ⇒ 槽映射的「可复用」红利只对 16px 成立；12px 仍每字独立领号。
2. **预渲染时机 = 打印时，不是 InitWindowTileData 时**：
   - `InitWindowTileData` 收到的「窗口控制块」**不知道**当前屏要显示哪些中文
     （文本运行时才逐个解出），所以「预渲染进 atlas」实际发生在**打印时**——
     中文首次打印才 blit 进空闲槽，之后同 code 复用。
   - 这使方式 A 与方式 B 在运行时行为趋同，唯一分水岭是「12px 相位」。
3. **槽空间**：atlas `[1, 0x201)` 是官方字库区。中文 16px 每字占 2 glyph 槽
   （4 tile）；需维护「code → glyph 槽」映射 + 空闲槽记账（按 tilemap 分桶）。

中文渲染数据流（V7 定稿，按字号分流）：

```
中文 code → GetGlyph 解压 128B 字模
        ├─ 16px → 槽映射(code→glyph槽) → blit 进 atlas → base+2*glyph 零像素引用
        ├─ 12px → 原地 blend + 相位（print_glyph_px，tile 号每字独立领）
        └─ 8px  → 1 槽
日文/半角 → FontFunc_NativeDispatch 直调官方 tm1 通道（放回）。
```

---

## 1. 一句话结论

中文的 tile 号来源从「高水位分配器 `v6_alloc_tile()`」改为「字形槽映射」的确定性
映射；日文放回官方 tm1 通道。**`v6_alloc_tile` 和日文统一通道删除**，12px 相位
机制保留（与 tile 号来源正交）。

---

## 2. 为什么成立（已反汇编实证）

### 2.1 tm1 官方通道的 tile 号是确定性的

`PrintGlyph_TextMode1` @0x0800360C → 调 `FontSubTable[fontNum]`（@0x081BB3BC）：

| fontNum | FontSubTable | 写表项函数 | tile 号 |
|---|---|---|---|
| 0, 3 | 0x08003585 | @0x08003584 | `base(1) + 2*glyph` |
| 1, 4 | 0x080035A1 | @0x080035A0 | `base + FontType1Map[glyph]`（紧凑表） |
| 2, 5 | 0x080035C9 | @0x080035C8 | `base + glyph + 0xD4` |
| 6 | 0x080035E5 | @0x080035E4 | `base + FontType1Map[glyph]`（变体） |

关键：`0x08003584`（font3 主路径）：

```
r2 = glyph << 1          ; glyph*2
r1 = win[0x16]           ; TILE_BASE = 1
r2 = r2 + r1             ; tile = base + 2*glyph
r2 |= 0x4000             ; palette<<12
UpdateTilemap(win, r2, r2+0x80)
```

→ **tile 号 = `base + 2*glyph`，零像素绘制，纯表项引用 atlas。** 只要 glyph 槽里
预渲染了正确字形，打印就是确定性的，无任何分配器。

### 2.2 InitWindowTileData 预渲染的落点

`InitWindowTileData` @0x08002A50，参数 `r0=控制块 r1=startOffset r2=glyph序号`：

```
目的地址 = r0[0x0C] + (startOffset<<5) + (glyph<<6)
```

每个 glyph 写 2 tile（<<6 = 64B = 2×32B）。官方调用 `startOffset=1` → 256 glyph
× 2 tile = 512 tile，铺满整个 charBase `[1, 0x201)`。

→ hook 这个函数，就能在**官方预渲染之外**，把中文字形写进 atlas 的空闲槽。

---

## 3. 核心约束：atlas 只有 512 槽，中文 7168 字

这是整个方案的成败点。官方 atlas = 512 tile = **256 个字形槽**（每个 glyph 占 2
tile），但中文有 `CHS_FONT_GLYPH_MAX=7168` 字，无法全预渲染。

因此必须**动态字形槽映射**：维护「中文 code → atlas glyph 槽」的运行时映射，
当前屏要显示的中文按需 blit 进空闲槽。这是「分配器」从 tile 号粒度上移到
glyph 槽粒度的等价物——但**语义完全不同**：

- 旧 v6_alloc_tile：在**未知空闲**的 VRAM 里找 tile（§4「空闲不可知」硬伤）。
- 新字形槽映射：在**窗口边界内、自己掌控的 256 槽 atlas**里分配，空闲是**可知
  的**（槽表自己记账，不依赖官方释放通知）。

---

## 4. 关键设计决策

### 4.1 槽表放哪、多大

- 256 槽 → 槽表 256 项，每项记「占用 code」（u16）+ 状态位。
- EWRAM 落点需新分配（见 game.h 分配表），或复用已释放的区。
- ⚠ 必须在窗口重进/重建时清零（对应 InitWindowTileData hook 的复位点）。

### 4.2 中文一个 glyph 槽 = 2 tile，与官方一致

中文 16×16 字模 = 4 tile（TL/BL/TR/BR）。但 tm1 atlas 一个 glyph 槽只有 2 tile
（上下各 1，8×16）。**这是第二个硬约束**：

- 官方日文字形是 8×16（宽 8 高 16），占 2 tile（upper+lower）。
- 中文是 16×16，占 4 tile（2 列 × 2 tile）。

→ 中文一个「字」要占**两个 glyph 槽**（左半字 + 右半字），打印时连续写两个
`base + 2*glyph` 表项。这正好对应 v6 的「lower_delta 恒=1」/ 16px 整格 2 列的
语义，只是现在槽号是确定性的。

### 4.3 12px 相位 vs tm1 等宽

tm1 是等宽通道（每 glyph 固定 8px 宽，`cursorTileX += 1`）。中文 12px 步进
（12 mod 8 = 4）在等宽通道里**放不下**——除非：

- **中文在 tm1 通道里也用 16px 整格**（每字 2 glyph 槽 = 16px 宽），放弃 12px
  的紧凑排版；或
- 保留 12px 相位，但那需要 `cursorTileX` 半列推进，等宽通道不支持。

→ **这是必须跟用户确认的排版代价**：走 tm1 通道 = 中文等宽 16px，牺牲 12px 的
紧凑性（设置菜单 12px 候选列会变宽）。

### 4.4 场景规则表 / 相位表是否还需要

（本节旧结论「场景规则表可能不再需要」**已作废**，见 §4.5。）

**保留清单（明确不删）：**

- **场景规则表 `kV6Scenes`**：保留。它承载两层能力——
  1. **排版层**：`zones[]` 按 curX 分区定字号（`x<8→16 / x>=8→12` 混排），
     这是用户明确要求保留的「按坐标分区定字号」能力；
  2. **落址层**：`row_tab` 每行固定 tile 基址（确定性排列、重绘幂等）。
- **ChsPhase 相位表**：保留（12px 步进 12 mod 8 = 4 的两态相位，与 tile 号来源正交）。

### 4.5 按坐标分区定字号 = 与槽映射正交的「排版层」（新增需求）

用户补的需求要点：**保留 `zones[]` 按 curX/curY 坐标分区定字号的能力，作为
达到槽上限时手动调样式兼容的兜底。**

这里要厘清**两层正交**，避免把「字号/步进」和「tile 号来源」错误耦合：

| 层 | 机制 | 决定什么 | V7 处理 |
|---|---|---|---|
| 排版层 | `zones[].cx_hi / font_px` | 每字字号 16/12/8、步进、相位、混排 | **全保留** |
| 落址层 | tile 号来源 | 字模写进哪个 tile | 槽映射替换 v6_alloc_tile |

**兜底语义**：当槽映射（落址层）吃满 256 槽/自由区时，可通过**改排版层**——
调 `zones[]` 的分区字号（如把 value 列从 12px 降 8px、或把某列从 16 改 12）来
压缩单屏 tile 占用，从而「手动调整样式兼容」，而不必改落址层逻辑。

- 16px 步进 = 每字 2 glyph 槽（4 tile），12px 步进 = 相位共享每 2 字 3 列（省 1 列），
  8px 步进 = 每字 1 列（2 tile）。**字号越小，单字 tile 占用越省** —— 这正是
  兜底调样式能「省槽」的物理依据。
- 因此 `zones[].font_px` 不只是排版美观，还是**槽容量的调节旋钮**。

---

## 5. 待确认问题（阻塞实现）

1. **中文在 tm1 通道的宽度**：16px 等宽整格（每字 2 glyph 槽），还是保留 12px
   相位紧凑？前者牺牲排版密度，后者与等宽通道冲突。
2. **槽表容量与复用策略**：256 槽够不够一屏中文？一屏最多 ~50 字（cb2 自由区
   实证），256 槽 = 128 个中文（每字 2 槽），理论够；但多窗并发（能力页 3 窗体）
   需按 tilemap/窗口分桶记账。
3. **槽表落点**：EWRAM 具体地址（需查分配表空闲区）。
4. **font4 小字窗（队伍名 8px）**：走 tm1 的 font4（FontType1Map 紧凑表），
   中文 8px 小字库能否同样映射进 atlas？还是保留原 8px 路径？

---

## 6. 实施步骤（对齐后执行）

1. 确认 §5 四个决策。
2. 反汇编 `InitWindowTileData` 的完整 6 case 分支，确认 hook 插入点与参数语义。
3. 设计槽表结构 + EWRAM 落点。
4. 写 `InitWindowTileData_Hook`（入口复位槽表 + 按需 blit 中文）。
5. 改 `PrintNextChar_Hook`：中文走 `base + 2*glyph` 映射；删 `v6_alloc_tile` /
   `draw_jp_glyph` / `jp_glyph_to_g128`；**保留**相位表 + 场景规则表 kV6Scenes
   及其 `zones[]` 按坐标分区定字号能力（含兜底调样式）。
6. 日文放回官方 tm1 通道（`FontFunc_NativeDispatch` 的 tm1 分支直调 Origin）。
7. 完整流水线：hook build.bat → 根 build.bat → check_rom_hook.py → 冒烟。

**⚠ 删 `v6_alloc_tile` 时的保护**：`chs_place` / `print_glyph_px` 里「命中场景
规则 → row_base 确定性排列」分支与「未命中 → v6_alloc_tile 高水位」分支是并列
的。删除时**只删高水位分支**，`zones[]` 分区定字号（`v6_scene_font` /
`v6_scene_zone` / `v6_same_zone`）及其调用点**全部保留**——它们是新需求要求的
兜底能力，与 tile 号来源无关。

---

## 7. 与旧结论的关系

本文是 `结论_替换BUG真正难点_空闲tile不可知.md` §5「方案 A」的**轻量落地**：

- 方案 A 的「窗口独占 charBase」= tm1 窗口本来就有自己的 512-tile atlas
  （`InitWindowTileData` 已预渲染铺满），无需再动 charBase 分配。
- 方案 A 的「每帧全量重绘」= atlas 槽位是持久预渲染的，无需每帧重绘；只需
  **槽表生命周期 = 窗口生命周期**（窗口重建时复位槽表）。
- 「空闲 tile 不可知」→ 在窗口自有 atlas 的 256 槽内，空闲**可知**（自己记账）。

即：tm1 窗口的 atlas 机制，恰好就是方案 A 想要的「窗口独占 charBase」——日版
引擎其实**已经给了**，只是汉化之前一直在 tm0 原地绘制路径上绕，没去用这条
现成的确定性通道。
