#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 ROM 数据自动推导每张定长表的「名字字段宽度」，不手填常量。

## 为什么

`usable`（名字字段的固定宽度 = name_offset 到元数据起点）之前是手填的，
这是错的：一旦换表/换区域就会失效，而且无法解释来源。

正确来源是数据本身：原版 ROM 里每张表的**最长名字**就定义了这个字段宽度
（编译器按最长项分配，短的补终止符）。所以

    usable = max over entries ( 名字终止符位置 - name_offset )

终止符按各表的 eos 取（道具名 0xFF、图鉴分类名 0x00）。

用法：
    python scripts/research/ruby/derive_usable.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
GAME = "POKEMON_RUBY_AXVJ00"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"


def eos_of(rom: bytes, base: int, stride: int, n: int, noff: int) -> int:
    """判定该表名字的终止符：FF 或 00（看哪个更常见）。"""
    ff = zz = 0
    for i in range(min(n, 200)):
        seg = rom[base + i * stride + noff: base + i * stride + stride]
        for k, b in enumerate(seg):
            if b == 0xFF:
                ff += 1
                break
            if b == 0x00:
                zz += 1
                break
    return 0x00 if zz > ff else 0xFF


def derive(rom: bytes, base: int, stride: int, n: int, noff: int,
           eos: int) -> tuple[int, list[int]]:
    """返回 (usable, 每项名字长度列表)。

    usable = 最长名字字节数 + 1（终止符本身也占一个字节，属于该字段）。
    实测对照：道具名最长 8B → usable 9（+0x00..+0x08），与 ROM 逐字节核对一致。
    """
    widths: list[int] = []
    for i in range(n):
        seg = rom[base + i * stride + noff: base + (i + 1) * stride]
        end = len(seg)
        for k, b in enumerate(seg):
            if b == eos:
                end = k
                break
        widths.append(end)
    longest = max(widths) if widths else 0
    return longest + 1, widths


def main() -> int:
    rom = ROM.read_bytes()
    tj = json.loads(TEXTS.read_text(encoding="utf-8"))

    print(f"{'表':<16}{'stride':>7}{'name@':>6}{'eos':>5}{'n':>5}"
          f"{'usable':>8}{'最长名':>7}  依据")
    print("-" * 78)
    out = {}
    for mid, meta in (tj.get("modules") or {}).items():
        typ = meta.get("type") or ""
        if typ not in ("stride", "struct", "stride_ptr", "ptr_stride"):
            continue
        start, end = meta.get("start"), meta.get("end")
        if not start or not end:
            continue
        read = meta.get("read") or {}
        stride = int(read.get("stride") or read.get("entry_size") or 0)
        if stride <= 0:
            continue
        base = int(str(start), 16)
        last = int(str(end), 16)
        n = (last - base) // stride
        noff = int(read.get("name_offset") or 0)
        eos = eos_of(rom, base, stride, n, noff)
        usable, widths = derive(rom, base, stride, n, noff, eos)
        out[mid] = {"usable": usable, "eos": eos, "n": n, "stride": stride,
                    "name_offset": noff}
        print(f"{mid:<16}{stride:>7}{noff:>6}{eos:>#5x}{n:>5}"
              f"{usable:>8}{max(widths) if widths else 0:>7}  最长名字定义字段宽度")

    print()
    print("JSON（供 plan_full_layout.py 读取，不再手填）：")
    print(json.dumps({k: v["usable"] for k, v in out.items()},
                     ensure_ascii=False))
    dst = ROOT / "work" / GAME / "table_usable.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[out] {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
