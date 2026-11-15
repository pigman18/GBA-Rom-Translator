# 遇敌台词 / 战斗菜单全空：调研

日期：2026-11-15  
产物 ROM：`POKEMON_RUBY_AXVJ00_translated.gba`  
SHA256：`9756FA1CB0D0A2BC13AB4BC5BC6652F66949347FC66855C1E33C2983BF14E769`  
bot：`work/POKEMON_RUBY_AXVJ00/bot/battle_full/20261115T214419_405931/`（`BOT_DUMP_ALLWINS=1`）

## 1. 现象

| 区域 | translated | origin |
|------|------------|--------|
| 遇敌/战斗底框 | 正文空，或铺满白色 ▼（预载/未改写 tile） | 日文正常（如「ゆけっ！バシャーモ！」） |
| 主菜单 / 招式 | 框在、光标在、选项全空 | たたかう等 PCS 正常 |
| 血条名 | 乱码/残墨（另案） | 正常 |
| HP / 精灵 | 正常 | 正常 |

▼ 与光标说明控制码（FA/FB）在跑；缺的是**可印字形落 VRAM/tilemap**。

## 2. 证伪：「某个 textMode 没实现」

| textMode | 战斗用途 | 现行 `PrintNextChar_hook` |
|----------|----------|---------------------------|
| **0** | 主菜单/对话窗（本轮主证） | 非 buffered 网格；**已接管** |
| 2 | 血条名缓冲 `win+0x20` | buffered 直绘；**已实现** |
| 3 | 其它菜单窗 | 网格 |

`bt_menu` 主窗（BG0，`tpl@0x081BB3F4`）：

```
translated: textMode=0 fontNum=3 TILE_BASE=0x02C0 TILE_OFF=0
            curX=25 curY=57 curTX=3 index=17
            text@0x0202362C 含 F7 00 …（串非空）
origin:     textMode=0 TILE_BASE=0x02C0 TILE_OFF=0x0008（官方累加）
            text@0x0202362C = FC… + たたかう PCS + FF
```

**遇敌/技能空 ≠ tm2 未写。** tm2 只对应血条名 NOTE。

## 3. Origin 打印路径（遇敌句 / 主菜单）

```
BufferStringBattle / 菜单字面量
  → Text_InitWindowWithTemplate
  → RunTextPrinter → PrintNextChar@0x080032F8（P01 全面接管）
```

主菜单字面量点：`docs/POKEMON_RUBY_AXVJ00.md` §7.2 E（`0x0802D7C8`）。  
台账：`TASKS.md` §3.1 — 战斗帧 tm0 / tm2 / tm3 均曾实测绘制。

## 4. 根因（已证实）

[`text_grid.h`](../../configs/POKEMON_RUBY_AXVJ00/hook/include/text_grid.h) / `grid_emit`：

```c
/* 绝对上限：禁止写 tile >= 0x1F0 */
if ((unsigned)t0 + 2u*(ncols-1u) + 2u > GRID_TILE_LIMIT)  /* 0x1F0 */
    return;  /* 只推进游标，不写 VRAM/tilemap */
```

公式：`t0 = TILE_BASE + 2 + band*62 + 2*col`。

战斗主窗 **`TILE_BASE=0x02C0` 已大于 `0x1F0`** → 任意列的 `t0` 都超限 → **整窗静默不画**。

| 计算 | 值 |
|------|-----|
| TB | `0x02C0` |
| band（curY=57 → row=28） | 4 |
| col≈25 时 t0 | `0x03EC` |
| `t0 > 0x1F0` | 恒真 → skip |

官方 tm0 用 **`TB + TILE_OFFSET` 线性累加**（origin `TILE_OFF` 递增）；汉化网格忽略 `TILE_OFF`，且用**绝对** `0x1F0` 当「本窗 arena 尾」——只对 TB≈0/1 的对话窗成立。

屏上 ▼ 铺满：字形 skip 后 tilemap 仍指战斗框预载三角/填充；用户「全空」= 清窗后同样 skip。

### 假说表

| ID | 假说 | 结论 |
|----|------|------|
| H1 | `GRID_TILE_LIMIT` 绝对比较 + 高 TB 战斗窗 → 静默不画 | **证实** |
| H2 | `blank_rest` 误伤战斗底框 | **否**：主菜单 `curX=25≥20` 不进守卫；非主因 |
| H3 | textMode 2 未实现 | **否**（见 §2） |
| H4 | `gDisplayedStringBattle` 打印前为空 | 菜单帧两侧均已清；主窗 `0x0202362C` **有** F7/PCS，非空串 |
| H5 | 血条名乱码 | **另案** tm2 / nick CpuSet；不与整窗空捆修 |

## 5. 明确不做

- 不改 lexicon / 译文凑显示  
- 不改 F7 协议  
- 不关战斗/script 整域冒充修复  
- 本调研不扩改血条名路径  

## 6. 已实施最小修复（2026-11-15）

1. **`grid_arena_hi(tb) = tb + GRID_TILE_LIMIT`**：emit / find_free / load 用相对上界（见 `PrintNextChar_hook.c` / `text_grid.h`）。  
2. **`blank_rest`：`TILE_BASE >= 0x80` 则跳过** — 战斗 TB 下 `TB+1` 是 ▼ 预载，Blank 会铺三角；存档底框 TB 小不受影响。

### 复验

| run | 帧 | 结果 |
|-----|-----|------|
| `…214932…`（仅相对 arena） | `031` | 有「去吧！バシャーモ！」+ 尾部 ▼ 铺满 |
| `…215305…`（+ blank_rest TB≥0x80 跳过） | `031` | **「去吧!バシャーモ!」干净，无 ▼ 尾** |
| 同上 | `052` | 招式「抓」「啄」可见；下两格仍空（另跟） |
| `save/…215326…/020` | confirm | L1 tile21–25 非白仍为 0（碎点未回退） |
| 血条名 | — | 仍 NOTE |

## 7. 验收（用户）

- 遇敌底框可见中文、非整窗空/整窗 ▼  
- 战斗主菜单 / 招式名可见  
- 存档 confirm L1 碎点不回退  
- 血条名乱码可另开票  
