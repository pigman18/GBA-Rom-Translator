# 落址公式调研：master vs 当前分支（2026-11-19）

> 触发：BUG-C 连续两次修坏（一次字碎、一次字距拉稀、一次连带普通渲染乱掉）。
> 用户指路：**参考 master 的公式；按 textMode 写不同落址，按 fontNum 选不同字体**。
> 本文只记录可核对的事实，不写推测。

## 一、master 的架构（`C:\code\GBA-master`）

### 1.1 总体数据流

`configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c` 文件头注释：

```
取码 → GetGlyph（唯一取址，逐字形字体属性）→ sPrintGlyphFuncs[textMode]
→ sWriteGlyphTilemapFuncs[fontNum] → UpdateTilemap(win, nCols, tiles..)

tm0 = FontFunc[0] Linear 滚动光栅（TILE_BASE+TILE_OFF，对话/战斗/详情页）
tm1 = FontFunc[1] 等宽：全局游标 scratch（7732 基线；等宽窗 tileData=共享
      只读 atlas，像素必须落自由区，表项经 UpdateTilemap 指向 scratch）
tm2 = FontFunc[2] 指针缓冲（dst==0 幻影跳过；血条走 slot+缓冲绘制）
tm3 = 与 tm1 共用（菜单/对话主窗；font4 队伍窗走原生 Origin 路径）
tm4..7 / 未验证 fontNum → UNKNOWN：消费返回 1、无绘制（缺字=排查信号）
```

### 1.2 两级函数表

```c
/* 第一级 [textMode] */
static const PcsPrintFunc sPcsPrintFuncs[8] = {
    PcsPrint_Custom,   /* 0：tm0 自绘 */
    PcsPrint_Tm1,      /* 1：二级查 fontNum ← 唯一需要分配 tile 的 */
    PcsPrint_Custom,   /* 2：tm2 缓冲自绘 */
    PcsPrint_Custom,   /* 3：tm3 自绘 */
    ...
};
sPcsPrintFuncs[win_u8(win, WIN_TEXTMODE) & 7u](win, cur_char);

/* 第二级 [fontNum]，仅 tm1 用 */
static const PcsPrintFunc sPcsTm1FontFuncs[8] = {
    PcsPrint_Custom,              /* font0 */
    PcsPrint_Custom,              /* font1 */
    PcsPrint_Custom,              /* font2 */
    PcsPrint_Custom,              /* font3：线性区与 scratch 带重叠 */
    PrintGlyph_TextMode1_Origin,  /* font4：FontType1Map 区在 scratch 带下方 */
    ...
};
```

### 1.3 落址：复用原版函数，不自创公式

`src/text/text_scene.c`：

```c
/* tm0 线性 */
uint16_t scene_gctn_linear(TextPrinter *win, unsigned xOff, unsigned yOff)
{
    return scene_remap_tile(win,
        (uint16_t)(win_u16(win, WIN_TILE_BASE) + win_u16(win, WIN_TILE_OFFSET)
                   + 2u * xOff + yOff));
}

/* tm2 缓冲 */
void scene_gctn_mode2(TextPrinter *win, int tile_x,
                      uint16_t *upper, uint16_t *lower)
{
    int x = curX + tile_x;
    int y = curY + curTY;
    int band = 0, origin = (tpl[1]==2) ? CHS_MODE2_ORIGIN_SHOP : 0;
    mode2_apply(win, &x, &y, &band, &origin);
    idx = y * CHS_TILE_GRID_W + x + band + TILE_BASE + origin;
    *upper = remap(idx);
    *lower = remap(idx + CHS_TILE_GRID_W);
}
```

`src/text/text_render.c` 的推进（tm0 分支）：

```c
off = win_u16(win, WIN_TILE_OFFSET);
abs_u = GetCursorTileNum_Linear(win, 0, 0);
abs_l = GetCursorTileNum_Linear(win, 0, 1);
...
map_at(win, map_tx, abs_u, abs_l);
win_set_u16(win, WIN_TILE_OFFSET, (uint16_t)(off + 2u));   /* 每字 +2 */
```

12px 第二遍（右半列）：

```c
win_set_u16(win, WIN_TILE_OFFSET,
            (uint16_t)(off + (startPixel == 0u ? 0u : 2u)));
```

### 1.4 `scene_remap_tile` —— 按场景小幅偏移，不重算网格

```c
uint16_t scene_remap_tile(TextPrinter *win, uint16_t tile)
{
    if (screen_battle(win))  return tile;              /* 战斗：原样 */
    if (screen_summary(win)) { /* 只挪 UI 图标与 PSS 区 */ }
    if (tile >= CHS_MENU_CURSOR_TILE && ...) return ALT + offset;
    if (tile >= CHS_UI_ICON_TILE_LO && ...)  return ALT + offset;
    return tile;
}
```

**关键**：master 的 tm0 是**纯线性 + 按场景小偏移**，没有任何 band 网格、
没有冲突规避分配器。

## 二、当前分支的问题

### 2.1 现状

`grid_tile()` 只有一个公式，被**所有 textMode 共用**：

```c
return (uint16_t)((unsigned)tb + 2u
        + (row & (GRID_SEG_COUNT - 1u)) * GRID_SEG_TILES   /* band*62 */
        + 2u * grid_store_col(row, col));                  /* + 2*col */
```

只有 `textMode == 2` 走了 `buffered` 分支，其余全靠这一个公式。

### 2.2 后果（实测）

| 窗 | textMode | TB | 公式给出 | origin 实际 | 结果 |
|---|---|---|---|---|---|
| 战斗对话 | 0 | 0x1B8 | `0x1F8`（band=1） | `0x1B8` | 越界 >0x1F0 → 整框空白 |
| 战斗菜单 | 0 | 0x190 | `0x1D0` | `0x190` | 位置错 |
| 招式列表 | 0 | 0x2C0 | `0x3EC` | `0x2C0` 起 | 越界 → 整框空白 |

公式 `band*62+2col` 是**为 tm1 槽位分配设计的**，被错套到 tm0/tm3。

### 2.3 我前两次修坏的原因

1. 只改「上界常量」不改公式 → 错误的 tile 号被放行
2. 加线性分支但推进写错：`grid_adv_col` 读的是**循环里已被改写过的**
   `cursorTileX` 再 +delta，每字多跳一列 → x20/x21 同指 0x1A4
3. 把「保护分支」也推进 TILE_OFFSET → 字距拉稀
4. 给所有窗套分派，误伤 textMode 3 的普通渲染

## 三、正确方案（待实施）

### 3.1 按 textMode 分派落址

| textMode | 落址公式 | 分配 tile |
|---|---|---|
| 0 | `TB + TILE_OFFSET`，每字 `+= 2` | 否 |
| 1 | 现有网格（唯一需要分配的） | **是** |
| 2 | 现有 buffered | 否 |
| 3 | `TB + 2 + col + 30*row`（反汇编 0x080034E0 实证） | 否 |

### 3.2 按 fontNum 选字体

`grid_font_for()` 已有：`fontNum==2||4 → FontChsSmall(8px)`，其余 `FontChsNormal(12px)`。
与 master 一致（「队伍等 fn4 = FontChsSmall 8px」）。

### 3.3 改动范围（最小）

只加 `textMode == 0` 一个分支，**不碰** 1/2/3 的现有行为。
推进用 `t->rel + delta`（setup 时保存的原值），不用循环里的实时值。

## 四、待验证的硬数据

| 事实 | 来源 | 状态 |
|---|---|---|
| tm0: `tile = TB + TILE_OFFSET`，每字 +2 | master `scene_gctn_linear` | ✅ |
| tm0: 换行时 TILE_OFFSET 不变，curTX 归零 | GDB origin 侧实测 index17→18 | ✅ |
| tm0: 行内 `TILE_OFFSET = 2*curTX` | GDB 序列 index0..17 | ✅ |
| tm0: 空格占 2 tile（x23=1AA→x25=1AE） | origin 帧058 tilemap | ✅ |
| tm3: `TB + 2 + col + 30*row` | 反汇编 0x080034E0 | ✅ |
| 只有 tm1 需要分配 tile | 用户指路 + master 架构 | ✅ |

---

## 五、实施结果（2026-11-19 17:47）

### 5.1 改动清单（全部只碰落址，未动渲染）

| 位置 | 改动 |
|---|---|
| `grid_tile_linear()` | 新增：`tile = TB + TILE_OFFSET` |
| `grid_emit()` | 新增 `textMode==0` 独立分支，直写、绕开网格与冲突规避 |
| `grid_emit()` 推进 | `TILE_OFFSET += 2*delta`，`cursorTileX = t->rel + delta` |
| `grid_load()` | textMode 0 用 `grid_tile_linear` + 上界 1024（不再卡 0x1F0） |
| `grid_draw_pcs()` 空格 | textMode 0 时 `TILE_OFFSET += 2` |
| `grid_bg()` | textMode 0 用 `win[0x0D]`（D=背景色） |

**未改动**：`grid_load` 的像素合成、`grid_pair_*`、`grid_glyph_px`、`grid_draw_chs`
的 12px 单遍绘制。**没有引入 master 的 8+4 / 4+8 双遍渲染。**

### 5.2 配色依据（GDB origin 侧，只统计真正打印的样本）

| 窗 | TB | 次数 | C/D/E | pal | D 在该 pal 下的颜色 |
|---|---|---|---|---|---|
| 对话 | 0x1B8 | 27 | 1/15/8 | 0 | 15 = 白 ✅ |
| 菜单 | 0x190 | 42 | 13/14/15 | 5 | 14 = 白 ✅ |
| 招式 | 0x2C0 | 18 | 13/14/15 | 5 | 14 = 白 ✅ |

⇒ **D 就是背景色**。旧代码取 `tpl[6]`，菜单/招式窗拿到 15 = 灰 `(213,213,205)`，
即用户截图里的灰块。

### 5.3 验证

**tilemap 逐项对齐（帧 058）**

```
origin      y3: 2:1B8 3:1BA 4:1BC 5:1BE 6:1C0 7:1C2 8:1C4 9:1C6 10:1C8 11:1CA 12:1CC 19:190 20:192 21:194 22:196 23:198 25:19C 26:19E 27:1A0
translated  y3: 2:1B8 3:1BA 4:1BC 5:1BE 6:1C0 7:1C2 8:1C4 9:1C6 10:1C8 11:1CA 12:1CC 19:190 20:192 21:194            25:19C 26:19E 27:1A0

origin      y5: 19:1A2 20:1A4 21:1A6 22:1A8 23:1AA 25:1AE 26:1B0 27:1B2
translated  y5: 19:1A2 20:1A4 21:1A6 22:1A8 23:1AA 25:1AE 26:1B0 27:1B2
```

y5 **完全一致**，包括空格跳过 `0x1AC`。y3 少 x22/x23 是因为中文 2 字 vs 日文 4 字。

**底色 nibble**

```
origin      tile 0x190 nibble={13:14, 14:39, 15:11}
translated  tile 0x190 nibble={13:14, 14:45, 15:5}   ← 底=14，与 origin 同构
```

**画面文字（逐字读图确认）**

| 界面 | 内容 | 结论 |
|---|---|---|
| 战斗菜单 | 战斗 / ▶背包 / 宝可梦 / 逃跑 | ✅ 白底、无残字 |
| 战斗对话 | バシャーモ怎么办? | ✅ 白字青底、三字完整 |
| 招式窗 | 0x300/0x310/0x320/0x330 段全部出现 | ✅ |
| 开始菜单 | 图鉴/宝可梦/背包/▶领航员/1?4/保存/设置/退出 | ✅ 8 项全对（`1?4` 是既有 BUG） |
| 背包 | 学习装置/PP单项小补剂/…/▶丝绸围巾 | ✅ 无空白行 |
| 图鉴 | No003 妙蛙花 / No004..No010 ------ | ✅ 行不覆盖 |
| 设置 | 改变设置/对话速度/…/关闭 | ✅ 全对 |

### 5.4 关键约束（用户 2026-11-19 补充）

> master 的 12px 通过 **8+4 / 4+8** 两遍渲染，所以 charBase 不够分配；
> 当前分支改进了渲染方式，所以 tm1 够了 —— 证据是训练家之眼完美渲染。
> **要复刻那边的落址，但不要照搬那边的渲染。**

本实施严格遵守：落址复刻（`TB+TILE_OFFSET`），渲染仍是当前分支的单遍像素合成。
