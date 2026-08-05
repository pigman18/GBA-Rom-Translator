# AXVJ 翻译模块

| 标记 | 含义 |
|------|------|
| `!` | 脏：默认关；「全选(不含!脏)」不勾 |
| `⭐` | 新挖：默认开 |

**地址区间台账（已挖 / 全图 / 待挖）：见 [`MODULE_BANDS.md`](MODULE_BANDS.md)。**  
改模块区间前先改台账；禁止为「缩小范围」关掉整域剧本。

## 注入开关（`relocate` / `hook`）

见 [`HOOK_RELOCATE_PLAN.md`](HOOK_RELOCATE_PLAN.md)。

| 字段 | 含义 |
|------|------|
| `relocate` | `true`：允许 Python 改指针写扩展区；`false`：禁止 |
| `hook` | `true`：前序失败后生成 `pointer_redirect.asm`；默认 `false` |

路径：`in_place` → `relocate` → `upgrade`(F9 80) → `hook` → `keep`。  
地点名：`relocate=false` 且 `hook=false`。

## 安全默认（`safe`）

界面：`ui_*` / `battle_*` / `bag_ui` / `summary_ui`  
剧本：`script_rare` + `script_14`…`script_19lo`  
名表：`moves` `ability` `item` `types` `nature` + `ime`  
物种 `pokemon` **默认关**。

## 新挖摘要（0.4.3–0.4.6）

| 模块 | 说明 |
|------|------|
| `⭐battle_ui` / `battle_hud` / `battle_prompt` | 战斗菜单 FC、HUD、提示条 |
| `⭐summary_ui` / `bag_ui` | 详情标题/能力标签、背包关闭与口袋 |
| `⭐moves` / `ability` / `item` / `types` / `nature` | 名表与性格 |

脏：`!script_other` `!ui_bank_3d` `!junk_*`
