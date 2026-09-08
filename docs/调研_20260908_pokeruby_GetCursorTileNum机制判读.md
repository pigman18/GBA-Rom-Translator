# 调研：pokeruby 官方 GetCursorTileNum 机制判读 —— 「回收重分发」是否存在、能否抄

> 日期：2026-09-07 ｜ 源码：pret/pokeruby master（tarball 克隆至 $TEMP/pokeruby-master）
> 背景：v9（cb0 独占带 + ours-GC）被实机证伪回退 v8 基线后，用户指示「参考 pokeRS 源码的 GetCursorTileNum 底层实现，看它的回收 tile 重新分发机制能不能抄」。
> 纪律：本文只写源码可证的事实，推论单独标注。

## 一、官方 GetCursorTileNum 全文（text.c L4380）

```c
static u16 GetCursorTileNum(struct Window *win, u32 xOffset, u32 yOffset)
{
    u16 index;
    if (win->textMode == TEXT_MODE_UNKNOWN2)   // 变宽模式
        index = win->tileDataStartOffset
              + win->tileDataOffset
              + (((win->top + win->cursorY) >> 3) + yOffset) * win->width
              + (((win->left + win->cursorX) >> 3) + xOffset);
    else                                        // 等宽模式
        index = win->tileDataStartOffset + win->tileDataOffset + 2 * xOffset + yOffset;
    return index;
}
```

**结论：纯算术，无扫描、无状态探测、无回收、无重分发。** tile 号 = 窗口基址 + 行内偏移 + 网格坐标，一一对应窗口 tilemap 格子。

## 二、官方的「分配」实为三层顺序拨给（无运行时动态分配）

### 1. 窗口创建时一次性预留（text.c L1800）
```c
static u16 InitVariableWidthFontTileData(struct Window *win, u16 startOffset)
{
    win->tileDataStartOffset = startOffset;
    win->tileDataOffset = 2;                  // tile0=空tile, tile1=背景tile
    ...
    return win->tileDataStartOffset + win->tileDataOffset + win->width * win->height;
    //     ^^^ 返回值 = 下一窗口的起点（预算 = 2 + width×height 个 tile）
}
```
等宽字体（LoadFixedWidthFont）更暴力：一次性把 256 个字形预载进 `[startOffset, startOffset+512)`，返回 512。

### 2. 调用方用返回值顺序拨号（menu.c L81~156）
```c
gMenuTextTileOffset = tileOffset;                                   // 场景代码显式给基址
gMenuTextWindowTileOffset = MultistepInitWindowTileData(gMenuWindowPtr, gMenuTextTileOffset);
gMenuWindowPtr->tileDataStartOffset = gMenuTextTileOffset;
```
`tileDataStartOffset` 是**调用方管理的游标**，各窗口区间互不重叠、由代码静态排布。

### 3. 每字推进只前进不回头（text.c L2571~2584, L2797~2824）
```c
DrawGlyph_TextMode0: cursorX += GetGlyphWidth(...)   // 像素推进
AddToCursorX: 跨 tile 边界时 tileDataOffset += 2     // tile 推进
ScrollWindowTextLines_TextMode0: 换行 tileDataOffset 复位为 2 或 2*sLineLength+2
```

### 4. 「回收」只存在于场景/窗口粒度
- `TextWindow_SetBaseTileNum(u16 baseTileNum)`（text_window.c L101）/ `TextWindow_SetDlgFrameBaseTileNum`：**由场景代码显式重设基址**，整个区间易主；对话框边框图形 tile（14 个，L263）也占用同一预留区间头部。
- 场景切换 = 调用方重新拨 `gMenuTextTileOffset` → 上一场景全部 tile 预算整体让出。
- **不存在任何"逐 tile 活引用探测 / VRAM 非空检测 / 回卷重分发"代码。** grep 全仓 `tileDataStartOffset` 仅 5 个文件，全是赋值/传参，无回收逻辑。

## 三、能否抄：逐条判读

| 官方机制 | 可否抄进 hook 注入架构 | 判读 |
|---|---|---|
| GetCursorTileNum 纯算术寻址 | ❌ 前提=每窗口拥有 `2+width×height` 的**专属连续预算区**，且窗口创建代码可改 | 我们是注入，无法在窗口创建处插入拨号；预算区需要 128~256 连续 tile，已实测 8 场景中 2 个（地图名 62 / 战斗UI 0）选不出 |
| 场景边界整体回收（重拨基址） | ⚠️ 等价物已存在 | 我们的 InitTextPrinter_hook 会话边界复位 + begin 全量重建位图，语义相同 |
| 顺序游标只进不退 | ❌ 无上限需求冲突 | 官方敢只进不退是因为预算按窗口上限预留；中文 16px 需求下全场景预算总和远超 cb 剩余空间 |
| tilemap 网格一一对应落址 | ❌ 已证伪路线 | 即 MEMORY 中「网格落址比顺序分配器更费空间」实测结论（2/8 场景选不出），官方模型恰好坐实了这一点：**官方能用的前提是它拥有全部窗口创建流程** |

**总结论：官方没有可抄的"回收重分发机制"——它的答案是把分配问题消灭在窗口创建期（场景代码静态排布预算区），运行期只做算术寻址。这条路径我们的注入架构走不通（改不了窗口创建代码、凑不出连续预算区）。**

## 四、对当前两处撞 UI（血条 / 华丽大赛 B 键）的启示

1. 官方模型再次确认：**撞 UI 的根因永远是"我们落进了官方窗口/图形的 tile 区间"**，官方自己不会撞自己，因为它从不越界——越界的只有我们。
2. 因此修复方向仍是被实机验收过一次的「场景表扩条」路线（kMapInfoScene/kTrainerInfoScene 先例）：把队伍页血条（tpl 0x081BB40C，v8 已有规则但现场仍有伤）与华丽大赛详情页两场景用 `gdb_patcher --ui-survey` 实测采清该场景 DISPCNT/BGxCNT/各 screenblock 引用桶，确认共享 healthbox tile 的归属，再决定是加避让带还是补场景规则。
3. 【推论/待实测】血条五条同位同伤的候选机制（begin 扫描时图形未就绪 / tile 曾属 ours 被官方复用后 blend 叠印）需 gdb 区分，未拿实测数据前不改分配区间。

## 五、附：官方关键源码位置索引

| 内容 | 位置 |
|---|---|
| GetCursorTileNum | text.c L4380 |
| DrawGlyphTiles / UpdateTilemap | text.c L4321 / L4360 |
| InitVariableWidthFontTileData（预留 2+w×h） | text.c L1800 |
| LoadFixedWidthFont（预载 256 字形=512 tile） | text.c L1812 |
| 每字推进 / 跨 tile 边界 +2 | text.c L2797~2824（SetCursorX/AddToCursorX/AddToCursorY） |
| 换行 tileDataOffset 复位 | text.c L2996~3015 |
| PrintNextChar 主循环 | text.c L2080 |
| 调用方顺序拨号 gMenuTextTileOffset | menu.c L42/L81/L94/L119/L150 |
| TextWindow_SetBaseTileNum / 边框 14 tile | text_window.c L101/L263 |
