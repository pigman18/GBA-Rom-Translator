# 通用写入算法（texts.json + texts_translated.json + python → build.json）

> 2026-11-04
> 用户指示：**不要只纠结单个文本或单个块，这是一个通用算法。**
> 抽象成四步：**读取一段文本 → 判断归属 → 放入新区 → 标记待修改指针**。
>
> 小规模变量修改、值重定向，一律写进 `hook/patches/*.asm`
> （参考 `patches/pokedex.asm` 的 `equ` 常量 + `.org` 覆盖做法）。

---

## 零、总体流水线

```
texts.json                 模块定义（区域、结构候选、过滤）
      │
texts_translated.json      译文（id → 中文）
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  meowth.pipeline                                         │
│                                                          │
│  ① READ       读取一段文本（从 ROM 按模块结构读出）        │
│  ② CLASSIFY   判断归属（属于哪种容器）                    │
│  ③ PLACE      放入新区（分配空间 + 生成字节 + 记录标记）   │
│  ④ RELINK     标记待修改指针（产出 patch 清单）           │
│                                                          │
└─────────────────────────────────────────────────────────┘
      │
      ▼
translated.build.json       每条译文 → 归属 / 新区地址 / 待改指针
      │
      ▼
rom_writer + armips patches 应用
```

**核心抽象**：一条文本无论属于哪种容器，都走同一条四步流水线，
只是 ② 的判定结果决定 ③ 的布局方式和 ④ 的改法。

---

## 一、① READ：读取一段文本

输入：模块 + 条目地址。

```python
@dataclass
class RawText:
    entry_id: str
    module: str
    offset: int          # 文件偏移
    raw: bytes           # 原始字节（含 eos）
    text: str            # 解码后的日文
```

**不需要判断归属**，只是把 ROM 里的这段字节读出来。

---

## 二、② CLASSIFY：判断归属

输出容器类型 + 容器参数。

```python
@dataclass
class Ownership:
    container: Container      # FIXED_TABLE / PTR_ARRAY / CODE_LITERAL /
                              # SCRIPT_INLINE / FREE_TEXT / NO_PTR
    params: dict              # 容器特有参数
    # FIXED_TABLE: {table, base, stride, usable, index}
    # PTR_ARRAY:   {array_base, slot_index, n_slots}
    # CODE_LITERAL:{site, ldr}
    # SCRIPT_INLINE:{sites}
    # FREE_TEXT:   {sites}
```

**判定优先级**（实测确定）：
```
1. 落在已知表区间   → FIXED_TABLE
2. 4 对齐指针 + 相邻也是指针 → PTR_ARRAY
3. 4 对齐指针 + 被 ldr 引用  → CODE_LITERAL
4. 非对齐引用 + 前缀 0f 00   → SCRIPT_INLINE
5. 4 对齐指针（其他）        → FREE_TEXT
6. 全无引用                  → NO_PTR
```

---

## 三、③ PLACE：放入新区

**关键：按容器决定布局，但统一走一个分配器。**

```python
@dataclass
class Placed:
    entry_id: str
    new_offset: int           # 新区文件偏移
    bytes_: bytes             # 要写入的字节
    mode: PlaceMode           # ORIGINAL_STRUCT / VARIABLE / RELOCATED
```

### 三种布局模式

| 模式 | 适用 | 说明 |
|---|---|---|
| **ORIGINAL_STRUCT** | FIXED_TABLE 且 stride 够用 | 整项复制原结构，只替换名字区 |
| **VARIABLE** | FIXED_TABLE 但 stride 不够 | 新表按新 stride 重排（stride 放大） |
| **RELOCATED** | 其余容器 | 文本单独放，靠指针指过来 |

### 统一分配器

**空间不是约束**（32MB ROM 只用 30.65MB，7 张表全换新仅 70KB）。
所以分配器只需保证不重叠，不需要抠空间。

```python
class RegionAllocator:
    """线性分配，4 字节对齐，记录已用区间。"""
    def alloc(nbytes, label, align=4) -> int
```

---

## 四、④ RELINK：标记待修改指针

**只产出 patch 清单，不直接改 ROM。**

```python
@dataclass
class RelinkPatch:
    kind: PatchKind       # LITERAL / INSTRUCTION / SCRIPT_SLOT / NONE
    offset: int           # 文件偏移
    data: bytes           # 新字节
    reason: str
```

### 三种改法

| kind | 适用 | 举例 |
|---|---|---|
| **LITERAL** | 改 u32 字面量 | 表基址指到新区 |
| **INSTRUCTION** | 改指令（立即数） | `lsls #3` → `lsls #5` |
| **SCRIPT_SLOT** | 改脚本体里的指针槽 | `0f 00 <ptr32>` 的 ptr |

算出的步长、基址、常规改指针、无指针重定向，一律写进打包生成的 **`hook/gen/patch_table.asm` 这一份**。
常规文本**不**再原地写回原槽。`hook/patches/` 只留有具体界面用途的旧补丁（PC 加宽、图鉴列距、默认名、单位），不往里再手写步长或指针。

---

## 五、6 张表的方案（通用算法下的判定结果）

| 表 | 项数 | 旧 stride | 可用 | 最长译文 | 新模式 | 新 stride | 指令改动 |
|---|---|---|---|---|---|---|---|
| 招式名 | 354 | 8 | 8 | 21B | VARIABLE | **32** | `lsls #3`→`#5` |
| 特性名 | 77 | 8 | 8 | 17B | VARIABLE | **32** | `lsls #3`→`#5` |
| 属性名 | 18 | 5 | 5 | 13B | VARIABLE | **20** | 乘法展开改写 |
| 道具名 | 348 | 40 | 9 | 29B | VARIABLE | **80** | 乘法展开改写 |
| 图鉴分类名 | 386 | 28 | 6 | 17B | VARIABLE | **56** | `×28`→`×56` 改写 |
| 秘密基地装饰名 | 120 | 28 | 10 | 29B | VARIABLE | **56** | `×28`→`×56` + `adds #0x14` |

**全部走 VARIABLE**（stride 放大），因为：
- 空间不是约束（70KB vs 1.35MB 余量）
- 放大 stride 只改一个立即数，比 VARLEN（重写乘法逻辑）安全
- 保持 `index×stride` 的访问形态不变，只改变 stride 值

### 指令改动写进 patches

参考 `patches/pokedex.asm` 的做法（`equ` 常量 + `.org` 覆盖）：

```asm
; patches/table_stride.asm
; 定长表 stride 放大：改乘法的移位立即数
; 常量唯一来源：game_addrs.asm

.org 0x0802B538
    lsls r1, r1, #5          ; 招式名 ×8 → ×32

.org 0x0809C6C2
    lsls r0, r4, #5          ; 特性名 ×8 → ×32

; ... 其余表
```

---

## 六、模块划分

```
src/meowth/
  pipeline.py         四步流水线编排（READ → CLASSIFY → PLACE → RELINK）
    ├─ read_text(...)
    ├─ classify(...)        调 auto_layout
    ├─ place(...)           调 table_expand / 新区分派
    └─ relink(...)          产出 patch 清单

  auto_layout.py      ② 的判定器（已实现）
  table_expand.py     ③ 的布局器（已实现，需补 VARIABLE 模式）
  table_relink.py     ④ 的 patch 生成（已实现，需补 INSTRUCTION 类）
  region_alloc.py     ③ 的统一分配器
```

**最终产出 `translated.build.json`**：
```json
{
  "entries": [
    {
      "id": "...",
      "module": "招式名",
      "ownership": {"container": "FIXED_TABLE", "table": "招式名", "index": 5},
      "placed": {"new_offset": "0x09F00000", "mode": "VARIABLE"},
      "relink": [{"kind": "LITERAL", "offset": "0x02B580", "data": "..."}]
    }
  ],
  "tables": [{"name": "招式名", "new_base": "...", "new_stride": 32, "asm_patch": "..."}]
}
```

---

## 七、与原方案的差异

| 项 | 原方案（逐表定制） | 新方案（通用算法） |
|---|---|---|
| 代码结构 | 每个表一个脚本 | 一条流水线 + 可配置判定 |
| 归属判定 | 人工逐个查 | auto_layout 自动 |
| 空间 | 抠 1MB | 不设限（32MB 够用） |
| 指令改动 | 混在 Python 里 | 统一进 `patches/*.asm` |
| 产出 | 分散的 patch json | 统一 build.json |

---

## 八、当前主线（2026-11-05 统一）

有译文就走下面三类之一。**不做原地写回原槽。**  
理论上不该再因「放不下 / 没指针」落成 keep（模块整表禁止改写、无译文、校验拒绝除外）。

编排：`texts.json` + 译文 + 原盘 → **`write.plan.json`**（`meowth.write_plan`）。  
落盘：`meowth.rows_writer` **只按计划写**（表 → `gen/patch_table.asm` + armips；常规 pointer/redirect → 直接改 ROM）。

| # | 条件 | 做法 | 写到哪里 |
|---|---|---|---|
| 1 | 等长 / 等距表（含结构体表） | 整表进新区；新步长按**该表最长一条译文**算；改基址指针 + 改步长指令（结构体另算字段偏移） | **`gen/patch_table.asm`** |
| 2 | 常规文本，有可用指针 | 正文进新区，改全部引用指针（不论原槽够不够） | **`rows_writer.apply_rows`** |
| 3 | 常规文本，无可用指针 | **重定向**（字面量站点）；定不出站点 → `skip: unresolved_redirect` | **`rows_writer.apply_rows`** |

`main.asm` 只 include 这一份算出的 `gen/patch_table.asm`。`hook/patches/` 仍只留有具体界面用途的旧补丁，不再手写步长 / 常规改指针 / 常规重定向。

### 与现状的差距（必须按上表改）

| 项 | 现在错在哪 | 应按上表 |
|---|---|---|
| 原地写入 | 仍有 `replace` 写原槽 | **取消**；常规一律 #2 或 #3 |
| 等距表 | 四张纯步长进了补丁表；结构体整表 skip；属性名等因单移位算不出新 K 就整张不写 | **#1 整表必写**；算不出移位就换乘法/展开，不得 keep 成日文 |
| 常规无指针 | 曾用未过滤全 ROM 搜址当 redirect → 假指针改崩读档 | 暂记 `skip: unresolved_redirect`；bl_stub 另补 |
| 结构体放大 | 道具名 40→80 缺字段立即数 → 输入停摆 | 步长变大的 struct 暂不写入，待 field 立即数 |
| 物种名读点 | 部分站点（如 GetSpeciesName）未进移位集合 | 图鉴列表名可能仍空，需补站点发现 |

`F9` 一组 4 字节，中间可夹单字节假名，不能切断一组。图鉴检索等 `write` 全关的模块仍整表不改。验收：`dex`、`pokemon_menu`、`start_menu`、`bag`。
