# text 汉化重构设计：接管分发 + 薄桥接层

> 目标：抛开现有 `PrintNextChar` 分支架构，用**更少的代码**重建汉化 text 路径，
> 并**最大化复用 ROM 官方原语**（日版优先，美版只借语义不借代码）。
>
> 状态：**设计稿**，尚未落地。现有代码在 `git` 工作区（6 个文件 M，未提交）。

---

## 0. 结论先行

| 问题 | 结论 |
|---|---|
| 能用美版 text.c 桥接吗？ | **不能整体搬**。它依赖 US `struct Window` 布局、`gCurGlyph` 全局 RAM、`sFonts` 指向 US ROM 地址——三样我们在 AXVJ 上全不满足。 |
| 那"优先用美版"怎么落实？ | **借语义，不借代码**。只借两个概念：① 像素级游标（`AddToCursorX`）② 宽度表（压成 switch）。 |
| 真正的杠杆是什么？ | **日版官方原语**。尤其是 `sub_8003630(glyph, dst, ...)`——`dst` 是**参数**，比美版 `DrawGlyphTile_*` 写死 `gCurGlyph` 更好用。 |
| 能省多少代码？ | 约 **−230 行（13%）**，且顺带修掉 P1 的"两套 tile 空间" bug。 |

---

## 1. 能力对照：日版到底缺什么

| 能力 | 美版 pokeruby | 日版 AXVJ | 结论 |
|---|---|---|---|
| 字形解码 + 像素绘制 | `DrawGlyphTile_*` | **`sub_8003630(glyph, dst, ...)`** | 日版自带，且 `dst` 可传 → **比美版好用** |
| 写屏幕表项 | `UpdateTilemap` | `0x080036DC` | 都有 |
| 控制码 / 状态机 | `HandleExtCtrlCode` | **`0x08003110`** | 都有，直接用 |
| 下箭头动画 | `DrawInitialDownArrow` | **`0x08003F4C`** | 都有，直接用 |
| 宽度表 | `sGlyphWidths` | — | 只需 8/12/16 三个值 → **switch 比表更省** |
| **像素级游标** | `cursorX`（像素） | `cursorTileX` +0x1B（**tile 级**） | **日版唯一真正缺的东西** |

**所以：日版缺的不是"引擎"，是"宽度间接层"的那一半——分配器 + 像素步进 + 半列相位。**
这三样美版也没有可搬的（美版靠 pixel cursor 天然绕过），只能自己写。

---

## 2. 三层架构

```
┌──────────────────────────────────────────────────────────┐
│ L0  接管点（唯一 hook）                                    │
│     拦截 glyph 绘制公共入口，取回 (win, glyph, textMode)    │
│     → 不再按 textMode 分 4 套分支，只留 1 条路径            │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│ L1  桥接层 bridge.c（我们写，~250 行）                     │
│                                                           │
│   chs_alloc(win)          ← 唯一 tile 分配器（含相位）      │
│   chs_add_px(win, adv)    ← 唯一像素步进                   │
│   chs_paint(win,g,dst)    ← 分派：汉字直搬 / 其余交官方      │
│   chs_emit(win, tile)     ← UpdateTilemap 保 cursorX 封装   │
│                                                           │
│   ⚠ 铁律：所有字符（含日文/ASCII/数字）都必须走 chs_alloc   │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│ L2  ROM 官方原语（零维护，直接 bl）                        │
│     0x08003630 sub_8003630(glyph, dst, font, fg, bg, sh)  │
│     0x080036DC UpdateTilemap                              │
│     0x08003110 HandleExtCtrlCode                          │
│     0x08003F4C DrawInitialDownArrow                       │
└──────────────────────────────────────────────────────────┘
```

**关键差异 vs 现状**：现状是"中文走我们的分配器、日文交还原生"——**同一个窗口里两套 tile 空间**。
新设计里日文也走 `chs_alloc`，只是**像素交给官方画**。这就是修 P1 的原理。

---

## 3. 桥接层代码骨架

```c
/* bridge.c —— 唯一的分配器 / 唯一的步进器 / 唯一的分派点 */

/* 3.1 唯一 tile 分配器：像素相位 → tile 序号 */
static uint16_t chs_alloc(TextPrinter *win)
{
    uint16_t base = win_u16(win, WIN_TILE_BASE);
    uint16_t px   = chs_px(win);              /* 我们自己维护的像素游标 */
    uint16_t tile = base + (px >> 3);         /* pitch 分配：8px/列 */
    win_set_u8(win, WIN_CURSOR_TILE_X, (uint8_t)(px >> 3));
    return tile;
}

/* 3.2 唯一像素步进：借美版 AddToCursorX 语义 */
static void chs_add_px(TextPrinter *win, int adv)
{
    chs_set_px(win, chs_px(win) + adv);       /* adv ∈ {8, 12, 16} */
}

/* 3.3 唯一分派点：汉字直搬，其余交官方原语 */
static void chs_paint(TextPrinter *win, uint32_t glyph, uint8_t *dst)
{
    if (is_chs(glyph)) {
        chs_blit(glyph, dst);                 /* 预展开 4bpp 直搬，现有代码可复用 */
    } else {
        /* 关键：dst 由我们给，官方只管画像素，不管落址 */
        sub_8003630(glyph, dst, font_num(win), fg(win), bg(win), shadow(win));
    }
}

/* 3.4 对外唯一入口 */
void Chs_DrawGlyph(TextPrinter *win, uint32_t glyph)
{
    if (is_ctrl(glyph)) { HandleExtCtrlCode_Origin(win, glyph); return; }

    uint16_t tile = chs_alloc(win);                    /* ① 我们分配 */
    uint8_t *dst  = vram_tile(win, tile);
    chs_paint(win, glyph, dst);                        /* ② 分派绘制 */
    UpdateTilemap_PreserveCursorX(win, tile, tile + 1);/* ③ 写表项 */
    chs_add_px(win, chs_advance(glyph));               /* ④ 像素推进 */
}
```

四个函数，四条铁律。**现状 415 行的 hook 分支塌缩成这一个函数。**

---

## 4. 文件布局与行数预估

| 文件 | 现状 | 新设计 | 说明 |
|---|---|---|---|
| `PrintNextChar_hook.c` | 415 | **~120** | 只做：取 glyph → `Chs_DrawGlyph` → 控制码回原生 |
| `bridge.c`（新） | — | **~250** | 分配器 + 步进 + 分派 + 相位 |
| `text_render.c` | 575 | **~420** | 保留字模搬/相位/池管理，删掉与 hook 重复的分支 |
| `text_scene.c` | 233 | 233 | **原样保留**（场景门控，日版不提供，借不来） |
| `text_translter.c` | 507 | 507 | **原样保留**（码位/查表，与架构无关） |
| 合计 | 1730 | **~1530** | **−200 行（−12%）** |

**省不掉的 1530 行里，大头是 tile 分配 + 场景门控 + 相位**——这三样日版引擎根本不提供，
桥接层借不来，只能自己有。桥接能省的（重建原生语义那部分）已经省完了。

---

## 5. 迁移步骤（建议分 3 phase，每 phase 可独立验证）

**Phase A — 建立桥接层（不动现有行为）**
1. 新增 `bridge.c`，实现 4 个函数，暂不接入。
2. 在 `Chs_DrawGlyph` 里加 `DBG` 开关，双跑对比（新路径 vs 旧路径）结果一致性。

**Phase B — 切换中文路径**
3. `PrintNextChar_hook.c` 的中文分支改为调用 `Chs_DrawGlyph`。
4. 回归：对话框 / 菜单 / 战斗文本。

**Phase C — 切换日文路径（修 P1 bug 的关键）**
5. 日文/ASCII/数字**也**改为走 `Chs_DrawGlyph`（`chs_paint` 内部自动分派给官方）。
6. 回归重点：混排窗口的数字、三角箭头落点、PSS 图标行。

> Phase C 前必须先 `git stash` 或建分支保存现有可用基线。

---

## 6. 风险与未决

| 风险 | 说明 | 对策 |
|---|---|---|
| 像素游标存哪 | AXVJ `TextPrinter` 无空闲字段；现状靠外部影子数组 | 需确认影子数组生命周期与窗口复用是否一致（**未决**） |
| `sub_8003630` 的 `fontNum/fg/bg/shadow` 取值 | 需从 `win` 现场还原，参数来源待实证 | 反汇编 `0x08003630` 调用点，确认 5 个参数来源 |
| 半列相位 | 12px 字符跨 tile，需 `px&7` 相位 | 复用现有 `text_render.c` 相位逻辑 |
| 场景门控 | 部分窗口（PSS/Battle）tile 池特殊 | `text_scene.c` 原样保留，桥接层通过回调挂钩 |

---

## 7. 一句话总结

**不是"用美版源码替换日版"，而是"接管分发 + 薄桥接 + 复用日版原语"。**
美版真正值得借的只有"像素游标"这个**语义**；代码层面，`sub_8003630(glyph, dst, ...)`
这个把 `dst` 作为参数暴露的签名，本身就是比美版更好的桥接点。
