# 禁止避让带 / 抬水位 —— 只认美版 VRAM 分配器

> 2026-09-09 用户裁定。与 `.cursor/rules/axvj-no-avoidance-band.mdc` 同步。
> 目的：封死两条反复打转的死路，锚定唯一正确方向（复刻美版 VRAM 分配器）。

## 一、两条禁令

1. **禁止无脑抬水位的假做法**
   占段 + 全局顶基址 + `SetBase` 永久改写 + 改 `textMode` 冒充美版。
   详见 `禁止_假划界抬水位冒充美版窗.md`。

2. **禁止测避让带（本文件新增封禁）**
   扫描 / 采样 VRAM 找「空闲带」再把文本 tile 塞进去。一律禁止，包括但不限于：
   - v8 分配器（测避让带 + 贪心排 tile）
   - W0 预算表 / cb-survey / `602 连续空闲` / `cb3 尾巴占用` 等一切变体

## 二、为什么这两条是同一条死路

| | 抬水位 | 避让带 |
|---|---|---|
| 动作 | 主动「固定顶基址占一段」 | 被动「测哪里空就往哪塞」 |
| 本质 | 全局改写，冒充美版 | 依赖场景占用快照，动态漂移 |
| 共性 | **无所有权 / 无生命周期的裸 VRAM 抢占** | 同左 |

区别只在「抢的时机」，都不具备美版那套「分配游标 + 窗口所有权 + 用完释放」。

**实测反例（用户提供）**：「领航员」存放大量宝可梦 / 训练家介绍文本，
空闲带不够放——证明避让带模型在数据量上就站不住。

## 三、唯一正确路线：复刻美版 VRAM 分配器

用户原话要义：**复刻美版引擎，连 UI 都接管到 window 里**。即引入美版 window
系统自带的 VRAM 管理，而不是替日版固定 charblock 共享图集「找空位」。

美版 `text_window.c` 已确认的契约（研读中，随研读补全）：
- `TextWindow_SetBaseTileNum(base)`：设全局游标 `sTextWindowBaseTileNum`，返回 `base+9`（标准框 9 tile）。
- `TextWindow_SetDlgFrameBaseTileNum(base)`：返回 `base+14`（对话框 14 tile）。
- `TextWindow_LoadStdFrameGraphics(win)`：把框 tile 复制到
  `win->template->tileData + TILE_SIZE_4BPP * sTextWindowBaseTileNum`。
- 窗口**开 → 分配一段 → 返回下一段起点**；**关 → 游标回退 / 复用**。

关键差别：美版不是「找空位」，而是**一个单调分配游标 + 明确的所有权与生命周期**。

## 四、自检（写代码前先对照）

- diff 出现「扫描 / 采样 VRAM 空闲区间 → 按区间塞 tile」→ 违规（避让带）。
- diff 出现「固定 span 顶基址 / 按区间永久 SetBase」→ 违规（抬水位）。
- 正确形态：美版式 `sTextWindowBaseTileNum` 游标 + `base+span` 返回 + 关闭复用。
