# AXVJ 开场 / 早期 UI 地址登记表

机器可读表：[`src/meowth/axvj_intro_addrs.py`](../src/meowth/axvj_intro_addrs.py)

**本表 ⊂ 漏斗 S1（PointerClass）**，不是平行注入政策。  
改写安全、分区、内容策略见 [`axvj_policy.py`](../src/meowth/axvj_policy.py) 与 [AXVJ.md](AXVJ.md#inject-funnel)。

## 结论（对应截图）

| 画面 | 分类 | 说明 |
|------|------|------|
| 博士扔球「ポケットモンスター / すなわち…」 | **ui_bank + birch_pool** | 指针 `0x79B8` → 字符串在 **UI 区** `0x3E9670`，不是普通 `0x14xxxx` loadword 剧情。 |
| 男女孩对话「おとこのこ？…」 | **birch_pool** | 指针 `0x7D34` → `0x197B09`。中文注入曾导致性别 UI 白屏；`axvj_policy.SKIP_ZH_INJECT_ORIGINALS` 强制留日。 |
| 左上「おとこ / おんな」 | **menu_tile / menu_ui** | UI 短标签 `0x3E9630` 一带，与对话行分开。 |
| 「じぶんできめる」 | **menu_ui** | ROM 内无空格；与对话种子分开维护。 |

## 分类含义

- **birch_pool**：低地址 Thumb 字面量池指针（S1 登记）。
- **ui_bank**：字符串本体在 `0x3E9440–0x3EB000`（S0 Geography）。
- **menu_tile / menu_ui**：短菜单；种子在 S4。
- **story_loadword**：常规剧情（`0F xx` + 指针），不在本表。

## 维护

新增开场指针时只改 `axvj_intro_addrs.py` 登记表；**不要**在 `rom_writer` 再加 site deny。假 LZ / UI bank 例外由 `axvj_policy` 统一处理。
