# L2b 落地计划：软件缓冲文字引擎（日版 AXVJ）

**决策锁定（2026-09-23）：** 坚持日版底，主路线 = L2b（Mother2 系：EWRAM/IWRAM 1bpp 缓冲 → 4bpp 写回）。  
**明确不做：** v8 避让带、抬水位、假划界 span、改 textMode→2、未授权打包。

对照开源：jeffman `vwf.c` / `m2-vwf-entries.asm`；中文增量参考 Imavoyc Mother2Gba-chs（双字节步进）。

---

## 1. 与现状的切割点

| 现状（v8） | L2b 目标 |
|---|---|
| `chs_emit` 按 tm 直接写 VRAM（tm1/tm3 → `v8_alloc_tile`） | 字形先 blit 进**窗私有 1bpp 软缓冲** |
| `InitTextPrinter_hook` → `v8_alloc_begin`（扫活引用） | Init：**分配/绑定缓冲 + 清缓冲**；**删除避让带快照职责** |
| 落址 = freelist 领号 | 落址 = **(pixel_x, pixel_y) → 窗内 tile 公式**，再 sync 到官方已映射的那批 tile |
| 每字即时 UTM | 可按字 sync 或按行/串 batch sync（首版按字 sync 更易调） |

**保留：** `text_translater` FA..FF / 双字节通路；`resolve_draw` 字号档；`blend_glyph` / 1bpp 字库；tm0 官方线性、tm2 血条缓冲可**首版旁路**（仍走旧路径），避免一次换全作。

---

## 2. 核心契约（Mother2 → AXVJ）

```
PrintNextChar (中文)
  → decode + 取 1bpp 字模
  → blit 到 win 绑定的 softbuf[pixel_x..]   // 跨 8px tile 边界移位 OR
  → expand 1bpp→4bpp（查表，对齐现有 blend/字库色）
  → 写入「该窗 tilemap 已指向的」VRAM tile
  → pixel_x += advance
```

**VRAM 所有权来源（L2b 与假划界的分界）：**

- Softbuf **不**自己去「找空闲带」。
- Sync 目标 = 该 `TextPrinter` 开窗时官方已准备好的 **tile 矩形**（来自 template：`tilemap` + `TILE_BASE` + 窗宽高）。
- 若日版 tm1 开窗时仍先灌 512 图集占位：L2b **第一期**在设置/领航员路径上改为「开窗只铺空窗格 map、不灌图集」，软缓冲 sync 进这些格——这是 **按窗生命周期映射**，不是全局占段。

---

## 3. 分期（缩小爆炸半径）

### Phase 0 — 骨架（不出 ROM 验收也可编译）

- 新模块：`softbuf.c/h`（或 `vwf_win.c`）  
  - 每窗/每会话一块 1bpp 缓冲（尺寸：`w_tiles * 8 * h_px` 或固定上限，如 30×16 字格量级）  
  - API：`softbuf_begin(win)` / `softbuf_blit_glyph(...)` / `softbuf_flush_tile(...)` / `softbuf_end(win)`
- `InitTextPrinter_hook`：对 **白名单场景** 调 `softbuf_begin`，**不**调 `v8_alloc_begin`
- `PrintNextChar`：白名单 + 中文 → softbuf 路径；其余保持 v8

### Phase 1 — 设置页验收切片

- 白名单：设置页模板/已知 tpl（用现有 scene 识别，禁止写死剧情句）
- 跳过 Multistep 图集灌入（仅该路径；参考曾回滚的 TLWT 思路，但 **返回值/落址改由 softbuf 窗矩形**，禁止 e6f0 全局抬水位）
- 验收：设置页中文选项不花屏、不撞旁路 UI（用户自测；代理不擅自开 mGBA）

### Phase 2 — 领航员

- 同模型接线；字号继续走 Middle 场景表
- 验收：介绍长文不撞

### Phase 3 — 收紧

- tm1 主路径默认 softbuf；v8 仅留应急或删
- tm0/tm3/tm2 按需迁或永久旁路

---

## 4. 文件与符号（预计）

| 路径 | 动作 |
|---|---|
| `hook/src/text/softbuf.c` + `include/softbuf.h` | **新增** 核心 |
| `PrintNextChar_hook.c` | tm1 白名单改走 softbuf；注释改「L2b」 |
| `InitTextPrinter_hook.c` | 白名单改 `softbuf_begin` |
| `tile_alloc.c` | Phase1 **不删**；白名单不再调用 |
| `hooks_origin.s` / `entry.s` | 仅当需新钩开窗时再加（设置页 skip atlas） |
| `build.bat` `game_syms` | 新导出符号登记 |
| `win_canvas.*` | 保持死代码或删；**不**复活假划界 |

---

## 5. 风险与铁律

1. Thumb 跳板：续跑地址奇数、零污染（`axvj-thumb-hook-safety`）。  
2. VRAM 只 `strh`/`str`，禁止 `strb`。  
3. 缓冲放 EWRAM；热路径可后期搬 IWRAM。  
4. 清窗必须 `softbuf_end` + 清对应 VRAM/map，防脏字。  
5. 不改 lexicon 凑显示。  
6. 打包只走 `configs/.../hook/build.bat`；用户说打包再打。

---

## 进度补记（S6 · 2026-09-23）

用户点名 **S6** 后已落地（`--no-pack` 通过）：

- `opt_pixel.c/h` + `opt_pixel_entry.s`
- 设置 tpl：TLWT 开像素会话（返回官方容量）+ Multistep skip 图集
- `Menu_PrintText` 短路 → EWRAM 叠画 → 整页 flush
- softbuf 公式路径已退出链接（文件可留树）

待你打包自测设置页。已知风险：tilemap 按 `(left,top)` 当 screenblock 原点写，若实机窗原点非 (0,0) 需再校正。
