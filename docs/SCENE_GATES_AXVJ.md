# AXVJ 场景门控（Scene Gates）— bak 台账与拦截层设计

> 来源：[`configs/POKEMON_RUBY_AXVJ00/hook/src/bak/text/DrawGlyphTiles_hook.c`](../configs/POKEMON_RUBY_AXVJ00/hook/src/bak/text/DrawGlyphTiles_hook.c)（2026-08-22 `scene_off_test` A/B 实证）。  
> 目的：把「风控」从散落的 `if` 收成**可配置规则表**，供后续 `text_scene.c` 接入；**本文只记录，不改运行时**。

---

## 1. 「风控」在干什么（一句话）

日版 `TextPrinter` 的 **同一套 CHS 8+4 绘制**，在不同界面里 **tile 寻址公式不同**（Linear 滚动 vs Mode2 网格），且有些窗 **根本不能走 CHS 引擎**（dest=缓冲 RAM）。  
Scene gates = **按 win 快照判定界面类型 → 选布局算法 / 改 GCTN 参数 / 避开保留 tile / 或整窗交还原生 FontFunc**。

不是翻译/policy 层的事；与 Meowth 模块勾选无关。

---

## 2. 两层拦截（能否都在 PrintNextChar？）

> **与 `text_render.c` 里 `draw_use_linear` 的边界**：`textMode==0 → Linear`、`Font3 → Mode2` 是 **pokeRS/日版 FontFunc 原生布局分叉**，不是本文 §4 的 scene 探测器。删掉它会导致标题/菜单误用 Linear GCTN（叠字、踩 UI tile、品红碎字）。**可安全移除的只有** bak 里的 `scene_is_*` / `avoid_dex_ui_tile` / 分场景 `linear.floor` 等——应进 `text_scene.c`，不应动 refpr/相位/Font3 分叉。

| 层 | 名称 | bak 函数 | 典型作用 | 适合拦截阶段 |
|----|------|----------|----------|----------------|
| **A. 路由门控** | Route | `scene_is_buffer_printer` | 整窗 **不画 CHS**，`return 0` 交原生 FontFunc | **PrintNextChar**（必须） |
| **B. 布局门控** | Layout | `DrawGlyph_ShouldUseLinear` + `scene_mode2_apply` + `ensure_linear_dest_floor` + `avoid_dex_ui_tile` | 同一 CHS 字 **写到哪块 tile** | **DrawGlyphTiles / GetCursorTileNum**（主）；PrintNextChar 仅写 **状态位** |

**结论**

- **只有路由门控适合（且必须）在 PrintNextChar 顶栏做**——一旦进了 `DrawGlyphTiles`，VRAM/tilemap 已被错误语义触碰。
- **布局门控不适合全部前移到 PrintNextChar**：判定依赖 `TILE_BASE`、`CURSOR_X/Y`、`TILE_OFFSET`、行内相位，且在 **同一行多字** 过程中不变；在 `DrawGlyphTiles` 入口或 `GetCursorTileNum` 算一次即可。
- **例外**：F9 短语 `write_op`（`ChineseTileState.write_op`）在 bak 里由 **PrintNextChar/F9 路径写入**，由 **`scene_mode2_apply` 读取**——属于 **跨层状态**，不是纯 PNC 拦截。

当前薄路径 [`text_render.c`](../configs/POKEMON_RUBY_AXVJ00/hook/src/text/text_render.c) **未接 B 层**；[`PrintNextChar_hook.c`](../configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c) 对 tm1 font4 仍走 `PrintGlyph_TextMode1_Origin`，与 bak 的 `scene_is_buffer_printer`（tm1+font4 缓冲）**部分冲突**，见 §6。

---

## 3. 路由门控（Layer A）— 配置表

```yaml
# scene.route — 命中则 PrintNextChar 不接管（return 0 → 原生 FontFunc）
routes:
  - id: buffer_battle_tm2
    match:
      textMode: 2
    effect: delegate_origin   # 血条/战斗界面缓冲，dest=win[0x20]
    fail_symptom: 血条乱码、固定 '/AP' 类残留

  - id: buffer_bold_tm1_font4
    match:
      textMode: 1
      fontNum: 4
      template.tilemap: 0          # NULL；队伍 0x081BB43C 有 tilemap≠0 不匹配
    effect: delegate_origin   # RenderTextHandleBold 静态窗，dest=win[0x20]
    fail_symptom: 血条 '/AP' 乱码；误匹配队伍窗 → PC=0x00000004 卡死
    note: 同 win=0x03004170 复用，靠 tilemap 区分
```

**PrintNextChar 伪代码**

```
if scene_route_delegate(win):
    return 0   # 原版 FontFuncTable
# else F9 / DrawGlyph / DrawGlyphTiles
```

---

## 4. 场景探测器（Layer B）— 配置表

所有探测器 **只读** `win` + `win_template()` +（商店）`gMenu @ ADDR_GMENU`；**无副作用**。

### 4.1 `scene_is_battle_text_window`

```yaml
- id: battle_text
  match_any:
    - tileBase: 0x0090          # 战斗台词窗
    - tileBase_range: [0x0190, 0x01C0)   # 指令/说明窗 0x190、0x1B8 等
    - tileBase_gte: 0x0280      # CHS_BATTLE_FIXED_BASE
  used_by: [battle_force_linear, avoid_dex_ui_tile_skip_remap]
  fail_if_missing: 招式说明黑块（Mode2 误写 charblock 1）
```

### 4.2 `scene_is_party_footer`

```yaml
- id: party_footer
  match_all:
    - template.charBase: 2
    - fontNum: 3
    - cursorX_lt: 14            # CHS_SHOP_LIST_LEFT
    - cursorY_in: [17, 136]     # tile 17 或 px 17*8
  effect_tags: [mode2_footer_band, linear_floor_0x2C0]
  fail_if_missing: 队伍 DoWhat 底栏错位、与昵称区串台
```

### 4.3 `scene_is_shop_desc`

```yaml
- id: shop_desc
  match_all:
    - template.charBase: 2
    - fontNum: 3
    - cursorX_lt: 14
    - cursorY_in: [13, 104]      # 0x68 px 或 tile 13
  excludes: [party_footer]
  effect_tags: [force_linear, linear_floor_0x228]
  fail_if_missing: 商店描述区串台
```

### 4.4 `scene_is_shop_bag_list`

```yaml
- id: shop_bag_list
  match_all:
    - template.charBase: 2
    - fontNum: 3
  excludes: [shop_desc, party_footer]
  match_any:
    - { cursorX: 2, tileBase_range: [0x80, 0x120) }   # 背包名
    - { cursorX: 7, tileBase_range: [0x60, 0x90) }    # 数量列
    - gMenu: { left: 1, top: 1, maxMinus1_gte: 6, cursorX_in: [2, 7] }
  effect_tags: [force_linear, linear_floor_0x100]
  fail_if_missing: 商店/背包列表踩窗框 tile、与 ▶ 游标池冲突
  note: 故意不匹配 continue 屏 left=2（过窄门控）
```

### 4.5 `scene_menu_wants_mode2`

```yaml
- id: menu_mode2
  match_all:
    - fontNum: 3
    - template.charBase_in: [0, 2]   # 标题/软键盘 charBase0；菜单 charBase2
  excludes: [shop_desc, shop_bag_list]
  effect: layout_mode2
  fail_if_missing: 标题/软键盘/主菜单 Linear 串台（continue 叠字）
```

### 4.6 遗留/辅助

| 函数 | 作用 |
|------|------|
| `scene_field_wants_linear` | 旧 field 判定；**已不再**用 left&lt;14 逼 Linear（会误伤 continue 多选） |
| `scene_battle_force_linear` | == `scene_is_battle_text_window` |
| `scene_is_battle_interface_dest` | textMode==2（路由层子集） |
| `scene_jp_via_chs` | 非 textMode2 时 PCS 可走 CHS 池 |
| `scene_keep_linear_16` | 已废弃（恒 0） |

---

## 5. 布局效应（Layer B）— 配置表

### 5.1 算法选择 `DrawGlyph_ShouldUseLinear`

**优先级（bak 顺序）**

```yaml
layout.pick:   # true=Linear, false=Mode2(GetCursorTileNum_Mode2)
  - if: battle_text          -> linear
  - if: shop_desc            -> linear
  - if: shop_bag_list        -> linear
  - if: menu_mode2           -> mode2
  - if: fontNum == 3         -> mode2   # 其余 Font3
  - default                  -> linear
```

### 5.2 Linear 池下限 `ensure_linear_dest_floor`

```yaml
linear.floor_tileOffset:
  battle_text:     skip      # 不抬 floor
  party_footer:    0x2C0
  shop_bag_list:   0x100
  shop_desc:       0x228
  template.charBase==2 其他: 0x100   # CHS_MENU_LINEAR_FLOOR
  default:         4
```

触发时机：**行首** `chs_px==0`（或 phase 槽刚绑定）写 `WIN_TILE_OFFSET = max(off, floor)`。

### 5.3 Mode2 几何修正 `scene_mode2_apply`

输入/输出：在算 `idx = y*30 + x + band + tileBase + origin` 前改 `x,y,band,origin`。

```yaml
mode2.apply:
  - if: party_footer
    origin: 2                    # CHS_MODE2_ORIGIN_SHOP
    y_transform: "if y>=136: y/=8; if y>=16: y-=16"
    band: 0x2A0                  # CHS_MODE2_PARTY_FOOTER_BAND

  - if: write_op != 0
    then: return                  # F9 短语 op 接管，跳过下列

  - if: party_menu               # left>=20 && y>=13 && 非 footer 特例
    x: "+1"
    y: "-13"
    band: 0x17A                  # CHS_MODE2_MENU_BAND
    origin: 0x20                  # CHS_MODE2_ORIGIN_MENU

  default:
    origin: 2                    # shop 系；charBase!=2 时 origin=0
```

`write_op` 来源：**PrintNextChar** 处理 `F9 80` / 短语 op 时写入 pitch 槽（非 scene 探测器）。

### 5.4 保留 tile 重映射 `avoid_dex_ui_tile`

```yaml
tile.remap:
  battle_text: none             # 战斗对话 remap 会留黑条（FillWindow 0x0A）
  range [0x1E0, 0x1E1]: -> 0x168 + offset   # 菜单 ▶，勿 remap 到 0x1D0
  range [0x1E8, 0x1FF]: -> 0x3E8 + offset   # 图鉴/能力页 UI 图标
```

用于 **Linear 与 Mode2** 的 GCTN 返回值。

---

## 6. 与当前 PrintNextChar 分发的关系

| bak 行为 | 当前 `PrintNextChar_hook.c` | 差距 |
|----------|----------------------------|------|
| `scene_is_buffer_printer` → 整窗 delegate | 顶栏 `scene_is_buffer_printer`（**tm1+font4 须 tilemap==NULL**） | 已收窄；队伍 0x081BB43C 走 tm1 Origin |
| tm1 font4 队伍名 PCS | `PrintGlyph_TextMode1_Origin` | 一致 |
| F9 → `write_op` | 薄路径 pitch 槽无 `write_op` | 能力页/短语 Mode2 band 失效 |

**建议（后续 `text_scene.c`）**

1. **路由表**只在 `PrintNextChar_Hook` 开头查一次。  
2. **布局表**导出 `scene_layout_for(win) -> { linear, floor, mode2_apply_fn }`，供 `text_render.c` 在 `DrawGlyphTiles` / `GetCursorTilePair` 调用。  
3. **不要**把 `avoid_dex_ui_tile` / `mode2_apply` 搬进 PrintNextChar 循环体——每字调用浪费且易与相位不同步。

---

## 7. 失败症状 ↔ 规则 速查

| 实机现象 | 优先查的规则 id |
|----------|----------------|
| 标题/continue 叠字、软键盘串行 | `menu_mode2` 未生效 → 误 Linear |
| 战斗招式说明黑块 | `battle_text` 未 force Linear |
| 商店描述与列表互串 | `shop_desc` / `shop_bag_list` |
| 队伍 DoWhat 底栏错位 | `party_footer` + `mode2.apply.party_footer` |
| 能力页/图鉴图标变字 | `tile.remap` 0x1E8–0x1FF |
| 菜单 ▶ 被中文覆盖 | `tile.remap` 0x1E0–0x1E1 |
| 血条/概览名乱码 | `buffer_battle_tm2` / `buffer_bold_tm1_font4` 路由 |

---

## 8. 实现落位（2026-08-27 已接入）

```
hook/include/text_scene.h       # 公共 API
hook/src/text/text_scene.c      # §3–§5 全部门控 + GCTN/remap/floor
hook/src/text/text_render.c     # refpr/相位；经 thin wrapper 调 scene_*
hook/src/text/PrintNextChar_hook.c  # scene_is_buffer_printer → PrintNextChar_Origin
hook/src/text/text_translter.c  # F9 短语 → chs_pitch_set_write_op
hook/src/text/entry.s           # PrintNextChar_Origin incbin 0xA0 @ baserom 0x32F8
```

可选：把 §4–§5 表迁到 `configs/.../hook/scene_rules.yaml` 仅作文档/生成器输入（**运行时仍 C**）。

---

## 9. 常量索引

见 [`hook/include/game.h`](../configs/POKEMON_RUBY_AXVJ00/hook/include/game.h) `CHS_*` / `CHS_BATTLE_*` / `GMENU_*`；与本文 YAML 字段一一对应。

---

## 10. 参考

- bak 实证注释：`DrawGlyphTiles_hook.c` L567–572（关闭 scene → 战斗黑块、商店串台、队伍底栏、血条乱码）。  
- 布局背景：[`docs/AXVJ_TEXT_PIPELINE.md`](AXVJ_TEXT_PIPELINE.md) FontFunc[0]/[3] Linear vs grid。  
- 桥接分工：[`docs/DISASM_20260827_JP_US_TEXT_BRIDGE.md`](DISASM_20260827_JP_US_TEXT_BRIDGE.md) 桥接层映射表。
