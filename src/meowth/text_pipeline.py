"""四步通用文本流水线：READ → CLASSIFY → PLACE → RELINK。

对应 docs/ALGO_PIPELINE.md。

用户要求（2026-11-04）：
  **不要只纠结单个文本或单个块，这是一个通用算法。**
  读取一段文本 → 判断归属 → 放入新区 → 标记待修改指针。
  最终 texts.json + texts_translated.json + python = translated.build.json

与 `meowth/pipeline.py` 的区别：
  `pipeline.py` 是旧的 TranslationEngine 兼容层（deprecated），本模块是新的
  通用写入算法，不依赖旧引擎。

典型用法::

    from meowth.text_pipeline import run_pipeline

    result = run_pipeline(
        rom=rom,
        entries=translated_entries,
        tables=KNOWN_TABLES,      # 含 base/stride/n/usable/eos
        encoder=charmap.encode,
    )
    result.build_json()           # → translated.build.json
    result.byte_patches           # → 直接应用到 ROM
    result.asm_patches            # → hook/patches/*.asm
"""
from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field

from .auto_layout import (
    Container, build_ptr_index, classify_entry,
)
from .region_alloc import RegionAllocator, default_allocator
from .table_relink import (
    AsmPatch, Patch, find_literal_sites, make_stride_scale_patch,
)

GBA_BASE = 0x08000000


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------
@dataclass
class EntryResult:
    """一条文本的完整处理结果。"""

    entry_id: str
    module: str
    old_offset: int
    container: str
    text: str
    encoded: bytes
    placed_offset: int = 0
    placed_mode: str = ""
    relink: list[dict] = field(default_factory=list)
    note: str = ""


@dataclass
class TableResult:
    """一张表的处理结果。"""

    name: str
    orig_base: int
    orig_stride: int
    new_stride: int
    mode: str
    new_base: int
    size: int
    n_items: int
    n_entries: int
    literals: list[int] = field(default_factory=list)


@dataclass
class PipelineResult:
    entries: list[EntryResult] = field(default_factory=list)
    tables: list[TableResult] = field(default_factory=list)
    byte_patches: list[Patch] = field(default_factory=list)
    asm_patches: list[AsmPatch] = field(default_factory=list)
    table_blobs: dict[str, tuple[int, bytes]] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)

    def build_json(self) -> dict:
        return {
            "entries": [
                {
                    "id": e.entry_id,
                    "module": e.module,
                    "old_offset": f"0x{e.old_offset:06X}",
                    "container": e.container,
                    "text": e.text,
                    "placed": {
                        "offset": (f"0x{e.placed_offset:06X}"
                                   if e.placed_offset else None),
                        "mode": e.placed_mode,
                    },
                    "relink": e.relink,
                    "note": e.note,
                }
                for e in self.entries
            ],
            "tables": [
                {
                    "name": t.name,
                    "orig_base": f"0x{t.orig_base:06X}",
                    "new_base": f"0x{t.new_base:06X}",
                    "orig_stride": t.orig_stride,
                    "new_stride": t.new_stride,
                    "mode": t.mode,
                    "size": t.size,
                    "n_items": t.n_items,
                    "n_entries": t.n_entries,
                }
                for t in self.tables
            ],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _addr(e: dict) -> int:
    try:
        a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
    except ValueError:
        return 0
    return a - GBA_BASE if a >= GBA_BASE else a


def _index_in_table(e: dict, geom: dict) -> int | None:
    """由条目地址反算表中的索引。

    必须扣除 name_offset：条目地址 = base + i*stride + name_offset。
    实测 name_offset 因表而异（秘密基地装饰名是 1，其余多为 0），
    不能假设为 0。
    """
    a = _addr(e)
    base, stride, n = geom["base"], geom["stride"], geom["n"]
    noff = geom.get("name_offset", 0)
    if a < base + noff:
        return None
    delta = a - base - noff
    if delta % stride:
        return None
    idx = delta // stride
    return idx if 0 <= idx < n else None


# ---------------------------------------------------------------------------
# ① READ
# ---------------------------------------------------------------------------
def read_text(rom: bytes, entry: dict) -> tuple[int, bytes]:
    """读出一段文本的原始字节（含 eos）。"""
    addr = _addr(entry)
    try:
        raw = bytes.fromhex((entry.get("original_hex") or "").replace(" ", ""))
    except ValueError:
        raw = b""
    return addr, raw


# ---------------------------------------------------------------------------
# ③ PLACE：定长表
# ---------------------------------------------------------------------------
def _place_table(
    rom: bytes,
    tname: str,
    geom: dict,
    items: list[tuple[dict, bytes]],
    alloc: RegionAllocator,
    result: PipelineResult,
) -> TableResult:
    """处理一张定长表：FIXED 或 VARIABLE。

    每项布局 = [name_offset 字节的头部][名字区 usable][元数据 meta]
    其中 name_offset + usable + meta == stride
    """
    stride = geom["stride"]
    usable = geom.get("usable", stride)
    n = geom["n"]
    eos = geom.get("eos", 0xFF)
    noff = geom.get("name_offset", 0)
    meta = stride - noff - usable

    longest = max((len(enc) for _, enc in items), default=0)

    # 按索引归位置
    slot_enc: dict[int, bytes] = {}
    for e, enc in items:
        idx = _index_in_table(e, geom)
        if idx is not None:
            slot_enc[idx] = enc

    def take(i: int) -> bytes:
        """取第 i 项的名字字节（有译文用译文，否则用原文）。"""
        if i in slot_enc:
            return slot_enc[i]
        src = geom["base"] + i * stride + noff
        return rom[src:src + usable]

    if longest <= usable:
        # === FIXED：保持 stride，整项复制原结构，只替换名字 ===
        blob = bytearray()
        for i in range(n):
            src = geom["base"] + i * stride
            item = bytearray(rom[src:src + stride])
            nb = take(i)[:usable]
            item[noff:noff + len(nb)] = nb
            # 名字之后的剩余字节补 eos（若原文更长）
            for k in range(noff + len(nb), noff + usable):
                item[k] = 0x00
            blob += item

        new_base = alloc.alloc(len(blob), label=f"{tname}:fixed")
        blob = bytes(blob)
        mode = "fixed"
        new_stride = stride
    else:
        # === VARIABLE：放大 stride ===
        # 优先用几何里显式声明的 new_stride（对应 asm patch）
        new_stride = geom.get("new_stride")
        if new_stride is None:
            mult = 8
            for k in (2, 4, 8):
                if longest <= stride * k - (stride - usable):
                    mult = k
                    break
            new_stride = stride * mult

        # 新可用宽度：显式声明优先，否则按「元数据字节数不变」推算
        name_cap = geom.get("new_usable")
        if name_cap is None:
            name_cap = new_stride - noff - meta
        else:
            name_cap = name_cap

        # 元数据区长度：新旧保持一致
        new_meta = new_stride - noff - name_cap
        if new_meta < 0:
            raise ValueError(
                f"{tname}: new_stride {new_stride} 不足以容纳 "
                f"name_offset {noff} + new_usable {name_cap}"
            )

        blob = bytearray()
        for i in range(n):
            src = geom["base"] + i * stride
            nb = take(i)
            if len(nb) > name_cap:
                nb = nb[:name_cap - 1] + bytes([eos])
            # [头部][名字][补 eos 到 name_cap][元数据]
            blob += rom[src:src + noff]
            blob += nb
            blob += bytes([eos]) * (name_cap - len(nb))
            if new_meta:
                meta_src = rom[src + noff + usable:src + stride]
                if len(meta_src) < new_meta:
                    meta_src = meta_src + bytes(new_meta - len(meta_src))
                blob += meta_src[:new_meta]

        new_base = alloc.alloc(len(blob), label=f"{tname}:variable")
        blob = bytes(blob)
        mode = "variable"

    result.table_blobs[tname] = (new_base, blob)

    # ④ RELINK：改基址字面量
    old_gba = GBA_BASE + geom["base"]
    new_gba = GBA_BASE + new_base
    literals = find_literal_sites(rom, old_gba)
    for site in literals:
        result.byte_patches.append(Patch(
            site, struct.pack("<I", new_gba),
            f"{tname} base 0x{old_gba:08X}→0x{new_gba:08X}",
        ))

    # 记录每条
    for e, enc in items:
        idx = _index_in_table(e, geom)
        result.entries.append(EntryResult(
            entry_id=str(e.get("id") or e.get("address")),
            module=tname,
            old_offset=(geom["base"] + idx * stride + noff)
                       if idx is not None else 0,
            container="FIXED_TABLE",
            text=e.get("translated") or "",
            encoded=enc,
            placed_offset=((new_base + idx * new_stride + noff)
                           if idx is not None else 0),
            placed_mode=mode,
            relink=[{"kind": "LITERAL", "offset": f"0x{s:06X}",
                     "target": f"0x{new_gba:08X}"} for s in literals],
            note=(f"stride {stride}→{new_stride}" if mode == "variable" else ""),
        ))

    return TableResult(
        name=tname, orig_base=geom["base"], orig_stride=stride,
        new_stride=new_stride, mode=mode, new_base=new_base,
        size=len(blob), n_items=n, n_entries=len(items),
        literals=literals,
    )


# ---------------------------------------------------------------------------
# ① ~ ④ 总体
# ---------------------------------------------------------------------------
def run_pipeline(
    rom: bytes,
    entries: list[dict],
    tables: dict,
    *,
    encoder,
    alloc: RegionAllocator | None = None,
    only_tables: bool = False,
) -> PipelineResult:
    """跑完整四步。

    参数：
      entries: 每条含 id/module/address/original_hex/translated
      tables:  {表名: {base, stride, n, usable, eos}}
      encoder: 文本 → 字节（含 eos）
      only_tables: True 时只处理定长表，其余容器跳过
    """
    if alloc is None:
        alloc = default_allocator()

    result = PipelineResult()

    # ② CLASSIFY
    ptr_index = build_ptr_index(rom)
    classified = [classify_entry(rom, e, tables, ptr_index) for e in entries]

    by_table: dict[str, list[tuple[dict, bytes]]] = {}
    others: list[tuple[dict, bytes, object]] = []

    for c, e in zip(classified, entries):
        text = e.get("translated") or ""
        if not text:
            continue
        enc = encoder(text)
        if c.container is Container.FIXED_TABLE:
            by_table.setdefault(c.detail["table"], []).append((e, enc))
        elif not only_tables:
            others.append((e, enc, c))

    # ③④ 定长表
    for tname, items in by_table.items():
        geom = tables.get(tname)
        if not geom:
            continue
        result.tables.append(_place_table(rom, tname, geom, items, alloc, result))
    result.tables.sort(key=lambda t: -t.n_entries)

    # ③④ 其余容器：文本单独放新区，指针指过来
    for e, enc, c in others:
        off = alloc.alloc(len(enc), label=f"{c.container.value}", align=1)
        new_gba = GBA_BASE + off
        relink = []

        sites: list[int] = []
        if c.container is Container.PTR_ARRAY:
            if c.detail.get("site"):
                sites.append(c.detail["site"])
        elif c.container is Container.CODE_LITERAL:
            if c.detail.get("site"):
                sites.append(c.detail["site"])
        elif c.container is Container.SCRIPT_INLINE:
            sites.extend(c.detail.get("sites") or [])
        elif c.container is Container.FREE_TEXT:
            sites.extend(c.detail.get("sites") or [])

        for s in sites:
            result.byte_patches.append(Patch(
                s, struct.pack("<I", new_gba),
                f"{c.container.value} → 0x{new_gba:08X}",
            ))
            kind = ("SCRIPT_SLOT" if c.container is Container.SCRIPT_INLINE
                    else "LITERAL")
            relink.append({"kind": kind, "offset": f"0x{s:06X}",
                           "target": f"0x{new_gba:08X}"})

        result.entries.append(EntryResult(
            entry_id=str(e.get("id") or e.get("address")),
            module=str(e.get("module") or ""),
            old_offset=_addr(e),
            container=c.container.value,
            text=e.get("translated") or "",
            encoded=enc,
            placed_offset=off,
            placed_mode="relocated",
            relink=relink,
        ))

    # 汇总
    cnt = Counter(e.container for e in result.entries)
    result.summary = {
        "total": len(result.entries),
        "by_container": dict(cnt),
        "tables": len(result.tables),
        "byte_patches": len(result.byte_patches),
        "alloc_used": alloc.cursor - 0x09F00000,
        "alloc_remaining": alloc.remaining,
    }
    return result
