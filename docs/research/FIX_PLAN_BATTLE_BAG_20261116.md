# 战斗/背包 BUG 修复计划（2026-11-16 用户确认版）

> 本文件是压缩后的唯一权威任务台账。基线：分支 `refactor/drop-f980-slt2`，commit `5f37bd5`。
> 上游文档：`HANDOFF_BATTLE_BAG_20261116.md`（H01–H06）、`BATTLE_EMPTY_TEXT.md`、`BATTLE_MENU_MOVES_TYPE.md`、`BAG_LIST_TILE_COLLISION.md`、`SPECIES_NICK_AND_BAG_ALGO.md`、`P1C_HEALTHBOX_NAME_WIDTH_PLAN.md`。

---

## 0. 用户定的四条准则（最高优先级，每轮必须遵守）

1. **审图模型固定 `trae/glm-5.3-flash`**：bot 采集后的看图验收必须由该模型的子代理执行，不得静默降级为其它模型。
   - 状态（2026-11-16 16:5x）：本会话 `subagentModelSelectionPolicy = null`，显式子代理路由被限制为父路由 `trae/deepseek-v4.1-flash`；`trae` 目录下也无 `glm-5.3-flash`。需用户在 GUI **插件 → 子智能体 → 模型选择** 里启用并勾选 `glm-5.3-flash` 路由后才能派单。
2. **每个修复流程必须四路并行取证**：全网搜索 + 静态反汇编 + 动态 bot 采集 + 动态 gdb。
   - 禁止闭门造车；禁止「改1改2就跑 bot 乱测」。
   - 四路的产物都要落盘到 `work/` 或本文件对应小节。
3. **交付粒度：每轮自验通过后才交给用户实测**。自验 = bot 采集 + 子代理逐帧看图全 PASS + 产物 SHA256 绑定。
4. **验收口径严格照 `bot/SKILL.md`**：撞 UI / 日文是否丢或译 / 文字颜色三项；逐帧 `PASS|FAIL|SUSPECT`；禁止 `bot/verify.py`；旧 ROM 截图作废。

---

## 1. BUG 拆解（实测确认，非文档传闻）

来源：3 次 bot 采集全部绑定产物 ROM SHA256 `862D3385…FACD13`（32505856 B，mtime 2026-11-16 14:14:06）。
run 目录：
- `work/POKEMON_RUBY_AXVJ00/bot/battle_menu_audit/20261116T154437_026318`（105 对）
- `work/POKEMON_RUBY_AXVJ00/bot/bag_blank_rows/20261116T154356_591348`（192 对）
- `work/POKEMON_RUBY_AXVJ00/bot/battle_result/20261116T154713_677256`（835 对）

| ID | 场景 | 现象 | 复现 | 根因（已证） |
|----|------|------|------|--------------|
| **B1** | 战斗主菜单 | 帧 037–065、103–105 框内全白，只剩 ▶ 且 ▶ 跟随输入 | ✅ 致命 | 见 §2 |
| **B2** | 招式表 + PP + 类型 | 帧 066–102 整块全白，只剩 ▶ | ✅ 致命 | 同 B1 |
| **B3** | 战斗对话框 | 帧 019–105 共 87 帧全空，中日文皆无，只剩红 ▼ | ✅ 致命 | 同 B1 |
| **B4** | 对话框内 | 帧 027–036 两排白 ▼（15×2=30 个，7×4px，bbox x96–214 y121–133） | ✅ 高 | `grid_blank_rest_dialogue_line` 把 `TB+1` 当空白 tile 重写，而 `TB+1` 是预载 ▼ |
| **B5** | 敌方名牌 | `ジュカイン♀Lv:24` → `蛇手♀ −Lv:26`，只剩 2 个汉字 + 深绿 `−` 残迹；等级 24→26 | ✅ 高 | 名字缓冲 `0x0202362C` 仅 20B，被 `FC 00 01`+5×4B `F7` 流撑爆（帧 043 dump 实测溢出） |
| **B6** | 我方 HP | `77/115` → `377/115`，多出前导 3，数字行起点 x174→x167，71 帧全有 | ✅ 高 | 血条 CpuSet 掩码覆盖 HP 数字区（P03 三池） |
| **B7** | 我方名牌 | 蓝色竖条（RGB 107,148,255，28px，bbox x129–189 y73–88）压在 `バシャーモ` 与 `Lv` 之间；板外 x≈205–215 有蓝碎片 | ✅ 高 | 同 B6 |
| **B8** | 双方名牌背景 | 米色/浅绿被换成浅绿/深绿条纹（敌方 622→857px、824→583px；我方 746→983、1061→839，互相抵消） | ✅ 中 | 同 B6 |
| **B9** | 我方名 | 仍是日文 `バシャーモ`（敌方已半译） | ✅ 中 | 种名展示通路只覆盖敌方一侧 |
| **B10** | 背包列表 | 第 8 行整行名字丢失只剩 `×1`；光标移到第 7 行时第 7 行也丢 | ✅ 稳定 | 见 §3 |
| **B11** | 战斗撕裂 | 仅 translated，帧 090–104 底部 y112–159 纯黑带；上屏是冻结的过渡帧（UI 上移、菜单框空白） | ✅ 15 帧 | 起始帧 = 招式菜单被重绘为空白的同一帧 ⇒ 疑与 B1/B2 同路径 |
| **B12** | 说明框 | 泄漏 `｜｜begin▁of▁sentence｜｜` 标记 | ✅ | 翻译数据侧，非渲染 |

**不复现（只做回归覆盖，不当活跃 BUG 修）**
- **H01** ▶ 撞首字：192 帧 ▶ 右缘恒 119，首字左缘 120，1px 间隙。
- **H06** 战后软复位：835 帧全非黑，帧 835 正常回 Route 118 草地。

---

## 2. B1/B2/B3 根因（硬件级双层证据）

**层一 · 窗口结构 RAM**（win struct `0x03004170`，IWRAM 偏移 `0x40000+0x4170`）

| 帧 | 侧 | TB | **TILE_OFFSET(+0x18)** | cX | cTX | idx |
|----|----|----|----|----|----|----|
| 043 | origin | 0x1B8 | **0x18** | 2 | 12 | 13 |
| 043 | translated | 0x1B8 | **0x0000** | 2 | 10 | 19 |
| 080 | origin | 0x2C0 | **0x0008** | 25 | 4 | 13 |
| 080 | translated | 0x2C0 | **0x0000** | 25 | 3 | 17 |

⇒ 官方线性累加器 `WIN_TILE_OFFSET`（`game.h:118` 已定义）**从未被 hook 读取/写入**，grep 证明 `hook/src` 里 0 处使用。

**层二 · VRAM tile 内容**（`.vram.bin`，32B/tile）

- tile `0x1B8..0x1C3`：origin 帧 043/080 每 tile 32 字节全非零；translated **每 tile 全 0 字节**。
- tile `0x2C0..0x2CB`：origin 帧 080 前 8 tile 32 字节非零；translated 全 0。

⇒ translated 侧**根本没往这些 tile 写过字模**，是静默跳过，不是画错位置。

**机制**：引擎用 `tile = TB + 2 + band*62 + 2*col`（绝对公式）。TB=0x2C0 / band=4 / col=25 → `0x3EC`，超过绝对上限 `GRID_TILE_LIMIT 0x1F0`，在 `grid_emit:641` 被跳过 → 只推进光标、不写 VRAM、不写 tilemap。
连带证据：BG0 tilemap 32-base 扫描显示 translated 缺 9 个 origin 有内容的块（`0x1800 0x2000 0x2800 0x3000 0x3800 0x5800 0x6000 0x6800 0x7000`）。

**待改点（8 处，全在 `configs/POKEMON_RUBY_AXVJ00/hook/src/text/PrintNextChar_hook.c` + `include/text_grid.h`）**

| 位置 | 现状 | 改为 |
|------|------|------|
| `text_grid.h` L36 | `GRID_TILE_LIMIT 0x1F0u` | 新增 `grid_arena_hi(tb) = min(tb + GRID_TILE_LIMIT, GRID_TILE_BITS)` inline |
| `grid_emit` L641 | `> GRID_TILE_LIMIT` | `> grid_arena_hi(tb)` |
| `grid_load` L716/L720 | 两处绝对比较 | 同上 |
| `grid_clear_tail_pixels` L1196/L1199 | 两处绝对比较 | 同上 |
| `grid_tile_free` L235 | 绝对上下界 | 下界 `tb+2`、上界 `grid_arena_hi(tb)` |
| `grid_tile_find_free` L334 | `n < GRID_TILE_LIMIT` | 同上 |
| `grid_tile_is_other_col_natural` L300/L303 | `arena = tb+2` + 绝对上限 | 上界改相对 |
| `grid_blank_rest_dialogue_line` L1216–1264 | 无条件重写 `TB+1` | `TB >= 0x80` 时跳过（修 B4） |
| `pokenav/PokeNav_TrainerEye_DetailEnter_hook.c` L76–77 | `end = GRID_TILE_LIMIT` | 相对上界（防回归） |
| `pokenav/PokeNav_TrainerEye_ListRedraw_hook.c` L75–76/L91 | clamp/scrub 到绝对上限 | 同上 |

**风险控制**：`TB=0/1` 时 `arena_hi = 0x1F0/0x1F1`，与现状等价 ⇒ 背包/对话/图鉴行为不变。

### 2.1 band 折叠方案：**已实测证伪并废弃**（2026-11-16 20:5x）

上表 8 处只解决「**首行**越界」，第二行仍整行空白。GRID_DIAG 抓到直接证据：帧 080 有 **6 条 `tag=3` SKIP，t0 = `0x41E 0x420 0x424 0x43E 0x440 0x444`**，全 > `0x400`。招式窗 TB=`0x300`，band=4 起点已是 `0x3FA`，第二行落 band4/band5 必然越界。

曾尝试 `grid_band_count(tb)` + `band %= nseg` 折叠。**结果：修好了第二行，但引入更严重回归 —— 方案作废。**

| 对照实验 | 第二行招式 | 底部纯黑带帧数（battle_result 835 帧全扫） |
|---|---|---|
| 不折叠（`grid_arena_hi` only） | ❌ 整行空白 | **0 帧** |
| 折叠（`band %= nseg`） | ✅ 正常出字 | **18 帧**（045–054、077–084，y112–159 100% 纯黑 + UI 上移 + 8 帧完全冻结） |

折叠的致命代价是**行别名**：TB=0x300 时 nseg=4，row0 与 row4 共用同一 62-tile 段，同窗两行文本互相覆盖；TB=0x310/0x320/0x330 时 nseg=3 更糟（row0/row3/row6 三段挤一段）。

⇒ `grid_band` 必须保持 8 段独立。已在源码写入禁止折叠的注释。**第二行招式空白仍是未修缺陷，需另寻方案**（候选：给高 TB 战斗窗改用独立 charBase / 扩 `GRID_TILE_BITS` 到 1024 以上不可能 / 按 origin 的「按字形槽号分配」而非屏幕位置）。

### 2.2 当前交付产物（band 折叠已回退）

- `roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`，33554432 B，SHA256 **`438DD590860C316F9B83CD98999771CC2F1FBCE2057C05AB8CB136472EEF3773`**（= band 折叠前的第 1 轮版本）。
- hook `out/game.bin` = **9884 B**。
- `battle_result/20261116T205201_270863`（835 对，绑定上述 SHA）→ **撕裂 0 帧**。


---

## 3. B10 背包根因（tilemap 级）

bag run 帧 014 / 056，BG0 tilemap `0x0600F800`（vram off `0xF800`），cols 12–30：

- origin 每行都有真实 tile 号（`y=16: 0b9 0f3 0b1 033 0bb 0ad 15d 0d9`）。
- translated `y=2..15` 是顺序分配的 tile（`y=2: 05d 05f 061 …`），但 **`y=16` 和 `y=17` 整行全 `001`（空白 tile）** ⇒ 第 8 行名字格从未写入 tilemap 索引，与「0 墨迹」观测一致。
- 帧 056（光标在第 7 行）translated `y=14: 190 000 1d1 001 001 …`，只剩光标 tile + 空白。
- **关键**：bag 窗口结构两版**字节完全相同**（`tpl=0x81bb544 tm=1 fn=3 TB=1 OFF=0 cX=14 cY=2 cTX=1 cTY=0 idx=2 text=0x81BB544`）⇒ 纯 grid/tilemap 写缺陷，不是窗口初始化问题。

**禁止路线**（handoff §3，用户已否决）：盲改 skip / find_free / 改 left 公式。
**允许**：先加 `-DGRID_DIAG` 编译开关采一次诊断（用户已批准），读 diag ring 定位命中哪条 guard 再改。

---

## 4. B5–B9 血条根因线索

- `UpdateNickInHealthbox @0x08042408`（反汇编见 `work/_hb.bin` + `work/_hb`）：
  - `0x0804243C` → `bl 0x08004298` = `StringTruncate5`（`movs r4,#5; cmp r2,r4; bcc`）→ 硬截 5 字符。
  - 随后 `bl 0x080042F0` = `StringCopy`（`cmp r3,#7` 上限 7）写入 `buffer+3`。
  - 写 `FC 00`、`01`、名字、性别 `0x1D/0x20` → `0x0B 0xB5`/`0x0A 0xB6`，末尾 `FF`。
- 名字缓冲 `0x0202362C`（20B）：帧 043 origin = `96 5c 84 ae 73 1a 00 45 03 0d 29 ac ff 37 00 14 47 41 0c 13 07 10 ab fb ff`（JP PCS 名 + 终止）；translated = `96 5c 84 ae 73 f7 00 10 0a f7 00 09 4c f7 00 01 4b 3d ff 0b bd f7 f7 00 0d 02 f7 00 02 78 f7 00 …` ⇒ **F7 流溢出 20B 缓冲**。
- 扩展池 `0x020231F0`（gStringVar1）帧 043 两侧**全 0** ⇒ 池存在但未启用。
- P03 CpuSet 掩码三处 pool：Alt1 `0x08041760`、Alt2 `0x08042620`、主 `0x08042C38`，已由 `0x04000008` 改 `0x04000006`。
- 种名真函数 `GetSpeciesName @0x0803B11C`，`cmp r2,#0xa` @`0x0803B154` 后接 `0xDDEE`（ble）；`write_plan._copy_limit_patches` 已支持 `bls`+`ble`，需确认种子路径覆盖到。

---

## 5. 轮次计划与验收口径

| 轮 | 修 | 交付前必须自验 |
|----|-----|----------------|
| **第 1 轮** | B1 B2 B3 B4（+ 可能连带 B11） | `build.bat` → 全量打包 → bot 跑 `battle_menu_audit` / `dialogue` / `bag_blank_rows` / pokenav → 子代理逐帧看图全 PASS → VRAM tile `0x1B8+`/`0x2C0+` 非零 → 9 个缺失 tilemap base 回填 |
| **第 2 轮** | B5 B6 B7 B8 B9 | bot 跑 `battle_result` / `battle_species_name` → 血条名/HP 数字/名牌背景逐帧审图 |
| **第 3 轮** | B10 | 先 `-DGRID_DIAG` 诊断 → 改 → bot 跑 `bag_blank_rows` 192 帧，行 7/8 名字回来且行 1–6 无回归 |
| **第 4 轮** | B11（若未随第 1 轮消失）+ B12 | 密集采集定位；B12 走流水线侧 |

### 5.1 第 1 轮状态：**已交付，但 B2 第二行未修**（2026-11-16 21:0x）

- 产物：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`，33554432 B，SHA256 `438DD590860C316F9B83CD98999771CC2F1FBCE2057C05AB8CB136472EEF3773`。
- hook `out/game.bin` = 9884 B。
- bot run `battle_menu_audit/20261116T175417_654034`（105 对）→ `analyze_battle_menu_frames.py` = **104 PASS / 0 FAIL / 0 SUSPECT**。
- bot run `battle_result/20261116T205201_270863`（835 对）→ **撕裂 0 帧**。
- 视觉确认（帧 080）：**第一行**招式「抓 / 啄」、`PP 31/35`、「类型／ 一般」出字；主菜单帧 043「战斗 / 宝可梦 / 道具 / 逃跑」四项齐全。
- 已消除：B1（主菜单空白）、B3（对话窗空白）、B4（两排白 ▼）、B7（蓝色竖条）。
- **B2 仅部分修复**：招式表第二行（「二连踢 / 火焰踢」）仍整行空白 —— band 折叠能修但引入 18 帧撕裂，已废弃（见 §2.1）。**下一轮必须另寻方案**。
- **B11 未修**：本产物撕裂 0 帧（对照实验证明折叠才是撕裂来源），但第二行空白仍在。
- **B10 仍复现**（按计划留第 3 轮）：背包第 8 行仍只剩 `× 1`。
- 子代理审图（2026-11-16 20:4x，**本轮按用户决定降级为 `trae/deepseek-v4.1-flash`**，违反规则 1，规则 1 从第 2 轮起严格执行）结论：
  - `battle_menu_audit` PASS（29 帧）／ `bag_blank_rows` PASS（17 帧）／ `dialogue` PASS（18 帧）／ `start_menu` PASS（14 帧）
  - `navigator` SUSPECT（帧 140 行尾末字被屏幕右缘裁切，译文变长导致，未破 UI）
  - `battle_result` FAIL（该次审的是折叠版 18 帧撕裂；折叠已废弃，本产物重跑后 0 帧）
- 已知既有缺陷（**非本轮引入**，2026-11-15 旧产物同样存在）：招式面板汉字间隙白块；战斗菜单第四项「道具」首字黑块；敌方名牌种名残字「蛇手」；我方名 `バシャーモ`；我方 HP `377/115`；开始菜单玩家名行「1ッキ」（origin「ユウキ」）。

### 5.2 B2 第二行：两种候选方案**均已实测证伪并回退**（2026-11-17）

问题本质：`grid_tile = TB + 2 + band*62 + 2*col` 是**屏幕位置**分配，而 tile 号只有 10 bit（<0x400）。高 TB 战斗窗（0x2C0/0x300/0x310/0x320/0x330）根本没有 8×62 的空间，band4+ 必然越界。

> ⚠️ 本节 2026-11-16 写的「✅ 候选正解：线性槽分配」是**错的**，已被同日实测证伪，见下。

**方案 A：band 折叠（`band %= nseg`）** — ❌ 2026-11-16 已证伪，18 帧撕裂。

**方案 B：越界改走线性槽 `TB+2+2*rel`** — ❌ 2026-11-17 实测证伪，同样 10–23 帧底部黑带。

两次 bot 采集对照（产物 `a9e3c6a8…`，`battle_result` 835 帧全扫，判据 = translated 底部 y112–159 纯黑但 origin 同帧正常）：

| run | 额外黑带帧 |
|---|---|
| `20261117T162903_769216` | 10 帧：045–054 |
| `20261117T163220_697553` | 18 帧：073–080、153–159（+ …） |

根因：**行别名**。线性槽 `TB+2+2*rel` 在同一窗口内忽略了行号，第二行（band4+）与第一行共用同一批 tile，两行文本互相覆盖 → 屏幕下半 48 行整片重绘成黑。

反例（回退后同 SHA 复采）：`20261117T163812_365283` 额外 4 帧、`20261117T164027_585667` 额外 **0 帧** ⇒ 该黑带对 bot 采集时序敏感（同一 ROM 三次采集：0/4/0 帧），但方案 A/B 稳定拉高到 10–23 帧，判定为真实回归。

**当前状态**：`PrintNextChar_hook.c` 已回退到第 1 轮版本（`band` 保持 8 段独立、`grid_arena_hi` 仅抬高上界不折叠）。产物 SHA 回到 **`438DD590860C316F9B83CD98999771CC2F1FBCE2057C05AB8CB136472EEF3773`**（33554432 B，hook `game.bin` 9884 B）。

**B2 仍是未修缺陷**；后续可行方向只剩「给高 TB 战斗窗换 charBase 另找 ≥8×62 空间」，需先确认战斗 BG 的 charBase 余量，不要再用折叠/线性槽。

### 5.3 第 2 轮（2026-11-17）验尸结论

- **审图员**：`dshgw/workbuddy/glm-5.3-flash`，已固化为常驻子代理 `glm-reviewer`（见 `REVIEW_MODEL_ROUTE_20261117.md`）。
- 该模型在实验产物 `a9e3c6a8` 上**独立发现**了招式表第二行空白消失（B2 表面修好）以及 PP/类型框灰底、HP `377/115`、背包项乱码、敌方名牌假名错排——四项均已确认为**既有缺陷**，非本轮引入。
- PP/类型框灰底已像素级坐实：origin 该区主色 `FFFFFF`（1491 px），translated 主色 `D6D6CE`（1299 px）⇒ 真实调色差异，进后续轮次。
- ⚠️ **glm 审图路由已不可用**：`workbuddy/glm-5.3-flash`（dshgw）、`doubao/person-glm-5-3-flash-261111`、`trae/glm-5.3-flash` 三条路由 2026-11-17 17:00 后**全部连续失败**（子代理无收尾消息即退出），疑为账号积分耗尽。本轮后半段改用主代理自身读图 + 像素统计完成核验。**下一轮开始前需先修好审图路由。**

### 5.4 B2 已修复（2026-11-17 第 2 轮交付）

**修法**：`grid_tile_overflow()` —— 只对「位置公式越界、本来会被静默丢弃」的格子做兜底：在本窗 arena `[TB+2, 0x400)` 内，挑一对「本窗 tilemap 未引用 + VRAM 该对为空」的 tile（判据与既有 tile 冲突规避同源），再写 tilemap 指过去。

- 关键：**不改 `grid_band`、不改 tile 号公式**，所以不会出现行别名；它严格是「从无到有」。
- 找不到空位时保持旧行为（丢弃），不会退化成花屏。

**验证（产物 SHA256 `5D88EB7215061A2CAE1C40B108ACDED9BC4EDC54BE8B76BF5174D974395A89CA`，33554432 B，hook `game.bin` 10084 B）**：

| 项 | 结果 |
|---|---|
| `battle_menu_audit` 帧 080 VRAM tile 0x300–0x33F | translated 58 个非零 vs origin 57 个（基线版该区 translated 全 0） |
| 招式表第二行 | ✅ 四招全出：抓 / 啄 / 二连踢 / 火焰踢，▶ 光标位置与 origin 一致 |
| 全 105 帧整块空白扫描 | ✅ 0 帧（判据：translated 墨量 < origin 35%） |
| `battle_result` 835 帧撕裂 | ✅ 额外 0 帧（translated 黑带帧 = origin 黑带帧 = 2–6 转场） |
| `battle_result` 对话框文字区空白 | ✅ 0 帧（判据：同阶段相似度 ≥0.93 且 origin 该区墨量 >150、translated <20） |
| A/B 像素差（vs 基线 `438dd590`） | origin 侧 0.0535 = 纯 RNG 基线；translated 侧 0.072 = 多出的正是 B2 修复区域 |

> ⚠️ 扫描踩坑记录（别再用错判据）：整屏按 8px 横带比墨量会**大量误报**。
> 原因：origin 有敌方血条 UI / 我方仍在招式菜单，translated 已进入结算（RNG 导致阶段不同）；
> 且中文笔画比日文细，墨量天然偏低。必须先用「同阶段相似度」过滤，再只查**已知文字区域**。

**仍未修（后续轮次）**：B5–B9 血条族（HP `377/115`、名牌、蓝竖条、背景色）、B10 背包（干净基线上第 8 行有墨迹，需按新 run 重判）、B12 说明框标记泄漏、PP/类型框灰底。



每轮完成：更新本文件 §5 状态 + `HANDOFF_BATTLE_BAG_20261116.md` 台账。

---

## 6. 已知坑 / 别踩

- `roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba`（SHA256 `6809C9D2…`，33554432 B，11/15 22:32）是**旧产物**，其内嵌 hook 二进制（10052 B）与当前不同 9255 字节，且**不含任何 `TILE_OFFSET`/Linear/`0x180`/`0x1F0` 字面量**，但 `work/_cmp/old_080.png` 证明那版能正确渲染高 TB 战斗窗口 ⇒ **不要试图从 `_new.gba` 反推补丁**，只能从 origin 行为重新推导。
- `BATTLE_EMPTY_TEXT.md` §6 声称的两个 fix、`BATTLE_MENU_MOVES_TYPE.md` §5.5 声称的 `grid_use_linear`，**源码和 git 里都不存在**（`git log -S grid_use_linear` 只匹配文档 commit）。文档不能当已落地事实。
- 打包命令：`cd /d C:\code\GBA-Rom-Translator` → `set PYTHONPATH=%cd%\src` → `C:\Python314\python.exe -m meowth full roms/origin/POKEMON_RUBY_AXVJ00.gba -o roms/outputs --work-dir work --source ja --target zh-Hans --seed-only`（`--modules` 已废弃）。
- 改 `hook/src/**` 后**必须**先 `cd configs\POKEMON_RUBY_AXVJ00\hook && .\build.bat`，流水线只嵌入现成 `hook/out/game.bin`。
- 工具链：`arm-none-eabi-gcc` @ `C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin`；Python `C:\Python314\python.exe`；mGBA dev @ `tools\mgba_dev\mGBA-build-*/mGBA.exe`。
- PowerShell 控制台 GBK：打印中文前先 `$env:PYTHONIOENCODING='utf-8'`。
- ROM 内 hook 反汇编技巧：取 `rom[off:off+len]` 存 raw bin，再 `arm-none-eabi-objdump -D -b binary -m armv4t -M force-thumb --adjust-vma=0x08000000+off`。
