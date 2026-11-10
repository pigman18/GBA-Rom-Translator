#!/usr/bin/env python3
"""特性名单表端到端验证：符号执行 → patch → 新表 → 打包。

特性名条件最优：
  - 只有 3 个 ldr 站点，K 全部 = 8（100% 确定）
  - stride 8 → 16（×2，净移位 +1）
  - 名字可用宽度 8 → 16 字节，最长译文 17B？

⚠️ 等等：最长译文 17B > 16B！需要重新算。

原：stride=8, usable=8, 译文最长 17B → 8→16 只有 16B，还是不够。
需要 stride 8 → 32（×4，净移位 +2）。

重新确认：
  stride 8 → 32：可用 32B ≥ 17B ✓
  net 移位 +2

用法：
    python scripts/research/ruby/verify_ability_table.py
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

ROM = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

# 特性名表
BASE = 0x1CBC44
OLD_STRIDE = 8
USABLE = 8          # 名字区可用宽度（100% 合规判据）
N = 77
EOS = 0xFF


def main() -> int:
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body
    from meowth.thumb_symexec import solve_site
    from meowth.table_stride import find_ldrs, thumb_shift

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    rom = ROM.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    # 1. 先算最长译文，决定新 stride
    entries = [e for e in (d.get("entries") or [])
               if e.get("module") == "特性名"
               and e.get("type") == "replace"
               and e.get("phrase_code") is not None]
    print(f"=== 1. 特性名条目 {len(entries)}，算译文长度 ===")
    longest = 0
    for e in entries:
        b = encode_body(cm, e.get("translated") or "")
        longest = max(longest, len(b))
    print(f"  最长译文 {longest}B")

    # 选新 stride：必须 >= 最长译文，且是 8 的 2 的幂倍
    new_stride = None
    delta = 0
    for k in (2, 4, 8):
        cand = OLD_STRIDE * k
        if longest <= cand:
            new_stride = cand
            delta = k.bit_length() - 1
            break
    if new_stride is None:
        print("  ❌ 即使 ×8 也不够")
        return 1
    print(f"  ⇒ 新 stride {OLD_STRIDE} → {new_stride}（×{new_stride//OLD_STRIDE}，"
          f"净移位 +{delta}）")

    # 2. 符号执行求全部站点
    print()
    print("=== 2. 符号执行：求全部 ldr 站点的 K ===")
    ldrs = find_ldrs(rom, BASE)
    patches = []
    for ldr in ldrs:
        r = solve_site(rom, ldr)
        mark = ""
        if r.stride == OLD_STRIDE:
            print(f"  0x{ldr:06X}  K={r.stride}  ✅ 要改")
        else:
            print(f"  0x{ldr:06X}  K={r.stride}  ({r.reason})  ❌ 不改")
            continue

        # 找那条移位指令
        # solve_site 只给 K，需要再定位指令 —— 这里直接从表_stride 拿
    print(f"  合计 {len(ldrs)} 站点")

    # 3. 用 table_stride 生成 patch
    print()
    print("=== 3. 生成 patch（只改 K==8 的站点）===")
    from meowth.table_stride import rewrite_table_stride
    rr = rewrite_table_stride(rom, BASE, OLD_STRIDE, new_stride,
                              require_full=False)
    print(f"  识别站点 {rr.n_sites}/{rr.n_ldrs}")
    for p in rr.patches:
        print(f"    0x{p.offset:06X}: {p.data.hex(' ')}  {p.label}")

    # 4. 建新表
    print()
    print("=== 4. 建新表 ===")
    items = {}
    for e in entries:
        try:
            a = int(str(e.get("address") or "0x0").replace("0x", ""), 16)
        except ValueError:
            continue
        if a >= GBA_BASE:
            a -= GBA_BASE
        items[a] = e

    blob = bytearray()
    meta = OLD_STRIDE - USABLE          # 8 - 8 = 0，无元数据
    name_cap = new_stride - meta
    n_trans = 0
    for i in range(N):
        src = BASE + i * OLD_STRIDE
        e = items.get(src)
        if e and (e.get("translated") or ""):
            body = encode_body(cm, e["translated"])
            n_trans += 1
            if len(body) > name_cap:
                body = body[:name_cap - 1] + bytes([EOS])
        else:
            body = rom[src:src + USABLE]
        blob += body + bytes([EOS]) * (name_cap - len(body))
        blob += bytes(meta)

    print(f"  {n_trans} 项有译文，新表 {len(blob):,} B（{N} × {new_stride}）")

    # 5. 输出
    out = ROOT / "work" / "_probe" / "ability_table_test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "table": "特性名",
        "base": f"0x{BASE:06X}",
        "old_stride": OLD_STRIDE,
        "new_stride": new_stride,
        "n_items": N,
        "n_translated": n_trans,
        "blob_size": len(blob),
        "patches": [{"offset": f"0x{p.offset:06X}",
                     "data": p.data.hex(" "),
                     "label": p.label} for p in rr.patches],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
