# AXVJ UI / 文本 BUG 台账（逐项修）

原则：**一次只修一类**；出 ROM → 你测 → 说「正常」后本地 commit → 再开下一项。

## 当前进度（2026-08-09）

| ID | 现象 | 状态 |
|----|------|------|
| B01 | 存档信息框花屏 | **已验收** |
| B02 | 遇敌等 A / 内联续父串 | 基线可用 |
| B02g | 路名白边、双▼（拼接已 OK） | **已验收** |
| B02h | 出招后无限打印 / 卡死 | **已验收** |
| B02i | 战斗倒下/反作用力仍日文 | **已验收** |
| B03 | 商店 / 背包光标 | **已验收** |
| B04 | 对话等 A（▼/♥）位置偏左 | 进行中 |
| B05 | 地名细项 / 血条名 | 未修 |

## B02g — 已验收

1. **双▼**：钩 `DrawInitialDownArrow@0x3F4C` / `WaitArrow_Prepare_C`（`chs_px` 对齐 TILE_X，必要时 `TILE_OFFSET+=2`）。
2. **路名白边**：跳过 `GetMapName(fill=10)` pad，直跳 `MenuPrint`。
3. 遇敌拼接：中串 F9 内联续父串；短语 `啊！野生的\\03…` 同行。

## B02h — 出招后无限打印（已验收）

含 `FD`/`\XX` 的战斗模板禁止整串 `F9 80`；`ROM[addr-1]==FD`（extract 裁串首）亦禁。可 F900 / relocate / hook / keep。

## B02i — 战斗倒下 / 反作用力仍日文（已验收）

根因：`scan_addr_bands` 把 `0xFD`（StringExpand）当控制码跳过 → 条目从 `addr+1` 起、无指针、禁 F980 后 keep 留日；倒下模板甚至缺条。  
修复：允许 FD 起串；战斗带重扫合并；短语补 `やせいの` / `\0C倒下了` / 反作用力。

## B03 — 商店 / 背包光标（已验收）

`DrawMenuCursorEF` → `0x1E0/0x1E1`；CHS 避让到 `0x168`；列表 Linear。

## B04 — 对话等 A 符号位置（进行中）

1. 同句 `\\p`：`TILE_X = base_tx + ceil(chs_px/8)`（勿减 `CURSOR_X`）→ 商店 OK。  
2. `\n{\p}`：FE 后保持下一行光标，**禁止**按上行 `chs_px` 回画到行末（会双▼：行末静态 + 角上跳动）。只抬 `TILE_OFFSET` 防踩墨水。  
3. **译文格式**：中文把 `\n{\p}` 收成 `{\p}`（同句等 A，箭头跟在末字后）。`text_wrap.wrap_text` 对 `zh*` 做同样归一；缓存 `texts_translated.json` 已批量改过。

## 约定

你说「正常」→ 本地 `git commit`。
