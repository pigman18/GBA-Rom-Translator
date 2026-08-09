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
| B03 | 商店 / 背包光标 | 进行中 |
| B04–B05 | 地名细项 / 血条名 | 未修 |

## B02g — 已验收

1. **双▼**：钩 `DrawInitialDownArrow@0x3F4C` / `WaitArrow_Prepare_C`（`chs_px` 对齐 TILE_X，必要时 `TILE_OFFSET+=2`）。
2. **路名白边**：跳过 `GetMapName(fill=10)` pad，直跳 `MenuPrint`。
3. 遇敌拼接：中串 F9 内联续父串；短语 `啊！野生的\\03…` 同行。

## B02h — 出招后无限打印（已验收）

含 `FD`/`\XX` 的战斗模板禁止整串 `F9 80`；`ROM[addr-1]==FD`（extract 裁串首）亦禁。可 F900 / relocate / hook / keep。

## B02i — 战斗倒下 / 反作用力仍日文（已验收）

根因：`scan_addr_bands` 把 `0xFD`（StringExpand）当控制码跳过 → 条目从 `addr+1` 起、无指针、禁 F980 后 keep 留日；倒下模板甚至缺条。  
修复：允许 FD 起串；战斗带重扫合并；短语补 `やせいの` / `\0C倒下了` / 反作用力。

## B03 — 商店 / 背包光标（进行中）

商店/背包列表光标都是 `InitMenu` → `Menu_PrintText(0xEF)`（上下两块 BG tile）。  
根因：中文与 FontFunc **共用 tile 池** → ▶ 被盖成碎块。  
- `0x3E4` 固定槽：越界踩 screenblock（窗框被盖）  
- avoid→`0x1D0`：摘要「文字替换」  
- 钩 `Menu_PrintText` 再 `RedrawMenuCursor`：易踩坏 ▶ 绘制，光标又碎  

现修法：`DrawMenuCursorEF` → 块内 `0x1E0/0x1E1`；中文仅这对避让到池内 `0x168`（**不**进 `0x1D0`）；列表 Linear；拆掉 `Menu_PrintText` 钩。

## 约定

你说「正常」→ 本地 `git commit`。
