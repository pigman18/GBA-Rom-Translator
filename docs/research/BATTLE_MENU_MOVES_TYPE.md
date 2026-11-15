# 战斗主菜单 / 四招式 / PP+类型：调研

日期：2026-11-15  
范围：**只调研**，收口前不改 `PrintNextChar` / 绘制。  
产物 ROM：`roms/outputs/POKEMON_RUBY_AXVJ00_translated.gba`（以 bot manifest sha 为准）

## 1. 用户现象（截图）

| 区域 | 现象 |
|------|------|
| 主菜单 2×2 | 「战斗」可读；「背包/逃跑」残缺或碎块；白/灰补丁 |
| 四招式格 | 仅见「抓」「啄」等单字+灰底；下两格常空 |
| PP / 类型 | 「PP」「类型/」与数值/属性名之间大白块；属性名带灰底 |
| 底框台词 | 「バシャーモ怎么办？」名仍日、句中文（另案混语） |
| 血条名 | 乱码/残墨（另案 tm2，不绑本票） |

## 2. 全网 / pret 对照

US pokeruby `battle_controller_player.c`：

| 调用 | tileDataStartOffset | left | top |
|------|---------------------|------|-----|
| 主菜单 `BattleText_MenuOptions` | **400 (0x190)** | 18 | 35 |
| 招式名 `sub_802E12C` | **0x300 + i×20** | i奇?11:1 | i<2?0x37:0x39 |
| PP 数值 `sub_802E220` | **0x2A2** | 0x19 | 0x37 |
| 类型名 `sub_802E2D4` | **0x2C0** | 0x17 | 0x39 |
| PP 标签 | **0x290** | 0x17 | 0x37 |
| 清区 | `Text_FillWindowRect(..., 0x1016, ...)` | 多矩形 | |

共性：**同一 win 模板、textMode=0 Linear、调用方指定高段 TILE_BASE**，官方用 `TILE_BASE+TILE_OFFSET` 线性累加，**不是** `TB+band×62+2×col` 网格。

## 3. AXVJ 反汇编（origin ROM）

### 3.1 主菜单 `0x0802D7C8`

```
gBattle_BG0_Y = 160
FillWindowRect ×2（清左右区）
Text_InitWindow8002E4C(win=0x03004170, str=0x083DC9AF,
                       tileStart = 200<<1 = 400, x=19, y=35)
Text_PrintWindow…
Text_InitWindow8002E4C(..., gDisplayedStringBattle@0x0202362C,
                       tileStart = 220<<1 = 440, x=2, y=35)  ; 「怎么办」句
```

字面量点是 **JP `0x083DC9AF`**（非 KEEP-US `BattleText_MenuOptions@0x08400CF3` 那块数据）。

### 3.2 PP / 类型（`0x0802B61A` / `0x0802B6BA` 一带）

| 项 | 编码 | 值得 |
|----|------|------|
| PP 数值 | `ldr r2, =0x2A2`；x=24 y=55 | 与 US 同 TB |
| 类型 | `movs r2,#176; lsls #2` → **0x2C0**；x=25 y=57 | TB 同，坐标略偏 |
| PP 标签 | `movs r2,#164; lsls #2` → **0x290** | 同 US |
| 清区 | `FillWindowRect` tilemap 项 **0x1016** | 同 US |

### 3.3 招式名循环（`0x0802B500+`）

- 先 `FillWindowRect(..., 0x1016, x=1..16, y=55..58)` 清招式区  
- 循环 `i=0..3`：拼串 → `Text_InitWindow8002E4C`；`movs r1,#192` 参与 **0x300+f(i)** 计算；y∈{55,57}，x∈{1,10}  
- 符号表 `sub_802E12C@0802B818` 落在字面量/短桩，**真体在前方 `0x0802B500` 一带**（以 BL `0x08002CFC` 为准）

### 3.4 与汉化绘制的冲突（假说，待 bot/GDB 钉死）

| ID | 假说 | 预期证据 |
|----|------|----------|
| H1 | tm0 战斗高 TB 被送进 **grid band**，字写到与 `0x1016` 清区/官方 Linear 槽错位的 tile → 灰底块、缺格 | GDB `InitTextPrinter`：TB∈{0x190,0x2A2,0x2C0,0x300+} 且 translated `TILE_OFF` 不累加；shot 灰底 ROI |
| H2 | 中文 12px 宽 > 日文 2×2 槽宽，主菜单空格排版挤爆「背包/逃跑」 | origin 四项完整 vs zh 右列残；串内仍是空格非 CLEAR_TO |
| H3 | 相对 arena 修复后上两招可见、下两招仍 skip（col/band 或第二次 Init 被清） | `bt_move_3/4` 仍空；GDB 有 Init 命中 |
| H4 | 白块 = FillWindowRect(0x1016) 后 tilemap 仍指空白，字形没写回对应 cell | origin 同帧无大白；zh PP/类型行 white_ratio 高 |
| H5 | 协议/译文本身坏 | **否**：串含 F7；部分字已画出 |

**协议不动**；布局不靠改 lexicon。

## 4. Bot / GDB 计划

场景：`bot/scenes/POKEMON_RUBY_AXVJ00/battle_menu_audit.lua`  
分析：`bot/analyze_battle_menu_frames.py`  
固定遇敌：`poke gRngValue@0x03004818 = 0xAAAA` + `hunt`（与 battle_full 同款）；物种从 `*.ram.bin` 读 `gBattleMons` 复核两侧一致。

```
BOT_DUMP_ALLWINS=1
python bot/run.py POKEMON_RUBY_AXVJ00 battle_menu_audit \
  --gdb InitTextPrinter --gdb-side both
python bot/analyze_battle_menu_frames.py <run_dir>
```

## 5. 取证结果

### 5.1 Bot 跑次

| run | 用途 | 野宠 |
|-----|------|------|
| `…/battle_menu_audit/20261115T220537_719421` | +`--gdb InitTextPrinter` | 分岔（GDB 打断点加剧） |
| `…/20261115T220747_464004` | 无 GDB，单次钉 RNG+hunt | 仍分岔（拉电 vs 长翅鸥） |
| `…/20261115T221044_969315` | **hunt 逐步钉 RNG**（`rng_addr/value`） | 仍分岔：origin 6 步蛇纹熊 / zh 10 步雷电兽 |

逐步钉 RNG **不能**消掉「两侧遇敌步数差」→ 野宠种仍可能不同。  
**菜单/四招式对照不以野宠为准**：同一 `Route118_68-7.sav` 我方火焰鸡招式固定（ひっかく/つつく/にどげり/ブレイズキック ↔ 抓/啄/…）。

逐帧描述：`frame_descriptions.md` + **看图** `agent_verdict.md`（指标稿会误 PASS，以看图为准）。

### 5.2 GDB `InitTextPrinter`（两侧各 15 次高 TB，集合相同）

| TB | hex | 用途（与 pret/反汇编一致） | cur_x |
|----|-----|---------------------------|-------|
| 400 | 0x190 | 主菜单四项 | 0x13 |
| 440 | 0x1B8 | 「怎么办」句 | 0x02 |
| 768 | 0x300 | 招式0 | 0x02 |
| 784 | 0x310 | 招式1 | 0x0A |
| 800 | 0x320 | 招式2 | 0x02 |
| 816 | 0x330 | 招式3 | 0x0A |
| 656 | 0x290 | PP 标签 | 0x13 |
| 674 | 0x2A2 | PP 数值 | 0x18 |
| 704 | 0x2C0 | 类型名 | 0x19 |

win 恒 `0x03004170`。**四招 Init 都有** → 下两格空 ≠「没调用打印」。

### 5.3 看图（`221044` / 与用户截图同构）

| 帧 | origin | translated |
|----|--------|------------|
| bt_menu | たたかう/バッグ/ポケモン/にげる 白底清晰 | 战斗/宝可梦+灰底；背包残片；逃跑竖黑切 |
| bt_move_1 | 四招完整；PP 31/35；わざタイプ/ノーマル | 仅抓/啄+灰底；下空；PP 间白块；一般灰底 |
| bt_move_3 | 光标在三；にどげり | PP/类型已是格斗 24/30，**左栏仍几乎只有上两格字** |

### 5.4 假说结论

| ID | 结论 |
|----|------|
| **H1** | **成立（主因）**：战斗 tm0 + 高 TB 被网格 `TB+band×62+2×col` 画；官方是 `TB+TILE_OFF` 线性槽。相对 arena 后字能写出，但落点/清区（0x1016）错位 → 灰底块、白洞、缺格 |
| **H2** | **成立（主菜单右列）**：中文宽 + 空格排版挤爆背包/逃跑；宜 CLEAR_TO/绘制宽，不改 lexicon |
| **H3** | **否**：GDB 证明 0x300..0x330 四次 Init 都在 |
| **H4** | **成立**：白块 = FillWindowRect(0x1016) 后字形未写回对应 cell |
| **H5** | **否**：串非空（F7/部分汉字可见） |

### 5.5 已实施（2026-11-15）

1. **`grid_use_linear`**：`textMode==0 && TB≥0x180` → tile=`TB+TILE_OFFSET`，emit 后 `OFF+=2*delta`；空格同步 `OFF+=2`。  
2. **白底 bg**：菜单/招式/PP/类型用 `win COLOR_D`（FC 后 0x0E=pal 白）；`tpl[6]=0x0F` 在战斗 pal 下是灰。0x1B8 底框仍用模板色。  
3. 产物：`roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba`（主文件若被 mGBA 锁住）。  
4. bot 复验 `…/battle_menu_audit/20261115T223238_731390`：四招齐全、菜单四项可读、灰底基本消失。  

### 5.6 残留（另票）

- PP/类型标签与数值之间大空隙（原版空格排版 + 中文更短）  
- 主菜单右列偶发裁切  
- 血条名 / HP 377 / 野宠强锁  
- 关 mGBA 后把 `_translated_new.gba` 改回正式名

## 6. 明确不做（本票）

- 不改绘制 / `PrintNextChar` / F7 协议  
- 不改 lexicon 缩词凑显示  
- 不修血条名 tm2  
- 不关战斗模块冒充缩小范围  

## 7. Bot 扩展（已落地）

- 场景 `battle_menu_audit.lua` + `scene_saves.json`  
- `hunt{ rng_addr, rng_value }`：每格前钉 RNG（`bot.lua` / `_lib.lua`）  
- `bot/analyze_battle_menu_frames.py`：面板 ROI 指标 + `frame_descriptions.*`（须配合看图）  

