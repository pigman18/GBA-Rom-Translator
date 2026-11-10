#!/usr/bin/env python3
"""Phase 0: lock FireRed F7 compose H1 vs H2 from existing ewram dumps (no numpy)."""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "_probe" / "ewram"
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
BASE = 0x08000000
DOC = ROOT / "docs" / "research" / "FIRERED_COMPOSE_LOCK.md"


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def entropy(blob: bytes) -> float:
    if not blob:
        return 0.0
    c = Counter(blob)
    n = len(blob)
    import math

    return -sum((x / n) * math.log2(x / n) for x in c.values())


def like_jp_text(blob: bytes) -> bool:
    """Gen3 JP PCS-ish: most bytes < 0xF0, ends before we call this."""
    if not blob:
        return False
    ok = sum(1 for b in blob if b <= 0xDF or b in (0xFA, 0xFB, 0xFC, 0xFD, 0xFE))
    return ok / len(blob) >= 0.7


def analyze_table(tag: str, tbl: bytes, zh: bytes, ja: bytes) -> dict:
    n = min(len(zh), len(ja))
    vals = [u32(tbl, i * 4) for i in range(len(tbl) // 4)]
    rom = ew = zero = other = 0
    samples = []
    ff_ok = 0
    checked = 0
    lens = []
    for i, v in enumerate(vals):
        if BASE <= v < BASE + n:
            rom += 1
            checked += 1
            off = v - BASE
            # prefer ZH payload (hanization may relocate strings)
            e = zh.find(b"\xff", off, off + 80)
            src = zh
            if e < 0:
                e = ja.find(b"\xff", off, off + 80)
                src = ja
            if e > 0:
                content = src[off:e]
                ff_ok += 1
                lens.append(len(content))
                if len(samples) < 12:
                    samples.append(
                        {
                            "i": i,
                            "ptr": v,
                            "L": len(content),
                            "ent": round(entropy(content), 2),
                            "jp_like": like_jp_text(content),
                            "hex": content[:32].hex(" "),
                        }
                    )
        elif 0x02000000 <= v < 0x03000000:
            ew += 1
        elif v == 0:
            zero += 1
        else:
            other += 1
    return {
        "tag": tag,
        "rom": rom,
        "ew": ew,
        "zero": zero,
        "other": other,
        "ff_ok": ff_ok,
        "checked": checked,
        "ff_pct": (100.0 * ff_ok / checked) if checked else 0.0,
        "lens": lens,
        "samples": samples,
        "first16": vals[:16],
    }


def find_lo_consumption(zh: bytes) -> list[str]:
    """Static notes around known transcoder; search for F7-related patterns."""
    notes = []
    # literal TABLE base used by transcoder
    for lit in (0x081DB6D8, 0x081DB85C):
        off = lit - BASE
        if 0 <= off + 4 <= len(zh):
            notes.append(f"literal @{lit:08X} = 0x{u32(zh, off):08X}")
    # Disasm already documented: F7 branch skips F7+hi only (adds #1 twice);
    # lo remains for downstream. Search ROM for cmp #0xF7 near width fn.
    notes.append(
        "Known from FIRERED_RENDER_ENCODING: transcoder F7 branch consumes "
        "F7+hi only (TABLE[hi] expand); lo not consumed there (R-2)."
    )
    return notes


def sample_f7_in_rom(zh: bytes, limit: int = 20) -> list[dict]:
    """Collect F7 hi lo triples from main text band and show TABLE[hi] if dump known."""
    # main text area from encoding doc ~0x6D0000
    start, end = 0x6D0000, min(len(zh), 0x6D0000 + 0x80000)
    out = []
    i = start
    while i + 3 <= end and len(out) < limit:
        if zh[i] == 0xF7:
            hi, lo = zh[i + 1], zh[i + 2]
            out.append({"off": i, "hi": hi, "lo": lo, "trip": zh[i : i + 3].hex(" ")})
            i += 3
        else:
            i += 1
    return out


def main() -> int:
    zh = ROM_ZH.read_bytes()
    ja = ROM_JA.read_bytes()
    dumps = sorted(OUT.glob("d*.f7table.bin"))
    if not dumps:
        print("No d*.f7table.bin — run 51_dump_ewram.py first")
        return 1

    results = []
    for f in dumps:
        results.append(analyze_table(f.stem, f.read_bytes(), zh, ja))

    # Prefer dump with most ROM pointers
    best = max(results, key=lambda r: (r["rom"], r["ff_ok"]))
    print("=" * 72)
    print(f"best dump: {best['tag']}  rom={best['rom']} zero={best['zero']} "
          f"ff_ok={best['ff_ok']}/{best['checked']} ({best['ff_pct']:.0f}%)")
    print("first16:", [f"{v:08X}" for v in best["first16"]])
    for s in best["samples"]:
        print(f"  [{s['i']:3}] ptr=0x{s['ptr']:08X} L={s['L']} ent={s['ent']} "
              f"jp_like={s['jp_like']}  {s['hex']}")

    # H1 verdict
    h1 = (
        best["rom"] >= 8
        and best["ff_pct"] >= 70.0
        and sum(1 for s in best["samples"] if s["jp_like"]) >= max(1, len(best["samples"]) // 2)
    )
    # empty table at fixed addr is a known prior failure mode
    empty = best["rom"] == 0 and best["zero"] == len(best["first16"]) * 16 or (
        best["zero"] > 200 and best["rom"] < 4
    )

    print("\nH1 compose:", "PASS" if h1 else "FAIL")
    print("empty-table suspicion:", empty)

    # Also scan full EWRAM for pointer runs if table empty
    ew_path = OUT / f"{best['tag'].replace('.f7table','')}.ewram.bin"
    # d1.f7table -> d1.ewram
    tag_base = best["tag"].split(".")[0] if "." in best["tag"] else best["tag"]
    # stem is d1.f7table -> actually Path stem of d1.f7table.bin is d1.f7table
    stem = dumps[0].name.split(".")[0]  # d1
    # re-pick matching ewram for best
    for r in results:
        st = r["tag"].split(".")[0]
        if r is best or r["tag"] == best["tag"]:
            stem = best["tag"].split(".")[0]
            break
    ew_file = OUT / f"{stem}.ewram.bin"
    ew_runs = []
    if ew_file.exists():
        ew = ew_file.read_bytes()
        m = len(ew) // 4 * 4
        run_start = None
        run_len = 0
        for i in range(0, m, 4):
            v = u32(ew, i)
            is_rom = BASE <= v < BASE + min(len(zh), len(ja))
            if is_rom:
                if run_start is None:
                    run_start = i
                    run_len = 1
                else:
                    run_len += 1
            else:
                if run_start is not None and run_len >= 8:
                    ew_runs.append((0x02000000 + run_start, run_len))
                run_start = None
                run_len = 0
        if run_start is not None and run_len >= 8:
            ew_runs.append((0x02000000 + run_start, run_len))
        ew_runs.sort(key=lambda x: -x[1])
        print(f"\nEWRAM ROM-pointer runs (>=8): {len(ew_runs)}; top:")
        for addr, cnt in ew_runs[:8]:
            print(f"  0x{addr:08X} x{cnt}")

    triples = sample_f7_in_rom(zh, 15)
    print("\nF7 samples in ROM text band:")
    for t in triples[:10]:
        print(f"  @{t['off']:06X} {t['trip']} hi={t['hi']:02X} lo={t['lo']:02X}")

    lo_notes = find_lo_consumption(zh)

    # If TABLE[hi] works, try expand first few hi values from best table
    expands = []
    if best["rom"]:
        for hi in range(min(16, len(best["first16"]))):
            v = best["first16"][hi]
            if not (BASE <= v < BASE + len(zh)):
                continue
            off = v - BASE
            e = zh.find(b"\xff", off, off + 64)
            if e < 0:
                e = ja.find(b"\xff", off, off + 64)
                blob = ja[off:e] if e > 0 else b""
            else:
                blob = zh[off:e]
            if blob:
                expands.append({"hi": hi, "ptr": v, "pcs": blob.hex(" "), "L": len(blob)})

    # Write lock doc
    lines = []
    lines.append("# FireRed compose lock (Phase 0)")
    lines.append("")
    lines.append("> ROM: `roms/translated/宝可梦火红日版汉化2.2.gba`")
    lines.append("> Dump: `work/_probe/ewram/d*.f7table.bin` (script `51_dump_ewram.py`)")
    lines.append("> Analyzer: `scripts/research/firered/compose_lock_p0.py`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if h1:
        lines.append("**H1 COMPOSE PASS** — F7 TABLE entries are ROM pointers to "
                     "FF-terminated byte strings that look like Gen3 PCS text. "
                     "Chinese is assembled from vanilla glyph sequences, not a "
                     "standalone Han bitmap font on the print path.")
    elif empty:
        lines.append("**H1 INCONCLUSIVE / TABLE EMPTY at 0x0203F2C0** — dump shows "
                     "mostly zeros at the documented EWRAM slot. See EWRAM pointer "
                     "runs below; do not force AXVJ compose until a live filled "
                     "table is captured on a screen that has already rendered CN text.")
    else:
        lines.append("**H1 FAIL / H2 suspected** — table pointers do not look like "
                     "FF-terminated JP PCS. Stop AXVJ compose port.")
    lines.append("")
    lines.append(f"- Best dump: `{best['tag']}`")
    lines.append(f"- ROM ptrs: {best['rom']}  zero: {best['zero']}  "
                 f"FF-terminated: {best['ff_ok']}/{best['checked']} "
                 f"({best['ff_pct']:.0f}%)")
    if best["lens"]:
        lines.append(f"- String lengths: min={min(best['lens'])} "
                     f"med={sorted(best['lens'])[len(best['lens'])//2]} "
                     f"max={max(best['lens'])}")
    lines.append("")
    lines.append("## Samples (TABLE entries)")
    lines.append("")
    lines.append("| idx | ptr | L | ent | jp_like | head hex |")
    lines.append("|-----|-----|---|-----|---------|----------|")
    for s in best["samples"]:
        lines.append(
            f"| {s['i']} | `0x{s['ptr']:08X}` | {s['L']} | {s['ent']} | "
            f"{s['jp_like']} | `{s['hex']}` |"
        )
    lines.append("")
    lines.append("## lo consumption (R-2)")
    lines.append("")
    for n in lo_notes:
        lines.append(f"- {n}")
    lines.append("- Working model for AXVJ: `hi` selects page/base string via "
                 "`TABLE[hi]`; `lo` is a sub-index consumed by a second stage "
                 "(must be confirmed on a filled table / second hook). "
                 "Until confirmed, treat full `F7 hi lo` as 3-byte token and "
                 "mirror FireRed transcoder+downstream pair in disasm.")
    lines.append("")
    lines.append("## F7 triples in ROM (text band @0x6D0000)")
    lines.append("")
    for t in triples[:12]:
        lines.append(f"- `0x{t['off']:06X}`: `{t['trip']}` (hi=`{t['hi']:02X}` lo=`{t['lo']:02X}`)")
    lines.append("")
    if expands:
        lines.append("## Expand preview TABLE[hi] → PCS")
        lines.append("")
        for e in expands:
            lines.append(f"- hi=`{e['hi']:02X}` → `0x{e['ptr']:08X}` L={e['L']}: `{e['pcs']}`")
        lines.append("")
    if ew_runs:
        lines.append("## Alternate EWRAM ROM-pointer runs")
        lines.append("")
        for addr, cnt in ew_runs[:10]:
            lines.append(f"- `0x{addr:08X}` × {cnt}")
        lines.append("")
    lines.append("## Gate for Phase 1+")
    lines.append("")
    if h1:
        lines.append("Proceed to AXVJ compose codec + dictionary export.")
    else:
        lines.append("**Do not** change AXVJ inject/hooks for compose yet. "
                     "Re-dump after navigating to a CN text screen, or locate "
                     "the real filled TABLE run in EWRAM and re-run this script.")
    lines.append("")

    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {DOC}")
    return 0 if h1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
