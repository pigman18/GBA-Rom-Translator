#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
texts_patcher.py
================
按 ``configs/<game_id>.yaml`` 的 ``texts.modules`` 从 ROM 导出 ``texts.json``
（预置产物，不进 Meowth 流水线）。

用法：
  python texts_patcher.py export <rom.gba>
  python texts_patcher.py export <rom.gba> --module 物种名
  python texts_patcher.py scan <rom.gba> キーワード [--start 0x..] [--end 0x..]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CONFIGS_DIR = SCRIPT_DIR / "configs"
OUT_DIR = SCRIPT_DIR / "out"

BASE = 0x08000000
EOS = 0xFF
MAX_PCS = 512

# entries 字段顺序（便于人工查看；缺省键靠后）
ENTRY_KEY_ORDER = (
    "id",
    "module",
    "address",
    "byte_length",
    "original",
    "original_hex",
    "translated",
    "table_index",
    "table_base",
    "is_fixed_table",
    "is_pointer_based",
    "pointer_sources",
    "pointer_addresses",
)

# 保证可 import meowth（decode / scan）
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def parse_addr(v: Any) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 16) if s else 0


def parse_int(v: Any) -> int:
    """十进制，或 ``0x`` 前缀十六进制（stride 等）。"""
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    if not s:
        return 0
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 10)


def make_entry_id(game_code: str, address_hex: str, original_hex: str) -> str:
    """``{game_code.lower()}_`` + md5(address+hex) 前 12 位（与现算法同构，前缀动态）。"""
    raw = f"{address_hex}{original_hex.replace(' ', '').replace(chr(10), '')}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{game_code.lower()}_{digest}"


def load_yaml_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError as e:
        raise SystemExit(
            "需要 PyYAML：pip install pyyaml"
        ) from e
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid config: {path}")
    if "texts" not in data or not isinstance(data["texts"], dict):
        raise ValueError(f"config missing texts: {path}")
    if "modules" not in data["texts"]:
        raise ValueError(f"config missing texts.modules: {path}")
    return data


def resolve_config(rom_path: Path, config: Path | None) -> Path:
    if config is not None:
        return config
    # 文件名 stem 优先，否则按 ROM 头 game code 映射
    stem = rom_path.stem
    cand = CONFIGS_DIR / f"{stem}.yaml"
    if cand.is_file():
        return cand
    rom = rom_path.read_bytes()
    if len(rom) >= 0xB0:
        code = rom[0xAC:0xB0].decode("ascii", errors="replace")
        for p in CONFIGS_DIR.glob("*.yaml"):
            try:
                cfg = load_yaml_config(p)
            except Exception:
                continue
            if str(cfg.get("game_code") or "").upper() == code.upper():
                return p
    raise FileNotFoundError(
        f"no yaml config for {rom_path}; pass --config"
    )


def identify_rom(rom: bytes) -> str:
    if len(rom) < 0xB0:
        raise ValueError("ROM too small")
    return rom[0xAC:0xB0].decode("ascii", errors="replace")


def _slot_text(rom: bytes, off: int, stride: int) -> tuple[str, bytes]:
    from meowth.jp_pcs import decode_pcs

    slot = rom[off : off + stride]
    if 0xFF not in slot:
        return "", slot
    end = slot.index(0xFF)
    raw = slot[: end + 1]
    return decode_pcs(raw), raw


def _stamp(
    e: dict,
    *,
    mid: str,
    game_code: str,
) -> dict:
    addr = e.get("address") or ""
    ohex = e.get("original_hex") or ""
    e["id"] = make_entry_id(game_code, addr, ohex)
    e["module"] = mid
    e.setdefault("translated", "")
    e.setdefault("pointer_sources", [])
    e.setdefault("pointer_addresses", [])
    e.pop("category", None)
    e.pop("_axvj_module", None)
    return _order_entry(e)


def _order_entry(e: dict) -> dict:
    """按 ENTRY_KEY_ORDER 重排；未知键保持相对顺序附在末尾。"""
    ordered: dict[str, Any] = {}
    for k in ENTRY_KEY_ORDER:
        if k in e:
            ordered[k] = e[k]
    for k, v in e.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def default_output_path(game_id: str, module: str | None = None) -> Path:
    """``configs/<game_id>/translate/texts.json`` 或单模块 ``texts_<模块>.json``。"""
    base = REPO_ROOT / "configs" / game_id / "translate"
    if module:
        return base / f"texts_{module}.json"
    return base / "texts.json"


def _modules_as_dict(modules_list: list[dict]) -> dict[str, dict]:
    """yaml ``texts.modules`` list → ``{id: meta}``（id 不进 meta）。"""
    out: dict[str, dict] = {}
    for m in modules_list:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("id") or "").strip()
        if not mid:
            continue
        out[mid] = {k: v for k, v in m.items() if k != "id"}
    return out


def extract_stride(rom: bytes, mod: dict, game_code: str) -> list[dict]:
    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    # YAML 写 38 = 十进制 38；定长槽请写 0x38 或 56
    stride = parse_int((mod.get("read") or {}).get("stride") or 0)
    if not stride or end < start:
        return []
    # end 含尾（与其它固定表一致）
    count = (end - start + 1) // stride
    out: list[dict] = []
    table_ptr = BASE + start
    for i in range(count):
        off = start + i * stride
        text, raw = _slot_text(rom, off, stride)
        if not text:
            continue
        e = {
            "address": f"0x{BASE + off:08X}",
            "table_index": i,
            "table_base": f"0x{table_ptr:08X}",
            "byte_length": stride,
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "is_pointer_based": False,
            "is_fixed_table": True,
            "pointer_sources": [],
            "pointer_addresses": [],
        }
        out.append(_stamp(e, mid=mid, game_code=game_code))
    return out


def extract_struct(rom: bytes, mod: dict, game_code: str) -> list[dict]:
    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    read = mod.get("read") or {}
    entry_size = int(read.get("entry_size") or 0)
    name_stride = int(read.get("name_stride") or 0)
    if not entry_size or not name_stride or end < start:
        return []
    count = (end - start + 1) // entry_size
    out: list[dict] = []
    table_ptr = BASE + start
    for i in range(count):
        off = start + i * entry_size
        text, raw = _slot_text(rom, off, name_stride)
        if not text or set(text) <= {"？", "ー", "-", " "}:
            continue
        e = {
            "address": f"0x{BASE + off:08X}",
            "table_index": i,
            "table_base": f"0x{table_ptr:08X}",
            "byte_length": name_stride,
            "original_hex": raw.hex(" "),
            "original": text,
            "translated": "",
            "is_pointer_based": False,
            "is_fixed_table": True,
            "pointer_sources": [],
            "pointer_addresses": [],
        }
        out.append(_stamp(e, mid=mid, game_code=game_code))
    return out


def extract_stride_ptr(rom: bytes, mod: dict, game_code: str) -> list[dict]:
    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    ptr_stride = int((mod.get("read") or {}).get("stride") or 4)
    if end < start:
        return []
    from meowth.jp_pcs import decode_pcs

    out: list[dict] = []
    i = 0
    lit = start
    while lit + 4 <= end + 1 and lit + 4 <= len(rom):
        ptr = struct.unpack_from("<I", rom, lit)[0]
        if BASE <= ptr < BASE + len(rom):
            so = ptr - BASE
            eos = rom.find(b"\xFF", so, so + 24)
            if eos >= 0:
                raw = rom[so : eos + 1]
                text = decode_pcs(raw)
                if text:
                    e = {
                        "address": f"0x{BASE + so:08X}",
                        "table_index": i,
                        "table_base": f"0x{BASE + start:08X}",
                        "byte_length": len(raw),
                        "original_hex": raw.hex(" "),
                        "original": text,
                        "translated": "",
                        "is_pointer_based": True,
                        "is_fixed_table": False,
                        "pointer_sources": [f"0x{BASE + lit:08X}"],
                        "pointer_addresses": [f"0x{BASE + lit:08X}"],
                    }
                    out.append(_stamp(e, mid=mid, game_code=game_code))
        lit += ptr_stride
        i += 1
    return out


def _module_bands(mod: dict) -> list[list[str]]:
    ranges = mod.get("ranges")
    bands: list[list[str]] = []
    if ranges:
        for r in ranges:
            if isinstance(r, dict):
                lo, hi = parse_addr(r.get("start")), parse_addr(r.get("end"))
            elif isinstance(r, (list, tuple)) and len(r) >= 2:
                lo, hi = parse_addr(r[0]), parse_addr(r[1])
            else:
                continue
            if hi >= lo > 0:
                bands.append([f"0x{lo:X}", f"0x{hi:X}"])
    if not bands:
        lo, hi = parse_addr(mod.get("start")), parse_addr(mod.get("end"))
        if hi >= lo > 0:
            bands.append([f"0x{lo:X}", f"0x{hi:X}"])
    return bands


def extract_scan(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
) -> list[dict]:
    from meowth.extract import (
        SCRIPT_BANK_MIN,
        TITLE_LZ_BAND,
        read_pcs,
        scan_addr_bands,
    )
    from meowth.jp_pcs import decode_pcs, looks_like_jp_text
    from meowth.policy import looks_like_translatable

    mid = mod["id"]
    bands = _module_bands(mod)
    if not bands:
        return []
    min_bl = mod.get("min_byte_length")
    max_bl = mod.get("max_byte_length")

    if ptr_index is not None:
        out: list[dict] = []
        seen: set[int] = set()

        def _parse(v: object) -> int:
            if isinstance(v, int):
                return v
            s = str(v).strip().lower().replace("0x", "")
            return int(s, 16) if s else 0

        for lo_s, hi_s in bands:
            lo, hi = _parse(lo_s), _parse(hi_s)
            if hi < lo:
                continue
            a = lo
            while a <= hi:
                b = rom[a]
                if b == 0xFF or b == 0x00 or b >= 0xF7:
                    a += 1
                    continue
                raw = read_pcs(rom, a, 512)
                if raw is None:
                    a += 1
                    continue
                end = a + len(raw) - 1
                if looks_like_jp_text(raw):
                    text = decode_pcs(raw)
                    if looks_like_translatable(text, len(raw)):
                        if a < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= a < TITLE_LZ_BAND[1]:
                            a = end + 1
                            continue
                        if a in seen:
                            a = end + 1
                            continue
                        bl = len(raw)
                        if min_bl is not None and bl < int(min_bl):
                            a = end + 1
                            continue
                        if max_bl is not None and bl > int(max_bl):
                            a = end + 1
                            continue
                        ptrs = list(ptr_index.get(a, []))
                        seen.add(a)
                        e = {
                            "address": f"0x{BASE + a:08X}",
                            "original": text,
                            "original_hex": raw.hex(" "),
                            "byte_length": bl,
                            "is_pointer_based": bool(ptrs),
                            "pointer_sources": [
                                f"0x{BASE + q:08X}" for q in ptrs
                            ],
                            "pointer_addresses": [
                                f"0x{BASE + q:08X}" for q in ptrs
                            ],
                        }
                        out.append(_stamp(e, mid=mid, game_code=game_code))
                a = end + 1
        return out

    out = []
    for e in scan_addr_bands(rom, bands):
        bl = int(e.get("byte_length") or 0)
        if min_bl is not None and bl < int(min_bl):
            continue
        if max_bl is not None and bl > int(max_bl):
            continue
        out.append(_stamp(dict(e), mid=mid, game_code=game_code))
    return out


def extract_module(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
) -> list[dict]:
    rtype = str(mod.get("type") or "scan")
    if rtype == "stride":
        return extract_stride(rom, mod, game_code)
    if rtype == "struct":
        return extract_struct(rom, mod, game_code)
    if rtype in ("stride_ptr", "ptr_stride"):
        return extract_stride_ptr(rom, mod, game_code)
    if rtype in ("scan", "addr_bands"):
        return extract_scan(rom, mod, game_code, ptr_index=ptr_index)
    # needle/prefix/pointer: corpus already in texts.json; no Meowth re-scan
    return []


def _build_ptr_index(rom: bytes) -> dict[int, list[int]]:
    ptr_index: dict[int, list[int]] = {}
    n = len(rom)
    o = 0
    while o + 4 <= n:
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + n:
            so = v - BASE
            if so >= 0x100000 and so < n:
                ptr_index.setdefault(so, []).append(o)
        o += 4
    return ptr_index


def export_texts(
    rom_path: Path,
    *,
    config_path: Path | None = None,
    output: Path | None = None,
    module: str | None = None,
) -> Path:
    cfg_path = resolve_config(rom_path, config_path)
    cfg = load_yaml_config(cfg_path)
    game_id = str(cfg.get("game_id") or rom_path.stem)
    game_code = str(cfg.get("game_code") or "").strip()
    if not game_code:
        raise ValueError(f"config missing game_code: {cfg_path}")

    rom = rom_path.read_bytes()
    rom_code = identify_rom(rom)
    if rom_code.upper() != game_code.upper():
        print(
            f"[!] ROM game_code {rom_code!r} != config {game_code!r}",
            file=sys.stderr,
        )

    modules = list(cfg["texts"]["modules"] or [])
    modules_dict = _modules_as_dict(modules)
    if module:
        modules = [m for m in modules if (m.get("id") or "") == module]
        if not modules:
            known = list(modules_dict.keys())
            raise SystemExit(
                f"module not found: {module!r}; known={known}"
            )
        modules_dict = _modules_as_dict(modules)

    need_ptr = any(
        str(m.get("type") or "scan") in ("scan", "addr_bands") for m in modules
    )
    ptr_index: dict[int, list[int]] | None = None
    if need_ptr:
        print("[i] building pointer index…")
        ptr_index = _build_ptr_index(rom)

    entries: list[dict] = []
    seen_addr: set[str] = set()
    skipped: dict[str, int] = {}

    for mod in modules:
        mid = mod.get("id") or ""
        rtype = str(mod.get("type") or "scan")
        chunk = extract_module(rom, mod, game_code, ptr_index=ptr_index)
        if not chunk and rtype in ("needle", "prefix", "pointer"):
            skipped[rtype] = skipped.get(rtype, 0) + 1
            continue
        n = 0
        for e in chunk:
            addr = e.get("address") or ""
            if addr and addr in seen_addr:
                continue
            if addr:
                seen_addr.add(addr)
            entries.append(_order_entry(e))
            n += 1
        print(f"  [{mid}] type={rtype} -> {n}")

    if skipped:
        print(f"[i] skipped module types (not implemented): {skipped}")

    out_path = output or default_output_path(game_id, module=module)
    # modules 只来自 yaml（不与旧 texts.json 合并，避免改 label/id 后残留）
    doc = {
        "game": game_id,
        "game_id": game_id,
        "source_lang": "ja",
        "modules": modules_dict,
        "count": len(entries),
        "entries": entries,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] {len(entries)} entries / {len(modules_dict)} modules -> {out_path}")
    print(f"     config={cfg_path}")
    return out_path


def _to_file_offset(addr: int | None, rom_len: int, *, default: int) -> int:
    """接受文件偏移或 0x08xxxxxx VA；None → default。"""
    if addr is None:
        return default
    a = int(addr)
    if a >= BASE:
        a -= BASE
    if a < 0:
        a = 0
    if a >= rom_len:
        a = rom_len - 1 if rom_len else 0
    return a


def _encode_keyword_pcs(keyword: str) -> bytes | None:
    """把纯字形关键字编成 PCS 字节；含无法编码的字符则返回 None。"""
    from meowth.jp_pcs import CHAR_TO_BYTE

    out = bytearray()
    for ch in keyword:
        if ch not in CHAR_TO_BYTE:
            return None
        out.append(CHAR_TO_BYTE[ch])
    return bytes(out) if out else None


def _module_scan_bounds(cfg: dict, module_id: str) -> tuple[int, int] | None:
    """取 yaml 模块 start/end 或 ranges 并集，作 scan 默认区间。"""
    mods = (cfg.get("texts") or {}).get("modules") or []
    mod = next((m for m in mods if (m.get("id") or "") == module_id), None)
    if not mod:
        return None
    bands = _module_bands(mod)
    if not bands:
        return None
    los = [parse_addr(a) for a, _ in bands]
    his = [parse_addr(b) for _, b in bands]
    return min(los), max(his)


def _ff_span_at(rom: bytes, hit: int, lo: int, hi: int) -> tuple[int, int] | None:
    """含 hit 的句子：上一 FF 之后起，到下一 FF（含）止。"""
    prev = rom.rfind(EOS, 0, hit)
    so = prev + 1 if prev >= 0 else 0
    if so < lo:
        # 区间外的串头：若整句与 [lo,hi] 相交仍保留
        pass
    nxt = rom.find(EOS, hit, min(len(rom), hit + MAX_PCS * 2))
    if nxt < 0:
        return None
    if nxt < lo or so > hi:
        return None
    return so, nxt


def scan_keyword(
    rom_path: Path,
    keyword: str,
    *,
    start: int | str | None = None,
    end: int | str | None = None,
    output: Path | None = None,
    max_hits: int = 200,
    config_path: Path | None = None,
    module: str | None = None,
) -> list[dict]:
    """在 [start, end] 内按「上一 FF → 下一 FF」切句，匹配含 keyword 的句子。

    规则（固定）：
      句子 = rom[prev_FF+1 : next_FF]（含结尾 FF）
      解码后做子串匹配。
    """
    from meowth.jp_pcs import decode_pcs

    if not keyword:
        raise SystemExit("keyword must not be empty")

    rom = rom_path.read_bytes()
    n = len(rom)

    default_lo, default_hi = 0, (n - 1 if n else 0)
    if module:
        cfg_path = resolve_config(rom_path, config_path)
        cfg = load_yaml_config(cfg_path)
        bounds = _module_scan_bounds(cfg, module)
        if not bounds:
            raise SystemExit(f"module has no address range: {module!r}")
        default_lo, default_hi = bounds
        print(
            f"[i] module={module!r} bounds "
            f"0x{default_lo:X}..0x{default_hi:X} ({cfg_path.name})"
        )

    lo = _to_file_offset(
        parse_addr(start) if start is not None else None,
        n,
        default=default_lo,
    )
    hi = _to_file_offset(
        parse_addr(end) if end is not None else None,
        n,
        default=default_hi,
    )
    if hi < lo:
        lo, hi = hi, lo

    needle = _encode_keyword_pcs(keyword)
    hits: list[dict] = []
    seen: set[int] = set()

    def _add_span(so: int, eo: int, *, match_at: int | None = None) -> None:
        if so in seen:
            return
        if eo < so or eo >= n:
            return
        raw = bytes(rom[so : eo + 1])
        if len(raw) < 2 or raw[-1] != EOS:
            return
        if len(raw) > MAX_PCS + 1:
            return
        text = decode_pcs(raw)
        if keyword not in text:
            return
        seen.add(so)
        hits.append(
            {
                "address": f"0x{BASE + so:08X}",
                "end_address": f"0x{BASE + eo:08X}",
                "file_offset": f"0x{so:08X}",
                "match_offset": (
                    f"0x{BASE + match_at:08X}" if match_at is not None else None
                ),
                "byte_length": len(raw),
                "original": text,
                "original_hex": raw.hex(" "),
            }
        )

    # 快路径：关键字可编码 → 找字节命中，再取所在 FF 句
    if needle is not None:
        pos = lo
        while pos <= hi and len(hits) < max_hits:
            i = rom.find(needle, pos, hi + 1)
            if i < 0:
                break
            span = _ff_span_at(rom, i, lo, hi)
            if span:
                _add_span(span[0], span[1], match_at=i)
            pos = i + 1
    else:
        # 关键字含无法编码字符：顺序扫所有 FF 句再匹配解码文本
        # 从 lo 前一个 FF 之后开始，避免截断句首
        prev = rom.rfind(EOS, 0, lo)
        cur = prev + 1 if prev >= 0 else 0
        while cur <= hi and len(hits) < max_hits:
            eo = rom.find(EOS, cur, min(n, hi + MAX_PCS + 1))
            if eo < 0:
                break
            if eo >= lo:  # 与搜索区间有交集才报
                _add_span(cur, eo)
            cur = eo + 1

    print(
        f"[scan] keyword={keyword!r} range=0x{lo:X}..0x{hi:X} "
        f"hits={len(hits)}" + (" (truncated)" if len(hits) >= max_hits else "")
    )
    if not hits and needle is None:
        print("[!] 关键字含无法编成 PCS 的字符，已跳过字节搜索")
    if not hits:
        print(
            "[!] 无命中。请确认是 ROM 日文原文（例：てきを はたいて，"
            "不是 あいてを たたいて）"
        )
    for h in hits:
        preview = h["original"].replace("\n", "\\n")
        if len(preview) > 80:
            preview = preview[:77] + "..."
        print(f"  {h['address']} .. {h['end_address']}  {preview}")

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "keyword": keyword,
            "start": f"0x{lo:08X}",
            "end": f"0x{hi:08X}",
            "module": module,
            "count": len(hits),
            "hits": hits,
        }
        output.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[ok] wrote {output}")

    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="texts_patcher: export / scan")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("export", help="按 yaml texts.modules 导出 texts.json")
    p_ex.add_argument("rom", type=Path)
    p_ex.add_argument(
        "--config",
        type=Path,
        default=None,
        help="yaml 配置（默认 configs/<rom_stem>.yaml 或按 game_code 匹配）",
    )
    p_ex.add_argument(
        "--module",
        default=None,
        help="只导出指定模块（输出 texts_<模块名>.json，便于测试）",
    )
    p_ex.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出路径（默认 configs/<game_id>/translate/texts.json）",
    )

    p_sc = sub.add_parser(
        "scan",
        help="按关键字搜索含该字串的 PCS 语句及地址",
    )
    p_sc.add_argument("rom", type=Path)
    p_sc.add_argument("keyword", help="要搜索的原文关键字（日文 PCS 解码后子串）")
    p_sc.add_argument(
        "--start",
        default=None,
        help="起始地址（文件偏移或 0x08xxxxxx）；默认可被 --module 覆盖，否则 0",
    )
    p_sc.add_argument(
        "--end",
        default=None,
        help="结束地址（含）；默认可被 --module 覆盖，否则 ROM 末尾",
    )
    p_sc.add_argument(
        "--module",
        default=None,
        help="用 yaml 中该模块的 start/end（或 ranges 并集）作为默认搜索区间",
    )
    p_sc.add_argument(
        "--config",
        type=Path,
        default=None,
        help="yaml 配置（配合 --module）",
    )
    p_sc.add_argument(
        "--max-hits",
        type=int,
        default=200,
        help="最多命中条数（默认 200）",
    )
    p_sc.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="可选：把命中列表写成 JSON",
    )

    args = ap.parse_args(argv)
    if args.cmd == "export":
        export_texts(
            args.rom,
            config_path=args.config,
            output=args.output,
            module=args.module,
        )
        return 0
    if args.cmd == "scan":
        scan_keyword(
            args.rom,
            args.keyword,
            start=args.start,
            end=args.end,
            output=args.output,
            max_hits=args.max_hits,
            config_path=args.config,
            module=args.module,
        )
        return 0
    ap.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
