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

## 待办 / 约定

- 设置菜单 tm1 布局拟从 `TM1_ROW_TAB` 等文件级字面量，重构为
  **按窗口模板地址键控的静态配置表**（未登记模板走默认，不猜场景）。
- 打包被标题 logo 阻塞时，可从 build 阶段产物
  `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba` 手动补 32MB 对齐出可测 ROM。
- 识图用仓库根 `vision.js`（需 `.env` 配 VISION_API_KEY / VISION_MODEL）。

## 相关文档

- `docs/复盘_20260829_设置菜单tm1落址BUG链.md` —— tm1 落址 BUG 链与方法论
- `docs/FONT_12PX_DRAW.md` —— 12px 绘制约定（相邻字共享 tile 等）
- `docs/START_HERE.md` —— 任务分类判断树
