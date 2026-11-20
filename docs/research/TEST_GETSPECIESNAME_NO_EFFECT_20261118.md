# 实测记录：GetSpeciesName 补丁上限对血条名无效（2026-11-18）

## 假设（来自 `SPECIES_NICK_AND_BAG_ALGO.md` §1.4）

> 物种名截断（「溶+」「长チ」）是因为 `GetSpeciesName @0x0803B11C` 的拷贝上限
> 仍是 10 字节，没被流水线放大到 stride-1 = 23。

## 验证方法（最小改动 + 单判据）

反汇编确认上限位置与形态：

```
0803b154: 290a    cmp r1, #10      ← 真正的拷贝上限
0803b156: ddee    ble.n 0x803b136 ← 分支是 ble
```

对比 origin / translated ROM：

| ROM | 0x0803B154 | 含义 |
|---|---|---|
| origin | `290a` | cmp r1,#10 |
| translated | `290a` | **未改** ⇒ 流水线确实漏打 |

漏打原因（读 `src/meowth/write_plan.py::_copy_limit_patches`）：
1. 只匹配 `h2 & 0xFF00 == 0xD900`（**bls**），而此处是 `ble`（`0xDDEB` 系）
2. 值域检查 `lo = max(old_stride-1, 5)`，实际 b0=10 落在范围外

## 实验：手动打补丁

```python
d[0x03B154] = 0x17   # cmp r1,#23
```

写出 `work/_probe_species.gba`，跑 `battle_species_name` 场景
（run `20261118T151506_699753`，122 帧对）。

## 结果：**无效**

| 项 | 结果 |
|---|---|
| 敌方血条名 | 仍显示「长チ♀」残字，与打补丁前一致 |
| 敌方名区墨量（多帧） | origin 385 / translated 385，**完全相同** |
| 对话文本 | 仍是空框（属 BUG-1 战斗对话框问题，与本补丁无关） |

## 结论

**`GetSpeciesName` 不是血条名的数据源。** 修它的上限对血条无效。

这与 `SPECIES_NICK_AND_BAG_ALGO.md` §1.4 表格的结论一致：

| 路径 | 数据源 | 容量 | 中文结果 |
|---|---|---|---|
| 战斗血条 / 遇敌句 / 多数「当前宝可梦名」 | **昵称槽 6B** | 6B | **必截断** |
| 图鉴 `CreateMonName` | 名表 StringCopy（上限已放到 23） | 栈 ≥32B | 正常 |

## 对后续的意义

1. **不要再走「修 GetSpeciesName 上限 → 修血条」这条路**（本轮已证伪）。
2. 血条名要修，只能改**展示层数据源**：`species → 名表 stride24 → StringCopy 到大缓冲`。
   即文档 §1.5 的算法结论第 2 条。
3. 该改动属于「改游戏逻辑」，按 `HOOK_DEBUG_WORKFLOW.md` 四步走，
   且必须先解决 BUG-1 战斗对话框空白（否则血条名即使修好也看不见整句）。

## 遗留：流水线漏打本身仍是 bug

即使对血条无效，`GetSpeciesName` 上限没放大仍是**真实缺陷**
（任何直读名表的调用点都会截断）。但：
- 修它需要改 `_copy_limit_patches` 支持 `ble`
- 影响面涉及 3 个调用点（`0x08037D06` / `0x0803FC68` / `0x0811CA60`）
- **当前没有可观测的受害者**（血条走昵称槽，图鉴走 CreateMonName）

⇒ 优先级降为「低」，等有实际症状再修。**不要**为了「补全正确性」去改流水线。
