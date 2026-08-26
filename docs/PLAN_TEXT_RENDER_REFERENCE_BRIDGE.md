# PLAN — text_render 三层 Reference 桥接重构(pokeemerald 单一引入)

> 状态:V1-V3 已实施(2026-08-27);V4 折中落地;V5 未开始。
> **2026-08-27 变更:16px 整列方案(路线 B)已决策放弃**,PLAN_GLYPH_CACHE_ROUTE_B.md
> 已删除。ref_glyph_copy 的 runtime 切换随之取消——draw_tile 维持现役实现,
> vendored ref 件仅作官方算法对照参照。
> 背景:`text_render_inplace12.c`(611 行)渲染核心手写混乱;prett 三家还原工程
> (`tools/pokeruby|pokeemerald|pokefirered`)绘制算法均为可 verbatim 编译的纯函数。
> 本方案以 pret **pokeemerald** 为唯一引入对象,rename 现有 rh 参照目录,五文件收敛。
> 关联:`调研_20260827_美版布局代码移植评估与全网成熟实现.md`、`调研_20260827_pokeRS类12px机制与日版AXVJ00接入分析.md`。

## 0. 定案速览

1. **引入 pokeemerald 一家**;pokefirered 同族跳过;pokeruby 仅 vendor 文献件(默认不编译)。
2. `reference/pokeemerald-ch` → 改名 **`reference/pokeemerald-expansion`**(按上游工程实名);
   新增 `reference/pokeemerald/`(GLYPH_COPY 提取件)。
3. `chinese_text.c/.h` **注销**:CHS 分支并入 text_render.c 的 GetGlyph(heritage 注释保留来源)。
4. src 收敛为四 C 文件 + entry/hooks_origin(plan 见 §3 树)。

## 1. 为什么是 pokeemerald(不再摇摆)

- **decode/draw 格式同构**:`chinese_text.c` 按上游写的字形缓冲(TextGlyph 行主序,
  TL|TR / BL|BR)正是 emerald 引擎消化格式;GLYPH_COPY 逐 nibble 寻址直接吃我们
  的 4bpp 预展开字模 —— decode 到 draw 零转换。
- pokeruby `DrawGlyphTile_UnshadowedFont` 走 1bpp 调色展开(colors[src>>7]),与本工程
  4bpp 字模不同构;且其 ~400 行 static 函数群(sGlyphMasks[9][8][3] 等)只为支撑
  "startPixel 相位"数学 —— emerald 的 GLYPH_COPY 用逐 nibble 寻址天然覆盖相位,
  不需要那张表。
- pokefirered 与 emerald 同族(text.c 差异为版本级),无独立增量;FRLG 场景差异
  将来若有需要再取。
- rh-hideout-chinese(:=pokeemerald-expansion fork)继续作为 decode 层 diff 监视源,
  render 层确认零贡献(前一轮结论维持)。

## 2. reference 目录规则(新)

```
hook/reference/
├── pokeemerald-expansion/     ← 现 pokeemerald-ch 更名(mv);rh 四原件原样
├── pokeemerald/               ← 新增提取件 copy_glyph_to_tiles.c(见 §4)
└── pokeruby/(可选文献)      ← DrawGlyphTile_* 家族摘录,标注不编译
```

提取件规则:
- 头注标明 `source: pret/pokeemerald src/text.c L583-650 @ master (fetched 2026-08-27)`+
  本地镜像路径 `tools/pokeemerald/src/text.c`;
- 允许的仅有的两处改写:(a) 去 `gWindows[]/gCurGlyph` 全局 → 参数化;
  (b) static 化与命名前缀(`ref_`);
- tools/ 下三套 clone 保持干净,专门用于 diff 同步(reference 提取件 ↔ 上游行号)。

## 3. src/text 目标树与迁移映射

```
src/text/
├── entry.s / hooks_origin.s        不动
├── PrintNextChar_hook.c            ← 现 text.c 更名(~390行):Hook状态机/HandleExtCtrlCode/
│                                     PcsPrint 分发/DrawGlyph/PrintGlyph/arrow/menu cursor
│                                     (-GetGlyph 64行 移出;text_translate.c→改名见下)
├── text_render.c                   ← 四段:
│    [ref]   ref_glyph_copy 参数化原语(emerald GLYPH_COPY/CopyGlyphToWindow ~100行)
│    [glyph] GetGlyph 统一字形解析(空白/Sym带/CHS←chinese_text.c 遗产/日文
│            GetGlyphTilePointers_Origin)+ copy_tile32 去重
│    [bridge]日版 TextPrinter 视图:[win+0x0C]tileData/窗宽tiles/currentX/Y/fg-bg-shadow
│            → 填参数(include/text.h WIN_* 宏集中,未标定偏移补齐在此步)
│    [policy]12px 步进 + scene 门控(队伍页脚/菜单mode2/商店/战斗窗特判集中成带注释分区);
│            pitch 相位家族(chs_pitch_key/bind_slot 等~100行)**保留**(原定随 16px 整列方案退役;
          该方案已放弃,此状态变更,后续如需收敛另立新案)
└── text_translter.c                ← 现 text_translate.c 更名;F900 整串+F980短语+slot v2
                                      全家**保留**(用户实测:全走 slot 太卡,通道无法删),
                                      仅 slot_lookup_legacy 待 v2 覆盖率验证后再清(~60行)

删除项(bat 同步更新):
├── text_render_band.c(528)  ├── text_vfw12.c(61)  └── render_active 选择器+RENDER_SEL_ADDR(~20)
│   chinese_text.c/chinese_text.h(注销并入)
bak/ 目录移出 hook/src 树(build.bat 无引用为前提核对一次)
include/chinese_text.h 删,text.h 中 heritage 注释一行带过
```

规模预期:text_render.c ~650 / PrintNextChar_hook.c ~390 / text_translter.c ~300 /
entry+hooks_origin.s 不变 —— 较现状净减约 700–800 行,且渲染数学全部来自官方实现。

## 4. ref 原语签名(emerald GLYPH_COPY 参数化草案)

```c
/* source: pret/pokeemerald src/text.c GLYPH_COPY L583-609, CopyGlyphToWindow L596 */
void ref_copy_glyph_to_tiles(u8 *windowTiles, u32 winWidthTiles,
                             u32 x, u32 y,
                             const struct TextGlyph *g /*gfxBufferTop/Bottom*/,
                             s32 glyphW, s32 glyphH);
/* 内部 = GLYPH_COPY ×(w,h ≤8/跨界) 分支矩阵,逻辑原样,仅
   template->width*32 → winWidthTiles*32,gCurGlyph → 形参 g */
```

PrintGlyph 链调用面:`ref_copy_glyph_to_tiles(win_tiledata(win), win_width_tiles(win),
win->cursorX, win->cursorY, &glyph, glyph.width, glyph.height)` 后接现有 UpdateTilemap
桥(日版 [win+0x16] tile 计数推进保持现状语义)。

## 5. 实施顺序(每步一个 build 验收点)

1. 删 band/vfw12/render_active 选择器;build.bat 编译清单清理 → build 绿 = V1。
2. 更名两个文件(text.c→PrintNextChar_hook.c、text_translate.c→text_translter.c)+
   bat/markdown 内引用更新 → build 绿 + 实机行为不变 = V2。
3. GetGlyph 移入 text_render.c;CHS 分支内联(注销 chinese_text.*,copy_tile32 去重)
   → build 绿 + 用户实测基础页 = V3。
4. reference/pokeemerald 原语参数化落地,inplace12_core 调用替换;像素级 A/B
   (gdb_patcher --vram-survey 或打包让用户实机过老场景) = V4。
5. scene 门控归拢 policy 分区注释。(原第 6 步"pitch 家族随 16px 整列方案退役"
   已随方案放弃而取消,pitch 相位家族维持现状保留。)

## 6. 风险与对策

- 日版 TextPrinter 未标定偏移(窗宽 tiles 字段等)→ V4 前用 HOOK_DEBUG_WORKFLOW
  补一轮静态标定;WIN_* 宏已集中的话只动一处。
- emerald 原语写窗前不做越界检查(glyphWidth/glyphHeight 由调用方 clamp——
  CopyGlyphToWindow 里对 currentX/Y 与窗宽取 min 的语义必须一起移植,勿丢)。
- -O2 freestanding 别名:copy_tile32 既有 u32 直拷惯例沿用,禁止 char* 绕写。

## 7. 已撤决策备案

- `REMOVE_F980_HOOK_REFACTOR_REQ.md` 于 2026-08-27 应用户指令移除:
  F980/PhraseTable 通道**保留**(全走 slot 实测太卡);slot/relocate 主链不变,
  slot key 字节边界(A/B 口径)遗留开放,实施 text_translter 时一并定。
