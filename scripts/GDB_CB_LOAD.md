# 官方 cb2/cb3 装载参数取证（`--preset cb-load`）

> 2026-09-11 新增，同日**首采后补强到 v2**。上游：`docs/开发_20260911_S1_BGxCNT写入点归类与官方cb2cb3入口.md`
> 下游：`docs/开发_20260911_接管全部charblock_设计.md` §4 的 **S5.5**（官方装载改道）
> 首采判读：`docs/开发_20260911_S1.6_cb_load首采判读与埋点补强.md`

## 目的

S1 静态分析留下两个**只能实测**的问题（S1 报告 §4/§5）：

1. 官方**运行时**往 cb2/cb3 写的**实际参数**——目的地址、解压多大、覆盖哪些 tile？
   （S1 只证明「有 17~19 个官方装载函数会写 cb2/cb3」，没证明**写多少**）
2. 这些写入是否发生在「**我方已经往 VRAM 写过字之后**」？
   - 若**开窗后不再写** ⇒ v10 走方案 (a) 抢时间窗：层 2 在开窗时改 `charBase` 即可；
   - 若**开窗后还在写** ⇒ 必须走方案 (b) 改道（S1 已点名 hook 面：2 个原语 + DMA 封装）。

## 埋点清单（`--preset cb-load`，**13 个**断点）

### 装载路径（有参数 → 换算 tile 区间）

| 监听点 | 地址 | 读到的参数 | 为什么埋它 |
|---|---|---|---|
| `BgLz77VramSvc` | `0x081B1298` | r0=源 r1=目的（+ 源头的 LZ77 头 → 解压大小） | **全游戏「解压到 VRAM」的唯一蹦床**，S1 的 34/41 处 cb2/cb3 装载都过这里 |
| `BgGfxHeapLoad` | `0x08070A4C` | r0=源 r1=目的 r2=大小 | `DecompressAndLoadBgGfxUsingHeap`：LZ77→heap→CpuSet，**62 个调用点**；走 CpuSet 不走蹦床，必须单独埋 |

### 装载路径（标记点 → 只打 r0..r3）

| 监听点 | 地址 | 读到的参数 | 为什么埋它 |
|---|---|---|---|
| `BgGfxDmaCopy` | `0x08070A90` | r0..r3 | ⚠ **v2 新补**。`DecompressAndLoadBgGfxUsingHeap` 的**第二入口**（纯 CpuSet 搬运，不解压）。首采发现派发器 `0x080EB56C` 调的是**它**而不是 `0x08070A4C` ⇒ v1 漏了一整类。注意 **r1 是「半字偏移」不是目的地址**（目的 = 字面量池基址 + r1×2），故只作标记点 |
| `BgDmaLoadCb2` | `0x0804B61C` | r2=目的（DMA 的 DAD 槽） | DMA 路线的代表点（S1 §3.2 的 6 处 DMA 之一） |
| `BgCondLoadCb2` | `0x0800ACDC` | 无入参 | 带「已加载」标志的条件装载器：14 次固定 LZ77→cb2 |
| `BgStdLoad` | `0x0800AFD8` | 无入参 | 标准 BG 图形装载（cb0 + cb3 + heap + 条件装载器） |
| `BgTsSwitch` | `0x0800B988` | r0=bgId | 按 bgId(0..6) 分支的 tileset 切换器 |

### 界面归属（v2 新增：给 CBLD 明细标注「属于哪个界面」）

| 监听点 | 地址 | 读到的参数 | 为什么埋它 |
|---|---|---|---|
| `CbSceneDisp0` | `0x080EA530` | r0 低 8 位 = 界面 ID | 12 路跳转表派发器，按当前界面 ID 选一套 BG 图形装载。**首采的 4/7 次装载出自这里** |
| `CbSceneDisp1` | `0x080EB56C` | 同上 | 同构的派发器（另一组界面）。**首采的 3/7 次装载出自这里**——即首采 100% 的装载都出自这两个派发器 |

### A1 全层复位（判「会不会把我们的层打回原形」）

| 监听点 | 地址 | 读到的参数 | 为什么埋它 |
|---|---|---|---|
| `ResetBgs` | `0x0808FD5C` | mask/无 | A1 类①：清 BG0..3CNT 后写回默认值 |
| `DisableBgs` | `0x0808DB54` | r0=层掩码 | A1 类②：9 个调用点（A1 里最多） |
| `BgResetB` / `BgResetC` | `0x080B1300` / `0x080FCA24` | 无 | A1 类③④：与 ResetBgs 同形的另两份拷贝 |

> A1 四点 = S1 §2.3 判定的「**能一口气改写全部 4 层 `BGxCNT`**」的**全部**函数。
> 它们是 v10 层 2 在实现后必须确认「不会在开窗后把我们的层打回原形」的对象。

## 采集步骤

与 `GDB_SCENE_OWNER.md` 相同，只有第 2 步的命令不同：

```powershell
# 1) 启动带 GDB stub 的 mGBA（窗口会暂停，等 gdb 连上自动继续）
cd C:\code\GBA-Rom-Translator
& "tools\mGBA-0.10.5-win32\mGBA.exe" -g "roms\outputs\POKEMON_RUBY_AXVJ00_translated.gba"

# 2) 挂埋点
C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe `
  src\util\gdb_patcher.py log --preset cb-load `
  --log src/util/work/POKEMON_RUBY_AXVJ00/cb_load.log

# 3) 进游戏：**从标题一路走到领航员（PokéNav）训练家列表**，
#    途中刻意多进/出几个界面（地图、菜单、对话、战斗），每个界面停 3~5 秒
# 4) Ctrl-C     ← 必须用 Ctrl-C，否则拿不到 [CBSUMMARY]
```

日志：`src/util/work/POKEMON_RUBY_AXVJ00/cb_load.log`

> 断点地址是**原版 ROM 地址**（`0x08xxxxxx`），我们的 hook 没有改过这些函数，
> **不需要重新打包 ROM**——现有 `_translated.gba` 直接跑即可。
>
> 🔴 **首采的教训**：v1 采集只覆盖到「启动/标题」阶段就断开（7 次命中、无 `[CBSUMMARY]`）。
> 采集必须**真的走进目标界面**，并以 **Ctrl-C** 收尾。

## 怎么读

### `[CBLD]` — 装载参数（有目的地址）

```
[CBLD] #  4 LZ77→VRAM pc=0x081B1298 lr=0x080EA5D8 src=0x083B5544 lz=1280B dst=0x0600F800 ⇒ cb3+0x3800 t448..t487（40 tile）★ | 开窗前(ours=0) [sb31对齐⇒疑tilemap]
```

| 字段 | 含义 |
|---|---|
| `#12` | 本会话第 12 次装载 |
| `lr=` | **调用者**返回地址 → 用 `scripts/find_callers.py` 或反汇编定位是谁在装 |
| `lz=640B` | 从源头的 LZ77 头读出的**解压后字节数**（不是压缩后大小） |
| `cb2+0x040` | 目的地址落在 **charblock 2** 内、区内字节偏移 `0x40` |
| `t2..t21（20 tile）` | **覆盖的 tile 区间**（= 640B / 32B = 20 个 tile） |
| `★cb2` / `★cb3` | 目的地在 v10 要接管的两个 charblock 上 |
| `∩v10池 cb3[128,256)★` | 目的区间与 **v10 池（实测定稿值）**相交 ⇒ 直接入侵我们未来的地盘 |
| **`开窗前(ours=0)` / `⚠开窗后(ours=N)`** | **v2 新增**。`ours` = `0x0203FF70` 持久位图里已置位的 tile 数；非零 ⇒ 我方已写过字 ⇒ 这次装载发生在**开窗之后**。这是回答「官方开窗后还写不写」的**直接证据** |
| **`[sbN对齐⇒疑tilemap]`** | **v2 新增**。目的地址落在 **2KB 边界**（screenblock 粒度，`(dst-0x06000000) % 0x800 == 0`）⇒ 大概率是**整屏 tilemap 装载**，不是 tile 图形。首采 7 次里 **4 次**都是这种 |

### `[CBLD-MARK]` — 无参数装载入口（只看触发）

```
[CBLD-MARK] #  3 bgId切换 pc=0x0800B988 lr=0x08077DE4 r0=0x00000003 r1=0x00000000 ...
```

配合 `[CBLD]` 明细判断「这次装载是被哪条路触发的」。

### `[CBDISP]` — 界面派发器（v2 新增）

```
[CBDISP] pc=0x080EA530 lr=0x080EA100 r0=0x00000003 ⇒ 入参界面ID=3 界面ID[mem]=3（第 1 次）
```

- `入参界面ID` = `r0 & 0xFF`（函数内部就是 `lsls #0x18; lsrs #0x18` 取它）
- `界面ID[mem]` = 跳转表实际用的那个 ID（从全局结构里读），两者一致 ⇒ 确认语义
- **把同一时刻前后出现的 `[CBLD]` 归到某个界面** ⇒ 首采无法区分「启动 / 地图 / 领航员」的原因就在这里

### `[CNTRESET]` — A1 全层复位时机

```
[CNTRESET] #  1 关层 pc=0x0808DB54 lr=0x0808DB78 r0/mask=0x0000000A DISPCNT=0x0200
           BG0=0x1F09 BG1=0x1E0F BG2=0x0000 BG3=0x1F0A｜ours=4 tile ⇒ ⚠ 开窗后（我方已有字）
```

判据：`ours`（`0x0203FF70` 的持久位图）非零 ⇒ **我方已往 VRAM 写过字**，视为「已开窗」。

### `[CBSUMMARY]` — Ctrl-C 自动结算

```
[CBSUMMARY] 官方 VRAM 装载 42 次（非 BG 区 9 次）｜标记点 7 次｜按 cb：cb2:18次/12.3KB cb3:9次/6.1KB
            命中 v10 计划池：cb2:3次★
            装载发生在我方已写字**之后**的次数：2　⇒ 官方在开窗后仍写我们的 cb（必须改道）
            A1 全层复位 5 次，其中发生在我方已写过字之后 0 次　⇒ A1 复位未咬到我们
            界面派发器命中：0x080EA530/ID=3:1次 0x080EB56C/ID=0:1次
```

**直接读结论**：
- 「命中 v10 计划池」的次数 = 0 ⇒ 官方从不进犯实测池 ⇒ 池子可直接用；
- > 0 ⇒ 层 3 的池子要避开这些区间，或 S5.5 必须改道；
- **「我方已写过字之后」的装载次数 > 0** ⇒ 官方在开窗后仍写我们的 cb ⇒ **必须做 (b) 改道**；
- 「我方已写过字之后」的 A1 复位次数 > 0 ⇒ 同上，方案 (a) 不成立。

## v10 池子（实测定稿，2026-09-11）

| cb | 池子 | 依据 |
|---|---|---|
| cb2 | **`[44,512)`（468 tile）** | 首采实测只摸到 `t0..43`（#2 `t0..16`、#7 `t1..43`）；`sb16..23` 未见 tilemap 装载 |
| cb3 | **`[128,256)`（128 tile）** | 首采实测 `t256..298 / t320..383 / t448..487` 被整屏装载；`[0,124]` 是 BG1 占的（S1.5） |
| cb3 | ~~`[384,512)`~~ **禁地** | `sb30`/`sb31` = BG3/BG0 自身的 tilemap 区（`B7E4.tilemap=0x0600F000` / `B7B4.tilemap=0x0600F800`），首采 #4 直接往 `0x0600F800` 写了 1280B |

合计 **≈ 596 tile**（vs 初版假设 864）。⚠ 仍待「走到领航员场景」的完整采集复核。

## 相关代码

- 埋点实现：`src/util/gdb_patcher.py` → `_on_bg_cb_load()` / `_on_bg_load_enter()` /
  `_on_cb_dispatch()` / `_on_bg_cnt_reset()` / `_dump_cb_stats()` / `_lz77_size()` / `_cb_span()`
- 断点定义：`src/util/configs/POKEMON_RUBY_AXVJ00.yaml`（`gdb:` 段尾部 13 条）
- 静态依据：`docs/开发_20260911_S1_BGxCNT写入点归类与官方cb2cb3入口.md`
- 工具：`scripts/find_callers.py`（查 `lr=` 属于哪个函数）、`scripts/preview_cb_loads.py`（静态预演）
