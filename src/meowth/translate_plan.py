"""翻译通路规划：为每条目决策注入 type 并编码 target_hex。

type:
  f980     — translated 完全命中短语表（词典 / 自动分配），target=F9 80 code FF
  in_place — 编码字节 ≤ 原始槽位，原地写入
  relocate — 编码超槽位且该条目有指针源，写扩展区 + 指针改写
  upgrade  — relocate 不可用（无指针），自动分配短语码走 F9 80
  keep     — 都无法满足，保留原文（ROM 不动）

translate 阶段只做决策与编码（不注入 ROM），产出 translate.build.json，
build 阶段按 type 注入。texts_translated.json 降级为翻译缓存文件。
"""
from __future__ import annotations

from typing import Any

from .config_loader import F9_EOS, F9_PHRASE_DEFAULT


def _encode_phrase_ref(code: int) -> bytes:
    """F9 80 (code>>8) (code&0xFF) FF — 短语引用（5 字节）。"""
    return bytes([0xF9, F9_PHRASE_DEFAULT, (code >> 8) & 0xFF, code & 0xFF, F9_EOS])


def _translated_of(entry: dict) -> str:
    return (entry.get("translated") or "").strip('"')


def _original_of(entry: dict) -> str:
    return (entry.get("original") or "").strip('"')


def _ptr_sources(entry: dict) -> list:
    return entry.get("pointer_sources") or entry.get("pointer_addresses") or []


def preallocate_upgrade_phrases(
    entries: list[dict],
    charmap: Any,
    phrase_codes: dict[str, int],
) -> None:
    """先扫描“超槽位且无指针”的条目，为它们预先分配短语码。

    这样后续条目的 ``f980`` 完全匹配判定能命中自动分配的短语（用户要求
    type1 也包含自动分配的短语）。
    """
    for e in entries:
        t = _translated_of(e)
        o = _original_of(e)
        if not t or t == o:
            continue
        s = charmap._sanitize(t)
        if s in phrase_codes:
            continue
        byte_length = e.get("byte_length", 0) or 0
        if byte_length < 5:
            continue  # 槽位连 F9 80 都放不下 → keep
        if _ptr_sources(e):
            continue  # 有指针 → relocate
        try:
            raw_len = len(charmap.encode(t))
        except Exception:
            continue
        if raw_len > byte_length:
            phrase_codes[s] = len(phrase_codes)


def plan_entry(
    entry: dict,
    charmap: Any,
    phrase_codes: dict[str, int],
) -> dict:
    """决策单个条目的 type + target_hex。不改动 entry。"""
    original = _original_of(entry)
    translated = _translated_of(entry)
    byte_length = entry.get("byte_length", 0) or 0
    original_hex = entry.get("original_hex") or ""

    if not translated or translated == original:
        return {"type": "keep", "target_hex": original_hex}

    s = charmap._sanitize(translated)

    # type 1: F9 80 完全匹配（词典 / 自动分配短语，最高优先）
    code = phrase_codes.get(s)
    if code is not None:
        return {
            "type": "f980",
            "target_hex": _encode_phrase_ref(code).hex(" "),
            "phrase_code": code,
        }

    # 编码（F9 00 单字流等）
    try:
        encoded = charmap.encode(translated)
    except Exception:
        return {"type": "keep", "target_hex": original_hex}

    # type 2: 编码字节 ≤ 原始槽位 → 原地
    if len(encoded) <= byte_length:
        return {"type": "in_place", "target_hex": encoded.hex(" ")}

    # type 3: 编码超槽位且有指针 → 指针扩表（relocate）
    if _ptr_sources(entry):
        return {
            "type": "relocate",
            "target_hex": encoded.hex(" "),
            "pointer_sources": _ptr_sources(entry),
        }

    # type 4: relocate 不可用 → 升槽（此时 preallocate 已给码，直接命中 f980）
    if byte_length >= 5:
        code = phrase_codes.get(s)
        if code is not None:
            return {
                "type": "upgrade",
                "target_hex": _encode_phrase_ref(code).hex(" "),
                "phrase_code": code,
            }

    # type 5: 保留原文
    return {"type": "keep", "target_hex": original_hex}


def plan_entries(
    entries: list[dict],
    charmap: Any,
    phrase_codes: dict[str, int],
) -> list[dict]:
    """批量决策：先预分配 upgrade 短语码，再逐条 plan。返回 plan 列表。"""
    preallocate_upgrade_phrases(entries, charmap, phrase_codes)
    return [plan_entry(e, charmap, phrase_codes) for e in entries]
