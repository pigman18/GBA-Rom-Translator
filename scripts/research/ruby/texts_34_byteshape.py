#!/usr/bin/env python3
"""texts_34: 用「字节分布」区分真文本池与压缩/二进制数据（最客观的判据）。

观察（texts_33 转储）：
  0x1D3B80 处字节形如 2c 02 2e 02 34 0e 2b 1a 3c 27 24 32 ...
  —— 「xx 02」成对高频出现，这是 LZ77/位图数据的典型特征，不是自然日文。
  自然日文台词里 0x02（=「い」）不会以这种规律成对出现。

判据（全部基于字节统计，无语言学假设）：
  B1 单字节值熵：真文本用到的字节值种类多且分布自然；
     压缩数据常出现「低字节规律 + 高位固定」的模式。
  B2 「偶数字节位置 == 同一值」的比例：位图/压缩数据的强特征。
  B3 相邻字节差值 == 固定的比例。
  B4 0x00 密度：真台词几乎不含 0x00（除非空格），数据常含。

对 71 条 fallback + 已知正常样本做对比，找可分界。

用法: python scripts/research/ruby/texts_34_byteshape.py
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
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"


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


def shape(raw: bytes) -> dict:
    body = raw[:-1] if raw and raw[-1] == 0xFF else raw
    n = len(body)
    if n < 4:
        return {"n": n, "even_same": 0.0, "diff_const": 0.0, "zero": 0.0, "ent": 0.0}
    # B2：偶数位 vs 奇数位 各自是否为同一常数值
    ev = body[0::2]
    od = body[1::2]
    ev_same = 1.0 if len(set(ev)) == 1 else (Counter(ev).most_common(1)[0][1] / len(ev))
    od_same = 1.0 if len(set(od)) == 1 else (Counter(od).most_common(1)[0][1] / len(od))
    even_same = max(ev_same, od_same)
    # B3：相邻差值
    d = [body[i + 1] - body[i] for i in range(n - 1)]
    diff_const = Counter(d).most_common(1)[0][1] / len(d) if d else 0.0
    # B4
    zero = body.count(0) / n
    # 熵
    c = Counter(body)
    import math
    ent = -sum((v / n) * math.log2(v / n) for v in c.values())
    return {"n": n, "even_same": even_same, "diff_const": diff_const,
            "zero": zero, "ent": ent}


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))

    normal = [e for e in d["entries"]
              if e.get("module") == "剧情" and "fallback" not in e]
    fb = [e for e in d["entries"]
          if e.get("module") == "剧情" and "fallback" in e]

    def report(els, label, limit=None):
        vals = []
        for e in els:
            try:
                raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
            except ValueError:
                continue
            s = shape(raw)
            s["_e"] = e
            vals.append(s)
        print(f"\n=== {label}  n={len(vals)}")
        for key in ("even_same", "diff_const", "ent", "zero"):
            xs = sorted(v[key] for v in vals)
            if not xs:
                continue
            print(f"    {key:<11} min={xs[0]:.3f} p25={xs[len(xs)//4]:.3f} "
                  f"med={xs[len(xs)//2]:.3f} p75={xs[3*len(xs)//4]:.3f} max={xs[-1]:.3f}")
        return vals

    report(normal[:2000], "正常剧情（抽样 2000）")
    v = report(fb, "fallback 71 条")

    print()
    print("=" * 112)
    print("fallback 按 even_same 排序（高位=偶数位高度一致=数据特征）")
    print("=" * 112)
    v.sort(key=lambda x: -x["even_same"])
    for s in v[:20]:
        e = s["_e"]
        print(f"  0x{to_int(e.get('address')):08X} even_same={s['even_same']:.2f} "
              f"diff={s['diff_const']:.2f} ent={s['ent']:.2f}  "
              f"{(e.get('original') or '')[:44]!r}")
    print()
    print("  —— 低端（更像正常文本）——")
    for s in v[-10:]:
        e = s["_e"]
        print(f"  0x{to_int(e.get('address')):08X} even_same={s['even_same']:.2f} "
              f"diff={s['diff_const']:.2f} ent={s['ent']:.2f}  "
              f"{(e.get('original') or '')[:44]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
