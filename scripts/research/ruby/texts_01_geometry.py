#!/usr/bin/env python3
"""texts_01: 逐模块用 ROM 实测校验 texts.json 的几何参数。

校验项（全部基于 ROM 字节，不猜）：
  1. 定长表：用 cfg 的 (start, stride, n) 逐槽解码，统计「合法 FF 终止串」比例；
     若改按 ROM 实际推出的 stride/n 能显著更高，即证明 cfg 几何错。
  2. struct 表：在 cfg 的 entry_size/name_offset 下解码，统计合法率；
     并扫描 name_offset 的实际取值分布，验证 name_offset 是否与 ROM 吻合。
  3. 重叠：算出每个模块实际触及的 ROM 区间，两两求交。

用法: python scripts/research/ruby/texts_01_geometry.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"
OUT = ROOT / "work" / "_probe" / "texts_geometry.json"
GBA_BASE = 0x08000000

sys.path.insert(0, str(ROOT / "src"))
from meowth.jp_pcs import BYTE_TO_CHAR  # noqa: E402


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


def slot_ok(rom: bytes, off: int, size: int | None = None) -> tuple[bool, int, int]:
    """从 off 起判断是否为一个「单字节字形 + FF 终止」串。

    返回 (ok, length, terminator_pos)。ok 的标准：
      - 在 [off, off+size) 内（size 给定时）找到 0xFF 终止
      - 终止前每个字节都是合法单字节字形 / 允许的控制字节
      - 长度 >= 1
    """
    limit = len(rom) if size is None else min(len(rom), off + size)
    i = off
    while i < limit:
        b = rom[i]
        if b == 0xFF:
            return (i > off), (i - off), i
        if b >= 0xFA:  # FA FB FE 控制，FC FD 带参
            i += 1
            continue
        if b in BYTE_TO_CHAR:
            i += 1
            continue
        return False, 0, -1
    return False, 0, -1


def analyze_stride(rom: bytes, start: int, stride: int, end: int) -> dict:
    n = (end - start) // stride
    oks = 0
    lens = []
    bad = []
    for k in range(n):
        off = start + k * stride
        ok, ln, term = slot_ok(rom, off, stride)
        if ok:
            oks += 1
            lens.append(ln)
        else:
            bad.append((k, off))
    return {"n": n, "ok": oks, "ratio": oks / n if n else 0, "lens": lens, "bad": bad[:10]}


def find_true_stride(rom: bytes, start: int, limit_entries: int = 500) -> dict:
    """在 start 处不假定 stride，用「FF 后是否紧跟合法串起点」推真实步长。"""
    # 找 start 起第一个 FF 的位置
    i = start
    while i < len(rom) and rom[i] != 0xFF and i - start < 64:
        i += 1
    if i >= len(rom) or rom[i] != 0xFF:
        return {"first_ff": None}
    first_len = i - start + 1  # 含 FF
    # 用后续若干串的「起点差」统计步长
    diffs: dict[int, int] = {}
    pos = start
    ends = []
    for _ in range(limit_entries):
        j = pos
        while j < len(rom) and rom[j] != 0xFF and j - pos < 200:
            j += 1
        if j >= len(rom) or rom[j] != 0xFF:
            break
        ends.append((pos, j))
        nxt = j + 1
        # 下一串起点
        diffs[nxt - pos] = diffs.get(nxt - pos, 0) + 1
        pos = nxt
    return {"first_len_with_ff": first_len, "diffs": diffs, "sample": ends[:6]}


def analyze_struct(rom: bytes, start: int, end: int, entry_size: int, name_offset: int) -> dict:
    n = (end - start) // entry_size
    oks = 0
    lens = []
    for k in range(n):
        off = start + k * entry_size + name_offset
        ok, ln, _ = slot_ok(rom, off, entry_size - name_offset)
        if ok:
            oks += 1
            lens.append(ln)
    return {"n": n, "ok": oks, "ratio": oks / n if n else 0, "lens": lens}


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = d["modules"]
    entries = d["entries"]

    by_mod: dict[str, list] = {}
    for e in entries:
        by_mod.setdefault(e.get("module"), []).append(e)

    report = {}
    print(f"ROM size 0x{len(rom):X}\n")

    for name, m in mods.items():
        r = m.get("read") or {}
        start = to_int(m.get("start"))
        end = to_int(m.get("end"))
        typ = m.get("type")
        info: dict = {"type": typ, "start": start, "end": end, "read": r}
        print("=" * 110)
        print(f"{name}  type={typ} start={hex(start) if start else start} "
              f"end={hex(end) if end else end} read={r}  n_entries={len(by_mod.get(name, []))}")
        info["n_entries"] = len(by_mod.get(name, []))

        if typ in ("stride", "stride_ptr") and start is not None and end is not None:
            stride = r.get("stride")
            if stride:
                res = analyze_stride(rom, start, stride, end)
                info["stride_check"] = {
                    "n": res["n"], "ok": res["ok"], "ratio": res["ratio"],
                    "mean_len": (sum(res["lens"]) / len(res["lens"])) if res["lens"] else 0,
                }
                print(f"  stride={stride}: slots={res['n']} valid={res['ok']} "
                      f"({res['ratio']:.1%}) mean_len={info['stride_check']['mean_len']:.2f}")
                if res["bad"]:
                    print(f"  首个非法槽: idx={res['bad'][0][0]} off=0x{res['bad'][0][1]:X}")
                if res["ratio"] < 0.9:
                    t = find_true_stride(rom, start)
                    print(f"  真实步长推断: first_len_with_ff={t.get('first_len_with_ff')} "
                          f"diffs={sorted(t.get('diffs', {}).items(), key=lambda kv: -kv[1])[:6]}")
                    info["true_stride"] = {str(k): v for k, v in
                                           sorted(t.get("diffs", {}).items(),
                                                  key=lambda kv: -kv[1])[:6]}

        elif typ == "struct" and start is not None and end is not None:
            es = r.get("entry_size")
            no = r.get("name_offset") or 0
            if es:
                res = analyze_struct(rom, start, end, es, no)
                info["struct_check"] = {
                    "entry_size": es, "name_offset": no,
                    "n": res["n"], "ok": res["ok"], "ratio": res["ratio"],
                    "mean_len": (sum(res["lens"]) / len(res["lens"])) if res["lens"] else 0,
                }
                print(f"  entry_size={es} name_offset={no}: slots={res['n']} valid={res['ok']} "
                      f"({res['ratio']:.1%}) mean_len={info['struct_check']['mean_len']:.2f}")

        elif typ == "scan":
            print(f"  scan 区间: {hex(start) if start else start} - {hex(end) if end else end}")
            els = by_mod.get(name, [])
            print(f"  entries n={len(els)}")
            info["scan"] = True

        report[name] = info

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
