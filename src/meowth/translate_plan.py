"""翻译通路规划：为每条目决策注入 type 并编码 target_hex。

type:
  in_place — F900 编码字节 ≤ 原始槽位，原地写入（最高优先）
  relocate — 编码超槽位且有指针源且模块允许，写扩展区 + 指针改写
             （附带预分配 phrase_code，注入 relocate 失败时回退 F9 80）
  upgrade  — relocate 不可用（无指针/禁 relocate）但允许短语，F9 80 原地
  keep     — 都无法满足，保留原文（ROM 不动）

优先级链：F900 原地 → relocate → F9 80 原地 → keep。

translate 阶段只做决策与编码（不注入 ROM），产出 translate.build.json，
build 阶段按 type 注入。texts_translated.json 降级为翻译缓存文件。
"""
from __future__ import annotations

from typing import Any

from .config_loader import F9_EOS, F9_PHRASE_DEFAULT

# 不 relocate 的模块 type：定长槽（stride/struct 走 in_place/upgrade）。
# 特殊 UI 用 modules.json 的 ``no_relocate: true`` 标志控制（渲染不走钩子，
# relocate 的 F9 00 流会导致花屏/崩溃；也不允许 F9 80 短语引用）。
NO_RELOCATE_TYPES = frozenset({"stride", "struct"})

# 同 id 多 type 冲突时保留优先级更高者（注入去重 / 载入 build 用）
PLAN_TYPE_RANK: dict[str, int] = {
    "relocate": 40,
    "in_place": 30,
    "upgrade": 20,
    "f980": 20,
    "keep": 10,
}


def plan_type_rank(ptype: str | None) -> int:
    return PLAN_TYPE_RANK.get(str(ptype or "keep"), 0)


def dedupe_entries_by_id(entries: list[dict]) -> list[dict]:
    """按 id 去重：同一 id 只保留首次出现。无 id 的条目原样保留。"""
    seen: set[str] = set()
    out: list[dict] = []
    for e in entries:
        eid = str(e.get("id") or "")
        if not eid:
            out.append(e)
            continue
        if eid in seen:
            continue
        seen.add(eid)
        out.append(e)
    return out


def prefer_plan(existing: dict | None, candidate: dict) -> dict:
    """同 id 多份 plan 时保留 type 优先级更高者；同级保留已有（先到）。"""
    if existing is None:
        return candidate
    if plan_type_rank(candidate.get("type")) > plan_type_rank(existing.get("type")):
        return candidate
    return existing


def build_plan_map_by_id(plan_entries_rows: list[dict]) -> dict[str, dict]:
    """从 translate.build.json entries 建 id→plan，冲突按 PLAN_TYPE_RANK。"""
    out: dict[str, dict] = {}
    for row in plan_entries_rows:
        eid = str(row.get("id") or "")
        if not eid or not row.get("type"):
            continue
        out[eid] = prefer_plan(out.get(eid), row)
    return out


def _module_meta(game_id: str, module_id: str | None) -> dict:
    if not module_id:
        return {}
    try:
        from .modules import _get_modules

        return _get_modules(game_id).get(module_id) or {}
    except Exception:
        return {}


def module_allows_relocate(game_id: str, module_id: str | None) -> bool:
    """该模块是否允许 relocate。

    由 modules.json 控制：``no_relocate: true`` 或 type 为 stride/struct 时
    不允许 relocate。
    """
    meta = _module_meta(game_id, module_id)
    if meta.get("no_relocate"):
        return False
    try:
        from .modules import module_type

        return module_type(game_id, module_id) not in NO_RELOCATE_TYPES
    except Exception:
        return True


def module_allows_phrase(game_id: str, module_id: str | None) -> bool:
    """该模块是否允许 F9 80 短语引用（f980 / upgrade）。

    ``no_relocate`` 只禁止 relocate（渲染不经钩子），**不禁止 F9 80 短语**：
    no_relocate 模块 F900 超槽时同样升槽为 F9 80 原地插入。
    """
    return True


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
    game_id: str = "",
) -> None:
    """只给“超槽位且确定走 F9 80”的条目预分配短语码。

    走 relocate 的条目（有指针 + 允许 relocate）不预占码——F9 80 按需申请，
    可 relocate 的路径用不到；只有无法 relocate（无指针/禁 relocate）的
    超槽条目才需要 F9 80 码。
    """
    for e in entries:
        t = _translated_of(e)
        o = _original_of(e)
        if e.get("_reject"):
            continue
        if not t or t == o:
            continue
        if "|||" in t:
            continue
        s = charmap._sanitize(t)
        if s in phrase_codes:
            continue
        byte_length = e.get("byte_length", 0) or 0
        if byte_length < 5:
            continue  # 槽位连 F9 80 都放不下 → keep
        module_id = e.get("module") or e.get("_axvj_module") or e.get("category")
        if _ptr_sources(e) and module_allows_relocate(game_id, module_id):
            continue  # 可 relocate → 走 relocate，不预占 F9 80 码
        if not module_allows_phrase(game_id, module_id):
            continue  # ui 特殊界面不短语引用 → keep
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
    game_id: str = "",
) -> dict:
    """决策单个条目的 type + target_hex。不改动 entry。"""
    original = _original_of(entry)
    translated = _translated_of(entry)
    byte_length = entry.get("byte_length", 0) or 0
    original_hex = entry.get("original_hex") or ""
    module_id = entry.get("module") or entry.get("_axvj_module") or entry.get("category")

    # config.json rejects / 阈值校验：无条件 keep，不进 relocate/upgrade
    if entry.get("_reject"):
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "rejects/校验拒绝(_reject)",
        }

    if not translated or translated == original:
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "无翻译或译文与原文相同",
        }

    # LLM batch 分隔符泄漏：||| 会编进 target_hex（含 00 填充），禁止注入
    if "|||" in translated:
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "译文含 LLM 分隔符 |||",
        }

    s = charmap._sanitize(translated)
    allow_reloc = module_allows_relocate(game_id, module_id)
    allow_phrase = module_allows_phrase(game_id, module_id)

    # 编码（F9 00 单字流等）
    try:
        encoded = charmap.encode(translated)
    except Exception:
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "译文编码失败",
        }

    # type 1: F900 编码 ≤ 原始槽位 → 原地（最高优先）
    if len(encoded) <= byte_length:
        return {"type": "in_place", "target_hex": encoded.hex(" ")}

    # type 2: 编码超槽位且该模块允许 relocate 且有指针 → 指针扩表。
    # F9 80 码按需申请：走 relocate 的条目不预占码。
    if allow_reloc and _ptr_sources(entry):
        return {
            "type": "relocate",
            "target_hex": encoded.hex(" "),
            "pointer_sources": _ptr_sources(entry),
        }

    # type 3: 超槽位且 relocate 不可用（无指针/禁 relocate）但允许短语
    # → F9 80 短语引用原地（preallocate 已给码）
    if allow_phrase and byte_length >= 5:
        code = phrase_codes.get(s)
        if code is not None:
            return {
                "type": "upgrade",
                "target_hex": _encode_phrase_ref(code).hex(" "),
                "phrase_code": code,
            }

    # type 4: 保留原文，记录具体原因
    if not allow_reloc and not allow_phrase:
        reason = "特殊UI模块禁止relocate/短语，且超槽位"
    elif not allow_reloc:
        reason = "模块禁止relocate，且槽位<5无法升槽"
    elif not allow_phrase:
        reason = "模块禁止短语引用，且无指针可relocate"
    else:
        reason = "无可用注入路径（超槽位/无指针/无短语码）"
    return {"type": "keep", "target_hex": original_hex, "reason": reason}


def plan_entries(
    entries: list[dict],
    charmap: Any,
    phrase_codes: dict[str, int],
    game_id: str = "",
) -> list[dict]:
    """批量决策：先按 id 去重，再预分配 upgrade 短语码，再逐条 plan。"""
    entries = dedupe_entries_by_id(entries)
    preallocate_upgrade_phrases(entries, charmap, phrase_codes, game_id=game_id)
    return [plan_entry(e, charmap, phrase_codes, game_id=game_id) for e in entries]
