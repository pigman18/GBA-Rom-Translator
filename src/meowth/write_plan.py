"""从 texts.json + 译文生成唯一写入计划 ``write.plan.json``。

**重定向**（与 ``hook/patches/start_menu.asm`` 同义）：
新区放译文体 → 改原引用站点（``.word`` 字面量，或读点 ``ldr+bx``/``bl`` 钩子）
指向新区。无传统指针、动态拼接、超短槽，只要定得出站点，都走这条。

写入类（不做原地 F9 写回原槽）：

1. **stride 表** → tables[]：按**最长译文**选 ``old×2^k`` 新步长；
   整表进新区；改基址字面量 + 改步长移位指令；无译文槽填原文。
2. **常规有指针** → rows[]（kind=pointer）：改登记/展开的指针槽。
3. **struct 名字** → 整块规划后**按子值重定向**：
   能定读点时 → tables[] ``mode=trampoline_name_ptrs``
   （旁路 name_ptr 表 + 读点 ``ldr+bx``；原结构体不动；每槽有译用译、无译用原文）；
   否则 → 回落逐条 redirects[] / rows[]（与下项同一条路，禁止整模块死刑）。
4. **常规无指针 / 超短等兜底** → redirects[]（发现字面量站点）；定不出 → skip。

写入器只消费本计划，见 ``rows_writer``。
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path
from typing import Any, Callable

from .patch_table import (
    GBA_BASE,
    TABLE_AREA,
    TABLE_AREA_END,
    _choose_stride,
    _code_base,
    _fit,
    _groups_intact,
    _off,
)
from .table_relink import parse_ldr_literal_target
from .table_stride import find_literal_sites, plan_stride_rewrite
from .thumb_symexec import solve_site_auto

# stride → tables[] 扩步长；struct → 整块按值重定向（读点钩或逐条 redirect）
STRIDE_TABLE_TYPES = frozenset({"stride"})
STRUCT_TYPES = frozenset({"struct"})
TABLE_TYPES = STRIDE_TABLE_TYPES  # 兼容旧名：扩步长仅 stride
Encoder = Callable[[str], bytes]


def _write_disabled(mod: dict) -> bool:
    write = mod.get("write") or {}
    return (
        write.get("relocate") is False
        and write.get("replace") is False
        and write.get("slot") is False
    )


def _prepare_text(text: str, *, game_id: str = "", module: str = "") -> str:
    """折行：按模块 ``word_count`` / ``wrap_pages`` 重排（道具说明=9 字只插 ``\\n``）。"""
    if not text:
        return text
    import re

    from .charmap import normalize_zh_punct
    from .config_loader import module_wrap_kwargs
    from .text_wrap import wrap_text

    t = (
        text.replace("{\\n}", "\n")
        .replace("{\\p}", "\n\n")
        .replace("{\\l}", "\\l")
    )
    t = re.sub(r"(?<![\\])\{([^\\}]+)\}", r"\1", t)
    t = t.replace("\\p", "\n\n").replace("\\n", "\n")
    if not (game_id or module):
        return t
    try:
        return wrap_text(
            normalize_zh_punct(t),
            target_lang="zh-Hans",
            **module_wrap_kwargs(game_id, module or None),
        )
    except Exception:
        return t


def _encode(
    text: str,
    encoder: Encoder | None,
    *,
    game_id: str = "",
    module: str = "",
) -> bytes:
    if not text or encoder is None:
        return b""
    text = _prepare_text(text, game_id=game_id, module=module)
    try:
        raw = encoder(text)
    except Exception:
        return b""
    if raw and raw[-1] != 0xFF:
        raw += b"\xFF"
    return raw


def _entry_file_off(entry: dict) -> int | None:
    raw = entry.get("address")
    if raw in (None, ""):
        return None
    try:
        return _off(raw)
    except (TypeError, ValueError):
        return None


def _module_entries(entries: list[dict], module: str) -> list[dict]:
    return [e for e in entries if (e.get("module") or "") == module]


def _stride_geom(rom: bytes, mod: dict) -> tuple[int, int, int]:
    read = mod.get("read") or {}
    stride = int(read["stride"])
    declared = _off(mod["start"])
    end = _off(mod["end"])
    base = _code_base(rom, declared, stride)
    span = end - base + 1
    if stride <= 0 or span % stride:
        raise ValueError("区间不是步长整数倍")
    return base, stride, span // stride


def _rows_by_index(
    entries: list[dict],
    base: int,
    stride: int,
    count: int,
    name_off: int,
    encoder: Encoder | None,
    *,
    game_id: str = "",
) -> dict[int, bytes]:
    rows: dict[int, bytes] = {}
    for entry in entries:
        addr = _entry_file_off(entry)
        if addr is None:
            continue
        delta = addr - base - name_off
        if delta % stride or not (0 <= delta // stride < count):
            # 语料地址有时直接是条目起点（name_offset=0）
            delta2 = addr - base
            if delta2 % stride or not (0 <= delta2 // stride < count):
                continue
            idx = delta2 // stride
        else:
            idx = delta // stride
        text = entry.get("translated") or ""
        orig = entry.get("original") or ""
        if not text or text == orig:
            continue
        raw = _encode(
            text,
            encoder,
            game_id=game_id,
            module=str(entry.get("module") or ""),
        )
        if not raw:
            continue
        rows[idx] = raw
    return rows


def _try_fit_name(raw: bytes, cap: int) -> bytes | None:
    """等距槽：整字放入 cap，放不下返回 None（调用方改用原文）。"""
    fitted = _fit(raw, cap)
    if fitted is not None:
        return fitted
    body = raw[:-1] if raw.endswith(b"\xFF") else raw
    while body and not _groups_intact(body):
        body = body[:-1]
    if not body:
        return None
    return _fit(body + b"\xFF", cap)


def _plan_table_stride(
    rom: bytes,
    name: str,
    mod: dict,
    entries: list[dict],
    encoder: Encoder | None,
    cursor: int,
    *,
    game_id: str = "",
) -> tuple[dict | None, int, str | None]:
    """成功返回 (table_dict, new_cursor, None)；失败 (None, cursor, reason)。

    新步长 = 能放下最长译文的最小 ``old×2^k``；整表搬新区并改指针/移位。
    """
    try:
        base, stride, count = _stride_geom(rom, mod)
    except ValueError as exc:
        return None, cursor, str(exc)
    rows = _rows_by_index(
        entries, base, stride, count, 0, encoder, game_id=game_id
    )
    if not rows:
        return None, cursor, "没有译文"
    need = max(len(raw) for raw in rows.values())
    new_stride = _choose_stride(stride, need)
    if new_stride is None:
        new_stride = stride  # 最长已 ≤ 旧步长，仍搬表改基址
    return _finish_table(
        rom, name, base, stride, count, rows, new_stride,
        name_off=0, old_cap=stride, new_cap=new_stride,
        field_map=None, cursor=cursor,
    )


def _finish_table(
    rom: bytes,
    name: str,
    base: int,
    old_stride: int,
    count: int,
    rows: dict[int, bytes],
    new_stride: int,
    *,
    name_off: int,
    old_cap: int,
    cursor: int,
    field_map: dict | None,
    new_cap: int | None = None,
) -> tuple[dict | None, int, str | None]:
    if new_cap is None:
        new_cap = new_stride

    insns: list[dict] = []
    literals: list[dict] = []
    note = ""

    if new_stride != old_stride:
        try:
            plan = plan_stride_rewrite(rom, base, old_stride, new_stride)
        except ValueError as exc:
            # 非 2 幂比：仍写表与基址，步长指令记入 note，由后续补乘法
            plan = None
            note = f"stride_rewrite:{exc}"
        if plan is not None and plan.patches:
            ldrs: list[int] = []
            ok = True
            for patch in plan.patches:
                match = re.search(r"ldr 0x([0-9A-Fa-f]+)", patch.label)
                if not match:
                    ok = False
                    break
                ldrs.append(int(match.group(1), 16))
            muls_imm = any("muls stride" in (p.label or "") for p in plan.patches)
            if ok and len(ldrs) == len(plan.patches):
                old_gba = GBA_BASE + base
                lit_ok = True
                lit_offs: list[int] = []
                for ldr in ldrs:
                    lit = parse_ldr_literal_target(rom, ldr)
                    if lit is None or lit + 4 > len(rom):
                        lit_ok = False
                        break
                    if struct.unpack_from("<I", rom, lit)[0] != old_gba:
                        lit_ok = False
                        break
                    lit_offs.append(lit)
                if lit_ok:
                    accept = False
                    need = max((len(r) for r in rows.values()), default=0)
                    # movs#K+muls：乘法在 ldr 之前，改完后 symexec 仍可能报
                    # base+const；立即数已是 new_stride 即可信任。
                    if muls_imm and new_stride >= need:
                        accept = True
                        note = note or f"movs+muls stride→{new_stride}"
                    else:
                        sim = bytearray(rom)
                        for patch in plan.patches:
                            sim[patch.offset:patch.offset + len(patch.data)] = (
                                patch.data
                            )
                        want = new_stride
                        actuals = [
                            solve_site_auto(bytes(sim), ldr, expect=want).stride
                            for ldr in ldrs
                        ]
                        # 复合乘法（如 ×19）改一位移位可能得到 79 而非 76：
                        # 各站实测 K 一致且 ≥ 最长译文 → 采用实测步长
                        if (
                            actuals
                            and all(a == actuals[0] for a in actuals)
                            and actuals[0]
                            and actuals[0] >= need
                        ):
                            if actuals[0] != want:
                                note = (
                                    f"stride_rewrite实测K={actuals[0]}"
                                    f"（原目标{want}）"
                                )
                            new_stride = int(actuals[0])
                            new_cap = new_stride
                            accept = True
                        else:
                            bad = sum(1 for a in actuals if a != want)
                            note = f"改完 {bad} 处 K 不是 {want}（实测{actuals}）"
                    if accept:
                        for patch in plan.patches:
                            insns.append({
                                "off": f"0x{patch.offset:X}",
                                "bytes": patch.data.hex(" "),
                                "label": patch.label,
                            })
                        for lit in sorted(set(lit_offs)):
                            literals.append({"off": f"0x{lit:X}"})
                        insns.extend(
                            _copy_limit_patches(
                                rom, ldrs, old_stride, new_stride
                            )
                        )
                else:
                    note = note or "字面量对不上基址"
            else:
                note = note or "移位指令没有对应的 ldr"
        elif plan is not None and not plan.patches:
            note = note or f"没有 K 等于旧步长 {old_stride} 的站点"

    # 基址字面量：即使没改步长指令也要指到新区
    if not literals:
        for lit in find_literal_sites(rom, GBA_BASE + base):
            literals.append({"off": f"0x{lit:X}"})

    # 步长变了却改不了指令 → 半吊子表会读错槽，整张不写
    if new_stride != old_stride and not insns:
        return None, cursor, note or "步长已变但无可用移位指令"
    # 步长不变但找不到基址字面量：写了也没人读，跳过免占区
    if new_stride == old_stride and not literals:
        return None, cursor, "找不到表基址字面量"

    blob = bytearray()
    for i in range(count):
        src = base + i * old_stride
        prefix = bytes(rom[src:src + name_off])
        suffix_off = name_off + old_cap
        suffix = bytes(rom[src + suffix_off:src + old_stride])
        raw = rows.get(i)
        if raw is None:
            old_name = bytes(rom[src + name_off:src + suffix_off])
            if 0xFF in old_name:
                old_name = old_name[: old_name.index(0xFF) + 1]
            raw = old_name if old_name else b"\xFF"
        fitted = _try_fit_name(raw, new_cap)
        if fitted is None and new_stride == old_stride:
            # 等长等距：放不下就退回该槽原文
            old_name = bytes(rom[src + name_off:src + suffix_off])
            if 0xFF in old_name:
                old_name = old_name[: old_name.index(0xFF) + 1]
            fitted = _try_fit_name(
                old_name if old_name else b"\xFF", new_cap
            )
        if fitted is None:
            return None, cursor, "译文切不开整字"
        entry = prefix + fitted + suffix
        if len(entry) < new_stride:
            entry = entry + bytes(new_stride - len(entry))
        elif len(entry) > new_stride:
            entry = entry[:new_stride]
        blob += entry

    blob_size = len(blob)
    if cursor + blob_size > TABLE_AREA_END:
        return None, cursor, "补丁表区域满了"
    new_base = cursor
    cursor = (cursor + blob_size + 3) & ~3
    bin_name = f"plan_table_{name}.bin".replace("/", "_")
    # 文件名简化
    safe = re.sub(r"[^\w\-]+", "_", name)
    bin_name = f"plan_table_{safe}.bin"

    table = {
        "module": name,
        "old_base": f"0x{base:X}",
        "old_stride": old_stride,
        "new_base": f"0x{new_base:X}",
        "new_stride": new_stride,
        "count": count,
        "name_offset": name_off,
        "old_name_cap": old_cap,
        "new_name_cap": new_cap,
        "blob": f"gen/{bin_name}",
        "blob_name": bin_name,
        "blob_hex": blob.hex(),  # writer 可直接用；落盘时拆 bin
        "insns": insns,
        "literals": literals,
        "field_map": field_map or {},
        "note": note,
    }
    return table, cursor, None


def _copy_limit_patches(
    rom: bytes, ldrs: list[int], old_stride: int, new_stride: int
) -> list[dict]:
    """把站点附近的 ``cmp/movs #旧上限`` 放大到 ``new_stride-1``。

    物种名复制循环是 ``cmp r1, #0x0A``（最多 11 字节），步长改成 24 后
    仍按 11 截断会切断 F9 组 → 图鉴列表空白。
    """
    if new_stride <= old_stride:
        return []
    new_lim = min(new_stride - 1, 255)
    lo = max(old_stride - 1, 5)
    hi = max(old_stride + 6, 12)
    out: list[dict] = []
    seen: set[int] = set()
    for ldr in ldrs:
        for off in range(max(0, ldr - 0x40), min(len(rom) - 1, ldr + 0x60), 2):
            if off in seen:
                continue
            b0, b1 = rom[off], rom[off + 1]
            # cmp rn,#imm8 : 00101 nnn iiiiiiii → hi=0x28|rn
            # 只改 cmp 复制上限。不改 movs：摘要页等处 movs r3,#9 常是
            # 打印坐标/宽度（后接 bl），当成 len 改成 new_stride-1 会让特性名空白。
            if (b1 & 0xF8) == 0x28 and lo <= b0 <= hi and b0 < new_lim:
                seen.add(off)
                out.append({
                    "off": f"0x{off:X}",
                    "bytes": bytes([new_lim, b1]).hex(" "),
                    "label": f"cmp r{b1 & 7},#{b0:#x}→#{new_lim:#x}",
                })
    return out


def _struct_table_base_bus(modules: dict[str, Any]) -> set[int]:
    """Struct 表基址（总线）。这些字面量是整表入口，禁止当单条名字 pointer 改写。"""
    out: set[int] = set()
    for mod in modules.values():
        if not isinstance(mod, dict) or mod.get("type") not in STRUCT_TYPES:
            continue
        try:
            base = _off(mod["start"])
        except (KeyError, TypeError, ValueError):
            continue
        read = mod.get("read") or {}
        name_off = int(read.get("name_offset") or 0)
        out.add(GBA_BASE + base)
        if name_off:
            out.add(GBA_BASE + base + name_off)
    return out


def _packed_scan_pool_heads(
    rom: bytes,
    modules: dict[str, Any],
    entries: list[dict],
) -> set[int]:
    """Scan 模块里「打包串池」的首址（总线）。

    训练家 class 名等是连续 ``…FF 下一条…``，代码字面量常只挂池头
    （如 ``ポケモントレーナー`` @ 0x1C4A14）。把该字面量改成单条扩展译文
    后，后续 class 名全部失联 → 领航员训练家信息列表错位乱画。
    """
    by_mod: dict[str, list[dict]] = {}
    for e in entries:
        by_mod.setdefault(str(e.get("module") or ""), []).append(e)

    heads: set[int] = set()
    for name, mod in modules.items():
        if not isinstance(mod, dict) or mod.get("type") != "scan":
            continue
        ranges = mod.get("ranges")
        if not ranges:
            if mod.get("start") in (None, "") or mod.get("end") in (None, ""):
                continue
            ranges = [{"start": mod["start"], "end": mod["end"]}]
        ents = sorted(
            (e for e in by_mod.get(name, []) if _entry_file_off(e) is not None),
            key=lambda e: _entry_file_off(e) or 0,
        )
        for rg in ranges:
            try:
                lo = _off(rg["start"])
                hi = _off(rg["end"])
            except (KeyError, TypeError, ValueError):
                continue
            in_rg = [
                e for e in ents
                if (a := _entry_file_off(e)) is not None and lo <= a <= hi
            ]
            if len(in_rg) < 2:
                continue
            # 多数 class 名池是「FF 后紧接下一条」，偶有数字节垫片；
            # 不要求完美无缝——只要同 range 内 ≥2 条，池头字面量就不能单条改写。
            near = 0
            for i in range(len(in_rg) - 1):
                a = _entry_file_off(in_rg[i])
                b = _entry_file_off(in_rg[i + 1])
                if a is None or b is None:
                    continue
                end = rom.find(0xFF, a, min(a + 256, len(rom)))
                if end >= 0 and end < b <= end + 16:
                    near += 1
            if near < max(1, (len(in_rg) - 1) // 2):
                continue
            head = _entry_file_off(in_rg[0])
            if head is not None:
                heads.add(GBA_BASE + head)
            heads.add(GBA_BASE + lo)
    return heads


def _ptr_sources_for_entry(
    rom: bytes,
    entry: dict,
    *,
    text_spans: list[tuple[int, int]] | None,
    lz_spans: list | None,
    struct_bases: set[int] | None = None,
) -> list[str]:
    from .policy import expand_pointer_sources
    from .translate_plan import _ptr_sources

    addr = _entry_file_off(entry)
    if addr is None:
        return []
    raw = list(_ptr_sources(entry))
    module_id = entry.get("module") or ""
    offs = expand_pointer_sources(
        rom,
        addr,
        raw,
        category=module_id,
        original=entry.get("original") or "",
        expected_pointer=GBA_BASE + addr,
        lz_spans=lz_spans,
        text_spans=text_spans,
    )
    # 树果名[0] 等：名字嵌在表头，extract 会把「=gBerries」整表字面量当成
    # 第 0 条的 pointer_sources；逐条 relocate 会改掉表基 → 元数据全毁。
    bases = struct_bases or set()
    if bases:
        kept: list[int] = []
        for p in offs:
            if p + 4 > len(rom):
                continue
            cur = struct.unpack_from("<I", rom, p)[0]
            if cur in bases:
                continue
            kept.append(p)
        offs = kept
    return [f"0x{p:X}" for p in offs]


def build_write_plan(
    rom: bytes,
    texts_path: Path,
    entries: list[dict],
    *,
    encoder: Encoder | None,
    game_id: str = "",
    out_path: Path | None = None,
) -> dict:
    """生成写入计划。``entries`` 须已带 translated / original / module。"""
    from .extract import trusted_lz_spans
    from .policy import collect_entry_text_spans
    from .translate_plan import dedupe_entries_by_id

    texts = json.loads(Path(texts_path).read_text(encoding="utf-8"))
    modules: dict[str, Any] = texts.get("modules") or {}
    entries = dedupe_entries_by_id(list(entries))
    lz_spans = trusted_lz_spans(rom)
    text_spans = collect_entry_text_spans(entries)
    # 整表/打包池基址字面量：禁止当单条 pointer/redirect 改写
    protected_bases = _struct_table_base_bus(modules) | _packed_scan_pool_heads(
        rom, modules, entries
    )

    tables: list[dict] = []
    rows: list[dict] = []
    redirects: list[dict] = []
    skip: list[dict] = []
    table_notes: list[tuple[str, str]] = []
    cursor = TABLE_AREA

    # 仅 stride 算「整表已写入」；struct 只有读点钩成功才加入，失败回落逐条 redirect
    table_modules: set[str] = {
        n for n, m in modules.items()
        if isinstance(m, dict) and m.get("type") in STRIDE_TABLE_TYPES
    }
    handled_ids: set[str] = set()

    for name, mod in modules.items():
        if not isinstance(mod, dict):
            continue
        if _write_disabled(mod):
            for e in _module_entries(entries, name):
                eid = str(e.get("id") or "")
                skip.append({"id": eid, "module": name, "reason": "write_disabled"})
                if eid:
                    handled_ids.add(eid)
            continue

        is_stride = mod.get("type") in STRIDE_TABLE_TYPES
        is_struct = mod.get("type") in STRUCT_TYPES
        if not is_stride and not is_struct:
            continue

        mod_entries = _module_entries(entries, name)
        live = [
            e for e in mod_entries
            if not e.get("_reject")
            and (e.get("translated") or "")
            and (e.get("translated") or "") != (e.get("original") or "")
        ]

        if is_struct:
            from .struct_trampoline import (
                plan_struct_same_stride_clone,
                plan_struct_trampoline,
            )

            # 主路径：整块克隆（嵌名字子值 + 改结构体基址字面量）。
            # trampoline「子值旁路」仅当克隆失败（无字面量 / 译文全超槽等）时回落。
            table, cursor, err = plan_struct_same_stride_clone(
                rom, name, mod, mod_entries, encoder, cursor,
            )
            if table is None:
                clone_err = err
                table2, cursor2, err2 = plan_struct_trampoline(
                    rom, name, mod, mod_entries, encoder, cursor,
                )
                if table2 is not None:
                    table, cursor = table2, cursor2
                    table_notes.append(
                        (
                            name,
                            f"整块克隆未成，回落 trampoline（原：{clone_err}）",
                        )
                    )
                else:
                    table_notes.append(
                        (
                            name,
                            f"整块克隆与 trampoline 均失败"
                            f"（{clone_err}; {err2}），回落逐条",
                        )
                    )
                    for e in mod_entries:
                        if e.get("_reject"):
                            eid = str(e.get("id") or "")
                            skip.append(
                                {"id": eid, "module": name, "reason": "reject"}
                            )
                            if eid:
                                handled_ids.add(eid)
                    # 不 continue：留给下方 rows/redirects
            if table is not None:
                for e in mod_entries:
                    eid = str(e.get("id") or "")
                    if eid:
                        handled_ids.add(eid)
                    if e.get("_reject"):
                        skip.append({"id": eid, "module": name, "reason": "reject"})
                tables.append(table)
                table_modules.add(name)
                if table.get("note"):
                    table_notes.append((name, str(table["note"])))
            continue

        for e in mod_entries:
            eid = str(e.get("id") or "")
            if eid:
                handled_ids.add(eid)
            if e.get("_reject"):
                skip.append({"id": eid, "module": name, "reason": "reject"})

        table, cursor, err = _plan_table_stride(
            rom, name, mod, live, encoder, cursor, game_id=game_id,
        )
        if table is None:
            table_notes.append((name, err or "失败"))
            # 扩步长失败：撤销 handled，回落逐条重定向（超短/无指针兜底）
            for e in mod_entries:
                eid = str(e.get("id") or "")
                if eid:
                    handled_ids.discard(eid)
            table_modules.discard(name)
            for e in mod_entries:
                if e.get("_reject"):
                    eid = str(e.get("id") or "")
                    skip.append({"id": eid, "module": name, "reason": "reject"})
                    if eid:
                        handled_ids.add(eid)
        else:
            tables.append(table)
            if table.get("note"):
                table_notes.append((name, str(table["note"])))
            # 扩步长后仍塞不进新槽的 → 从整表摘出，改走逐条重定向
            new_cap = int(table.get("new_name_cap") or table.get("new_stride") or 0)
            if new_cap:
                for e in live:
                    raw = _encode(
                        e.get("translated") or "",
                        encoder,
                        game_id=game_id,
                        module=name,
                    )
                    if raw and _try_fit_name(raw, new_cap) is None:
                        eid = str(e.get("id") or "")
                        if eid:
                            handled_ids.discard(eid)
                        table_notes.append((
                            name,
                            f"超短槽回落重定向 id={eid}",
                        ))

    for entry in entries:
        eid = str(entry.get("id") or "")
        if eid and eid in handled_ids:
            continue
        module = entry.get("module") or ""
        mod = modules.get(module) if module in modules else {}
        if isinstance(mod, dict) and _write_disabled(mod):
            skip.append({"id": eid, "module": module, "reason": "write_disabled"})
            continue
        if entry.get("_reject"):
            skip.append({"id": eid, "module": module, "reason": "reject"})
            continue
        translated = entry.get("translated") or ""
        original = entry.get("original") or ""
        if not translated or translated == original:
            skip.append({"id": eid, "module": module, "reason": "no_translation"})
            continue
        # 表模块已处理；落单条目若仍挂在表模块上（无译文已 skip）则忽略
        if module in table_modules:
            continue

        body = _encode(
            translated, encoder, game_id=game_id, module=module,
        )
        if not body:
            skip.append({"id": eid, "module": module, "reason": "encode_failed"})
            continue

        # S2：正文目标必须是真 PCS。WindowTemplate 等「xx 00 yy 00 FF」会被
        # looks_like_jp_text 误收成「み お 」；改指针 → 领航员训练家信息爆错。
        # 列对齐 UI（write.space_pad）放宽 00 密度，仍拒 is_struct_like_pcs。
        addr = _entry_file_off(entry)
        if addr is not None:
            from .jp_pcs import looks_like_jp_text
            from .policy import is_struct_like_pcs

            end = rom.find(0xFF, addr, addr + 201)
            if end < 0:
                skip.append({"id": eid, "module": module, "reason": "bad_text_target"})
                continue
            raw = bytes(rom[addr : end + 1])
            space_pad = bool((mod.get("write") or {}).get("space_pad"))
            if is_struct_like_pcs(raw) or not looks_like_jp_text(
                raw, allow_space_pad=space_pad
            ):
                skip.append({"id": eid, "module": module, "reason": "bad_text_target"})
                continue

        ptrs = _ptr_sources_for_entry(
            rom,
            entry,
            text_spans=text_spans,
            lz_spans=lz_spans,
            struct_bases=protected_bases,
        )
        if ptrs:
            rows.append({
                "id": eid,
                "module": module,
                "kind": "pointer",
                "address": entry.get("address"),
                "body_hex": body.hex(" "),
                "pointer_sources": ptrs,
            })
            continue

        # 无登记指针：全 ROM 发现后再走同一套 filter（禁止裸 find 直写）
        filtered: list[int] = []
        if addr is not None:
            from .policy import discover_pointer_sources, filter_pointer_sources

            discovered = discover_pointer_sources(rom, addr)
            filtered = filter_pointer_sources(
                rom,
                discovered,
                addr,
                category=module,
                original=original,
                expected_pointer=GBA_BASE + addr,
                lz_spans=lz_spans,
                text_spans=text_spans,
            )
            # 与 rows 相同：整表/打包池基址字面量不得进 redirects
            if protected_bases:
                filtered = [
                    p for p in filtered
                    if p + 4 <= len(rom)
                    and struct.unpack_from("<I", rom, p)[0] not in protected_bases
                ]
        if filtered:
            redirects.append({
                "id": eid,
                "module": module,
                "kind": "redirect",
                "address": entry.get("address"),
                "body_hex": body.hex(" "),
                "sites": [
                    {"off": f"0x{p:X}", "mode": "literal"} for p in filtered
                ],
            })
        else:
            skip.append({
                "id": eid,
                "module": module,
                "reason": "unresolved_redirect",
            })

    plan = {
        "game_id": game_id,
        "tables": tables,
        "rows": rows,
        "redirects": redirects,
        "skip": skip,
        "table_notes": [{"module": n, "note": m} for n, m in table_notes],
        "summary": {
            "tables": len(tables),
            "rows": len(rows),
            "redirects": len(redirects),
            "skip": len(skip),
            "skip_unresolved": sum(
                1 for s in skip if s.get("reason") == "unresolved_redirect"
            ),
            "table_area_cursor": f"0x{cursor:X}",
        },
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # 落盘时去掉 blob_hex 的巨型重复：bins 旁路；保留 hex 以便单文件自洽
        slim = dict(plan)
        out_path.write_text(
            json.dumps(slim, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return plan


def plan_to_translate_build_mirror(plan: dict, entries: list[dict]) -> dict:
    """兼容旧 inject 路径的调试镜像（无 keep 假通路）。"""
    by_id = {str(e.get("id") or ""): e for e in entries}
    out_entries: list[dict] = []
    for row in plan.get("rows") or []:
        e = by_id.get(row.get("id") or "", {})
        out_entries.append({
            "id": row.get("id"),
            "type": "relocate",
            "address": row.get("address") or e.get("address"),
            "module": row.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": row.get("body_hex"),
            "pointer_sources": row.get("pointer_sources"),
        })
    for row in plan.get("redirects") or []:
        e = by_id.get(row.get("id") or "", {})
        out_entries.append({
            "id": row.get("id"),
            "type": "redirect",
            "address": row.get("address") or e.get("address"),
            "module": row.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": row.get("body_hex"),
            "redirect_sites": row.get("sites"),
        })
    for s in plan.get("skip") or []:
        e = by_id.get(s.get("id") or "", {})
        out_entries.append({
            "id": s.get("id"),
            "type": "skip",
            "address": e.get("address", ""),
            "module": s.get("module"),
            "original": e.get("original", ""),
            "translated": e.get("translated", ""),
            "original_hex": e.get("original_hex", ""),
            "target_hex": e.get("original_hex", ""),
            "reason": s.get("reason"),
        })
    return {
        "game_id": plan.get("game_id"),
        "count": len(out_entries),
        "entries": out_entries,
        "write_plan_summary": plan.get("summary"),
    }
