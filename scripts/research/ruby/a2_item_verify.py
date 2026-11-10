#!/usr/bin/env python3
"""道具名定案：base=0x39A648, stride=40, name@+0x28（反汇编确认）。

反汇编证据（0x0A5388..0x0A5390）：
    0x0A5388: lsls    r0, r1, #2
    0x0A538A: adds    r0, r0, r1
    0x0A538C: lsls    r0, r0, #3      ← (idx*4 + idx) * 8 = idx * 40
    0x0A538E: ldr     r1, [pc, #8]    ← 基址字面量
    0x0A5390: adds    r0, r0, r1      ← base + idx*40

字面量值 = 0x0839A648 → base = 0x39A648

字段验证：
  0x39A648 + 0*40 + 0x28 = 0x39A670  → 6f 5d 60 ae 9a ae 79 FF  'マスターボール'(7B)
  0x39A648 + 1*40 + 0x28 = 0x39A698  → 6a 52 9b ae 9a ae 79 FF  'ハイパーボール'

**name_offset = 0x28，可用字段宽 = 40 - 0x28 = 16 字节**

中文 F9 00 hi lo ×2 + FF = 9 字节 ✓ 塞得下
中文 ×3 + FF = 13 字节 ✓ 塞得下
中文 ×4 + FF = 17 字节 ✗ 超 16

用法：
    python scripts/research/ruby/a2_item_verify.py
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
sys.path.insert(0, str(ROOT / "src"))

ROM_PATH = ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
BUILD = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"
GBA_BASE = 0x08000000

BASE = 0x39A648
STRIDE = 40
NAME_OFF = 0x28
CAP = STRIDE - NAME_OFF   # 16
N = 348


def main() -> int:
    rom = ROM_PATH.read_bytes()
    d = json.loads(BUILD.read_text(encoding="utf-8"))

    print(f"=== 几何：base=0x{BASE:06X} stride={STRIDE} name@+0x{NAME_OFF:X} "
          f"字段宽={CAP}B ===")
    for i in range(4):
        off = BASE + i * STRIDE + NAME_OFF
        seg = rom[off:off + CAP]
        ff = seg.find(b"\xFF")
        print(f"  item{i} 0x{off:06X}: {seg.hex(' ')}  FF@{ff}")

    # 用 build.json 的条目地址核对
    items = {}
    for e in d.get("entries") or []:
        if e.get("module") != "道具名":
            continue
        try:
            addr = int(str(e.get("address") or "").replace("0x", ""), 16)
        except ValueError:
            continue
        if addr >= GBA_BASE:
            addr -= GBA_BASE
        items[addr] = e

    print()
    print(f"=== build.json 道具名条目 {len(items)} 条 ===")
    ok = 0
    for i in range(6):
        off = BASE + i * STRIDE + NAME_OFF
        e = items.get(off)
        print(f"  item{i} 0x{off:06X}: "
              + (f"✅ {e.get('original')!r} → {e.get('translated')!r}" if e else "❌ 无条目"))
        if e:
            ok += 1
    print(f"  命中 {ok}/6")

    # 全量校验
    print()
    hit = sum(1 for i in range(N) if (BASE + i * STRIDE + NAME_OFF) in items)
    print(f"=== 全量：{N} 项中命中 {hit} 条 ({hit/N:.1%}) ===")

    # 译文能否塞进 16B
    print()
    from meowth.charmap import Charmap
    from meowth.config_loader import get_charmap_path
    from meowth.table_expand import encode_body

    cm = Charmap(charmap_path=get_charmap_path("POKEMON_RUBY_AXVJ00"),
                 target_lang="zh-Hans")
    fits = over = 0
    over_samples = []
    for i in range(N):
        off = BASE + i * STRIDE + NAME_OFF
        e = items.get(off)
        if not e:
            continue
        text = e.get("translated") or ""
        if not text:
            continue
        body = encode_body(cm, text)
        if len(body) <= CAP:
            fits += 1
        else:
            over += 1
            if len(over_samples) < 5:
                over_samples.append((i, text, len(body)))

    print(f"=== 译文能否保持 stride=40（字段宽 {CAP}B）===")
    print(f"  塞得下: {fits}")
    print(f"  超长:   {over}")
    for i, t, n in over_samples:
        print(f"    item{i} {t!r} = {n}B")
    print()
    if over == 0:
        print("✅ 全部塞得下 → 可 expand_fixed，只改基址字面量")
    else:
        print(f"⚠️ {over} 条超长 → 这些需要 expand_varlen 或缩句")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
