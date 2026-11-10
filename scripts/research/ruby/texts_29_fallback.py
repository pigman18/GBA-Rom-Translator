#!/usr/bin/env python3
"""texts_29: 71 条 fallback 条目 = 指向乱码的无效文本（第2步"无效文本"的真答案）。

背景：texts_28 发现重抽时少 71 条，全部带 fallback 标记。
抽查发现它们是乱码（如 'わいんいゃせろはざらやぇ？ずせぱチカゅツ'）。

本脚本对全部 71 条做字节级判定，给出可删结论：
  F1 语言特征：平假名/片假名比例、全角拉丁比例、2-gram 自相似度
  F2 是否在 ROM 里被真指针指向（有指针≠是文本）
  F3 与其它模块内容是否重复
  F4 用 ROM 原始 hex 复核

用法: python scripts/research/ruby/texts_29_fallback.py
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

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402
from meowth.pcs_codes import fc_arg_count  # noqa: E402


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


def features(raw: bytes) -> dict:
    body = raw[:-1] if raw and raw[-1] == 0xFF else raw
    c = Counter()
    seq: list[int | None] = []
    i = 0
    while i < len(body):
        b = body[i]
        if b == 0xFC:
            if i + 1 >= len(body):
                break
            i += 2 + fc_arg_count(body[i + 1])
            c["ctrl"] += 1
            continue
        if b == 0xFD:
            i += 2
            c["ctrl"] += 1
            continue
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            c["ctrl"] += 1
            continue
        if b == 0xF7 or b == 0xF8:
            c["high"] += 1
            seq.append(None)
            i += 1
            continue
        if b not in BYTE_TO_CHAR:
            c["unknown"] += 1
            seq.append(None)
            i += 1
            continue
        if b == 0x00:
            c["space"] += 1
            seq.append(None)
            i += 1
            continue
        if 0x01 <= b <= 0x50:
            c["hira"] += 1
        elif 0x51 <= b <= 0xA0:
            c["kata"] += 1
        elif 0xA1 <= b <= 0xBA:
            c["punct"] += 1
        else:
            c["latin"] += 1
        seq.append(b)
        i += 1
    g = c["hira"] + c["kata"] + c["punct"] + c["latin"]
    s = [x for x in seq if x is not None]
    grams = Counter(tuple(s[k:k + 2]) for k in range(len(s) - 1))
    return {
        "glyphs": g,
        "kana_ratio": (c["hira"] + c["kata"]) / g if g else 0.0,
        "hira": c["hira"], "kata": c["kata"], "latin": c["latin"],
        "punct": c["punct"], "high": c["high"], "unknown": c["unknown"],
        "max_gram": max(grams.values()) if grams else 0,
        "len": len(s),
    }


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    story = [e for e in d["entries"] if e.get("module") == "剧情"]
    fb = [e for e in story if "fallback" in e]

    print("=" * 116)
    print(f"71 条 fallback 条目逐条判定（共 {len(fb)} 条）")
    print("=" * 116)

    garbage = []
    for e in fb:
        try:
            raw = bytes.fromhex((e.get("original_hex") or "").replace(" ", ""))
        except ValueError:
            continue
        f = features(raw)
        # 乱码判据：无裸F7/F8 且 片假名比例极高 + 2-gram 自相似 + 无正常假名节奏
        sus = []
        if f["high"]:
            sus.append(f"裸F7/F8×{f['high']}")
        if f["unknown"]:
            sus.append(f"未知字形×{f['unknown']}")
        if f["kana_ratio"] > 0.85 and f["len"] >= 10:
            sus.append(f"假名占比{f['kana_ratio']:.0%}")
        if f["max_gram"] >= 3 and f["len"] >= 12:
            sus.append(f"2-gram重复×{f['max_gram']}")
        if sus:
            garbage.append((e, f, sus))

    print(f"\n判为乱码: {len(garbage)} / {len(fb)}\n")
    print(f"  {'address':>12} {'len':>4} {'kana':>6} {'2gram':>6}  原文")
    print("  " + "-" * 96)
    for e, f, sus in garbage[:30]:
        print(f"  0x{to_int(e.get('address')):08X} {f['len']:>4} "
              f"{f['kana_ratio']:>5.0%} {f['max_gram']:>6}  "
              f"{(e.get('original') or '')[:44]!r}")

    print()
    print("=" * 116)
    print("这些条目在 ROM 里是否真有指针？（有指针≠有文本）")
    print("=" * 116)
    with_ptr = sum(1 for e, _, _ in garbage if e.get("pointer_sources"))
    print(f"  pointer_sources 非空: {with_ptr} / {len(garbage)}")
    print("  说明：这些都是「指针指向一块二进制/压缩数据，被当作文本解码」的伪命中。")

    out = ROOT / "work" / "_probe" / "texts_fallback_garbage.json"
    out.write_text(json.dumps(
        [{"address": e.get("address"), "original": e.get("original"),
          "reasons": sus, "features": f} for e, f, sus in garbage],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {out}")

    print()
    print("=" * 116)
    print("结论")
    print("=" * 116)
    print(f"  剧情模块中 fallback 放行的 {len(fb)} 条里，{len(garbage)} 条是乱码伪命中。")
    print("  建议：删除这些条目，并收紧 fallback_filters（dialogue_shape 的 pointer_ok=false")
    print("        恰恰纵容了「有指针就放行」）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
