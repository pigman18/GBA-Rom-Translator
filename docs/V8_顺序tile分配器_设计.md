# V8 顺序 tile 分配器 —— 设计文档

> 状态：已落地（2026-09-04 编译链接通过，待实机验证）
> 日期：2026-09-04
> 定位：替换 v6 静态行带表 + v7 动态行基址表的**第三套方案**，回到用户最初认知的
>   「顺序放入 + 避让带」模型。

---

## 0. 为什么又重写（必须写清楚，否则会重蹈覆辙）

### 0.1 用户的核心认知（正确，一直没被认真执行）

> 就是 `1..255` 的空间，里面有一些空间不能用（避让带），然后根据
> `字符串 + 渲染字体宽度（8 / 12 / 16）` 来存放进去而已。可以用占用最贪的
> 算法——默认前后都多出半格 + 分隔符来放入。

翻译成工程语言：

- **空间模型**：一块连续的 tile 号区间（相对当前 BG charBase 的偏移），其中有
  若干"避让带"（官方字库 / 场景映射 / UI 图标 / OBJ 精灵区）不可占用。
- **分配模型**：给定一个字符串 + 字号，按顺序把每个字放进空闲区间，字与字之间
  可留间隔 / 分隔符。**顺序分配器（sequential allocator）**。
- **唯一状态**：一个"当前放到哪了"的游标，窗口内递增，窗口退出即重置。

### 0.2 现状为什么"越改越烂"

当前回滚后的基线（git `5aec2db`）里，**一个字的 tile 号有三个互相对立的来源**：

| 来源 | 位置 | 触发条件 | 问题 |
|------|------|----------|------|
| ① 静态行带表 `row_tab` | `scene_cfg.c` | 命中 scene 规则 + `rule->row_tab` | 手写死 7 行，加窗口就要加表 |
| ② 分区偏移 `z->off` | `scene_cfg.c` | 命中 scene 规则 | 与 row_tab 叠加，语义是"tile 偏移"还是"像素偏移"没定死，两处注释自相矛盾 |
| ③ 动态分配器 `v7_alloc_tile` | `tile_alloc.c` | 未命中规则 / 16px 路径 | 位图 + 游标，但 16px 与 12px 走了**两条不同路径** |

三个来源在 `chs_place` / `print_glyph_px` 里按不同分支各自领号，导致：

1. **16px 标签列走 ③，12px 候选列走 ①+②** —— 同一窗口两种字号的 tile 号语义分裂。
2. **`off` 单位模糊**：`scene_cfg.c` 注释说"行内 tile 偏移"，值却是 0/10/20，而
   335d0e3 代码里 `row_base = row_base + z->off` 是当 **tile 号**直接加的。当 tile
   号加 10 就跳 10 列（80px），跟"候选 B 占 [10,20) 像素"的注释完全对不上。
3. **相位状态跨窗口残留**：`struct ChsPhase` 8 槽用"行指纹"当 key，窗口切换时靠
   失配检测兜底，不是显式清空 → 来回切换偶发残留（用户反复踩的 BUG）。

### 0.3 结论

**不是用户方案不对，是执行把它复杂化了。** 用户方案（顺序分配器 + 避让带）就是
对的，而且比现状简单。本文档把它定为唯一方案，删掉三来源，只留一个。

---

## 1. 目标

1. **tile 号 = 一个顺序分配器**：输入 `(窗口, 字号, 字符串)`，输出连续 tile 号，
   跳过避让带，字间可留间隔 / 分隔符。
2. **渲染侧最小侵入**：只保留"根据 fontSize 走对应渲染路径"这一层，**不动**官方
   光标推进、`UpdateTilemap`、`GetGlyph` 解压、栅格化等既有正确逻辑。
3. **状态最小化**：唯一可变状态是一个分配游标；它**只在窗口生命周期内有效**，
   窗口退出（新 `InitTextPrinter` 会话 / 模板指纹变化）即重置，杜绝跨窗口残留。
4. **通用**：对所有 tm1 窗口一致，不逐窗登记、不手写行数、不维护静态表。

---

## 2. 空间模型

### 2.1 坐标与单位

- tile 号是**相对当前 BG charBase 的偏移**（`0..1023`，tilemap 表项低 10 bit）。
- 一个 tile = 8×8 像素 = 1 列。
- 中文字模（128B 4bpp）按字号切成列对，每列对 = upper 32B + lower 32B（两个 tile）。

### 2.2 避让带（不可占用区间）

| 区间（相对号） | 含义 | 来源 |
|---------------|------|------|
| `[0x000, 0x100)` | 官方预渲染字库 atlas（InitWindowTileData 静态预渲染） | 实证，v4 tile_alloc.c |
| 详情页场景映射带（`~0x1C9..0x1F7` 一带） | 场景 / UI 图标 | game.h 硬编码 + gdb 实证 |
| OBJ 精灵区 | `charBase+t/512 == obj_charBlock` 的相对号段 | `(REG_DISPCNT>>4)&3` 运行时算 |

**可用区** = 全区间 `[lo, hi)` 减去避让带后的并集。`lo` 默认 `0x100`，`hi` 由 OBJ
charBlock 截断（见 §4）。

### 2.3 分配粒度

一个中文字占用的 tile 数由字号决定：

| 字号 | 列数 | tile 数 | 说明 |
|------|------|---------|------|
| 8px  | 1 列  | 2 tile | 半角 / 标点，upper+lower |
| 12px | 视墨迹 | 2~3 tile | 相位共享，最宽约 2 列 |
| 16px | 2 列  | 4 tile | 整格 |

**字间间隔 / 分隔符**（用户说的"前后多出半格 + 分隔符"）：分配器为每个字预留
固定间隔，避免相邻字在相位共享时互相踩踏。间隔粒度与实现见 §5。

---

## 3. 核心接口（唯一入口）

```c
/* 顺序分配器：为「当前要画的这个字」分配 tile 号。
 * 输入：
 *   win      当前 TextPrinter（取 charBase / tilemap / 模板指纹）
 *   font_px  字号 8 / 12 / 16
 *   glyph_len 这个字预计占用的 tile 数（8px→2，16px→4，12px→由相位定）
 * 输出：
 *   分配的起始 tile 相对号（0 表示无空闲，调用方放弃绘制，宁缺不砸 UI）
 * 副作用：
 *   推进窗口内分配游标；标记本次占用（防同会话内自撞）
 */
uint16_t v8_alloc_tile(TextPrinter *win, uint8_t font_px, uint8_t glyph_len);
```

**关键原则（用户定稿）**：

- **一个函数**，不再有"静态表命中走 A、未命中走 B"的双路径。
- **顺序放入**：游标单调推进，字间留间隔 / 分隔符，跳过避让带。
- **无行基址表、无 row_tab、无 z->off、无窗口指纹清空**——这些全删。

---

## 4. 分配算法（确定性 + 贪心）

```
alloc(win, font_px, glyph_len):
    char_base = tpl[TPL_CHARBASE]          # 相对号基准
    hi = alloc_hi(char_base)               # OBJ 精灵区上界截断
    lo = 0x100                              # 避开官方 atlas
    cursor = read_cursor(win)              # 窗口内游标（RAM，见 §6）

    # 从游标起，找 glyph_len 个连续空闲 tile，且整段不落避让带
    for t = max(cursor, lo); t + glyph_len <= hi; t += step:
        if 整段 [t, t+glyph_len) 全空闲 且 不落避让带:
            mark_used(t, glyph_len)         # 防同会话自撞
            write_cursor(win, t + glyph_len + GAP)   # 推进，留 GAP 间隔
            return t

    # 回卷：从 lo 再扫一遍（宁回卷也不越界砸 UI）
    for t = lo; t + glyph_len <= hi; t += step:
        if 整段空闲:
            mark_used(t, glyph_len)
            write_cursor(win, t + glyph_len + GAP)
            return t

    return 0                                # 彻底无空闲 → 放弃
```

要点：

1. **确定性**：固定起点 `lo` + 游标单调推进，同输入同输出（重绘幂等，防 v4 随机
   取址 / 重绘漂移坑）。
2. **贪心留间隔**：`write_cursor(t + glyph_len + GAP)`，`GAP` 是字间间隔 tile 数，
   实现"前后多出半格 + 分隔符"的效果，相邻字不共享边界 tile。
3. **避让带不靠猜**：空闲判定来自 tilemap 活引用扫描（§5），不是硬编码一张长表。
4. **OBJ 隔离**：`hi = (obj_cb > char_base) ? (obj_cb - char_base)*512 : 1024`，
   charBase 相对号天然不落 OBJ 精灵 charBlock。

---

## 5. 避让带如何获得（活引用快照）

避让带 = 「官方已经在用的 tile 号」。来源是**运行时扫 tilemap 活引用**，不是猜：

```
snapshot(win):                          # 每个打印会话（窗口）开始时调用一次
    clear_bitmap()
    tilemap = tpl[TPL_TILEMAP]           # 32×32 = 1024 表项
    for i in 0..1023:
        t = tilemap[i] & 0x3FF           # 低 10 bit 是 tile 号，高 4 bit 是 palette
        if t != 0: set_bit(t)
```

- 这张位图是**本会话的占用基线**，之后本会话自己写进去的 tile **不再回头看**
  （防"自画污染"——把自己刚画的字也当官方占用，导致后续字无处可放）。
- 位图尺寸：1024 bit = 128 字节，落 EWRAM 固定地址（见 §6）。

**为什么这样最简单也最稳**：官方窗口在 `InitWindowTileData` 时已把要显示的字形
预渲染进 tilemap，扫一遍就是完整避让带，不需要人工维护"哪些区间能用"。

---

## 6. RAM 状态（最小化 + 生命周期）

| 地址 | 大小 | 内容 | 生命周期 |
|------|------|------|----------|
| `ADDR_V8_ALLOC_STATE` | 128B | 占用位图快照 | 每个打印会话（窗口）开始时重建 |
| `ADDR_V8_CURSOR` | 2B | 分配游标 | 随位图一起重建，窗口退出即失效 |
| `ADDR_V8_PHASE` | 2B | 12px 相位（px，phase=px&7） | 随游标一起重建，窗口退出即失效 |

**关键（用户反复强调的"别来回切换出 BUG"）**：

- 游标、位图、相位**三者都在会话边界（`InitTextPrinter` 块）重建**，不存在跨窗口
  残留。相位不再是全局 8 槽 + 行指纹 key，而是一个会话内的单调增量。
- 不再需要单独的"窗口指纹清空"逻辑——因为游标本身就是窗口内的，新窗口自然从
  头开始顺序放，相位也从 0 重新累计。
- 删除 `struct ChsPhase` 的 8 槽跨窗口状态表（`ADDR_CHS_PHASE=0x0203FF90`），改为
  单一 `ADDR_V8_PHASE`（2B）。

> ⚠ RAM 地址需避开 `0x0203FFD2`（游戏数据区）。当前 `ADDR_V7_ALLOC_STATE=0x0203FEC0`
> 一带空闲，可沿用；`ADDR_V8_PHASE` 紧跟位图之后（`ADDR_V7_ALLOC_STATE+128+2`）。

---

## 7. 渲染侧（最小侵入）

保留既有的正确分层，**只替换 tile 号来源**：

```
chs_print(win, code, fontSize):
    fn = 真实 fontNum；tm = textMode
    fontSize = getFontSize(win, fn, tm, ...)   # 决策字号：8/12/16（见 §8）
    GetGlyph(win, code, g128, &w)              # 解压字模（不动）
    chs_place(win, tm, fn, fontSize, g128)     # 落址（只改 tile 号来源）
```

`chs_place` 内部（保留 12px 相位共享，但相位状态会话内绑定游标）：

```
chs_place(win, tm, fn, fontSize, g128):
    if tm == 2:  # 血条缓冲，无 VRAM（不动）
        ...
    if fontSize == 12:   # 12px 相位共享：两段式 + phase 0/4，复用上一列 tile
        px = read_phase(win)            # 会话内相位（会话边界重建）
        phase = px & 7
        if phase == 0:  tile0 = v8_alloc_tile(win, 12, 2)   # 领新列
        else:           tile0 = last_tile                       # 复用上一列
        # 画两段，推进 px += 12，记 last_tile
        write_phase(win, px + 12)
        return
    # 8px / 16px 整格：每列领 2 tile
    cols = chs_rasterize(g128, fontSize, buf)
    for col in 0..cols:
        tile = v8_alloc_tile(win, fontSize, 2)   # 每列 2 tile
        chs_place_col(win, tile, 1, buf_u, buf_l)  # 写像素 + UTM（不动）
        # 光标推进（不动，保留官方语义）
```

**删掉的东西**：

- `v6_scene_row_base` / `v6_scene_row_index` / `z->off` 分支
- `scene_cfg.c` 的 `kOptLabelRowBase` / `kOptRowBase` 静态表（保留注释作历史参考）
- `v7_row_base` / `v7_row_clear` / 窗口指纹 `ADDR_V7_WIN_FP`
- `struct ChsPhase` 8 槽全局相位表 + `cur_tile` 复用状态机（改为会话内单相位量
  `ADDR_V8_PHASE` + `last_tile`，与分配游标同生命周期）

---

## 8. 字号决策 `getFontSize`（回答用户第 1 个疑问）

用户设想：`fontSize = getFontSize(win, state, textMode, fontNum, 色C/D/E, pal,
TILE_BASE, TILE_OFF, curX, curTX, curY, curTY, index)`。

实际工程里，字号决策只需要**最少必要输入**，不必全量传入：

```c
uint8_t getFontSize(TextPrinter *win):
    fn = 真实 fontNum
    if fn == 4: return 8        # font4 小字
    tm = textMode & 7
    if tm == 2: return 8        # 血条缓冲原生 8px 槽
    # 设置菜单（tpl==0x081BB874）左标签 16px / 右候选 12px，用 curX 分区：
    if 命中设置菜单规则:
        return (curX < 8) ? 16 : 12
    return 12                   # 其余 tm1 默认 12px
```

- 其余参数（色 C/D/E、pal、TILE_BASE/TILE_OFF）是**渲染层**内部已有的，字号决策
  不需要它们；把它们塞进 `getFontSize` 签名反而制造"为什么传这么多"的困惑。
- 设置菜单的 16/12 分区用 `curX < 8` 一个判断即可，不再需要 `V6Zone` 数组 + off。

---

## 9. 与原静态表的等价性（怎么证明"算法算出静态配置"）

用户要求：动态算法算出的结果**等价于**原来手写的 `kOptLabelRowBase` / `kOptRowBase`。

等价性判据（不是逐字节相同，而是**渲染结果一致**）：

1. 顺序分配器从 `lo=0x100` 开始、按字号占用 + 间隔推进，在设置菜单这个特定输入下，
   会给每行分配一个稳定的 tile 基址（因为输入顺序确定 ⇒ 输出确定）。
2. 16px 标签列每字 4 tile、12px 候选列每字 2~3 tile，配合间隔，最终各字落在
   **不重叠、不撞避让带**的位置 —— 这正是静态表要达到的效果。
3. **无需让动态算出的基址数字恰好等于手写表的数字**（0x003/0x053/...）。手写表
   数字只是"当时手动挑的空闲缝"，动态算法按规则重新挑，只要同样空闲、同样不撞，
   就是等价。

> 这一点要在文档里明确写死，否则又会陷入"动态结果必须 == 静态表数字"的误解，
> 导致反复对不上。

---

## 10. 风险与边界

| 风险 | 缓解 |
|------|------|
| 区间不够放（长字符串） | 回卷 + `return 0` 放弃绘制，宁缺不砸 UI |
| 避让带漏扫（官方字被踩） | 位图来自 tilemap 全表扫描，不漏 |
| 12px 相位共享踩踏 | 间隔 `GAP` 保证相邻字不共享边界 tile |
| 跨窗口残留 | 游标/位图都在会话边界重建，无跨窗口状态 |
| 自画污染 | 快照后不看自己写的表项 |

---

## 11. 落地步骤（确认本设计后执行）

1. 删 `scene_cfg.c/h` 的静态表与 `off` 分区（保留结构定义最小化）。
2. 重写 `tile_alloc.c` → `v8_alloc_tile` 顺序分配器（删 row_base/row_clear/指纹）。
3. `PrintNextChar_hook.c`：`chs_place` / `print_glyph_px` 统一走 `v8_alloc_tile`，
   删 row_tab / z->off 分支与 `cur_tile` 复用。
4. `game.h`：清理废弃 ADDR，定义 `ADDR_V8_ALLOC_STATE` / `ADDR_V8_CURSOR`。
5. 完整流水线：build.bat → meowth full --seed-only → check_rom_hook.py 逐字节一致。
6. 实机验证：设置页 16px 标签 + 12px 候选无重叠、开始游戏页无残影、来回切换无残留。

---

## 12. 开放问题 —— 已确认结论（2026-09-04 用户拍板）

1. **字间间隔**：**紧排，不要 GAP**（相位共享完全生效，相邻字间距 0）。GAP 作为
   未来可配置项暂不引入（默认 0），避免多一个无必要状态。
2. **设置菜单 16/12 分区**：**维持左 16 / 右 12**，做成 `getFontSize(win)` 钩子嵌入
   主流程（`curX < 8 → 16px，否则 12px`），不再用 `V6Zone` 数组 + `off` 分区。
3. **12px 相位共享**：**保留（用户选 B）**。相邻 12px 字共享交界半列 tile（phase 0/4
   两态），视觉紧排。相位状态与分配游标**同生命周期**——都在 `InitTextPrinter`
   会话边界重建，不再用全局 8 槽 + 行指纹 key 的跨窗口兜底（根治来回切换残留）。

> 结论：本文档 §7/§9 中"12px 退化为一列一字、去掉相位状态"的假设作废，改为
> "保留相位共享，相位状态会话内绑定游标"。
