---
name: bot-origin-translated-review
description: >-
  Reviews bot-captured origin vs translated GBA screenshots for UI collision,
  Japanese-to-Chinese translation coverage (JP text must not vanish or must be
  properly translated), and text color accuracy. Use when accepting bot runs,
  verifying汉化 screens, spawning sub-agents to judge frame pairs under
  work/{gameId}/bot/{scene}/{run}/, or when the user asks to check bot results
  without the old verify.py pipeline.
---

# bot：origin vs translated 验收（子代理）

采集仍由 `bot/run.py` + mGBA 完成。验收**不再**跑 `verify.py`。  
子代理必须**直接看图**对比同号帧：`origin/NNN.png` ↔ `translated/NNN.png`（以 `manifest.json` 的 `pairs` 为准）。

## 何时用

- 用户要求验 bot / 过场景 / 看汉化截图是否合格
- 打完 ROM 后要报场景结果
- 派子代理批量审 `work/**/bot/**` 某次 run

## 输入

1. run 目录：`work/{gameId}/bot/{scene}/{timestamp}/`
2. 读 `manifest.json` → 逐对打开 `origin/{NNN}.png` 与 `translated/{NNN}.png`
3. 绑定当前产物 ROM：`manifest.roms.translated.sha256` 必须等于本次要验收的 ROM

## 必须验证的三项（逐帧）

### 1）是否有撞 UI

- translated 上的文字/墨迹是否压进 origin 同位置的边框、图标、HP 条、菜单框、精灵图等非文本 UI
- 大面积花屏、色带贯穿列表/面板 → 撞 UI / 图形损坏
- 仅因中文变宽导致的合理换行，若未压坏 UI 结构，可记 note，不单凭「变宽」判 FAIL

### 2）日文文本是否正常译成中文（或至少不丢）

对 origin 上可读的日文文案（对话、菜单项、标签、说明等）：

- **合格**：translated 对应位置为正确中文，或该段策略性保留日文且完整可读
- **不合格**：日文整段消失留下空白/缺半边字/碎字；或变成乱码/残片；或关键文案未译且日文也被擦掉

至少做到：**原本的日文文本不会丢失，或者正常翻译成中文。**

专名、数字、假名玩家名等按游戏惯例保留日文可接受，但不得残缺。

### 3）文字颜色是否准确

- 相对 origin 同角色文案：主色/阴影关系是否明显跑偏（例如该黑变蓝、该白变灰绿、整行异色）
- 允许中日字形差异；不允许整块错调色板、发光色带当字色、与周围 UI 色严重冲突

## 输出格式（子代理必须遵守）

对每个 run 输出：

```text
scene: <scene>
run: <path>
rom_sha256: <manifest 中的 translated sha，或 MISMATCH>
frames: pass=<n> fail=<n> suspect=<n>
```

逐帧一行（可只详写非 pass）：

```text
NNN <step> PASS|FAIL|SUSPECT | collide=<y/n> | jp_text=<ok|lost|broken|kept_jp> | color=<ok|bad> | note=...
```

- **PASS**：三项皆可接受  
- **FAIL**：任一项明确不合格  
- **SUSPECT**：看不清、动画中、或仅轻微存疑  

场景结论：有 FAIL → 场景 FAIL；无 FAIL 但有 SUSPECT → SUSPECT；全 PASS → PASS。

禁止用旧 `verify.py` 的 g_garble / 像素哈希分数代替看图。禁止只抽几帧报「场景通过」。

## 子代理执行要点

1. 用读图能力直接打开 PNG（不要调用已删除的根目录 `vision.js`，不要跑 `bot/verify.py`）
2. 先看 origin 再看 translated，按三项打勾
3. 结果写回聊天；若用户要求落盘，写入该 run 下 `agent_verdict.md`（勿再生成旧版 `verdict.json` 伪分）
