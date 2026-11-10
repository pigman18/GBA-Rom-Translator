# F7 编码协议改造方案（方向 2 的第一步）

> 目标：把 `F9 00 hi lo`（4 字节/汉字）改成 `F7 hi lo`（3 字节/汉字），
> 与火红一致，让 stride=8 的定长表能放下 2 个汉字。
>
> 撰写时间：2026-11-04
> 前置状态：方向 1/2/3 均未动手，本文档是**动手前的实施方案**。

---

## 一、为什么必须先做这一步

实测数据（`scripts/research/ruby/probe_geometry_ff.py`）：

| 编码 | stride=8 表放 2 汉字 | 结论 |
|---|---|---|
| `F9 00 hi lo`（4B/字） | 9B | ✗ 放不下 → 只能走 F980 |
| `F7 hi lo`（3B/字） | 7B | ✓ 放得下 |

招式名 354 + 特性名 77 = **431 条**，现在全部因为「差 1 字节」被迫走 F980 运行时查表。
换成 F7 后这 431 条可直接原地写入，**零运行时开销**。

这也是用户最初判断「f7、f9 能减少 1 位编码」的实质收益。

---

## 二、0xF7 字节可用性：已验证安全

三支脚本交叉验证：

| 检查项 | 结果 |
|---|---|
| 名称表区 `0x1CA000..0x1CC000`（902 串） | 含 F7 的串 **0** ✅ |
| 剧情文本区 `0x1C0000..0x1D0000`（1,741 串） | 含 F7 的串 **0** ✅ |
| UI 文本区 `0x1D0000..0x1E0000`（605 串） | 含 F7 的串 **0** ✅ |
| 全 ROM 34,311 个 F7 | 集中在代码段与 Thumb `bl` 指令（`ff f7 xx fe`），非文本 |
| 现有 hook 行为 | `PrintNextChar_hook.c:161` `if (cur_char >= 0xF7u) return 1;` 已把 0xF7 当不可印位消费 |

**唯一冲突点：`charmap.py:26` 的 `_DEFAULT_IDEOSPACE = bytes([0x01, 0xF7])`**
用于全角空格，产物里出现 535 次，build.json 有 24 条用到。**必须改成别的表示**（见 §五）。

---

## 三、协议设计

### 现状（F9 双通道）

```
F9 00 hi lo      单汉字（内联，4 字节）
F9 80 hi lo      短语引用（5 字节，含 FF）
FF               终止
```

### 目标（F7 单通道 + 保留 F9 短语）

```
F7 hi lo         单汉字（内联，3 字节）        ← 新增
F9 80 hi lo FF   短语引用（不变）             ← 保留
FF               终止
```

**为什么保留 F9 80 短语表？**
短语表解决的是「整段文本复用」（10,595 条短语），
它和「单字编码粒度」是两件正交的事。火红没有短语表，
但火红是「整表换指针数组」，不需要短语表来省字节。
我们换指针表之后短语表也可以退场，那是方向 1 的后半程，不是这一步。

### 渲染侧改动

**关键约束（已核实 `text_translter.c:78-99`）**：
```c
lead_trail_ok(lead, trail):   lead 必须在 0x01..0x1E（排除 0x06 / 0x1B）
pack_glyph_index(lead,trail): 压缩成 16 位 gidx，上限 CHS_FONT_GLYPH_MAX = 7168
```
**F7 直接复用同一套 `pack_glyph_index`，字库和码位分配完全不用改。**

`TranslateHandleChar()`（`text_translter.c:396`）现在是：

```c
if (c != CHS_ESCAPE)              // 不是 F9
    return slot_lookup_and_draw(win, c);
```

改为（在 slot 查表**之前**插 F7 分支）：

```c
if (c == 0xF7) {                  // 新增：F7 hi lo
    text = (const uint8_t *)(uintptr_t)win_u32(win, WIN_TEXT_PTR);
    idx2 = win_u16(win, WIN_TEXT_INDEX);
    p = text + idx2;
    if (!lead_trail_ok(p[0], p[1])) {
        win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 2));
        return 1;
    }
    gidx = pack_glyph_index(p[0], p[1]);
    win_set_u16(win, WIN_TEXT_INDEX, (uint16_t)(idx2 + 2));   // 消费 hi lo
    if (gidx < CHS_FONT_GLYPH_MAX)
        PrintGlyph(win, gidx, CHS_GLYPH_ADVANCE_PX);
    return 1;
}
if (c != CHS_ESCAPE)
    return slot_lookup_and_draw(win, c);
```

**必须同步改**：`PrintNextChar_hook.c:161` 的
```c
if (cur_char >= 0xF7u) return 1;    // ← 会把 F7 在进 TranslateHandleChar 前就吃掉
```
改成 `if (cur_char > 0xF7u) return 1;`，否则新编码永远进不来。

### 宽度计算同步

`phrase_width_px()`（`:452`）/ `GetStringWidth()`（`:478`）都要加 F7 分支：
```c
if (b == 0xF7) { w += CHS_GLYPH_ADVANCE_PX; i += 2; continue; }
```
注意 F7 只消费 **2 字节**（hi lo），不是 F9 的 3 字节（op hi lo）。

---

## 四、改动清单

### Python 侧

| 文件 | 改动 |
|---|---|
| `src/meowth/charmap.py:384-391` | 内联汉字从 `extend(escape_bytes + enc)` 改成 `extend([0xF7] + enc)` |
| `src/meowth/charmap.py:26` | `_DEFAULT_IDEOSPACE` 改掉 `0xF7` 依赖 |
| `src/meowth/translate_plan.py` | 编码长度判断自动跟随（用 `len(encoded)`，无需改逻辑） |
| `src/meowth/config_loader.py:56` | 协议注释更新，加 `F7_GLYPH = 0xF7` |

### C 侧

| 文件 | 改动 |
|---|---|
| `include/game.h:287` | 加 `#define CHS_GLYPH_F7 0xF7u` |
| `text/PrintNextChar_hook.c:161` | `>= 0xF7u` → `> 0xF7u` |
| `text/text_translter.c:396` | `TranslateHandleChar()` 加 F7 分支 |
| `text/text_translter.c:452` | `phrase_width_px()` 加 F7 分支 |
| `text/text_translter.c:478` | `GetStringWidth()` 加 F7 分支 |
| `pokedex/UnusedPrintMonName_hook.c:105` | 确认宽度计算兼容 |

### 不需要改的

- `F9 80` 短语表（`build_rom_data.py`、PhraseTable）
- `F9 00` 通道保留（向后兼容旧 build.json）
- SLT2（这一步不动）
- 12px 渲染（这一步不动）

---

## 五、`0x01 0xF7` 全角空格的处理（已查清）

**根因**：`charmap.py:130` 把全角空格 `　`(U+3000) 映射成 `self._ideospace_bytes`，
默认值 `_DEFAULT_IDEOSPACE = bytes([0x01, 0xF7])`（`charmap.py:26`）。

**实测用法**（`probe_ideospace.py`）：build.json 只有 **24 条** target_hex 含 `01f7`，
且这 24 条全是**短语表引用**（`f9 80 1f 70 ff …`），`01 F7` 实际在短语正文里，
不在 ROM 槽位里。译文里**没有任何 ASCII 空格或全角空格字符**——
说明它们来自日文原文的 `\01` 变量占位（`\\01さん` → `\01`），不是排版用的空格。

**结论：这是一个纯映射项，改起来零风险。**

| 选项 | 做法 | 评价 |
|---|---|---|
| **A（推荐）** | `char_to_bytes["　"] = bytes([0x00])`，全角空格统一用日版原生空格 | 最干净。全角空格在中文排版本就不常用 |
| B | 换一个未占用的两字节组合 | 需再查可用性，收益为零 |
| C | 让 F7 分支先判断前一字节是否 0x01 | 脆弱，代码复杂化 |

**实施**：只改 `charmap.py:26` 的 `_DEFAULT_IDEOSPACE = bytes([0x00])`，
并同步 `char_to_bytes["　"]`。产物里那 535 个 `01 F7` 会变成 `00`。

**验证**：改完重打包，确认 `build.json` 里 `01f7` 计数归零，
且 `\\01` 变量占位（如「向\01询问」）仍能正常显示玩家名字。

---

## 六、验证方式

**阶段 1（不跑模拟器）**
1. 单测 `charmap.encode("拍击")` → 期望 `F7 00 03 F7 00 63 FF`（7 字节）
2. 比对改前/改后 build.json 的 `target_hex` 长度
3. 确认 stride=8 的招式名/特性名条目从 `replace+F980` 变成 `replace+F7`

**阶段 2（用户实测）**
- 打 ROM → 进队伍界面、招式界面、商店
- 检查点：中文显示正常、无乱码、无错位
- 对比改前基线截图

**阶段 3（回归）**
- 跑完整场景基线（`docs/BASELINE_SCENES.md`）
- 确认 F980 条目数从 7,144 降到约 6,713（减少 431）

---

## 七、风险与回滚

| 风险 | 应对 |
|---|---|
| `0xF7` 与某界面已有控制码冲突 | 已用 3 个文本区验证（含 F7 串 = 0）；若实测仍有问题，回滚 `game.h` 的 `> 0xF7u` |
| 全角空格改 `0x00` 排版变窄 | 先只改这 24 条，实测确认 |
| 宽度计算漏改导致换行错位 | `phrase_width_px` + `GetStringWidth` 两处都改，并检查 `UnusedPrintMonName_hook.c` |
| 12px 渲染与 F7 步进不一致 | 本步不改步进（仍 `CHS_GLYPH_ADVANCE_PX=12`），只改编码字节数 |

**回滚**：git 层面只需回滚 `charmap.py` + 3 个 C 文件；ROM 用 `--seed-only` 重打包即可。

---

## 八、预期收益

| 项 | 改前 | 改后 |
|---|---|---|
| 单汉字编码 | 4 字节 | **3 字节**（-25%） |
| stride=8 表能放 | 1 汉字 | **2 汉字** |
| 招式名 F980 条目 | 352 | 约 0（2 字内的） |
| 特性名 F980 条目 | 77 | 约 0 |
| 短语表总字节 | 不变 | 略减（正文里 F9 00 → F7） |

---

## 九、与方向 1 / 3 的关系

- **方向 1**：F7 让 431 条脱离 F980，但 3 字以上的名字仍需整表换指针表。F7 是方向 1 的**前置减负**，不是替代。
- **方向 3**：F7 不改步进（仍 12px），所以与渲染重构解耦。方向 3 独立推进。
- **顺序**：F7 → 实测 → 方向 1 → 方向 3。
