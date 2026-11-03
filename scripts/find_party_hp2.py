#!/usr/bin/env python3
"""从 SaveBlock1 的 playerParty 里实测 HP 偏移（不用 gPlayerParty 符号）。

── 为什么换数据源 ────────────────────────────────────────────────────
上一版用 gPlayerParty @0x03004360（符号标 KEEP-US），实测读出来
level=8/25/28、status=0x00080012，与存档解出的 36/36/4/10/18/5 完全不符
⇒ **该符号在日版不可信**（和本项目已发现的 gCamera、gObjectEvents 一样）。

改用本项目**已知实证**的路径：
    SaveBlock2 运行时地址（prove 定位） + 0x890 = SaveBlock1
    SB1+0x234 = partyCount（u8）
    SB1+0x238 起 = playerParty[6]，每只 100 字节，+0x54 = level（明文）

本脚本读一帧 ram.bin，用 scene.log 里的 sb1 地址定位，然后把每只的
明文区 u16 列出来，找 hp/maxHp。

用法：python scripts/find_party_hp2.py <run_dir> [帧名]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000
SB1_DELTA = 0x890
O_COUNT, O_PARTY = 0x234, 0x238
MON = 100


def find_sb1(run: Path):
    """从 scene.log 的 [PROVE] 行拿 sb2 地址。"""
    for side in ("translated", "origin"):
        log = run / side / "scene.log"
        if not log.is_file():
            continue
        txt = log.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"sb2=0x([0-9A-Fa-f]{8})", txt)
        if m:
            return int(m.group(1), 16), side
    return None, None


def load_ram(run: Path, side: str, key: str | None):
    d = run / side
    if key:
        for line in (d / "index.csv").read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                f = d / f"{p[3].replace('.png', '')}.ram.bin"
                if f.is_file():
                    return f.read_bytes(), f.name
    for f in sorted(d.glob("*.ram.bin")):
        return f.read_bytes(), f.name
    return None, None


def slice_ram(data: bytes, addr: int, n: int):
    off = (EWRAM_LEN + (addr - IWRAM_BASE)) if addr >= IWRAM_BASE else (addr - EWRAM_BASE)
    if off < 0 or off + n > len(data):
        return None
    return data[off:off + n]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    key = sys.argv[2] if len(sys.argv) > 2 else None

    sb2, side = find_sb1(run)
    if sb2 is None:
        print("[ERR] scene.log 里没有 sb2 地址")
        return 1
    sb1 = sb2 + SB1_DELTA
    print(f"SaveBlock2=0x{sb2:08X}  SaveBlock1=0x{sb1:08X}  (side={side})")

    data, name = load_ram(run, side, key)
    if data is None:
        print("[ERR] 找不到 ram.bin")
        return 1
    print(f"帧 {name}")

    head = slice_ram(data, sb1 + O_COUNT, 1 + 4 * MON)
    if head is None:
        print("[ERR] SaveBlock1 越界")
        return 1
    cnt = head[0]
    print(f"partyCount = {cnt}")
    if not (0 < cnt <= 6):
        print("[!] partyCount 异常，可能读错帧")
        return 1

    blob = head[1:]
    print(f"\n{'#':>2} {'lv':>3} {'status':>10} {'+56':>5} {'+58':>5} {'+5A':>5} {'+5C':>5} {'+5E':>5}")
    for i in range(cnt):
        m = blob[i * MON:(i + 1) * MON]
        lvl = m[0x54]
        status = int.from_bytes(m[0x50:0x54], "little")
        v = [int.from_bytes(m[o:o + 2], "little") for o in (0x56, 0x58, 0x5A, 0x5C, 0x5E)]
        print(f"{i:>2} {lvl:>3} 0x{status:08X} " + " ".join(f"{x:>5}" for x in v))

    print("\n判读：hp/maxHp 应满足 0 < hp <= maxHp，且随等级增大。")
    print(f"清零写法：sb1 偏移 = 0x{O_PARTY + 0x56:03X} + 100*i")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
