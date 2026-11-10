#!/usr/bin/env python3
"""texts_03: 用「entries 自我一致性」检查 texts.json 与 ROM 的字节级吻合。

对每个 entry：
  - 把 original_hex 与 ROM[address] 处同样长度比对
  - 解码 original 与 ROM 解码结果比对
  - 检查 address 是否落在该模块声明的 start..end 内
统计每模块的不符条目数并列出样本。这是「配置 vs ROM」最直接的证据。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
GBA_BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import decode_pcs  # noqa: E402


def to_int(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    try:
        return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
    except ValueError:
        return None


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    entries = d["entries"]

    by_mod: dict[str, list] = {}
    for e in entries:
        by_mod.setdefault(e.get("module"), []).append(e)

    print(f"{'module':<22} {'n':>6} {'hex_mismatch':>12} {'decode_mismatch':>16} "
          f"{'out_of_range':>13} {'dup_gid':>8}")
    print("-" * 88)

    detail = {}
    for name, m in mods.items():
        els = by_mod.get(name, [])
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        hex_bad, dec_bad, oor = [], [], []
        ids = Counter(e.get("id") for e in els)
        dup_ids = sum(c - 1 for c in ids.values() if c > 1)
        for e in els:
            addr = to_int(e.get("address"))
            if addr is None:
                continue
            off = addr - GBA_BASE if addr >= GBA_BASE else addr
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            if not raw:
                continue
            if (start is not None and end is not None
                    and not (start <= off <= end)
                    and not (start == 0 and end == 0xFFFFFF)):
                oor.append((addr, e.get("original")))
            actual = rom[off:off + len(raw)]
            if actual != raw:
                hex_bad.append((addr, raw.hex(" "), actual.hex(" "), e.get("original")))
                continue
            if decode_pcs(raw) != (e.get("original") or ""):
                dec_bad.append((addr, decode_pcs(raw), e.get("original")))

        detail[name] = {
            "n": len(els),
            "hex_mismatch": len(hex_bad),
            "decode_mismatch": len(dec_bad),
            "out_of_range": len(oor),
            "dup_ids": dup_ids,
            "samples_hex": hex_bad[:5],
            "samples_oor": oor[:5],
        }
        print(f"{name:<22} {len(els):>6} {len(hex_bad):>12} {len(dec_bad):>16} "
              f"{len(oor):>13} {dup_ids:>8}")
        if hex_bad:
            a, want, got, orig = hex_bad[0]
            print(f"    hex不符样本: 0x{a:08X} cfg={want} rom={got} original={orig!r}")
        if oor:
            a, orig = oor[0]
            print(f"    越界样本: 0x{a:08X} original={orig!r} (模块范围 0x{start:X}..0x{end:X})")

    out = ROOT / "work" / "_probe" / "texts_selfcheck.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
