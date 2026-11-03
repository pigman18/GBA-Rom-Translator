#!/usr/bin/env python3
"""在运行时 RAM 里搜「角色真实位置」到底存在哪。

── 为什么需要 ──────────────────────────────────────────────────────────
2026-11-03 实测：poke SaveBlock1.pos（`sb1+0x00/0x02`）后
  · [POS] 日志立刻变、值也保持（(23,17)→(5,12)→(30,12)）
  · 但**画面/角色 sprite 几乎没动**
⇒ 渲染读的不是 SaveBlock1.pos。必须找出真正驱动画面的那份坐标。

做法：拿同一场景里**两个已知坐标的帧**（例如出门后的 (23,17) 与
      poke 后的 (5,12)），在各自 ram.bin 里搜索 16 位小端字节对，
      取**两帧同时存在、且值各自匹配**的地址 —— 那就是候选。

用法：
  python scripts/find_real_pos.py <run_dir> <frameA> <xA> <yA> <frameB> <xB> <yB>
  例：
  python scripts/find_real_pos.py work/.../run pw_out 23 17 pw_after_step 5 12
"""
from __future__ import annotations

import sys
from pathlib import Path

EWRAM_BASE, EWRAM_LEN = 0x02000000, 0x40000
IWRAM_BASE = 0x03000000


def load(run_dir: Path, key: str):
    side = run_dir / "translated"
    if not side.is_dir():
        side = run_dir / "origin"
    num = None
    label = "?"
    csv = side / "index.csv"
    if csv.is_file():
        for line in csv.read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split(",")
            if len(p) >= 4 and (p[2] == key or p[0] == key):
                num, label = p[3].replace(".png", ""), p[2]
                break
    if num is None:
        num = key.zfill(3)
    f = side / f"{num}.ram.bin"
    return (f.read_bytes() if f.is_file() else None), label


def addr_of(off: int) -> int:
    return (IWRAM_BASE + off - EWRAM_LEN) if off >= EWRAM_LEN else (EWRAM_BASE + off)


def hits(data: bytes, x: int, y: int, limit=400):
    """找 4 字节模式 <x:u16><y:u16>（也接受 s16 负值写法）。"""
    pat = x.to_bytes(2, "little", signed=True) + y.to_bytes(2, "little", signed=True)
    out, i = [], data.find(pat, 0)
    while i >= 0 and len(out) < limit:
        out.append(i)
        i = data.find(pat, i + 1)
    return out


def main() -> int:
    if len(sys.argv) < 8:
        print(__doc__)
        return 2
    run = Path(sys.argv[1])
    fa, xa, ya = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    fb, xb, yb = sys.argv[5], int(sys.argv[6]), int(sys.argv[7])

    da, la = load(run, fa)
    db, lb = load(run, fb)
    if da is None or db is None:
        print("[ERR] 缺 ram.bin")
        return 1
    print(f"A = {la} ({xa},{ya})   B = {lb} ({xb},{yb})")

    ha = set(hits(da, xa, ya))
    hb = set(hits(db, xb, yb))
    common = sorted(ha & hb)
    print(f"A 命中 {len(ha)} 处，B 命中 {len(hb)} 处，**两帧都命中** {len(common)} 处")

    if not common:
        print("\n[!] 没有共同地址 ⇒ 这两帧之间坐标可能没真正写进去，"
              "或游戏把坐标存成了别的形式（像素 = 格*16+8）")
        # 再试像素形式
        px, py = xa * 16 + 8, ya * 16 + 8
        qx, qy = xb * 16 + 8, yb * 16 + 8
        pa, pb = set(hits(da, px, py)), set(hits(db, qx, qy))
        cc = sorted(pa & pb)
        print(f"改试像素坐标：A=({px},{py}) B=({qx},{qy}) ⇒ 共同 {len(cc)} 处")
        for o in cc[:20]:
            print(f"  0x{addr_of(o):08X}")
        return 0

    print("\n候选地址（两帧都对得上，且值各自匹配）：")
    for o in common[:40]:
        print(f"  0x{addr_of(o):08X}  (ram 偏移 0x{o:06X})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
