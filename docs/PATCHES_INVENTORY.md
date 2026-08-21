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
| `.include gen/translated_slot.asm` | slot 查找表 @0x09EA0000 | v2 分桶格式（'SLT2'） |

## 1. 补丁清单（按地址排序）

类型：**JMP**=订址跳板 / **INS**=指令替换 / **NOP** / **DATA**=数据改写

### A. 文本引擎钩子（必须常驻，互相依赖 game.bin 内部布局）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P01 | `0x0800336E` | `ldr r0,=(PrintNextChar_C\|1); bx r0`（6B+pool） | JMP | 可印字符统一进 CHS 引擎（F9 协议/slot/JP 同池），不命中回落官方 FontFuncTable | `src/text.c` `PrintNextChar()` 常规字形分支（查 FontFuncTable 之前的位置，AXVJ 符号 PrintNextChar_RegularGlyph） |
| P02 | `0x08003730` | `push {r4}; ldr r4,=(GetGlyphTilePointers_Hook\|1); bx r4`（6B+pool） | JMP | 字库取址分发：bit15=1 走 CHS 伪 glyph，否则重定位副本走原函数 | `src/text.c` `GetGlyphTilePointers()`（美版多 language 参数，日版 4 参） |
| P05 | `0x08003F4C` | `ldr r3,=(WaitArrow_Prepare\|1); bx r3`（4B+pool） | JMP | 等 A 箭头前置同步 CHS 相位（防双▼），随后回落原版主体 `0x08003DAD` | `src/text.c` FA/FB 等 A 箭头绘制段（DrawInitialDownArrow，AXVJ 命名） |

### B. 战斗

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P03 | `0x08042C38` / `0x08041760` / `0x08042620` | 字面量池 `0x04000008→0x04000006`（4B×3，armips include `src/battle/UpdateNickInHealthbox_hook_origin.s`） | DATA | HP 条昵称遮罩 CpuSet 32B→24B，避免盖掉 10/12px 汉字上半 | `src/battle_interface.c` `UpdateNickInHealthbox()` 共享字面量池 |

### C. 地图名弹窗旁路（结构性绕过——GetStringWidth 无法替代，见 §3 说明）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P04 | `0x0809F67E` | `ldr r0,=(MapName_DisplayCellLength\|1); bx r0`（6B+pool）；trampoline 直跳 `0x0809F6CB`（MenuPrint 前置点） | JMP | 跳过 `StringLength→右对齐 pad→二次 GetMapName(fill=10)`。⚠️ 该路径用**字节长度**与硬编码 10 格右对齐：内联 F9 地名 >10 字节时 `10-len` 下溢至 ~0xFFFE → 野写 + 65534 次清零循环（模拟器报 0xA2A2F6A4 类飞 PC 的根因） | `src/map_name_popup.c` `DrawMapNamePopup()`；GetMapName 见 `strings.c` |

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
| P08 | `0x080889F0` | `push {r3}; ldr r3,=(DrawOptionMenuChoice_Hook\|1); bx r3`（6B+pool） | JMP | 设置窗口选项高亮：F9 80 短语引用下 style 不能写 dst[2]，改为调色板/前景色覆盖变量 | `src/option.c` `DrawOptionMenuChoice()` |

### F. 数据清理（置空日文残留）

| ID | 地址 | 改动 | 类型 | 目的 | pokeruby 对应 |
|---|---|---|---|---|---|
| P13 | `0x08090EF0` | NOP×6（12B） | NOP | 图鉴计数函数1：去掉硬编码「ひき」后缀 | `src/pokedex.c` 计数显示族（配合 `string_util.c` ConvertIntToFullwidthBytes） |
| P14 | `0x08090F3C` | NOP×6 | NOP | 函数2（AXVJ 注：GetNationalPokedexCount） | 同上 |
| P15 | `0x08090FAA` | NOP×6 | NOP | 函数3（AXVJ 注：GetHoennPokedexCount，用 R0） | 同上 |
| P16 | `0x081BC164` | `.byte 0xFF,0xFF`（2B） | DATA | 徽章屏文字后缀置空 | 徽章相关数据串（pokeruby 无独立符号） |

## 2. 被 C 层直接调用的官方函数（不在 main.asm，但同属依赖面）

| 官方地址 | AXVJ 符号 | pokeruby 对应 | C 层调用者 |
|---|---|---|---|
| `0x08003730` | GetGlyphTilePointers | text.c 同名 | chs_get_glyph_tile_pointers（JP 字模取址） |
| `0x08003830` / `0x080038A0` | CopyGlyph1bppTo4bpp / CopyGlyph2bppTo4bpp | text.c 同名辅助 | 颜色重映射 |
| `0x080036DC` | UpdateTilemap | text.c tilemap 更新 | chs_update_tilemap |
| `0x0806F16C` | Menu_PrintText | `src/menu.c` Menu_PrintText | option/dex hook 组串后委托 |
| `0x0800436C` | StringLength | `src/string_util.c` | （弹窗原路径用） |
| `0x08004228` / `0x08004530` | GetGlyphWidth / GetStringWidth | text.c 同名 | ⚠️ 未接线；且 0x04228 有「实为 spacing 表」的争议记录，见 GetGlyphWidth_hook.c 头注 |
| `0x081BB3AC` / `0x081B12DC` | FontFuncTable / CallViaR2 | lib 工具段 | PrintNextChar 回落官方 FontFunc |
| `0x081B1294` | CpuSet | crt0/lib 工具段 | 血条遮罩（池常量被 P03 改短） |

## 3. 关键结论（影响后续去留决策）

1. **P04 不能靠 GetStringWidth 替代**：弹窗路径不查像素宽度，用的是 `StringLength` 字节数 + 硬编码 10 格右对齐；中文内联 F9 地名普遍 13~17 字节 > 10 → `10-len` 下溢 → `sp+0xFFFE` 野写 + 65534 次清零（本次 0xA2A2F6A4 飞 PC 的根因）。要么保留 P04 旁路，要么重构原版逻辑本身。
2. **P01/P02/P05 三钩互为前提**：都依赖 game.bin 内部符号布局（经 game_syms.asm 回填）。任何 game.bin 重编后必须同步重跑 armips。
3. **P09~P12 是同一事务**：初始宠 label 四处改动必须同时存在，拆分时归并为一节。
4. **P19~P23 共用一个常量**：DEX_NAME_COLUMN 定义在 game_addrs.asm，改值即可全局调整。
5. 死代码（不影响运行，占 game.bin 空间）：GetGlyphWidthHook / GetStringWidthChinese（未订址）、HealthboxNickCpuset*（仅导出常量）、MapName_DisplayCellLength_C（trampoline 不再经过它）。

## 4. 已实施的拆分结构（2026-08-22）

```
hook/
├── main.asm                        # 纯装配骨架：open/include 清单/game.bin/fonts/slot 表
├── game_addrs.asm                  # 纯 equ 唯一来源（未动）
├── patches/                        # 【纯值补丁】就地指令/数据改写，无 C 依赖
│   ├── ui_starter.asm              # P06 P09 P10 P11 P12（初始宠 label 整组）
│   ├── ui_pss.asm                  # P17 P18（PSS 图标列）
│   ├── ui_dex.asm                  # P19~P23（图鉴名字列 ×5）
│   └── clean_suffix.asm            # P13 P14 P15 P16（ひき NOP / 徽章 FF）
└── src/
    ├── text/hooks_origin.s         # P01 P02 P04 P05（订址桩；逻辑在 ../entry.s + *_hook.c）
    ├── battle/hooks_origin.s       # P03（池常量；原 UpdateNickInHealthbox_hook_origin.s 改名）
    ├── pokedex/hooks_origin.s      # P07
    └── option/hooks_origin.s       # P08
```

分层规则：
- **纯值**（改指令/数据，无逻辑）→ `patches/{类名}.asm`
- **复杂钩**（需要 C 逻辑/寄存器编组）→ `src/{类名}/entry.s` 钉跳板 + `src/{类名}/*_hook.c` 逻辑，
  ROM 侧订址桩统一放 `src/{类名}/hooks_origin.s`（armips include，不进 gcc）

### 已验证

| 项 | 结果 |
|---|---|
| 整理前后 game.bin | md5 一致 `a7fd0038aafb8ff1ea3be5586112b1f9`（纯移动，零语义变化） |
| armips 全量装配 | exit=0，output.gba 32,131,389B |
| 六个订址桩字面量 | 全部命中回滚后 syms 地址 ✅ |
| P03 血条池 | 0x04000006 ✅ |

### 踩坑记录（重要）

1. **armips 不认 GNU as 的 `@` 行注释**——且不是报错，是**静默崩溃 exit=9 无任何输出**。
   armips 侧文件注释一律用 `;`；`@` 只允许出现在 gcc 汇编（GNU as）文件里。
2. **WSL 调 Windows 控制台 exe 必须重定向 stdin**（`</dev/null`），否则永久阻塞。
   tools/wsl-bin/ 三个包装器已内置；新加包装器务必照抄这一行。
3. Makefile 已修复：16 个 obj 补齐 + text_entry.o 链接首位规则 + CR 安全 grep +
   6 符号 syms 输出（与 build.bat 对齐）。
