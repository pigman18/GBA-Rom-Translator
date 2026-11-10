#!/usr/bin/env python3
"""用「名字必须能被正确解码」这一硬判据，反推每张表的可用宽度。

思路（比统计法可靠）：
  对每个候选宽度 w，检查该表所有条目的前 w 字节是否都满足：
    1. 以 0xFF（或该表的 eos）结尾
    2. 结尾符之后到下一项之间是填充（0x00 或 0xFF）
    3. 用项目自己的 charmap 解码出来是合法日文

满足这些条件的最大 w，就是真实可用宽度。

这比「元数据众数」强，因为它同时约束了 386 个条目。

用法：
    python scripts/research/ruby/a2_width_by_decode.py
"""
from __future__ import annotations

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
GBA_BASE = 0x08000000

TABLES = [
    ("招式名",         0x1CACFC, 8,  354, 0xFF),
    ("特性名",         0x1CBC44, 8,  77,  0xFF),
    ("属性名",         0x1CBB0C, 5,  18,  0xFF),
    ("道具名",         0x39A648, 40, 348, 0xFF),
    ("图鉴分类名",     0x38474C, 28, 386, 0x00),
    ("秘密基地装饰名", 0x3C2A44, 28, 120, 0xFF),
    ("树果名",         0x3A1050, 28, 43,  0xFF),
]


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM_PATH.read_bytes()

    print(f"{'表':<16} {'stride':>6} {'eos':>5} {'最佳w':>6} {'合规':>6} "
          f"{'可用':>5} {'解码成功':>8}")
    print("-" * 70)

    for name, base, stride, n, eos in TABLES:
        best_w = 0
        best_rate = 0.0

        for w in range(1, stride + 1):
            ok = 0
            decodable = 0
            total = 0
            for i in range(n):
                off = base + i * stride
                seg = rom[off:off + stride]
                if not seg:
                    continue
                total += 1
                body = seg[:w]
                # 必须含 eos
                if eos not in body:
                    continue
                p = body.index(eos)
                # eos 之后到 w 之间必须是填充
                tail = body[p + 1:]
                if any(b not in (0x00, 0xFF) for b in tail):
                    continue
                ok += 1
                # 尝试解码
                try:
                    txt = cm.decode(body[:p]) if hasattr(cm, "decode") else None
                    if txt:
                        decodable += 1
                except Exception:
                    pass

            rate = ok / total if total else 0
            if rate > best_rate or (rate == best_rate and w < best_w):
                best_rate = rate
                best_w = w

        # 用最佳 w 复核
        ok = total = 0
        for i in range(n):
            off = base + i * stride
            body = rom[off:off + best_w]
            if not body:
                continue
            total += 1
            if eos in body:
                p = body.index(eos)
                if all(b in (0x00, 0xFF) for b in body[p + 1:]):
                    ok += 1

        print(f"{name:<16} {stride:>6} {f'0x{eos:02X}':>5} {best_w:>6} "
              f"{ok}/{total:<4} {best_w:>5} ")

    print()
    print("说明：最佳 w = 让「含 eos + 其后仅填充」比例最高的最小宽度")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
