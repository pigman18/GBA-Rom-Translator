# 图鉴分类名打印 Hook —— 交接文档（供接手人使用）

状态：**交接待办**。原作者（AI）在定位阶段无限循环、未完成实现，本文件汇总：
① 已确认的事实（可直接信任）；② 原作者的错误与教训；③ 接手人必须做的事（按步骤执行，先 hook 验证再深究）。

## 任务目标

修复日版图鉴条目屏「分类名」行的渲染 bug：

- 2 字分类名 → 显示 `蝴蝶？？宝可梦`（残留问号）
- 3 字分类名 → 正常（`坏心眼宝可梦`）
- 4 字分类名 → 吃掉「宝」(`森林蜥蜴可梦`)

## 已确认的事实（可靠，勿推翻重查）

### 美版参考实现（pokeruby 源码）

`UnusedPrintMonName` @ `tools/pokeruby/src/pokedex.c:4228-4247`：

```c
for (i = 0; name[i] != EOS && i < 11; i++)
    str[i] = name[i];
str[i] = EOS;
MenuPrint_AlignedToRightOfReferenceString(str, left, top, gDexText_UnknownPoke);
```

- `MenuPrint_AlignedToRightOfReferenceString` @ menu.c:666-672：
  `width = GetStringWidth(gMenuWindowPtr, widthRefStr)`；`AlignString(win, buffer, src, width, 1)`；`Text_InitWindowAndPrintText(buffer, left, top)`。
- `AlignString` alignType=1 @ text.c:3575-3585：`width(src) < alignAmount` 时前置 `FC 13 (alignAmount-width)`（EXT_CTRL 19 = 右对齐空格推进），否则原样拷贝。
- 调用点：pokedex.c:2944 与 3835（`UnusedPrintMonName(categoryName, CATEGORY_LEFT, 5)`）。
- 美版符号（pokeruby.sym）：
  - `UnusedPrintMonName` = `0x08091304`（size 0xa0）
  - `PrintEntryScreenSpeciesName` = `0x080911c8`
  - `MenuPrint_AlignedToRightOfReferenceString` = `0x08072b80`
  - `AlignString` = `0x08004b24`
  - `gDexText_UnknownPoke` = `0x0840dff9`
  - `PrintNextChar` = `0x08002fe0`

### 日版地址（已从 AXVJ ROM 确认）

- 日版 `gDexText_UnknownPoke` = **`0x083E9688`**
  - 现内容：`ac ac ac ac ac f9 80 03 fa ff` = 「？？？？？宝可梦」
  - 原盘内容：`ac ac ac ac ac 9f 59 73 7e ff` = 「？？？？？ポケモン」
- 引用 `0x083E9688` 的 pool 槽：`0x0808C238`、`0x0808D5D8`（全 ROM 仅这两处）。
- `0x0808C234` 起是一个指针表：`0x0202D8FC, 0x083E9688, 0x083E9692, 0x083E9699, 0x0838474C`。
- 图鉴条目屏代码区：`~0x0808C0D0-0x0808C2A0`。
  - owned 检查：`LDRB r1,[r2,#2]` / `AND r0,#2` / `BEQ 跳过`。
  - **分类名打印调用点**：`0x0808C1DA MOV r1,#0x0D`（x=13）；`0x0808C1DC MOV r2,#0x05`（y=5）；`0x0808C1DE BL → 0x0808D7A0`。
  - 身高：`BL 0x0808D7E6` @ (16,7)；体重：`BL 0x0808D7F1` @ (16,9)；描述：`BL 0x0806E9C9` @ (3,13)。
  - 日版 `CATEGORY_LEFT = 13`（美版为 11）。
- 运行时捕获（InitTextPrinter 日志）：
  - 分类名以短语打印：`f9 80 0b 32 ff`（= 森林蜥蜴，phrase 0x800B=2866）。
  - 占位串按 `ac×5 + f9 80 03 fa ff` 打印。
  - 两条均 win=0x0202E658、textMode=1、fontNum=3；LR=0x08002D14。
- 宽度规则（`GetStringWidth_hook.c`）：中文汉字 12px/字；JP 假名/问号 8px/字。5 个问号区 = 40px。

## 根因（一句话）

日版分类名打印 = 先打占位符「？？？？？宝可梦」，再把分类名覆盖上去并右对齐到占位符宽度。
中文分类名按 12px/字推进、问号按 8px/字，导致 2 字/4 字名的覆盖宽度与 5 问号区（40px）不匹配：
2 字（24px）盖不满剩 2 个问号；4 字（48px）溢出吞掉「宝」。

## 原作者犯的错误与教训（接手人注意）

1. **无限循环**：反复「反汇编 → 得出地址 → 自我怀疑 → 换锚点再反汇编」，同一片区域反汇编 6-7 遍，从未推进到写 hook。
2. **不按用户给定方法**：用户明确要求「以 PrintNextChar 查日美偏移 → 按偏移找 UnusedPrintMonName → 到 ROM 该地址附近找函数、对比输入输出确认 → 直接 hook 验证」。原作者却用 AGENTS.md 里「跨分段偏移不是常数」自我怀疑，宁可反复验证也不肯先 hook 实测。
3. **验证纪律误用**：AGENTS.md 说「禁止主动启动模拟器」，但 hook 编译/armips 汇编验证不依赖模拟器，可以直接做；原作者没做。
4. **教训**：先按偏移算出候选地址、找到函数、hook 上去编译验证；验证不过再回头查。**不要先追求 100% 确认再动手。**

## 接手人必须做的事

### 步骤 1：查日美偏移（已算好，复核即可）

- 美版 `PrintNextChar` = `0x08002FE0`；日版 `ProcessCurrentChar` = `0x080032F8`（game_addrs.asm:8）。
- `Δ = 0x318`。

### 步骤 2：按偏移找 JP UnusedPrintMonName 并确认

- 美版 `UnusedPrintMonName` = `0x08091304` → 日版初算 `0x08091304 + 0x318 = 0x0809161C`。
- 去 ROM `0x0809161C` 附近找函数：`0x080915EC` 有一函数体（`B5F0` 开头），**对比输入输出**：
  - 入参应类似 `(name, left, top)`（与美版一致）；
  - 应有「拷 name 到局部 buffer（`LDRB/STRB` 循环）」+「调右对齐打印」两条特征。
  - 与反汇编出的 `0x0808D7A0`（分类名打印调用点）互相印证。
- **若 `0x0809161C` 附近对不上**：以 `0x0808D7A0`（分类名打印调用点，已确认）为准往回找函数起点。

### 步骤 3：新建 `src/pokedex/UnusedPrintMonName_hook.c`

参考现有 hook 写法：`src/text/PrintNextChar_hook.c`、`src/battle/UpdateNickInHealthbox_hook.c`、
`src/battle/UpdateNickInHealthbox_entry.s`。

重写核心拷贝逻辑（不再按固定 11 字节），处理中文短语引用：

- 按 PCS 逐字节解析：`0xFF`（EOS）即停；`F9 xx xx xx` 短语整体 4 字节拷贝。
- 覆盖宽度按 12px/字推进，使分类名正好盖住 5 问号区（40px），不残留问号也不吞「宝可梦」。
- 保留右对齐打印（JP 等效调用），坐标 (13, 5)。

### 步骤 4：接线

- `hook/build.bat`：新增编译 + 链接 `src/pokedex/UnusedPrintMonName_hook.c`（参照现有行）。
- `hook/Makefile`：OBJS 加入新 .o。
- `hook/main.asm`：在 JP 分类名打印函数入口 `.org` 处跳入 hook（`ldr r0,=(hook|1); bx r0`）。
- `hook/game_addrs.asm`：登记 JP `UnusedPrintMonName` 地址常量。

### 步骤 5：验证（不依赖模拟器，可直接做）

1. `cd configs\POKEMON_RUBY_AXVJ00\hook; .\build.bat`（需 arm-none-eabi-gcc 在 PATH）。
2. armips 打补丁：`Copy-Item ..\..\roms\origin\POKEMON_RUBY_AXVJ00.gba baserom.gba` + `..\..\..\tools\armips.exe main.asm`。
3. 打 ROM 后用户实测三类分类名：2 字（蝴蝶）、3 字（坏心眼）、4 字（森林蜥蜴）。

## 相关文件

- 美版源码：`tools/pokeruby/src/pokedex.c:4228-4247`、`menu.c:666-672`、`text.c:3562-3607`
- 现有 hook 范例：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c`、
  `configs/POKEMON_RUBY_AXVJ00/hook/src/battle/UpdateNickInHealthbox_hook.c`、
  `configs/POKEMON_RUBY_AXVJ00/hook/src/battle/UpdateNickInHealthbox_entry.s`
- 构建：`configs/POKEMON_RUBY_AXVJ00/hook/build.bat`、`Makefile`、`main.asm`、`game_addrs.asm`
- 宽度规则：`configs/POKEMON_RUBY_AXVJ00/hook/src/text/GetStringWidth_hook.c`
- 日版占位串：`0x083E9688`