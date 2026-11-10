#!/usr/bin/env python3
"""A2.4 道具名：正确几何的全链路验证。

最终确认的结构（字节级 + 反汇编双重证据）：
  代码：base + idx*40，base = 0x39A648（反汇编 0x0A5388..0x0A5390）
  每项 40B = [名字][FF 填充][元数据（含指针）]
  名字可用宽度 = 40B（原文最长 9B，绰绰有余）

  例：0x39A670: 6f 5d 60 ae 9a ae 79 ff ff 00 01 00 00 00 00 00
                └── マスターボール (7B) ──┘ FF FF + 标志
                0x39A680: dc 84 39 08 ...  ← 元数据（描述指针）

路线 A（本脚本）：保持 stride=40，整项复制，只替换名字 → 只改字面量
路线 B（备选）：变长 + 指针数组 → 必须改 index*40 的机器码

用法：
    python scripts/research/ruby/a2_item_route_a.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
OUT = ROOT / "work" / "_probe" / "a2_item_route_a.json"
GBA_BASE = 0x08000000

BASE = 0x39A648
STRIDE = 40
N = 348
ALLOC_START = 0x09F00000
ALLOC_SIZE = 0x100000


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import ExpandAllocator, expand_fixed, encode_body, describe
    from meowth.table_relink import find_literal_sites, find_ldr_literals, Patch

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        try:
            addr = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        items[addr] = e

    print(f"=== 阶段 1：构造 {N} 项（整项 40B 复制，只替换名字）===")
    bodies: list[bytes] = []
    n_trans = 0
    over = []

    for i in range(N):
        base = BASE + i * STRIDE
        e = items.get(base)
        text = (e.get("translated") or "") if e else ""

        if not text:
            bodies.append(rom[base:base + STRIDE])
            continue

        body = encode_body(cm, text)
        n_trans += 1
        if len(body) > STRIDE:
            over.append((i, text, len(body)))
            body = body[:STRIDE - 1] + bytes([0xFF])

        # 保留原项的元数据部分：找原名字的 FF 结尾，之后原样保留
        orig = rom[base:base + STRIDE]
        ff = orig.find(b"\xFF")
        tail = orig[ff + 1:] if ff >= 0 else b""
        new_item = body + bytes([0x00]) * max(0, STRIDE - len(body) - len(tail)) + tail
        bodies.append(new_item[:STRIDE].ljust(STRIDE, b"\x00"))

    print(f"  有译文 {n_trans} 项，超长 {len(over)} 项")
    for i, t, n in over[:5]:
        print(f"    item{i} {t!r} = {n}B")

    # ---- 阶段 2 ----
    alloc = ExpandAllocator(start=ALLOC_START, size=ALLOC_SIZE)
    plan = expand_fixed(
        name="道具名", orig_base=BASE, stride=STRIDE, n=N,
        bodies=bodies, alloc=alloc, name_offset=0,
    )
    print()
    print("=== 阶段 2：新区排列 ===")
    print(f"  {describe(plan)}")
    print(f"  新区 0x{plan.new_base:06X}..0x{plan.new_base + len(plan.blob):06X}")
    print(f"  stride 保持 {STRIDE}，代码 index*40 无需改 ✅")

    # 校验：每个 item 的首字节是名字起始
    bad = 0
    for i in range(N):
        off = i * STRIDE
        seg = plan.blob[off:off + STRIDE]
        if b"\xFF" not in seg:
            bad += 1
    print(f"  每项含 FF 结尾: {N - bad}/{N}" + ("  ✅" if bad == 0 else f"  ❌{bad}"))

    # ---- 阶段 3 ----
    print()
    print("=== 阶段 3：指针修改 ===")
    old_gba = GBA_BASE + BASE
    sites = find_literal_sites(rom, old_gba, require_aligned=True)
    print(f"  旧表基址 0x{old_gba:08X} 的字面量 {len(sites)} 处")

    patches = []
    for s in sites:
        if struct.unpack_from("<I", rom, s)[0] != old_gba:
            continue
        ldrs = find_ldr_literals(rom, s)
        patches.append(Patch(s, struct.pack("<I", GBA_BASE + plan.new_base),
                             f"ldr@0x{ldrs[0]:X}" if ldrs else "裸指针"))
    print(f"  patch {len(patches)} 条")
    for p in patches[:4]:
        print(f"    0x{p.offset:06X}: {p.data.hex(' ')}  {p.label}")

    print()
    print("=== 结果 ===")
    print(f"  新表 {len(plan.blob):,} B @0x{plan.new_base:06X}")
    print(f"  消灭 F980: {n_trans} 条")
    print(f"  **不改任何机器码**，只改 {len(patches)} 处字面量")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "table": "道具名",
        "orig_base": f"0x{BASE:06X}",
        "new_base": f"0x{plan.new_base:06X}",
        "stride": STRIDE,
        "n_items": N,
        "n_translated": n_trans,
        "blob_size": len(plan.blob),
        "patches": [{"offset": f"0x{p.offset:06X}", "data": p.data.hex(" "),
                     "label": p.label} for p in patches],
        "blob_sha_head": plan.blob[:32].hex(" "),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
