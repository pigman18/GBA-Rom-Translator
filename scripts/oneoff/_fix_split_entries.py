#!/usr/bin/env python3
"""把「切在串中间」的战斗模板条目迁到真正的串首。

扫描器遇到 ``FD xx xx 00 FD xx xx`` 这种连续变量控制码时，会把后面的
``00``（空格）当成「上一条串的结尾」，于是新串从控制码之后开始算：

    ROM  0x3DB87E:  FD 1D 14 00 FD 1E 14 19 ...   （真实串首）
    texts.json    :  0x3DB884  との\\nしょうぶに かった！   ← 偏了 6 字节

偏移后的地址没有任何指针指向它（指针都指向串首），所以永远写不进去。
这里把 address / original / translated 一起对齐到串首。

译文的控制码必须原样保留（``\\1D``/``\\1E``/``\\19``/``\\1A`` 是名字占位符，
运行时由游戏替换），只翻日文部分。

用法::

    PYTHONPATH=src python scripts/oneoff/_fix_split_entries.py --apply
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GID = "POKEMON_RUBY_AXVJ00"
ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / GID / "translate" / "texts.json"
CACHE = ROOT / "configs" / GID / "translate" / "texts_translated.json"

# 旧 address（偏移后）→ (串首 address, 完整原文, 译文)
FIX: dict[str, tuple[str, str, str]] = {
    "0x083DA740": (
        "0x083DA736",
        "\\10の \\17で\n\\0Eは どくをあびた！",
        "\\10的 \\17\n\\0E中毒了！",
    ),
    "0x083DB884": (
        "0x083DB87E",
        "\\1Dと \\1Eとの\nしょうぶに かった！",
        "\\1D与 \\1E的对战\n胜利了！",
    ),
    "0x083DB8A8": (
        "0x083DB892",
        "\\1Dとの\nしょうぶに まけた！",
        "\\1D的对战\n失败了！",
    ),
    "0x083DB8CE": (
        "0x083DB8B6",
        "\\1Dとの\nしょうぶに ひきわけた！",
        "\\1D的对战\n平局了！",
    ),
    "0x083DBD2E": (
        "0x083DBD28",
        "\\1Dと \\1Eが\nしょうぶを しかけてきた！",
        "\\1D与 \\1E\n发起了对战！",
    ),
    "0x083DBD6E": (
        "0x083DBD68",
        "\\19の \\1Aは\n\\00を くりだした！",
        "\\19的 \\1A\n派出了\\00！",
    ),
    "0x083DBE75": (
        "0x083DBE6F",
        "\\19の \\1Aは\n\\00を ひっこめた！",
        "\\19的 \\1A\n收回了\\00！",
    ),
}


def _norm(addr: str) -> int:
    return int(str(addr), 16)


def main() -> int:
    apply = "--apply" in sys.argv
    want = {_norm(k): v for k, v in FIX.items()}

    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8"))

    hit = []
    for e in texts.get("entries") or []:
        try:
            a = _norm(e.get("address") or "")
        except ValueError:
            continue
        if a not in want:
            continue
        new_addr, new_orig, new_zh = want[a]
        hit.append((e, new_addr, new_orig, new_zh))

    print(f"命中 {len(hit)} / {len(FIX)} 条")
    for e, na, no, nz in hit:
        print(f"  {e.get('address')} → {na}")
        print(f"    old={e.get('original')!r}")
        print(f"    new={no!r}  →  {nz!r}")

    if not apply:
        print("\n（未落盘；加 --apply）")
        return 0

    cache_old = {e.get("original") for e, *_ in hit}
    for e, na, no, nz in hit:
        e["address"] = na
        e["original"] = no
        e["translated"] = nz

    # 缓存：删掉偏移版的 key，写入完整串
    cache = [x for x in cache if x.get("original") not in cache_old]
    have = {x.get("original") for x in cache}
    for e, na, no, nz in hit:
        if no not in have:
            cache.append({"original": no, "translated": nz, "status": 200})

    TEXTS.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已迁移 {len(hit)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
