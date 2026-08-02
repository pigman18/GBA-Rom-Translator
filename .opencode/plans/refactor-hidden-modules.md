# 真模块化 hidden scanner + 去除 category/modules_defaults/content_classes 标签体系

## 背景与目标
- 现状 `extract_axvj → extract_modules` 已是模块驱动主路径。
- 但 8 个 hidden UI 模块（needle/prefix/pointer 类型）在 `extract_pipeline.extract_modules`
  走 `_UI_EXTRACTOR` → `_run_ui_op` → 复用 extract.py 里**硬编码的独立 scanner 函数体**，
  并非真正按 `read.scan_addr_bands` 通用扫描。这些函数内部又各自调用
  `enrich_*` → policy →（回退 game.json）打 `category` 标签，耦合深、不可靠、无日志。
- `category = story / ui / ime / unclassified` 这套标签由 `modules_defaults` 提供，
  但在 `stamp_entry_module`（modules.py:282）处被**覆盖为真实模块 id**，从未真正驱动任何归属。
- 用户要求：真驱动 hidden + 去除 category 标签体系 + modules 里扫描命中可见（日志）。

## 设计决策（用户已确认）
- **一次到底**：全部 8 个 hidden 模块改为走通用 scan 引擎，按 `read.scan_addr_bands` 驱动。
- **彻底去除** `category` 标签体系与 `modules_defaults` / `content_classes` 旁路。
- 归属收敛为单一 `module` 字段（stamp_entry_module 已保证，见 modules.py:282-293）。
- 代价：每个 hidden 模块原 scanner 的**特殊解码/指针规则**需迁到模块 `read` 配置。

## 调研结论（决定 How）
- 读取这些 scanner 已从模块源取参：`enrich_scan_bands`/`enrich_seed_originals`/
  `enrich_keep_any_contains`/`enrich_prefix` 均优先 hidden 模块 read。**bands/needles 已在模块**。
- 构建侧 engine/layout/rom_writer 用 `entry.get("module") or entry.get("_axvj_module") or entry.get("category")`
  逐级回退；去除 category 后只要 module 始终 stamp，即安全（set 时会全覆盖三键）。
- `content_classes.存档与电源`（唯一一条共享规则）→ 内联进「存档提示扫描」模块 read。
- 主脚本指针 scanner（extract_script_pointers）的 story/UI 切分依赖
  `module_defaults().story/["ui"]` + `enrich_default_module("短标菜单")` + `is_enrich_seed_label`——
  需改为从模块导出分类 → 被 `stamp_entry_module` 按地址覆盖，此处标签仅临时。

## 实操步骤

### 1. modules.json：hidden 模块 read 补全/内联
- 「存档提示扫描」：把 `content_classes.存档与电源` 的 `any_of` 规则表移到
  `read.any_of`（或 read.sample_rules），删依赖全局 content_classes。
- 「FC彩窗扫描」：读处 `classify_rules`。
- 「战斗提示扫描」：读处 `classify_rules`。
- 「状态背包采集」：读处 `module_by_original`。
- 「选项菜单扫描」「短标菜单采集」「战斗HUD采集」：读处 `default_module`（若需）。
- 逐个 hidden 模块确保 `read.scan_addr_bands` 就是实际扫描带（已是）。
- 删除 game.json `extraction.enrich.*` 对应冗余字段与 `content_classes`。

### 2. policy.py：enrich_* → 统一从模块 read 读（删除 game.json 回退路径）
- `enrich_block/enrich_default_module/enrich_classify_rules/enrich_module_by_original/`
  `enrich_seed_from_lexicon/enrich_keep_any_contains/enrich_content_class` 全部改为
  「hidden 模块 read 优先」+ 无回退（game.json 不再承载）。
- `matches_content_class`/`content_class_spec` 改为读模块 read 内联规则。

### 3. extract_modules / _run_ui_op：hidden 真驱动
- 让 needle/prefix/pointer 模块也能经通用 `scan_addr_bands`（bands 已在 read）。
- 各家特有取样逻辑（wrapper 解码/指针规则）用 read 新字段表达（如 `prefix`、`min_len`、`max_len`、
  `ptr_aligned`、`require_ptr`、`keep_any_contains`……）。
- 至少覆盖：FC彩窗(prefix)、选项菜单(prefix)、战斗提示(prefix)、短标/状态背包/HUD(needle)、
  存档(needle)、主脚本(pointer)。

### 4. 去除 category 标签体系
- extract.py 各 scanner 不再写 `category`（或写也随 stamp 覆盖）。
- `module_defaults()`、`extract_pipeline.module_defaults`、`_classify_ui` 相关删除。
- loader/build 侧 `e.get("category")` 回退改为仅 `module`/`_axvj_module`。
- 保留 `stamp_entry_module` 只写 `module`/`_axvj_module`（category 可删或同步去）。

### 5. 扫描命日志
- 在 extract_modules 每个模块按 band/needle 扫描后输出命中数（logger），
  hidden 模块专属抽样也输出 станций数 + 末尾汇总：每模块命中 vs bands。

### 6. game.json 精简
- 只留 game_id/label + 全局扫参（encoding/script_bank_min/script_text_ptr_opcodes/trusted_lz_bands）
+ reject.gfx_string_target（唯一特定拒绝值）。其余全部迁 modules.json 或删。

## 验证（回归，必须与原数一致）
- 主流程 `extract_axvj`：核对条目总数与模块分布（当前基线 13683，FC彩窗 75 / HUD 929 / 开始菜单 183）。
- hidden_only：107 条基线。
- tables_from_modules_inject：6 表。
- `python -m meowth full --seed-only` 打包到 `roms/outputs`，确认 build 全链成功。

## 风险与说明
- 通用 scan 引擎对 memory 特殊取样（FC 前缀 / 指针对齐）需 read 字段表达，可能对
  FC彩窗/选项/短标 命中数带来变化——必须逐步对拍，守住上述基线。
- `stamp_entry_module` 已保证 module 覆盖，故去除 category 不影响归属。
- 涉及文件：modules.json、game.json、policy.py、extract_pipeline.py、extract.py、
  modules.py、engine.py、layout.py、rom_writer.py、table_patch.py。