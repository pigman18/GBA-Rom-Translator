# AXVJ main.asm 补丁盘点（POKEMON_RUBY_AXVJ00）

> 快照时间：2026-08-21 23:53（用户回滚后版本）。
> 目录/命名规则见 `configs/POKEMON_RUBY_AXVJ00/hook/README.md`（新增补丁前必读）。
> 范围：`configs/POKEMON_RUBY_AXVJ00/hook/main.asm` 全部 `.org` 补丁 + 装配结构。
> 用途：后续拆分/移除/重构的决策底账。每条补丁有唯一 ID（Pxx），拆分与删除操作以 ID 为单位。

---

## 0. 装配结构（非补丁，main.asm 骨架）

| 行 | 内容 | 说明 |
|---|---|---|
| 头部 | `.gba/.thumb/.loadtable charmap.txt` | armips 环境 |
| `.open baserom.gba→output.gba` | ROM 打开 | 输出 32MB（SlotTable @0x09EA0000 撑大） |
| `.include game_addrs.asm` | **地址唯一事实来源** | 所有 equ 在此 |
| `.include out/game_syms.asm` | gcc 符号回填 | 由 build.bat/Makefile 从 game.map 提取 |
| `.org GameBinAddresses` + `.incbin out/game.bin` | **C 文本引擎装载** @0x08800000 | gcc 产物，入口符号 PrintNextChar_C |
| `.include graphic/fonts.s` | CHS 字库写入 0x09000000/0x091E0000 | pipeline 生成 |
| `.include gen/translated_slot.asm` | slot 查找表 @0x09EA0000 | **已废**：只剩空表桩（256 桶全空），待删 |

## 1. 补丁清单（按地址排序）

类型：**JMP**=订址跳板 / **INS**=指令替换 / **NOP** / **DATA**=数据改写

### A. 文本引擎钩子（必须常驻，互相依赖 game.bin 内部布局）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P01 | `0x080032F8` | `ldr r1,=(JP2CHS_Entry\|1); bx r1`（6B+pool，r0=win 原样进 C） | JMP | **全面接管**（Phase C 换装）：原生 PrintNextChar 整函数替换——FA-FF 控制码 + FC 子类型 1-16 + EF/F9/slot/可印字形全由引擎消化，零回落 FontFunc；返回值契约 docs/ruby_jp_text.md §六A。2026-08-24 收敛后为文本域唯一 ROM hook（P02/P05 移除、P05 折入本钩 FA/FB 分支）；入口跳板=`hook/src/entry.s` EngineEntry | `src/text.c` `PrintNextChar()`（AXVJ 同名函数入口；引擎=`hook/src/text.c`） |
| ~~P02~~ | `0x08003730` | （已移除 2026-08-24）原：`push {r4}; ldr r4,=(GetGlyphTilePointers_Hook\|1); bx r4` | ~~JMP~~ | **已移除**（只 hook PrintNextChar 收敛）：CHS 字模取址收归 `text.c` 内部 `static GetGlyphTilePointers`；原生函数恢复原样由 `chs_get_glyph_tile_pointers` 直调。ID 永不复用 | `src/text.c` `GetGlyphTilePointers()`（美版多 language 参数，日版 4 参） |
| ~~P05~~ | `0x08003F4C` | （已移除 2026-08-24）原：`ldr r3,=(WaitArrow_Prepare_Hook\|1); bx r3` 回落主体 `0x08003DAD` | ~~JMP~~ | **已移除并折入 P01**：相位同步逻辑进 `text.c static DrawInitialDownArrow`（pokeruby 同名），FA/FB 分支直调；反汇编实证原生包装 ≡ `win[6]=0 + 尾调 0x08003DAC`，等价成立。ID 永不复用 | `src/text.c` FA/FB 等 A 箭头绘制段（DrawInitialDownArrow 同名折入） |
| ~~P24~~ | `0x08002A50` | （**2026-08-25 已移除**，ROM 该址保持原版 `70 b5 82 b0 04 1c…`） | ~~JMP~~ | **已移除**：页游标表落 `0x0203FFD2` 撞游戏数据区 → 背包/队伍死机（PC=0x00000004 实证）。`entry.s` 的 `GlyphIwtdTramp` 与 `src/text/hook_origin.s` 桩同步删除；`game_addrs.asm` 的 `InitWindowTileData` equ 仅作文档参考、**不再订址**。ID 永不复用。原设计（供考古）：**InitWindowTileData 页游标复位**：多帧字库加载 worker（gdb 采集 2656 命中实证 JP=US 同址）入口改跳 entry.s GlyphIwtdTramp 跳板——保存全现场、调 text.c InitWindowTileData_Hook（复位该 tilemap 的 CHS 页游标：窗体初始化=旧文本作废，跨场景累积清零，修能力/技能/开始菜单回绕互踩）、恢复现场、重执行被覆盖的 4 条 prologue、落回 0x2A58 原函数体（字库加载不受影响）。ARMv4T 远调用惯用法（mov lr,pc+bx，无 blx） | src/text.c InitWindowTileData()（AXVJ 同址同构，256 字模分帧加载） |

### B. 战斗

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P03 | `0x08042C38` / `0x08041760` / `0x08042620` | 字面量池 `0x04000008→0x04000006`（4B×3，armips include `src/battle/UpdateNickInHealthbox_hook_origin.s`） | DATA | HP 条昵称遮罩 CpuSet 32B→24B，避免盖掉 10/12px 汉字上半 | `src/battle_interface.c` `UpdateNickInHealthbox()` 共享字面量池 |

### C. 地图名弹窗旁路（结构性绕过——GetStringWidth 无法替代，见 §3 说明）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P04 | `0x0809F67E` | `ldr r3,=(MapName_DisplayCellLength\|1); bx r3`（只用 r3 转跳）；跳板在 `src/map_name_popup/entry.s`，C 钩 `MapNamePopup_hook.c` 返回留白格数、注入 `r1=1+留白` | JMP | 跳过 `StringLength→右对齐 pad→二次 GetMapName(fill=10)`。⚠️ 该路径用**字节长度**与硬编码 10 格右对齐：内联 F9 地名 >10 字节时 `10-len` 下溢至 ~0xFFFE → 野写 + 65534 次清零循环（模拟器报 0xA2A2F6A4 类飞 PC 的根因）。2026-08-24 起独立为 map_name_popup 域三件套 | `src/map_name_popup.c` `DrawMapNamePopup()`；GetMapName 见 `strings.c` |

### D. UI 布局微调（指令级小改）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P06 | `0x081053D0` | `mov r2,#0x1D`（原 `adds r2,#8`，2B） | INS | 初始宠 label 擦除右边界 left+8→固定 29 列，修中文名残留碎字 | `src/starter_choose.c` `CreateStarterPokemonLabel()` |
| P09 | `0x081053B2` | `sub sp,0x60`（原 0x20，2B） | INS | B06：label 栈帧扩容（两行 buffer 隔离） | 同上 |
| P10 | `0x08105416` | `add r1,sp,0x30`（原 0x10，2B） | INS | 第二行 buffer 移位 | 同上 |
| P11 | `0x0810551C` | `add sp,0x60`（2B） | INS | 配对还原栈 | 同上 |
| P12 | `0x0810544C` | 拷贝循环重写 26B（固定拷 5B→拷到 0xFF、上限 0x11） | INS | 「ポケモン」→「宝可梦」F9 序列完整落盘，修乱码+名字重复 | 同上 |
| P17 | `0x0809D60C` | `mov r1,#0x17`（原 0x18，2B） | INS | PSS 右上角 B 图标左移一列（防中文反向增长踩图标） | `src/pokemon_summary_screen.c` 头部图标布局（AXVJ 符号 PrintSummaryWindowHeaderText @0x0809D5D4） |
| P18 | `0x0809D616` | `mov r1,#0x18`（原 0x19，2B） | INS | 同上第二个图标 | 同上 |
| P19~P23 | `0x0808AA00` `0x0808AA24` `0x0808AB34` `0x0808ABDA` `0x0808ABFE` | `mov r1,#DEX_NAME_COLUMN`(0x16，原 0x17，各 2B) | INS | 图鉴列表页名字列间距（NoXXX 与名字） | `src/pokedex.c` 列表页 `CreateMonName` 列坐标（5 处共用常量） |

### E. 菜单/图鉴逻辑钩子（C 层拼流后委托官方 Menu_PrintText）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P07 | `0x0808DD60` | `ldr r3,=(UnusedPrintMonName_Hook\|1); bx r3`（4B+pool） | JMP | 图鉴条目屏分类名行：拼接分类+宝可梦短语流一次性打印 | `src/pokedex.c` 条目页分类名行打印（美版为静态函数，AXVJ 自命名 UnusedPrintMonName） |
| P08 | `0x080889F0` | `push {r3}; ldr r3,=(DrawOptionMenuChoice_Hook\|1); bx r3`（6B+pool） | JMP | 设置窗口选项高亮：改为调色板/前景色覆盖变量 | `src/option.c` `DrawOptionMenuChoice()` |

### F. 数据清理（置空日文残留）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P13 | `0x08090EF0` | `bl AppendZhi_R0` | JMP | 图鉴计数后追加「只」（`.strn`） | ConvertIntToFullwidth 后缀 |
| P14 | `0x08090F3C` | 同上 | JMP | 同上 | 同上 |
| P15 | `0x08090FAA` | `bl AppendZhi_R4` | JMP | 同上（R4 游标） | 同上 |
| P16 | `0x080077A0`→`SuffixGe`；`0x081BC164` 置空 | `.strn "个$"` | DATA | 徽章后缀「个」 | 原「こ」静态串 |

## 2. 被 C 层直接调用的官方函数（不在 main.asm，但同属依赖面）

| 官方地址 | AXVJ 符号 | pokeruby 对应 | C 层调用者 |
|---|---|---|---|
| `0x08003730` | GetGlyphTilePointers | text/ 同名 | `text_render.c` 内取址（JP 字模） |
| `0x08003830` / `0x080038A0` | CopyGlyph1bppTo4bpp / CopyGlyph2bppTo4bpp | text/ 同名辅助 | 颜色重映射 |
| `0x080036DC` | UpdateTilemap | text/ tilemap 更新 | `text_render.c` |
| `0x0806F16C` | Menu_PrintText | `src/menu.c` Menu_PrintText | option/dex hook 组串后委托 |
| `0x0800436C` | StringLength | `src/string_util.c` | （弹窗原路径用） |
| `0x08004228` / `0x08004530` | ~~GetGlyphWidth / GetStringWidth~~ | — | ⚠️ **AXVJ 无此二函数，已定论不再订址**（2026-08-22）：`0x08004228` 实为 `{u32,u32}` 表查映射（表@0x081BB8D4，6 callers）；`0x08004530` 实为 FA~FF 控制码字符串展开复制（125 callers）。日版步进由 FontFuncTable 各处理器硬编码。美版 US=0x080048E8/0x08004BCC。 |
| `0x081BB3AC` / `0x081B12DC` | FontFuncTable / CallViaR2 | lib 工具段 | PrintNextChar 回落官方 FontFunc |
| `0x081B1294` | CpuSet | crt0/lib 工具段 | 血条遮罩（池常量被 P03 改短） |

## 3. 关键结论（影响后续去留决策）

1. **P04 不能靠 GetStringWidth 替代**：弹窗路径不查像素宽度，用的是 `StringLength` 字节数 + 硬编码 10 格右对齐；中文内联 F9 地名普遍 13~17 字节 > 10 → `10-len` 下溢 → `sp+0xFFFE` 野写 + 65534 次清零（本次 0xA2A2F6A4 飞 PC 的根因）。要么保留 P04 旁路，要么重构原版逻辑本身。
2. **P01 单钩自洽**（2026-08-24 起；P02 移除、P05 折入，见上表）：依赖 game.bin 内部符号布局（经 game_syms.asm 回填）。任何 game.bin 重编后必须同步重跑 armips。
3. **P09~P12 是同一事务**：初始宠 label 四处改动必须同时存在，拆分时归并为一节。
4. **P19~P23 共用一个常量**：DEX_NAME_COLUMN 定义在 game_addrs.asm，改值即可全局调整。
5. 死代码：旧引擎死代码 GetGlyphWidthHook / GetStringWidthChinese 已随 2026-08-24 收敛彻底消失（text.c 内部化后 nm 无残留）；现存 HealthboxNickCpuset*（仅导出常量，占 game.bin 空间不影响运行）。

## 4. 已实施的拆分结构（2026-08-22；2026-11-02 校正为现状）

> 实际结构以 `configs/POKEMON_RUBY_AXVJ00/hook/README.md` §1 为准（本节已同步）。
> 文本引擎已由单文件 `src/text.c` 拆为 `src/text/` 四文件（2026-08-24 收敛）。

```
hook/
├── main.asm                        # 纯装配骨架：open/include 清单/game.bin/fonts/slot 表
├── game_addrs.asm                  # 纯 equ 唯一来源（未动）
├── build.bat                       # Windows 构建（权威）
├── Makefile                        # WSL 构建（⚠️ 源清单过时，见 §4 末尾说明）
├── patches/                        # 【纯值补丁】就地指令/数据改写，无 C 依赖
│   ├── player.asm                  #   玩家名/性别
│   ├── player_pc.asm               #   PC 玩家名
│   ├── initialpoke.asm             # P06 P09 P10 P11 P12（初始宠 label 整组）
│   ├── pokedex.asm                 # P19~P23（图鉴名字列 ×5）
│   ├── start_menu.asm              #   开始菜单
│   └── ui_pss.asm                  # P17 P18（PSS 图标列）
├── reference/                      # 官方 pokeruby/pokeemerald 移植件（参与 gcc）
└── src/
    ├── text/                       # 【文本引擎域】
    │   ├── entry.s                 #   P01 跳板（EngineEntry，链接首位 = game.bin 起点）
    │   ├── hook_origin.s           #   P01 订址桩（只 hook PrintNextChar）
    │   ├── PrintNextChar_hook.c    #   引擎主体
    │   ├── text_translter.c        #   F7 协议层
    │   ├── text_render.c           #   共享绘制原语（GlyphScratchRange/页游标）
    │   └── text_scene.c            #   场景布局闸
    ├── map_name_popup/             # P04 三件套（entry.s / MapNamePopup_hook.c / hooks_origin.s）
    ├── battle/                     # P03 池常量 + UpdateNickInHealthbox_{entry.s,_hook.c}
    ├── pokedex/                    # P07 + UnusedPrintMonName_{entry.s,_hook.c}
    └── option/                     # P08 + DrawOptionMenuChoice_{entry.s,_hook.c}
```

分层规则：
- **纯值**（改指令/数据，无逻辑）→ `patches/{类名}.asm`
- **复杂钩**（需要 C 逻辑/寄存器编组）→ `src/{域}/{Name}_entry.s` 钉跳板 + `src/{域}/{Name}_hook.c` 逻辑，
  ROM 侧订址桩统一放 `src/{域}/hooks_origin.s`（armips include，不进 gcc）

> ⚠️ **`Makefile` 当前不可用**：其 `OBJS` 仍引用 `src/text.c`、`src/chinese_text.c`、
> `src/text_translate.c`（均已不存在）与 `src/entry.s`（已移入 `src/text/`）。
> 在补齐为新四文件结构前，构建一律以 **`build.bat`** 为准（该脚本的 6 个漏编 obj 已于
> 2026-11-02 修复，实测 `game.bin` 15452B 构建通过）。

### 已验证（2026-11-02 在原版 AXVJ 上重测）

| 项 | 结果 |
|---|---|
| 订址点原版字节 | 16 处逐一核对通过（PrintNextChar `10 b5 04 1c…`、InitWindowTileData `70 b5 82 b0…`、P04 `64 f7 75 fe…` 等） |
| FontFuncTable 7 项 | `08003569 / 0800360D / 0800338D / 08003495 / 08003585 / 080035A1 / 080035C9`，与文档一致 |
| `build.bat` 全量编译 | 15 个 obj 全过，`out/game.bin` 15452B |
| 成品 ROM hook 落地 | P01/P04/P07/P08 桩全部命中；P03 三池 `0x04000006`；`game.bin` 嵌入一致 |
| PhraseOffsets 位宽 | u32 单调递增（`0x0 / 0x9 / 0x12 / 0x1b`），符合 DONT#12 |

### 踩坑记录（重要）

1. **armips 不认 GNU as 的 `@` 行注释**——且不是报错，是**静默崩溃 exit=9 无任何输出**。
   armips 侧文件注释一律用 `;`；`@` 只允许出现在 gcc 汇编（GNU as）文件里。
2. **armips 不能在 `hook/` 原地跑**：`main.asm` 的 `.loadtable "./charmap.txt"` 与
   `.include "./graphic/fonts.s"`、`.include "./gen/translated_slot.asm"` 都依赖
   `font_patch.apply_font_patch()` 组装出的 staging 目录（`work/{game}/build/`），
   由它复制 charmap、生成 fonts.s、落 phrase_data。直接 `cd hook && armips main.asm`
   会以 `charmap.txt / graphic\fonts.s does not exist` 中止——**这是正常现象，不是缺陷**。
3. **WSL 调 Windows 控制台 exe 必须重定向 stdin**（`</dev/null`），否则永久阻塞。
   tools/wsl-bin/ 三个包装器已内置；新加包装器务必照抄这一行。
4. `build.bat` 曾漏编 3 个域共 6 个 obj（battle/pokedex/option），链接期才报
   `cannot find UpdateNickInHealthbox_entry.o`。已修（2026-11-02）。
5. **流水线不自动编译 C（重要）**：`font_patch.apply_font_patch()` 只是把
   `hook/out/game.bin` **现有文件**复制进 staging 再用 armips 嵌入，**不会调用
   `build.bat`**。所以：
   - 改了 `hook/src/**` 后，**必须先跑 `build.bat`，再打包**，否则打进 ROM 的是旧引擎；
   - 它会做 `_verify_game_bin_embedded()` 校验，但校验的是「ROM 里的 == 刚才复制的那个
     game.bin」，**不校验该 bin 是否由当前源码编出**——源码与 bin 脱节时静默通过。
   - 2026-11-02 实测踩到：仓库里遗留的旧 `out/game.bin`（trampoline 目标
     `0x08800159`）被静默打包；重跑 `build.bat` 后应为 `0x08800165`。
   - **自检**：打包后确认 `struct.unpack_from('<I', rom, 0x800004)` 等于
     `out/game.map` 里 `EngineEntry`/首个符号的地址。
6. **`reference/` 已移除（2026-11-02）**：`hook/reference/` 的
   `pokeemerald/copy_glyph_to_tiles.c` 与 `pokeruby/draw_glyph_tile.c` 编译后只提供 5 个
   `ref_glyph_copy` / `ref_fill_rect4bit` / `refpr_*` 全局符号，**全仓无任何调用者**
   （纯死代码，原占 `.text 0x161C + .rodata 0x3E8` ≈ 8KB）。绘制原语早已内联在
   `src/text/text_render.c`。移除后 `game.bin` 由 15452B → 8840B。
7. **字体来源单一化（2026-11-02）**：唯一来源是
   `configs/<game>/fonts/{normal,middle,small}.bdf`；仓根 `fonts/`（224MB / 95 文件）
   已删除并入 `.gitignore`，`engine.py` 不再回退扫描它。四套字库由
   `font.config.json` 的 `font_slots[].bdf` + `[].ink` 逐槽指定。
