"""找出「同一日文原文对应多个 ROM 地址，但产物里只替换了部分」的漏翻。

【为什么需要】
实测发现 UI 按钮「もどる」（返回）在 texts.json 里有 3 个地址：
  0x0839DE7F / 0x083DE362 / 0x083E9AC7
译文表按「日文原文」做键，只有 1 条记录（这是合理的，避免重复翻译），
但**写入产物时应对 3 个地址都替换**。实际产物里 3 处都还是日文 `23 45 29`。

本脚本把「同一原文的多地址」全部检查一遍，看产物里哪些地址没被替换。

用法：
    python scripts/verify/find_multisite_miss.py --limit 20
    python scripts/verify/find_multisite_miss.py --only もどる
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
BASE = 0x08000000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--only", default=None, help="只查该日文原文")
    a = ap.parse_args()

    entries = json.loads(TEXTS.read_text("utf-8"))["entries"]
    rom = ROM.read_bytes()

    # 按日文原文分组
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        orig = (e.get("original") or "").strip()
        if not orig or not e.get("address"):
            continue
        groups[orig].append(e)

    multi = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"多地址原文: {len(multi)} 组")

    miss_total = 0
    miss_groups = []
    for orig, es in multi.items():
        if a.only and a.only not in orig:
            continue
        unchanged = []
        for e in es:
            addr = int(e["address"], 16)
            hx = e.get("original_hex")
            if not hx:
                continue
            pat = bytes.fromhex(hx.replace(" ", ""))
            off = addr - BASE
            if off < 0 or off + len(pat) > len(rom):
                continue
            if rom[off:off + len(pat)] == pat:
                unchanged.append(addr)
        if unchanged:
            miss_total += len(unchanged)
            miss_groups.append((orig, len(es), unchanged))

    miss_groups.sort(key=lambda x: -len(x[2]))
    print(f"存在未替换地址的组: {len(miss_groups)}，共 {miss_total} 处未替换")
    print()
    for orig, n, un in miss_groups[:a.limit]:
        print(f"{orig!r}  (共 {n} 个地址, {len(un)} 个未替换)")
        for u in un[:6]:
            print(f"    0x{u:08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
