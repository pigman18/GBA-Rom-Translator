# Gen3 台词对照语料（离线抓取）

来源：[abcboy101/poke-corpus](https://github.com/abcboy101/poke-corpus)  
在线检索：[Poké Corpus](https://abcboy101.github.io/poke-corpus/)（可勾 RS / FRLG / Emerald + JPN Kana）

| 目录 | 文件 | 用途 |
|------|------|------|
| `RubySapphire/` | `ja-Hrkt_msg.txt` / `en_msg.txt` / `qid_msg.txt` | 红蓝宝石日文假名 + 英文 + 消息 ID |
| `FireRedLeafGreen/` | 同上 | 火叶 |
| `Emerald/` | 同上 | 绿宝石 |

## 用途（util）

[`POKEMON_RUBY_AXVJ00.yaml`](../configs/POKEMON_RUBY_AXVJ00.yaml) 的 `texts.msg_corpus` → `msg_filter`：

- 剧情 / 训练家：`msg_filter` + 对白形态（`*story_bias`）
- UI：`msg_filter` + 短标/控制符（`*ui_bias`）
- 特殊：仅 `msg_filter`（整表导出时收差集）
- 词条 / 说明：**不引用**语料闸；说明 scan 用模块内启发式

### 整表导出：地址先到先得

顺序：词条/说明 → 前期/中期剧情 → 训练家对白 → 后期剧情 → UI界面 → 特殊文本。

特殊全 ROM + 仅语料 = **剧情/UI 未占用的语料命中**（差集靠顺序，不是单独差集 filter）。

### 单模块导出：`shadowed_by`

`--module X` 会干跑 yaml 里排在 X 之前的模块，对「整表里本会被前面抢走」的条目写 `"shadowed_by": "<模块id>"`（仍保留原文），控制台汇总 `FCFS shadow: N/M …`。

路径相对 `src/util/work/`（本目录的上级）。

说明：

- 仅作对照/搜针/filter 真源，**不是**日版 ROM 注入基座。
- AXVJ 定址仍靠本机 ROM + util export。
- 语料常见全角空格 `　`、`\n`/`\c`/`\r`、`[PLAYER]` 等，经 yaml `mapping` 对齐 Meowth `decode_pcs`。
- `msg_filter`：exact/norm → `rapidfuzz` Top-K 召回 → 剥控制/`[TAG]`/变量前缀后 **soft_key 全等**才命中；`min_plain_chars`（AXVJ 语料为 3）拒绝纯控制符/过短串。
- [wikiwiki.jp/poketext](https://wikiwiki.jp/poketext/) 常 403，勿依赖。
- 网上**没有**现成 AXVJ「地址+全文」表。

重抓：`python src/util/work/_fetch_poke_corpus.py`

抓取日期：2026-08-11
