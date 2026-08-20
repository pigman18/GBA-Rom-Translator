# 需求文档：移除 F980 / hook 指针重定向，保留 relocate/replace/slot

> 目的：一份可执行的需求说明。**只列决策、范围、改动清单、验收，不做运行时微观设计**。
> 用户指出的路径即路径本身，本档不允许代理擅自加码或简化。

## 1. 背景与目标

当前翻译注入有 4 条通路：`in_place`（含 F900 整串 + F980 短语引用）、`relocate`、`hook`（pointer_redirect 指针槽）、`slot`。

目标（用户 2026-08 明确指令）：

1. **移除 F980 / PhraseTable 通道**（`in_place` 里的 `F9 80` 短语引用子路径、`type=phrase`、`PhraseTable/PhraseOffsets` 数据区、C 里短语查找逻辑）。
2. **移除 `type=hook` 指针重定向**（`pointer_redirect.py`、`main.asm` 里 `pointer_redirect.asm` include、C 里对应逻辑）。
3. **保留** `relocate`、`replace`（=旧 `in_place`，仅 F900 整串直写，去掉 F980 升槽子路径）、`slot`（扩展为**无长度上限**，仿旧 F980 的重定向思想：运行时按 JP 整条流查表替换成中文流）。
4. **全量改名** `in_place` → `replace`（含 `texts_patcher` 相关、脚本文件名 `find_orphan_inplace.py`）。

新链路（用户确认）：
`replace`（F900 ≤ 槽）→ `relocate`（有可用指针且模块允许）→ `slot`（其余全部可译条目，运行时查表重定向，无长度上限）→ `keep`。

## 2. 决策记录（已确认）

| 项 | 决策 |
|----|------|
| slot 槽表 VMA | `0x09F00000`（ROM file 偏移 `0x01F00000`） |
| relocate 写入封顶 | 从 `FONT_BOUNDARY(0x01FD3000)` 改为 `0x01F00000` |
| relocate 前提 | 必须解析到可用指针；无指针的候选降级到 slot |
| F980 / PhraseTable | 整体删除（`ADDR_PHRASE_OFFSETS/TABLE`、`PhraseOffsetsVMA/PhraseTableVMA`） |
| slot 语义 | `key:value`，`key = hash(jp_hex)`；相同 jp_hex 去重复用；命中后二次核对 `jp_len+jp_bytes` |
| GetStringWidth | 一并修（slot 命中返回中文流宽度，勿用旧的错误猜测地址 `0x08004CC0`） |
| texts_patcher YAML | 无字面 `in_place` → **YAML 不改** |
| 脚本文件名 | `find_orphan_inplace.py` → `find_orphan_replace.py` |
| `F9 00` 汉字字形通道 | **保留**（仅删 `F9 80` 短语引用注入） |
| C 渲染 hook（PrintNextChar/DrawGlyph 等） | **保留**，仅删其中的 phrase/op!=0 逻辑 |

## 3. 范围

### 3.1 必须移除（F980/PhraseTable）

- Python：`engine.py`（`_ensure_phrase_codes`、`phrases` 字段、`_auto_phrase_extra`、`_sideload_encode` 短语路径、custom_translation 短语码分配、`phrase_code` 字段）、`build_rom_data.py` 的 `write_phrase_data_asm`、`font_patch.py` 的 `_stage_phrase_data_fixed_vma` 与 phrase include。
- C/asm：`PrintNextChar_hook.c` 的 `phrase_stream_lookup` / `redirect_phrase_stream` / `inline_phrase_no_controls` / `phrase_parent_continues` 及 `op!=0` 分支；`GetStringWidth_hook.c` 的 `f9_width_at op!=0`；`UnusedPrintMonName_hook.c` 的 phrase 引用；`game_addrs.asm` 的 `PhraseOffsetsVMA/PhraseTableVMA`；`game.h` 的 `ADDR_PHRASE_OFFSETS/TABLE`。

### 3.2 必须移除（type=hook）

- `pointer_redirect.py` 整文件删除。
- `font_patch.py` 的 `write_pointer_redirect_asm` 调用。
- `main.asm` 的 `.include "./gen/pointer_redirect.asm"`。
- `rom_writer.py` 的 hook 分支与 stats `hook_skipped`。

### 3.3 保留并改名

- `replace`（旧 in_place）：仅 F900 整串直写，无 F980 升槽、无截断（超槽一律转 slot，不截断）。
- `relocate`：封顶 `0x01F00000`，必须有可用指针。
- `slot`：无长度上限，hash-keyed，VMA `0x09F00000`。
- `translated_slot.py` 重写：收集 `type=slot` 条目，按 `hash(jp_hex)` 排序生成查找表。
- `in_place` → `replace` 改名范围：`src/meowth/{rom_writer,translate_plan,layout,core/engine,i18n/messages}.py`、`src/util/debug_patcher.py`、`scripts/{check_animcmd,find_orphan_inplace,rebuild_full_zh,seg_hist}.py`、`docs/{MODULES,HOOK_RELOCATE_PLAN}.md`、`src/util/README.md`、`src/meowth/extract.py`、`src/util/tiles_patcher.py`。

## 4. 当前 build.json 分布与改造后预期

- 现状：in_place 5700（f900_full 119、phrase_ref 5128）、keep 658、hook 6、relocate 2133、slot 0。
- 改造后预期：`replace ≈ 119`、`relocate ≈ 2133`、`slot ≈ 5128+6`、`keep ≈ 658`。

## 5. 验收标准（流水线 + 静态断言）

运行：

```powershell
$env:PYTHONPATH = "$PWD\src"
C:\Python314\python.exe -m meowth full "roms\origin\POKEMON_RUBY_AXVJ00.gba" --seed-only --target zh-Hans -o "roms\outputs"
```

断言：

1. `translate.build.json` 无 `hook`/`f980`/`upgrade`/`phrase_code` 字段。
2. 分布符合 §4 预期（replace≈119、relocate≈2133、slot≈5134、keep≈658）。
3. 原槽未改写（slot 条目原地址仍为日文）。
4. 槽表位于 `0x01F00000`，`relocate` 正文未越界封顶。
5. `0x083E9688` 图鉴占位串恢复为原盘日文（`ac ac ac ac ac 9f 59 73 7e ff`）。
6. 编译通过：`hook\build.bat` + armips 打补丁不报错。

> ROM 实际运行效果由用户实测验收，按台账约定等用户说「正常」再 commit。

## 6. 需用户拍板的开放点（不得由代理擅自定）

slot 运行时 key 的**字节边界**（涉及 UI界面/剧情等 `fc 05` 前导控制码的 61 条条目）：

- **A**：`key = hash(整条 JP 流，从串起点含前导 fc/fd 控制码，读到 FF)`。
- **B**：`key = hash(去掉前导控制码后的可印子流)`。

两份口径给出的 build 侧 key 不同，运行时与 build 侧必须**完全一致**，否则 slot 条目静默不译。此点需用户确认后再实现 C 运行时与 `translated_slot.py`。