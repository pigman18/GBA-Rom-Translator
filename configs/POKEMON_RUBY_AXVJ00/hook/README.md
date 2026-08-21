# hook/ 目录组织与命名规范

> 生效日期：2026-08-22。任何新增/移动/删除补丁文件前必读。
> 逐条补丁底账见 `docs/PATCHES_INVENTORY.md`（ID 体系来源）。

## 1. 目录总览

```
hook/
├── main.asm                  # 【骨架】只做装配，禁止再堆 .org 补丁
├── game_addrs.asm            # 【地址唯一事实来源】所有 equ 在此定义
├── patches/                  # 【纯值补丁】armips 就地改写，无 C 依赖
│   ├── ui_starter.asm        #    文件名 = {域}_{对象}.asm，小写下划线
│   ├── ui_pss.asm
│   ├── ui_dex.asm
│   └── clean_suffix.asm
├── src/                      # 【复杂钩子】gcc 编入 out/game.bin + armips 订址桩
│   ├── text/
│   │   ├── entry.s           #    gcc：跳板合集（历史遗留的大文件，不再往里加新钩）
│   │   ├── hooks_origin.s    #    armips：本域全部订址桩（固定文件名）
│   │   └── *_hook.c          #    gcc：C 逻辑
│   ├── battle/hooks_origin.s #    同上；另有 {Name}_entry.s + {Name}_hook.c 成对
│   ├── pokedex/hooks_origin.s
│   └── option/hooks_origin.s
├── link/game.ld              # gcc 链接脚本（VMA 0x08800000）
├── out/                      # 生成物：game.bin / game.map / game_syms.asm（勿手改）
└── build.bat / Makefile      # Windows / WSL 两条等价构建路径
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
          │   例：P04 地名弹窗居中（跳板 MapName_DisplayCellLength 也放 entry.s，
          │       C 逻辑 MapNamePopup_hook.c 按引擎步进算留白、加大 MenuPrint x 起点）
          └─ 否 →【纯值】patches/{域名}.asm 里就地改写指令/数据
              例：P06 mov r2,#0x1D、P13~P15 NOP 组、P16 数据 FF
```

**判定口径**：改动是否只是「换了个立即数/换了几条无分支指令」？是 → 纯值；
只要出现「条件分支循环重写」「要查表」「要读窗口状态」→ 复杂钩。
拿不准时按复杂钩处理（可测试后再降级）。

## 3. 命名规则

| 对象 | 规则 | 例 |
|---|---|---|
| 域名（目录） | 固定枚举：`text` / `battle` / `pokedex` / `option`；新域先在本文件登记 | `src/pokedex/` |
| 纯值补丁文件 | `patches/{域}_{对象}.asm`，小写下划线 | `ui_starter.asm` |
| 订址桩文件 | 固定名 `hooks_origin.s`，每域一个，不许拆散 | `src/text/hooks_origin.s` |
| gcc 跳板/逻辑对 | `{Name}_entry.s` + `{Name}_hook.c` 同名成对（Name=官方函数名） | `UnusedPrintMonName_entry.s` / `UnusedPrintMonName_hook.c` |
| 补丁 ID | Pxx 顺序号，分配后永不复用；写在节头 `[Pxx]` | `[P24] xxx` |

> `src/text/entry.s` 是历史遗留的跳板合集（链接首位约束），维持现状；
> **新的复杂钩一律走 `{Name}_entry.s` 成对模式**，不要再往里追加。

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
改 C/hook.c ──► build.bat（或 WSL make）──► out/game.bin + out/game_syms.asm
                                                      │ syms 地址可能变化
改 asm 补丁 ──────────────────────────────────────────┤
                                                      ▼
                                     armips main.asm ──► output.gba
```

- **game.bin 重编后必须重跑 armips**（syms 回填变了）；
- WSL 构建：先 `scripts/wsl-interop-setup.sh`（binfmt 注册），然后
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
