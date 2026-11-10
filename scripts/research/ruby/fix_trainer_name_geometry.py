#!/usr/bin/env python3
"""修正「训练家个人名」模块几何：真表在 0x1C4CB8，name_offset=0。

反汇编实测（2026-11-04）：
  真表 0x1C4CB8..0x1CA338，693 项 × 32 字节，名字在 +0x00（PCS 串，FF 结尾）。
  texts.json 原声明 0x1C5040 / name_offset=24 是错的：
    - 0x1C5040 那一片是**名字正文区**（不是结构体表头）
    - name_offset=24 处是指向另一结构的指针（0x1C14BC，u16 表），不是名字
  按 name_offset=0 重读 693 项，681 项能解出名字，内容与旧条目完全一致。

本脚本：
  1. 保留旧的 id / translated（按 original 内容匹配）
  2. 把 address / table_index / table_base 更新成正确值
  3. 补上旧几何漏掉的条目

用法：
    python scripts/research/ruby/fix_trainer_name_geometry.py --dry-run
    python scripts/research/ruby/fix_trainer_name_geometry.py --write
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

GAME = "POKEMON_RUBY_AXVJ00"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"

MOD = "训练家个人名"
BASE = 0x1C4CB8        # 文件偏移
STRIDE = 32
COUNT = 693
NAME_OFF = 0
END_OFF = BASE + STRIDE * COUNT - 1


def main() -> int:
    write = "--write" in sys.argv
    from meowth.codec import get_codec

    cd = get_codec(GAME)
    rom = ROM.read_bytes()
    d = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = d["entries"]

    def name_at(off: int) -> str:
        seg = rom[off:off + STRIDE]
        cut = len(seg)
        for j, b in enumerate(seg):
            if b == 0xFF:
                cut = j
                break
        if not cut:
            return ""
        try:
            return cd.decode(seg[:cut])
        except Exception:
            return ""

    print("=" * 76)
    print(f"{MOD} 几何修正  {'（写入）' if write else '（dry-run）'}")
    print("=" * 76)

    old = [e for e in entries if e.get("module") == MOD]
    print(f"旧条目 {len(old)}")

    # 旧条目按内容分组（保留 id / translated）
    pool: dict[str, list[dict]] = defaultdict(list)
    for e in old:
        pool[(e.get("original") or "").strip()].append(e)

    rebuilt: list[dict] = []
    reused = fresh = 0
    for k in range(COUNT):
        off = BASE + k * STRIDE + NAME_OFF
        text = name_at(off)
        if not text:
            continue
        addr = f"0x{off + 0x08000000:08X}"
        cand = pool.get(text.strip())
        if cand:
            e = cand.pop(0)
            reused += 1
        else:
            e = {
                "id": f"axvj_{MOD}_{k:04d}",
                "module": MOD,
                "original": text,
                "translated": "",
                "original_hex": rom[off:off + STRIDE].hex(" "),
            }
            fresh += 1
        e["address"] = addr
        e["byte_length"] = min(len(rom[off:off + STRIDE].split(b"\xff")[0]) + 1, STRIDE)
        e["table_index"] = k
        e["table_base"] = f"0x{BASE + 0x08000000:08X}"
        e["is_fixed_table"] = True
        rebuilt.append(e)

    leftover = [e for v in pool.values() for e in v]
    print(f"重建 {len(rebuilt)} 条  (复用旧的 {reused}, 新建 {fresh})")
    print(f"旧条目未匹配剩余 {len(leftover)}")
    if leftover:
        for e in leftover[:5]:
            print(f"   {(e.get('original') or '')[:30]!r}  {e.get('address')}")

    print()
    print("前 5 条:")
    for e in rebuilt[:5]:
        print(f"   {e['address']}  idx={e['table_index']:<3} {e['original']!r}")

    if not write:
        print()
        print("dry-run 结束。加 --write 执行。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TEXTS.with_suffix(f".json.bak_{stamp}")
    shutil.copy2(TEXTS, bak)
    print(f"\n已备份: {bak.name}")

    # 用 rebuilt 替换该模块全部条目，其余模块原样保留
    rest = [e for e in entries if e.get("module") != MOD]
    d["entries"] = rest + rebuilt
    d["count"] = len(d["entries"])

    # 模块定义同步
    m = d["modules"][MOD]
    m["start"] = f"0x{BASE:06x}"
    m["end"] = f"0x{END_OFF:06x}"
    m["read"] = {"entry_size": STRIDE, "name_offset": NAME_OFF}

    TEXTS.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"已写入: count = {d['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
