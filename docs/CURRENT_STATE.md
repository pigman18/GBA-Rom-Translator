# 当前状态（单一事实源）

> **本文件是唯一权威的「现在什么有效、什么已证伪」。**
> 其它文档与本文冲突时，以本文为准；本文更新日期写在标题。
>
> 最后更新：2026-11-18
> 产物基线：分支 `refactor/drop-f980-slt2`，HEAD `f5ab01c`，
> ROM `8BE7B0FE0D3C95DB3CC5BBF022A82741902D5FBC26F171236526139CF17AE513`

---

## 一、代码现状

| 项 | 状态 |
|---|---|
| 渲染引擎 | `hook/src/text/PrintNextChar_hook.c`，纯函数 tile 网格（`DESIGN_TEXT_12PX_GRID.md`） |
| arena 上界 | **绝对值 `GRID_TILE_LIMIT = 0x1F0`**（当前代码就是这样） |
| 已修好的场景 | 背包列表、宝可梦详情特性说明、训练家之眼列表、开始菜单、设置、商店、宝可梦中心、图鉴详情 |
| 已知坏掉的场景 | 战斗对话框/菜单/招式表（整框空白）、图鉴列表名字列、训练家详情道路名 |

---

## 二、已证伪的路径（**不要重试**）

| # | 路径 | 证伪方式 | 文档 |
|---|---|---|---|
| 1 | `grid_band()` band0→5 重映 | 命中 summary/背包窗 → 特性说明叠印、背包整行空白 | `BUG_LEDGER_20261118.md` |
| 2 | 背包窗「又 skip 又迁址」 | 用户侧变进门乱码/空名 | `HANDOFF_BATTLE_BAG_20261116.md` §3.5 |
| 3 | 全局 / GetMonData 内嵌套种名晋升 | 战斗后软复位 | 同上 §3.1 |
| 4 | HealthboxPromote 就地晋升 | 血条名整段空白 | 同上 §3.3 |
| 5 | 修 `GetSpeciesName` 上限 → 修血条名 | **本轮实测无效**（血条读昵称槽 6B，非名表） | `TEST_GETSPECIESNAME_NO_EFFECT_20261118.md` |
| 6 | stride 反推语义（手抄站点/ldr 前找 lsls/按寄存器追踪） | 4 次尝试，覆盖率 7%→57%→80%→41%，越改越差 | `STRIDE_FAILED_4TIMES.md` |
| 7 | 扩容 charBase / tile 分配器 / PHYS 池 / 场景门控 | 用户判定「没一个场景能看的」 | `DESIGN_TEXT_12PX_GRID.md` §1、§9 |
| 8 | 12px 缓存 / 相位变体 / 私有区 48×8 | 已证死路 | `START_HERE.md` §3.6 |
| 9 | 改 F7 协议 / 改短译名凑容量 | 违反仓库铁律 | `AGENTS.md` |

---

## 三、文档冲突裁决

### 冲突 1：arena 上界该用绝对值还是相对值？

| 文档 | 说法 | 时间 |
|---|---|---|
| `DESIGN_TEXT_12PX_GRID.md` §9 | 禁止扩容 charBase / tile 分配器 | 11-13 |
| `BATTLE_EMPTY_TEXT.md` §6 | 已实施 `grid_arena_hi(tb) = tb + 0x1F0`，验收通过 | 11-15 |
| `BUG_LEDGER_20261118.md` | 用绝对值，改成 `TB+0x1F0` 会写坏 UI 图标 | 11-18 |

**当前裁决**：代码用绝对值 `0x1F0`（HEAD `f5ab01c` 的实际状态）。
11-18 曾按 `BATTLE_EMPTY_TEXT.md` 改回相对值，**被用户回滚**，理由是
战斗菜单虽然出字了但菜单项残缺（「背包」显示成「一モ」）。

⇒ **未解决**。下次动这块必须先确认：相对上界是否真的会写坏
`0x1F0/0x1F1`（菜单 ▶）、`0x1E8..0x1FF`（Summary/图鉴图标）。
判据：改后跑 `battle_menu_audit` + `pokemon_menu` + `dex` 三场景，
量这三处图标区的像素是否被覆盖。

---

## 四、当前 BUG 优先级（按可测量性，不按严重度）

| # | BUG | 可测量判据 | 状态 |
|---|---|---|---|
| 1 | 战斗对话框/菜单整框空白 | `battle_menu_audit` f045 对话框墨量（origin 1360） | 未修，根因已定位（arena 越界） |
| 2 | 图鉴列表名字列全 `------` | `dex` f035 名字列墨量 | 未修，根因未定位 |
| 3 | 训练家详情道路名空白 | `navigator` f114 框内文字墨量（origin 182） | 未修，代码位置已定位 |
| 4 | PP/属性框灰底 | 像素统计（origin FFFFFF×1491 vs D6D6CE×1299） | 未修 |
| 5 | HP `377/115` | — | 未修 |
| 6 | 敌方名牌假名错序 / 我方日文 | — | 未修（血条走昵称槽，见 §二.5） |
| 7 | `｜｜begin▁of▁sentence｜｜` 泄漏 | 文本搜索 | 未修 |

---

## 五、工具与验证（已就绪）

| 用途 | 命令 |
|---|---|
| 编译 hook | `cd configs\POKEMON_RUBY_AXVJ00\hook; .\build.bat` |
| 打包 | `meowth full --seed-only`（AGENTS.md Build Rules） |
| 单场景 | `python bot\run.py POKEMON_RUBY_AXVJ00 <scene> --save bot\scenes\POKEMON_RUBY_AXVJ00\saves\Route118_68-7.sav` |
| 全量批跑 | `python work\batch_all.py` |
| 审图 | 子代理 `provider=qoder, model=gfmodel` |
| 探针 ROM | 直接改 `roms\outputs\*.gba` 副本，用 `--translated <path>` 跑 bot |

**探针 ROM 技巧**（本轮验证有效）：不用改源码重编，直接对产物 ROM
打单字节补丁 → 跑 bot → 看效果。适合快速证伪假设。
