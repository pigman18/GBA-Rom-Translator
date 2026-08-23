# 日版 AXVJ 原生文本管线运行时分析（text_jp2chs 全面接管·调研期产出）

> 日期：2026-08-23
> 证据来源：`src/util/gdb_patcher.py` 文本埋点 × 6 轮采集（17:28–17:45，日志 8.5MB / 17898+ 行），
> 监听点 `InitTextPrinter / PrintNextChar / CtrlHnd_A..G / BattleBufferGlyph / DrawInitialDownArrow / TextClearWindow`，
> 对照 `docs/AXVJ_TEXT_PIPELINE.md` 静态反汇编结论。
> 目的：为「全新打印引擎 `hook/src/text_jp2chs.c` 全面接管日版打印（订钉上移至 PrintNextChar 入口、零回落）」提供设计输入。

---

## 一、原生分发结构（静态 + 运行时双重确证）

```
PrintNextChar @0x080032F8
  ├─ r4 = win；index++ @win+0x14；c = text[index]
  ├─ c ≥ 0xFA ? → 控制码跳表（7 项字面量表）      ← 本次埋点主战场
  │     FA → 0x08003354        FB → 0x0800334A
  │     FC → 0x08003362        FD → 0x08003342
  │     FE → 0x08003346        FF → 0x0800333C
  │     （表首还有一项 0x08003324，本次全程零命中）
  └─ 否则 → RegularGlyph @0x0800336E
        └─ FontFuncTable[textMode] @0x081BB3AC（CallViaR2）
```

**关键修正**：此前 game_addrs.asm 认为「日版无 0xFC 控制码链」仅对了一半——
日版确实没有 pokeruby 式 switch 比较链，但存在**跳表版扩展控制码**（见 §三），
`F9` 因为 < 0xFA 才落到 RegularGlyph 成为我们现在的入口。

## 二、控制码语义表（R1 · 运行时铁证）

| 码 | 处理器 | 命中 | 前置 state | 关联行为（运行时对账） | pokeruby 对应 |
|----|--------|------|-----------|------------------------|---------------|
| FA | 0x08003354 | 19 | 全为 2 | → DrawInitialDownArrow×19，**无清屏** | `CHAR_PROMPT_SCROLL`（▼+滚动翻页） |
| FB | 0x0800334A | 79 | 全为 2 | → 箭头 + 之后 `Text_ClearWindow`×79（79:79 完全对账） | `CHAR_PROMPT_CLEAR`（▼+等A后清屏） |
| FC | 0x08003362 | 621 | 多为 1 | 打字中最高频；带参数子类型（§三） | `EXT_CTRL_CODE_BEGIN` 家族 |
| FD | 0x08003342 | 74 | 多为 1 | 占位符 `FD + id`（\FD xx） | `PLACEHOLDER_BEGIN` |
| FE | 0x08003346 | 182 | 2 为主(135)、1 为次(47) | 换行 | `CHAR_NEWLINE` |
| FF | 0x0800333C | 1261 | 1(952)/2(309) | 结束；对话关闭时清屏×115 | `EOS` |

对账数据：箭头总命中 98 = FA 19 + FB 79（无一遗漏、无一多余）；
清屏 197 = ff 后 115 + fb 后 79 + 杂项 3（非文本路径调用）。

**EF（0xEF，< 0xFA 走 RegularGlyph）**：观测 94 次 `ef → ff` 相邻（菜单 ▶ 后即串尾），
印证 ▶ 由 FontFunc 当普通字形处理——现有 `DrawMenuCursorEF` 拦截点不变。

## 三、FC 子类型形态（字节流实测）

```
fc 01 01          ×67    ← 类型1 + 1 参数（前景色？）
fc 05 05 fc02 …   ×61    ← 类型5 + 1 参数（调色板/字体？）
fc 04 0d 0e 0f    ×61    ← 类型4 + 3 参数（三色全设：fg/bg/shadow）
fc 02 02 a4a9     ×14    ← 类型2 + 1 参数（背景色？）
```

- 形态与 pokeruby `sExtCtrlCodeFuncs` 族高度同构（01=FG、02=BG、04=AllColors(3参)…）。
- 流内常连续出现多个 FC（`fc0101fc02…`），且 `ff/1 → fc/1` 迁移 285 次：
  **对话开窗后先发一串 FC 设色再打字**——引擎接管后必须在 FF 收尾/新窗开始处正确处理这些。
- 参数长度表待 Phase B 静态反汇编 FC 处理器（12B 主干，疑似再委托子函数）确认；
  可参照 `meowth/pcs_codes.py::fc_arg_count` 交叉验证。

## 四、win->state 字段（@+0x04）观测

| 观测点 | 值 |
|--------|-----|
| `InitTextPrinter` 完成时 | **恒为 0**（1190/1190） |
| 打字过程 PncEntry 采样 | 1×8005、2×5533、0×1189（0 多见于刚初始化） |
| FA/FB 命中前置态 | **全为 2** |
| FC/FD 命中前置态 | 几乎全为 1 |
| 相邻迁移 | 态内稳定（1→1、2→2 占绝对多数），跨态迁移稀少 |

初步解读（待反汇编定论）：0=初始/BEGIN；1、2 为两种运行常态
（疑似「可否被打断/自动播放」或「普通 vs 提示等待」维度的标记）。
**引擎设计输入**：控制码处理器需要原样复刻各 handler 对 state 的写入值——
这是 Phase B 唯一的硬性 RE 剩余项（七段 handler 合计 <100 字节 Thumb）。

## 五、血条缓冲 FontFunc[2]（R2 · 已破案）

监听 `BattleBufferGlyph @0x0800338C`，297 次命中全部来自 win=`0x020231CC`：

- **win+0x20 = u32 当前写指针**（EWRAM，任务起始 ≈0x02000000）；
- 每字形写入后**指针 +0x40**（upper 32B + lower 32B 两 tile）；
  实测指针序列 `…0000→0040→0080→…→0520→0560→05A0→05E0→0620…`
- 新打印任务时指针回卷基址（#14 样本回到 0x02000000）；
- win+0x16/+0x18（TILE_BASE/OFF）全程恒 0——缓冲模式完全不碰 BG tile 编号；
- 字符样本含假名+拉丁混合（A6/A3/B5/9F/84 + 'Q''a''s''T''e'），
  即调用方随后用 CpuSet 把整块缓冲刷进血条 OBJ VRAM。

**引擎实现口径**：缓冲模式 = 用现有 CHS 组合字模（TL/BL）按 shadowed 重映射着色后
写 `[win+0x20]` 指向处 0x40B，再 `+= 0x40`。中文昵称因此可以直接上血条。

## 六、全面接管设计输入汇总（Phase B 规格）

1. **订钉点**：P01 从 `0x0800336E` 上移到 `0x080032F8`（PrintNextChar 整函数替换）。
2. **引擎职责**（零回落）：
   - 取字符/index 推进（复刻原生前 8 条指令语义）
   - 六个控制码处理器（§二表）+ FC 子类型分派（§三）
   - EF 菜单▶（现有 `DrawMenuCursorEF` 并入）
   - F9 协议（内联汉字/短语表）+ SlotTable 查找（现有逻辑平移）
   - 可印字形：VRAM 路径（两趟 8+N spill，现有引擎）+ **新增缓冲路径（§五）**
3. **留原生**：帧级状态机/节奏（延迟、等键）、`InitTextPrinter` 窗口生命周期、
   滚动/清屏的执行体（引擎只按语义触发同等效果：FB→等A后清屏由原生完成，
   引擎负责画箭头前的相位同步）。

## 六A、Phase A 反汇编定案（2026-08-23 补全，capstone 实测）

### 分发器与跳表（0x080032F8）

```
push {r4,lr}; r4=win
index=u16[win+0x14]; u16[win+0x14]=index+1      ; u16 回绕推进
c = *(u8*)(u32[win+0x10] + (u16)index)
r0 = c-0xFA; if r0>5 → RegularGlyph@0x336E
r0<<=2; r1=[pc-rel]=0x08003324(表基址); pc=[表+r0]
```

**勘误**：0x08003324 是跳表**基址**（前文误列为 handler），表内 6 项：

| 码 | handler | 精确语义（指令级） | 返回 |
|----|---------|--------------------|------|
| FA | 0x3354 | `DrawInitialDownArrow(win); state←9` | 2 |
| FB | 0x334A | `DrawInitialDownArrow(win); state←8` | 2 |
| FC | 0x3362 | `return sub_8003110(win)` | 子结果 |
| FD | 0x3342 | `state←7` | 2 |
| FE | 0x3346 | `state←6` | 2 |
| FF | 0x333C | `state←0` | 0 |

state 写入值与 pokeruby WIN_STATE 枚举**同号同义**（6=NEWLINE、7=PLACEHOLDER、
8=WAIT_CLEAR、9=WAIT_SCROLL、0=END；FC 内另有 4=PAUSE、5=WAIT_BUTTON、10=WAIT_SOUND）。
RegularGlyph 尾：FontFunc[textMode](win,char) 后 `return 1`。

### FC 子处理器 sub_8003110（类型字节 1–16，>16 默认返回 2）

| 类型 | 语义 | 写入 | 参长 |
|------|------|------|------|
| 01/02/03 | FG/BG/Shadow 色 | win+C / +D / +E | 1 |
| 04 | 三色全设 | C,D,E ← 连续3B | 3 |
| 05 | 调色板 | win+F | 1 |
| 06 | 字体切换 | win+B ← arg | 1 |
| 07 | 默认字体 | win+B ← template[8] | 0 |
| 08 | 暂停 | state←4；win+09 ← arg | 1 |
| 09 / 0A | 等 A / 等音效 | state←5 / 10 | 0 |
| 0B / 0C | PlayBGM / PlaySE | u16 LE → 0x080724AC/CC | 2 |
| 0D | Escape（直印一字） | FontFunc[textMode](win,arg) | 1 |
| 0E / 0F | 移列 / 移行 | win+1B += arg / win+1D += arg | 1 |
| 10 | 清窗 | Text_ClearWindow(0x08003BA8) | 0 |

### 缓冲路径

- **FontFunc[2]** @0x338C：`BlitGlyphTiles(char, [win+0x20], font=win[B], FG=C, D, E)`
  → 缓冲布局 upper@[ptr+0]、lower@[ptr+0x20]，然后 `[win+0x20] += 0x40`。
- **FontFunc[1]** @0x360C：`SubTable[win[B]](win,char)` 后固定 `cursorTileX(+1B)+=1`。
  （textMode==1&&fontNum==4 即 RenderTextHandleBold 加粗缓冲。）

### Phase A 前 RE 清单 → 已全部闭环 ✅

- [x] 七段 handler 语义 + state 写入值（本节表）
- [x] FC 子类型参数长度表（本节表）
- [x] 0x08003324 用途＝跳表基址（勘误）

## 六B、Phase B/C 交付状态

- 文件：`configs/POKEMON_RUBY_AXVJ00/hook/src/text_jp2chs.c`（约 1100 行）
- 入口：`ProcessCurrentChar_C(win)`——整函数替换原生 PrintNextChar；
  返回值契约：可印/F9/slot/EF=1，FF=0，FA/FB/FD/FE=2，FC=子结果。
- 结构对照 text.c：§1 常量/枚举 → §2 协议原语 → §3 相位槽 → §4 像素件+场景门控 →
  §5 单tile盖章(DrawGlyphTile_ShadowedFont 合一) → §6 tile编号(Linear/Mode2+保护带) →
  §7 两趟核心 → §8 打印家族(含缓冲分流) → §9 取址分发(bit15) → §10 单字节分发 →
  §11 F9 协议 → §12 SlotTable → §13 控制码处理器(FA-FF+FC 16型) → §14 主入口 →
  §15 过渡出口(P05/P04/EF钩+宽度工具)。
- 验证：arm-none-eabi-gcc（build.bat 同款 flags，-Wall）独立编译零错误零警告；
  nm 符号面与 game.h 声明一致。

**Phase C 换装（2026-08-23 完成）**：
- `entry.s`：旧 PrintNextChar 编组/回落跳板移除，新增 `EngineEntry`（=bin 起点，
  r0=win 尾跳 ProcessCurrentChar_C）；Hook3/MapName/WaitArrow 跳板不变。
- `hooks_origin.s` P01：订钉 0x0800336E → **0x080032F8**，`ldr r1,=(JP2CHS_Entry|1)`。
- `main.asm`：bin 起点标签改名 `JP2CHS_Entry`；`game.ld` ENTRY(EngineEntry)；
  build.bat / Makefile 链接清单换为 text_jp2chs.o（旧 8 个 text 钩子对象移出，
  源文件保留作回滚基线）；game_addrs.asm 删除已无引用的 PrintNextChar_RegularGlyph。
- 成品 ROM 实测字节验证（roms/outputs/*_translated.gba）：
  - P01@0x32F8 = `00 49 08 47 | 01 00 80 08` ✓（→ JP2CHS_Entry）
  - 旧 RegularGlyph@0x336E 恢复原生机码（死代码，引擎不回落）✓
  - P02@0x3730、P05@0x3F4C 不变 ✓
- 待用户实测验收清单：开场白/NPC 多页对话（FA/FB 翻页、FE 换行）、开始菜单 ▶、
  商店买卖、战斗血条昵称（新缓冲路径）、图鉴、命名界面。

## 七、埋点工具备注

- 本轮新增 yaml 点 11 个 + handler 3 个（`PrintNextChar`/`WinDump`/`BattleBufferGlyph`）
  + `_win_fields()` 统一摘要行，已随仓库提交可用。
- 经验教训：**handler 按 yaml `name` 匹配注册**——`CtrlHnd_*` 因名字错配走了通用日志
  （仅 r0-r3，r4 不显），靠「PncEntry 字节流首字节 → 下一个 CtrlHnd 命中」的时序对照
  补齐了映射；后续复采时应把 handler 名直接命名为 `CtrlHnd_A..G` 或统一改挂。
- 日志字节流为小写 hex；分析脚本正则须 `[0-9A-Fa-f]`。

---

## 七、修正记录：队伍名空白 bug（2026-08-23）

**误判纠正**：textMode==1&&fontNum==4（队伍名列表）不是 win+0x20 缓冲。RE 定案：

- FontFunc[1] @0x0800360C：按 fontNum 查二级子表 @0x081BB3BC →
  SubTable[4]=0x080035A0：upper=TILE_BASE+map[2g]、lower=TILE_BASE+map[2g+1]
  （map=sFontType1Map@0x081B34A8）→ 直接 UpdateTilemap(0x036DC) 写表项；
  尾部统一 cursorTileX++。＝美版 WriteGlyphTilemap_Font1_Font4 原生同构，
  纯 BG 表项驱动（256-tile 预渲染块由场景初始化装载，实测 TILE_BASE=1 起）。
- 日版两条独立包装：@0x02CC0 RenderTextHandleBold——Init 后强制 textMode←2
  并写 win[0x20]=dest（这才是缓冲路径）；@0x02CFC 通用打印包装——保留模板
  mode1/font4（队伍名列表走此条，对应日志 LR=0x02D14）。
- 另证：InitTextPrinter 每次调用重置全部游标字段（日志"残留值"是断点在函数体
  执行前读到的上一轮末态），行间无累计依赖。

**结构修正（对齐 pokeruby 分发模式）**：

- 删除 is_buffer_printer() 全局风控；改为 sChsPrintGlyphFuncs[8] 表驱动
  （索引=win->textMode）：{Field,Field,Buffer,Field,×4预留}，越界回落 Field 行。
- 全面接管后原生 FontFuncTable 不再被查询，此表即唯一打印分发器；扩展新
  textMode（含自定义 ≥4 值）＝表尾追加一行，未来可为专属 CHS 模式订新值到场景模板。
- mode1 窗口改走 Field 行＝Linear 动态 tile 上载 + 原生 UpdateTilemap 写表项，
  与原生 SubTable[4] 语义同构（tile 来源不同：动态合成 vs 256 预渲染）。

重建出包后字节验证 P01 落位正常（00 49 08 47 | 01 00 80 08）。
