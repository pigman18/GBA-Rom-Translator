#!/usr/bin/env python3
"""把 texts 条目地址改回「指针真实目标」（含前导 00 / 控制码头）。

抽取常从第一个「正文假名」起算 address，但 ROM 指针往往指向：
  - 前导 00 空格垫片，或
  - ``FC/FD`` 等扩展控制码头（如 ``\\CC050E\\02\\CC050Fで であった``）

本脚本只改正数据（texts.json / texts_translated.json），不在 Python 注入侧做兼容：

  address / original_hex / original ← 从指针目标读到 FF
  pointer_sources                   ← 指向该目标的站点
  translated                        ← 按新 original 对齐前导空格；词库可补译

用法（仓库根）：
  set PYTHONPATH=%cd%\\src
  python scripts/texts/fix_ptr_string_head.py --dry-run
  python scripts/texts/fix_ptr_string_head.py --write
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
from meowth.seed_translate import seed_translate_entry  # noqa: E402
from meowth.config_loader import set_active_game_id  # noqa: E402

GAME = "POKEMON_RUBY_AXVJ00"
TEXTS = ROOT / "configs" / GAME / "translate" / "texts.json"
TRANSLATED = ROOT / "configs" / GAME / "translate" / "texts_translated.json"
ROM = ROOT / "roms" / "origin" / f"{GAME}.gba"
GBA_BASE = 0x08000000
# 控制码头 + 短垫片：指针相对正文起点回退上限
MAX_BACK = 24
DEFAULT_MODULES = frozenset({"剧情", "UI界面", "补漏剧情"})


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
    if not translated:
        return translated
    need = _leading_spaces(original)
    body = translated.lstrip(" \u3000")
    return (" " * need) + body


def _ptr_index(rom: bytes) -> dict[int, list[int]]:
    idx: dict[int, list[int]] = {}
    n = len(rom)
    for o in range(0, n - 3, 4):
        v = struct.unpack_from("<I", rom, o)[0]
        if GBA_BASE <= v < GBA_BASE + n:
            tgt = v - GBA_BASE
            if tgt >= 0x100000:
                idx.setdefault(tgt, []).append(o)
    return idx


def _pcs_end(rom: bytes, start: int) -> int:
    return rom.find(0xFF, start, start + 512)


_RE_VISIBLE_JP = __import__("re").compile(r"[ぁ-んァ-ン一-龥Ａ-Ｚａ-ｚA-Za-z0-9]")


def _prefix_pad_or_ctrl_only(rom: bytes, cand: int, body: int) -> bool:
    """``[cand, body)`` 只能是前导 00 或扩展控制码，不能吞上一段正文。"""
    if cand >= body:
        return False
    prefix = bytes(rom[cand:body]) + b"\xFF"
    try:
        text = decode_pcs(prefix)
    except Exception:
        return False
    # 去掉空白与 \\TOKEN 后不应再有可见假名/汉字/字母数字
    compact = text
    for _ in range(8):
        nxt = __import__("re").sub(r"\\[A-Za-z0-9]+", "", compact)
        nxt = nxt.replace(" ", "").replace("\u3000", "").replace("\n", "")
        if nxt == compact:
            break
        compact = nxt
    return not _RE_VISIBLE_JP.search(compact)


def plan_fixes(
    rom: bytes,
    entries: list[dict],
    zh_by_original: dict[str, str] | None = None,
    *,
    modules: frozenset[str] | None = None,
) -> list[dict]:
    """条目地址晚于指针目标、前缀仅为 00/控制码 → 回退到指针目标。"""
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
        end = _pcs_end(rom, body)
        if end < 0:
            continue
        cur_hex = (e.get("original_hex") or "").replace(" ", "").lower()
        rom_at_body = rom[body : end + 1].hex()

        best: int | None = None
        for cand in range(body, max(0, body - MAX_BACK) - 1, -1):
            if cand not in ptrs:
                continue
            if len(ptrs[cand]) > 8:
                continue
            if cand < body and not _prefix_pad_or_ctrl_only(rom, cand, body):
                continue
            cend = _pcs_end(rom, cand)
            if cend != end:
                continue
            raw = bytes(rom[cand : end + 1])
            if not looks_like_jp_text(raw):
                continue
            best = cand
            break
        if best is None:
            continue
        raw = bytes(rom[best : end + 1])
        new_original = decode_pcs(raw)
        old_original = e.get("original") or ""
        if (
            best == body
            and new_original == old_original
            and cur_hex == raw.hex()
            and e.get("pointer_sources")
        ):
            continue
        # 同址只修 hex/指针缺失
        if best == body and cur_hex == rom_at_body and e.get("pointer_sources"):
            continue
        old_zh = (
            (e.get("translated") or "").strip()
            or zh_map.get(old_original)
            or zh_map.get(new_original)
            or ""
        )
        if not old_zh:
            old_zh = seed_translate_entry(new_original) or ""
        # 残片译文对不上完整串时，优先词库对完整 original 的种子
        seeded_full = seed_translate_entry(new_original)
        if seeded_full and (
            not old_zh or old_original != new_original and old_zh and "\\" not in old_zh
            and "\\CC" in new_original
        ):
            # 控制码头串：残片译（如「在……相遇了」）不如词库完整模板
            if "\\CC" in new_original or "\\0" in new_original:
                old_zh = seeded_full
        sites = [f"0x{GBA_BASE + s:08X}" for s in ptrs[best]]
        out.append({
            "id": e.get("id"),
            "old_address": e.get("address"),
            "new_address": f"0x{GBA_BASE + best:08X}",
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
        row["translated"] = _align_zh_spaces(f["new_original"], zh) if zh else (
            f.get("new_translated") or ""
        )
        seen_new.add(f["new_original"])
        n += 1
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
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--modules",
        default=",".join(sorted(DEFAULT_MODULES)),
        help="逗号分隔；空=不限",
    )
    args = ap.parse_args()
    if not args.write:
        args.dry_run = True

    set_active_game_id(GAME)
    rom = ROM.read_bytes()
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))
    entries = texts.get("entries") or []
    cache = json.loads(TRANSLATED.read_text(encoding="utf-8"))
    if not isinstance(cache, list):
        raise SystemExit("texts_translated.json: expected list")
    zh_by = {
        r.get("original") or "": r.get("translated") or ""
        for r in cache
        if r.get("original") and r.get("translated")
    }
    mods = (
        frozenset(x.strip() for x in args.modules.split(",") if x.strip())
        if args.modules != ""
        else None
    )
    fixes = plan_fixes(rom, entries, zh_by_original=zh_by, modules=mods)
    print(f"candidates: {len(fixes)}")
    for f in fixes[:40]:
        print(
            f"  {f['id']} {f['old_address']} -> {f['new_address']} "
            f"orig={f['old_original'][:28]!r} => {f['new_original'][:36]!r} "
            f"zh={f['new_translated'][:28]!r}"
        )
    if len(fixes) > 40:
        print(f"  ... +{len(fixes) - 40} more")

    if args.dry_run or not args.write:
        print("dry-run: no files written")
        return 0

    n = apply_texts(entries, fixes)
    TEXTS.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    nt = apply_translated_cache(cache, fixes)
    TRANSLATED.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote texts.json entries={n}, texts_translated.json rows={nt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
