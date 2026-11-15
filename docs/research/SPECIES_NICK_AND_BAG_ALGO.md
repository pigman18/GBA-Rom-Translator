# 物种名错字 + 背包空白行：算法层结论

日期：2026-11-15  
范围：**先定算法，再改代码**；禁止点状叠补丁。  
ROM：`roms/outputs/POKEMON_RUBY_AXVJ00_translated_new.gba`  
约束：日版底；F7 协议只加不改；昵称存档字段不得扩宽。

---

## 0. 用户现象（本轮截图）

| 场景 | 现象 | 不是什么 |
|------|------|----------|
| 野生溶食兽 | 对话「溶+」、血条名乱码 | 不是 12px 画错 / 不是 Linear 门控 |
| 逃走句 | 前缀残留「ち」+ 中文 | 展开缓冲错位，同源 |
| 背包道具 | 有数量「1」的空白行 | 不是 Linear；TB≈1 仍走网格 |

---

## 1. 物种名：两套「名字」被揉成一套

### 1.1 数据层（已正确）

| 项 | 值 |
|----|-----|
| 中文名表 | `0x09EB0AF4`，stride **24** |
| 溶食兽 #316 | `F7 00 0F 73 F7 00 0E AE F7 00 09 40 FF…`（溶食兽，完整） |
| 读表 ×24 | 图鉴 `CreateMonName@0x0808AD74` 等；移位 `lsls #3` + `cmp #0x17` 已打 |

表本身无错。§9.4.6 已证：VRAM 里搜不到正确字形 ⇒ **打印前缓冲已坏**。

### 1.2 宝可梦结构里的昵称槽（硬上限 6B）

`GetBoxMonData` / `SetBoxMonData` 整串昵称分支：

```text
Get @0x0803A1FE:  movs r4,#0
                  从解密结构 +0x14 逐字节拷到 dst
                  cmp r4,#6 / bls     ← 最多 6 字节
                  再强制 dst[6]=FF

Set @0x0803A8C0:  同样 cmp r2,#6      ← 写入也最多 6 字节
```

这是 **存档/结构布局**，不是渲染。F7 一字 4B ⇒ 6B 只能装下「1 个整字 + 半截 F7」。

### 1.3 截断如何变成「溶+」

```text
表内:  F7 00 0F 73 | F7 00 0E AE | F7 00 09 40 | FF
写入昵称槽（6B）: F7 00 0F 73 F7 00
打印:  第一字「溶」OK；第二字只有 F7 + 00 → 码位残缺 → 屏上「+」类垃圾
若再被强制 FF 或与邻接字节拼接 → 孤立 F9 / 假名「ち」前缀（§9.4.6 / 逃走句）
```

### 1.4 谁读表、谁读昵称

| 路径 | 数据源 | 容量 | 中文结果 |
|------|--------|------|----------|
| 图鉴 `CreateMonName` | 名表 StringCopy，上限已放至 23 | 栈 ≥32B | 正常 |
| 部分 UI `StringCopy`←名表 | 名表 | 视 dst | 视缓冲 |
| 战斗血条 / 遇敌句 / 多数「当前宝可梦名」 | **昵称槽 6B**（`MON_DATA` 0x3A.. 或整串 Get） | 6B | **必截断** |
| `StringExpandPlaceholders` | 只展开已写入的 StringVar | 256B | 上游坏则整句坏 |

符号表 `GetSpeciesName@0x0803B48C` **标错**（UNVERIFIED）。

**真 `GetSpeciesName` = `0x0803B11C`**（`ldr=0x09EB0AF4`，`species×24` 已打，`cmp r1,#0x0A` + **`ble`** 循环）：

| 项 | 现状 | 应有 |
|----|------|------|
| 拷贝上限 | `#0x0A`（最多约 11B） | `#0x17`（stride24−1） |
| 流水线 | `_copy_limit_patches` 只认后接 **`bls`（D9）** | 本函数是 **`ble`（DD）** → **整站漏打** |
| 调用方 | CreateBoxMon `0x08037D06`（栈 32B→再 Set 昵称 6B）；战斗 `0x0811CA60`；另 `0x0803FC68`（栈仅 20B） | 展示走大缓冲；昵称写入仍受 6B Set 限制 |

`CreateBoxMon`：`GetSpeciesName(sp)` → `SetBoxMonData(NICKNAME=2, sp)` → **再截成 6B 进结构**。  
故即使修好 GetSpeciesName 上限，**血条若仍读昵称槽** 依旧是「溶+」；遇敌句若走 `0x0811CA60` 直读名表，修好上限即可。

### 1.5 算法结论（物种名）

```text
名表(24B,F7中文) ──StringCopy──► 大缓冲 UI（图鉴等）     ✅
       │
       └──Create/SetMon──► 昵称槽(6B) ──Get──► 战斗/血条/遇敌  ❌
```

**根因**：把「展示用中文种名」和「结构体内定长昵称」当成同一条管道。  
**禁止**：扩昵称槽、改 F7、改短译文凑 6B、在 `PrintNextChar` 里特判「溶」。  
**正解（按层）**：

1. **存储层**：昵称槽继续 6B（存档兼容）。默认种名写入时不应再指望它装下中文 F7 串（应保留可比较的默认形态，或接受槽内非展示数据）。
2. **展示层**：凡「默认种名」显示（血条、遇敌、逃走相关 StringVar、未改名时的种名）必须 `species → 名表 stride24 → StringCopy 到大缓冲`，**禁止**把 6B 昵称当中文种名源。
3. **改名检测**：`NicknameDiffersFromSpeciesName` 须与「默认=读名表」同一套比较基准（日文默认名或「截断中文」都要能识别为默认），否则会把默认当成自定义昵称。

---

## 2. 背包空白行：列表绘制算法，不是漏 Blank

### 2.1 日版列表算法（origin 已如此）

```text
每行: Menu_BlankWindowRect(15..30, y)
    → ItemId_GetName → Menu_PrintText(name, left=15, y)
    → 另一次 Print 数量 @ left≈26（× + 数字）
```

道具名与数量是 **两次 Print**；行前 Blank 已有。空白行 **不是**「忘了清」。

### 2.2 中文网格下的分配公式

```text
tile = TILE_BASE + 2 + (band)*62 + 2*col
背包列表: TILE_BASE≈1，textMode=1，模板 0x081BB544
```

历史问题（`BAG_LIST_TILE_COLLISION.md`）：8px「×」规避迁 tile → 被后续行 12px 本征公式踩爆。

### 2.3 当前引擎对背包的策略（`PrintNextChar_hook.c`）

```c
grid_use_linear: tm0 && TB >= 0x180   // 背包 TB=1 → 不走 Linear ✅

bag 专属 grid_emit:
  - Y≥18 或 12px 伸到 col≥26 → 只推进、不写
  - 12px 本征 tile 已被占 → 只推进、不写（禁止 find_free）
```

「只推进不写」= **名字墨迹被跳过，游标仍前进**。  
数量是第二次 Print（8px，col≈26），仍可能打出「1」→ 截图里的 **空白行 + 孤零零的 1**。

### 2.4 Linear 门控

| 窗 | TB | Linear? |
|----|-----|---------|
| 战斗菜单/招式 | ≥0x180 | 是（本轮战斗 UI 修复） |
| 背包列表 | ≈1 | **否** |
| 对话底框 | 低 TB | 否 |

**背包空白与 Linear 无关**；勿为背包去关战斗 Linear。

### 2.5 算法结论（背包）

```text
根因: 网格按「屏上行列 → 全局本征 tile」映射，列表多行共享公式空间；
      冲突时对背包选择「跳过绘制」而非「安全改分配」。
后果: 名空白、数量残留；滚动/多行时复现「又出现空白行」。
```

**禁止**：全局 `clear_cols`；改译文缩短；用 Linear 硬套背包。  
**正解（按层）**：

1. **冲突策略（本轮）**：禁止「只推进不画」稳态；行前 Blank 已改 tilemap 时，12px **写本征覆盖** VRAM 残墨。
2. **分配层（仍可加强）**：列表窗按行隔离 tile（行私有 band / 行内线性槽），从根上消掉 8px 规避与 12px 本征互踩。
3. **场景层**：TM No. 图块与名起点重叠另案（P38 等）。

---

## 3. 与「修 BUG」心态的对照

| 修 BUG 心态 | 算法心态 |
|-------------|----------|
| 血条再 P03 缩一点遮罩 | 先定「名从哪来」：表 vs 昵称槽 |
| 背包再 skip 一列 | 先定「tile 如何按行分配」 |
| 关 Linear 看背包好不好 | 门控已证明无关 |
| 把「溶食兽」改成两字 | 禁改译文凑布局 |

---

## 4. 改动顺序（本轮已落地 / 仍待）

### 已落地（算法层，非点状）

1. **`write_plan._copy_limit_patches`**：拷贝环后接条件兼认 **`bls` + `ble`** → 真 GetSpeciesName `cmp #0x0A` 可升到 `#0x17`。
2. **`write_plan._bl_caller_stack_patches`**：BL GetSpeciesName 且 dest=sp 的调用方，`sub/add sp` 升到 ≥32（战斗原 12、另一站 20）。
3. **背包 `grid_emit`**：去掉「12px 本征被占 → 只推进不写」；Blank 后写本征覆盖残墨（仍禁止 bag find_free）。

### 本轮落地（bot 实证后）

4. **种名晋升（未并入产品）**：全局钩 `GetMonData`/`GetBoxMonData` 昵称读会软复位（嵌套或冲小 scratch）。下一步只挂战斗大缓冲站点（`StringVar` / expand 后）。
5. **已在场句**：种子曾 `\CC09已经在战斗中出场\n了!\CC09`（丢 `\02`）。改为 `\02已经在\n战斗中出场了！\CC09`。bot：空白消失，中文两行可见。
6. **背包行私有 tile**：`BAG_LIST_TEMPLATE` 按 `ty>>1`×30，基址 `TB+0xC0`，禁 `find_free`。神奇糖果行已恢复；底行与说明框互踩仍待把说明窗也迁出共享低 band。

回归 bot：`battle_species_name` / `battle_already_out` / `bag_blank_rows`。

---

## 5. bot 证据（2026-11-15）

| 场景 | run | 结论 |
|------|-----|------|
| 种名 | `…/battle_species_name/20261115T231855_877927` | 遇敌「雷↑」+ 血条乱码；名表 OK、`GetSpeciesName` cmp#0x17 已打仍不够 → 昵称槽 |
| 已在场 | `…/battle_already_out/20261115T232149_337312` | T 空白 vs O 日文；RAM `gStringVar1` 有中文但译文丢 `\02`、硬换行「了!」 |
| 背包 | `…/bag_blank_rows/20261115T231948_618630` | 帧 140：O「神奇糖果×4」/ T「关闭背包×4」→ tile 互踩非 ItemId |

---

## 6. 证据索引

| 证据 | 位置 |
|------|------|
| 名表完整 | `0x09EB0AF4 + 316*24` |
| Get 昵称 7B | `0x0803A1FE` `cmp r4,#6` / bls |
| Set 昵称 7B | `0x0803A8D0` `cmp r2,#6` |
| P40 晋升 | `hook/src/pokemon/PromoteDefaultNick_*` |
| 图鉴读表 OK | `0x0808AD74` `cmp #0x17` |
| 背包公式/GDB | `docs/research/BAG_LIST_TILE_COLLISION.md` |
| bag 行隔离 | `PrintNextChar_hook.c` `grid_tile` bag 分支 |
| Linear 门控 | `grid_use_linear` TB≥0x180 |
