# AXVJ / 日版 Gen3 汉化（Meowth-AXVJ）

**主入口：`start_gui.bat`。** 不要混用 `Meowth-GBA-Translator`。

## 用法

1. 双击 `start_gui.bat`
2. ROM 选 `roms\origin` 里的日版（当前可跑全流程的是 **红宝石 AXVJ**）
3. Source = Japanese，Target = Chinese（选中 AXVJ 会自动填）
4. 填 API Key，**不要**勾「仅词库/种子」
5. Output 选 `roms\outputs`，开始（Extract → Translate → Build）

Build 会：打字库、按 **翻译模块** 注入（默认安全集 `ui+script_early+ime`，见 [`MODULES.md`](MODULES.md)）、Geo 地址带可选收窄、保护标题 logo 类。  
扩展剧本/名表在 GUI **勾选模块**（或 `MEOWTH_AXVJ_MODULES`）并验收，禁止写死剧情名单。  
每次 Build 写入 `<rom>.gba.build.json`（含 `modules`）与 `build_history.jsonl`，见 [`BUILD_VERSION.md`](BUILD_VERSION.md)。  
工作目录自动为输出目录同级的 `work\`（会合并其中已有的 `texts_translated.json`，避免重跑丢译文）。

「仅词库/种子」只适合调试字库；勾了剧情会大量留日文。

出问题：回退可玩 build → diff 补丁/源哈希 → 改模块划分/政策，禁止再 1+1 写死地址。

## 模块流水线 {#inject-funnel}

权威说明：[`MODULES.md`](MODULES.md) + Cursor 规则 `axvj-funnel-no-hardcode`。

注入规则集中在 [`src/meowth/axvj_modules.py`](../src/meowth/axvj_modules.py)（勾选划分）+ [`axvj_policy.py`](../src/meowth/axvj_policy.py)，**从粗到细（大→小）**，禁止在 `rom_writer` / extract 再堆平行特例与剧情地址名单：

| 级 | 只回答 | 要点 |
|----|--------|------|
| Module | 归入哪个可勾选模块？ | `assign_module`：类别 + 地址区间 |
| S0 Geography | 落在哪类区域？ | 已并入模块（script_early / birch_pool / ui_bank / junk…） |
| S1 PointerClass | 指针位是什么？ | loadword、登记**类**、local pool（非逐句 ptr） |
| S2 TargetClass | 正文能不能当文本？ | 拒低地址/title LZ/gfx；UI bank 例外 |
| S3 ContentPolicy | 译还是留日？ | **按域**；IME 五十音整类留日；毒窗口用形态规则 |
| S4 Translation | 译文从哪来？ | 种子模板 / LLM（**不**改指针） |
| S5 RewriteGate | 可否改指针？ | title gfx deny、brand skip、预期目标匹配 |
| S6 PostRestore | 误伤回滚 | `restore_false_gfx_pointers` |
| Version | 产物是谁？ | `.build.json` / 补丁树哈希 |

字库补丁：`main.asm` + `out/game.bin` + `game_addrs.asm`；源码 `hook/src/`（`game.h` + `text/PrintNextChar/`）。  
构建需 **arm-none-eabi-gcc**；见 [`HOOKS.md`](../configs/docs/HOOKS.md)。  
布局与踩坑记录见 [`configs/POKEMON_RUBY_AXVJ00/docs/CHS_TILE_LAYOUT.md`](../configs/POKEMON_RUBY_AXVJ00/docs/CHS_TILE_LAYOUT.md)。  
**不** hook ClearWindow / StringLength / TitleMenu。

## 多游戏注册表

导入时读 ROM 头 `0xAC`，经 `meowth.game_backends` 分流：

| 码 | 后端 | 状态 |
|----|------|------|
| AXVJ | `ruby_jp` | 可用 |
| AXPJ | `sapphire_jp` | 占位 |
| BPEJ | `emerald_jp` | 占位 |
| BPRJ | `firered_jp` | 占位 |
| BPGJ | `leafgreen_jp` | 占位 |

美版 ROM 会直接拒绝。

## 状态

- [x] `AXVJ` → `ruby_jp`（全量可译日文抽取；IME 五十音格保留日文；按钮/UI/剧情进翻译）
- [x] 物种/招式表按站点安全注入（能 widen 的改中文，不能的仍指向日文表）
- [x] GUI 主入口
- [ ] 其余日版后端逐个填充
- [ ] 缺 API Key 时未译文需 GUI/脚本补翻

进度条批次 = LLM 批次数。缺 Key 时无法补全新抽出的未译文。

开场博士指针在 Thumb 字面量池（S1 登记，非 loadword）。中文编码 `F9 00`；`\\p`/`\\l` → `0xFB`。

**翻译范围：** 凡日文能纳入的都译；**仅**起名输入法五十音格保留日文。强制留日名单见 `configs/POKEMON_RUBY_AXVJ00/translate/README.md`（性别主文、起名主文、选宠两条 FC 精确串等）。短标签「男孩/女孩」、时钟是/否合串走 lexicon。交付只走 `start_gui.bat` 正统流程，勿手改成品 ROM。

**回归门禁：** `scripts/check_axvj_regressions.py` — 漏斗 oracle（关键 UI 含 `F9`；title/gfx 指针不得拐进 expansion）。
