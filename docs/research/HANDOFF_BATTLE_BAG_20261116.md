# 交付台账：战斗种名 / 血条 / 背包 / 画面撕裂（2026-11-16）

## 0. 回滚状态（接手必读）

| 项 | 值 |
|----|-----|
| 代码回滚点 | 分支 `refactor/drop-f980-slt2`，commit **`5f37bd5`**（`fix(text): clear dialogue line tail flecks by pixel width`） |
| 动作 | 丢弃未提交的种名晋升 / 背包私有 tile / 血条钩改动；删除未跟踪 `configs/.../hook/src/pokemon/`；`build.bat` + `--seed-only` 重打 ROM |
| 当前产物 | `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（与回滚后 `hook/out/game.bin` 对齐） |
| 输入底盘 | 日版 `roms/origin/POKEMON_RUBY_AXVJ00.gba`（**禁止**美版冒充） |

本轮「修种名/背包」的实验代码**不得**再当基线；下面 BUG 均相对用户实测与 bot 截图，在 **5f37bd5 基线**上仍可能存在或需另开方案。

---

## 1. 用户验收失败现象（本轮最终截图）

截图资产（Cursor assets，便于对照）：

1. `.../assets/image-63b8d238-a570-4709-af11-4fbe241719a9.png` — 背包进门乱码 / ▶ 戳首字  
2. `.../assets/image-c63cbc4f-d80b-4c6d-b243-2b09376ee382.png` — 光标到「小蘑菇」行**列表名空白**（说明框仍有文案）  
3. `.../assets/image-a388b925-799e-4558-863e-7cd1bf3b217c.png` — 用户所称**画面撕裂**（战斗 UI 上移、底黑、血条白条）

| ID | 场景 | 现象 | 严重度 |
|----|------|------|--------|
| H01 | 背包道具口袋 | **一进背包就乱码**：多行首字花屏/叠字；▶ 与首字重叠 | 高 |
| H02 | 背包上下 | 光标移到「小蘑菇」等行 → **列表侧名字消失**，只剩 `×1`；说明框可能仍正常 | 高 |
| H03 | 战斗出招/菜单 | **画面撕裂**：战斗 UI 整块上移到中场，下半屏黑；敌我血条名区白条/缺字；PP/类型框错位 | 致命 |
| H04 | 战斗血条 | 我方被打中 / 菜单态 **名称位置黑条或白条**；偶发 HP 显示异常（如 `377/115`） | 高 |
| H05 | 战斗种名 | 对话可对、血条错/截断：曾出现「落+」「蛇↑」「长手」；长翅鸥曾被读成类「长尾怪手」字形 | 高 |
| H06 | 战斗胜利 | 用户报告 **打赢后软复位/重启**（与小缓冲晋升砸栈强相关，实验分支上加重） | 高 |

口袋标签「どうぐ」仍为日文图块属预期（非本轮范围）。

---

## 2. 根因分层（已探明 / 半探明）

### 2.1 种名：展示管道 ≠ 昵称槽（算法已写清）

权威笔记：`docs/research/SPECIES_NICK_AND_BAG_ALGO.md`

| 层 | 事实 |
|----|------|
| 名表 | `0x09EB0AF4`，stride **24**，中文 F7 全文 OK |
| 结构昵称 | Get/Set 硬上限 **6B** → F7 中文默认名必截成「一字 + 半截」→ 屏上「溶+ / 落+ / 蛇↑」 |
| 对话展开 | `BattleStringExpandPlaceholders` @`0x0811C7B0` 一带；应用 **SPECIES→名表** 升全文到 `gStringVar1@0x020231F0`（JP 池，非 KEEP-US `0x020231CC`） |
| 血条 | `UpdateNickInHealthbox*` 读昵称槽；挂「就地晋升」易 **整格空白**（曾试 P43，已撤） |
| 误匹配 | 无 mon 时按「首 F7 字形扫表」会撞同首字物种（如「长*」多档）；必须 **SPECIES 或全局唯一前缀** |

**禁止**：扩昵称槽、改 F7 协议、为躲裁切改短译名。

### 2.2 背包：网格按行列映射 → 撞字 / 空白

| 层 | 事实 |
|----|------|
| 模板 | 列表 `BAG_LIST_TEMPLATE = 0x081BB544`；TB≈1，**不走** Linear（Linear 仅 tm0 且 TB≥0x180） |
| 历史 | `docs/research/BAG_LIST_TILE_COLLISION.md`：8px「×」迁址 ↔ 12px 本征互踩 |
| 本轮回归 | 为修 ▶ 幽灵改「行私有 tile + 改 left + 禁 skip」后，用户侧变为 **进门乱码 / 小蘑菇行空名** → **已回滚** |
| 光标 | ▶ 若走 band×62 公式会踩他行名槽（曾现「奇▶迹」）；专用槽与 left 右移需在**不破坏 Blank/数量列**前提下重做 |

Bot 场景（可复用）：`bot/scenes/POKEMON_RUBY_AXVJ00/bag_blank_rows.lua`（未跟踪，可保留作取证）。

### 2.3 画面撕裂 / 软复位

| 线索 | 说明 |
|------|------|
| 软复位 | `GetMonNickname` 等路径若把 **PROMOTE_MAX(19B)** 写入调用方 **≤11B** 缓冲 → 砸栈 → 战后重启。实验分支曾加重；回滚后应减轻，仍须回归确认 |
| 撕裂（图3） | UI 层整体上移 + 底黑 + 低帧；更像 **显存/任务崩溃或 VBlank 长期超时** 的结果帧，难单帧复现。优先查：战斗热路径额外 BL、错误 CpuSet 遮罩、晋升写坏接口缓冲 |
| 血条 CpuSet | P03 三池原 `0x04000008`；实验曾改 `0x04000002`。回滚后以 commit 内 `battle/hooks_origin.s` 为准 |

Bot：`battle_species_name.lua`（Route118 遇敌密采）。

---

## 3. 失败过的路线（接手勿重复）

1. **全局 / GetMonData 内嵌套晋升** → 软复位。  
2. **无 SPECIES 的中文首字形扫表** → 错种名（长手类）。  
3. **HealthboxPromote 就地晋升** → 血条名整段空白。  
4. **GetMonNickname 内晋升进 dest** → 小缓冲溢出。  
5. **背包为躲撞字盲目 skip / find_free / 改 left 公式** → 空白行或进门乱码（本轮用户否决）。  
6. **改 F7 协议 / 改短译名凑 6B** → 违反仓库铁律。  
7. **美版 ROM / 美版 decomp 当交付底** → 禁止。

---

## 4. 建议下一任顺序（大→小，动态规则）

1. **先复现 H03/H06 于 5f37bd5 产物**：确认撕裂与软复位是否仍在（与实验分支解耦）。  
2. **种名展示层**：只在大缓冲站点（StringVar / expand）按 SPECIES 升全文；血条另案（加大栈 + GetSpeciesName，或官方 Font Patch 血条几何），禁止碰协议。  
3. **背包**：在不动剧情/战斗的前提下，用 bot `bag_blank_rows` 做 leave-one-out（仅 grid 公式 / 仅 Blank / 仅光标列）；禁止再叠「又 skip 又迁址」。  
4. **撕裂**：战斗菜单 settle 连采 + origin 对照；先证明是否与中文 PrintNextChar 热路径耗时/写坏相关。  

验收纪律：出 ROM → 用户自测；场景采集用 `bot/run.py` + `bot/SKILL.md` 看图；**禁止**键盘模拟按键。

---

## 5. 相关路径速查

| 用途 | 路径 |
|------|------|
| 回滚 commit | `5f37bd5` |
| 打包 | `docs/PACK_ROM.md` |
| 种名/背包算法 | `docs/research/SPECIES_NICK_AND_BAG_ALGO.md` |
| 背包撞字史 | `docs/research/BAG_LIST_TILE_COLLISION.md` |
| 打印引擎 | `configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c` |
| 血条 CpuSet | `configs/POKEMON_RUBY_AXVJ00/hook/src/battle/hooks_origin.s` |
| 旧 UI 台账 | `docs/AXVJ_UI_BUGS.md`（B01–B08，偏早期） |

---

## 6. 一句话给接手

**代码已回到 `5f37bd5` 并重打 ROM；种名/背包实验方案作废。优先在干净基线上复现 H03 撕裂与 H01/H02 背包，用 SPECIES→名表 修展示，勿再往 6B 昵称槽或小栈硬塞全文。**
