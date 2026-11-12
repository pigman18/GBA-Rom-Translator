# AXVJ 中文 12px 渲染：串页方案（String-Page Renderer）— **已退役**

> ⚠️ 2026-11-11 晚：本方案因「页池盖住原版场景图块」实机画面不可看，
> 已整体退役。现行方案是 **纯函数 tile 网格**，见
> [`DESIGN_TEXT_12PX_GRID.md`](DESIGN_TEXT_12PX_GRID.md)。
> 本文档保留作为反证与取证记录（tm1 反汇编、字库、调色板实证仍然有效），
> 但页表 / PHYS / 列内容池 / 后置烙入等**不再是现行实现**。

> 2026-11-11 · 从 0 设计 · 不复用 `src/text/`、不参考 `text.bak`（两者已被删除）
> 本轮一手证据：日版 ROM 反汇编（capstone）、产物 ROM 字库逐字节解码、
> `scripts/research/string_page/page_prototype.py` 原型实测。
> 已读并遵守：`docs/FONT_12PX_DRAW.md`、`docs/DONT.md` §9/§13、
> `docs/POKEMON_RUBY_AXVJ00.md` §9.3/§9.4、`docs/AXVJ_UI_ISSUES_20261111.md` §11–§14、
> `docs/调研_20260827_pokeRS类12px机制与日版AXVJ00接入分析.md`。

---

## 0. 一句话

之前所有方案都在**运行时现场把字形像素拼进 VRAM**；本方案把这一步
**整体前移到构建期**：每条中文串在 PC 上被预栅格化成一组有序的 8×16 tile 列
（「页」），12px 相位已经烘进列像素里。GBA 运行时只剩三件原版本来就做的事——
**查表拿到 tile 号 → 整列 64B 搬进 VRAM → 写 tilemap 引用**。
没有像素合成、没有相位状态、没有行段、没有 arena、没有分配器、没有回收。

---

## 1. 本轮挖出来的最底层事实（反汇编实证，非文档转述）

### 1.1 日版 tm1 是「纯引用」，根本不写 VRAM

`FontFunc[1] @0x0800360C` 按 `fontNum` 分派 `FontSubTable @0x081BB3BC`：

```asm
08003612  ldrb  r0,[r4,#0xb]     ; fontNum
08003614  lsls  r0,r0,#2
08003618  ldr   r2,[r0,r2]       ; FontSubTable[fontNum]
0800361C  bl    0x081B12DC       ; CallViaR2(win, glyph)
08003620  ldrb  r0,[r4,#0x1b]    ; cursorTileX += 1
```

实测 `FontSubTable[3] = 0x08003585`，而实测场景里 `fontNum` 几乎恒为 3
（`AXVJ_UI_ISSUES_20261111.md` §13.3：bag 435/478、options 3509/3556、dex 70/111
都是 tm1）。`0x08003584` 全文：

```asm
08003584  push  {lr}
08003586  lsls  r2,r1,#1          ; r2 = glyph*2
08003588  ldrh  r1,[r0,#0x16]     ; TILE_BASE
0800358A  adds  r2,r2,r1          ; upper = TB + 2*glyph
08003590  movs  r3,#0x80 ; lsls #9 ; = 0x10000
08003594  adds  r2,r2,r3          ; lower = upper + 1
08003598  bl    0x080036DC        ; UpdateTilemap
```

`UpdateTilemap @0x080036DC` 只做 `strh` 到 tilemap（`palette<<12`）：

```asm
080036F0  ldrb  r1,[r6,#0xf] ; lsls #12 ; orrs r4,r1 ; strh r4,[r0]
080036F8  adds  r0,#0x40                        ; 下一行
08003700  strh  r5,[r0]
```

**⇒ 这条主链从头到尾没有一次 VRAM tile 内容写入。** tile 内容由
`LoadFixedWidthFont` 在窗口初始化时一次性 LZ 解压进 `[TB, TB+512)`
（§9.3.3 的 256 字形 × 2 tile），之后打印只是**引用**固定槽号。
这正是 `AXVJ_UI_ISSUES_20261111.md` §14.2 实测「同一个字全屏共用同一个 tile 号」的原因。

### 1.2 我们错在：在 tm1 的地盘上做了 tm0 的事

| | 原版 tm1（`FontFunc[4]`） | 我们十几轮的 hook |
|---|---|---|
| tile 号来源 | `TB + 2*glyph`（字符码，纯函数） | `TB + seg*62 + col*2`（屏幕位置，运行时算） |
| VRAM 内容 | 窗口初始化写一次，之后不动 | 每字逐像素合成、反复改写 |
| 需要的额外状态 | 无 | 相位表 / 行段号 / 清行判据 / 重印判据 / 池 |
| 冲突面 | 只占自己的字库槽 | 任意 tile 号，撞边框 / 精灵球 / ▶ 光标 |

`FONT_12PX_DRAW.md` 里写的 `abs = TILE_BASE + OFFSET + 2*xOff + yOff`、
`OFFSET += 2` 是 **tm0** 的契约（`0x08003570` 的 `ldrh [r4,#0x18]; adds #2`）。
我们把它当成了所有 textMode 的落址公式，于是从根上就选错了层。
**火红 / Wokann 之所以简单，不是因为字号不同，而是它们始终待在
「字库在 ROM → 一次性/按需搬进 VRAM → tilemap 引用」这条链上。**

### 1.3 为什么 12px 不能直接用「固定字库」

12px 步进 ⇒ `12 % 8 = 4`，相邻两字必然共享一个 8px tile 列，列内容依赖
「左字右 4px + 右字左 4px」。所以「按字符做固定 tile 号」（§14.4）在数学上
不成立；而「按内容做全局静态图集」本轮也实测证否了（见 §3）。
**相位是数据，不是状态** —— 这就是本方案的支点。

---

## 2. 方案：把相位从运行时状态变成构建期数据

### 2.1 构建期（PC，新增 `meowth/text_page.py`）

对产物里每一条文本串，按真实 token 宽度排布：
`F7 00 hi lo` = 12px、PCS 单字节 = 8px、控制码 = 0px（`FE/FB` 换行 = 切新页项）。

```
串 "妙蛙种子" (4 字 × 12px)
  → 6 个 8×16 tile 列（每列 64B = 上 32B + 下 32B）
  → owner  = [0,1,1,2,3,3]      # 每列由「最后一个碰到它的字」拥有
  → 每字引用列 = [[0],[1,2],[3],[4,5]]
```

栅格化规则（原型已实现，见 `page_prototype.py`）：
- 字模 128B / 16×16 槽，四象限 `TL BL TR BR`；墨迹盒 12×12 @ `pad_top=3`；
- **4bpp 低半字节 = 左像素**（`game.h` 与 §9.3.7 定案）。旧 `tile_get_px/put_px`
  按高半字节读是「重影 / 两字叠一起」的直接根因；本方案只在构建期读一次，
  运行时**完全不碰 nibble**，这个 bug 从物理上消失；
- 字 k 的像素 `X = 12k`，列号 `c = X>>3`、列内相位 `p = X&7`，
  共享列由两个字自然叠加进同一个 64B 缓冲。

**产物布局（ROM 扩展区，二进制格式见 §5.3）**：
| 区 | 内容 | 大小（实测 / 推算） |
|---|---|---|
| 内容池 | 全局去重后的 64B 列内容 | 27,997 × 64B ≈ **1.8 MB** |
| token 表 | 每个可印 token 一条：`addr / col_first / ncols / col_base / len / flags`，按 `addr` 升序 | **189,692 条 × 12B = 2.28 MB**（生成器实测） |
| 列 ID 序列 | 各 token 拥有的列 ID，全局拼接成 `u16[]` | **291,933 × 2B = 0.58 MB** |
| 窗口表 / `PHYS[288]` | `{tpl_lo,slot,nrow}`、逻辑列→物理 tile | < **2 KB** |

**生成器实测总量 4,652,588 B ≈ 4.44 MB**
（`work/string_page/page_table_report.json`），比初稿估算大，因为按地址
索引后串**不去重**（39,291 条实际串 vs 原型去重口径 23,215 条），
换来 §5.1 判断 C 的零运行时状态。已核对占用：
`0x09400000..0x09E00000` 是空段（`table_data.asm` 从 `0x09EB0000` 起、
`translated_slot.asm` 在 `0x09EA0000`、`region_alloc` 从 `0x09F00000` 起），
把 `PageTableVMA` 定在 `0x09500000` 可容纳到 `0x09970000`，不冲突。
内容池按字节去重，不是缓存、不是池分配。

### 2.2 运行时（GBA）

每个 token 到达 `PrintNextChar` 时（索引口径见 §5.1 判断 C）：

```
addr = WIN_TEXT_PTR + WIN_TEXT_INDEX             # 唯一免状态定位信息
1. 按 addr 二分查 token 表 → ncols / col_base / col_first / token_len
2. 对 i = 0..ncols-1：
     L     = zone*24 + col_base + i              # 纯函数，无状态
     upper = PHYS[L] ; lower = upper+1           # 构建期静态映射表
     copy64( tileData + 32*upper, POOL[id[col_first+i]] )   # 整列 64B 覆盖
     UpdateTilemap_Origin(win, upper, lower)     # 原版函数，写表项
     cursorTileX += 1
3. 非 F7 token 同样走页（构建期已把它的 8px 墨迹烘进列）
4. 未命中 / 动态流 / 页表缺失 → 消费但不绘制（§5.1 判断 D）
```

三个关键性质：
- **整列覆盖**：每列 64B 全写（含透明像素），不读回 VRAM、不做 OR/合成。
  `AXVJ_UI_ISSUES_20261111.md` §9.4.7 折腾四轮的「重印残留 / 清旧尾巴」
  自动消失——新串的每一列都把旧内容整块盖掉。
- **owner 表**：每列恰好在「最后一个碰到它的字」打印时被引用一次，
  `sum(owned) == ncols`、顺序严格递增（原型已 assert）。打字机逐字效果正确，
  不会出现「下一字左半提前露出」。
- **零运行时状态**：没有 `chs_px`、没有 `ChsPhase`、没有 EWRAM 相位表、
  没有 `gcache`、没有 `next_alloc`、没有 LRU。`game.bin` 无 RAM 段这个老坑
  （§9.3.5）也不再相关，因为唯一需要的状态是 `win` 自带的 `textIndex`。

### 2.3 编号：`(zone, col)` 纯函数 + 静态物理映射

```
tpl   = win_template(win)                    # 窗口模板指针（ROM 常量）
slot  = WIN_SLOT[tpl]                        # 构建期静态表：该窗口的区号起点
nrow  = ROWS_PER_WIN[tpl]                    # 构建期静态表：该窗口可见行数上界
row   = (CURSOR_Y + CURSOR_TILE_Y) >> 1      # 连续文本行号，依据见 §5.4
zone  = slot + (row % nrow)
L     = zone*24 + col_base + i                # col_base 来自 token 表项，i∈[0,ncols)
upper = PHYS[L] ; lower = upper + 1
```

`row` 的依据：`GetCursorTilemapPointer @0x08003708` 的
`lsls r1,#0x18` + `lsrs r1,#0x13` = `sum << 5`，说明
`sum = curY + curTY` 本身就是 tilemap 行号（32 项/行）；
换行 `CTY += 2`（16px 字占上下两行），故 `>>1` 得连续文本行号。

预算：`sum(nrow) * 24列 * 2tile`。实测同屏最多 3 个模板
（§7.1），按 9/1/2 分配 = 12 区 × 48 = **576 tile**。
`PHYS` 编号是相对 `tpl[0x0C]` 的 VRAM 索引（非 512 tile 字库区上限），
扫描 0..0x400 扣掉保留槽后生成器实测可用 288 对以上，足额。

- **为什么必须按模板分层**（本轮新证据，见 §7.1）：GDB 实测几乎所有窗口
  `TILE_BASE=0x0001`、`tileData=0x06008000`，**不同模板共用同一块 VRAM 字库区**。
  只按 `row%9` 会让两个窗口落进同一个物理区、互相覆盖。分层后每个模板有
  自己的区号段，仍是纯函数、静态表、零运行时判断。
- **为什么取模不会撞**：同一窗口内可见行的 `row` 是连续整数，连续 `nrow` 个
  整数模 `nrow` 给出互不重复的排列。§13.10 之所以炸，是映射表只有 6 项且
  「段满就整表清空重来」；本方案表长由实测行数定、永不重置。
- **为什么 `col` 不会越界踩自己**：列号是**串内相对列**，
  不是 §13.8 里那个从 19 起、到 31 的屏幕绝对列。
  **全量实测 39,291 条串、最长 15 字 = 23 列**
  （`page_table_report.json` 的 `max_col_span=23`），
  故页宽直接取 **24 列覆盖 100%**，构建期**不拆段**、运行时无 SPLIT 状态。
  初稿按 20 列 + 拆段是为了迁就「≤512 tile」这个后来被证伪的假设
  （PHYS 编号是相对 VRAM 基址的 10-bit 表项号，不受 512 限制）。
- **`PHYS[]`**：构建期从该窗口字库区里挑 288 个连续 tile 对，
  **排除**已被 UI 图形占用的槽：`0x000..0x07F`（BG3 边框 / 精灵球，
  §11.1）、`0x1E8..0x1FF`（▶ / No / 球图标，§11.1）、
  `0x20A..0x20D`（PSS B 图标，`game.h`）。
  排除是**构建期静态查表**，运行时没有 `scene_remap_tile`、没有场景门控，
  `text_scene.c` 整个文件不需要存在。
  **编号体系本轮已由旧代码一手确认**：`text_render.c::vram_tile(win,tile)`
  返回 `win_u32(tpl,0x0C) + (tile<<5)`，注释明写「模板 +0x0C 就是 VRAM 地址
  （实测 0x06008000 / 0x0600C000），不是偏移量」；`UpdateTilemap` 把同一
  tile 号 OR `palette<<12` 写表项（10 bit，0..0x3FF）。
  故 tile 号是**相对该 VRAM 基址的索引**，上界取 `0x400`
  （`0x06008000 + 0x400*32 = 0x06010000 < VRAM 末端 0x06018000`）。
  `text_page.py` 按三段保留槽跳过扫描，实测可挑满 288 对，预算不冲突。

### 2.4 这不是抬水位，也不是分配器

| 判据 | 本方案 |
|---|---|
| 改 `TILE_BASE`？ | ❌ 用游戏给的 `win[0x16]`，一个字节不改 |
| 改 `tileData` / 模板 `[+0x0C]`？ | ❌ 不改（§13.6 已证单独改必花屏） |
| 改 `BGxCNT.charBase` / 换 block？ | ❌ 不改（§12.1 已证此路死） |
| 找一段连续空段平移过去？ | ❌ 没有 arena，tile 号仍在窗口自己的 512 字库区内 |
| 运行时空闲表 / 回收 / LRU / key 哈希？ | ❌ 全无；`L = zone*24+col` 是纯函数，内容池只读 |
| 无证据调 +1/+2 常量？ | ❌ 12 / 8 / 24 / 12 区 / 576 tile 全部有出处（见 §3、§7.1、生成器实测） |

与"抬水位"的区别：抬水位是**把整个 arena 平移到更大的空段**；
本方案是**留在原地，只把已被 UI 图形占用的槽从静态编号表里划掉**。

---

## 3. 容量证明（本轮实测，不是估算）

`C:/Python314/python.exe scripts/research/string_page/page_prototype.py`
读取产物 ROM + 产物字库，扫出全部真实 F7 串并逐串栅格化：

| 量 | 实测值 | 来源 |
|---|---|---|
| 有效中文串（去重口径） | 23,215 条 / 137,144 字 / 2,883 个不同字 | 原型：产物 ROM 全扫 + charmap 过滤 |
| 有效中文串（按地址口径） | **39,291 条 / 189,692 字** | `text_page.py` 生成器全量实测 |
| 每串 tile 列数 | **max 23 / avg 9.08 / p99 20** | 逐串栅格化 |
| 超 24 列需拆段的串 | **0（24 列覆盖 100%）** | 生成器 `max_col_span=23` |
| 全局不同列内容 | **27,997** → 55,994 tile | 64B 内容字节去重 |
| 页表实测体积 | **4,652,588 B**，189,692 token / 291,933 列引用 | `page_table_report.json` |
| 每窗口预算 | **12 区 × 24 列 × 2 = 576 tile**，PHYS 实测 288 对足额 | §12.2 一屏 9 行 + §7.1 同屏 3 模板 + 生成器 |

两个结论：
1. **全局静态图集不可行**（27,997 列 ≫ 512/1024 tile）→ 这同时否掉了
   §14.4 的「按字符缓存」和用户已否掉的 `gcache`：任何想把全部内容
   常驻 VRAM 的做法都会被这个数字卡死。必须**按串按需搬列**。
2. **按串搬列完全可行**：平均串只要 9 列 = 18 tile，一屏 9 行 ≈ 162 tile，
   远低于 576 预算；最长 23 列也只占单区 24 列中的 23 列，不需要拆段或换区。

### 原型正确性（`work/string_page/page_sample.png`）

上排 = 理想 12px 逐字直绘，下排 = 页列经 tilemap 回放，
**逐像素 mismatch = 0**，目视「妙蛙种子」笔画完整、无重影、无粘连。
`page_report.json` 存了 owner 表与全部数字。

---

## 4. 两个 BUG 的修复机理

| BUG | 旧因 | 新方案为什么不再发生 |
|---|---|---|
| 图鉴滚动：精灵球变白块、编号错序 `012,009,013,008…` | arena 按 `row%7` / 累计行号映射到任意 tile 号，滚动时不同内容抢同一段并越界写到 BG3 边框 / 球图标（§11.1、§13.10） | tile 号 = `(模板槽, row%nrow, 串内col)` 的纯函数，`PHYS[]` 已排除所有 UI 图形槽；同窗口连续行取模互不重复、跨模板槽不重叠；每列整块 64B 覆盖，不残留、不串台 |
| 背包：每行文字叠影（两字画同一位置） | 运行时相位游标 `chs_px` 与 `cursorTileX` 记账不一致 + `tile_get_px/put_px` 把 4bpp 高半字节当左像素（`game.h` 注释、§9.4.1） | 相位在构建期烘进列像素；运行时按 owner 表顺序引用列，`CTX` 每列 +1；运行时零 nibble 运算 |

附带清掉的旧问题：重印残留（§9.4.7）、`scene_remap_tile` 的门控误伤、
`gcache` key 撞键、EWRAM 相位表被游戏清零、tm2 补余量把整块 tile 填成背景。

---

## 5. 文件结构：三件套收敛 + 数据侧重划

用户约束：`hook/src/text/` **只保留三件套**
`hooks_origin.s` / `entry.s` / `{函数}_hook.c`，
其余文件不沿用旧 `text_render.c` / `text_scene.c` / `text_translter.c`
的职责与命名。本节取代 §2.1/§2.2 里的 `stream_id / token_no` 接口，
栅格化规则、容量证明、`PHYS[]` 不变；页宽按全量实测从 20 列收紧为
**24 列（覆盖 100%、取消拆段）**，预算相应为 12 区 × 24 列 × 2 = 576 tile。

### 5.1 本轮三条设计判断（自己从代码倒推，不是文档转述）

**判断 A — 运行时逻辑真的薄到可以收进一个 C 文件。**
旧 6 文件里另三个模块的职责分别是逐像素 blit（render）、场景门控/remap
（scene）、F9/SLT2 协议翻译 + 1bpp→4bpp 解压（translter）。
按用户口径，F9 短语与 SLT2 **整体废弃**、全局统一 `F7 00 hi lo`。
本轮核查佐证：`charmap.py::encode()` 只 `extend(self._glyph_prefix)`，
`_escape_bytes`（F9 00）是从未写进输出的死字段；
`translate_plan.py` 2026-11-05 注释已明确「F980 通道彻底移除」
「SLT2 运行时查表通道彻底移除」。
于是：前两个职责**物理消失**（运行时不碰 nibble、不判断场景、没有 arena
需要避让），第三个**连翻译层都不存在了**——运行时流只剩
`F7 00 hi lo` / PCS 单字节 / `FA..FF` 控制码三类。
剩下的「取字节 → 查表 → 64B 搬 → 写表项 → 推进游标」没有再拆模块的理由。
**三件套不是硬塞，是逻辑真的变薄了**——这也是「只保留三个文件」能成立
的前提，而不是单纯为了对齐其他域的目录习惯。

**判断 B — 页表既不进 `game.bin`、也不走 armips，而是流水线【后置烙入】。**
`link/game.ld` 的 `ROM LENGTH = 0x10000`（64KB），当前 `game.bin` 实测
1,964 B；页表 4.44MB 塞进链接镜像要改 linker 长度、动摇
`JP2CHS_Entry == game.bin 起点` 这条硬约束（`main.asm` 直接把标签贴在
`.incbin` 上）。更关键的是 `engine.run_full()` 的阶段顺序：
`hook/apply_font_patch(armips)` **早于** `build` 阶段的文本注入，
armips 时 ROM 里还没有 F7 串，页表不可能按最终字节地址建表（§7.8）。
所以 `engine.run_full()` 在 `return built` 之前调用
`text_page.install_page_table()`：读**已经写完的 ROM** → 生成表 →
直接写到文件偏移 `0x09500000-0x08000000 = 0x1500000`。
`token.addr` 与 ROM 字节天然一致，无需两阶段打包、无需 `write.plan` 反推地址。
`install_page_table()` 自带开关：只有 hook 目录带 `include/text_page.h` 的游戏
才启用，其余返回 `None`；目标区必须全 `FF` 或已是旧 `PAG1` 表，否则拒绝覆盖。
⇒ `build.bat` / `Makefile` 的 syms 列表一个字都不用改，
`main.asm` 也不需要 include 页表。

**判断 C — 页表按「当前取指字节的绝对地址」索引，不按「串 ID + token 序号」。**
§2 原接口的 `stream_ofs(stream_id) / first_col_of(stream_id, token_no)`
有个没解决的前提：运行时得知道「我在本串第几个 token」。但旧
`PrintNextChar_hook.c` 取字符只有一行 `c = *(tptr + index)`——
`WIN_TEXT_PTR + WIN_TEXT_INDEX` 本来就是唯一、免状态的定位信息。
协议统一后**没有任何运行时切流**（`WIN_TEXT_PTR` 全程不变），
所以「现在属于哪条静态流」这个问题根本不存在；按串 ID 记账反而要
额外维护串起点与 token 计数。`FE/FB` 换行、`FC 0E` 跳列同理：
表项绑定的是**这个字节**，不是游标位置。
⇒ 格式从「每串一条记录」改成「每个可印 token 一条记录，key = ROM 绝对地址」，
运行时一次二分查找。条目数从 23,215（去重串）涨到 **189,692**（按地址 token，
生成器全量实测），每条 12B = 2.28MB，换来**零运行时状态**：
连「本串第几个 token」的计数都不用存。

**协议边界（用户口径，本轮已核查）**：运行时流只有三类——
`F7 00 hi lo`（4B / 12px）、PCS 单字节（1B / 8px）、`FA..FF` 控制码。
生成器不解析 `PhraseTable` / `SlotTable`，C 引擎不含任何
`redirect_phrase_stream` / `slot_lookup_v2` / FNV 分桶 / 短语展开。
`font.config.json` 里 `escape_bytes: [249,0]`（死配置）、
`main.asm` 仍 `.include gen/translated_slot.asm`、
`font_patch.py` 仍生成 `phrase_data.asm` 属历史残留：产物 ROM 仍扫到
2,205 处 `F9 00` / 33 处 `F9 80` / 2 处 `SLT2`，多为代码区噪声与未清理的
死表。按 §7 登记为流水线清理项，**新引擎一行都不依赖**；
运行时遇到 `0xF9` 按未命中处理（消费但不绘制，判断 D）。

**判断 D — 降级不回落原版函数。**
P01 只盖 `PrintNextChar@0x080032F8` 的 8 字节，且订址桩用 `bx`
（不是 `bl`）进 `EngineEntry`，所以 C 的 `lr` 是**原版调用者**的返回地址。
此时再从 C 里 `bl PrintNextChar_Origin`（回放 4 条序言后 `bx 0x08003301`）
会多压一层 `{r4,lr}`，与原版函数自身的 `pop {r4-r7,pc}` 深度不匹配，
栈会失衡。故页表缺失 / 动态 EWRAM 流 / 未命中一律走
**「消费但不绘制」**（推进 `WIN_TEXT_INDEX`、返回 1）：不写 VRAM、
不动 tilemap，最坏是那一格空白，绝不会重现花屏或飞 PC。
`PrintNextChar_Origin` 桩仍保留在 `entry.s` 作为契约文档，但当前不调用。

### 5.2 重新划分后的文件

| 位置 | 文件 | 职责 | 状态 |
|---|---|---|---|
| `hook/src/text/` | `hooks_origin.s` | P01 订址桩（armips），只 hook `PrintNextChar@0x080032F8` | **保留**（旧名 `hook_origin.s` 按 README §3.2 统一为复数） |
| | `entry.s` | `EngineEntry`（game.bin 起点，链接首位）+ `PrintNextChar_Origin` 回放桩 | **保留** |
| | `PrintNextChar_hook.c` | 引擎全部运行时逻辑：控制码状态机 / 按地址查页表 / 64B 列发射 | **保留并重写** |
| `hook/include/` | `text_page.h` | 页表二进制格式、`PAGE_*` VMA 与容量常量 | **新**（取代三个旧头） |
| `work/<game>/page_table/` | `page_data.bin` / `page_table_report.json` | 流水线后置产物；`page_data.asm` 仅供离线核对，**不经 armips** | **新，流水线生成** |
| `src/meowth/` | `text_page.py` | 扫最终 ROM 的 `F7 00` 流 → 预栅格化 → 去重 → 按地址排序写表 → 烙进 ROM | **新API** |
| `src/meowth/core/engine.py` | `run_full()` 末尾 | 调 `install_page_table()`，ROM 写完后才建表 | **新接线** |
| `src/meowth/` | `text_page.py` | PC 生成器：扫产物 ROM 的 `F7 00` 流 → 预栅格化 → 去重 → 按地址排序写表 | **新** |
| `scripts/research/string_page/` | `page_prototype.py` | 像素一致性 / 容量验证原型 | 已交付 |

**删除且不复建**：`text_render.c`、`text_scene.c`、`text_translter.c`，
以及 `include/text_render.h`、`include/text_scene.h`、`include/text.h`。
前三者的存在理由分别是「相位在运行时」「要避让 arena」「F9/SLT2 协议层 +
字模运行时解压」；串页 + F7 00 统一协议下三条前提全不成立。
`text.h` 里剩下的只有 `GetGlyph` / `PrintGlyph` / `DrawGlyph` /
`TranslateHandleChar` 这几个已废弃 API 的声明，留着只会误导，
故连它一起删，`text_page.h` 成为唯一引擎头。
`game.h` 只保留窗口访问器与 `ADDR_*` 常量，`CHS_*_FLOOR` /
`CHS_*_POOL_END` 那批 arena 常量留作历史注释、新代码不引用。

### 5.3 页表二进制格式（`text_page.h` 是唯一契约）

```
@PageTableVMA（建议 0x09500000，见 §7）
 PageHeader 32B : magic 'PAG1' | n_tokens | n_windows | off_tokens
                  | off_col_ids | off_pool | off_phys | off_windows
 PageToken  12B : addr(u32) | col_first(u32) | ncols(u8) | col_base(u8)
                  | token_len(u8) | flags(u8)   ← 按 addr 升序，二分查找
 Window      4B : tpl_lo(u16) | slot(u8) | nrow(u8)
 col_ids    u16[]: 每 token 拥有的列 ID 序列（全局拼接）
 pool       64B[]: 全局去重的 tile 列内容
 phys       u16[288]: 逻辑列 → 物理 tile 号（lower = upper+1）
```

`flags` 位：`bit0` = tm2 缓冲直绘（不写 tilemap）。
**无拆段位**：页宽 24 列 ≥ 全量实测最长 23 列，构建期无需拆段。

C 侧全部 `const` 只读，**没有 static 可写变量**——`game.ld` 无 RAM 段
这个老坑不再相关。

### 5.4 运行时骨架（`PrintNextChar_hook.c` 核心）

```c
/* 唯一入口：P01 → entry.s EngineEntry → PrintNextChar_Hook */
int PrintNextChar_Hook(TextPrinter *win)
{
    uint16_t index = win_u16(win, WIN_TEXT_INDEX);
    uint32_t addr = win_u32(win, WIN_TEXT_PTR) + index;
    uint8_t c = *(const uint8_t *)addr;
    const PageToken *tk;

    if (!page_ready() || !page_is_rom(addr))
        return page_consume_blank(win, addr);   /* 判断 D：不回落、不绘制 */

    if (c >= PCS_CTRL_BASE)                    /* FA..FF / FC 状态机 */
        return page_control(win, c, index);

    tk = page_find(addr);                      /* 按地址二分，判断 C */
    if (!tk)
        return page_consume_blank(win, addr);

    page_emit(win, tk);                        /* 见下 */
    win_set_u16(win, WIN_TEXT_INDEX,
                (uint16_t)(index + tk->token_len));
    return 1;
}

static void page_emit(TextPrinter *win, const PageToken *tk)
{
    uint32_t vram = rd32(win_template(win) + 0x0C);   /* 模板给的字库区 */
    unsigned zone = page_zone(win);                    /* 纯函数，无状态 */

    for (unsigned i = 0; i < tk->ncols; ++i) {
        unsigned L = zone * 24u + tk->col_base + i;
        if (L >= 288u) break;
        uint16_t upper = page_phys(L);
        copy64((uint8_t *)(vram + 32u * upper),        /* 整列 64B 覆盖 */
               page_col(page_col_id(tk->col_first + i)));
        UpdateTilemap_Origin(win, upper, (uint16_t)(upper + 1));
        win_set_u8(win, WIN_CURSOR_TILE_X,
                   (uint8_t)(win_u8(win, WIN_CURSOR_TILE_X) + 1));
    }
}
```

`page_zone()` 的行号依据（本轮新补的反汇编证据）：
`GetCursorTilemapPointer @0x08003708` 里
`lsls r1,#0x18` + `lsrs r1,#0x13` 合起来是 `sum << 5`，
即 `sum = curY + curTY` **本身就是 tilemap 行号**（每行 32 项），
不是像素值。实测 18 份 GDB 日志里 `sum` 取 0..18 连续 + 20/22/…/36，
说明换行 `CTY += 2`（一个 16px 字占上下两行）；
故 `line = (curY + curTY) >> 1` 才是**连续的文本行号**，
`zone = slot + (line % nrow)` 在步长 2 下依然覆盖全部区。
§2.3 的公式正确，但原先写的理由是错的，这里更正。

`textMode 2`（战斗缓冲，不走 tilemap）复用同一份 64B 列内容：
`copy64(win_u32(win, WIN_TILE_DATA) + i*0x40, src)`，由 `tk->flags` 位选择，
无需第二套绘制路径、无需场景门控。

---

## 6. 与火红 / Wokann / 原版的对照

| | 原版 ruby tm1 | 火红汉化 | Wokann pokeRS | 本方案 |
|---|---|---|---|---|
| 字库在哪 | ROM，窗口初始化 LZ 载入 VRAM | ROM 空白区 | ROM 扩容区 `0x09000000` | ROM 扩展区内容池 |
| 载入时机 | 窗口初始化，一次 | 独占 char block | 每字 `DrawGlyphTiles` | 每 token 一次 64B 整列搬 |
| tile 号 | `TB+2*glyph`（字符码） | 屏幕列连续递增 | `GetCursorTileNum` | `(模板槽, row%nrow, 串内col)` 纯函数 |
| 12px 相位 | 无（8px 等宽） | 独占块，按列写 | `8+4` 两趟 + `GetGlyphWidth` 返回 4 | **构建期烘进列像素** |
| 撞 UI | 不撞（只引用自己的槽） | 不撞（独占块） | 不撞（独占块） | 不撞（`PHYS[]` 排除保留槽） |

**四者并行的是同一条底层链**：字模在 ROM → 搬进 VRAM tile → tilemap 写引用。
本方案没有发明第四条链，只是把「字库单位」从「单字 128B」换成
「预合成 tile 列 64B」，从而让 12px 相位不再是运行时问题。

---

## 7. 未决项与风险（诚实列出，动手前逐条证伪）

1. **多窗口 `TILE_BASE` 是否隔离 → 本轮已实证「不隔离」，方案已按模板分层**。
   聚合 18 份 `bot/*/gdb_probe.log`（bag/dex/navigator/options，共 5,538 次
   `InitTextPrinter`）得到：

   | 场景 | 命中 | TILE_BASE | 同屏模板数 | tileData | 行区 `row%9` 覆盖 |
   |---|---|---|---|---|---|
   | bag | 954 | 全 `0x0001` | 2 | `0x06008000` | 0..8 全用到 |
   | dex | 873 | 全 `0x0001` | 2 | `0x06008000` | 0..8 全用到 |
   | options | 3555 | 全 `0x0001` | 2 | `0x06008000` | 0..8 全用到（zone2 占 1550） |
   | navigator | 156 | `0x0001` ×116 / `0x0000` ×40 | 4 | `0x06008000` / `0x06000000` | 0..8 |

   ⇒ **几乎所有窗口共用 `TB=1` 与 `tileData=0x06008000`，靠不同 tilemap
   （`0x06007000 / 0x06007800 / 0x0600F800`）区分**。所以 §2.3 必须用
   `WIN_SLOT[tpl]` 把区号按模板分层，只靠 `row%9` 会让两个窗口落进同一物理区。
   navigator 里 `tileData=0x06000000` 的窗口是另一个 charBase，天然独立，
   构建期给它单独一张 `PHYS[]` 即可。
   **仍需一次逐帧 GDB**：确认「同一帧内同时活跃的不同模板数 ≤3」以及各模板
   的可见行数上界，用来定 `WIN_NROW[]`（当前按 9/1/2 = 12 区估，576 tile）。
2. **混合串**：PCS 假名 / 数字 / 标点也要烘进页。字模可从原版
   `GetGlyphTilePointers_Origin(fontNum, code)` 在建 ROM 时离线导出
   （1bpp→4bpp 规则见 `FONT_12PX_DRAW.md`），不需要模拟器。
3. **换行 / 清空控制码**：`FE/FB` 在构建期把串切成多个页项；
   `FC 0E` 定位重排会让 `cursorTileX` 跳列——按地址索引（§5.1 判断 C）
   已把表项绑定到字节地址而非游标，`col_base` 由构建期给死，
   运行时不受跳转影响；但仍需一次 bot 回归确认跳列串的屏幕位置。
4. **颜色档**：`tpl[5..7]` 的组合有限（§10.2 实测两种典型）；
   页内容按「索引 0/1」生成，串首一次性把 1 映射成实际 fg 索引。
   若组合数超预期，改为按颜色档生成多份内容池（ROM 够）。
5. **页表体积与地址（已实证）**：全量 4,652,588 B；产物 ROM 回读
   `0x09500000` 得 `PAG1`，随机抽 500 个 token 的 `addr` 全部精确指向
   `F7 00`，`game.bin`(1,964B) 完整嵌入、P01 桩跳 `0x08800001`。
6. **`PageTableVMA = 0x09500000` 已实测**：运行时 GDB/RAM 诊断读到
   `PageHeader.magic = 0x31474150`（`!ready` 计数恒为 0），mGBA 对
   32MB ROM 的该区映射有效。
7. **流水线侧待清理（按用户口径，本轮不动）**：
   `main.asm` 仍 `.include "./gen/translated_slot.asm"`、
   `font_patch.py` 仍调 `write_slot_table_asm` / `write_phrase_data_asm`、
   `font.config.json` 仍留 `escape_bytes: [249,0]`、
   `game_addrs.asm` 仍留 `SlotTableVMA` / `Phrase*VMA`。
   新引擎与 `text_page.py` 都不读这些表；产物里 2,205 处 `F9 00` /
   33 处 `F9 80` / 2 处 `SLT2` 需在清理后用一次全 ROM 扫描复核是否归零。
8. **打包先后依赖（已解决：后置烙入）**：hook/armips 阶段早于文本注入，
   页表不能在 armips 里按最终地址生成。改为 `engine.run_full()` 在
   `return built` 之前调 `text_page.install_page_table()`，读**已写完的
   最终 ROM** → 建表 → 直接烙进文件偏移 `0x1500000`。
   `token.addr` 与 ROM 字节天然一致；离线冒烟验证了「页表区外字节逐字节
   不变」与「重复调用幂等」。`main.asm` 不再 include 页表。

### 7.9 ★ 首次实机 bot 实证的三处缺口（**均已修复并复测**）

**起点**：`bag` 道具名「学习装置 / 活力碎片 / 丝绸围巾」能渲染，
证明 `页表 → 64B 列拷 VRAM → UpdateTilemap` 整条链在 **ROM 静态流**上是通的，
页表装载、VMA、token 地址、PHYS 编号都没错。三处缺口同一批截图可见：

| # | 现象 | 实测原因 | 修复 |
|---|---|---|---|
| A | `dex` 列表只剩静态 `No`，编号与名字整片空白；`bag` 说明框空白 | 流指针是 `0x03007DE9`（IWRAM 临时缓冲），游戏把串复制进去再 `AddTextPrinter`；按 ROM 绝对地址建的 token 表对**动态流**失配 | **内容索引 `PagePair`**（见下） |
| B | `×2 / ×5 / ×3` 数字、标点全消失 | 生成器只烘 `F7 00` 汉字，PCS 单字节无 token，走「消费但不绘制」 | **PCS 现场展开**：`GetGlyphTilePointers@0x08003730` + `CopyGlyph1bppTo4bpp@0x08003830`（fg/bg 是参数），font3/4/5 shadowed 走 32B 直拷 |
| C | 中文是白字/发虚，`bag` 224 帧被判 `g_garble` fail | 字库像素实测只有 `0/0xF`，`0xF` 没映射到窗口前景色 | **`copy64_fg()`**：把非 0 nibble 换成 `win[0x0C]`（foregroundColor，`FC 01` 可改＝红字跟随）；栈上拼 64B 再 32bit 写（VRAM 禁 byte 写） |

**A 的做法（内容索引 `PagePair`，8B/条）**
12px 字模的列归属只取决于 `(前一个字, 本字, 是否串尾)`，与串的位置无关，于是：

```
key = (bits << 16) | cur_code
bits = [15] is_last | [14] has_prev | [13:0] prev_code   （has_prev = 相位 4）
      相位 phase = (12*k) & 7 ∈ {0,4}；相位 0 的列从边界起，与 prev 无关
```

运行时遇 `F7 00 hi lo` 且地址未命中：前扫最多 15 字拿 `prev` 与 `k`、后看 4 字节判串尾，
算 key → 二分 → 取 `(col_first, ncols)` → 走**同一套** `page_emit_cols()`。
全程零状态、零分配。生成器实测 **30,586 条**（245 KB），
且列 ID 序列按签名去重后总量从 4.65 MB 降到 **4,416,936 B**。

**同时修掉的两个定位错误**（都由实机截图暴露）：
- 页内列号必须用 **`curX + cursorTileX`**，与 `GetCursorTilemapPointer@0x08003708`
  同口径。只用 `cursorTileX` 会让同一行的多次 print（图鉴「编号 cx=19 + 名字 cx=22」）
  从头互相覆盖，表现为「学习装置 → 2装置」。页宽随之由 24 改 **32 列**，
  区数 12 → **9**（9×32×2 = 288 = PHYS 上限）。
- 菜单光标 `0xEF` 不是字模，是固定 tile 对 `0x1F0/0x1F1`；PCS `0x00..0x1F`
  属控制/空格区，取 0 号字模会画出杂字。两者都改为「占位不写 VRAM」。

**复测结果**（`work/string_page/bag_v5.png` / `dex_v6.png`）：
`bag` 八行道具名全部完整、`×N` 在正确列、颜色为深色；`dex` 显示
「◉No 003 妙蛙花」——精灵球图标完好、编号正常、**中文名出现**；
说明框「恢复宝可梦的体力 / 恢复 50」完整。

⚠️ `verify.py` 仍不能直接当验收：`dex` 的 `pass` 会把「日文被擦除」
判成汉化，`bag` 的 `g_garble` 会把深色中文与 origin 墨色差异判成乱码。
**逐帧看图才是本轮唯一可信判据。**

### 7.10 本轮同时修掉的两个 P0（已实证有效）

1. **控制码必须【先于】流位置判断**：原实现把 `!page_ready() ||
   !page_is_rom(addr)` 短路放在 `c >= 0xFA` 之前，导致 IWRAM 动态串里的
   `0xFF` 结束符被当普通字节吞掉，`WIN_STATE` 永远到不了
   `AXV_STATE_END`，RenderText 无限调用 → 游戏主循环不读输入 →
   bot 报「输入回调停摆 fr=6839」。A/B：恢复原版 P01 桩可跑 161 帧，
   新桩 + 原顺序必卡；把控制码前置后 161 帧全采完。
2. **缓冲直绘窗口不得调 `UpdateTilemap`**：`tpl[0x10]` 为 NULL 时原生
   `GetCursorTilemapPointer` 会把 tile 号 `strh` 到 `0 + offset`。
   按旧 `scene_is_buffer_printer()` 的同一判据（tm2 或 tilemap 基址为 0）
   改走 `win[0x20]` 缓冲，不回落原版函数（判断 D 的栈契约仍成立）。

### 7.11 颜色档的实测结论：单色只能取 index 1

`dex/bag` 列表窗口的运行时实测（EWRAM 诊断 + 调色板 dump）：
`fontNum = 3/4`（**shadowed font**）、`tpl[5] = 1`、`tpl[6] = 15`（背景）、
`win[0x0C] = 1`；调色板 bank15 里 `#4A4A4A@idx1`、`#D6D6CE@idx8`、
`#7BBDE7@idx14`。

origin 的日文是 **8（`#D6D6CE` 白）主墨 + 1（`#4A4A4A`）阴影**的双色预渲染字模，
白字靠深灰阴影才立得起来。而我们的 BDF 字库只有单色 `0xF`：

| 映射到 | 结果 |
|---|---|
| `tpl[5]` / `win[0x0C]`（=1） | 深灰、清晰（iter5 / iter14 截图） |
| `8`（白） | 在米色底上几乎看不见（iter13 截图实证） |
| `14`（`#7BBDE7`） | 早先误用，偏亮蓝、与白字风格差最多 |

**当前取 index 1**（`FontIsShadowed(fn) ? 1 : tpl[5]`）。
要完全还原 origin 的立体感，需要在构建期把 12px 墨迹烘成「主色 + 右下 1px 阴影」
的双色列（相当于给 BDF 加 shadow），属另一项工作，未做。

⚠️ 由此 `verify.py` 的 `g_garble` 在本工程基本不可用：它的
`sliver`（宽≤2 高≥6 的竖条）与 `fragment`（面积/填充率异常）判据会把
12px 中文的竖笔、偏旁直接判成「乱码/碎片」——`bag` 263 帧里 250 fail
全是这一类，而截图逐帧看是对的。**验收只能靠看图**。

## 8. 验收口径

1. 原型：`page_prototype.py` mismatch=0、`max_cols<=24`；
   生成器 `page_table_report.json` 的 `phys_budget_ok=true`、
   `strings_exceeding_zone=0`、`max_col_span=23`（已通过）。
2. 构建：10 个 obj 全过 → `meowth full` 重打包（页表由
   `install_page_table()` 后置烙入）→ ROM 回读页表 magic / token 地址。
3. 逐帧 bot：`dex` 滚动帧精灵球/编号与 origin 逐像素一致、
   `bag` 九行无叠影、`options/navigator/start_menu` 不回归；
   判据沿用 `AXVJ_UI_ISSUES_20261111.md` §10.3 的口径
   （sliver 误报单独收敛，不拿它当渲染失败）。
4. 反证：打印路径里搜索 `strh` 到 VRAM tile 内容的写入点，
   除 `PrintNextChar_hook.c` 的 `copy64` 外应为 0 处。

---

### 8.1 本轮实测结果（2026-11-11，正式流水线产物）

产物：页表 4,416,936 B / 189,692 token / 30,586 内容索引 / PHYS 288，
`game.bin` 2,840 B，ROM 32 MB。

| 场景 | pass/suspect/fail | fail 维度 | 逐帧看图 |
|---|---|---|---|
| dex | 20/39/102 | `g_garble` 101 | ✅「◉No 003 妙蛙花」精灵球完好、编号+中文名正确 |
| bag | 1/12/250 | `g_garble` 596 | ✅ 八行道具名、说明框、`×N` 位置全对 |
| options | 1/2/88 | `s_scene` 88 | ✅「对话速度/战斗动画/对战规则/声音/按键模式/窗口」全对 |
| navigator | 2/62/51 | `g_garble` 51 | ✅ 未发现错位 |
| start_menu | 54/1/1 | `a_translated` 1 | ✅ |

⇒ **判据与画面相反**：`g_garble` 的 `sliver`/`fragment` 把 12px 中文竖笔
判成乱码；`s_scene` 把「文字全换」判成非同一场景。**本工程的验收只能是人工看图**，
`verify.py` 需先为 12px 中文重写 sliver/fragment 阈值才可能自动化。



## 9. 与已有结论的冲突说明

- `FONT_12PX_DRAW.md` 的 `abs = TILE_BASE+OFFSET+2*xOff+yOff` 是 **tm0** 契约，
  本方案不走它（改用 `PHYS[]`），不构成对文档的否定，是把适用范围说清。
- `AXVJ_UI_ISSUES_20261111.md` §14.4「按字符归属」方向对，但实测
  27,997 个不同列内容证明**任何常驻 VRAM 的按字符/按内容图集都装不下**；
  本方案把它降级成「ROM 内容池 + 按串按需搬列」，不做运行时缓存。
- `DONT.md` §9「12px 只指墨水/步进，不改 8×16 容器」：本方案容器仍是
  8×16 tile 列（64B = 上/下两个 8×8 tile），完全遵守。
