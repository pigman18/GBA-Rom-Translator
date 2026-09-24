# S2 方案：不通过 cb —— screenBase 通道

> 状态：**待用户确认**（2026-09-11）
> 前置：v20 已完整撤销，当前树 = v18 干净树，ROM = `_translated.gba` @ `074791122ee9`，
> hook `game.bin` = 9060 B，`0x081B1298` 已还原原装 `12df 7047`。

---

## 0. 用户的三句话定义了本方案

1. 「背包进入卡死，领航员进入重启」⇒ v20 手法**判决**（下面 §1 有硬证据）。
2. 「全网搜索一下是否有更好的解决方法」⇒ 已找到 pret 官方 wiki 的权威表述（§2）。
3. 「**或者不通过 cb**」⇒ 正是本方案的落点（§3）。

---

## 1. v20 为何必崩：手法与生命周期打架（硬证据）

`tools/pokeruby/src/party_menu.c:623`：

```c
DmaFill16Large(3, 0, (void *)(VRAM + 0x0), VRAM_SIZE, 0x1000);
```

**这些 UI 每进一次，就整块清空 VRAM，然后按固定顺序逐项重新装载。**

v20 干的事是「在 LZ 装载点把目标区间清 0」——它插在人家「整块清 + 顺序重装」的**中间**，
把刚铺好、马上要被引用的中间数据清掉 ⇒ 背包卡死 / 领航员重启。

⇒ **不是判据错，是「在装载点上动手」这个手法本身不成立。** v20 判死。

---

## 2. 搜索结果：pret 官方 wiki 给了权威答案

来源：`pret/pokeemerald` wiki **How Menus Work ‐ Part 2**（已取全文）。

原文三条规则：

| | 规则 |
|---|---|
| ✅ | tilemap **允许**覆盖 tileset 中**未使用**的部分 |
| ❌ | tilemap **不允许**覆盖 tileset 中**实际用于 tile 图形**的部分 |
| ❌ | tilemap **不允许**互相重叠 |

原文关键句：

> tilesets 和 tilemaps **存在于同一地址空间**，**没有硬性规则规定谁该放在哪里**
> ——由你在 `BgTemplate` 里自行决定。

> 菜单打开时**通常清空 VRAM**，因此 tileset 中**唯一使用的 tile 是你分配给 window 的**，
> 以及你额外加载的图形。

⇒ 推论：**「UI 空白」不需要碰 cb、不需要清 VRAM。**

---

## 3. 方案：screenBase 重定向

### 3.1 原理

`REG_BGxCNT` 的 **screenBase = 位 8..12**（`0x1F00` 掩码），**单位 2KB，范围 0..31**。

把承载 UI 的 BG 的 **tilemap 指到一块预先清空的 screenblock**
⇒ 整层渲染为 tile 0 = 全透明 ⇒ **UI 视觉完全消失**。

**charblock / tile 分配器 / 任何 tile 图形，一个字节都不动。**

### 3.2 这条通道的三个官方背书

1. **tonc**：`Each charblock overlaps eight screenblocks. When loading data, make sure
   the tiles themselves don't overwrite the map, or vice versa.`
   ⇒ 两者同地址空间、可自由摆位。
2. **copetti.org**：`Programmers may place screenblocks anywhere in VRAM, potentially
   overlapping background charblocks (where tiles reside). This means that not all
   tile entries contain graphics!`
3. **项目内先例**（最有力）：`tools/pokeruby/src/pokemon_summary_screen.c:1342-1377`
   有 6 处运行时改 `REG_BG1CNT/REG_BG2CNT`：

   ```c
   REG_BG1CNT = (REG_BG1CNT & 0xE0FF) + 0x800;   // screenBase = 1
   REG_BG2CNT = (REG_BG2CNT & 0xE0FF) + 0xA00;   // screenBase = ...
   REG_BG1CNT = (REG_BG1CNT & 0xE0FF) + 0xC00;
   ```
   **官方自己就在运行时切 screenBase。** 这条路是可用的，不是我们发明。

### 3.3 相比 v20 的三条硬收益

| | v20（装载点清 VRAM） | screenBase 重定向 |
|---|---|---|
| 与 `DmaFill16Large` 生命周期 | ❌ 打架 ⇒ 卡死/重启 | ✅ 完全不相干 |
| 触碰 tile 分配器 | 间接（清了自己占的） | ✅ **零接触** |
| 「禁止抬水位」 | 需额外论证 | ✅ **天然满足**（不设任何不可用区） |

---

## 4. 各 UI 场景 BG 归属（已 grep 核实）

| 场景 | 文件:行 | BG0 | BG1 | BG2 | BG3 |
|---|---|---|---|---|---|
| 队伍菜单 / 背包 | `party_menu.c:740-743` | `0x1E05` | `0x703` | `0xF08` | `0x602` |
| 宝可梦信息页 | `pokemon_summary_screen.c:824-827` | `0x1E08` | `0x4801` | `0x4A02` | `0x5C03` |
| 信息页运行时切 | `pokemon_summary_screen.c:1342-1377` | — | `(x&0xE0FF)+0x800` | `+0xA00/0xC00` | — |
| 领航员 | `pokenav.c:357-359` | `0x1F01` | — | `0x1D0A` | `0x1C0B` |
| 领航员子页 | `pokenav.c:920/1081/1775` | `0x1F01` | — | — | `0x1E03` |
| 领航员 | `pokenav.c:1543/1706` | `0x1D0D` | — | — | `0x170B` |
| 简易聊天 | `easy_chat_2.c:963/980` | `0x8B00` | — | — | `0x0F0F` |
| 战斗 | `battle_main.c:1461` | — | `0x4801` | — | — |

解码掩码（供逐场景解析）：
- screenBase 位 = `(v >> 8) & 0x1F`
- charBase 位 = `(v >> 2) & 0x3`
- 256 色位 = `(v >> 7) & 1`
- 尺寸位 = `(v >> 14) & 0x3`

⚠ `party_menu.c` / `pokenav.c` / `easy_chat_2.c` **没有 `BgTemplate` 结构**，
是日版引擎的老式「裸写寄存器」风格 ⇒ 只能按上面的赋值点定位。

---

## 5. 实施步骤（待确认后执行）

**Step 1 — 补 equ（`hook/game_addrs.asm`）**

```asm
REG_BG0CNT   equ 0x04000008
REG_BG1CNT   equ 0x0400000A
REG_BG2CNT   equ 0x0400000C
REG_BG3CNT   equ 0x0400000E
REG_DISPCNT  equ 0x04000000
```
（当前 `game_addrs.asm` **一条都没有**。`tile_alloc.c` 里已有 `0x04000008 + bg*2` 的
C 端写法，可对齐。）

**Step 2 — 选「空 screenblock」的落点（已核实候选：SB 1..5）**

约束：必须在 VRAM 2KB 对齐处，且**不与正在使用的 tileset 图形重叠**（§2 第 2 条规则）。

实测推算（`party_menu.c:2204-2225` 的 5 处 LZ dst）：

| 资源 | dst 偏移 | VRAM | 占 SB |
|---|---|---|---|
| `gPartyMenuMisc_Gfx` | `+0x0000` | `0x06000000` | 0（跨多个） |
| `gPartyMenuMisc_Tilemap` | `+0x3800` | `0x06003800` | 7 |
| `gPartyMenuHpBar_Gfx` | `+0x6000` | `0x06006000` | 12 |
| `gPartyMenuOrderText_Gfx` | `+0x6180` | `0x06006180` | 12 |
| `gStatusGfx_Icons` | `+0x7180` | `0x06007180` | 14 |

⇒ **`SB 1..5`（`0x06000800..0x06002800`，共 10KB）未被队伍菜单使用**，
是「空 screenblock」的候选落点。

⚠ 但这只是**队伍菜单**的推算。**必须先确认 SB1..5 没有被其它场景的 tileset 图形占用**
（领航员 / 信息页 / 简易聊天 / 战斗各自的装载点都要单独核）。

⚠ 「划一块空 screenblock」**不是抬水位**：tile 分配器只发 **tile 号**（charblock 域），
从不发 **tilemap 号**（screenblock 域）。两者是不同地址空间里的两个概念。
但**这一点必须先向用户说明并获认可**，否则会被当成变相不可用区。

**Step 3 — 埋点：UI 场景的「进/出」**

方案有两态（正常 screenBase / 空 screenBase），必须在场景切换时切回去。
候选埋点 = 各 UI 的 BG 寄存器赋值点（§4 那张表），
在赋值处把 screenBase 换掉。**这里是本方案最需要谨慎设计的一环**，
因为要保证「出场景一定切回」，否则会把别的画面也弄空。

**Step 4 — 验收（按用户判据）**

- 满池 ⇒ 文字空白（已有，v18 行为）
- 满池 ⇒ **UI 也空白**（本方案新增）
- 背包能正常进入、领航员能正常进入（不回归 v20 的卡死/重启）

---

## 6. 🔴 必须先和用户对齐的一个语义分歧

**screenBase 通道给的是「UI 视觉空白」，不是「UI 分配失败返回 0」。**

因为它压根**不经过分配器** —— 这恰好是用户说的「不通过 cb」。

但用户此前的验收判据是：

> 「一旦分配区分完了，直接就返回空了，所以到顶 UI 和文字都会空白」

这两者的**屏幕输出一致**（都是 UI + 文字一起空），**机制不同**：
- **分配器路**：满池 → `v8_ui_alloc` 返 0 → ⑤ 返 0 → 框不画（**机制上「一起失败」**）
- **screenBase 路**：满池 → 检测到满池 → 切 screenBase → UI 整层看不见
  （**机制上「UI 被藏起来」**）

⇒ 若用户要的是「机制上真正同一条分配路径」，screenBase 路**不满足**（它绕过了分配器）。
⇒ 若用户要的是「屏幕上看不到 UI 和文字」，screenBase 路**满足**，且不卡死。

**这一点必须先确认。**

---

## 7. 另一条候选：真正接入分配器（收尾备注）

若用户坚持「机制上同路径」，则唯一出路是让各 UI 的图形装载**先向分配器要号**：

- 队伍菜单：`party_menu.c:2204-2225` 的 5 处 `LZDecompressVram` 改为先 `v8_ui_alloc` 拿号；
- `InitPartyMenu` 的 `DmaFill16Large(...)` 整块清 VRAM 必须**改为只清自己那几十个 tile**；
- 领航员 / 简易聊天同理。

**代价**：要改 `party_menu.c` / `pokenav.c` / `easy_chat_2.c` 三个场景的装载逻辑，
每个场景的「清 → 装 → 画」序都要重排 ⇒ 等于 §3.6 说的「渲染层重写」的一部分。
**风险远高于 screenBase 路。** 作为备选记录。

---

## 8. 参考

- `docs/UI_HOOK_SURVEY.md` §0/§2.3/§4（三句结论 + `sub_8095C8C` + 三条路）
- `docs/REWRITE_DESIGN_混合写入架构.md`（混合写入语义，运行时零 tile 分配）
- `docs/UI_LZ_SITES.md`（118+42 处装载点全表）
- `scripts/gen_lz_ui_sites.py` / `lz77_own.py` / `apply_v20.py` / `revert_v20.py`
- 外部：`pret/pokeemerald` wiki **How Menus Work** Part 1/2/3；
  gbatek `BGxCNT` 位定义；tonc charblock/screenblock 重叠；
  copetti `screenblocks anywhere in VRAM`；
  `rh-hideout-chinese/pokeemerald-expansion`（中文汉化，同问题活样本）
