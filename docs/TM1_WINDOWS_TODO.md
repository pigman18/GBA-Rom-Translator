# tm1 中文渲染 — 自动 tile 分配（已废弃白名单机制）

> 状态：2026-08-31 白名单消除完成。架构 = `REWRITE_DESIGN_混合写入架构.md`
> §4.1 例外条款 1。

## 变更摘要

v5 之前：每个 tm1 窗口需在 `kTm1Windows[]` 手动登记空闲 tile 段（需 gdb 取证）。
v5 现在：所有 tm1 窗口统一从 tile 512 起自动分配，无需逐窗配置。

### 原理

- `InitWindowTileData` 预渲染字模占 tile 0..511
- 官方 mode1 至多写 BASE+2*127=254+1=255 ≤ 511 → tiles 512..1023 无原生引用
- `TILE_OFFSET` 由 `AddTextPrinter` 每行清 0
- 中文方案：行首（TILE_OFFSET==0）自动设 512，跳过预渲染区
- 此后与 tm0 完全同构（col_stride=2 / lower_delta=1 / 相位机制照用）

### 已删除

- `kTm1Windows[]` 白名单表
- `Tm1TileCfg` 结构体
- `tm1_row_alloc()` 函数
- `ADDR_TPL_DEX_LIST` / `DexListWindowTemplate`（不再需要）

### 待验收

所有 tm1 窗口中文显示需用户实测：
1. 图鉴列表页（原已登记窗口，应无回归）
2. PSS 能力数值窗
3. 队伍底栏
4. 队伍名
5. 图鉴说明窗
6. 其他 tm1 窗口

## 非 tm1 缺口（步骤 3 其余项）

| 项 | 现状 | 计划 |
|---|---|---|
| tm2 血条（对战数值） | PrintGlyph 只消费推进 `win[0x20]`，中文不画（8px 槽塞不下 16px 字） | 对照美版 pokeRS `main_R.asm` 血条 ×3 专用 hook；中文是否需要出现先拍板 |
| 寄放系统 ×2 | 无任何 hook | 同上，逐个收敛，不做通用机制 |
| 捡拾道具提示 | 走标准打印器，textMode 未确认 | gdb 确认 textMode；若 tm0 则已在覆盖路径，回归"复发路径"即可 |
| 静态预渲染烘焙 | 未做 | 清单枚举后按 D 商重绘思路走构建期管线，优先级最低 |
