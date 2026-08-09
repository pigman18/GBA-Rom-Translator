# AXVJ UI / 文本 BUG 台账（逐项修）

基线：`git` 工作区已于 2026-08-09 **整棵回滚到 HEAD**（含本轮 PhraseResume / 内联短语 / 商店 `base_tx` / PrintSave 16B 等未提交改动）。  
原则：**一次只修一类**；出 ROM → 你测 → 过了再开下一项；禁止顺手叠几何/lexicon。

## 修复顺序（推荐）

| 序 | ID | 现象 | 疑似根因（域） | 允许动的文件 | 勿碰 |
|----|-----|------|----------------|--------------|------|
| 0 | BASE | 回滚后基线确认 | — | 仅打包 | 一切源码 |
| 1 | B01 | 存档信息框假名/乱纹 | `PrintSave*` 栈拷 7–8B，中文 `F9 00×2+FF` 丢 `FF` | `hook_origin.s` + `game_addrs.asm`（PrintSave*） | `print_next_char` / draw_* |
| 2 | B02 | 遇敌/逃敌/出招残首字；放技能狂打至死机 | `redirect_phrase_stream` 弃父串，Phrase `FF`=整句 EOS；resume **必须 IWRAM**（禁 game.bin `.bss`） | **仅** `print_next_char.c` + `game.h` 地址常量 | draw_* / MapName / 存档 |
| 3 | B03 | 地名弹窗白边突出 / 残留 | `DrawMapNamePopup` 格宽 vs 12px；或窗口清图 | `get_string_width.c`（MapName_*）及 MapName armips；必要时独立清窗 | 短语 resume / 商店 |
| 4 | B04 | 商店/背包光标脏 | 列表 `left==14` 与 12px 墨水盖光标 OBJ | **仅** `draw_scene.c` / `draw_glyph.c` 几何 | 短语 / 存档 / MapName |
| 5 | B05 | 血条昵称乱码 | `textMode==2`→FontFunc；与 CpuSet 24B 补丁正交 | healthbox 专用路径（另开） | 对话 Phrase |

## 分类详表

### B01 — 存档信息框

- **复现**：继续游戏界面左上信息（地名/徽章/图鉴/时间）花屏；底栏提示可能仍正常。
- **机制**：固定 `memcpy` 长度 < 中文槽 `F9 00 ×2 + FF`（9B）→ 无终止符 → 打印扫栈。
- **状态**：曾用扩栈+`mov r2,16` 修过；**已随回滚丢掉**，需按序重做。
- **验收**：信息四行中文清晰，无假名拖尾。

### B02 — 战斗短语切流（高危）

- **复现**：遇敌/逃敌/出招后角上留对方名首字（如「溶」）；放技能后无限打字至花屏死机。
- **机制**：战斗串嵌入 `F9 <op> hi lo` → 切到 PhraseTable；流末 `FF` 被原版当整窗 EOS；`GetStringWidth` 已 `index+4` 续父串，打印未对齐。
- **失败教训**：
  1. `static` PhraseResume 进 `game.bin` `.bss`（ROM）→ 写入无效，等于没修。
  2. 纯字形「一次画完整句」→ 打乱地名一字一帧，白边/顶出加重。
- **预定修法**：IWRAM `PhraseResume`（如 `0x0203FFF0`）+ 仍逐字切流 + 流末 `FF` 前 pop；**禁止**整句内联。
- **验收**：遇敌/逃敌/出招整句完整；放技能不狂打；地名（B03）不得回退。

### B03 — 地图名弹窗

- **复现**：进入地图时「××市/道路」白底相对外框错位；严重时白条突出且弹窗消失后残留。
- **机制**：日版用 `StringLength`（字节）居中；中文已有 `MapName_DisplayCellLength`（按 px/8）。回滚后应先确认是否仍坏；若基线正常则 **B02 不得再动 MapName**。
- **验收**：弹出时框与字对齐；消失后无白块残留。

### B04 — 商店 / 背包光标

- **复现**：选商品/道具时光标处图块脏、叠字或盖住箭头。
- **机制**：列表列与 12px 墨水/Mode2 池几何冲突（与 B02 短语 EOS **不同根因**）。
- **验收**：光标清晰；列表字不盖箭头；图鉴 No/球标不回归。

### B05 — 血条昵称

- **复现**：战斗血条上昵称乱码。
- **机制**：`textMode==2` 不走 CHS；`UpdateNickInHealthbox` CpuSet 长度另案。
- **验收**：昵称可读；不影响对话窗。

## 已回滚的失败尝试（勿直接重复合并）

- game.bin `.bss` PhraseResume  
- `draw_phrase_inline` 整句绘制  
- 商店 `scene_is_shop_bag_list` + `base_tx=1`（未经验收）  
- 扩大 Mode2 / ink-only / 图鉴 icon 带宽试验（历史会话）

## 当前进度

| ID | 状态 |
|----|------|
| BASE | 已确认：地名弹窗正常（2026-08-09） |
| B01 | 进行中：PrintSave 扩栈+拷 16B；待你测存档信息框 |
| B02–B05 | 未修 |

下一动：你验收 B01（存档信息四行清晰、无假名拖尾；地名仍正常）→ 再开 B02。
