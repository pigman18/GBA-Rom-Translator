# text.c 设计文档（text_jp2chs 重构案）

> 状态：已实施并收敛（2026-08-24：只 hook PrintNextChar，见文末 §九）
> 前置阅读：`docs/ruby_jp_en_compare.md`（美日对照）、`docs/ruby_jp2chs_bug_review.md`（旧引擎复盘）
> 目标文件：`configs/POKEMON_RUBY_AXVJ00/hook/src/text.c`
>   （原名 `text_ruby_jp.c`，2026-08-24 改名；引擎只 hook PrintNextChar，
>    除 `PrintNextChar` 与导出工具 `GetStringWidth_PCS` 外全部 static）
> 旧文件 `text_jp2chs.c` 及旧多文件引擎（原 `hook/src/text/`）归档于
> `src/text_jp2chs.c` / `src/bak/text/`，**移出构建**

---

## 一、设计原则（来自复盘的硬约束）

1. **一行一语义，无二次分发**：`sPrintGlyphFuncs[textMode]` 每行 = 一种日版原生
   FontFunc 语义；行内不得按 font/charBase/场景再猜路径。
2. **行间零共享可变状态**：TILE_OFFSET 属 tm0 专属；分配游标按 charBase 分区；
   跨行写入共享字段 = 互相踩踏（复盘 Bug6 根因）。
3. **字体是每字形属性**：同一文本流内混合多种字形（全角拉丁/假名/汉字/数字），
   font 与尺寸由 GetGlyph **逐字形**返回，不是窗口常量。
4. **UNKNOWN 诊断行**：未验证的 tm/fn/font 组合一律消费不绘制（返回 1）——
   游戏内"缺字"即排查信号，禁止猜测性回落。
5. **引擎状态只放固定 EWRAM**（BSS 陷阱，复盘 Bug0）。

## 二、数据流（严格 pokeruby 形状）

```
win->text[textIndex++]                    ← 原生取码（u32 c）
  │ 控制码 FA..FF / FC 子表 / EF          ← 原生语义平移（已定案）
  ▼
GetGlyph(win, c) → struct Glyph           ← 唯一取址入口（替代直接查字库）
  │   { tiles[128](TL,BL,TR,BR 归一化 0/E/F), width(px 8/12), bank }
  ▼
sPrintGlyphFuncs[textMode](win, &glyph)   ← 按 tm 分发绘制
  ▼
sWriteGlyphTilemapFuncs[fontNum](...)     ← 按 fn 分发表项写入
  ▼
UpdateTilemap(win, nCols, t0..t3)         ← 表项落格（支持 1/2 列）
```

## 三、GetGlyph —— 字形源 + 每字形字体属性

```
struct Glyph {
    uint8_t tiles[128];   /* TL,BL,TR,BR 归一化(墨15/影14/背0)，未着色 */
    uint8_t width;        /* 步进 px：8(日文/Sym/半角) 或 12(汉字) */
    uint8_t bank;         /* 字形来源：日文 fontNum / CHS 汉库 / 小号汉库(预留) */
};
int GetGlyph(TextPrinter *win, u32 code, struct Glyph *out);
```

- 解析顺序：CHS 汉库 → 空白 → Sym 带 → 日文 fontNum 字库（官方 GGTP）
- **混合字体**：队伍名流内 `ＭＥＷ`(全角拉丁)/`ジグザグマ`(假名) 为 font4 8×8 小字、
  F9 汉字为 12px——GetGlyph 逐字形返回各自 width/bank，渲染层与表项层
  按返回值处理，不做窗口级字体假设
- 小号汉字 bank（8px 高，与 font4 混排一致）= 预留 bank 维度，本版未含（记账）

## 四、sPrintGlyphFuncs —— 按 tm 一行一语义

| 行 | 语义（日版原生） | 场景（gdb 实证） | 实现 |
|----|------------------|------------------|------|
| 0 | FontFunc[0]：Linear，u=TILE_BASE+TILE_OFF | 对话/战斗文本/详情页字段 | 滚动光栅：像素写 TILE_OFF 连续区，`UpdateTilemap(nCols)`，TILE_OFF+=nCols*2 |
| 1 | FontFunc[1]+SubTable：等宽 | 队伍名/请选择/队伍选项 | 保留区像素 + `UpdateTilemap` 对写；**12px 汉字 1.5 列步进**（见 §五） |
| 2 | FontFunc[2]：指针缓冲 | 槽位数字（幻影 dst=0）/详情缓冲 | dst==0 → 消费不画；dst≠0 → 组色写缓冲（待 battle_interface 研究后启用） |
| 3 | FontFunc[3]：网格 | 开始菜单 | 网格 idx=(CX+TX+TILE_BASE)+(CY+TY)*30（JP 实测 85 起步） |
| 4..7 | 未观测 | — | **UNKNOWN** |

**UNKNOWN 行为**：消费字形、返回 1、无任何绘制/表项/游标变动。

## 五、UpdateTilemap —— tilesWidth 抽象与半角字体

### 5.1 签名（整数列数，对齐美版）

```
UpdateTilemap(win, nCols, up0, lo0, up1, lo1)
  nCols=0 → 不写（=美版 tilesWidth 0 + tilemap NULL 双守卫同源）
  nCols=1 → cursor 格写一对（8px 整列，日文）
  nCols=2 → cursor 格 + 右邻格（12px 汉字跨列）
```

### 5.2 1.5 列步进的归属

tilesWidth 的抽象值 = width/8（12px → 1.5），但**表项永远是整列**（0/1/2）。
1.5 的语义拆为：
- **表项**：本字形写 2 列（第二列只含 4px 墨 + 背景）
- **光标**：像素制游标（pitch 槽 chs_px），推进 +12px；下一字形从半列相位
  自动续接（"自动匹配下个字的一半"）——即 pokeruby mode0 的滚动光栅模型
- 行结束/裁剪：末半列由下一次 UpdateTilemap 或行冲刷收尾（美版 ClipRight
  `UpdateTilemap(win,1)` 同款）

### 5.3 半角字体（队伍名等）不需要 UpdateTilemap 加参数

队伍名原生即**混合字体**：全角拉丁（ＭＥＷ）/假名（ジグザグマ）为 font4
8×8 小字，经 SubTable[4] 配对（**上格=212 空白、下格=字形**）写一对表项。
半角语义由三处上游承载，UpdateTilemap 签名不变：
1. GetGlyph 的 bank/width（小号字形来源与 8px 步进）
2. 配对数据（空白格放置——map 表或调用方约定）
3. sWriteGlyphTilemapFuncs[fontNum] 的行分发

CHS 在半角窗的过渡策略：12px 汉字按 2 列表项 + 1.5 步进（已知比原生
8px 小字大，视觉记账）；终解 = 小号汉字 bank（§三预留维度）。

## 六、tile 分配与隔离矩阵

| 区域 | 归属 | 游标 | 生命周期 |
|------|------|------|----------|
| TILE_BASE+TILE_OFF | tm0 专属（原生字段） | win+0x18，ITP 清零 | 每次打印 |
| 保留区 [TILE_BASE+0x100, 上界) | tm1/tm3 共用分配池 | EWRAM 按 charBase 分槽 | 跨打印持久，上界防溢 screenblock |
| win[0x20] 缓冲 | tm2 专属 | 调用方设 | 每次打印 |

禁止事项：tm1/tm3 写 TILE_OFFSET（复盘 Bug6）；跨 charBase 共用游标；
C 静态变量（BSS 陷阱，复盘 Bug0）。

## 七、UNKNOWN 诊断矩阵

| 维度 | 已验证 | UNKNOWN（缺字排查） |
|------|--------|---------------------|
| textMode | 0/1/2/3 | 4/5/6/7 及越界 |
| fontNum（表项行） | 3/4 | 0/1/2/5/6 |
| 字形 bank | 日文/CHS/空白/Sym | 小号汉库（未制作） |

出现缺字 → 该处命中 UNKNOWN → 按 §四表格补实现/补验证即可，不影响其他路径。

## 八、实施与验证顺序

1. 骨架：GetGlyph + 分发表 + UNKNOWN 全行（全屏无字但游戏可跑）
2. tm0 行（对话/详情页 Linear）→ 单场景验证
3. tm1 行（队伍名 1.5 步进）→ 队伍页验证
4. tm3 行（开始菜单网格）→ 菜单验证
5. tm2 行（缓冲）→ 待 battle_interface 研究后
6. 每步只开一个场景；分游戏（美/日原盘 + 成品）日志对照

## 九、2026-08-24 收敛记录（hook 面 = 只有 PrintNextChar）

| 项 | 定案 | 缘由 |
|----|------|------|
| hook 面 | 仅 P01（PrintNextChar 整函数替换） | 「从这个函数入口，全面接管日版文字打印」 |
| Hook3/P02 | 移除（ROM 桩 + entry.s 跳板 + `GetGlyphTilePointers_*` 声明） | 引擎内部 `static GetGlyphTilePointers`（fontNum==4 → Small 库，bit15 分半）取代外部分发；顺带修复 `_C` 符号无定义的断链 |
| P05 箭头同步 | 折入 `text.c static DrawInitialDownArrow`（pokeruby 同名），删跳板与桩 | FA/FB 触发点本就在 PrintNextChar 内；反汇编实证原生包装 0x08003F4C ≡ `win[6]=0 + 尾调 0x08003DAC`，折入版逐语义等价 |
| P04 地名居中 | 保留，独立域 `src/map_name_popup/`（三件套）；`GetStringWidth_PCS` 仍由 text.c 导出 | 挂点在 DrawMapNamePopup，无法折入；移除会复活 >10B 地名野写 crash |
| 目录 | `src/entry.s`、`src/hooks_origin.s` 上移与 text.c 同级；旧引擎归档 `src/bak/text/` | 命名规范 `{域}/{方法}_hook.c + entry.s + hooks_origin.s` |
| 方法名对齐 pokeruby text.c | `GetCursorTileNum_Linear→GetCursorTileNum`、`map_at→WriteGlyphTilemap`、`WriteTilemap_Pair→WriteGlyphTilemap_Font3_Font4`、`WriteTilemap_Unknown→WriteGlyphTilemap_Unknown`、`DrawGlyphTile→DrawGlyphTile_ShadowedFont` | 与 `tools/pokeruby/src/text.c` 同名同族 |
| 构建纪律 | game_syms 流式直出：无拷贝变量、无默认回填（build.bat 与 Makefile 同规则） | 地址/常量只活在 game_addrs.asm / game.h / config.json；符号缺失时 armips 使用处响亮报错 |

导出面（nm 实测）：文本域全局符号 = `EngineEntry` / `PrintNextChar` / `GetStringWidth_PCS`
（+ map_name_popup 域的 `MapName_DisplayCellLength` / `MapNamePopup_CalcLeftPx`）。
