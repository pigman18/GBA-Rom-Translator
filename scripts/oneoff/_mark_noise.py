#!/usr/bin/env python3
"""给 texts.json 里的「非文本数据」条目打 noise 标记（可逆，不删条目）。

背景：0x1D4xxx 一带是「u16 递增序列 + FF FF」的坐标/路径数据，
扫描器把 FF FF 当串终止符，切出一堆解码后是乱码的「文本」：

    37 14 cd 1c fa 26 36 2f 60 39 36 40 | ff ff

判据（只用 ROM 结构，不用正则猜语义）：

* **双 FF**：串的终止符后面紧跟另一个 FF。正常文本的 FF 后面是命令字节
  或下一条文本的开头，不会连写两个。实测命中率：补漏剧情 59%、
  剧情 0.6%（对照组「有译文」的误报率也是 0.6%）。

只处理**缺译文**的条目：已有译文的都是真文本，不动。

标记写进条目字段 ``"noise": true``，plan 会把它归到 skip.reason="noise"，
既不算「缺译文」也不写入 ROM。想回滚直接删这个字段即可。

用法::

    PYTHONPATH=src python scripts/oneoff/_mark_noise.py            # 只报告
    PYTHONPATH=src python scripts/oneoff/_mark_noise.py --apply    # 落盘
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GID = "POKEMON_RUBY_AXVJ00"
ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / GID / "translate" / "texts.json"
CACHE = ROOT / "configs" / GID / "translate" / "texts_translated.json"
ROM = ROOT / "roms" / "origin" / f"{GID}.gba"
SCOPE = {"剧情", "补漏剧情"}


def rom_off(addr: str) -> int | None:
    try:
        v = int(addr, 16)
    except (TypeError, ValueError):
        return None
    return v - 0x08000000 if v >= 0x08000000 else v


def main() -> int:
    apply = "--apply" in sys.argv
    rom = ROM.read_bytes()
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    cache = {
        x.get("original"): (x.get("translated") or "")
        for x in json.loads(CACHE.read_text(encoding="utf-8"))
    }
    hit = []
    for e in texts.get("entries") or []:
        if e.get("module") not in SCOPE:
            continue
        if (cache.get(e.get("original")) or "").strip():
            continue  # 有译文 = 真文本
        if e.get("noise"):
            continue
        off = rom_off(e.get("address") or "")
        if off is None:
            continue
        end = rom.find(b"\xff", off, off + 600)
        if end < 0:
            continue
        if end + 1 < len(rom) and rom[end + 1] == 0xFF:
            hit.append(e)

    print(f"命中 {len(hit)} 条（双 FF 判据，仅缺译文的 剧情/补漏剧情）")
    for e in hit[:8]:
        print(f"  {e.get('address')} {(e.get('original') or '')[:40]!r}")
    if not apply:
        print("\n（未落盘；加 --apply 写入 noise: true）")
        return 0

    backup = TEXTS.with_suffix(".json.bak_noise")
    backup.write_text(TEXTS.read_text(encoding="utf-8"), encoding="utf-8")
    for e in hit:
        e["noise"] = True
    TEXTS.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写入 {len(hit)} 条；备份 {backup.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
