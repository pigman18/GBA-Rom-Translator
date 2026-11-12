# 当前文本协议（唯一权威，2026-11-12）

> 本文只写**现在实际在跑的**东西。中文只有一种编码：`F7 00 hi lo`。

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

## 4. 验收口径（不再看的旧项）

- `scripts/misc/verify_output_rom.py` 里还剩两项陈旧失败：
  `P25 InitWindowTileData`（该跳板 2026-08-25 已移除）、
  `Small ink 8x8`（允许区间卡在下界）。它们**不是回归**，但迟早要按新协议改写。
