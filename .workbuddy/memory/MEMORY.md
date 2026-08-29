# 项目长期记忆（GBA-Rom-Translator / AXVJ00 汉化）

## 用户偏好：场景（scene）门控的边界

- ✅ **可接受**：按**固定窗口**做特殊配置——以稳定标识（如窗口模板地址 `0x081BB874`）
  为键的**声明式静态配置表**，一条窗口一条记录，数字显式写出来，可审计可回归。
- ❌ **不接受**：**启发式 scene 门控**——靠 tileBase 区间 / 光标值 / 模板字段
  （如旧 bak `text_scene.c` 的 `screen_menu_mode2` / `screen_shop_bag` /
  `screen_party_footer`）去"猜"当前是哪个场景。这类门控会误判且难验证。
- **推论**：隐式的、散落在代码里的字面量（只为某个窗口调过参数却没声明属于谁）
  比两者都糟——至少启发式还有名字和 gate，裸数字两样都没有。

> 背景：tm1 每个窗口的字库都铺满 tile [1,513)，"哪些 tile 空闲"取决于**该窗口
> 实际引用了哪些字形**，是天生的 per-window 数据。所以这里的选择不是
> "要不要配置"，而是"声明式配置"还是"隐式字面量"。

## 用户偏好：修 BUG 时**不要擅自回退到已知旧版本**

- 当前方案出了 BUG，优先**在当前方案上定位并修掉**，而不是退回上一个"实测通过"的旧版本。
  用户原话：「别随便回退啊……那个（旧版本）可以啊」——指的是**旧版本里没出问题的那部分**，
  不是整版回退。
- 若确实认为必须回退，先说明理由并等用户确认，不要直接改。

## tm1 落址模式结论（2026-08-29）

- **当前生效：`TM1_MODE_MIX`**（混合模式）。按 curX 分区，每区独立选策略：
  标签列 `curX<8` → PTR 固定槽（16px 步进，幂等）；候选列 → DYN 动态 12px。
  规则表是 `text_scene.c` 的 `kOptZones`，支持任意多段（末条 cx_hi=0xFF 兜底）。
  PARTITION / GRID / PTR 三种旧模式行为完整保留，切 `OPTION_MODE` 即可回退。
- **DYN 段不占选中态额外 tile**：选中色 = 换个前景色**重画一遍**到同一处。
  只有 PTR 固定槽才需要红字镜像槽（槽内容长期有效，红色版本必须另存）。
  标签列不吃高亮 ⇒ `chs_slots_sel.inc` 当前为**空表**（省 164 tile 给动态区）。
- **容量算法**：12px n 字最大 off = **4n-2**，占 **4n** 个 tile（不是 2n+4）。
  3 字 → off 到 10，占 12 tile，span 要给 12。
- **PTR 的 16px 字距是固有限制，不是 BUG**：固定槽 ⇒ 相邻字无法共享中间 tile
  ⇒ 每字独占 2 列 = 16px 步进。12px 的本质是"相邻字共享一个 tile"，与固定槽互斥
  （共享列的 tile 内容取决于"字A+字B"组合，41 字 ⇒ 1681 组合，装不下）。
- 16px **不额外耗 tile**：12×16 与 16×16 都是 4 tile/字。
  → 若嫌字散，正解是**把字模做成 16px 宽填满格子**，别回头死磕 12px。
- **选中态槽必须 per-glyph**：选中/未选中字模颜色不同，不能共用槽；
  而选中槽若按"组内第几个字"共用（旧实现），光标一移动就会顶掉旧选中行
  仍在引用的那批槽 → 文字替换。现为 `chs_slots_sel.inc`（与 `chs_slots.inc` 同序）。
- **PTR 唯一维护成本**：槽表是构建期静态数据，取决于"译文用到哪些汉字"。
  译文变更（增删汉字）后**必须**重跑 `scripts/gen_tm1_slots.py`，
  否则新汉字回退旧路径。该脚本会**自动从 text_scene.c 读 kOptRows 与
  kOptZones 的 off/span 当禁区**，所以改完布局直接重跑它，槽表不会与配置脱节。

## ⚠ 两个坑（2026-08-29 实证）

- **8px 小字库（FontChsSmall / font=4）字形有误**：设置菜单"对战规则"的"战"
  显示成日文"対"。设置菜单一律用 12px 字库（font=0）。
- **`kOptRowSpans` 给 0（"该行不用行区"）是危险开关**：span=0 时 `chs_blit`
  不复位 win[0x18]，该行若有中文就会落到 `行基址 + 残留偏移` —— **写到 charblock
  外面**。现象极具欺骗性：屏幕上看着正常，实际已越界。
  某行"有没有中文候选"必须**识图/实测确认**，不能靠猜（按键模式行就是
  `普通/LR/L`，我误判成全字母，结果"普通"写到 tile 551）。

## 识图方法

我这边直接 Read PNG 会失败，**识图一律走仓库根 `vision.js`**（需 .env 配
VISION_API_KEY / VISION_MODEL）：
```
node vision.js bug/<目录>/10.PNG "逐行列出左边标签和右边选项的每个汉字"
```

## 代码分层约定（2026-08-29 与用户确认）

- `hook/src/text/text_scene.c` —— **只放配置**（声明式静态表，一窗一条）
- `hook/src/text/text_layout.c` —— **只放算法**（查表、求值、分区选择、槽查询）
- `hook/src/text/FontFunc_hook.c` —— 只消费落址结果，负责"怎么画"
- 新增 tm1 窗口：在 text_scene.c 加配置并登记进 `kTm1Windows[]`，算法侧不用动。

## 待办 / 约定

- 每次打完 ROM 先跑 `scripts/check_rom_hook.py`：确认 game.bin 与 ROM 逐字节一致
  + 读回 `kOptWindow.mode`。**"源码全对但运行不对"要先排除"打进去的是旧包"。**
- 设置菜单 tm1 布局拟从 `TM1_ROW_TAB` 等文件级字面量，重构为
  **按窗口模板地址键控的静态配置表**（未登记模板走默认，不猜场景）。
- 打包命令（bash 下 PYTHONPATH 必须用 Windows 路径，`/c/...` 格式 Windows Python 不认）：
  `PYTHONPATH='C:\code\GBA-Rom-Translator\src' C:/Python314/python.exe -m meowth full ...`
- 打包被标题 logo 阻塞时，可从 build 阶段产物
  `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba` 手动补 32MB 对齐出可测 ROM。
- 识图用仓库根 `vision.js`（需 `.env` 配 VISION_API_KEY / VISION_MODEL）。

## 相关文档

- `docs/复盘_20260829_设置菜单tm1落址BUG链.md` —— tm1 落址 BUG 链与方法论
- `docs/FONT_12PX_DRAW.md` —— 12px 绘制约定（相邻字共享 tile 等）
- `docs/START_HERE.md` —— 任务分类判断树
