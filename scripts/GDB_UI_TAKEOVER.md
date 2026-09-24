# 日版 UI 分配链「接管点」参数勘测（`--preset ui-takeover`）

> 2026-09-11 建立。对应 v10 设计 §3.0（接管点清单）与施工步 **S1.7**。
> 目标：把官方「固定公式分配」改写成 `vram_alloc` **之前**，实测确认每个点
> 「到底是哪个函数、入参/返回是什么、会不会被高频调用」。

## 为什么要先做这一步

用户原话：

> 「不只是基于现有代码改造，日版有 UI 分配的相关途径，都要 hook 然后进行自定义分配，
> 你该不会理解成只修改目前代码然后盲着进行分配了吧？」

以及本轮的具体要求：

> 「将需要 hook 的点在 gdb_patcher 中加埋点，这一步主要确认相关参数，不要 hook 错了，
> **记得以前有 hook 错函数结果一下子就把 cb 占满了明明没用到那么多内容**。」

⇒ 所以本 preset **不是**为了采「占用带」，而是为了**验证函数身份与参数**。

---

## 一、跑法

与 `GDB_CB_LOAD.md` 相同，分两步（**先开 mGBA，再挂埋点**）：

```powershell
# 1) 启动带 GDB stub 的 mGBA（窗口会暂停，等 gdb 连上自动继续）
cd C:\code\GBA-Rom-Translator
& "tools\mGBA-0.10.5-win32\mGBA.exe" -g "roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"

# 2) 挂埋点（🔴 用隔离 venv 的 python：本机 C:\Python314 没装 yaml）
C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe `
  src\util\gdb_patcher.py log --preset ui-takeover `
  --log src\util\work\POKEMON_RUBY_AXVJ00\ui_takeover.log

# 3) 走到目标界面操作（见下）
# 4) Ctrl-C     ← 必须 Ctrl-C，否则拿不到 [UISUMMARY]
```

> 🔴 **不要用裸 `python`**：本机 `python` → `C:\Python314\python.exe`，**没有 yaml**
> （`ModuleNotFoundError: No module named 'yaml'`）。
> 只有 `C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
> 装了 `yaml 6.0.3`。脚本无需 `PYTHONPATH`（它会自己把 `src` 塞进 `sys.path`）。

- **不需要重编 ROM**：①~⑩ 全是**原版 ROM 地址**，我们的 hook 没有覆盖过它们
  （唯一被桩覆盖的 `InitTextPrinter@0x08002C68` 不在本 preset 里）。
  翻译版 ROM 直接跑即可；想采「纯官方」行为也可以改用
  `roms\origin\POKEMON_RUBY_AXVJ00.gba`（10 个点同样全活）。
- 走到目标界面：**领航员训练家列表 / 队伍 / 背包 / 商店 / 对话框**，**每个进出一次、各停 3~5 秒**
  （参考首采教训：只采到「启动/标题」＝无效，必须真的走进目标界面）。
- **结束时按 Ctrl-C**（不按 Ctrl-C 就没有 `[UISUMMARY]`）。

日志：`src\util\work\POKEMON_RUBY_AXVJ00\ui_takeover.log`

> 若你自己环境里 `python` 已带 yaml，用 `python src\util\gdb_patcher.py log --preset ui-takeover …` 也一样。

---

## 二、三重防挂错（本 preset 的核心）

| # | 机制 | 在哪 | 触发时打什么 |
|---|---|---|---|
| ① | **静态自检** | 装载断点后立刻，读 ROM 首字节 vs 期望 | `✅ 接管点自检通过（10 个点…）` / `🔴 接管点自检失败: X @0x… ROM=… ≠ 期望 … ⇒ 挂错点！` |
| ② | **运行期 pc 自检** | 每次命中 | `[UIH-PC!!] X: 命中 pc=0x… ≠ 期望 0x… ⇒ 挂错点（本次不发参数）` |
| ③ | **热函数守卫** | 单点超过上限 | `[UIH-HOT] X: 命中已超 N 次 ⇒ 判为热函数，后续只计数` + **自动撤除该断点** |

- 详打上限：普通点 **80** 次，`kind=hot` 点 **24** 次。
- 为什么要有 ③：**真正的「分配点」不可能每秒被调几百次**。被调爆 ⇒ 大概率挂错，
  或者（更可能）那个地址根本不是分配函数而是**绘制热函数**——本轮就实测到这种。

---

## 三、断点清单（10 个）

| # | 点名 | 地址 | 角色 | 关键参数 |
|---|---|---|---|---|
| ① | `TextLoadWindowTemplate` | `0x08002950` | 图集入口·主链（**重置**游标） | `r0=win  r1=tileOffset` → 返回 cap |
| ② | `ChsAllocTplMenu` | `0x080028BC` | 图集入口·**菜单孪生**（**不重置**游标） | 同上 |
| ① | `JpTm1Alloc` | `0x080029DA` | ① 的**唯一出口** | `r0=cap  r3=win` |
| ③ | `MultistepInitWindowTileData` | `0x080029E0` | 图集分帧装载（每帧 16 字） | 入口 `r0` 无意义，读 `gTplSlot` |
| ④ | `InitWindowTileData` | `0x08002A50` | 装载核心（真正写 tile 数据） | `r0=template`（**模板指针，不是 win**）`r1=startOffset  r2=glyph` |
| ⑤ | `ChsAllocFrame9` | `0x08062080` | 标准框基址（**叶函数**） | `r0=base` → 存 `*0x03000514` → 返 `base+9` |
| ⑥ | `ChsAllocDlg14` | `0x08062368` | 对话框框基址（**叶函数**） | `r0=base` → 存 `*0x03000516` → 返 `base+14` |
| ⑦ | `ChsAllocFrameGfx` | `0x08062094` | 标准框图形装载 | `r0=win`，消费 `*0x03000514` |
| ⑧ | `ChsAllocDlgGfx` | `0x08062684` | 对话框框图形装载 | `r0=win`，消费 `*0x03000516`（`swi 0x0B` CpuSet） |
| ⑩ | `BgLz77VramSvc` | `0x081B1298` | 硬编码装载唯一收敛点 | `r0=src  r1=dst` |

> ⚠ **⑨（`MenuLoadStdFrameGraphics@0x0806F16C` / `MenuDrawStdWindowFrame@0x0806F224`）默认不含**。
> 静态已判死：`0x0806F16C` 有 **459** 个调用点、`0x0806F224` 有 **161** 个，且内部走
> `0x08002CFC`/`0x08002DE8` 的**绘制**原语 ⇒ 是窗口框**绘制热函数**，不消耗 tile 空间
> （与 `UI分配函数登记_20260910.md` §1.2 一致）。要验证时手动追加：

```
--functions TextLoadWindowTemplate,ChsAllocTplMenu,JpTm1Alloc,MultistepInitWindowTileData,InitWindowTileData,ChsAllocFrame9,ChsAllocDlg14,ChsAllocFrameGfx,ChsAllocDlgGfx,BgLz77VramSvc,MenuLoadStdFrameGraphics,MenuDrawStdWindowFrame
```

---

## 四、日志怎么读

### 4.1 启动时先看自检行

```
  ✅ 接管点自检通过（10 个点 ROM 首字节全部与期望一致）
```

出现 `🔴 … 挂错点！` ⇒ **立刻停下**，别再往下采。这行代表 yaml 地址与 ROM 实况不符。

### 4.2 每条命中

```
[UIH] ChsAllocFrame9 #1/80 ⑤ 标准框基址 → [base,base+9)
  pc=0x08062080 lr=0x0806F0AA r0=0x0000000A r1=0x00000000 r2=0x00000000 r3=0x00000000
  官方游标: gTplSlot=0x0834F000 gTplBase=33 gAtlasCur=16 gFrame9Base=1 gDlg14Base=10
  入参 base/tileOffset = 10 (0x000A)
  ⇒ 官方占用 = [10, 19) = 9 tile（槽 gFrame9Base 当前=1，本调用后应≈10）
```

判读三件事：

1. **`pc` 是否等于点名期望** —— 不等就是 ② 那行 `[UIH-PC!!]`。
2. **`lr`（调用者）是否落在合理模块** —— 需要对照 UI 登记表的调用点：
   - ① 的两个调用点 `0x080685CA` / `0x0806F006`
   - ② 的两个调用点 `0x0806F090` / `0x0806F106`（**全在 `0x0806xxxx` 菜单段**）
   - ⑤ 的 14 个、⑥ 的 4 个（`0x08061C10` / `0x0806F054` / `0x0806F0AA` / `0x0806F0FA`）
   - 若 `lr` 出现在莫名其妙的地方（中断/每帧/动画）⇒ 挂错。
3. **参数是否成链**（见 4.4）。

`官方游标` 一行是**同一时刻**的 5 个官方分配槽快照：

| 槽 | 含义 |
|---|---|
| `gTplSlot` `0x03000328` | 当前窗口模板指针 |
| `gTplBase` `0x0300032C` | 图集 `tileOffset`（① 写入） |
| `gAtlasCur` `0x0300032E` | 图集装载游标（③ 每次 +16） |
| `gFrame9Base` `0x03000514` | 标准框基址（⑤ 写入，⑦ 消费） |
| `gDlg14Base` `0x03000516` | 对话框基址（⑥ 写入，⑧ 消费） |

### 4.3 结束结算

```
[UISUMMARY] ===== 接管点勘测结算 =====
  ✅ 所有点 PC 与期望一致（没有挂错）
  · ChsAllocFrame9                   1 次  主调用者: 0x0806F0AA×1
  · MenuDrawStdWindowFrame          27 次  主调用者: 0x0806F266×27  ⚠热函数(已撤断点)
  · MultistepInitWindowTileData      0 次（本次未触发）
  判读：① 有没有 🔴；② 『分配点』的 base/cap 是否成链；③ 哪个点被调爆
```

### 4.4 本轮最想验证的四条 —— ✅ **2026-09-11 已实测判读完毕**

> 采集：439 次命中，`[UIH-PC!!]` 0 次。**结论已写回** `docs/开发_20260911_接管全部charblock_设计.md` §3.0.1。

| # | 待验 | 判读结果 |
|---|---|---|
| A | **①/② 的 cap 是不是 512 / 256** | ✅ **是**，但**口径要改**：它不是「cap」而是「**帧图形的起始号**」。tm1/font3→**512**（16 次）、tm1/font4→**256**（2 次）、**tm3→`tileOffset+602` = 603**（反汇编 literal `0x25A` 实证） |
| B | **链是否成链** | ❌ **原假设（`tileOffset→cap→+9→+14`）错**。实测真链：**`①/②返回 →(槽 0x0202E6F0)→ ⑤ base →(⑤返 +9，槽 0x0202E6F2)→ ⑥`**。实测 `⑤=512→⑥=521`、`⑤=603→⑥=612`（都 +9 ✔）。且 `tileOffset` **恒 1**、与返回号无关；同一模板在不同事件给不同 base ⇒ base 不来自模板 |
| C | **框钩子能否定 cb** | ❌ **⑤⑥ 不能**（入参只有号）。✅ **唯一权威路径 = 模板 `tileData`**（⑦ 内部 `bl 0x08004254(win)` = `win[0]->tpl->tileData`）。实测模板 `charBase` ∈ **{0,1,2,3}**，与 `tileData` 严格一一对应 |
| D | **官方到底占多少 tile** | tm3：**声明 602，实际只写 2**（+框 23）← **这就是「cb 被占满」的根源**；tm1/font0,3：512（256 字×2 tile，dst 步进 64B）；tm1/其余：256（256 字×1 tile）；⑦ 框 9；⑧ 框 14。**全部落 `tileData + 号*32`** |

**⇒ 由 A~D 得到的最重要一条**：**决策点只有 ① 和 ②**。⑤⑥⑦⑧ 拿的号是从 ①/② 返回值经中转槽
（`*0x0202E6F0` / `*0x0202E6F2`）传过来的 ⇒ **改了 ①/② 的返回值，它们自动跟随，一行都不用改**。
v10 的 S3 因此从「接 10 个点」收缩为「**接 2 个点**」。

### 4.5 顺带会看到的东西

- ④ 会打模板字段：`charBase / font / textMode / tileData / tilemap`。
  **`tileData` 是绝对 VRAM 指针**（实测公式 `tileData + (base+idx)*32`），
  ⇒ v10 改 `charBase` 时**必须同时改 `tileData`**，否则图集仍写回旧 cb。**这条要记牢。**
- ⑩ 会同时被 `cb-load` 的 `[CBLD]` 行覆盖（同一个点），可交叉印证装载区间。

---

## 五、采完之后

1. `[UISUMMARY]` 有没有 🔴 / ⚠。
2. 逐点核 **4.4 的 A~D**。
3. 结果写回 v10 设计 §3.0 与施工表 **S1.7**，然后才能进 **S2**（第一个动 ROM 的步骤，
   且是零回归验证点）。

> 📌 **2026-09-11 起，本 preset 同时兼作 S2 的 gdb 通道**：Ctrl-C 结算会多打一段
> `[BGMAP]`（v10 层 2「**复刻美版 `UpdateBGRegs`：用模板 `bgNum` 定位 BG 层**」的匹配轨迹，
> 读 EWRAM `0x0203FC04`；布局 = 16B 头 + 22×16B 条目）。它是 `bg_remap.c` 的产物，
> 与本文件 §三 的 10 个断点无关。
> 判读请看 [`GDB_BG_REMAP.md`](GDB_BG_REMAP.md)。

### 5.1 ✅ 2026-09-11 首采已完成（判读见 4.4）

**一条命令重出判读表**（不必再手工 grep；没有 `[UISUMMARY]` 也照样出）：

```powershell
C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe `
  scripts\analyze_ui_takeover.py
```

它打 5 张表：0) 自检（静态 / `[UIH-PC!!]` / `[UIH-HOT]` / 命中分布 / 收尾方式）、
A) ①②返回值、B) 链核对（自动判 `⑥ = ⑤+9` 与 `tileOffset 恒 1`）、C) cb 来源（⑦⑧ 的模板表）、
D) 官方用量、E) window 对象与模板全集。

- **自检**：`✅ 接管点自检通过（10 个点…）`、`[UIH-PC!!]` **0 次** ⇒ **没挂错函数**。
- ⚠ **但没有 `[UISUMMARY]`**：收尾是**直接关了 mGBA**（日志末尾
  `[停止] GDB 连接已断开（mGBA 关了 stub 或已崩）`），不是 Ctrl-C。
  ⇒ **下次务必按 Ctrl-C**；不过逐条 `[UIH]` 行里参数是全的，**脚本仍能聚合**，本次没白采。
- 命中分布：③④⑩ 各 80（到详打上限）、⑥ 48、⑦ 42、⑤ 41、② 25、①/①′ 各 18、⑧ 4。
- 🔴 **③④⑩ 触顶（80）属正常**：它们是每帧/每字/每块图形的**高频装载点**，不是挂错。
  （③ 每帧 16 字、④ 每字一次、⑩ 每块图形一次 —— 与「分配点」的"一窗一次"量级完全不同。）
  **真正要担心的是 ①/②/⑤⑥ 这类「一窗一次」的点触顶** —— 那才说明挂错了。---

## 附：S3（v10 框号接管）判据

> ⚠ **本文件是工具书，不是流程单。**
> S3 的**默认验收判据是 ④ 画面**——开 ROM 看一眼商店，够了。
> ①②③ 只在「画面与预期不符、且想不出下一步该改哪」时才采，
> 见 [`rules/axvj-verify-layering.mdc`](../.cursor/rules/axvj-verify-layering.mdc)。
> 另外「桩到底进没进 ROM」属 **L1 静态**：查 `file 0x62080` 字节即可，**不必开 gdb**。

S3 后 ⑤ `0x08062080` 已被 **16B「自带返回」桩**劫持（首字节 `10 B5`，原 `00 04`；
桩型选择见 [`rules/axvj-thumb-hook-safety.mdc`](../.cursor/rules/axvj-thumb-hook-safety.mdc) 铁律三）。
**⚠ 自检语义别搞混**：
- `_UI_PROBE_SPEC["ChsAllocFrame9"]["verify"]` **必须仍是 `0004`** —— `_verify_probe_static`
  比的是 **`origin`＝日版原盘**，不是补丁后的 ROM。填 `10B5` 会**永久误报「挂错点」**。
- **补丁在没在**，看 `_verify_rom_identity` 新加的**活体补丁自检**行：它从 target 读
  `0x08062080`，应打 `✅ S3 补丁自检：⑤ @0x08062080 运行镜像 = 10 b5（16B 桩在位）`；
  若打 🔴 ⇒ **mGBA 加载的不是含 S3 的 ROM**（重开 ROM 再测，EWRAM 里的
  v10 发号器状态也一并作废）。

**看 `[UIH] ChsAllocFrame9` 段新增的副行：**

```
[UIH] ChsAllocFrame9 #1/80  ⑤ 标准框基址（v10 已接管，号来自 win_alloc 发号器）
  入参 base/tileOffset = 512 (0x0200)
  ⇒ 官方入参 base=512（v10 下已弃用），槽 sTextWindowBaseTileNum 当前=512，本调用后应 = 发号器给的号
  · v10 发号器：本场景第 1 次发框 ⇒ 框 [512, 535) = 9 tile，文字起点 535，本窗上限 1024
```

**判据（按优先级排序，④ 是默认验收）：**

| # | 层 | 看什么 | 期望 |
|---|---|---|---|
| **④** | **L2 画面（默认，先看这个）** | 实机看**商店**（v8 的撞框现场） | 领航员「路线名 + 训练家名」**同时出现、不互相覆盖** ⇒ **过了就收工，不采** |
| ① | L3 gdb（条件） | 是否出现 `v10 发号器未初始化` | **不应出现**（出现 ⇒ 跑的不是 S3 之后的 ROM） |
| ② | L3 gdb（条件） | 每次发框的 `框 [a, b)` | 起点 `a` **逐次递增**（512 → 535 → …），相邻**不重叠** |
| ③ | L3 gdb（条件） | `文字起点` | == 本次框终点；且与 `v8` 文字实际起始号一致（`JpTm1Alloc` 段交叉验证） |

**什么时候才真需要采 ①②③** —— 同时满足两条：
「④ 画面**没变化**（或仍然撞）」，且「想不出下一步该改哪个文件」。那时的具体问题是：
**「桩跑了吗？发号器给的号是几？」** —— 这才是 gdb 不可替代的场景（例如 S2 那种
「设计上就该看不出变化」的零回归轮次）。

⚠ ⑤ 的 `入参 base`（512）**永远是官方值**，不再是生效的号 —— 生效值只看「v10 发号器」那一行。
