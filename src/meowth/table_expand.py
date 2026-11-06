"""定长表扩表与新区排列（流水线模块）。

对应 docs/ALGO_TABLE_EXPAND.md 阶段 1 + 2。

设计目标：
  1. 把「原版定长表」换成「扩展区新表」
  2. 支持两种布局：保持 stride（简单）/ 变长 + 指针数组（火红做法）
  3. 统一扩展区分配，避免重叠

典型用法::

    alloc = ExpandAllocator(start=0x09F00000, size=0x100000)
    plan = expand_varlen(
        name="招式名",
        orig_base=0x1CACFC, stride=8, n=354,
        bodies=[b"\\xF9\\x00\\x03\\x63\\xFF", ...],   # 已编码，含 FF
        alloc=alloc,
    )
    # plan.blob / plan.ptrarr_off / plan.new_base
"""
from __future__ import annotations

from dataclasses import dataclass, field

GBA_BASE = 0x08000000
EOS = 0xFF
ALIGN_U32 = 4


# ---------------------------------------------------------------------------
# 扩展区分配器
# ---------------------------------------------------------------------------
class ExpandAllocator:
    """扩展区线性分配器。

    只做「字节区间不重叠」这一件事。所有地址都是**文件偏移**（不含 0x08000000）。
    """

    def __init__(self, start: int, size: int):
        if start % ALIGN_U32:
            raise ValueError(f"start must be 4-byte aligned: 0x{start:X}")
        self._cursor = start
        self._end = start + size
        self._used: list[tuple[int, int, str]] = []   # (start, end, label)

    @property
    def cursor(self) -> int:
        return self._cursor

    def alloc(self, nbytes: int, label: str, align: int = ALIGN_U32) -> int:
        """分配 nbytes，返回起始文件偏移。"""
        if nbytes <= 0:
            raise ValueError("nbytes must be > 0")
        pos = self._cursor
        if align > 1:
            pos = (pos + align - 1) & ~(align - 1)
        end = pos + nbytes
        if end > self._end:
            raise MemoryError(
                f"扩展区不足：需要 {nbytes}B @0x{pos:X}，"
                f"但已到上限 0x{self._end:X}"
            )
        self._used.append((pos, end, label))
        self._cursor = end
        return pos

    def report(self) -> list[tuple[int, int, str]]:
        return list(self._used)

    def overlaps_with(self, lo: int, hi: int) -> bool:
        return any(not (hi <= s or lo >= e) for s, e, _ in self._used)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class ExpandedTable:
    """一张已扩表的完整描述。地址均为文件偏移。

    ⚠️ 关键区分（A2.4 踩过的坑）：
      `orig_base` 是**表基址**（元素 0 的起点），即代码里 `index×stride + base`
      的那条 base。**不是**名称字段的偏移。
      代码里的字面量存的是 `orig_base`，不是 `orig_base + name_offset`。
    """

    name: str
    orig_base: int                  # 表基址（元素 0 起点）
    orig_stride: int
    n_items: int
    mode: str                       # "fixed" | "varlen"
    name_offset: int = 0            # 名称字段在元素内的偏移
    new_base: int = 0               # 新表（或串区）起始
    blob: bytes = b""               # 实际要写入的字节（含串区 + 指针数组）
    ptrarr_off: int = 0             # 指针数组相对 new_base 的偏移
    n_ptr_slots: int = 0
    item_offsets: list[int] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def ptrarr_addr(self) -> int:
        """指针数组的绝对文件偏移。"""
        return self.new_base + self.ptrarr_off

    @property
    def ptrarr_gba(self) -> int:
        return GBA_BASE + self.ptrarr_addr

    def __len__(self) -> int:
        return len(self.blob)


# ---------------------------------------------------------------------------
# 阶段 1：保持 stride 的扩表（简单模式）
# ---------------------------------------------------------------------------
def expand_fixed(
    name: str,
    orig_base: int,
    stride: int,
    n: int,
    bodies: list[bytes],
    alloc: ExpandAllocator,
    *,
    name_offset: int = 0,
    pad: int = 0x00,
) -> ExpandedTable:
    """保持 stride 不变，每项 = [名字][填充][元数据]。

    参数 `orig_base` 是**表基址**（元素 0 起点）。
    `bodies` 里每项**必须** <= stride - name_offset。

    ⚠️ 与 expand_varlen 的区别：
      fixed 模式**只替换名字区**，其余字节由调用方保留（tail 参数）。
      这里为了通用，bodies 就是「整项 40B」，调用方负责拼好。
    """
    cap = stride - name_offset
    if len(bodies) != n:
        raise ValueError(f"{name}: bodies 数 {len(bodies)} != n {n}")
    for i, b in enumerate(bodies):
        if len(b) > cap:
            raise ValueError(
                f"{name}[{i}]: {len(b)}B 超过可用宽度 {cap}B"
                f"（stride {stride} - name_offset {name_offset}），"
                f"应改用 expand_varlen"
            )

    blob = bytearray()
    for b in bodies:
        if name_offset:
            blob += bytes(name_offset)
        blob += b
        blob += bytes([pad]) * (cap - len(b))

    new_base = alloc.alloc(len(blob), label=f"{name}:fixed", align=ALIGN_U32)
    return ExpandedTable(
        name=name,
        orig_base=orig_base,
        orig_stride=stride,
        n_items=n,
        mode="fixed",
        name_offset=name_offset,
        new_base=new_base,
        blob=bytes(blob),
        ptrarr_off=0,
        n_ptr_slots=0,
        item_offsets=[i * stride for i in range(n)],
        extra={"stride": stride, "name_offset": name_offset, "cap": cap},
    )


# ---------------------------------------------------------------------------
# 阶段 1+2：变长 + 指针数组（火红做法）
# ---------------------------------------------------------------------------
def expand_varlen(
    name: str,
    orig_base: int,
    orig_stride: int,
    n: int,
    bodies: list[bytes],
    alloc: ExpandAllocator,
    *,
    name_offset: int = 0,
    ptrarr_align: int = ALIGN_U32,
) -> ExpandedTable:
    """变长串区 + 紧跟 4 字节对齐的指针数组。

    参数 `orig_base` 是**表基址**（元素 0 起点），不是名称字段。

    布局::

        new_base ┌── 串 0 (含 FF) ──┬── 串 1 ──┬ ... ┬─ pad ─┬─ ptr[0] ─┬─ ptr[1] ─ ...
                 └────────────────┴─────────┴─────┴───────┴─────────┴────────

    ptr[i] 的值 = GBA_BASE + new_base + item_offsets[i]
    """
    if len(bodies) != n:
        raise ValueError(f"{name}: bodies 数 {len(bodies)} != n {n}")

    blob = bytearray()
    item_offsets: list[int] = []
    for b in bodies:
        if not b.endswith(bytes([EOS])):
            raise ValueError(f"{name}: 每项必须以 0xFF 结尾")
        item_offsets.append(len(blob))
        blob += b

    # 指针数组前做 4 字节对齐
    pad_n = (-len(blob)) % ptrarr_align
    blob += bytes(pad_n)
    ptrarr_off = len(blob)

    # 预留指针槽（值占位，等 new_base 确定后回填）
    blob += bytes(4 * n)

    new_base = alloc.alloc(len(blob), label=f"{name}:varlen", align=ALIGN_U32)

    # 回填指针值
    import struct

    for i, off in enumerate(item_offsets):
        struct.pack_into("<I", blob, ptrarr_off + i * 4,
                         GBA_BASE + new_base + off)

    return ExpandedTable(
        name=name,
        orig_base=orig_base,
        orig_stride=orig_stride,
        n_items=n,
        mode="varlen",
        name_offset=name_offset,
        new_base=new_base,
        blob=bytes(blob),
        ptrarr_off=ptrarr_off,
        n_ptr_slots=n,
        item_offsets=item_offsets,
        extra={"pad_before_ptrarr": pad_n, "name_offset": name_offset},
    )


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def encode_body(charmap, text: str) -> bytes:
    """用工程 charmap 把译文编码成含 0xFF 结尾的字节串。"""
    raw = charmap.encode(text)
    if not raw.endswith(bytes([EOS])):
        raw = bytes(raw) + bytes([EOS])
    return raw


def expand_variable(
    name: str,
    orig_base: int,
    orig_stride: int,
    new_stride: int,
    n: int,
    bodies: list[bytes],
    alloc,
    *,
    name_offset: int = 0,
    meta_bytes: int = 0,
    pad: int = 0x00,
) -> ExpandedTable:
    """VARIABLE 模式：放大 stride 后重排。

    适用：stride 放得下译文，但旧 stride 不够。
    要点：
      - 名字区 = new_stride - meta_bytes
      - 每项 = [名字区][元数据区]（元数据从原表对应位置复制）
      - 代码里的 `index×stride` 必须同步改成 `index×new_stride`

    参数：
      meta_bytes: 名字区之后的元数据字节数（原 stride - 原可用宽度）
      bodies:     每项的「名字区字节」（含 eos，长度 ≤ new_stride - meta_bytes）

    与 expand_fixed 的区别：
      fixed 保持 stride，本函数改变 stride（需配 asm patch）
    """
    name_cap = new_stride - meta_bytes
    if len(bodies) != n:
        raise ValueError(f"{name}: bodies 数 {len(bodies)} != n {n}")
    if new_stride < orig_stride:
        raise ValueError(f"{name}: new_stride {new_stride} < orig {orig_stride}")
    for i, b in enumerate(bodies):
        if len(b) > name_cap:
            raise ValueError(
                f"{name}[{i}]: {len(b)}B 超过名字区 {name_cap}B"
                f"（new_stride {new_stride} - meta {meta_bytes}）"
            )

    blob = bytearray()
    for b in bodies:
        blob += b
        blob += bytes([pad]) * (name_cap - len(b))
        blob += bytes(meta_bytes)   # 元数据区先补 0，调用方按需回填

    new_base = alloc.alloc(len(blob), label=f"{name}:variable", align=ALIGN_U32)
    return ExpandedTable(
        name=name,
        orig_base=orig_base,
        orig_stride=orig_stride,
        n_items=n,
        mode="variable",
        name_offset=name_offset,
        new_base=new_base,
        blob=bytes(blob),
        ptrarr_off=0,
        n_ptr_slots=0,
        item_offsets=[i * new_stride for i in range(n)],
        extra={
            "new_stride": new_stride,
            "orig_stride": orig_stride,
            "meta_bytes": meta_bytes,
            "name_cap": name_cap,
            "stride_mult": new_stride // orig_stride if orig_stride else 1,
        },
    )


def copy_variable_with_meta(
    name: str,
    rom: bytes,
    orig_base: int,
    orig_stride: int,
    new_stride: int,
    n: int,
    names: dict[int, bytes],
    alloc,
    *,
    meta_src: tuple[int, int],
) -> ExpandedTable:
    """VARIABLE 模式的实用版：保留原元数据字节。

    参数：
      names:    {index: 新名字字节}；缺项的按原表复制
      meta_src: (原元数据起点相对项起点的偏移, 元数据长度)
                例：道具名 meta_src=(9, 31) 表示元数据在 +9..+40

    这样能把原项的元数据（指针、标志等）原样搬到新表，不丢数据。
    """
    meta_off, meta_len = meta_src
    name_cap = new_stride - meta_len

    blob = bytearray()
    for i in range(n):
        src = orig_base + i * orig_stride
        # 名字
        nb = names.get(i)
        if nb is None:
            raw = rom[src:src + orig_stride]
            ff = raw.find(b"\xFF")
            z = raw.find(b"\x00")
            ends = [x for x in (ff, z) if x >= 0]
            end = min(ends) + 1 if ends else 1
            nb = raw[:end]
        if len(nb) > name_cap:
            raise ValueError(f"{name}[{i}]: {len(nb)}B > {name_cap}B")
        blob += nb + bytes(name_cap - len(nb))
        # 元数据原样复制
        blob += rom[src + meta_off:src + meta_off + meta_len]

    new_base = alloc.alloc(len(blob), label=f"{name}:variable", align=ALIGN_U32)
    return ExpandedTable(
        name=name,
        orig_base=orig_base,
        orig_stride=orig_stride,
        n_items=n,
        mode="variable",
        new_base=new_base,
        blob=bytes(blob),
        ptrarr_off=0,
        n_ptr_slots=0,
        item_offsets=[i * new_stride for i in range(n)],
        extra={
            "new_stride": new_stride,
            "orig_stride": orig_stride,
            "meta_bytes": meta_len,
            "meta_src": meta_src,
            "name_cap": name_cap,
            "stride_mult": new_stride // orig_stride if orig_stride else 1,
        },
    )


def describe(plan: ExpandedTable) -> str:
    """人类可读的摘要，日志用。"""
    return (
        f"{plan.name}: {plan.mode} n={plan.n_items} "
        f"orig=0x{plan.orig_base:06X}/stride{plan.orig_stride} "
        f"new=0x{plan.new_base:06X} blob={len(plan.blob)}B "
        + (f"ptrarr=0x{plan.ptrarr_addr:06X}({plan.n_ptr_slots})"
           if plan.mode == "varlen" else "")
    )
