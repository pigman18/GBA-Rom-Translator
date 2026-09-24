#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 gdb dump 出来的 bin 文件渲染一帧 PNG（复用 gdb_shot 的 Screen）。

用法: render_dump.py <prefix> <out.png>
  其中 <prefix>_vram.bin / _pal.bin / _oam.bin / _io.bin 需存在
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdb_shot import Screen, save_png  # noqa: E402


def main() -> int:
    pre = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else pre.with_suffix(".png")
    vram = Path(str(pre) + "_vram.bin").read_bytes()
    pal = Path(str(pre) + "_pal.bin").read_bytes()
    oam = Path(str(pre) + "_oam.bin").read_bytes()
    io = Path(str(pre) + "_io.bin").read_bytes()
    if len(vram) < 0x18000:
        print(f"警告：VRAM 只有 {len(vram)} 字节")
    s = Screen(vram, pal, oam, io)
    print(f"DISPCNT=0x{s.dispcnt:04X} mode={s.mode} blank={s.blank}")
    for i in range(4):
        c = s.bgcnt[i]
        print(f"  BG{i}: cnt=0x{c:04X} prio={c & 3} "
              f"charBase=0x{((c >> 2) & 3) * 0x4000:05X} "
              f"screenBase=0x{((c >> 8) & 0x1F) * 0x800:05X} "
              f"size={(c >> 14) & 3} {'8bpp' if c & 0x80 else '4bpp'} "
              f"en={(s.dispcnt >> (8 + i)) & 1} "
              f"hofs={s.hoff[i]} vofs={s.voff[i]}")
    px = s.render()
    save_png(px, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
