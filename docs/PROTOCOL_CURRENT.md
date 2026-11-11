# 当前文本协议（唯一权威，2026-11-11）

> 本文只写**现在实际在跑的**东西。`F9 00` 原地写、`F9 80` 短语引用、`SLT2` 运行时表、
> `PhraseTable` 位宽——**全部废弃**，不要再按它们做设计；还在产物里的死重量见 §4。
> 历史分析（为什么废弃、当年怎么量出来的）已随 `RUBY_ENCODING_CURRENT.md`、
> `TASKS_2026-11-04_archive.md` 一起删除，需要考古请查 git 历史。

## 1. 编码：`F7 00 hi lo`（4 字节/字）

```
F7 00 hi lo          单个汉字，hi/lo 是字库码位（pack_glyph_index）
F7 00 hi lo ... FF   整串，FF 结尾
```

- 每个汉字固定 4 字节；无「槽里放不下」这一说 —— 放不下就换写入方式（§2），不换编码。
- 渲染：`GetGlyph → PrintGlyph → DrawGlyphTiles`，12px 步进（`CHS_GLYPH_ADVANCE_PX`），
  字库 `FontChsNormal @ 0x09000000`，每字 128B。
- **自由长度**：`append_stream()` 按 4 字节组消费，不受原版「5 字节 + 遇 00 截断」限制。
  这是后缀注入（P07 `UnusedPrintMonName`）能直接拼 `宝可梦` 的前提。

## 2. 写入：只有 relocate（指针重定向到扩展区）

`meowth full` 的正常输出是 `0 replaced, 6938 relocated` —— **没有原地改写**。

```
plan → rows_writer → 扩展区成串落盘 → redirects 改指针
```

- 放不下 = 指针不够 / 表结构是「基址 + index×stride」→ 走
  `struct_trampoline`（就地折名字指针）或整表搬走 + 改基址字面量。
- 定长表的 stride 编译进代码（`index×stride` 乘法展开），**不可变**；要变长就改读点。
- 任何「缩短译文」「改译文去迁就槽」都不是方案（见 `docs/DONT.md`）。

## 3. 运行时 hook 面（当前生效）

| 点 | 地址 | 作用 |
|---|---|---|
| P01 `PrintNextChar` | `0x080032F8` → EngineEntry | 全面接管打印（12px 引擎 + 协议解析） |
| P04 `MapNamePopup` | — | 地名弹窗居中 |
| P07 `UnusedPrintMonName` | `0x0808DD60` | 图鉴分类名复制函数 + 注入 `宝可梦` 后缀 |
| P08 `DrawOptionMenuChoice` | — | 选项高亮 |
| P03 `Main` | — | 帧同步 |

## 4. 产物里的死重量（待清理，不影响功能）

| 残留 | 现状 | 说明 |
|---|---|---|
| `SLT2` 空表 @ `0x09EA0000` | 还在，`n_buckets=256`、**全桶为空**（`texts.json` 已无任何 `slot:true` 模块） | `text_translter.c` 仍会在每个非 F7/F9 字节上先查它，查不到才走正常绘制；纯开销 |
| `PhraseOffsets` / `PhraseTable` @ `0x08810000` / `0x08820000` | 还在，内容已是 `F7 00 …` 流 | 只剩 `GetStringWidth()` 的 `op != 0` 分支在读；`F9 80` 引用已清零 |
| `F9 80` | **实测已无有效引用**（32MB 里 33 处 `F9 80` 字节对，全是数据噪声） | 不要再用 |

清理顺序建议（每次只动一个、动完跑 bot 全场景）：先 `SLT2` 空表 + 查表分支（纯删除，
有 `texts.json` 无 `slot:true` 兜底）→ 再 `PhraseTable`（要先把 `GetStringWidth` 的
短语分支改成「整串按 F7 计宽」）。

## 5. 验收口径（不再看的旧项）

- `scripts/misc/verify_output_rom.py` 里还剩三项陈旧失败：
  `P25 InitWindowTileData`（该跳板 2026-08-25 已移除）、
  `PhraseTable F9 00 流`（现在表里是 F7 流，判据过期）、
  `Small ink 8x8`（允许区间卡在下界）。它们**不是回归**，但迟早要按新协议改写。
