# 字体调试工具集（给你的，给 Cursor 也行）

三个 Python 脚本，全部在 WSL / Linux / macOS 直接跑，不依赖 Windows。

---

## 1. check_font_layout.py —— 上 ROM 之前先过这关

**作用**：自动判断你的 `.bin` 是不是正确的 128B/glyph TL+BL+TR+BR 4bpp 布局。

```bash
python3 check_font_layout.py font_chs.bin --max 64
```

✅ 通过：
```
✅ File: font_chs.bin  size=917504  glyphs=7168  (128B each)
Checking first 64 glyphs...

=== Result: 64/64 glyphs OK ===
Layout looks correct. Safe to load at ADDR_FONT_CHS_NORMAL.
```

❌ 挂了（典型输出）：
```
⚠️ glyph #0  ink=  0  size=0x0  rows[0-0] cols[0-0]
           • only 0 ink px — likely wrong glyph or blank
⚠️ glyph #1  ink= 23  size=16x16  rows[0-15] cols[0-15]
           • height 16px → not a 12px font (too tall)
           • top padding has 8 ink px (expect 0 for 12-on-16)
           • bottom padding has 6 ink px (expect 0)
           • LEFT half all empty (possible TL/BL swapped or 1bpp?)

=== Result: 58/64 glyphs OK, 6 with problems ===
Likely causes:
  • TL/BL/TR/BR order wrong → regenerate with correct quadrant order
  • Source was 1bpp not 4bpp → repack as 4bpp (2 pixels/byte, high nibble=left)
  • Not a 12-on-16 font → redo BDF→tile with 2 rows top+bot padding
  • Index mismatch → check pack_glyph_index() vs your TBL
```

**这套诊断信息直接贴给 Cursor**，它就知道该改哪。

---

## 2. view_font_chs.py —— 肉眼看字对不对

**作用**：把 `.bin` 按 128B 拆成 16×16 图，终端打 ASCII 预览 + 出 PNG 网格。

```bash
# 终端看第一个字的长相
python3 view_font_chs.py font_chs.bin --index 0

# 出一张 4×4 网格 PNG（前 16 个字）
python3 view_font_chs.py font_chs.bin --count 16 --out preview.png --cols 4
```

终端输出示例（应该看到“宝”字轮廓，上下两行是 `.` 空白）：
```
--- ASCII preview of glyph #0 (bytes 0x00..0x7F) ---
................
................
...██......██....
..████....████...
..████....████...
.██████..██████..
.██████..██████..
...██........██..
...██........██..
..█████..█████..
.██████..██████..
.██████..██████..
..████....████...
...██......██....
................
................
Legend: . = 0(透明)  █ = 15(墨)  数字/符号 = 中间色(阴影)
Expected for an inked 12px glyph: rows 2-13 have █/heavy chars,
rows 0-1 and 14-15 are '.' (padding). Left/right 4 cols may also be '.'.
```

**判断标准**：
- ✅ 上下各 2 行是 `.`、中间 12 行有 `█` → 布局正确
- ❌ 16 行全 `.` → 字模是空的，索引错
- ❌ 字在左下角、右上角空 → TL/BL/TR/BR 排错了
- ❌ 全屏 `█` 噪点 → 这是 1bpp 当 4bpp 解的，让 Cursor 重转

---

## 3. bdf_to_font128.py —— BDF → 正确 128B 格式

**作用**：把你桌面上那份 `font_zh_12x12.bdf` 转成游戏能直接认的 128B/glyph 二进制。

```bash
python3 bdf_to_font128.py font_zh_12x12.bdf font_chs.bin
```

输出：
```
Loaded 16565 glyphs from font_zh_12x12.bdf
Emitting 16565 glyphs (0x20 .. 0x9fff)
✅ Wrote font_chs.bin  (2120320 bytes, 16565 glyphs)
   Load at ADDR_FONT_CHS_NORMAL, each glyph = 128B (TL+BL+TR+BR 4bpp)
```

然后立刻跑 check：
```bash
python3 check_font_layout.py font_chs.bin --max 32
```
全 ✅ 再灌进 ROM。

---

## 给你的标准排查流程（3 步）

```
第1步  check_font_layout.py  → 全过才进第2步
第2步  view_font_chs.py     → 肉眼确认"宝可梦查看能力"轮廓对
第3步  灌进 ADDR_FONT_CHS_NORMAL，断 DrawGlyph_Chinese 看 gidx
```

任何一步挂了，**把错误输出原样贴给 Cursor**，比口头描述"字是乱码"有用 10 倍——它会拿到精确诊断（哪个象限空、padding 有没有墨、是不是 1bpp）直接改对应代码。

---

## 给 Cursor 的备注（可粘）

> 字体工具链：
> - `check_font_layout.py`：自动校验 128B/glyph 4bpp TL+BL+TR+BR 布局，检查 12-on-16 padding、象限非空、高度≤14px
> - `view_font_chs.py`：ASCII + PNG 可视化，确认字形轮廓
> - `bdf_to_font128.py`：BDF → 128B 4bpp，ink=15, shadow=14, 0=transparent
>
> 字体 .bin 必须过 check 脚本才能灌 ROM。当前乱码问题优先怀疑：
> 1. .bin 是 1bpp 而非 4bpp（全屏噪点 → 用 bdf_to_font128 重转）
> 2. TL/BL/TR/BR 象限顺序错（字偏一角 → 改 tile 拼接顺序）
> 3. pack_glyph_index() 的 TBL 与文本 F9 lead/trail 不是同一套
> 4. ADDR_FONT_CHS_NORMAL 指向的 region 大小 ≠ glyph_count × 128
