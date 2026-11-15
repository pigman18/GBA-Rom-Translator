# 开始菜单残墨（开→关→开→上下）

## 复现

START 打开 → START 关闭 → START 再开 → 上下移动。  
bot：`_probe_start_reopen`（`work/.../bot/_probe_start_reopen/`）。

## 现象（像素）

- 不是饱和红；累加的是阴影灰 `(74,74,74)`。
- 修前：每路过一行在字列旁留灰影（open1→down4 新灰屑 ~104）。
- origin 同路径只在**当前光标**处多 29 灰像素。

## GDB

上下移动时只有 `RedrawMenuCursor`：`Menu_BlankWindowRect` + `Menu_PrintText(►=0xEF)`，**不重印菜单项**。

`GetBlankTileNum`（textMode3）= `TILE_BASE+1`。

## 根因

网格 `tile = TB + (row&7)*62 + 2*col` 时，band0/col0 的 lower = `TB+1`，写汉字/▶ 踩碎「空白」模板。  
光标 Blank 再把格指回 `TB+1` → 屏上冒旧阴影灰。

## 修复

`grid_tile` / 规避扫描从 `TB+2` 起，永不写 `TB`/`TB+1`。  
bot `20261114T042631`：新灰屑 29 = origin 29（仅当前光标）。

## 保存项显示成「退出」（2026-11-15）

指针/译文正确。根因：对话 band0→band6（`cursor_ty≥14`）把「とじる」(y=16) 映到与「レポート」(y=12, band6) 同槽。  
修复：remap / 对话回退仅 `CURSOR_X < 20`。详见 `SAVE_MENU_CORRUPTION.md` §10。  
bot：`work/.../bot/start_menu/20261115T180834_491109/`。
