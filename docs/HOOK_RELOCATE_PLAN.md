# 最终方案：`relocate` / `hook` 双开关 + `type=hook`

> 保存日期：2026-08-05。供日后查阅；实现以代码为准。

## 结论

1. **`type=hook`**：与 `relocate` / `upgrade` / `in_place` / `keep` 并列的 plan 决策。
2. **`relocate` 布尔**：替换旧字段 `no_relocate`（极性反过来：`relocate=true` 才允许改指针写扩展区）。
3. **`hook` 布尔**：前序路径都走不通后，是否允许「指针重定向 asm」路径。

地名等已踩坑域：**`relocate=false` 且 `hook=false`**，只保留装得下的 `in_place`（+ 可选 F980 `upgrade`，不改指针）。

## 模块字段（`modules.json` / util map）

| 字段 | 含义 | 建议默认 |
|------|------|----------|
| `relocate` | `true`：允许注入期改 `pointer_sources` 做扩展区正文 | 剧情等为 `true`；地点名/多数 UI/`stride` 表为 `false` |
| `hook` | `true`：前序失败后允许生成指针重定向 asm | **默认 `false`**；仅白名单显式 `true` |

迁移：

- 旧 `no_relocate: true` → `relocate: false`（删除 `no_relocate`）
- 旧 `no_relocate: false` 或未写 → `relocate: true`（`stride`/`struct`/`ptr_stride` 仍强制不可指针改写）
- 全部模块补 `hook: false`

## `plan_entry` 路径（固定顺序）

```text
in_place（F900 ≤ 槽）
  → relocate（relocate=true 且有指针）
  → upgrade（槽 ≥ 5，F9 80）
  → hook（hook=true 且有指针）→ 生成 pointer_redirect.asm
  → keep
```

- **`relocate` 与 `hook` 都是改指针**，交付不同：`relocate` = Python `rom_writer`；`hook` = armips asm。
- `hook` 条目载荷：`target_hex`、`pointer_sources`（与 relocate 相同）。

## `type=hook` 运行时

1. Build 收集 `type=hook`，生成 `configs/<game>/hook/gen/pointer_redirect.asm`
2. `main.asm` `.include` 该文件
3. `rom_writer` **跳过** `type=hook`（避免与 armips 双写）
4. PhraseTable / `game.bin` 绘制钩子不因此改动

## 约束

- 地点名：`relocate=false`, `hook=false`
- 禁止为消化 keep 打开地点名的 hook/relocate
- 禁止改 lexicon 缩写凑槽；禁止在 `.py` 写死单地址
- **扩展区**：`hook/config.json` `expansion_start` ≥ `0x01200000`（VMA `0x09200000`），须在 `FontChsSym`（`0x091E0000`+slot）之后；`rom_writer` 另用 `font_slots` 末端做 floor，防空闲扫描踩进字库导致全局红字

## 相关代码

- [`src/meowth/translate_plan.py`](../src/meowth/translate_plan.py)
- [`src/meowth/pointer_redirect.py`](../src/meowth/pointer_redirect.py)
- [`src/meowth/rom_writer.py`](../src/meowth/rom_writer.py)
- [`src/meowth/font_patch.py`](../src/meowth/font_patch.py)（armips 前写入 `gen/pointer_redirect.asm`）
- [`src/util/assign_modules.py`](../src/util/assign_modules.py)
- [`configs/POKEMON_RUBY_AXVJ00/hook/main.asm`](../configs/POKEMON_RUBY_AXVJ00/hook/main.asm)
- [`configs/POKEMON_RUBY_AXVJ00/hook/gen/pointer_redirect.asm`](../configs/POKEMON_RUBY_AXVJ00/hook/gen/pointer_redirect.asm)（空桩；打包时覆盖）
