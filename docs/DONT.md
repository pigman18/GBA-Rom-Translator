# 禁止文档 — 不可再犯的错误

## 编辑规范

### 1. 永远不要用 `oldString` 匹配可能被其他行共享的短文本

- `oldString` 必须包含足够多的上下文，确保全局唯一匹配
- 短文本（如 `SPECIES_COUNT = _SPECIES.get("count", 412)`）可能被其他行共享相同的模式
- ✓ 解决：包含前后各 1-2 行作为锚点

### 2. 永远不要在 Python 文件中使用复杂条件赋值代替简单添加

- 如需添加新行，直接使用 `edit` 在已有行之间插入，不要用条件表达式、walrus operator 等「技巧」
- ✓ 解决：先读文件确认精确位置，然后 `oldString` 写前后行，`newString` 包含新行

### 3. 每次修改后必须在本地验证完整 pipeline 再提交

- 不要在只改了一个文件、没跑完整流程的情况下就认为 done
- `python -c "from meowth.tables import SPECIES_COUNT, TYPE_NAME_STRIDE"` 这种快速检查可以提前发现 import 错误
- ✓ 解决：每个改动后至少跑一次 `python -c "from meowth.tables import *"` 或对应模块的 import check

### 4. 不要在 edit 中添加不存在的引用

- 例如引用了 `_get_type_stride()` 但该函数不存在
- 例如使用 walrus 赋值 `_TYPES := ...` 且分支永远不会执行
- ✓ 解决：写代码时假设自己是解释器，逐行模拟执行

### 5. 永远不要相信 ARMIPS 运行成功就等于输出文件正确

- `patched` 文件路径必须在 ARMIPS **运行后** 确定，而非运行前
- 字母序 fallback 会误取到 `baserom.gba`（未修补的原版）—— 必须显式排除
- ✓ 解决：运行后扫描 GBA 文件，跳过 `baserom`

### 6. 中间产物永远不要写入最终输出目录

- `texts.json`、`texts_translated.json` 是中间产物，应写入 `work_dir`
- `output_dir` 只放 ROM 和 `.build.json`
- GUI 的 `work_dir` 应与 CLI 默认一致（`Path("work")`），不能从 `output_dir` 推算

### 7. 不要让同一个文件同时作为进程输入和输出

- Windows 下 ARMIPS 创建的 memory-mapped section 会导致 `shutil.copy2` 失败（WinError 1224）
- ✓ 解决：用 `temp_in`/`temp_out` 分离路径，最后再删除

### 8. 记录禁止文档

- 每次犯错后更新 DONT.md，确保不会重复犯
- ✓ 当前已执行

### 9. 中文绘制：12px 度量，勿改 8×16 容器

- **8×16 tile 容器 / 128B 字槽**是 Gen3 硬件约定；**12px** 只指墨水、字高、步进、行距
- **禁止**再走「真 12×12 @ 18B 取代 16 高槽」——已证伪（无笔画）
- **禁止** ShadowedFont（`colors[0]=bg`+OR）；**禁止**默认 adv16
- 台账：[`FONT_12PX_DRAW.md`](FONT_12PX_DRAW.md)；规则：`.cursor/rules/axvj-font-12px-only.mdc`

### 10. GDB/dump 只做精确确认，绝不先抓现场

- **现象**：改 UI BUG（红框不全等）时，跳过静态分析直接抓 GDB/VRAM，抓到一坨数据
  也不知道该拿哪段、拿它干嘛 → 一塌糊涂；最后靠用户指入口 + 读源码静态分析才修好。
- **根因**：把「抓数据」当成「推进」，实际没先想清楚要问它什么。顺序必须反过来。
- **禁止**：
  - 先抓现场、再回来硬凑解释。
  - 还没读到能说出「具体函数名 + 写入路径 + 一个会被证伪的假设」就去抓 GDB。
- ✓ 解决：先读 `hook/src` + `tools/pokeruby/src`，锁死一条写入路径并给出可证伪假设；
  GDB 仅在「能说出三样 + 用户允许」时才做一次性精确确认。抓之前先问自己：
  「我现在能说出是哪个函数、哪条路径、哪个字节能证伪吗？」不能就回静态。

### 11. 用户给的路径/方法就是路径本身，不是"可选项"

- **现象**（2026-08-18 红框，连续两晚）：用户说「直接搜 ROM / 先读源码」，
  我却去 grep 符号表找 `gMenuSummaryGfx`、拿超 ROM 范围的地址做 LZ 解压、
  分析指针表变量；用户自己 `probe_data` 一把命中精灵图位置几分钟定案。
- **根因**：把 AGENTS.md 的「定位纪律」（查符号表）**误套用到"数据被写坏"类任务**上。
  符号表告诉你函数在哪，不告诉你哪块数据被写坏。
- **禁止**：
  - 用户说「直接搜字节/搜 ROM」时，第一动作不是字节级搜索/比对。
  - 图形异常/数据被写坏类任务，不先做 origin-vs-output 逐字节比对 + `probe_data` 特征搜索。
  - 把用户明确指出的路径擅自简化、替换成自己的惯性路径。
- ✓ 解决：先读 `docs/START_HERE.md` 判断树选对第一动作；动手前复述计划让用户确认。

### 12. PhraseOffsets 位宽：engine 和 hook 必须一致

- **现象**：全局文字变红、背景黑条/花屏、菜单光标消失。
- **根因**（2026-08）：engine.py 的 PhraseOffsets 生成改用 `.word`（u32，4B/项），
  但 hook 仍读 `uint16_t *offsets`（u16，2B/项）。
  导致奇数 code 全部读到 0 → 指向第一条目 → 渲染垃圾字形 → VRAM 腐蚀 → 全局红字。
- **现行**：`PhraseTable` / `PhraseOffsets` **已废弃**（不再有 `F9 80` 引用），
  只剩 `GetStringWidth()` 的 `op != 0` 分支还在读，属待清理死重量。
  这条只作为「读写步长必须同宽」的历史教训保留。
- **禁止**：单独改 engine.py 表生成或 hook 的 offsets 类型。两者必须同宽：
  engine 用 `.halfword` ↔ hook 用 `uint16_t *`，
  engine 用 `.word` ↔ hook 用 `uint32_t *`。
- **自检**：改完跑
  `python -c "import struct; rom=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read(); off=[struct.unpack_from('<I',rom,0x810000+i*4)[0] for i in range(4)]; print('offsets u32:', off)"`
  验证 offsets 步进递增、无异常回绕。

### 13. 已有协议只许加，不许改

- **现象**（2026-11-11）：图鉴分类名后缀搞不定，先去**给分类名译文追加「宝可梦」**
  （动了文本数据 = 动协议产出），又把原版占位串的打印点 `nop` 掉（动了原版流程）。
  两处都被用户否掉，全部回滚。
- **根因**：把「显示不对」当成「协议不够用」，于是改协议/改数据去迁就；
  实际编码逻辑本来就简单（一个前缀 `F7` + 码位），该做的是**在 hook 上叠一层**。
- **禁止**：
  - 未经证实就改 `F7 00 hi lo` 编码、`append_stream` 的自由长度语义、
    `rows/redirects/tables` 写入模型、任何 hook 的返回契约。
  - 把已废弃的 `F9 00` 原地写 / `F9 80` 短语引用 / `SLT2` / `PhraseTable` 重新引入
    或写进新文档（见 `docs/PROTOCOL_CURRENT.md`）。
  - 用「改译文/改 texts.json 数据」去绕显示问题（数据是协议产出，改了就等于改协议）。
  - 改原版指令来「消掉」某个显示（如 nop 打印点）；原版流程照跑，覆盖由 hook 负责。
- ✓ 解决：先给「现状为什么错」的实测证据（字节/截图/反汇编）。没有证据 → 只能加不能改。

### 14. 动手前先看 origin，把「原版怎么显示」讲清楚

- **现象**（2026-11-11）：图鉴分类名那行，我没看 origin 就断定「后缀丢了、要补」，
  于是追加后缀；实际 origin 里这行 = **占位串「？？？？？ポケモン」+ 分类名盖住问号**，
  那 4 个假名就是**占位符的尾巴**，不是分类名的一部分。
- **根因**：不看 origin 就脑补机制，补丁必然打在错的地方（还顺带把图鉴说明弄回日文）。
- **禁止**：
  - 没看 origin 同屏就动显示类补丁。
  - 先改再看现象（改完才发现「原来它本来就有」）。
- ✓ 解决：动手前回答四问——**这段字谁打的 / 打在哪 / 宽度怎么算 / 占位符与后缀从哪来**。
  另外先读**自家 hook**：`UnusedPrintMonName_hook.c` 一直在从 `0x083E9688`
  捡「ポケモン」当后缀，这才是真因，ROM 里没有谜题。
