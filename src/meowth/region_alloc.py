"""新区分配器（流水线模块）。

用户指示：ROM 可扩容到 16/32MB，**空间不是约束**。
所以本分配器只保证「区间不重叠 + 4 字节对齐」，不做紧凑优化。

典型用法::

    alloc = RegionAllocator(start=0x09F00000, end=0x0A000000)
    a = alloc.alloc(1024, "招式名")      # → 文件偏移
    b = alloc.alloc(2048, "特性名")
    alloc.report()
"""
from __future__ import annotations

from dataclasses import dataclass, field

GBA_BASE = 0x08000000
ALIGN = 4


@dataclass
class Region:
    """一段已分配区域。"""

    start: int
    end: int
    label: str

    @property
    def size(self) -> int:
        return self.end - self.start

    @property
    def gba_start(self) -> int:
        return GBA_BASE + self.start


class RegionAllocator:
    """线性分配器。地址都是文件偏移（不含 0x08000000）。"""

    def __init__(self, start: int, end: int):
        if start % ALIGN:
            raise ValueError(f"start 必须 4 字节对齐: 0x{start:X}")
        if end <= start:
            raise ValueError(f"end 必须大于 start: 0x{start:X}..0x{end:X}")
        self._cursor = start
        self._start = start
        self._end = end
        self._regions: list[Region] = []

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return self._end - self._cursor

    def alloc(self, nbytes: int, label: str, align: int = ALIGN) -> int:
        """分配 nbytes，返回起始文件偏移。"""
        if nbytes <= 0:
            raise ValueError("nbytes 必须 > 0")
        pos = self._cursor
        if align > 1:
            pos = (pos + align - 1) & ~(align - 1)
        end = pos + nbytes
        if end > self._end:
            raise MemoryError(
                f"扩展区不足：需要 {nbytes}B @0x{pos:X}，"
                f"上限 0x{self._end:X}（剩 {self.remaining}B）"
            )
        self._regions.append(Region(pos, end, label))
        self._cursor = end
        return pos

    def reserve(self, start: int, end: int, label: str) -> None:
        """标记一段已被占用（不分配，只记录）。"""
        if start % ALIGN:
            raise ValueError(f"start 必须 4 字节对齐: 0x{start:X}")
        self._regions.append(Region(start, end, label))
        if end > self._cursor:
            self._cursor = (end + ALIGN - 1) & ~(ALIGN - 1)

    def overlaps(self, lo: int, hi: int) -> list[Region]:
        """返回与 [lo,hi) 重叠的区域。"""
        return [r for r in self._regions
                if not (hi <= r.start or lo >= r.end)]

    def report(self) -> str:
        lines = [f"RegionAllocator 0x{self._start:X}..0x{self._end:X}",
                 f"  已用 {self._cursor - self._start:,}B  剩余 {self.remaining:,}B"]
        for r in self._regions:
            lines.append(
                f"  0x{r.start:06X}..0x{r.end:06X}  {r.size:>8,}B  {r.label}"
            )
        return "\n".join(lines)


def default_allocator() -> RegionAllocator:
    """默认扩展区：0x09F00000 到 0x0A000000（16 MB 空间）。

    注意：这不是「ROM 上限」，ROM 可扩到 32MB。
    只是选一个当前产物之外、且不与已知占用冲突的起点。
    """
    return RegionAllocator(start=0x09F00000, end=0x0A000000)
