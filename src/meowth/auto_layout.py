"""自动归属判定与划分（流水线模块）。

对应 docs/ALGO_AUTO_LAYOUT.md。

职责：
  1. 判定每条译文属于哪个「容器」——不依赖 texts.json 的 write.* 人工开关
  2. 按容器分组
  3. 每组选一种写入方式

设计原则（用户 2026-11-04 指示）：
  - texts.json 只存模块与文本，组装由 Python 自动完成
  - 等长/等距整块必然整块处理，不逐条处理
  - 能保持 stride 就不换结构（只改字面量，不动机器码）

典型用法::

    from meowth.auto_layout import build_layout_plan

    plan = build_layout_plan(rom, entries, tables=KNOWN_TABLES)
    for g in plan.table_groups:
        print(g.table_name, g.mode, len(g.entries))
"""
from __future__ import annotations

import struct
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum

GBA_BASE = 0x08000000


# ---------------------------------------------------------------------------
# 容器类型
# ---------------------------------------------------------------------------
class Container(str, Enum):
    """一条文本所属的「容器」。"""

    FIXED_TABLE = "FIXED_TABLE"      # 定长表元素（stride 表 / struct 数组）
    PTR_ARRAY = "PTR_ARRAY"          # 指针数组元素
    CODE_LITERAL = "CODE_LITERAL"    # 代码字面量池（ldr 加载）
    SCRIPT_INLINE = "SCRIPT_INLINE"  # 脚本内嵌（`0f 00 <ptr32>`）
    FREE_TEXT = "FREE_TEXT"          # 自由文本（有指针但不属于以上）
    NO_PTR = "NO_PTR"                # 无任何引用


# 写入模式
class WriteMode(str, Enum):
    FIXED = "fixed"                  # 保持 stride，只改字面量
    SWAP_STRIDE = "swap_stride"      # 放大 stride 到 2 的幂倍数（改移位立即数）
    SWAP_STRIDE_HARD = "swap_hard"   # 放大 stride 到非 2 幂倍数（改乘法展开）
    VARLEN = "varlen"                # 变长 + 指针数组，需重写乘法逻辑
    RELINK = "relink"                # 改指针值（数组/字面量/内嵌）
    INPLACE = "inplace"              # 原地写（塞得下）
    PRUNE = "prune"                  # 无法处理，保留原文


# 模式的中文说明（报告用）
MODE_DESC = {
    WriteMode.FIXED: "保持 stride，只改字面量",
    WriteMode.SWAP_STRIDE: "放大 stride（2的幂，改移位立即数）",
    WriteMode.SWAP_STRIDE_HARD: "放大 stride（非2幂，改乘法展开）",
    WriteMode.VARLEN: "变长+指针数组（重写乘法）",
    WriteMode.RELINK: "改指针值",
    WriteMode.INPLACE: "原地写",
    WriteMode.PRUNE: "保留原文",
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class Classified:
    """一条文本的归属判定结果。"""

    entry_id: str
    module: str
    addr: int                       # 文本文件偏移
    container: Container
    detail: dict = field(default_factory=dict)


@dataclass
class TableGroup:
    """一张定长表（整表搬）。"""

    table_name: str
    base: int
    stride: int
    name_offset: int
    n_items: int
    mode: WriteMode
    entries: list[Classified] = field(default_factory=list)
    fitted: int = 0                 # 塞得下的条数
    overflow: int = 0               # 超出的条数
    new_stride: int = 0             # SWAP_STRIDE 时的新 stride
    stride_mult: int = 1            # 放大倍数
    n_literals: int = 0             # 基址字面量站点数（relink 用）

    @property
    def cap(self) -> int:
        return self.stride - self.name_offset

    @property
    def detail(self) -> str:
        s = f"{self.mode.value}"
        if self.stride_mult > 1:
            s += f" stride {self.stride}→{self.new_stride}(×{self.stride_mult})"
        return s


@dataclass
class ArrayGroup:
    """一个指针数组（整组搬）。"""

    base: int                       # 数组起始文件偏移
    n_slots: int
    entries: list[Classified] = field(default_factory=list)


@dataclass
class LayoutPlan:
    """完整划分计划。"""

    table_groups: list[TableGroup] = field(default_factory=list)
    array_groups: list[ArrayGroup] = field(default_factory=list)
    code_literals: list[Classified] = field(default_factory=list)
    script_inline: list[Classified] = field(default_factory=list)
    free_text: list[Classified] = field(default_factory=list)
    no_ptr: list[Classified] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "tables": len(self.table_groups),
            "table_entries": sum(len(g.entries) for g in self.table_groups),
            "arrays": len(self.array_groups),
            "array_entries": sum(len(g.entries) for g in self.array_groups),
            "code_literals": len(self.code_literals),
            "script_inline": len(self.script_inline),
            "free_text": len(self.free_text),
            "no_ptr": len(self.no_ptr),
        }

    @property
    def total(self) -> int:
        return sum(self.summary()[k] for k in
                   ("table_entries", "array_entries", "code_literals",
                    "script_inline", "free_text", "no_ptr"))


# ---------------------------------------------------------------------------
# 判定工具
# ---------------------------------------------------------------------------
def build_ptr_index(rom: bytes) -> dict[int, list[int]]:
    """目标文件偏移 → [4 对齐指针站点]。"""
    idx: dict[int, list[int]] = defaultdict(list)
    for off in range(0, len(rom) - 4, 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < 0x0A000000:
            idx[v - GBA_BASE].append(off)
    return dict(idx)


def is_gba_ptr(rom: bytes, off: int) -> bool:
    if off < 0 or off + 4 > len(rom):
        return False
    v = struct.unpack_from("<I", rom, off)[0]
    return GBA_BASE <= v < 0x0A000000


def find_ldr_for(rom: bytes, lit: int, back: int = 4096) -> list[int]:
    """找引用字面量 `lit` 的 thumb `ldr rX,[pc,#imm]`。"""
    hits: list[int] = []
    lo = max(0, lit - back)
    for off in range(lo, lit, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0x4800:
            continue
        imm = (hw & 0xFF) * 4
        if ((off + 4) & ~3) + imm == lit:
            hits.append(off)
    return hits


def find_unaligned_refs(rom: bytes, target: int) -> list[int]:
    """找指向 target 的非 4 对齐 u32 位置（脚本体）。"""
    needle = struct.pack("<I", target + GBA_BASE)
    out: list[int] = []
    s = 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i & 3:
            out.append(i)
        s = i + 1
    return out


def table_of(addr: int, tables: dict) -> tuple[str, int, int, int] | None:
    """addr 落在哪张已知表内 → (name, base, stride, name_offset)。"""
    for name, geom in tables.items():
        base = geom["base"]
        stride = geom["stride"]
        n = geom["n"]
        noff = geom.get("name_offset", 0)
        if base <= addr < base + stride * n:
            return name, base, stride, noff
    return None


# ---------------------------------------------------------------------------
# 判定：单条
# ---------------------------------------------------------------------------
def classify_entry(
    rom: bytes,
    entry: dict,
    tables: dict,
    ptr_index: dict[int, list[int]],
    code_end: int = 0x100000,
) -> Classified:
    """判定一条文本属于哪个容器。"""
    eid = str(entry.get("id") or entry.get("address") or "?")
    module = str(entry.get("module") or "")
    try:
        addr = int(str(entry.get("address") or "0x0").replace("0x", ""), 16)
    except ValueError:
        return Classified(eid, module, 0, Container.NO_PTR, {"why": "地址非法"})
    if addr >= GBA_BASE:
        addr -= GBA_BASE

    # 1. 定长表（最强信号，先判）
    t = table_of(addr, tables)
    if t:
        name, base, stride, noff = t
        return Classified(eid, module, addr, Container.FIXED_TABLE, {
            "table": name, "base": base, "stride": stride,
            "name_offset": noff, "index": (addr - base) // stride,
        })

    sites = ptr_index.get(addr) or []

    # 2. 脚本内嵌（`0F 00 <ptr32>`）—— 必须排在对齐判定之前
    #
    # ⚠️ 2026-11-04 修复（实测 678 条被误判）：
    #    ruby 的脚本用 `0F 00` + u32 内嵌文本指针。该槽位**恰好 4 对齐**，
    #    旧逻辑先走「4 对齐指针」分支，于是这些脚本引用被当成 FREE_TEXT，
    #    改指针时逐条处理，没有按「脚本槽」语义成组处理。
    #    实测 0x0817004A：槽 0x16FFE0 前两字节正是 `0f 00`，
    #    是 `0f 00 4A 00 17 08`（= 0x0817004A）一条完整脚本指令。
    #
    #    判据：任一引用槽的前 2 字节是 `0F 00` → 脚本内嵌。
    script_sites = [
        s for s in sites
        if s >= 2 and rom[s - 2] == 0x0F and rom[s - 1] == 0x00
    ]
    if script_sites:
        return Classified(eid, module, addr, Container.SCRIPT_INLINE, {
            "sites": script_sites[:8],
            "n_sites": len(script_sites),
            "aligned": True,
        })

    # 3. 4 对齐指针
    if sites:
        s0 = sites[0]
        # 3a. 指针数组（相邻也是指针）
        prev_ptr = is_gba_ptr(rom, s0 - 4)
        next_ptr = is_gba_ptr(rom, s0 + 4)
        if prev_ptr or next_ptr:
            # 向前后扩展到不成组
            lo = s0
            while is_gba_ptr(rom, lo - 4):
                lo -= 4
            hi = s0
            while is_gba_ptr(rom, hi + 4):
                hi += 4
            return Classified(eid, module, addr, Container.PTR_ARRAY, {
                "site": s0, "array_base": lo,
                "n_slots": (hi - lo) // 4 + 1,
                "slot_index": (s0 - lo) // 4,
            })
        # 3b. 代码字面量
        ldrs = find_ldr_for(rom, s0)
        if ldrs and s0 < code_end:
            return Classified(eid, module, addr, Container.CODE_LITERAL, {
                "site": s0, "ldr": ldrs[0],
            })
        # 3c. 自由文本
        return Classified(eid, module, addr, Container.FREE_TEXT, {
            "sites": sites[:8], "n_sites": len(sites),
        })

    # 4. 非对齐引用 + `0f 00` 前缀（未对齐的脚本体）
    un = [p for p in find_unaligned_refs(rom, addr)
          if p >= 2 and rom[p - 2] == 0x0F and rom[p - 1] == 0x00]
    if un:
        return Classified(eid, module, addr, Container.SCRIPT_INLINE, {
            "sites": un[:8], "n_sites": len(un),
            "aligned": False,
        })

    # 5. 无指针
    return Classified(eid, module, addr, Container.NO_PTR, {})


# ---------------------------------------------------------------------------
# 写入模式选择
# ---------------------------------------------------------------------------
def choose_table_mode(
    cap: int, bodies: list[bytes], old_stride: int | None = None
) -> tuple[WriteMode, int, int]:
    """定长表：按「改动代价」从低到高选模式。

    返回 (mode, fitted, overflow)。

    优先级（用户原则：能少改就不多改）：
      1. 全部塞得下              → FIXED（只改字面量）
      2. 放大到 2 的幂倍数够用    → SWAP_STRIDE（改一个移位立即数）
      3. 放大到非 2 幂倍数够用    → SWAP_STRIDE_HARD（改乘法展开）
      4. ×8 仍不够               → VARLEN（重写为指针数组）
    """
    if not bodies:
        return WriteMode.FIXED, 0, 0

    fitted = sum(1 for b in bodies if len(b) <= cap)
    overflow = len(bodies) - fitted
    if overflow == 0:
        return WriteMode.FIXED, fitted, 0

    longest = max(len(b) for b in bodies)
    stride = old_stride if old_stride is not None else cap

    # 尝试放大 stride
    for k in (2, 4, 8):
        need = stride * k
        if longest <= need:
            is_pow2 = (need & (need - 1)) == 0
            mode = WriteMode.SWAP_STRIDE if is_pow2 else WriteMode.SWAP_STRIDE_HARD
            return mode, fitted, overflow

    return WriteMode.VARLEN, fitted, overflow


def suggest_stride(cap_needed: int, old_stride: int, max_k: int = 8) -> tuple[int, int] | None:
    """返回 (新stride, 倍数)，若放大到 max_k 倍仍不够则 None。

    只考虑 2/4/8 倍，因为 Thumb 乘法展开靠移位。
    """
    if cap_needed <= old_stride:
        return None
    for k in (2, 4, 8):
        if k > max_k:
            break
        if cap_needed <= old_stride * k:
            return old_stride * k, k
    return None


# ---------------------------------------------------------------------------
# 划分：批量
# ---------------------------------------------------------------------------
def build_layout_plan(
    rom: bytes,
    entries: list[dict],
    tables: dict,
    *,
    body_of=None,
    code_end: int = 0x100000,
) -> LayoutPlan:
    """把全部条目按容器分组，并给每组选写入模式。

    `body_of(entry) -> bytes` 用于估算译文编码长度；不传则不评估 overflow。
    """
    ptr_index = build_ptr_index(rom)
    plan = LayoutPlan()

    buckets: dict[Container, list[Classified]] = defaultdict(list)
    for e in entries:
        c = classify_entry(rom, e, tables, ptr_index, code_end=code_end)
        buckets[c.container].append(c)

    # 定长表：按表名分组
    by_table: dict[str, list[Classified]] = defaultdict(list)
    for c in buckets[Container.FIXED_TABLE]:
        by_table[c.detail["table"]].append(c)

    for tname, items in by_table.items():
        geom = tables[tname]
        stride = geom["stride"]
        noff = geom.get("name_offset", 0)
        # ★ 可用区（2026-11-05 修正）
        # 名字字段后面常常还有元数据（道具名 +0xA 起是指针/属性字段、
        # 图鉴分类名 +0x0C 起 16B 元数据）。用 `stride - noff` 当容量会把
        # 元数据也算进名字区，得出「全都装得下」的假结论
        # （实测 11 张表全报 fixed、溢出 0，而道具名 281 条里只有 13 条真放得下）。
        cap = int(geom.get("usable") or (stride - noff))
        bodies = [body_of(c) for c in items] if body_of is not None else []
        if bodies:
            mode, fitted, overflow = choose_table_mode(cap, bodies, stride)
            longest = max(len(b) for b in bodies)
            sug = suggest_stride(longest, stride)
            new_stride, mult = sug if sug else (stride, 1)
        else:
            mode, fitted, overflow = WriteMode.FIXED, len(items), 0
            new_stride, mult = stride, 1

        # 统计该表基址的字面量站点（relink 用）
        n_lit = len(ptr_index.get(geom["base"], []))

        plan.table_groups.append(TableGroup(
            table_name=tname, base=geom["base"], stride=stride,
            name_offset=noff, n_items=geom["n"],
            mode=mode, entries=items, fitted=fitted, overflow=overflow,
            new_stride=new_stride, stride_mult=mult, n_literals=n_lit,
        ))
    # 大表优先
    plan.table_groups.sort(key=lambda g: -len(g.entries))

    # 指针数组：按数组基址分组
    by_array: dict[int, list[Classified]] = defaultdict(list)
    for c in buckets[Container.PTR_ARRAY]:
        by_array[c.detail["array_base"]].append(c)
    for abase, items in by_array.items():
        n = max(c.detail["n_slots"] for c in items)
        plan.array_groups.append(ArrayGroup(base=abase, n_slots=n, entries=items))
    plan.array_groups.sort(key=lambda g: -len(g.entries))

    for c in buckets[Container.CODE_LITERAL]:
        c.detail["mode"] = WriteMode.RELINK.value
        plan.code_literals.append(c)
    # 同一字面量可能服务多条，去重交给上层
    plan.code_literals.sort(key=lambda c: c.detail.get("site", 0))

    for c in buckets[Container.SCRIPT_INLINE]:
        c.detail["mode"] = WriteMode.RELINK.value
        plan.script_inline.append(c)
    plan.script_inline.sort(key=lambda c: c.addr)

    for c in buckets[Container.FREE_TEXT]:
        c.detail["mode"] = WriteMode.RELINK.value
        plan.free_text.append(c)
    plan.free_text.sort(key=lambda c: c.addr)

    for c in buckets[Container.NO_PTR]:
        c.detail["mode"] = WriteMode.PRUNE.value
        plan.no_ptr.append(c)
    plan.no_ptr.sort(key=lambda c: c.addr)

    return plan


def report(plan: LayoutPlan) -> str:
    """生成人类可读摘要。"""
    s = plan.summary()
    lines = [
        f"总计 {plan.total:,} 条",
        f"  定长表      {s['tables']:>3} 张  {s['table_entries']:>6,} 条",
        f"  指针数组    {s['arrays']:>3} 个  {s['array_entries']:>6,} 条",
        f"  代码字面量  {'':>3}       {s['code_literals']:>6,} 条",
        f"  脚本内嵌    {'':>3}       {s['script_inline']:>6,} 条",
        f"  自由文本    {'':>3}       {s['free_text']:>6,} 条",
        f"  无指针      {'':>3}       {s['no_ptr']:>6,} 条",
    ]
    if plan.table_groups:
        lines.append("")
        lines.append("定长表处理方案：")
        for g in plan.table_groups:
            lines.append(
                f"  {g.table_name:<16} {len(g.entries):>4} 条  "
                f"{MODE_DESC.get(g.mode, g.mode.value):<28} "
                f"字面量 {g.n_literals} 处"
            )
    return "\n".join(lines)
