# hook/ 目录组织与命名规范

> 生效日期：2026-08-22。任何新增/移动/删除补丁文件前必读。
> 逐条补丁底账见 `docs/PATCHES_INVENTORY.md`（ID 体系来源）。

## 1. 目录总览

```
hook/
├── main.asm                  # 【骨架】只做装配，禁止再堆 .org 补丁
├── game_addrs.asm            # 【地址唯一事实来源】所有 equ 在此定义
├── patches/                  # 【纯值补丁】armips 就地改写，无 C 依赖
│   ├── player.asm            #    玩家名/性别
│   ├── player_pc.asm         #    PC 玩家名
│   ├── initialpoke.asm       #    P06 P09 P10 P11 P12 初始宠 label 整组
│   ├── pokedex.asm           #    P19~P23 图鉴名字列 ×5
│   ├── start_menu.asm        #    开始菜单
│   └── ui_pss.asm            #    P17 P18 PSS 图标列
├── src/                      # 【复杂钩子】gcc 编入 out/game.bin + armips 订址桩
│   ├── text/                 #    文本引擎域（收敛为三件套）
│   │   ├── entry.s           #      P01 跳板 EngineEntry（链接首位约束）
│   │   ├── hooks_origin.s    #      P01 订址桩（armips 侧，只 hook PrintNextChar）
│   │   └── PrintNextChar_hook.c  #  运行时全部逻辑：控制码 / 纯函数 tile 网格 /
│   │                             #  12px 逐像素合成 + GetStringWidth
│   ├── include/              #    game.h / text_grid.h（网格常量唯一契约）
│   │                         #    旧 text.h / text_render.h / text_scene.h 已删除
│   ├── map_name_popup/       #    P04 地名弹窗域三件套
│   │   ├── entry.s           #      跳板 MapName_DisplayCellLength
│   │   ├── MapNamePopup_hook.c
│   │   └── hooks_origin.s
│   ├── battle/               #    P03 池常量 + 复杂钩三件套
│   │   ├── hooks_origin.s    #      池字面量 0x04000008→0x04000006
│   │   ├── UpdateNickInHealthbox_entry.s
│   │   └── UpdateNickInHealthbox_hook.c
│   ├── pokedex/              #    P07 三件套
│   │   ├── hooks_origin.s
│   │   ├── UnusedPrintMonName_entry.s
│   │   └── UnusedPrintMonName_hook.c
│   └── option/               #    P08 三件套
│       ├── hooks_origin.s
│       ├── DrawOptionMenuChoice_entry.s
│       └── DrawOptionMenuChoice_hook.c
├── reference/                # 【2026-11-02 已删除】5 个 ref* 符号无调用者（原占约 8KB）
│                              #   旧绘制原语随 2026-11-11 串页重构一并删除
├── link/game.ld              # gcc 链接脚本（VMA 0x08800000）
├── gen/                      # 生成物：translated_slot.asm（流水线写，勿手改）
├── graphic/                  # 生成物：fonts.s + phrase_data（流水线写，勿手改）
├── out/                      # 生成物：game.bin / game.map / game_syms.asm（勿手改）
├── build.bat                 # 【权威】Windows 构建
└── Makefile                  # WSL 构建（2026-11-11 按 text 三件套 / 10 obj 重写，未实测）
```

## 2. 新补丁分类决策树

```
拿到一个新补丁，依次问：

Q1 需要用 C 写逻辑吗？（查表 / 协议解析 / 寄存器编组 / 超过 ~10 行算术）
 ├─ 是 →【复杂钩】三件套：
 │        src/{域}/hooks_origin.s          ← 加订址桩（.org + ldr/bx far-jump）
 │        src/{域}/{Name}_entry.s          ← gcc 跳板（保参数寄存器、回落原版）
 │        src/{域}/{Name}_hook.c           ← C 逻辑
 │   例：P07 UnusedPrintMonName、P08 DrawOptionMenuChoice
 │
 └─ 否 → 再问：是跳到某个已存在符号吗？
          ├─ 是 →【JMP 桩】src/{域}/hooks_origin.s 里加订址桩即可
          │   例：P04 地名弹窗居中（map_name_popup 域；跳板 MapName_DisplayCellLength，
          │       C 逻辑 MapNamePopup_hook.c 按引擎步进算留白、加大 MenuPrint x 起点）
          └─ 否 →【纯值】patches/{域名}.asm 里就地改写指令/数据
              例：P06 mov r2,#0x1D、P13~P15 NOP 组、P16 数据 FF
```

**判定口径**：改动是否只是「换了个立即数/换了几条无分支指令」？是 → 纯值；
只要出现「条件分支循环重写」「要查表」「要读窗口状态」→ 复杂钩。
拿不准时按复杂钩处理（可测试后再降级）。

## 3. 命名规则

### 3.1 C 函数命名（2026-08-25 起，全引擎强制）

| 场景 | 命名 | 例 |
|---|---|---|
| hook 官方函数，**原版实现**在自定义代码中被调用 | `XXX_Origin` | `InitWindowTileData_Origin`、`UpdateTilemap_Origin` |
| hook 官方函数，**自定义修改后替换**原版 | `XXX_Hook` | `PrintNextChar_Hook`、`InitWindowTileData_Hook` |
| **模仿官方函数**（来源 pokeruby / pokeemerald / pokefirered），仅内部使用 | 直接用官方名 | `UpdateTilemap`、`GetCursorTileNum`、`DrawGlyphTiles` |
| 项目自有逻辑（官方无对应物） | 官方风格命名，见名知义 | `BindPitchSlot`、`GlyphScratchBase` |

**禁止**：函数名出现 `_CHS` / `_EN` / `_I18N` 字样——本汉化目标是多语言汉化，
方法名直接跟随官方命名（如 `GetStringWidth`，而非 `GetStringWidth_CHS`）。
同理禁用 `chs_` 前缀与「bak 破方法名」回潮（`DrawGlyph_JP_ViaCHS` 类）。

### 3.2 目录与文件命名

| 对象 | 规则 | 例 |
|---|---|---|
| 域名（目录） | 固定枚举：`map_name_popup` / `battle` / `pokedex` / `option`；新域先在本文件登记（文本引擎本体在 `src/` 根：text.c + entry.s + hooks_origin.s） | `src/pokedex/` |
| 纯值补丁文件 | `patches/{域}_{对象}.asm`，小写下划线 | `ui_starter.asm` |
| 订址桩文件 | 固定名 `hooks_origin.s`，每域一个，不许拆散 | `src/battle/hooks_origin.s` |
| gcc 跳板/逻辑对 | `{Name}_entry.s` + `{Name}_hook.c` 同名成对（Name=官方函数名） | `UnusedPrintMonName_entry.s` / `UnusedPrintMonName_hook.c` |
| 补丁 ID | Pxx 顺序号，分配后永不复用；写在节头 `[Pxx]` | `[P24] xxx` |

> 文本引擎收敛后（2026-08-24）：引擎入口跳板上移为 `src/entry.s`、订址桩为
> `src/hooks_origin.s`，与 `src/text.c` 同级；旧多文件引擎归档于 `src/bak/text/`
> （只读历史，不参与构建）。
> **新的复杂钩一律走 `{Name}_entry.s` 成对模式**。

## 4. 补丁节头模板（patches/ 与 hooks_origin.s 通用）

```asm
; -----------------------------------------------------------------------------
; [P24] 一句话标题                              status: KEEP | TENTATIVE
; pokeruby: src/xxx.c Symbol()（对应美版位置）
; 原版@0x0800XXXX: bl 0x0800436C（被替换的原版指令）
; 动机: 为什么打这个补丁（关联 bug 现象/crash 地址）
; 回滚: 删除本节即恢复原版
; -----------------------------------------------------------------------------
.org <addr>
    ...
```

要求：
1. 每个 ID 分配后登记进 `docs/PATCHES_INVENTORY.md` 对应分组表；
2. 「原版指令」必须写（未来做 baserom 自动校验的数据源）；
3. 同一事务的多处改动（如初始宠 label 四处）合用一个 ID，放同一个文件同一节。

## 5. 注释风格（⚠️ 血泪坑）

| 文件类型 | 注释符 | 原因 |
|---|---|---|
| `patches/*.asm`、`src/*/hooks_origin.s`（armips） | **只用 `;`** | armips 遇到 `@` 行注释会**静默崩溃 exit=9 且零输出**，不报错 |
| `src/**/*.s`（gcc/GNU as） | `@` 或 `;` 均可 | GNU as 正常处理 |

## 6. 地址与符号纪律

1. 新地址一律先进 `game_addrs.asm`（带一行用途注释），补丁里只引用 equ，
   禁止裸写十六进制（历史遗留除外，重构时顺手收编）；
2. 需要从 C 回填给 armips 的符号，必须同时在两处登记提取规则：
   `build.bat`（findstr + echo）和 `Makefile`（grep + printf），两边列表保持一致；
3. `out/game_syms.asm` 是生成物，勿手改；
4. **美版符号 ≠ 日版存在**：proximity 换算（含 jp.sym 的 UNVERIFIED 链）必须
   反汇编验证行为后才可订址。案例（2026-08-22）：GetGlyphWidth/GetStringWidth
   在 AXVJ 根本未编译——打印步进由 FontFuncTable 各处理器硬编码、全 ROM 无
   FC 控制码 switch / cmp#0x16 特征；game_addrs 曾错标 0x08004228（实为
   {u32,u32} 表查映射）与 0x08004530（实为 FA~FF 字符串展开复制）。两个宽度钩
   （GetGlyphWidthHook / GetStringWidthChinese）已随死代码移除（2026-08-22），
   中文宽度由 PrintNextChar_C 自管，详见 game_addrs.asm「String util」节注释。

## 7. 构建顺序与联动

```
改 C/hook.c ──► build.bat ──► out/game.bin + out/game_syms.asm
                                     │ syms 地址可能变化
改 asm 补丁 ─────────────────────────┤
                                     ▼
              meowth 流水线（font_patch.apply_font_patch）
                     ├─ 复制 hook/ → work/{game}/build/
                     ├─ 复制 charmap.txt 到 staging 根
                     ├─ 生成 graphic/fonts.s + phrase_data.asm
                     ├─ 生成 gen/translated_slot.asm
                     └─ armips main.asm ──► output.gba
```

- **game.bin 重编后必须重跑 armips**（syms 回填变了）；
- **不要 `cd hook && armips main.asm`**：`main.asm` 的 `./charmap.txt`、
  `./graphic/fonts.s`、`./gen/translated_slot.asm` 只在流水线 staging 目录里齐全，
  原地跑必然报 `does not exist`。单独验证汇编层请用完整打包命令（见 `docs/PACK_ROM.md`）。
- **`build.bat` 是权威构建脚本**（Windows）。`Makefile` 与 `build.bat` 的
  **10 个 obj** 顺序逐项对齐（2026-11-11 串页重构后：text 域只剩
  `text_entry.o` + `PrintNextChar_hook.o`，旧三个 .c 已删除）。
  构建期**零页表**：字库由 `font_patch` 装入 `0x09000000`，运行时直接按
  `gidx` 取 128B 字模；`engine.run_full()` 不再后置烙入 `0x09500000`。
  串页方案（4.4MB 页表 / PHYS 288 对）因页池盖住原版场景图块已整体退役，
  见 `docs/DESIGN_TEXT_12PX_GRID.md`。
- **可选运行时诊断**：`set EXTRA_CFLAGS=-DGRID_DIAG && build.bat` 会把每个字的
  `phase/col/t0/fg/bg/win[0x0D]/tpl[6]` 写进 EWRAM `0x0203E000` 环形区；
  bot 的 `NNN.ram.bin` 偏移 `+0x3E000` 可离线解码。产品构建不带此宏。
  当前环境未装 WSL，`Makefile` 尚未实测——首次使用请先核对产物
  `game.bin` 大小/符号（`EngineEntry` 必须等于 `0x08800000`）。
- WSL 构建（待实测）：先 `scripts/wsl-interop-setup.sh`（binfmt 注册），然后
  `PATH="$REPO/tools/wsl-bin:$PATH" make`；包装器内置 `</dev/null`
  （Windows 控制台 exe 在此环境不重定向 stdin 会永久阻塞）。

## 8. 禁止事项

1. ❌ 往 `main.asm` 加 `.org` 补丁——它只允许出现 include 与 incbin；
2. ❌ 在 `hook/` 目录内跑翻译管线——会在本地生成 `work/` 递归嵌套垃圾
   （现存一棵待清理，别再添新的）；staging 由管线统一写到 `work/{游戏ID}/build/`；
3. ❌ 手改 `out/`、`gen/` 下任何生成物；
4. ❌ armips 侧文件使用 `@` 注释（见 §5）；
5. ❌ 裸写新十六进制地址（见 §6.1）；
6. ❌ 删除补丁不走「删整节 + 更新 PATCHES_INVENTORY.md 状态」流程——
   底账与实物必须一致，否则下次盘点又是考古。

## 9. 新增补丁标准流程（checklist）

```
[ ] 1. 反汇编确认原版指令，拍下「原版字节」
[ ] 2. 按 §2 决策树定层，确定归属文件
[ ] 3. 分配 Pxx ID，docs/PATCHES_INVENTORY.md 登记行
[ ] 4. 写节头（§4 模板）+ 补丁体；新地址先入 game_addrs.asm
[ ] 5. 若新增 game.bin 导出符号：同步 build.bat + Makefile 的 syms 列表
[ ] 6. 构建：game.bin（如动了 C）→ armips → 模拟器冒烟
[ ] 7. 校验：订址桩字面量 == syms 地址（可临时 dump 或用调试器确认）
```

## 10. 文本引擎：原生分区实测与 CHS 绘制移植设计（2026-08-25）

> 数据来源：gdb_patcher 采集 `InitWindowTileData`（入口 0x08002A50 / 出口 0x08002AEA，
> 均与美版同址，fontNum 跳表 7 项实证）+ `InitTextPrinter`，原盘 ROM，
> 覆盖场景：对话/开始菜单/队伍/图鉴/能力技能页/地图弹窗。日志 20514 行。

### 10.1 实测事实

| # | 事实 | 证据 |
|---|---|---|
| F1 | **tm1 窗（textMode=1）场景进入时把整个字库分帧预渲染**：256 字模 × 2 tile = 512 tile，startOffset 恒 1 → **恰好铺满整个 charBase**（[1,0x201)） | 每模板恰好 256 次命中（r2=字模序号 0..255 逐帧递增，每次 1 字模=2 tile）；弹窗 3 次进入=768 命中 |
| F2 | 预渲染按窗体模板逐份进行，实测 5 份：`081BB874`（对话,cb0）、`081BB5BC`（cb2）、`081BB49C`（弹窗,cb0,×3）、`081BB43C`（队伍,cb1）、`081BB484`（cb2,采集截断） | IWTD r0 分布 |
| F3 | **tm3 窗（`081BB46C`，开始菜单，470 次 ITP）不预渲染** → tm3 = 逐字原地像素绘制（FontFuncTable[3] @0x08003494 另一策略） | IWTD 无该模板 |
| F4 | 场景图标 = 字库预渲染**之后**盖进的章（覆盖对应字模槽）：队伍 Lv/♂/♀ = 0x14C-0x151、状态 = 0x18C-0x19B（原生 `PartyMenuWriteTilemap` 直写 VRAM） | pokeruby party_menu.c + 队伍截图对照 |
| F5 | 出口 r0 = 0x08002AAB（函数内返回地址残留）→ 分帧加载器返回值无意义，加载进度由调用方的 r2 序号承载 | IWTD-Ret 恒值 |
| F6 | 全部窗体 TILE_BASE=1（1586 条 ITP 实证） | gdb 日志 |
| F7 | **能力页场景自加载字库**：LZ77 → 0x06008000，dst_size=0x2000（8KB = tile [0x00,0x100)），**不走 InitWindowTileData**（081BB544/081BB784 有 ITP 无 IWTD 的原因）——场景字库与 font3 预渲染是两套互斥机制，按场景二选一 | 第二轮采集 LZDecompressVram LR=0x0800AE4E |
| F8 | **能力页场景映射 [0x1C9,0x1F7]**（win=0x0202E5DC，LR=0x080034DA）——场景在 charBase 2 尾部映射自己的图形槽 | 原生 UTM 51 条明细 |
| F9 | **队伍窗原生数字映射 [0x74,0xD5]**（u=0xD5 恒定 + l=0x74-0x9A，LR=0x080035C0）——cb1 池 [0xD7,0x14B] 恰好避开（0xD5<0xD7，队伍页实测通过） | 原生 UTM 明细 |
| F10 | 原生代码确实会走 UpdateTilemap（共 51 条，LR 三类：0x080035C0 队伍数字 / 0x08003EB2 光标 0xBA-0xBB / 0x080034DA 能力页）——「场景章」不止直写 VRAM 一种 | UTM 调用方分布（C引擎 1306 / 原生 51） |

### 10.2 原生绘制架构结论

```
tm1（等宽）: 场景进入 → InitWindowTileData 分帧预渲染字库（512 tile 铺满 charBase）
            → 打印 = 写表项映射字库槽（font3 线性 2*glyph / font4 FontType1Map 紧凑表）
            → 零像素绘制；场景图标章在字库槽之上
tm3（菜单）: 无预渲染；逐字原地像素画（FontFuncTable[3]）
tm0:        原地画 + 表项（pokeruby DrawGlyph_TextMode0 同构）
分区方式:    无分配器——场景代码硬编码分区（字库区=全 charBase，图标章踩字库保留槽）
```

**推论**：tm1 窗的 charBase 里**不存在**原生预留的 CHS scratch 空间——CHS 必须
与字库/图标章**槽位共存**。任何"全局游标池"都与多窗多块并发互斥（能力页/图鉴
乱码根因），必须废除。

### 10.3 CHS 绘制移植设计（pokeruby 结构 + 槽位分区表）

**目标结构**（全部按 §3.1 命名；2026-08-25 深夜定稿 = **页游标制**）：

```
PrintNextChar_Hook            # 入口（hooks_origin.s 用 game_addrs equ 不受改名影响）
 ├─ GetGlyph                  # 取字模（不变）
 ├─ 两级 PCS 分发表            # (1,4)=PrintGlyph_TextMode1_Origin（保留，实测✓）
 └─ PrintGlyph_TextMode1      # CHS/自绘
     ├─ GlyphScratchRange     # 自由区表（cb0/cb1/cb2，§10.4）
     ├─ GlyphPageCur          # 页游标表：{u16 tilemap_lo, u16 cursor}×8
     │                        #   @0x0203FFD2（扫描实证无游戏引用）
     │                        #   同页块顺序 disjoint；异页互斥显示共享区间
     ├─ DrawGlyphTiles 几何   # 两趟 8+(w-8)（不变）
     └─ WriteGlyphTilemap     # 不变
InitWindowTileData_Hook       # 预留未实现（新场景分区收口时再加）
InitWindowTileData_Origin     # 预留未实现
```

**页游标制 vs 早期方案**：曾先后设计过「全局池」「charBase 水位线」「LRU 回收」，
仿真全部复现互踩/回绕踩（能力页 3 窗体×4 块=288 tile > 201 自由区）。
**根因是粒度错误**：能力/技能/情报页 = 同 charBase 的 3 个不同 tilemap（互斥显示），
按 charBase 记账会把互斥页当并发页挤在一起。**按 tilemap 记账后**：
- 同页块顺序 disjoint（页容量 = 自由区 201 tile ≈ 50 字/页，实测每页 ≤96 ✓）
- 异页共享区间互相覆盖——不可见，无害；页重入游戏重印 → 重绘自愈
- 仿真：3 窗体×4 块 + 页重入重绘 = 零重叠、幂等 ✓

### 10.4 场景盖章槽位表（实测 2026-08-25 第二轮，含能力页）

| charBase | 已实测占用（不可碰） | 自由区（CHS 可用） | 依据 |
|---|---|---|---|
| 1（队伍 font4） | font4 区 [2,0xD6]；**原生数字映射 [0x74,0xD5]**；图标章 [0x14C-0x151]；状态章 [0x18C-0x19B] | **[0xD7,0x14B]**（117 tile ≈ 29 字） | F4/F8/F9；队伍页实测通过 |
| 2（font3 菜单/对话/图鉴/**能力页**） | **能力页自加载字库 [0x00,0x100)**（F7）；**能力页映射 [0x1C9,0x1F7]**（F8）；▶对 [0x1E0-0x1E1]；UI 图标 [0x1E8-0x1FF]；font3 预渲染 [1,0x201)（菜单/对话场景，无原生映射=可覆写） | **[0x100,0x1C8]**（201 tile ≈ 50 字，各场景公共自由区） | F7/F8 + 两轮 UTM 落点分布 |
| 0（弹窗/对话 font3） | 地图 tileset 共存关系未明（LZ→0x06000000 ×11） | 现池 [0x101,0x1AB] 实测正常，暂不动 | 弹窗 3 次进入均全量 blit |

> ⚠️ cb2 自由区 [0x100,0x1C8] 容量 50 字/屏：对话满 3 行（~54 字）会回绕踩本屏
> 前 4 字——对话场景 font3 全区无章，若实测出现可按场景放宽（能力页才需要让出
> [0x00,0x100)）。根治见 §10.5 位置式寻址。

### 10.5 pokeruby 逻辑能否避开这些 bug？（结构分析）

| bug 类 | 实例 | pokeruby 结构下 |
|---|---|---|
| 全局游标踩踏 | 图鉴名称碎片、跨窗跨块互踩、能力页文本碎片 | **结构上不可能**：无全局分配器，tile 位置由窗体自有 cursor 字段决定（位置式寻址） |
| 场景硬编码章被踩 | 队伍图标（池踩 0x14C-0x151）、能力页字库/映射（池踩 [0x00,0x100)/[0x1C9,0x1F7]） | **美版能**（章=场景 C 代码，编译进场景逻辑自洽）；**JP 必须用声明式槽位表替代**——JP 场景无源码，章的位置只能 gdb 实测积累 |

**结论**：pokeruby 路线 = ①位置式寻址（结构根治第一类）+ ②场景章表（第二类
的唯一解，表是 JP 场景分区的实测描述，不是补丁）。表的每一行都有 gdb 证据链
（本节 F1-F10），新场景出乱码 = 表缺一行，补一行即收口。

### 10.8 参考汉化版实测（2026-11-03）

改字号前先看成熟汉化版怎么排的，别凭空定数。实测对象：
`roms/translated/宝可梦火红日版汉化2.2.gba`（火红汉化 2.2）。

**正文汉字实测**（帮助页「首先，进行游戏的操作以及所分配的按键说明。」，
纯净白字蓝底，无抗锯齿干扰）：

| 指标 | 实测值 |
|---|---|
| 汉字墨迹宽 | **12px**（多数，个别 11） |
| 字起点间距（步进） | **13px** |
| 字高 | 12px |
| 行距 | 15px |
| 标点 | 3px 窄符 |

对照本工程：Normal `ink=11x11` / `advance=12`；火红是 `ink=12x12` / `advance=13`。
**成熟实现的规律是 `advance = ink_w + 1`**（12→13，11→12），本工程正好符合。
这说明「步进必须等于墨迹宽」是错的（那样 12px 字挤在一起），
`advance = ink_w + 1` 才留得出 1px 字距。

> ⚠️ **队伍小字（fontNum=4）仍未实测**：手头的火红 `.sav`
> （`roms/translated/宝可梦火红日版汉化2.2.sav`，2026-11-03 提供）经解析
> **只有 SaveBlock2 两组副本、缺 SaveBlock1**，游戏读档后停在「操作说明」帮助页，
> 进不了队伍。`savlib.rebuild()` 报 `missing_sectors` 含 14–31 就是这个原因。
> 需要一个**含 SaveBlock1** 的完整存档（进游戏能走能按 START）。
> 校验：两组扇区内容不能都是「玩家名开头」的 SaveBlock2。

### 10.7 三档字库（2026-11-02）与两条必守铁律

字库来源唯一：`configs/{game}/fonts/{normal,middle,small}.bdf`；四套槽位由
`translate/font.config.json` 的 `font_slots[].bdf` / `[].ink` 逐槽指定。

| 槽位 | 地址 | BDF | 墨迹 | 步进 | 使用者 |
|---|---|---|---|---|---|
| Normal | `0x09000000` | normal.bdf | 11×11 | 12 | 对话/菜单/摘要 |
| Middle | `0x09320000` | middle.bdf | 9×11 | 12 | 备用第 4 套 |
| Small  | `0x09100000` | small.bdf | 9×9 | 9 | 队伍名/战斗名（`fontId==4`） |
| Sym    | `0x091E0000` | normal.bdf | 11×11 | — | 标点 |

**铁律 1 —— 半字节顺序必须是 lo-first。**
`pack_slot16_4bpp(lo_first=True)`：左像素占**低** 4 位。旧 `*_unshadow` bin 是这个
布局，hook 的 `DrawGlyphTile_refpr` / `CopyGlyph2bppTo4bpp_Origin` 也按它读。
若误用 hi-first（primary 布局），墨迹整体横移半像素 → **重影**（title_menu 实测
每个字都叠一层）。`build_chinese_font.py --nibble-order` 默认已是 `lo-first`。

**铁律 2 —— 步进 ≥ 墨迹宽度，且尽量与 8px 栅格同周期。**
`DrawGlyphTiles_common` 用 `expect = base_tx + ((chs_px + last_adv - 1) >> 3)`
反推游标；步进与 8 的关系决定相位稳定性。
- 步进 **< 墨迹宽** → 相邻字重叠（Small 曾用 8 而墨迹 9 → 队伍名糊成一片）；
- 步进 **11**（与 8 无稳定周期）→ 相位逐字漂移、反复重锚 → 字粘连成一条
  （start_menu 实测墨块由 `[11,11]` 退化为 `[28]`）。
- 现行：Normal/Middle 12（12%8=4 二相稳定），Small 9（9%8=1，仅短名用，可接受）。

改字体尺寸时**只改** `font.config.json` 的 `ink`，步进在
`GetChineseFontWidthFunc` 与 `game.h` 的 `CHS_GLYPH_ADVANCE_PX` 两处同步。

### 10.6 实施顺序（2026-08-25 深夜定稿；P24 已撤销）

0. ✓ cb2 自由区 [0x100,0x1C8]（并入 `GlyphScratchRange`）
1. ✓ 改名（§3.1 全表，entry.s / map_name_popup 同步）
2. ✓ **页游标制**：`GlyphScratchRange` + `GlyphPageCur`（页游标表 @0x0203FFD2，
   按 tilemap 低 16 位记账）+ `GlyphScratchAlloc`（槽记 `scratch_tx`/`tiles_drawn`，
   重绘幂等）；删 `AllocGlyphTiles`/`MONO_TILE_NEXT`/共享列 hack/`PcsPrint_NativeTm1`；
   struct 位域重排 8B 零迁移
3. ✓ 场景章由自由区表编码；新场景出乱码 = §10.4 表补一行
4. ~~✓ **P24 已实装**~~ → ❌ **2026-08-25 已撤销**：页游标表落 `0x0203FFD2`
   撞游戏数据区，导致背包/队伍死机（PC=0x00000004 实证）。`src/text/hook_origin.s`
   的 P24 桩、`src/text/entry.s` 的 `GlyphIwtdTramp` 均已删除；`0x08002A50`
   在成品 ROM 中保持原版 `70 b5 82 b0 04 1c…`。`game_addrs.asm` 的
   `InitWindowTileData` equ 与 `game.h` 的 `ADDR_INIT_WINDOW_TILE_DATA` 仅作文档参考，
   **不再订址**。ID 永不复用。
   > 结论：页游标「跨场景累积」问题未根治，当前靠「同页块顺序 disjoint +
   > 页重入重印自愈」兜底。
5. 待回归六场景：队伍（HP标签/♂/铁哑铃）、图鉴、能力↔技能页、弹窗、对话、开始菜单
