# PLAN — ROM 分发表桥接层：用官方函数替换手写实现

> 状态：**P0/P1 已实施并通过静态验证（2026-08-28）；P2/P3 已被 P1 吸收；P4/P5 暂缓**。
> 依据：`docs/调研_20260828_日版AXVJ文本引擎分发表与美版桥接评估.md`（全部静态反汇编证据）。

---

## 实施记录（2026-08-28）

### ✅ P0 标定 —— 完成

全部 5 项标定完毕，另有 2 项超出原计划的发现（见调研文档 §1.5、§4）：

| 项 | 结果 |
|---|---|
| `sub_8003EE0`（FontSubTable 第二用户） | = **TryEraseDownArrow**：先 `bl sub_8003964`，再 switch textMode；case0 直接 `bl sub_8003520(win,0)`（`0x08003F1A` 实证，**不经 FontFuncTable**，故改表不影响擦箭头）、case1 `FontSubTable[fontNum](win,0)`（`0x08003F24` 实证） |
| `sub_8003464` | tm3 内层，经 `sub_80034A8` 算 tile：`cursorTileX+(cursorX+2)+tileBase+row*30`，lower=+30 |
| `0x080032B0` | FontFuncTable 第二用户的 literal pool，宿主未标定（**不阻塞**：P1 不改表） |
| `sub_8003964` | TryEraseDownArrow 的前置判断 |
| **printer 0x1E/0x1F 空闲性** | **已证空闲**（构造函数不写 + 引擎簇零命中）。但仅 2 字节，详见 P4 |

### ✅ P1 前端瘦身 —— 完成，**−230 行**

`PrintNextChar_hook.c` **416 → 180 行**。删除并交还原生：

| 删除 | 行 | 交还 |
|---|---|---|
| `HandleExtCtrlCode` + `AXV_STATE_*` + `FC_*` | 129 | 原生 `0x08003110`（返回值 0/1/2 正确传播，实证） |
| `axv_play_bgm/play_se/clear_window` | 15 | 随 FC 0B/0C/10 交还原生 |
| FA/FB/FD/FE/FF 状态机分支 | 25 | 原生跳转表 `0x08003324` |
| `DrawInitialDownArrow` | 10 | 原生 `0x08003F4C`（`win[0x06]=0` + body，实证一致） |
| `PcsPrint_Custom`/`PcsPrint_Tm1`/`sPcs*` 两级表 | 84 | 原生 `FontFuncTable`（`FontFunc_Origin`） |
| `scene_is_buffer_printer`/`delegate`/`jp_via_chs` | 19 | 无需按窗型特判 |

保留（原生确实做不到）：F9/slot 翻译前端、菜单 ▶(0xEF) 自绘、FA/FB 的 12px 相位预对齐。

### ✅ P2/P3 —— 已并入 P1，**不单独立项**

实施中发现两者目标已被 P1 覆盖，无需再动：

- **P2（建桥接层 + 改 ROM 分发表）**：P1 之后，`PrintNextChar_Origin` 让原生自己走
  `FontFuncTable[textMode]` 两级分发，我们不需要再往表里塞指针即可获得官方分发。
  菜单 ▶ 在前端拦截即可，改表反而会牵动 `TryEraseDownArrow` 的 tm1 分支。
  **结论：不改表，只加 `FontFunc_Origin()`（读 ROM 表直接调原生）。**
- **P3（非汉字直通官方）**：`FontFunc_Origin()` 就是。另经查 `GetGlyph` 早已在用
  官方原语（`GetGlyphTilePointers_Origin` + `CopyGlyph1bppTo4bpp_Origin`），
  没有手写的 JP 解码需要替换——原估计的 −70 行里大部分本就不存在。

### 验证（全部静态，未启模拟器）

- `build.bat` 编译通过，零新增告警；`game.bin` **15,032 → 14,204 字节**（余 51,332）
- 已删函数在 `out/game.map` 中 **0 处残留**
- Meowth 完整流水线 `full --seed-only` **exit=0**，产出
  `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（30.7 MB），日志无 error/abort
- 产出 ROM 字节级核对：
  - `0x080032F8` = `ldr r1,[pc,#0]; bx r1` → `0x08800000`(EngineEntry) ✓
  - 原生字节自 `0x08003300` 起完好未被覆盖 ✓
  - `PrintNextChar_Origin@0x08800008` 重放 4 条序言后 `bx 0x08003301` ✓
  - 符号地址 `PrintNextChar_Hook=0x0880011C`、`TranslateHandleChar=0x088003E0` 与 map 一致 ✓

> ⚠️ **仍需用户实机验收**：控制码（颜色/字体切换/暂停/BGM/SE）、▼ 翻页、
> 六场景（对话/菜单/战斗/背包/图鉴/队伍）。静态只能证明链路接对了。
> 目标：**不靠重写、靠"换成调官方函数"来少写代码**，同时消除"手写实现与原生语义漂移"这一类 bug。
> 关联：`PLAN_TEXT_RENDER_REFERENCE_BRIDGE.md`（V1–V4 已落地，本方案是其延续，不是替代）。

---

## 0. 一句话

现役引擎 1734 行 C 里，有相当一部分是在**重新实现 ROM 里本来就跑得好好的东西**
（控制码处理器、状态机、箭头、tile 定位、tilemap 写入、字形绘制）。
这些官方函数**大多把关键量做成了参数**（尤其是 `sub_8003630` 把 `dst` 做成了参数），
可以直接调用。本方案分 6 步把它们换掉，并把 CHS 绘制策略**注入 ROM 的两张分发表**，
让 `PrintNextChar` 退化成一个只管字节流翻译的薄前端。

---

## 1. 官方函数可调用清单（本方案的资产表）

全部经 capstone 反汇编确认签名，可用 `scripts/dis_axvj.py` 一键复核。

### 1.1 字形 / 绘制

| 官方函数 | 地址 | 签名 | 说明 | 能替换现役什么 |
|---|---|---|---|---|
| **`sub_8003630`** | `0x08003630` | `(u32 glyph, u8 *dst, u8 fontNum, u8 fg, u8 bg, u8 shadow)` | **字形 → dst，`dst` 是参数**。内部 `GetGlyphTilePointers` + `CopyGlyph{1,2}bppTo4bpp` | `GetGlyph` 的 JP/ASCII 分支、`DecompressGlyph_Chinese` 的非 CHS 部分 |
| **`sub_8003520`** | `0x08003520` | `(win, u32 glyph)` | = 定位 VRAM → `sub_8003630` → `UpdateTilemap(win, t, t+1)`。**tm0 的一条龙** | `PcsPrint_Custom` 的 JP/ASCII 分支、`vram_tile`、`map_at` |
| `GetGlyphTilePointers` | `0x08003730` | `(u8 fontNum, u16 glyph, u8 **upper, u8 **lower)` | 4 参，**无 language 参** | 已在用（`GetGlyphTilePointers_Origin`） |
| `CopyGlyph1bppTo4bpp` | `0x08003830` | `(src, dst, fg, bg)` | 1bpp → 4bpp 调色展开 | — |
| `CopyGlyph2bppTo4bpp` | `0x080038A0` | `(src, dst, fg, bg, shadow)` | 2bpp → 4bpp | 已在用 |
| `UpdateTilemap` | `0x080036DC` | `(win, u16 upper, u16 lower)` | 写屏幕表项（会推 `win[0x1A]`，CHS 侧须 `PreserveCursorX`） | 已在用 |
| `sub_80034A8` | `0x080034A8` | `(win)` | tm3 tile 号：`cursorTileX + (cursorX+2) + tileBase + row*30`，lower = +30 | `GetCursorTileNum_Mode2` |

### 1.2 分发表（**改数据即可，无需跳板**）

| 表 | 地址 | 项 | 现役指针 |
|---|---|---|---|
| `FontFuncTable` | `0x081BB3AC` | 4 | tm0 `0x08003569` / tm1 `0x0800360D` / tm2 `0x0800338D` / tm3 `0x08003495` |
| `FontSubTable` | `0x081BB3BC` | 7 | f0,3 `0x08003585` / f1,4 `0x080035A1` / f2,5 `0x080035C9` / f6 `0x080035E5` |

各模式语义（已反汇编）：

```c
void tm0(win, glyph){ sub_8003520(win,glyph); win->tileDataOffset(0x18)+=2; win->cursorTileX(0x1B)+=1; }
void tm1(win, glyph){ FontSubTable[win->fontNum](win,glyph);                win->cursorTileX(0x1B)+=1; }
void tm2(win, glyph){ sub_8003630(glyph, win->buffer(0x20), fontNum, fg,bg,shadow); win->buffer(0x20)+=0x40; }
void tm3(win, glyph){ sub_8003464(win,glyph);                               win->cursorTileX(0x1B)+=1; }

void FontSub_f0_f3(win,glyph){ UpdateTilemap(win, tileBase+glyph*2,        tileBase+glyph*2+1); }
void FontSub_f1_f4(win,glyph){ UpdateTilemap(win, tileBase+Map[glyph*4],   tileBase+Map[glyph*4+1]); }
```

> `FontType1Map` 步长是 **4 字节/项**（`lsls r3,r3,#2`），不是 2。
> `FontSubTable` 表长是 **7**（第 8 word = 0x00010408 非指针）——现役 `sPcsTm1FontFuncs[8]`
> 配 `fontNum & 7` 有读越界风险，顺手修。

### 1.3 控制码 / 状态 / 窗口

| 官方函数 | 地址 | 替换现役 |
|---|---|---|
| `HandleExtCtrlCode` | `0x08003110` | `PrintNextChar_hook.c` L226-324（99 行手写） |
| `DrawInitialDownArrow` | `0x0800304C` | L216-225（10 行）+ `DrawGlyphTiles_arrow_prepare` 部分 |
| `Text_ClearWindow` | `0x08003BA8` | `axv_clear_window` 包装 |
| `PlayBGM` / `PlaySE` | `0x080724AC` / `0x080724CC` | 随 FC 0B/0C 交还原生 |
| `PrintNextChar` 跳转表 | `0x08003324` | FA/FB/FC/FD/FE/FF 六个分支（约 40 行） |
| `InitWindowTileData` | `0x08002A50` | （参考：预渲染 256 字 × 2 tile 的官方写法） |

---

## 2. 桥接层架构（4 层）

```
┌─ 层 0  原生（不动）───────────────────────────────────────────┐
│  PrintNextChar 0x080032F8    字节取指 + 控制码 + 状态机 + 分派  │
│  HandleExtCtrlCode 0x08003110 · DrawInitialDownArrow 0x0800304C│
│  sub_8003630 字形→dst · sub_8003520 一条龙 · UpdateTilemap      │
│  GetGlyphTilePointers · CopyGlyph{1,2}bppTo4bpp · sub_80034A8  │
└───────────────────────────────────────────────────────────────┘
                            ▲ bl / 表项回调
┌─ 层 1  桥接（新增，ROM 数据补丁）─────────────────────────────┐
│  .org 0x081BB3AC  .word Chs_Tm0|1   ...  ×4                    │
│  .org 0x081BB3BC  .word Chs_Sub_f0f3|1  ... ×7                 │
│  共 11 个 word。纯数据，零跳板、零压栈、零寄存器争夺。           │
└───────────────────────────────────────────────────────────────┘
                            ▲
┌─ 层 2  策略（新增 C，签名与原生一致：void (*)(win, u32 glyph)） ┐
│  Chs_Tm0 / Chs_Tm1 / Chs_Tm2 / Chs_Tm3                          │
│  Chs_Sub_f0f3 / Chs_Sub_f1f4 / Chs_Sub_f2f5                     │
│  内部二选一：                                                    │
│    非汉字 → 直接 bl 原生对应函数（一行）                          │
│    汉字   → 走 CHS 12px 路径（分配 tile + 两趟写 + 推进 12px）    │
└───────────────────────────────────────────────────────────────┘
                            ▲
┌─ 层 3  前端（瘦身后保留）─────────────────────────────────────┐
│  PrintNextChar_Hook：只做 F9 / slot 字节流翻译                   │
│    命中 → 消费字节、推进 index、return 1                         │
│    未命中 → index−1，bx 回原生 0x080032F9 全权处理               │
└───────────────────────────────────────────────────────────────┘
```

**关键契约**：层 2 函数签名与原生表项**完全一致**（`r0=win, r1=glyph`），
所以能直接塞进表层，不需要任何 trampoline。

**层 3 回跳原生的注意点**（已核实）：
`TranslateHandleChar` 拦截**每一个**字节（`c != 0xF9` 时走 `slot_lookup_and_draw`），
不只是 F9。所以薄前端必须保留 slot 查表；未命中时要把 `textIndex` 减 1 再
`bx 0x080032F9`，让原生重取该字节。

---

## 3. 分阶段实施

### P0 — 标定（零代码改动）

按调研文档 §4 完成 5 项标定：`sub_8003EE0` 的 case1/case3、`sub_8003464`、
`0x080032B0` 归属、`sub_8003964`、**printer 0x1E/0x1F 是否空闲**。
工具：`scripts/dis_axvj.py`。**阻塞 P2/P4，必须先做。**

### P1 — PrintNextChar 瘦身为 F9 前端 · **净减 ≈194 行** · 风险中

| 删除 | 行 | 交还给 |
|---|---|---|
| `HandleExtCtrlCode` | 99 | 原生 `0x08003110` |
| FA/FB/FC/FD/FE/FF 六分支 | 25 | 原生跳转表 `0x08003324` |
| `AXV_STATE_*` enum + `FC_*` defines | 30 | 随上 |
| `axv_play_bgm/se/clear_window` 包装 | 15 | 随 FC 0B/0C/10 交还原生 |
| `DrawInitialDownArrow` | 10 | 原生 `0x0800304C`（**相位对齐 `arrow_inplace12` 保留**，单独小 hook） |
| `DrawMenuCursorEF` | 31 → 移入层 2 | 净 −10 |

`PrintNextChar_hook.c`：416 → **约 222 行**。

> 验收：build 绿 + 实机过「对话 / 菜单 / 战斗 / 背包 / 图鉴 / 队伍」六场景，
> 重点看 FC 控制码（颜色、字体切换、暂停、BGM/SE）与 ▼ 箭头翻页。

### P2 — 建桥接层 · **新增 ≈120 行** · 风险中

- `src/text/bridge_table.c`（新）：7 个 `Chs_*` 薄函数 + 一张 11 项的地址表
- `src/text/hook_origin.s` 增补：11 个 `.org ... .word` 数据补丁
- 本阶段**先全部直通原生**（汉字分支留空/回退现役实现）→ 行为应完全不变

> 验收：build 绿 + 六场景行为与 P1 前逐帧一致（这是纯重构，不应有任何视觉变化）。

### P3 — 非汉字直通官方 · **净减 ≈60–80 行** · 风险低

| 删除 | 行 | 换成 |
|---|---|---|
| `GetGlyph` 的 JP/ASCII 分支 | ~30 | `sub_8003630(glyph, dst, fontNum, fg, bg, shadow)` |
| `GetCursorTileNum_Mode2` | 6 | 原生 `sub_80034A8` |
| `map_at` 中可由 `UpdateTilemap` 承担的部分 | ~20 | 原生 `UpdateTilemap` + 分配器 |

> 验收：像素级 A/B（打包两版让用户同屏对照）；重点看血条（tm2）与菜单（tm3）。

### P4 — 相位入 printer 结构 · **净减 ≈95 行** · 风险中

> **2026-08-28 实施结论：本步已标定完毕，但暂不改动，理由见下。**

现役把 12px 半列相位存在**全局 8 槽 LRU 表**（`0x0203FF80`，`chs_bind_pitch_slot` 55 行
+ `chs_pitch_key` + `pitch_reset` + `ChsPitchCtrl` 结构 ≈ 95 行），靠 16 位"行指纹"匹配，
这是**串台类 bug 的结构性来源**。

#### 标定结果（一手，可复核）

| 证据 | 结论 |
|---|---|
| `InitTextPrinter @0x08002C68`（构造函数）反汇编 | 只初始化 **0x04–0x1D**；**0x1E / 0x1F / 0x20 一字未写** |
| 全 ROM 带重同步反汇编（43 万条指令）过滤引擎簇 0x08002800–0x08004800 | **+0x1E / +0x1F 零命中**（+0x1B 有 22 处、+0x1D 有 18 处 —— 扫描方法有效性对照） |
| 引擎簇 0x18–0x30 逐偏移扫描 | 0x1E–0x1F、0x21–0x2B、0x2D、0x2F–0x30 零命中；0x20 有 4 处（tm2 缓冲指针） |
| 结构体布局 | 0x1C cursorY / 0x1D cursorTileY / **0x1E-0x1F 填充** / 0x20 u32 缓冲指针 |

→ **0x1E/0x1F 是 0x20 处 u32 的对齐填充，可证空闲（2 字节）。**
0x21–0x2B 在引擎簇同样零命中，但**无法静态排除非文本子系统共用同一块 IWRAM**，风险不可控。

#### 为什么暂不改：状态需要 8 字节，可证的只有 2 字节

实测相位状态**四个字段全在使用**（`text_render.c` 实证）：

| 字段 | 用途 | 行 |
|---|---|---|
| `chs_pitch_key` (u16) | 行指纹，槽位绑定 | 109 / 119 |
| `chs_px` (u16) | 行内已绘像素（相位本体） | 321 / 375 / 436 |
| `base_tx` (u8) | 行首表项列，tilemap 落点 + 失配检测 | 321 / 371 / 436-452 / 554 |
| `write_op` (u8) | 布局策略（`text_scene.c:162` 消费） | 164-171 |
| `char_base` (u8) | 指纹的一部分 | 108 / 119 |

共 **8 字节**，只有 `last_adv` 是纯记账（可省）。2 字节装不下。

若只把 `chs_px` + `write_op` 搬进 0x1E/0x1F，剩余 `base_tx` / `pitch_key` / `char_base`
仍要全局槽，`chs_bind_pitch_slot` 的 LRU 主体删不掉——收益从 −95 掉到 −30 左右，
却要承担"相位重置时机"这个**必须实机迭代**的语义风险。

> 历史教训（`game.h` 注释）：旧页游标表落在 0x0203FFD2 游戏数据区，
> 曾是**背包/队伍死机**的根因。相位/串台区是全项目最脆的部分。

#### 后续若要做（按顺序）

1. 先确认 printer 数组步长：gdb 日志见 printer @0x0202E5DC 与 0x0202E658 相距 **0x7C**；
   若确为数组元素，则 0x24–0x7B 可能是同记录的其它字段，**不能占用**；若只是两个
   独立全局，则 0x21–0x2B 可用。
2. 确认后再把整个 `struct ChineseTileState` 搬进 printer（建议落 0x24，8 字节对齐），
   此时 LRU / 指纹 / 驱逐 / 失配检测全部可删，−95 行且结构性消串台。
3. 相位重置时机改为显式：换行（FE）由原生推进 `cursorTileY(0x1D)`，
   可用 `cursorTileX(0x1B) <= base_tx` 判新行（现役已有此逻辑，见 436 行）。

### P5 — tile 分配器统一 · **净减 ≈100–150 行** · 风险高、回报高

官方引擎只用一个游标管所有分配：`win->tileDataStartOffset(0x016) + win->tileDataOffset(0x018)`。
现役则在 `game.h` 里散落了几十个场景魔数（`CHS_TILE_POOL_END`、`CHS_LINEAR_STICKY_END`、
`CHS_MENU_LINEAR_FLOOR`、`CHS_MODE2_FOOTER_BAND`、`CHS_SHOP_DESC_POOL_END`……）
并在 `text_scene.c`（234 行）里逐场景门控。

目标：把分配收敛成一个"按 (charBase, template) 分带的 bump 分配器"，
让 `text_scene.c` 从"逐场景特判"退化为"少量例外表"。

> **建议单独立项、最后做**，不要和 P1–P4 混在一起。

---

## 4. 量化汇总

| 阶段 | 净增减 | 累计 | 风险 | 前置 |
|---|---|---|---|---|
| P0 标定 | 0 | 1734 | 无 | — |
| P1 前端瘦身 | **−194** | 1540 | 中 | P0 部分 |
| P2 建桥接层 | **+120** | 1660 | 中 | P0 完成 |
| P3 直通官方 | **−70** | 1590 | 低 | P2 |
| P4 相位入结构 | **−95** | 1495 | 中 | P0 第 5 项 |
| P5 分配器统一 | **−125** | ~1370 | 高 | P3 |

**保守口径：1734 → 约 1370 行（−21%）。**

必须诚实说明：**桥接层不会让代码腰斩。** 12px 推进、半列相位、CHS 字模落位、
场景门控这四块是日版汉化的固有复杂度，换任何架构都消不掉。
桥接层的真实收益是两条，比行数更重要：

1. **删掉"重建原生语义"的那 ~270 行** —— 控制码、状态机、箭头、tile 定位。
   这些代码与 ROM 里跑着的原版是两份实现，任何一处漂移都是 bug 源。删掉即消除整类风险。
2. **风险从"我们的状态机"收敛到"推进语义"一处** —— 状态机交给已验证 20 年的原生代码，
   我们只负责"下一个字画在哪"。

---

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| 改 `FontSubTable` 会波及 `sub_8003EE0`（擦 ▼ 箭头） | P0 必须标定其 case1/case3；擦箭头走 tm0 时是**直接 bl `sub_8003520`**，不经 `FontFuncTable`——替换 tm0 时要单独确认 |
| `FontFuncTable` 有第二个用户 `0x080032B0` | P0 标定；若它是另一条打印路径，替换后必须一并验证 |
| 层 3 回跳原生时 `textIndex` 回退被 slot 逻辑干扰 | slot 未命中路径单独写测试串（含 F9 与非 F9 混排） |
| `UpdateTilemap` 会推 `win[0x1A]` | 现役已有 `UpdateTilemap_PreserveCursorX`，桥接层沿用，**勿省** |
| 官方 `DrawGlyphTile` 族**不含背景清扫**（upstream 由 `ClearTextSpan` 先铺底） | 桥接层必须保留现役 `draw_tile` 的清底段（见 `PLAN_TEXT_RENDER_REFERENCE_BRIDGE.md` 附 §3） |
| `FontSubTable` 只有 7 项 | 现役按 8 项建的 `sPcsTm1FontFuncs` 越界读，P2 一并修正为 7 |
| 一次性改太多难定位回归 | 严格按 P0→P1→…→P5 单步推进，每步一个 build 验收点 + 实机六场景 |

---

## 6. 与既有 PLAN 的关系

- 本方案**不替代** `PLAN_TEXT_RENDER_REFERENCE_BRIDGE.md`；V1–V4（vendored
  `reference/pokeruby/draw_glyph_tile.c`、`reference/pokeemerald/copy_glyph_to_tiles.c`、
  equivalence 对照器）**继续保留**，那是"绘制数学"的官方来源。
- 本方案解决的是**另一层**：谁来决定"下一个字画在哪、用哪个绘制函数"。
  这层现在由 1734 行手写 C 决定，改为由 ROM 分发表 + 官方原语决定。
- 待拍板的 甲/乙/丙（旧 PLAN 附）中，本方案**推荐走"乙"的加强版**：
  不在 `draw_tile` 层面切换 runtime 实现，而是**在分发点切换**（更外、更粗、更安全）。

---

## 7. 待用户拍板

1. 是否按 P0→P5 推进？（还是只做 P1+P2 先拿确定性收益）
2. P4（相位入结构）是否授权先做一轮 printer 结构体字段标定？（是 P4 的唯一前置）
3. P5（分配器统一）是否另立一案、放到最后？
