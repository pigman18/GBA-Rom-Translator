#!/usr/bin/env python3
"""补齐战斗文本模板的译文（拼接式，保留名字占位符）。

这些是「名字变量 + 后缀模板」的拼接串：游戏先把训练家/宝可梦名写进缓冲，
再接上下面这条。中文语序不同，只能让后缀自洽，所以译文以「的/派出了」开头：

    [名前] + との\\nしょうぶに かった！       → 的对战\\n胜利了！
    [名前] + が\\nしょうぶを しかけてきた！   → 发起了\\n对战！
    [名前] + は\\n\\00を くりだした！          → 派出了\\n\\00！

``\\00`` 是运行时替换成名字的控制码，必须原样保留。

用法::

    PYTHONPATH=src python scripts/oneoff/_fill_battle_templates.py --apply
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GID = "POKEMON_RUBY_AXVJ00"
ROOT = Path(__file__).resolve().parents[2]
TEXTS = ROOT / "configs" / GID / "translate" / "texts.json"
CACHE = ROOT / "configs" / GID / "translate" / "texts_translated.json"

# 地址 → 译文（原文从 ROM 取，避免手抄反斜杠出错）
BY_ADDR: dict[str, str] = {
    "0x083DA740": " 中毒了！",
    "0x083DB884": "的对战\n胜利了！",
    "0x083DB8A8": "的对战\n失败了！",
    "0x083DB8CE": "的对战\n平局了！",
    "0x083DBD2E": " 发起了\n对战！",
    "0x083DBD6E": " 派出了\n\\00！",
    "0x083DBE75": " 收回了\n\\00！",
    "0x083EB34E": "……！",
}


def main() -> int:
    apply = "--apply" in sys.argv
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8"))

    want = {int(k, 16) for k in BY_ADDR}

    def _a(entry) -> int | None:
        try:
            return int(str(entry.get("address")), 16)
        except (TypeError, ValueError):
            return None

    todo = []
    for e in texts.get("entries") or []:
        addr = _a(e)
        if addr not in want:
            continue
        addr = f"0x{addr:08X}"
        orig = e.get("original") or ""
        zh = BY_ADDR[addr]
        todo.append((addr, orig, zh, e.get("translated") or ""))

    print(f"命中 {len(todo)} 条")
    for addr, orig, zh, cur in todo:
        print(f"  {addr} {orig!r} -> {zh!r}" + (f"  (已有 {cur!r})" if cur else ""))

    if not apply:
        print("\n（未落盘；加 --apply）")
        return 0

    by_orig = {o: z for _, o, z, _ in todo}
    for e in texts.get("entries") or []:
        addr = _a(e)
        if addr in want:
            e["translated"] = BY_ADDR[f"0x{addr:08X}"]

    n = 0
    for x in cache:
        o = x.get("original")
        if o in by_orig and (x.get("translated") or "") != by_orig[o]:
            x["translated"] = by_orig[o]
            x["status"] = 200
            n += 1
    # cache 里没有的就补一条
    have = {x.get("original") for x in cache}
    for orig, zh in by_orig.items():
        if orig not in have:
            cache.append({"original": orig, "translated": zh, "status": 200})
            n += 1

    TEXTS.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写入 texts.json {len(todo)} 条 / 缓存 {n} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
