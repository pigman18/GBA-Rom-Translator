# 自动划分架构（texts.json 只存模块与文本）

> 2026-11-04
> 用户目标：**texts.json 未来只存放「模块 + 待翻译文本」，
> 组装由 Python 侧读 texts_translated.json 自动完成。**
>
> 现状问题：`write.relocate / write.replace / write.slot / write.byte_length`
> 这些是「人工指定写入策略」的妥协产物，必须退场。

---

## 一、职责重新划分

### 旧架构（人工指定策略）

```
texts.json
  ├─ modules.<id>.read     几何（stride/entry_size/name_offset）
  ├─ modules.<id>.write    ★ 人工指定走 relocate / replace / slot
  └─ modules.<id>.filters  抽取过滤

translate_plan.py
  └─ 按 write.* 决策 → 产出 type: relocate/replace/slot/keep
```

问题：
- `write.relocate=false` 是人拍脑袋设的，不代表 ROM 真的没指针
- `write.byte_length` 与真实 ROM 几何脱节（道具名就是这样）

### 新架构（Python 自动判定）

```
texts.json                    ← 只存模块与文本
  └─ modules.<id>
        ├─ label / group / description
        ├─ read    几何（仍需人工提供候选，但会被 ROM 校验）
        └─ filters 抽取过滤
      （write.* 全部删除）

texts_translated.json         ← 译文
  └─ 条目 id → 译文

src/meowth/auto_layout.py     ← 新增：自动归属判定 + 划分
  1. 对每条译文，判定它属于哪个容器（FIXED_TABLE / PTR_ARRAY /
     CODE_LITERAL / SCRIPT_INLINE / FREE_TEXT / NO_PTR）
  2. 按容器分组
  3. 每组选一种写入方式
  4. 产出 build.json（含具体 patch 计划）
```

---

## 二、自动归属判定器的判据（已实测验证）

输入：条目地址 `A`、ROM 字节。

按优先级判定：

```
1. FIXED_TABLE
   条件：A 落在某张已知定长表的 [base, base + stride*n) 区间内
   证据：模块 read 几何 + ROM 字节校验（stride、name_offset 与实际吻合）
   输出：表名、base、stride、元素索引 i

2. PTR_ARRAY
   条件：指向 A 的 4 对齐指针站点 S，且 S-4 或 S+4 也是指向文本区的指针
   证据：成组指针（相邻 4 字节）
   输出：数组基址（向前后扩展到不成组）、组内序号

3. CODE_LITERAL
   条件：指向 A 的 4 对齐指针站点 S，且 S 被 ldr [pc,#n] 引用
   证据：Thumb `ldr` 模式匹配 + pc 相对计算
   输出：字面量偏移、ldr 指令偏移

4. SCRIPT_INLINE
   条件：A 被非 4 对齐位置引用，且引用前的 2 字节是 `0f 00`
   证据：实测 2,780 条走这个形态
   输出：引用位置

5. FREE_TEXT
   条件：有 4 对齐指针，但不属于以上
   输出：指针站点列表

6. NO_PTR
   条件：任意对齐都找不到引用
   输出：无（只能原地写/缩句/keep）
```

**判定器必须可复现**：输入相同 ROM + build.json → 相同输出。

---

## 三、按容器自动选写入方式

| 容器 | 写入方式 | 需要改代码？ |
|---|---|---|
| FIXED_TABLE | 整表搬新区，保持 stride | 只改字面量 |
| FIXED_TABLE（塞不下） | 整表换变长 + 指针数组 | **改 index×stride** |
| PTR_ARRAY | 整数组搬走，改数组值 | 不改 |
| CODE_LITERAL | 逐条改字面量 | 不改 |
| SCRIPT_INLINE | 逐条改内嵌指针 | 不改 |
| FREE_TEXT | relocate | 不改 |
| NO_PTR | 原地写 / 缩句 / keep | 不改 |

**关键判据：stride 塞不塞得下**（用户原则：能保持 stride 就不换结构）

```python
def choose_mode(container: str, stride: int, name_offset: int,
                bodies: list[bytes]) -> str:
    """返回 'fixed' | 'varlen' | 'relocate' | 'inplace'"""
    if container == "FIXED_TABLE":
        cap = stride - name_offset
        if all(len(b) <= cap for b in bodies):
            return "fixed"          # 保持 stride，只改字面量
        return "varlen"             # 必须改机器码
    if container == "PTR_ARRAY":
        return "relocate"           # 改数组值即可
    ...
```

---

## 四、新增模块：`auto_layout.py`

```
src/meowth/auto_layout.py
  ├─ class Container          枚举：FIXED_TABLE / PTR_ARRAY / ...
  ├─ classify_entry(...)      单条归属判定
  ├─ group_by_container(...)  批量分组
  ├─ choose_mode(...)         按容器选写入方式
  └─ build_layout_plan(...)   产出完整计划
```

**输出结构**：
```python
@dataclass
class LayoutPlan:
    table_groups: list[TableGroup]      # 定长表 → 整表搬
    array_groups: list[ArrayGroup]      # 指针数组 → 整组搬
    singles: list[SinglePatch]          # 逐条改
    inplace: list[Entry]                # 原地写
    unpatchable: list[Entry]            # 无法处理（NO_PTR）
```

---

## 五、texts.json 的新形态

### 删除的字段

| 字段 | 理由 |
|---|---|
| `write.relocate` | 自动判定 |
| `write.replace` | 自动判定 |
| `write.slot` | 无 |
| `write.byte_length` | 与 ROM 脱节（道具名实测错误） |
| `write.op` / `write.style` | 早已废弃 |

### 保留的字段

| 字段 | 说明 |
|---|---|
| `label` / `group` / `description` | 界面显示 |
| `type` | **仅做提示**，实际以 ROM 校验为准 |
| `read` | 几何候选，须通过 ROM 字节校验 |
| `filters` | 抽取过滤（职责不变） |
| `word_count` / `wrap_pages` / `max_lines` | 文本排版 |
| `min_byte_length` | 抽取过滤 |

### 新增的字段

| 字段 | 说明 |
|---|---|
| `verify` | 期望的 ROM 校验结果（如 `{"stride": 8, "n": 354}`），构建时校验 |

---

## 六、迁移步骤

1. **先并行**：`auto_layout.py` 能跑出与现有 build.json 等价的计划
2. **再切换**：translate_plan 改用 auto_layout 的结果
3. **最后清理**：删掉 texts.json 里的 write.*

**不一次性删 write.\***：先用它做对照，验证 auto_layout 判定一致后再删。

---

## 七、与 ALGO_TABLE_EXPAND 的关系

```
auto_layout.py          判定归属、分组、选模式
      ↓ LayoutPlan
table_expand.py         阶段 1+2：扩表与新区排列
      ↓ ExpandedTable
table_relink.py         阶段 3：指针修改
      ↓ Patch 列表
rom_writer.py           应用 patch
```

四层职责清晰，每层可单独测试。
