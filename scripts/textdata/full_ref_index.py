#!/usr/bin/env python3
"""全域文本引用索引（含非对齐、脚本指令内嵌）。

为什么需要它（实测 2026-11-04）：
  ruby 的剧情文本引用有两种形态：
    A. `0F 00 <ptr32>`          脚本 TEXT 指令，ptr 4 对齐
    B. `<op u16><id u16><ptr32>` 脚本指令族，ptr **非 4 对齐**
  实测 0x08149329 的引用槽 0x1490BF：
      99 02 00 00 | 29 93 14 08
      └命令+ID──┘ └──指针32──┘
  `build_ptr_index` 只扫 4 对齐位置，所以形态 B 全部漏掉，
  1,917 条真台词因此被判「无指针」。

本模块提供 build_full_ptr_index()：逐字节扫描，建立
  目标文件偏移 → [引用槽位]（含非对齐）
以及 classify_ref()：按槽位上下文判定引用类型。

用法：
    from scripts.research.ruby.full_ref_index import build_full_ptr_index
"""
from __future__ import annotations

import struct
from collections import defaultdict

GBA_BASE = 0x08000000
ROM_MAX = 0x0A000000


def build_full_ptr_index(rom: bytes) -> dict[int, list[int]]:
    """逐字节扫描全 ROM，建立「目标文件偏移 → 引用槽位」索引。

    与 auto_layout.build_ptr_index 的区别：后者只扫 4 对齐位置，
    本函数扫每一个字节偏移，因此能抓到脚本指令里的非对齐指针。
    """
    idx: dict[int, list[int]] = defaultdict(list)
    n = len(rom)
    for off in range(0, n - 4):
        v = struct.unpack_from("<I", rom, off)[0]
        if GBA_BASE <= v < ROM_MAX:
            idx[v - GBA_BASE].append(off)
    return dict(idx)


def ref_context(rom: bytes, slot: int, back: int = 6) -> dict:
    """看一个引用槽位前后的字节，判定它属于哪种引用形态。"""
    pre = rom[max(0, slot - back):slot]
    post = rom[slot + 4:slot + 8]
    out = {
        "slot": slot,
        "aligned": (slot % 4 == 0),
        "pre": pre.hex(" "),
        "post": post.hex(" "),
        "kind": "unknown",
    }
    # A. 0F 00 <ptr32>
    if len(pre) >= 2 and pre[-2:] == b"\x0f\x00":
        out["kind"] = "TEXT_OP"          # 脚本 TEXT 指令
    # B. <op u16><id u16><ptr32>：槽前 4 字节 = XX XX 00 00 或类似的命令字
    elif len(pre) >= 4 and pre[-2:] == b"\x00\x00":
        out["kind"] = "SCRIPT_CMD"       # 脚本指令 + ID
    # C. 2 字节命令
    elif len(pre) >= 2:
        out["kind"] = "SHORT_CMD"
    return out
