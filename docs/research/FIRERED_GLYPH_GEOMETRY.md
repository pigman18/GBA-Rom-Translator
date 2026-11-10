# FireRed glyph geometry (Phase 0 lock)

> ROM：`roms/translated/宝可梦火红日版汉化2.2.gba`  
> 对照：`roms/origin/POKEMON_FIRE_BPRJ00.gba`  
> VRAM 实证：`work/_probe/snap3/vram.bin`（标题/继续游戏屏，pal=15 文字带）  
> 关联：`FIRERED_RENDER_ENCODING.md`（字宽档 2/10/12）、`FIRERED_RENDER_FINAL.md`（早期 11px 读数）、`scripts/research/firered/198_true_width_glyphs.py`

## 1. 实测（snap3 列投影）

| 量 | 值 | 证据 |
|----|-----|------|
| 汉字墨迹宽 | **12 px**（主峰；偶发 11） | band0 四段全部 width=12；band5 五段 width=12 |
| 水平字距 / pitch | **13 px**（12 墨 + 1 隙） | band0/band5 `pitch_mode=[(13, n)]` |
| 行带高度 | **12 px**（y=11..22 等） | 六条文字带均为 h=12 |
| 屏上承载 | 2×2 个 8×8 tile（16×16 格） | tilemap 邻项连续；字形跨 tile 连续点阵 |
| 是否 8+4 / 4+8 双趟拼 | **否** | 单字一次连续写入；无左 8 再右 4 的排版相位产品语义 |
| 字宽引擎档 | 2 / 10 / **12** | 反汇编 `cmp … → 12/10/2`（见 encoding 定案） |

早期 `FIRERED_RENDER_FINAL` 记「11×11 / 步进 13」来自灰度截图像素估读；**以本文件 VRAM 列为准：12 墨 + 13 pitch**。

## 2. 开始菜单三字尺（「宝可梦」类）

| 目标 | 公式 | 结果 |
|------|------|------|
| 火红三字占用 | `12 + 13 + 13` 或首起→末止 `pitch×2+ink` | **≈38 px**（band0：x=26..63 → 38） |
| AXVJ 验收目标 | `CHS_GLYPH_ADVANCE_PX × 3`，advance=**12** | **36 px**，菜单三项汉字自然落格，不靠 biphasic 拼缝 |

尺规含义：产品观感对齐火红「约 12px 汉字 + ~1px 字距」，**不是**把 Ruby 改成火红 F7 组字编码。

## 3. T1 vs T2（本阶段锁定）

| 方案 | 存储 | 绘制 | 判定 |
|------|------|------|------|
| **T1** | 真 ~12 宽槽（如 12×16 4bpp ≈96B/字） | 单趟 blit + advance 12 | 远期格式；需重建字库与取字 `<<7` |
| **T2（锁定）** | 仍可 128B 取字（TL·BL·TR·BR），**不作产品叙事中的「8×16 字号」** | **单趟**连续写 12 列 + `CHS_GLYPH_ADVANCE_PX=12`；**删除** 8+4 双趟编排（中途改 `chs_px` / `TILE_OFFSET`） | **Phase 1–2 采用** |

锁定理由：

1. 火红观感由 **advance≈12 / 连续墨迹** 决定，不由「是否 128B 文件格式」决定。  
2. AXVJ 仍走 Ruby `PrintNextChar` + Mode2/Linear（见 `ruby_text.md`）；T2 不拆窗公式，只改绘制编排。  
3. 用户本轮否决：**双相 8+4/4+8** 与 **把 8×16 当产品字号模型**；T2 满足否决且可立刻改 hook，无需先重建 BDF。

T1 仅在 T2 绘制验收通过后，作为可选字库收敛（另开任务），不阻塞本计划。

## 4. 对 AXVJ 的硬约束（转入 Phase 1）

- 单趟 blit；`glyphWidth` 常态 **12**；Small（fontId=4）仍可 width=8 单列。  
- ink-only；禁止 ShadowedFont bg OR；禁止默认 advance 16。  
- Mode2 vs Linear 门控与 `ruby_text.md` 公式保留；只删双趟 orchestration。  
- 编码（F9 旁载等）可后随；本文件不改注入协议。

## 5. 自检

- [x] 火红 VRAM 墨宽 / pitch / 行高已测  
- [x] 三字菜单尺已给出（FR≈38 / AXVJ target=36）  
- [x] T2 锁定；T1 标为远期  
- [ ] 字库重建 — **禁止**在本 Phase 0 执行（计划原文）
