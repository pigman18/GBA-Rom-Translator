"""翻译通路规划：为每条目决策注入 type 并编码 target_hex。

type:
  replace  — 写入原槽：F900 整串，或越槽时的 F9 80 短语引用（带 ``phrase_code``）
  relocate — 编码超槽位且有可用指针源且模块 ``relocate=true``，写扩展区 + 指针改写
  keep     — 都无法满足，保留原文（ROM 不动）

优先级链（纯 1→4，编排期一次定死）：
  1. F900 原地
  2. 不够 → relocate（指针须在编排期校验可用）
  3. 指针不够 → F980 原地
  4. F980 不够 → hook
  否则 keep

translate 阶段产出 ``translate.build.json``（含已校验的 pointer_sources /
phrase_code / target_hex）；build 阶段按 type **直入**，不再改路径、不再回退。
"""
from __future__ import annotations

import re
from typing import Any

from .charmap import normalize_zh_punct
from .config_loader import F9_EOS, F9_PHRASE_DEFAULT

# Meowth decode of FD xx → \20 / \13 / …；勿匹配 \\CC 色码。
_RE_EXPAND_PLACEHOLDER = re.compile(r"\\(?!CC)(?:v|[0-9A-Fa-f]{2})")

# 定长槽类型强制不可指针改写（不受 modules.json relocate 覆盖为 true）
NO_RELOCATE_TYPES = frozenset({"stride", "struct", "ptr_stride", "stride_ptr"})

POINTER_OFFSET = 0x08000000

# 同 id 多 type 冲突时保留优先级更高者（注入去重 / 载入 build 用）
PLAN_TYPE_RANK: dict[str, int] = {
    "relocate": 50,
    "replace": 30,
    # legacy aliases (read-only compat with old translate.build.json)
    "upgrade": 30,
    "f980": 30,
    "slot": 20,
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
    """该模块是否允许 relocate（Python 改指针 + 扩展区正文）。

    modules.json：``relocate: true/false``（旧 ``no_relocate`` 过渡兼容）。
    ``stride``/``struct`` 等定长表类型始终不允许。
    """
    meta = _module_meta(game_id, module_id)
    try:
        from .modules import module_type

        if module_type(game_id, module_id) in NO_RELOCATE_TYPES:
            return False
    except Exception:
        pass
    if "relocate" in meta:
        return bool(meta.get("relocate"))
    if "no_relocate" in meta:
        return not bool(meta.get("no_relocate"))
    return True


def module_allows_phrase(game_id: str, module_id: str | None) -> bool:
    """该模块是否允许 F9 80 短语引用（仍写入原槽，type=replace）。

    ``relocate=false`` 只禁止改指针，**不禁止** F9 80 短语原地。
    """
    return True


def module_allows_table_widen(game_id: str, module_id: str | None) -> bool:
    """是否允许 write 扩表（literal_ref_widen / item 等）。

    与 ``module_allows_relocate`` 不同：不因 stride/struct 类型恒 false。
    仅当模块配置显式 ``relocate: true`` 时扩表；``false`` 或未写则否。
    """
    meta = _module_meta(game_id, module_id)
    return bool(meta.get("relocate"))


def module_write_build_meta(game_id: str, module_id: str | None) -> dict | None:
    """build.json 仅在本轮真会扩表时附加 write（无用则不出现）。"""
    if not module_allows_table_widen(game_id, module_id):
        return None
    meta = _module_meta(game_id, module_id)
    write = meta.get("write")
    if not isinstance(write, dict) or not write:
        return None
    return dict(write)


def _encode_phrase_ref(code: int, channel: int = F9_PHRASE_DEFAULT) -> bytes:
    """F9 <channel> (code>>8) (code&0xFF) FF — 短语引用（5 字节）。"""
    return bytes([0xF9, channel & 0xFF, (code >> 8) & 0xFF, code & 0xFF, F9_EOS])


def pad_inplace_to_slot(encoded: bytes, byte_length: int) -> bytes:
    """in_place：正文后用 FF 补齐到 ``byte_length``（target_hex 与槽等长）。

    避免只写短串（如 5B 的 F980）而槽尾残留日文假名。
    """
    eos = bytes([F9_EOS])
    body = bytes(encoded)
    while body.endswith(eos):
        body = body[:-1]
    if byte_length <= 0:
        return body + eos
    if len(body) >= byte_length:
        return body[: byte_length - 1] + eos
    return body + eos * (byte_length - len(body))


def _translated_of(entry: dict) -> str:
    return (entry.get("translated") or "").strip('"')


def _original_of(entry: dict) -> str:
    return (entry.get("original") or "").strip('"')


def _ptr_sources(entry: dict) -> list:
    return entry.get("pointer_sources") or entry.get("pointer_addresses") or []


def _file_offset(addr: int | str) -> int:
    a = int(str(addr).replace("0x", ""), 16)
    if a >= POINTER_OFFSET:
        a -= POINTER_OFFSET
    return a


def entry_has_expand_placeholder(entry: dict) -> bool:
    """True if the JP slot is a StringExpand template (FD xx / \\XX).

    仅作形态标记；纯 1→4 链不再据此禁止 F980。
    """
    hx = (entry.get("original_hex") or "").replace(" ", "").lower()
    i = 0
    while i < len(hx) - 3:
        if hx[i : i + 2] == "fd":
            return True
        if hx[i : i + 2] == "f9":
            i += 8  # skip F9 op hi lo
            continue
        if hx[i : i + 2] in ("fc",):
            i += 2
            continue
        i += 2
    o = _original_of(entry)
    if _RE_EXPAND_PLACEHOLDER.search(o):
        return True
    return False


def _entry_address_off(entry: dict) -> int | None:
    raw = entry.get("address")
    if raw in (None, ""):
        return None
    try:
        return _file_offset(raw)
    except (TypeError, ValueError):
        return None


def extract_truncated_fd_prefix(
    rom: bytes | bytearray | None, entry: dict
) -> bool:
    """extract 裁掉串首 FD 时，address 落在缓冲 id 上（ROM[addr-1]==FD）。"""
    if rom is None:
        return False
    addr = _entry_address_off(entry)
    if addr is None or addr <= 0 or addr > len(rom):
        return False
    return rom[addr - 1] == 0xFD


def rebase_truncated_fd_slot(
    rom: bytes | bytearray | None, entry: dict
) -> tuple[int, int] | None:
    """若 extract 地址落在 FD 后的缓冲 id，回退到 FD 起点并扩 1 字节槽。

    返回 ``(write_addr_file_off, byte_length)``；无需回退则 None。
    """
    if not extract_truncated_fd_prefix(rom, entry):
        return None
    addr = _entry_address_off(entry)
    if addr is None:
        return None
    bl = int(entry.get("byte_length") or 0) + 1
    return addr - 1, bl


def resolve_usable_pointers(
    entry: dict,
    rom: bytes | bytearray | None,
    *,
    game_id: str = "",
    text_spans: list[tuple[int, int]] | None = None,
    lz_spans: list[tuple[int, int]] | None = None,
    min_pointer_source: int = 0x6000,
    text_address: int | None = None,
) -> list[str]:
    """编排期校验指针：只保留当前确实指向该正文的可用站点。

    无 ROM 时无法校验，原样返回登记指针（单测/缺 ROM 兜底）。
    始终 expand（全 ROM 搜 LE 字面量，含脚本 message 非对齐嵌入）再 filter，
    避免只改 C 字面量池、漏掉 ``02 67 <ptr>`` 一类脚本站点（PC 连接提示等）。
    ``text_address`` 可指定正文起点（FD 回退后用 addr-1）。
    """
    raw = list(_ptr_sources(entry))
    if not raw:
        return []
    if rom is None:
        return [str(p) for p in raw]

    from .policy import expand_pointer_sources

    addr = text_address if text_address is not None else _entry_address_off(entry)
    if addr is None:
        return []

    module_id = entry.get("module") or entry.get("_axvj_module") or entry.get("category") or ""
    original = _original_of(entry)
    expected = POINTER_OFFSET + addr
    kwargs = dict(
        category=module_id,
        original=original,
        expected_pointer=expected,
        lz_spans=lz_spans,
        min_pointer_source=min_pointer_source,
        text_spans=text_spans,
    )
    offs = expand_pointer_sources(rom, addr, raw, **kwargs)
    return [f"0x{p:X}" if isinstance(p, int) else str(p) for p in offs]


def _prepare_encoded(
    entry: dict,
    charmap: Any,
    game_id: str,
) -> tuple[str, str, bytes] | dict:
    """返回 (sanitized, to_encode, encoded)；失败则返回 keep plan dict。"""
    from .config_loader import module_wrap_kwargs
    from .text_wrap import wrap_text

    original = _original_of(entry)
    translated = _translated_of(entry)
    original_hex = entry.get("original_hex") or ""
    module_id = entry.get("module") or entry.get("_axvj_module") or entry.get("category")

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
    if "|||" in translated:
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "译文含 LLM 分隔符 |||",
        }

    translated = normalize_zh_punct(translated)
    s = normalize_zh_punct(charmap._sanitize(translated))
    to_encode = wrap_text(
        s,
        target_lang="zh-Hans",
        **module_wrap_kwargs(game_id, module_id),
    )
    try:
        encoded = charmap.encode(to_encode)
    except Exception:
        return {
            "type": "keep",
            "target_hex": original_hex,
            "reason": "译文编码失败",
        }
    # F901/F981 已移除：短语恒 F9 80，不再重写通道字节。
    return s, to_encode, encoded


def _ensure_phrase_code(phrase_codes: dict[str, int], text: str) -> int:
    code = phrase_codes.get(text)
    if code is None:
        code = len(phrase_codes)
        phrase_codes[text] = code
    return code


def _keep(original_hex: str, reason: str) -> dict:
    return {"type": "keep", "target_hex": original_hex, "reason": reason}


def _reuse_slot_capacity(
    entry: dict, game_id: str, module_id: str | None, fallback: int
) -> int:
    """``reuse_slot_padding`` 模块：定长字段可写到声明的槽宽，而非 EOS 截断长。

    槽宽读模块 ``write.byte_length``（struct 字段的声明槽宽）。
    stride 表的 byte_length 本身就是 stride，无需调整（fallback 已够）。
    """
    if not entry.get("is_fixed_table"):
        return fallback
    meta = _module_meta(game_id, module_id)
    if not meta.get("reuse_slot_padding"):
        return fallback
    write = meta.get("write") or {}
    try:
        cap = int(write.get("byte_length") or 0)
    except (TypeError, ValueError):
        return fallback
    if cap <= 0:
        return fallback
    return cap


def plan_entry(
    entry: dict,
    charmap: Any,
    phrase_codes: dict[str, int],
    game_id: str = "",
    *,
    rom: bytes | bytearray | None = None,
    text_spans: list[tuple[int, int]] | None = None,
    lz_spans: list[tuple[int, int]] | None = None,
    usable_ptrs: list[str] | None = None,
) -> dict:
    """决策单个条目的 type + target_hex。不改动 entry。

    纯 1→4：F900 → relocate → F980 → hook → keep。
    extract 若把地址落在 FD 后的缓冲 id：回退到 FD 起点写 in_place（槽+1）。
    """
    prepared = _prepare_encoded(entry, charmap, game_id)
    if isinstance(prepared, dict):
        return prepared
    _s, to_encode, encoded = prepared

    byte_length = entry.get("byte_length", 0) or 0
    original_hex = entry.get("original_hex") or ""
    module_id = entry.get("module") or entry.get("_axvj_module") or entry.get("category")
    slot_cap = _reuse_slot_capacity(entry, game_id, module_id, byte_length)
    allow_reloc = module_allows_relocate(game_id, module_id)
    allow_phrase = module_allows_phrase(game_id, module_id)
    channel = F9_PHRASE_DEFAULT  # F901/F981 已移除，短语恒 F9 80

    rebase = rebase_truncated_fd_slot(rom, entry)
    write_addr = _entry_address_off(entry)
    if rebase is not None:
        write_addr, byte_length = rebase
        slot_cap = _reuse_slot_capacity(entry, game_id, module_id, byte_length)

    if usable_ptrs is None:
        usable_ptrs = resolve_usable_pointers(
            entry,
            rom,
            game_id=game_id,
            text_spans=text_spans,
            lz_spans=lz_spans,
            text_address=write_addr,
        )
        # 回退前地址上也可能挂着指针
        if not usable_ptrs and rebase is not None:
            usable_ptrs = resolve_usable_pointers(
                entry,
                rom,
                game_id=game_id,
                text_spans=text_spans,
                lz_spans=lz_spans,
                text_address=_entry_address_off(entry),
            )

    def _with_write_meta(plan: dict) -> dict:
        if rebase is not None and write_addr is not None:
            plan["address"] = f"0x{write_addr:X}"
            plan["byte_length"] = byte_length
            plan["fd_rebased"] = True
        return plan

    # 1) F900 原地（reuse_slot_padding=true 时按槽宽可写）
    if len(encoded) <= slot_cap:
        plan = {
            "type": "replace",
            "target_hex": pad_inplace_to_slot(encoded, slot_cap).hex(" "),
        }
        if slot_cap != byte_length:
            plan["byte_length"] = slot_cap
        return _with_write_meta(plan)

    # 2) relocate
    if allow_reloc and usable_ptrs:
        return _with_write_meta({
            "type": "relocate",
            "target_hex": encoded.hex(" "),
            "pointer_sources": list(usable_ptrs),
        })

    # 3) F980 原地升槽（reuse_slot_padding=true 时按槽宽判断）
    if allow_phrase and slot_cap >= 5:
        code = _ensure_phrase_code(phrase_codes, to_encode)
        plan = {
            "type": "replace",
            "target_hex": pad_inplace_to_slot(
                _encode_phrase_ref(code, channel), slot_cap
            ).hex(" "),
            "phrase_code": code,
        }
        if slot_cap != byte_length:
            plan["byte_length"] = slot_cap
        return _with_write_meta(plan)

    # 4) slot — 超槽位且槽位<5无法F980、无可用指针：运行时查表拦截
    if allow_phrase and byte_length < 5 and not usable_ptrs:
        return _with_write_meta({
            "type": "slot",
            "target_hex": encoded.hex(" "),
            "original_hex": original_hex,
        })

    if not usable_ptrs and not allow_phrase:
        reason = "无可用指针且无法短语升槽"
    elif not usable_ptrs:
        reason = "超槽位；无可用指针；无法F980升槽"
    elif not allow_reloc and not allow_phrase:
        reason = "模块禁止 relocate/短语，且超槽位"
    else:
        reason = "无可用注入路径（超槽位/模块禁路径）"
    return _keep(original_hex, reason)


def _plan_ptr_slots(plans: list[dict]) -> set[int]:
    """relocate 计划的指针站点（文件偏移），供 in_place 避让。"""
    slots: set[int] = set()
    for p in plans:
        if (p.get("type") or "") != "relocate":
            continue
        for src in p.get("pointer_sources") or []:
            try:
                slots.add(_file_offset(src))
            except (TypeError, ValueError):
                continue
    return slots


def _inplace_write_len(plan: dict, byte_length: int) -> int:
    try:
        raw = bytes.fromhex((plan.get("target_hex") or "").replace(" ", ""))
    except ValueError:
        return 0
    if not raw:
        return 0
    return min(len(raw), byte_length) if byte_length > 0 else len(raw)


def finalize_plans_against_ptr_slots(
    entries: list[dict],
    plans: list[dict],
) -> list[dict]:
    """编排期末：in_place 若会盖住 relocate 指针槽 → 降为 keep。

    不再在 build 注入时改路径；冲突在 build.json 里就写成 keep。
    """
    slots = _plan_ptr_slots(plans)
    if not slots:
        return plans
    out: list[dict] = []
    for e, p in zip(entries, plans):
        if (p.get("type") or "") != "replace":
            out.append(p)
            continue
        try:
            if p.get("address"):
                addr = _file_offset(p["address"])
            else:
                addr = _entry_address_off(e)
        except (TypeError, ValueError):
            addr = _entry_address_off(e)
        if addr is None:
            out.append(p)
            continue
        bl = int(p.get("byte_length") or e.get("byte_length") or 0)
        wlen = _inplace_write_len(p, bl)
        if wlen <= 0:
            out.append(p)
            continue
        end = addr + wlen
        hits = sorted(s for s in slots if addr <= s < end)
        if not hits:
            out.append(p)
            continue
        out.append(
            _keep(
                e.get("original_hex") or p.get("target_hex") or "",
                "in_place会覆盖relocate/hook指针槽 "
                + ",".join(f"0x{h:X}" for h in hits[:4])
                + ("…" if len(hits) > 4 else ""),
            )
        )
    return out


def preallocate_upgrade_phrases(
    entries: list[dict],
    charmap: Any,
    phrase_codes: dict[str, int],
    game_id: str = "",
    **_kwargs: Any,
) -> None:
    """兼容旧调用：短语码改为 plan_entry 按需分配，此处不再预占。"""
    return None


def plan_entries(
    entries: list[dict],
    charmap: Any,
    phrase_codes: dict[str, int],
    game_id: str = "",
    *,
    rom: bytes | bytearray | None = None,
    min_pointer_source: int = 0x6000,
) -> list[dict]:
    """批量决策：去重 → 纯1→4 plan（含 FD 回退/指针校验）→ 指针槽避让收尾。"""
    entries = dedupe_entries_by_id(entries)

    text_spans = None
    lz_spans = None
    if rom is not None:
        from .policy import collect_entry_text_spans

        text_spans = collect_entry_text_spans(entries)
        try:
            from .extract import trusted_lz_spans

            lz_spans = trusted_lz_spans(rom)
        except Exception:
            lz_spans = None

    plans = [
        plan_entry(
            e,
            charmap,
            phrase_codes,
            game_id=game_id,
            rom=rom,
            text_spans=text_spans,
            lz_spans=lz_spans,
        )
        for e in entries
    ]
    return finalize_plans_against_ptr_slots(entries, plans)
