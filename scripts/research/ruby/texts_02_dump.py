#!/usr/bin/env python3
"""texts_02: 把 ROM 指定区间按 JP PCS 解码打印，用于人工核对表边界。

用法:
  python scripts/research/ruby/texts_02_dump.py --off 0x1CACEC --len 0x60
  python scripts/research/ruby/texts_02_dump.py --slots 0x1CA354 --stride 6 --n 6
  python scripts/research/ruby/texts_02_dump.py --ptr 0x39F798 --stride 4 --n 6
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
GBA_BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def read_until_eos(rom: bytes, off: int, eos: int = 0xFF, limit: int = 256) -> bytes:
    i = off
    while i < len(rom) and i - off < limit:
        if rom[i] == eos:
            return rom[off:i + 1]
        i += 1
    return rom[off:i]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", type=lambda s: int(s, 0))
    ap.add_argument("--len", type=lambda s: int(s, 0), default=0x40)
    ap.add_argument("--slots", type=lambda s: int(s, 0))
    ap.add_argument("--ptr", type=lambda s: int(s, 0))
    ap.add_argument("--stride", type=int, default=0)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--eos", type=lambda s: int(s, 0), default=0xFF)
    a = ap.parse_args()

    rom = ROM_PATH.read_bytes()

    if a.slots is not None:
        stride = a.stride
        for k in range(a.n):
            off = a.slots + k * stride
            raw = read_until_eos(rom, off, a.eos, stride if stride else 256)
            print(f"[{k:>3}] 0x{off:06X}  {raw.hex(' '):<40} {decode_pcs(raw)!r}")
        return 0

    if a.ptr is not None:
        stride = a.stride or 4
        for k in range(a.n):
            off = a.ptr + k * stride
            v = struct.unpack_from("<I", rom, off)[0]
            if not (GBA_BASE <= v < GBA_BASE + len(rom)):
                print(f"[{k:>3}] 0x{off:06X}  ptr=0x{v:08X}  <越界/非指针>")
                continue
            t = v - GBA_BASE
            raw = read_until_eos(rom, t, a.eos)
            print(f"[{k:>3}] 0x{off:06X}  ->0x{t:06X}  {raw.hex(' '):<40} {decode_pcs(raw)!r}")
        return 0

    if a.off is None:
        ap.error("需要 --off / --slots / --ptr 之一")
        return 2

    off = a.off
    chunk = rom[off:off + a.len]
    # 逐 16 字节 hex + 解码
    for i in range(0, len(chunk), 16):
        seg = chunk[i:i + 16]
        print(f"0x{off + i:06X}  {seg.hex(' '):<48} |{decode_pcs(seg)}|")
    print()
    raw = read_until_eos(rom, off, a.eos)
    print(f"从 0x{off:06X} 解码到首个 EOS: {decode_pcs(raw)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
