# AXVJ 中文 12px 渲染：纯函数 tile 网格（现行方案）

> 2026-11-12 定案。取代已退役的 [`DESIGN_TEXT_12PX_PAGE.md`](DESIGN_TEXT_12PX_PAGE.md)
> （串页 / PHYS 池 / 4.4MB 页表方案）。本文只描述**现行**引擎，历史方案见退役文档。
> 实现唯一来源：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c`
> 与 `include/text_grid.h`。

---

## 1. 为什么必须换掉串页方案

串页方案把「12px 相位」整体前移到构建期，于是运行时每一列 64B 内容都得先搬进某个
VRAM tile —— 反推出 PHYS 池、288 对槽、按 ROM 绝对地址建的 4.4MB 页表，以及
`engine.run_full()` 末尾对 `0x09500000` 的后置烙入。这条路的后果是：页池直接盖住
原版场景图块/字库区，实机出现黑块、碎片、叠影，用户判定「没一个场景能看的」。

更根本地说，**它又回到了「管 tile」**：分配器、水位、回收、场景门控全都回来了。
用户要的是「绕开 tile」。

绕开的钥匙在日版 Ruby 自己的 tm1 机制里（`docs/POKEMON_RUBY_AXVJ00.md`
§9.3.2 / §9.3.3、`TASKS.md` §1.2）：

```
FontFunc[1] @0x0800360C 只写 tilemap，不写 VRAM tile 内容
tile 号 = TILE_BASE + 2 × 字形码        ← 纯函数，没有任何分配器
[TB, TB+512) 是预载的 256 个日文字形，每个窗口独占 0x4000 = 512 tile
```

11-10 已实证的推广形式（§9.3.4 / §9.4）：

```
行号 = (CURSOR_Y + CURSOR_TILE_Y) >> 1
tile = TILE_BASE + (行号 & 7) × 62 + 列 × 2 + {上=0, 下=1}
列   = CURSOR_X + CURSOR_TILE_X
```

**tile 号是屏幕行列的纯函数**。没有水位、没有回收、没有页表、没有 EWRAM 相位表、
没有场景门控。8 行 × 62 tile = 496，尾部 `0x1F0/0x1F1` 留给 ▶ 菜单光标。

---

## 2. 契约

### 2.1 文件结构（用户指定）

`hook/src/text/` 只保留三件套，不沿用任何旧方案文件：

| 文件 | 职责 |
|---|---|
| `entry.s` | `EngineEntry`：`ldr r1, =PrintNextChar_Hook; bx r1` |
| `hooks_origin.s` | 原版函数订址桩（armips 侧） |
| `PrintNextChar_hook.c` | 唯一的 C 模块：控制码状态机 + 网格渲染器 |
| `include/text_grid.h` | 唯一契约头文件：网格常量 / 字库常量 / `lead_adjust` |

构建期**零页表**：字库由 `font_patch` 装入 `0x09000000`，`engine.run_full()` 不再
烙入 `0x09500000`（该区最终 ROM 实测为全 `0xFF`）。

### 2.2 文本流协议

全局统一 `F7 00 hi lo`；`F9` 短语 / `SLT2` 已废弃。

| token | 长度 | 步进 | 处理 |
|---|---|---|---|
| `F7 00 hi lo` | 4B | 12px | `gidx = lead_adjust(hi)*256 + lo` → `0x09000000 + gidx*128` |
| PCS 单字节 | 1B | 8px | `GetGlyphTilePointers_Origin` + 1bpp→4bpp 现场展开 |
| `FA..FF` | 1B+ | 0px | 原版控制码状态机（**必须先判**，见 §5） |

`hi` 是 charmap 的原始 lead，不是字库 gidx 高位。实测分布
`[(1,…), (28,18), (29,17), (30,843), (247,3)]`，必须做：

```c
lead_adjust(h) = h - 1 - (h >= 6) - (h >= 0x1B)
```

直接用 `(hi<<8)|lo` 会取到完全不相干的字形。

### 2.3 字库与 VRAM 口径

- `0x09000000` 起 7168 槽 × 128B；顺序 `TL(0) BL(32) TR(64) BR(96)`；
  4bpp **低半字节 = 左像素**；最终 ROM 实测非空槽 6807、墨迹值只有 `0/15`。
- 12×12 墨迹盒、`pad_top=3`，步进 12px；`12 % 8 = 4` ⇒ 只有 `0/4` 二相周期。
- 相位不落 EWRAM：`grid_phase(text, index)` 从串首（或最近 `FE/FB/FC 10` 换行/
  清窗）累计 `F7=12px / PCS=8px / 控制码=0px`，取 `w & 7`。
- GBA VRAM 禁止 byte 写：一列 64B 一律 `uint32_t` 读写。

### 2.4 跨列共享与逐像素合成

12px 字跨 1.5 个 8px 列。每个字读回目标列 64B，铺背景、写墨迹、32bit 写回：

- `phase=0`：写 `col` 整列 + `col+1` 左 4px，游标 `+1`。
- `phase=4`：`grid_load()` 把当前列**左 4px**（前一个字的右半）挑回来，
  其余铺背景，再写本字右 4px + 下一列整列，游标 `+2`。

因为 tile 号是 `(行,列)` 的纯函数，两次写会自然落在同一个 tile 上，共享列
天然合成，不需要任何表来记「这一列归谁」。

---

## 3. 颜色：只认窗口模板背景（V4/V5 实证修订）

空白像素**不能写 0**（透明会露出下层 BG / palette0 黑底），必须写窗口背景色。
但背景色取自哪里，是 V3 → V5 两轮实机取证才定下来的：

| 场景 | `tpl[6]` | 常态 `win[0x0D]` | 结论 |
|---|---|---|---|
| dialogue / options / navigator / start_menu | `0x0F`（白） | `0x0F` | 一致 |
| bag / dex | `0x00`（透明，露出白气泡） | `0x00` | 一致 |
| dex 滚动高亮段 | `0x00` | **被 FC 临时改成 `0x02`（红）** | 分歧 |

`-DGRID_DIAG` 环形日志（落 `0x0203E000`，128×16B，bot 的 `shot` 会从
`ram.bin` 偏移 `0x3E000` 读回）显示：六个场景里 `win[0x0D]` 正常恒等于
`tpl[6]`，只有图鉴在名字后补打 `0x20/0x80` 填充字时被 FC 改成 2。
V3 拿 `win[0x0D]` 铺整列 ⇒ VRAM tile `0x16B..0x171` 主色 nibble 变成 2，
整片纯红方块盖掉「妙蛙种子」后两字。

**定案**：tile 背景只认 `tpl[6]`（窗口模板固定色），`win[0x0D]` 只是 FC
可改的瞬时绘制色，不能拿来铺整块 tile。没有模板时才退回 `win[0x0D]`。

前景色：V7 定案 —— **三色语义按 `win[0x0C/0x0D/0x0E]`（C/D/E）逐像素还原**，
不再有 ink-only 归一，也不写死常量：

| 字模 nibble | 语义 | 取值 | 来源 |
|---|---|---|---|
| `15`（汉字墨迹 / font3 主墨） | 主墨 C | `win[0x0C]` | `InitTextPrinter` 从 `tpl[5]` 拷入，`FC 01` 可动态改 |
| `14`（font3 阴影） | 阴影 E | `win[0x0E]` | `tpl[7]`，六场景 DIAG 实测恒为 `8` |
| `0`（空白） | 背景 D | `tpl[6]` | 见上表，**不取** `win[0x0D]` |

- 旧 `grid_fg()` 写死 `1` 或取 `tpl[5]`，把开始菜单玩家名一行的 `FC 01 0E`
  （C=14）整段吞掉 → 「继续游戏菜单颜色不对」根因。
- 旧 PCS `v ? fg : bg` ink-only 重映射把 `14` 折成主墨、`15` 折成主墨，
  阴影层 `8` 整片消失（V6 实测 start_menu `8` 只有 12 vs origin 396）。
- font0/1/2/6 是 1bpp 8B/tile，先按 `CopyGlyph1bppTo4bpp_Origin(…,1,0)` 展开成
  纯墨迹标记，再走同一三色映射；font3/4/5 是 32B/tile 的 4bpp-index 预渲染字模
  （`0/14/15`），原样保留。

**12px 汉字程序化阴影层**：中文 BDF 字库是单色 `0/15`，没有 origin 日文假名/
菜单字模的「C 主墨 + E 右下 1px 阴影 + D 背景」三色。V7 在 `grid_draw_chs()`
里先按墨迹在右下 1px 写 `E`、再写 `C` 压上，`bg` 由 `grid_pair_fill` 一次铺满
（主墨循环**不再写 bg**，否则会把刚补的阴影洗掉）。这不是 `DONT.md §9` 禁止的
`ShadowedFont(colors[0]=bg+OR)`：这里是显式三色独立像素。定量结果
（VRAM nibble 直方图）：`start_menu` 阴影 `8` 从 V6 的 12 恢复到 391（origin 396），
`options` 从 0 恢复到 1208（origin 1411）。

**无墨迹字形只推进游标、不重绘 tile**：原版 tm1 的空格只是把表项指到预载的
空白 tile，从不改 VRAM；本引擎若照常整列铺背景，会把 phase=4 共享列里前一个
12px 汉字的右半擦掉。

---

## 4. PCS 细节

- **`0xEF` 菜单光标是普通 PCS ▶ 字模，不是固定 tile 对**。ROM 实证：
  `font3 0xEF` upper/lower 是三角墨迹，`font0 0xEF` lower 是
  `00 60 70 78 7c 78 70 60`；origin 开始菜单把它画在 BG tile `0x128` 里的
  三色预渲染字模。V1~V5 特判成固定 `0x1F0/0x1F1` 且只写 tilemap，而新引擎
  从未往那两个 tile 写内容（VRAM 实测全 0）→ 光标整块消失。**已删除特判**，
  与其它 PCS 一样取字模展开。
- `0x00..0x1F` 是控制/空格区，取 0 号字模会画出杂字（图鉴/背包实证）。
- shadowed font 走 32B 直拷 + 三色重映射；其余走
  `CopyGlyph1bppTo4bpp_Origin`。重映射 `0→D / 14→E / 其余→C`，
  绝不 `v ? fg : bg` ink-only 归一（否则 `0xAB`「！」等预渲染三色字模会
  把阴影 nibble 当调色板彩色显示成蓝绿方块）。
- 图鉴数字是 PCS `0xA1='0' … 0xAA='9'`、`0xAE='-'`，由游戏运行时生成，
  **不是渲染器字形错乱**。

---

## 5. 控制码优先级（踩过的坑）

`c >= PCS_CTRL_BASE` 必须先于任何流位置判断。EWRAM/IWRAM 动态串里的 `0xFF`
若被吞掉，`WIN_STATE` 到不了 `AXV_STATE_END` → `RenderText` 无限调用 →
bot 出现输入停摆。`FC` 参数按类型跳过（`FC_ALLCOLORS` 3 参、
`FC_PLAYBGM/PLAYSE` 2 参、其余 1 参），否则颜色号会被当成 PCS 画出来。

P01 @`0x080032F8` 只盖 8B 且订址桩用 `bx`（非 `bl`），C 的 `lr` 就是原版
调用者返回地址；从 C 再 `bl PrintNextChar_Origin` 会多压一层 `{r4,lr}` →
栈失衡，故**任何情况下都不回落原版 PrintNextChar**。

---

## 6. 构建与诊断

```bat
REM 只重编 hook（产品构建；-DGRID_DIAG 为可选诊断开关）
cd configs\POKEMON_RUBY_AXVJ00\hook
set EXTRA_CFLAGS=-DGRID_DIAG && build.bat      REM 诊断版；不设即产品版

REM 完整流水线（--seed-only 不调 LLM；含 tiles 阶段 + 补齐 32MB）
cd /d C:\code\GBA-Rom-Translator
set PYTHONPATH=%cd%\src
C:\Python314\python.exe -m meowth full roms\origin\POKEMON_RUBY_AXVJ00.gba ^
  -o roms\outputs --work-dir work --source ja --target zh-Hans --seed-only
```

`build.bat` 的 `%EXTRA_CFLAGS%` 是唯一可注入口；`GRID_DIAG` 产品构建不带，
日志区 `0x0203E000` 是 `docs/POKEMON_RUBY_AXVJ00.md` §9.4.4 实证的恒零安全区
（不要落 `0x0203FFxx`，会被游戏周期清零）。

只读回日志的最快通道：bot 的 `shot` 落 `NNN.ram.bin`（schema 3：EWRAM
`0x02000000+0x40000` 在前，故环形区在 `+0x3E000`），`+0x1000` 是写指针；
**128 条 × 24B**，字段为
`tag / code(2B) / phase / cx / rel / col / flags(fontNum|buffered) /
t0(2B) / fg / bg / winC / winD / winE / palette / tpl[5..8] / textPtr(4B)`。

**armips 补丁链路（P24 之前踩过的坑）**：`meowth full/build` 的
`font_patch.apply_font_patch()` 会
`shutil.copytree(configs/<game>/hook → work/<game>/build)`，然后在 staging 目录
跑 `armips main.asm`。因此 `patches/*.asm` 的 `.org` 纯值补丁要生效，必须满足
两个条件：① `main.asm` 里 `.include "./patches/xxx.asm"`；② 改动落在
`configs/.../hook/` 源目录（不是 `work/.../build/`，后者每次 copytree 前会被
`rmtree` 删掉）。`main.asm` 第 39 行已 include `patches/pokedex.asm`。

---

## 7. 验收（2026-11-12 V8 正式 ROM）

正式产物：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`，
33554432 B，`sha256 bed8f9eaebaf244dc1cb343ee9bdb952ceeddad42b2fc86eeef1297f0f8e79ce`；
`game.bin 3488B` 与嵌入 `+0x800000` 逐字节一致；P01 桩 `0049084701008008`；
`0x0808ADB2` = `0x46C0`（P24 生效）；物种名表 stride 24，「妙蛙种子」
= 4×`F7 00 hi lo` (16B) + `FF@16` 终止符。

**六场景 bot 全部绑定该 ROM 的 SHA256（6/6 manifest 校验通过）**，读档证明
全通过、无输入停摆：

| 场景 | 帧对 | black_tiles | 备注 |
|---|---|---|---|
| dialogue | 87 | 0 | |
| bag | 263 | 0 | pure0 引用数差异经复核为共有空白 tile，非回归 |
| dex | 161 | 0 | **V8 新增：纯红像素 110 → 0，见 §8** |
| options | 91 | 0 | |
| navigator | 115 | 0 | |
| start_menu | 56 | 0 | |

`work/string_page/grid_verdict.py` 六场景 `black_tiles = 0`；
`work/string_page/scan_vram.py` 六场景 `colorNib = 0`（V7 的 dex 110 已归零）、
无新增整块纯 0 / 纯 15 tile。关键帧 VRAM nibble 直方图确认 C(1) / E(8) /
D(15) 三色在六场景都保留、量级与 origin 一致。

**判据说明**：旧 `verify.py` 的 `g_garble` 会把中文竖笔/偏旁判乱码，
`s_scene` 会把「换字」和「场景不同」混淆，`EXIT=1/2` 不代表实机异常。
本方案全程**不依赖 verify.py**，改用：
① `grid_verdict.py` 三条结构指标（`black_tiles` / `neon_pixels` / `outside_diff`）；
② `scan_vram.py` 直接扫 VRAM palette15 tile nibble（渲染器直接产物，不受换字位移影响）；
③ origin/translated 逐帧像素距离与区域裁切定量；
④ 纯红像素计数、C/E/D nibble 直方图等定向判据。
`options/navigator` 聚合 `neon/outside` 偏大是这两屏本来就是橙红彩色界面、
换字后彩色像素位移，不是污染（逐帧 VRAM 扫描已排除）。

---

## 8. 图鉴名字终止符：P24（V8 新增，实测推翻旧判断）

### 8.1 现象

图鉴列表名字行画出怪字（如 `No.003 妙9?`），后续编号行 `No.012/013/014`
前出现一排白色残块，宝可梦精灵与问号图标上有纯红方块；`GRID_DIAG` 日志里
名字行后出现 `FC/FC/FB` 控制码与 `D=2` 红色填充字。
VRAM 里 dex `0x1FD/0x1FE` 出现 110 个彩色 nibble（palette15 index 2 纯红）。
V7 曾把它判成「origin/translated 采集不同步导致的 UI 状态差异」——**这是误判**，
V8 定量证据见 §8.3。

### 8.2 根因（反汇编实证）

`CreateMonName @0x0808AD44` 的拷贝循环（`0x0808AD94~ADB8`）：

```
0808ADA0  ldrb r0,[r0]        ; src[r4]
0808ADA2  strb r0,[r2]        ; buf[r4] = src[r4]  ← 先写
0808ADA4  r4++
0808ADAE  ldrb r0,[r1]        ; src[r4]（新位置）
0808ADB0  cmp r0,#0xff
0808ADB2  beq end             ; ← 见 FF 直接跳出，FF 没被写进 buf
0808ADB4  cmp r4,#9           ; 流水线已扩到 #0x17
0808ADB6  bls loop
```

原版靠 `0x0808AD72` 预置 `buf[5]=0xFF` 兜底（日版 5 假名 = 5B，刚好不覆盖）。
译文是 `F7 00 hi lo` 4B/字，2 字就覆盖 `buf[5]`，4 字（16B）后整条流
**没有终止符**，读穿栈缓冲把相邻控制码与红色填充字一起画出来。

流水线已把 `sub sp,#0xc → #0x20`、两处 `cmp r4,#9 → #0x17`、物种名索引
`*6 → *24`、`buf[5]=FF` 保留，但**没有**修这个 `beq` ——
`src/meowth/write_plan.py` 里「名字路径的 FF 由源串自带」的假设与循环实际行为
不符，是根因。

### 8.3 修法与证据

`configs/POKEMON_RUBY_AXVJ00/hook/patches/pokedex.asm` **[P24]**：

```asm
.org 0x0808ADB2
    .dh 0x46C0        ; 0x0FD0 (beq end) → mov r8,r8 (thumb nop)
```

改 nop 后流程落到 `cmp r4,#0x17 / bls`，下一轮自然把 `src[r4]=0xFF` 写进
`buf[r4]`。5 个调用点全部丢弃 `r0` 返回值（`bl` 后直接 `b`/`pop`），故循环
跑满到 `r4=0x18` 不影响调用者。破折号占位分支 `0x0808ADC0` 不经过此循环，
仍用 `buf[5]` 的 FF，不受影响。**零新增 hook、零场景门控、零译名改动。**

| 证据 | V7（P24 前） | V8（P24 后） | origin |
|---|---|---|---|
| dex 帧 116/120/135/146/155 纯红像素 | 110 | **0** | 0 |
| dex VRAM `colorNib` | 110 | **0** | 0 |
| dex palette15 文本 tile 数 | 256/258 | **256/256** | 256 |
| 左侧详情区 `(0,32,122,152)` 与 origin 差异像素 | 128（恒定，即红块） | **0** | — |
| 右侧列表区 `(122,20,240,152)` 与 origin 差异像素 | 586~893 | **99~588** | — |
| dex 全帧与 origin 差异像素 | 921~1081 | **274~648** | — |

**名字气泡视觉对照**（`work/string_page/final_v8_dex_list_compare.png`，
帧 116/120/135/155，右侧 `x=122..240`）：

- origin：`No.003 フシギバナ`（5 假名），编号行 `No.004/005/006` 干净。
- V7：`No.003 妙9?`（名字带怪字），`No.012/013/014` 前有一排**白色残块**
  （读穿栈垃圾画出的控制码/填充字），宝可梦精灵与问号上有红块。
- V8：`No.003 妙蛙花`（3 汉字，与物种名表 index 3 `FF@12` 一致），气泡干净、
  编号行白底残块全部消失、精灵与问号无红块。

即 P24 修好的不只是名字本身，**读穿栈垃圾污染到的后续编号行也一并恢复**。
右侧列表区的剩余差异是「日文假名 → 中文汉字」的正常换字位移，不是污染。

### 8.4 已知遗留

1. **定宽字段宽度**：图鉴名字气泡是日版 5 假名 × 8px = 40px，
   译文「妙蛙种子」4 汉字 × 12px = 48px。P24 解决的是**终止符/读穿**，
   不是宽度；48px 是否会越过气泡右缘仍需在实机按气泡边框确认。
   不在渲染器里加场景门控或抬 tile 容量（§9）。
2. **图鉴列表号码不同步**：同一采集步 origin 显示 `004/005/006`、
   translated 显示 `012/013/014`，是 bot 按「画面稳定」对齐时两侧滚动位置
   不一致；号码由 PCS 数字真实生成（见 §4），不是字形错乱。
3. `verify.py` 的 `g_garble/s_scene` 仍会报 FAIL；按 §7 的结构判据验收，
   不按它的字形相似度。

---

## 9. 禁止回退清单

- 禁止「抬水位」/扩容 charBase / tile 分配器 / PHYS 池 / 场景门控。
- 禁止重建 `0x09500000` 页表、`text_page.h`、`src/meowth/text_page.py`。
- 禁止 `F9` 短语 / `SLT2`；全局只用 `F7 00 hi lo`。
- 禁止把 `win[0x0D]` 当 tile 背景（§3 实证红块根因）。
- 禁止整列写 0 透明（黑底根因）、禁止直接贴 font3 预渲染双色字模（彩条根因）。
- 禁止把 PCS 三色字模 ink-only 归一成 `fg/bg`（阴影层消失、菜单发灰）。
- 禁止给 `0xEF` 菜单光标恢复「固定 `0x1F0/0x1F1` tile 对」特判（光标消失根因）。
- 禁止回退 `0x0808ADB2` 的 P24 nop（图鉴名字读穿 → 纯红块 + 控制码乱码）。
- 禁止把 dex `0x1FD/0x1FE` 红块重新解释成「采集不同步」—— 已由 P24 前后
  110→0 纯红像素、128→0 左侧详情区差异像素、以及名字气泡视觉对照证伪。
