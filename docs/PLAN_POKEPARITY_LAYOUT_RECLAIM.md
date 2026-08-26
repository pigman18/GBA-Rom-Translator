# PLAN — 官方布局回收路线（pokeRS-parity 讨论稿 v0.1，2026-08-27）

> 目标命题（用户提出）：若 CHS 渲染完全接入官方引擎布局（pokeRS 形态），
> scene 门控应该所剩无几。本文档验证该直觉、给出逐 gate 判决预测、
> 分阶段回收计划与风险边界。**讨论稿，未拍板不动手。**
>
> 上位参照:`docs/调研_20260827_pokeRS类12px机制与日版AXVJ00接入分析.md`(pokeRS 全链路)、
> `docs/PLAN_TEXT_RENDER_REFERENCE_BRIDGE.md`(vendored 原语束与 golden 体系)。

## 0. 一句话立场

用户直觉基本成立:scene 门控多的根因不是"12px 天生麻烦",而是当年选择了
**自建 scratch 布局层**(pitch 槽任意分配 + 手工 floor/避让)替代官方布局模型;
pokeRS 证明官方布局模型可以原样承载 12px 中文(它就是官方引擎+数据替换,
连溢出/相位/LUT 都是官方机制在处理)。回收路线=撤掉自建布局层、把落点
交还官方 `GetCursorTileNum/UpdateTilemap`,再将残余的真·VRAM 地盘冲突
降级为 pokeRS 式零星场景补丁。

## 1. pokeRS 参照系(为什么它没有 scene)

pokeRS 对窗布局的假设=完全官方:`dest = win->tileData + 32*GetCursorTileNum(win,c,r)`,
横向溢出由 `DrawGlyphTile_*` 内部按 ±32B 物理邻格处理,tilemap 表项随
`UpdateTilemap` 官方推进。因为从不开小灶,所以不存在"哪个场景布局特殊要绕"的
问题——绕的成本被"服从默认布局"吸收掉了。它的场景适配只剩四条 gfx 微调
(HP框字节 32→20/24、狩猎球名、剩余球数、寄放系统持有物坐标),
性质是"显示区域容纳度"微调,不是布局对抗。

## 2. 现 policy 门控全景与逐条预测判决

实现出处:`src/text/text_render.c` §policy 区(bak 引擎全量并入件)。

| # | 门控 | 现在做什么 | 当年防御对象(推测/实证) | 全官方布局下预测 | 处置 |
|---|---|---|---|---|---|
| G1 | `scene_menu_wants_mode2` | fontNum==3 且非商店的两类 charBase 窗 → 走 Mode2 槽指针路 | tm1/tm3 等宽菜单窗官方 tileData 为共享只读 atlas(等宽假名预渲染),直写会破坏邻近字符 | **保留需求**:atlas 共享是日版数据事实,与是否官方化无关;但官方 `WriteGlyphTilemap_Font1_Font4`/MultistepLoadFont 本身就有 per-char 独立 tile 模型,**可望复用官方槽分配替代 Mode2 自管** | 改造后撤销(降级为配置) |
| G2 | `scene_is_party_footer` / G5 party band | 队伍页脚行的 tile 行定位修正(16px 行界/子带切换) | 页脚行高与 CHS 两列步进的交错定位 bug | 官方 TM 路径下行列语义回归标准,c大概率失效性撤销 | P2 实测裁决 |
| G3 | `scene_is_shop_desc` | 商店描述行定位 | 同上类 | 同上 | P2 |
| G4 | `scene_is_shop_bag_list` | 背包物品名(TILE_BASE=0x8A+14*row)/数量打印器识别+重定位 | 物品名打印器走独立 TILE_BASE 序列,scratch 流与其错位 | 若回到官方 GetCursorTileNum,顺序性恢复,大成分撤销 | P2 |
| G6 | `scene_is_battle_text_window` / `battle_force_linear` | 战斗窗 TILE_BASE 特征匹配 → 强制 linear 路径 | 战斗对话流的 tile 分布特征 | linear 本来就是官方默认;特征匹配本身即"回归官方"的近似物,**有希望整族退役**(保留一个开关防回归) | P1/P2 |
| G7 | `avoid_dex_ui_tile` | 把 [MENU_CURSOR] 与 [UI_ICON] 区间请求重定向到 ALT 带 | 12px 扫描流可能踩官方 ▶游标/UI 图标章(cb2 [0x1E0,0x1FF],勘验实证) | **不消失**:这是真·VRAM 地盘冲突,pokeRS 也要此类(其 HP框 patch 同性质)。形态改为分配器内建避让即可 | 保留(简化形态) |
| G8 | `ensure_linear_dest_floor` + 五组 LINEAR_FLOOR | 各场景 offset 下限(防扫描流低位起步踩官方字库 [0x100)) | 同上地盘冲突 | 官方化+官方 floor 语义(若无)仍需一条通用 floor;五组常数预计收敛成少数 | 大幅收敛 |
| G9 | pitch 相位状态机(`chs_bind_pitch_slot/chs_px/base_tx/write_op`) | 自管相位/游标(off+=2 等) | 官方相位载体原生化后(存 win[0x1A])其实已半官方化;槽簿记是 Mode2 路径附带 | Mode2 撤销后随之退役 | 随 G1 |

小结:#G7/#G8 是真冲突将存活(收编为官方形态内的常规避让);
#G2/G3/G4/G6 是布线补丁,官方路径下预计退化撤销;
#G1/G9 是最大的一块——Mode2 自管层,若官方 per-char 独立 tile 模型可承接则整体退役。

## 3. 必须先回答的四个未知(Phase-0 勘验清单)

P0a. tm1/tm3 官方 `MultistepLoadFont/InitWindowTileData` 预渲染的 atlas 中,
     一个 tile 是否严格独立(官方 F1/F4 WriteGlyphTilemap 单格寻址)?
     CHS 12px 双列若映射"两格",是否天然无邻擦?
P0b. mode2 窗(scratch)当初到底炸过什么?——git 历史/回忆取证;
     若只是当时的临时方案,可直接在 P1 试验中并轨观察。
P0c. tm0 linear 的 `WIN_TILE_OFFSET +2` 是 CHS 自造还是镜像官方某字段?
     (决定 G6 族能否无痛切回官方流。)
P0d. 图标/游标区在官方化后是否仍会被 CHS 扫描触碰?(G7 存废依据)
工具:`gdb_patcher.py log --functions UpdateTilemap --vram-survey` 现成;
每问一轮勘验出结论,避免再造无档门控。

## 4. 回收三阶段(每阶段单独 commit/单独实机验收)

### P1 — 渲染内核官方化(零布局改动)
tm0 linear 两趟 `draw_tile` → `refpr_draw_tile_shadowed`
(gb 栈上 + refpr_colors_init(C/D/E));mode2 门控窗原样保留。
判定:`equivalence_refpr.py` 按 §附桥接配方(span-clear/pack 修正)bit-exact 后切。
风险:tm0 spill 落点差(+2 vs +32B)已证存在 ⇒ **本阶段限制在 startPixel==0 或
w≤8-startPixel 的不溢出 case 先行**(满相位 case 维持旧径),即"部分官方化"。
退出条件:build 绿 + golden 指纹重算比对报告 + 用户抽测对话/战斗文本。

### P2 — 布局回收(tm1/tm3 主战场)
前置:P0a-c 勘验齐。动作:GetCursorTileNum_Mode2 退役,CHS 落点改投官方
`GetCursorTileNum_Origin/WriteGlyphTilemap_Font1_Font4` 家族(vendored 组件已在束内,
或直接调日版 VERIFIED 原生@0x03B9C);G1-G6 门控逐一灰度关闭(场景巡检矩阵见 §5),
G7/G8 收编为分配器内建避让常量。
### P3 — 尾款
draw_tile/get_px/put_px 删除;policy 区剩「scene 巡检出的最小补丁集」
(预期 ≤ pokeRS 的四条量级);equivalence_test.py 指纹重锁新基线。

## 5. 验收场景矩阵(每阶段跑一遍,勾稽不通过项)

开场城市、宝可梦中心菜单、背包(物品名/数量)、商店(列表/描述)、队伍页脚、
对战(双方 HP 框名字/狩猎地带球数)、图鉴、设置页、名牌弹窗、寄放系统左侧持有物。
工具链:打包(`--seed-only`)→ mGBA 手动巡检 + `gdb_patcher --vram-survey` 抽查。

## 6. 回退策略

任一阶段异常:phase 内改动独立成 commit;异常场景将对应 gate 以
宏开关逐个复活定位(禁止无据新 gate);golden 指纹漂移必须书面归因。

## 7. 开放点(拍板前请示)

Q1 P1 的"部分官方化"(不溢出 case 先行)你是否接受,还是要求一把梭?
Q2 G1 Mode2 层若官方模型承接失败(存在无法收纳的场景),接受
   "残留一个精简 Mode2"作为长期形态吗?
Q3 P2 灰度期间允许两套渲染并存编译吗(增大 bin ~KB 级)?
