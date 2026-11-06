#!/usr/bin/env python3
"""把「指针落在正文前 00 垫片」的 texts 条目改回与指针一致。

抽取常从第一个非 00 字节起算 address，但 ROM 指针表往往指向垫片起点。
本脚本只改正数据（texts.json / texts_translated.json），不改注入发现逻辑：

  address      → 指针真实目标（含前导 00）
  original_hex → 从该目标读到 FF（含前导 00）
  original     → decode（0x00 → 空格）
  translated   → 前导空格数与 original 对齐（保留原译文正文）

用法（仓库根）：
  set PYTHONPATH=%cd%\\src
  python scripts/texts/fix_ptr_pad_prefix.py --dry-run
  python scripts/texts/fix_ptr_pad_prefix.py --write
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from meowth.jp_pcs import decode_pcs, looks_like_jp_text  # noqa: E402

GAME = "POKEMON_RUBY_AXVJ00"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"
TRANSLATED = ROOT / "configs" / GAME / "translate" / "texts_translated.json"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
GBA_BASE = 0x08000000
MAX_PAD = 8
# 补漏剧情里大量脚本碎片，默认不改；需要时 --modules 显式加上
DEFAULT_MODULES = frozenset({"剧情", "UI界面"})


def _file(addr: int | str) -> int:
    v = int(str(addr).replace("0x", ""), 16)
    return v & 0xFFFFFF


def _leading_spaces(s: str) -> int:
    n = 0
    for ch in s:
        if ch in (" ", "\u3000"):
            n += 1
        else:
            break
    return n


def _align_zh_spaces(original: str, translated: str) -> str:
    """让译文前导空格数与日文 original 一致；正文不改。"""
    if not translated:
        return translated
    need = _leading_spaces(original)
    body = translated.lstrip(" \u3000")
    return (" " * need) + body


def _ptr_index(rom: bytes) -> dict[int, list[int]]:
    """file_off → [pointer site file offs]（仅 08xxxxxx 总线指针）。"""
    idx: dict[int, list[int]] = {}
    n = len(rom)
    for o in range(0, n - 3, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if GBA_BASE <= v < GBA_BASE + n:
            tgt = v - GBA_BASE
            if tgt >= 0x100000:
                idx.setdefault(tgt, []).append(o)
    return idx


def plan_fixes(
    rom: bytes,
    entries: list[dict],
    zh_by_original: dict[str, str] | None = None,
    *,
    modules: frozenset[str] | None = None,
) -> list[dict]:
    ptrs = _ptr_index(rom)
    zh_map = zh_by_original or {}
    allow = modules if modules is not None else DEFAULT_MODULES
    out: list[dict] = []
    for e in entries:
        if allow and (e.get("module") or "") not in allow:
            continue
        addr = e.get("address")
        if not addr:
            continue
        body = _file(addr)
        # 已是垫片起点且存在精确指针 → 跳过
        if body in ptrs and (e.get("original_hex") or "").startswith("00"):
            continue
        # 仅串池形态：上一条 FF 之后的纯 00 垫片（非定长表名槽里的 00）。
        pad_start = body
        while pad_start > 0 and body - pad_start < MAX_PAD and rom[pad_start - 1] == 0x00:
            pad_start -= 1
        if pad_start == body:
            continue
        if pad_start > 0 and rom[pad_start - 1] != 0xFF:
            continue
        if pad_start not in ptrs:
            continue
        # 跳过整表基址字面量（同址被大量引用）
        if len(ptrs[pad_start]) > 4:
            continue
        end = rom.find(0xFF, pad_start, pad_start + 512)
        if end < 0:
            continue
        raw = bytes(rom[pad_start : end + 1])
        if not looks_like_jp_text(raw):
            continue
        new_original = decode_pcs(raw)
        old_original = e.get("original") or ""
        old_zh = (e.get("translated") or "").strip() or zh_map.get(old_original) or ""
        sites = [f"0x{GBA_BASE + s:08X}" for s in ptrs[pad_start]]
        out.append({
            "id": e.get("id"),
            "old_address": e.get("address"),
            "new_address": f"0x{GBA_BASE + pad_start:08X}",
            "old_original": old_original,
            "new_original": new_original,
            "old_hex": e.get("original_hex"),
            "new_hex": raw.hex(" "),
            "byte_length": len(raw),
            "pointer_sources": sites,
            "old_translated": old_zh,
            "new_translated": _align_zh_spaces(new_original, old_zh) if old_zh else old_zh,
        })
    return out


def apply_texts(entries: list[dict], fixes: list[dict]) -> int:
    by_id = {f["id"]: f for f in fixes if f.get("id")}
    n = 0
    for e in entries:
        f = by_id.get(e.get("id"))
        if not f:
            continue
        e["address"] = f["new_address"]
        e["original"] = f["new_original"]
        e["original_hex"] = f["new_hex"]
        e["byte_length"] = f["byte_length"]
        e["is_pointer_based"] = True
        e["pointer_sources"] = list(f["pointer_sources"])
        e["pointer_addresses"] = list(f["pointer_sources"])
        if f.get("new_translated"):
            e["translated"] = f["new_translated"]
        n += 1
    return n


def apply_translated_cache(cache: list[dict], fixes: list[dict]) -> int:
    """按旧 original 对齐缓存；写入带前导空格的新 original / translated。"""
    by_old = {f["old_original"]: f for f in fixes if f.get("old_original")}
    n = 0
    seen_new: set[str] = set()
    for row in cache:
        old = row.get("original") or ""
        f = by_old.get(old)
        if not f:
            continue
        row["original"] = f["new_original"]
        zh = row.get("translated") or f.get("old_translated") or ""
        row["translated"] = _align_zh_spaces(f["new_original"], zh)
        seen_new.add(f["new_original"])
        n += 1
    # 缓存里只有新 key、或 texts 有译但 cache 无旧 key：补一条
    have = {r.get("original") for r in cache}
    for f in fixes:
        neo = f["new_original"]
        if neo in have or neo in seen_new:
            continue
        zh = f.get("new_translated") or f.get("old_translated") or ""
        if not zh:
            continue
        cache.append({"status": 200, "original": neo, "translated": zh})
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="写回 texts.json / texts_translated.json")
    ap.add_argument("--dry-run", action="store_true", help="只打印（默认）")
    ap.add_argument(
        "--modules",
        default=",".join(sorted(DEFAULT_MODULES)),
        help="逗号分隔模块名；空字符串=不限模块",
    )
    args = ap.parse_args()
    if not args.write:
        args.dry_run = True

    rom = ROM.read_bytes()
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = texts.get("entries") or []
    cache = json.loads(TRANSLATED.read_text(encoding="utf-8"))
    zh_by = {
        r.get("original") or "": r.get("translated") or ""
        for r in (cache if isinstance(cache, list) else [])
        if r.get("original") and r.get("translated")
    }
    mods = (
        frozenset(x.strip() for x in args.modules.split(",") if x.strip())
        if args.modules is not None and args.modules != ""
        else None
    )
    fixes = plan_fixes(rom, entries, zh_by_original=zh_by, modules=mods)
    print(f"candidates: {len(fixes)}")
    for f in fixes[:30]:
        print(
            f"  {f['id']} {f['old_address']} -> {f['new_address']} "
            f"ptrs={len(f['pointer_sources'])} "
            f"orig={f['old_original'][:20]!r} => {f['new_original'][:24]!r}"
        )
    if len(fixes) > 30:
        print(f"  ... +{len(fixes) - 30} more")

    if args.dry_run or not args.write:
        print("dry-run: no files written")
        return 0

    n = apply_texts(entries, fixes)
    TEXTS.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not isinstance(cache, list):
        raise SystemExit("texts_translated.json: expected list")
    nt = apply_translated_cache(cache, fixes)
    TRANSLATED.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote texts.json entries={n}, texts_translated.json rows={nt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
