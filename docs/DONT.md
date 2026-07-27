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