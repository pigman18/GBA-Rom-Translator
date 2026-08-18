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
- **现行**（F9 80 字节流表）：表体常 >64KB，**两侧均为 u32**：
  engine `.word` ↔ hook `uint32_t *`。
- **禁止**：单独改 engine.py 表生成或 hook 的 offsets 类型。两者必须同宽：
  engine 用 `.halfword` ↔ hook 用 `uint16_t *`，
  engine 用 `.word` ↔ hook 用 `uint32_t *`。
- **自检**：改完跑
  `python -c "import struct; rom=open('roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba','rb').read(); off=[struct.unpack_from('<I',rom,0x810000+i*4)[0] for i in range(4)]; print('offsets u32:', off)"`
  验证 offsets 步进递增、无异常回绕。
