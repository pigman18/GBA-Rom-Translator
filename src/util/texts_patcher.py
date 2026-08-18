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
  python texts_patcher.py remove-preview <rom.gba> --addrs 0x08376A3C,0x086F0B14
  python texts_patcher.py remove <rom.gba> --addrs 0x08376A3C,0x086F0B14
  python texts_patcher.py remove-preview <rom.gba> --from-translated
  python texts_patcher.py remove <rom.gba> --from-translated [texts_translated.json]
  python texts_patcher.py mark-404 [--translated PATH] [--game-id ID]
  python texts_patcher.py migrate-omit [rom.gba] [--config yaml]
  python texts_patcher.py guess <rom.gba> 0x081CBB61 [--config yaml]

export 默认写出 ``src/util/work/<game_id>/texts.json``（单模块为
``texts_<模块>.json``）；与产品 ``configs/.../translate/texts.json`` 分离。
跳过带写在 ``texts.omit_ranges``（全局）；模块 ``ranges`` 保持粗带。
remove 整句洞 merge 进 omit，不再把模块 ranges 切碎。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, NamedTuple

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CONFIGS_DIR = SCRIPT_DIR / "configs"
WORK_DIR = SCRIPT_DIR / "work"
OUT_DIR = SCRIPT_DIR / "out"
PIPELINE_CONFIGS = REPO_ROOT / "configs"  # Meowth 流水线；util 禁止直写

BASE = 0x08000000
EOS = 0xFF
MAX_PCS = 512
# export 扫带启发式下限 / 标题 LZ（不读产品 texts.json / game config）
SCRIPT_BANK_MIN = 0x100000
TITLE_LZ_BAND = (0x36D000, 0x370000)

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


def _regex_mod():
    """第三方 ``regex``（character_filter / address_filter）；缺包时给出安装提示。"""
    try:
        import regex as _rx  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "character_filter/address_filter 需要第三方包 regex："
            " pip install regex"
        ) from e
    return _rx


def _safe_print(msg: str) -> None:
    """Windows GBK 控制台下避免 UnicodeEncodeError。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write((msg + "\n").encode(enc, errors="replace"))
            buf.flush()
        else:
            print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


def parse_addr(v: Any) -> int:
    """``0x…`` 十六进制；无前缀时含 a–f 按十六进制，否则十进制。

    无前缀十进制兼容 PowerShell 把 ``0x08376A3C`` 吃成 ``137849404``。
    """
    if isinstance(v, int):
        return v
    s = str(v).strip().lower().replace("_", "")
    if not s:
        return 0
    if s.startswith("0x"):
        return int(s, 16)
    if any(c in "abcdef" for c in s):
        return int(s, 16)
    return int(s, 10)


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


def _slot_text(
    rom: bytes, off: int, window: int, *, eos: int = 0xFF
) -> tuple[str, bytes]:
    """在 ``[off, off+window)`` 内读到 ``eos``（默认 FF）为止；返回 (解码, 含 eos 的原文)。"""
    from meowth.jp_pcs import decode_pcs

    if window <= 0 or off < 0 or off >= len(rom):
        return "", b""
    slot = rom[off : off + window]
    marker = eos & 0xFF
    if marker not in slot:
        return "", slot
    end = slot.index(marker)
    raw = slot[: end + 1]
    return decode_pcs(raw), raw


def _parse_eos_byte(val: Any) -> int:
    """``read.eos`` / ``read.suffix``；默认 ``0xFF``。"""
    if val is None or val == "":
        return 0xFF
    if isinstance(val, int):
        return val & 0xFF
    s = str(val).strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16) & 0xFF
    if any(c in "abcdef" for c in s):
        return int(s, 16) & 0xFF
    return int(s, 10) & 0xFF


def _struct_entry_size(read: dict) -> int:
    """行步长：只认 ``entry_size``（不用 stride，避免与 type=stride 混淆）。"""
    return int(read.get("entry_size") or 0)


def _struct_name_window(read: dict, entry_size: int) -> int:
    """名称搜索上限：可选 name_max/name_stride/desc_ptr_offset，否则整行。"""
    for key in ("name_max", "name_stride", "desc_ptr_offset"):
        if read.get(key) is not None:
            try:
                n = int(read[key])
                if n > 0:
                    return min(n, entry_size) if entry_size else n
            except (TypeError, ValueError):
                pass
    return entry_size


def _struct_name_offset(read: dict) -> int:
    """行内文本起始偏移：可选 name_offset，默认 0（行首）。"""
    try:
        return max(0, int(read.get("name_offset") or 0))
    except (TypeError, ValueError):
        return 0


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


def refuse_pipeline_write(path: Path) -> Path:
    """拒绝写入仓库根 ``configs/``（流水线）；util 产物只许 work/out/显式非流水线路。"""
    resolved = path.resolve()
    pipe = PIPELINE_CONFIGS.resolve()
    try:
        resolved.relative_to(pipe)
    except ValueError:
        return path
    raise SystemExit(
        f"util 禁止写入流水线配置目录: {path}\n"
        f"  请写到 {WORK_DIR}/<game_id>/… 或其它非 {pipe} 的路径"
    )


def default_output_path(game_id: str, module: str | None = None) -> Path:
    """``src/util/work/<game_id>/texts.json`` 或单模块 ``texts_<模块>.json``。"""
    base = WORK_DIR / game_id
    if module:
        return base / f"texts_{module}.json"
    return base / "texts.json"


def default_translated_path(game_id: str) -> Path:
    """``src/util/work/<game_id>/texts_translated.json``。"""
    return WORK_DIR / game_id / "texts_translated.json"


def read_pcs(rom: bytes, off: int, maxlen: int = 256) -> bytes | None:
    """读到 FF 的 PCS 体（含 EOS）；本地实现，不 import meowth.extract。"""
    if off < 0 or off >= len(rom):
        return None
    end = rom.find(bytes([EOS]), off, min(len(rom), off + maxlen))
    if end < 0:
        return None
    return rom[off : end + 1]


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


def _styles_as_dict(styles_list: list[dict]) -> dict[str, dict]:
    """yaml ``texts.styles`` list → ``{id: meta}``（与 modules 同形）。

    ``channel`` 已废弃（Meowth 按顺序交错 01/81/02/82…），写出时丢弃。
    """
    out: dict[str, dict] = {}
    for s in styles_list:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid:
            continue
        meta = {k: v for k, v in s.items() if k not in ("id", "channel")}
        out[sid] = meta
    return out


def _yaml_styles_dict(cfg: dict) -> dict[str, dict]:
    raw = (cfg.get("texts") or {}).get("styles")
    if raw is None:
        return {}
    if isinstance(raw, list):
        return _styles_as_dict(raw)
    if isinstance(raw, dict):
        out: dict[str, dict] = {}
        nested_keys = {str(k).strip().lower().replace("0x", "") for k in raw}
        if nested_keys and nested_keys <= {"00", "80", "0", "128"}:
            for fam in ("00", "80", "0", "128"):
                group = None
                for k, v in raw.items():
                    if str(k).strip().lower().replace("0x", "") == fam:
                        group = v
                        break
                if not isinstance(group, dict):
                    continue
                for sid, meta in group.items():
                    name = str(sid).strip()
                    if not name or not isinstance(meta, dict):
                        continue
                    out[name] = {k: v for k, v in meta.items() if k != "channel"}
            return out
        for sid, meta in raw.items():
            name = str(sid).strip()
            if not name or not isinstance(meta, dict):
                continue
            out[name] = {k: v for k, v in meta.items() if k != "channel"}
        return out
    return {}


def extract_stride(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
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
        if not _entry_passes_filters(
            fo=off,
            raw=raw,
            original=text,
            ptrs=[],
            mod=mod,
            filters=filters,
            byte_length=stride,
        ):
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


def extract_struct(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """结构体行表：按行 entry_size 步进，名称读到 eos（默认 FF）；byte_length=原文实际长。"""
    from meowth.jp_pcs import decode_pcs

    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    read = mod.get("read") or {}
    entry_size = _struct_entry_size(read)
    if not entry_size or end < start:
        return []
    eos = _parse_eos_byte(read.get("eos", read.get("suffix")))
    name_window = _struct_name_window(read, entry_size)
    name_offset = _struct_name_offset(read)
    count = (end - start + 1) // entry_size
    out: list[dict] = []
    table_ptr = BASE + start
    for i in range(count):
        off = start + i * entry_size
        text, raw = _slot_text(rom, off + name_offset, name_window, eos=eos)
        if eos != 0xFF and raw:
            text = decode_pcs(raw[:-1])
        if not text or set(text) <= {"？", "ー", "-", " "}:
            continue
        if not _entry_passes_filters(
            fo=off,
            raw=raw,
            original=text,
            ptrs=[],
            mod=mod,
            filters=filters,
            byte_length=len(raw),
        ):
            continue
        e = {
            "address": f"0x{BASE + off + name_offset:08X}",
            "table_index": i,
            "table_base": f"0x{table_ptr:08X}",
            "byte_length": len(raw),
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


def extract_stride_ptr(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    ptr_stride = int((mod.get("read") or {}).get("stride") or 4)
    # 指针目标 EOS 搜索窗（默认 24，兼容旧模块；长文本指针表可调大）
    try:
        eos_window = int((mod.get("read") or {}).get("eos_window") or 24)
    except (TypeError, ValueError):
        eos_window = 24
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
            eos = rom.find(b"\xFF", so, so + eos_window)
            if eos >= 0:
                raw = rom[so : eos + 1]
                text = decode_pcs(raw)
                if text:
                    if not _entry_passes_filters(
                        fo=so,
                        raw=raw,
                        original=text,
                        ptrs=[lit],
                        mod=mod,
                        filters=filters,
                        byte_length=len(raw),
                    ):
                        lit += ptr_stride
                        i += 1
                        continue
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
            if hi >= lo >= 0:
                bands.append([f"0x{lo:X}", f"0x{hi:X}"])
    if not bands:
        lo, hi = parse_addr(mod.get("start")), parse_addr(mod.get("end"))
        if hi >= lo >= 0:
            bands.append([f"0x{lo:X}", f"0x{hi:X}"])
    return bands


def _as_file_off_pair(lo: int, hi: int) -> tuple[int, int]:
    if lo >= BASE:
        lo -= BASE
    if hi >= BASE:
        hi -= BASE
    return lo, hi


def parse_omit_range_list(raw: Any) -> list[tuple[int, int]]:
    """yaml ``omit_ranges`` / ``ranges`` 条目 → 文件偏移闭区间列表。"""
    if not raw:
        return []
    out: list[tuple[int, int]] = []
    for r in raw:
        if isinstance(r, dict):
            lo, hi = parse_addr(r.get("start")), parse_addr(r.get("end"))
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            lo, hi = parse_addr(r[0]), parse_addr(r[1])
        else:
            continue
        lo, hi = _as_file_off_pair(lo, hi)
        if hi >= lo >= 0:
            out.append((lo, hi))
    return out


def get_texts_omit_ranges(cfg: dict) -> list[tuple[int, int]]:
    texts = cfg.get("texts") or {}
    return merge_spans(parse_omit_range_list(texts.get("omit_ranges")))


def omit_ranges_to_yaml(
    spans: list[tuple[int, int]],
) -> list[dict[str, str]]:
    return [
        {"start": _fmt_file_off(a), "end": _fmt_file_off(b)}
        for a, b in merge_spans(spans)
    ]


def set_texts_omit_ranges(cfg: dict, spans: list[tuple[int, int]]) -> None:
    texts = cfg.setdefault("texts", {})
    omit_yaml = omit_ranges_to_yaml(spans)
    styles = texts.pop("styles", None)
    modules = texts.pop("modules", None)
    # omit_ranges 紧挨 texts:，styles 在 modules 之前
    rest = {k: v for k, v in texts.items() if k != "omit_ranges"}
    texts.clear()
    texts["omit_ranges"] = omit_yaml
    texts.update(rest)
    if styles is not None:
        texts["styles"] = styles
    if modules is not None:
        texts["modules"] = modules


def module_band_tuples(mod: dict) -> list[tuple[int, int]]:
    return parse_omit_range_list(
        [
            {"start": lo, "end": hi}
            for lo, hi in _module_bands(mod)
        ]
    )


def effective_module_bands(
    mod: dict, omit: list[tuple[int, int]]
) -> list[list[str]]:
    """模块粗带减去全局 omit → 实际扫描区间（字符串形式）。"""
    omit_m = merge_spans(omit)
    out: list[list[str]] = []
    for lo, hi in module_band_tuples(mod):
        for a, b in split_band(lo, hi, omit_m):
            out.append([f"0x{a:X}", f"0x{b:X}"])
    return out


# ---------------------------------------------------------------------------
# texts.filters：统一 *_filter + FilterContext
# ---------------------------------------------------------------------------


class FilterContext(NamedTuple):
    """单条 PCS 候选的过滤上下文。"""

    address: int
    address_vma: int
    raw: bytes
    byte_length: int
    original: str
    original_plain: str
    is_pointer_based: bool
    pointer_offs: list[int]
    module_id: str
    module_type: str


def plain_original(original: str) -> str:
    """剥 \\CC / \\n\\l\\p / \\xx，供 character_filter 等使用。"""
    s = original or ""
    s = re.sub(r"\\CC[0-9A-Fa-f]+", "", s)
    s = re.sub(r"\\[nlp]", "", s)
    s = re.sub(r"\\[0-9A-Fa-f]{2}", "", s)
    return s


def _msg_soft_key(s: str) -> str:
    """msg_filter 二次匹配键：剥控制码/换行、方括号 tag、首部变量占位与助词，再去空白。"""
    t = plain_original(s)
    # 语料残留 [PALETTE]/[PAUSE…] / 未 mapping 的 [STR_VAR_…]
    t = re.sub(r"\[[^\]]*\]", "", t)
    # [PLAYER]/01 等：语料 mapping 后常为 \\01は…；ROM 侧无此前缀
    t = re.sub(r"^\\0[1-6][はがのもを]?", "", t)
    t = re.sub(r"^[\u0001-\u0006][はがのもを]?", "", t)
    # 句中仍可能残留的变量字节转义（软匹配用）
    t = re.sub(r"\\0[1-6]", "", t)
    # 语料侧 mapping 后为真实控制字节 \x01-\x06，句中同样剥掉（与 ROM 转义 `\01` 对称）
    t = re.sub(r"[\u0001-\u0006]", "", t)
    return _norm_original_key(t)


# msg_filter 语料缓存：(path, mtime, mapping) → (exact, norms, softs, mapped_lines)
# softs：剥占位后全等键；mapped_lines 保留供诊断/兼容，匹配不再 fuzz 召回
# v2：无后缀展开
_MSG_FILTER_CACHE: dict[
    tuple[Any, ...],
    tuple[frozenset[str], frozenset[str], frozenset[str], tuple[str, ...]],
] = {}


def _has_msg_include_filter(filters: list[dict[str, Any]] | None) -> bool:
    """模块是否有 msg_filter 包含模式（语料白名单）。"""
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "msg_filter":
            continue
        if "filter" in spec and not bool(spec.get("filter")):
            return True
    return False


def _has_include_original_text_filter(filters: list[dict[str, Any]]) -> bool:
    """模块是否声明了 original_text_filter 且为包含模式（filter: false）。"""
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "original_text_filter":
            continue
        # 未写 filter 默认 true=过滤；仅 false=包含
        if "filter" in spec and not bool(spec.get("filter")):
            return True
    return False


def _normalize_filters_list(raw: Any, *, where: str) -> list[dict[str, Any]]:
    """Accept flat id-list, or legacy ``{scan: [...], stride: []}`` (caller picks key)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [dict(x) for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        # legacy by-type bucket — only used when caller passes a list already
        raise SystemExit(
            f"{where}: texts.filters 须为带 id 的列表 "
            f"(旧 scan/stride 分桶已废弃)"
        )
    return []


def resolve_filters(cfg: dict, mod: dict) -> list[dict[str, Any]]:
    """texts.filters（扁平 id 列表）+ module.filters；同 id 后写覆盖整条。

    - ``type: scan``：基线 = 全局 ``texts.filters``。
    - 非 scan 且模块未写 ``filters`` 键：基线为空（兼容旧 stride/struct: []）。
    - 非 scan 且写了 ``filters``：基线 = 全局，再按 id 覆盖/追加。
    - 若模块声明了 ``msg_filter`` / ``original_text_filter`` 且 ``filter: false``：
      不叠全局启发式（长度/形似/垃圾等），只保留 address/anim/ime/msg。
    """
    mtype = str(mod.get("type") or "scan")
    texts = cfg.get("texts") or {}
    global_raw = texts.get("filters")
    # legacy: filters.scan / filters.stride
    if isinstance(global_raw, dict):
        base_src = global_raw.get(mtype) or []
        if not isinstance(base_src, list):
            base_src = []
        base = [dict(x) for x in base_src if isinstance(x, dict)]
    else:
        base = _normalize_filters_list(global_raw, where="texts.filters")

    has_mod_filters_key = "filters" in mod
    extra = list(mod.get("filters") or []) if has_mod_filters_key else []

    # 语料 / 原文白名单：不叠全局启发式（靠白名单本身）
    if (
        _has_include_original_text_filter(extra)
        or _has_msg_include_filter(extra)
    ):
        keep_types = {
            "msg_filter",
            "address_filter",
            "anim_cmd_filter",
            "ime_keyboard_filter",
            "require_pointer_filter",
            "story_pointer_filter",
        }
        base = [
            dict(s)
            for s in base
            if isinstance(s, dict) and str(s.get("type") or "") in keep_types
        ]
    elif mtype != "scan" and not has_mod_filters_key:
        base = []

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for spec in base + extra:
        if not isinstance(spec, dict):
            continue
        t = str(spec.get("type") or "").strip()
        if not t:
            continue
        if not t.endswith("_filter"):
            raise SystemExit(
                f"filter type 必须以 _filter 结尾: {t!r} (module={mod.get('id')!r})"
            )
        fid = str(spec.get("id") or "").strip()
        if not fid:
            # legacy entries without id: fall back to type as id
            fid = t
        if fid not in merged:
            order.append(fid)
        entry = dict(spec)
        entry["id"] = fid
        entry["type"] = t
        merged[fid] = entry
    return [merged[i] for i in order]


def _norm_original_key(s: str) -> str:
    """正文匹配用：去掉空白后比较。"""
    return re.sub(r"\s+", "", s or "")


class TextFilter(ABC):
    """单条 filter：``hit(ctx)`` 得条件命中，``keep(ctx)`` 得是否放行。"""

    type_name: str = ""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.id = str(spec.get("id") or self.type_name or "")
        self.value = spec.get("value")
        # 未写 filter 默认 true=排除命中；false=包含命中
        self.exclude = True if "filter" not in spec else bool(spec.get("filter"))

    @abstractmethod
    def hit(self, ctx: FilterContext) -> bool | None:
        """None=本闸禁用；True=命中条件侧。"""

    def keep(self, ctx: FilterContext) -> bool:
        h = self.hit(ctx)
        if h is None:
            return True
        return (not h) if self.exclude else bool(h)


class CharacterFilter(TextFilter):
    type_name = "character_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        pat = str(self.value or "")
        if not pat:
            return None
        plain = ctx.original_plain or ""
        rx = _regex_mod()
        try:
            return rx.search(pat, plain) is not None
        except rx.error as e:
            raise SystemExit(
                f"character_filter 正则无效 id={self.id!r}: {e}"
            ) from e


class DialogueShapeFilter(TextFilter):
    type_name = "dialogue_shape_filter"

    @staticmethod
    def shape_ok(ctx: FilterContext, *, pointer_ok: bool = True) -> bool:
        """对白/说明形态。

        ``pointer_ok=True``（默认，说明类兼容）：有指针即放行。
        ``pointer_ok=False``（剧情）：须像真脚本句，避免吞掉 UI 短标。
        """
        o = ctx.original or ""
        plain = ctx.original_plain or ""
        if pointer_ok and ctx.is_pointer_based:
            return True
        jp = len(re.findall(r"[\u3040-\u30ff]", o))
        # 剧情 + 有指针：短对白/路标式引号也放行（须在 jp<8 早退之前）
        if (not pointer_ok) and ctx.is_pointer_based:
            if ("\\l" in o or "\\p" in o or "\\n" in o) and jp >= 8:
                return True
            if ("『" in o or "「" in o) and jp >= 4:
                return True
            if ("！" in o or "？" in o or "！" in plain or "？" in plain) and jp >= 6:
                return True
        if jp < 8:
            return False
        if "ポケモン" in o:
            return True
        plain_no_btn = re.sub(r"[Ａ-Ｚａ-ｚ]ボタン", "", plain)
        fw = len(re.findall(r"[Ａ-Ｚａ-ｚ]", plain_no_btn))
        hw = len(re.findall(r"[A-Za-z]", plain_no_btn))
        if fw + hw >= 1:
            return False
        has_particle = bool(re.search(r"[はがをに]", o))
        if (
            ("！" in o or "？" in o or "！" in plain or "？" in plain)
            and has_particle
            and jp >= 8
        ):
            return True
        if ("\\l" in o or "\\p" in o) and has_particle and jp >= 10:
            return True
        if (
            ("。" in o or "。" in plain or "‥" in o)
            and re.search(r"[はがを]", o)
            and jp >= 12
        ):
            return True
        return False

    def hit(self, ctx: FilterContext) -> bool | None:
        val = self.value
        pointer_ok = True
        if isinstance(val, dict):
            if not bool(val.get("enabled", True)):
                return None
            pointer_ok = bool(val.get("pointer_ok", True))
        elif not bool(val):
            return None
        return not self.shape_ok(ctx, pointer_ok=pointer_ok)


class MinByteLengthFilter(TextFilter):
    type_name = "min_byte_length_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        try:
            n = int(self.value)
        except (TypeError, ValueError):
            return None
        return ctx.byte_length < n


class MaxByteLengthFilter(TextFilter):
    type_name = "max_byte_length_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        try:
            n = int(self.value)
        except (TypeError, ValueError):
            return None
        return ctx.byte_length > n


class RequirePointerFilter(TextFilter):
    type_name = "require_pointer_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        if not bool(self.value):
            return None
        return not bool(ctx.is_pointer_based)


class StoryPointerFilter(TextFilter):
    """剧情指针过滤：在 require_pointer_filter 之上校验「指针目标确实是剧情文本」。

    ``value: true``（默认排除极性）时命中（丢弃）两类候选：
      1. 无指针——同 require_pointer_filter；
      2. 有指针但指针目标 raw 像原始数据而非文本——顺号计数器段
         （``15 16 17 18 19 FF``，如 axvj_db99214d805e 一类数据表伪命中）、
         anim/指针表流、五十音键盘表、垃圾假名解码。
    语义：`pointer` 存在只说明「ROM 里有东西指着它」；是不是剧情，还看目标形态。
    """

    type_name = "story_pointer_filter"

    _COUNTER_LO = 0x00  # 全角字形区起点（假名/标点/空格）
    _COUNTER_HI = 0xA0  # 全角字形区终点（片假名结束）

    @classmethod
    def looks_counter_run(cls, raw: bytes | None, *, min_run: int = 5) -> bool:
        """单调递增/递减 ≥5 的连续全角字节段（表数据/索引计数器特征）。"""
        body = (raw or b"")
        if body and body[-1] == 0xFF:
            body = body[:-1]
        if len(body) < min_run:
            return False
        best_up = best_dn = run_up = run_dn = 1
        lo, hi = cls._COUNTER_LO, cls._COUNTER_HI
        for i in range(1, len(body)):
            prev, cur = body[i - 1], body[i]
            if lo <= prev <= hi and lo <= cur <= hi and cur == prev + 1:
                run_up += 1
                if run_up > best_up:
                    best_up = run_up
            else:
                run_up = 1
            if lo <= prev <= hi and lo <= cur <= hi and prev == cur + 1:
                run_dn += 1
                if run_dn > best_dn:
                    best_dn = run_dn
            else:
                run_dn = 1
        return best_up >= min_run or best_dn >= min_run

    @classmethod
    def looks_struct_slot(cls, raw: bytes | None) -> bool:
        """定长结构体槽指纹：``[单字符] + 全零填充``（如 ``10 00 00 00 ff``=た）。

        ``00`` 在真实对白里是合法空格，故不能只看「体内含 00」；判别是
        **首字节为一个字符、其后全为 00 填充**——精灵图/数据表里被误当文本
        的定宽槽特征（1 字符 + 零补齐），真实指针型剧情句不会长这样。
        """
        body = (raw or b"")
        if body and body[-1] == 0xFF:
            body = body[:-1]
        if len(body) < 2:
            return False
        if body[0] == 0x00:
            return False
        return all(b == 0x00 for b in body[1:])

    def hit(self, ctx: FilterContext) -> bool | None:
        if not bool(self.value):
            return None
        if not ctx.is_pointer_based:
            return True
        raw = ctx.raw or b""
        # 丢弃签名列表：任一命中即丢（均为非文本/定长槽指纹）
        return any(
            signature(ctx, raw)
            for signature in (
                self._sig_counter_run,
                self._sig_anim_cmd,
                self._sig_ime_keyboard,
                self._sig_struct_slot,
                self._sig_garbage,
            )
        )

    def _sig_counter_run(self, ctx: FilterContext, raw: bytes) -> bool:
        del ctx
        return self.looks_counter_run(raw)

    def _sig_anim_cmd(self, ctx: FilterContext, raw: bytes) -> bool:
        del ctx
        return AnimCmdFilter.looks_anim_cmd(raw)

    def _sig_ime_keyboard(self, ctx: FilterContext, raw: bytes) -> bool:
        return ImeKeyboardFilter.looks_ime_keyboard(raw, ctx.original or "")

    def _sig_struct_slot(self, ctx: FilterContext, raw: bytes) -> bool:
        del ctx
        return self.looks_struct_slot(raw)

    def _sig_garbage(self, ctx: FilterContext, raw: bytes) -> bool:
        del raw
        return GarbageHeuristicFilter.looks_garbage(ctx.original)


class GarbageHeuristicFilter(TextFilter):
    type_name = "garbage_heuristic_filter"

    # 「ポケモン」片假名 digraph；对白里反复出现不算垃圾
    _POKEMON_DIGRAPHS = frozenset({"ポケ", "ケモ", "モン"})

    @staticmethod
    def looks_garbage(original: str) -> bool:
        """窄启发式（garbage_heuristic_filter / mark-404）。

        不做无 address 的 ``axvj_entry_is_garbage``。
        全角 Ａボタン / Ｂボタン 不算垃圾。
        """
        o = original or ""
        try:
            from meowth.policy import is_garbage_jp

            if is_garbage_jp(o):
                return True
        except Exception:
            pass

        plain = plain_original(o)
        plain_no_btn = re.sub(r"[Ａ-Ｚａ-ｚ]ボタン", "", plain)

        latin = len(re.findall(r"[A-Za-zÄäÖöÜüß]", plain))
        jp = len(re.findall(r"[\u3040-\u30ff]", o))
        fw_letter = len(re.findall(r"[Ａ-Ｚａ-ｚ]", plain_no_btn))
        if latin >= 3 and jp >= 5:
            return True
        if fw_letter >= 4 and jp >= 3:
            return True
        if ("♂" in o or "♀" in o) and (
            fw_letter >= 1 or "Ｂ" in plain_no_btn or "Ａ" in plain_no_btn
        ):
            return True
        if len(plain.strip()) <= 8 and fw_letter >= 1 and 1 <= jp <= 2:
            return True

        # digraph≥3：排除 ポケモン 片；对白信号 + ポケモン 时整段跳过
        skip_digraph = "ポケモン" in o and (
            bool(re.search(r"[はがをに]", o)) or "\\l" in o or "\\p" in o
        )
        if not skip_digraph:
            for block in set(re.findall(r"[ァ-ン]{2}", o)):
                if block in GarbageHeuristicFilter._POKEMON_DIGRAPHS:
                    continue
                if o.count(block) >= 3:
                    return True
        if (
            jp >= 12
            and not re.search(r"[はがをのにてもだ]", o)
            and not re.search(r"[\u4e00-\u9fff]", o)
            and "ポケモン" not in o
            and "\\CC" not in o
        ):
            for block in set(re.findall(r"[ァ-ン]{2}", o)):
                if block in GarbageHeuristicFilter._POKEMON_DIGRAPHS:
                    continue
                if o.count(block) >= 2:
                    return True
        return False

    def hit(self, ctx: FilterContext) -> bool | None:
        if not bool(self.value):
            return None
        return self.looks_garbage(ctx.original)


class AnimCmdFilter(TextFilter):
    """踢误扫的 Gen3 精灵 anim 命令流 / 指针表（raw 形态，不看日文字形）。"""

    type_name = "anim_cmd_filter"

    @staticmethod
    def _is_rom_ptr(w: int) -> bool:
        return ((w >> 24) & 0xFF) in (0x08, 0x09)

    @staticmethod
    def _max_consecutive_rom_ptrs(raw: bytes) -> int:
        """4 字节对齐下最长连续 ROM 指针个数。"""
        best = 0
        run = 0
        for i in range(0, len(raw) - 3, 4):
            w = struct.unpack_from("<I", raw, i)[0]
            if AnimCmdFilter._is_rom_ptr(w):
                run += 1
                if run > best:
                    best = run
            else:
                run = 0
        return best

    @staticmethod
    def _has_frame_word(raw: bytes, lo: int, hi: int) -> bool:
        """窗内是否有 anim 帧字：``xx 01 10 00`` / ``xx 00 10 00``。"""
        lo = max(0, lo)
        hi = min(len(raw), hi)
        for i in range(lo, hi - 3):
            if raw[i + 2] == 0x10 and raw[i + 3] == 0x00 and raw[i + 1] in (0x00, 0x01):
                return True
        return False

    @staticmethod
    def _max_consecutive_frame_words(raw: bytes) -> int:
        """4 字节对齐下最长连续 anim 帧字个数（``xx 0{0,1} 10 00``）。"""
        best = 0
        run = 0
        for i in range(0, len(raw) - 3, 4):
            if (
                raw[i + 2] == 0x10
                and raw[i + 3] == 0x00
                and raw[i + 1] in (0x00, 0x01)
            ):
                run += 1
                if run > best:
                    best = run
            else:
                run = 0
        return best

    @staticmethod
    def looks_anim_cmd(raw: bytes) -> bool:
        if not raw or len(raw) < 8:
            return False
        if AnimCmdFilter._max_consecutive_rom_ptrs(raw) >= 2:
            return True
        # PCS 扫到单字节 FF 截断时：连续帧字 ≥2（如 80 01 10 00 ×3 + FF）
        if AnimCmdFilter._max_consecutive_frame_words(raw) >= 2:
            return True
        # Anim 帧 + 0xFFFF 结束，其后常跟指针表
        for i in range(0, len(raw) - 1, 2):
            if raw[i] != 0xFF or raw[i + 1] != 0xFF:
                continue
            if AnimCmdFilter._has_frame_word(raw, i - 12, i):
                return True
            # FFFF 后对齐处有 ≥1 个 ROM 指针
            for j in range(i + 2, min(len(raw) - 3, i + 18), 2):
                if j & 3:
                    continue
                w = struct.unpack_from("<I", raw, j)[0]
                if AnimCmdFilter._is_rom_ptr(w):
                    return True
        return False

    def hit(self, ctx: FilterContext) -> bool | None:
        if not bool(self.value):
            return None
        return self.looks_anim_cmd(ctx.raw or b"")


class ImeKeyboardFilter(TextFilter):
    """踢误扫的 Gen3 姓名输入五十音键盘码表（跨 AXVJ/AXPJ/BPRJ/BPGJ raw 形态）。"""

    type_name = "ime_keyboard_filter"

    # あ行 + な行页头（RS/FRLG 日版共有）
    _PAGE_SIG = bytes(
        [0x01, 0x02, 0x03, 0x04, 0x05, 0x00, 0x15, 0x16, 0x17, 0x18, 0x19, 0x00]
    )
    _ROW_MARKERS = (
        "あいうえお",
        "かきくけこ",
        "さしすせそ",
        "たちつてと",
        "なにぬねの",
        "はひふへほ",
        "まみむめも",
        "やゆよ",
        "らりるれろ",
        "わをん",
    )

    @staticmethod
    def _strip_eos(raw: bytes) -> bytes:
        body = raw or b""
        while body and body[-1] == 0xFF:
            body = body[:-1]
        return body

    @staticmethod
    def _is_kana_code(b: int) -> bool:
        return 0x01 <= b <= 0xA0

    @staticmethod
    def _count_gojuon_rows(body: bytes) -> int:
        """连续 5 个递增假名码且后接 0x00 / 行尾 → 一行。"""
        rows = 0
        i = 0
        n = len(body)
        while i + 5 <= n:
            chunk = body[i : i + 5]
            if (
                all(ImeKeyboardFilter._is_kana_code(b) for b in chunk)
                and all(chunk[j] + 1 == chunk[j + 1] for j in range(4))
            ):
                after = i + 5
                if after >= n or body[after] == 0x00:
                    rows += 1
                    i = after + (1 if after < n and body[after] == 0x00 else 0)
                    continue
            i += 1
        return rows

    @staticmethod
    def looks_ime_keyboard(raw: bytes, original: str = "") -> bool:
        body = ImeKeyboardFilter._strip_eos(raw)
        if len(body) >= len(ImeKeyboardFilter._PAGE_SIG) and (
            ImeKeyboardFilter._PAGE_SIG in body
            or body.startswith(ImeKeyboardFilter._PAGE_SIG)
        ):
            return True
        if len(body) >= 10 and ImeKeyboardFilter._count_gojuon_rows(body) >= 2:
            return True

        o = original or ""
        if not o:
            return False
        if re.search(r"[はがをに]", o) or "\\l" in o or "\\p" in o:
            return False
        compact = re.sub(r"\s+", "", o)
        if "あいうえお" not in compact:
            return False
        others = sum(1 for m in ImeKeyboardFilter._ROW_MARKERS[1:] if m in compact)
        return others >= 1

    def hit(self, ctx: FilterContext) -> bool | None:
        if not bool(self.value):
            return None
        return self.looks_ime_keyboard(ctx.raw or b"", ctx.original or "")


class AddressFilter(TextFilter):
    type_name = "address_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        val = self.value
        if isinstance(val, dict):
            lo = normalize_file_off(val.get("start") or 0)
            hi = normalize_file_off(val.get("end") or 0)
            if hi < lo:
                lo, hi = hi, lo
            return lo <= ctx.address <= hi
        pat = str(val or "")
        if not pat:
            return None
        rx = _regex_mod()
        hex_s = f"0x{ctx.address:X}"
        vma_s = f"0x{ctx.address_vma:08X}"
        try:
            return (
                rx.search(pat, hex_s) is not None
                or rx.search(pat, vma_s) is not None
            )
        except rx.error as e:
            raise SystemExit(
                f"address_filter 正则无效 id={self.id!r}: {e}"
            ) from e


def _file_off_from_yaml_addr(addr: Any) -> int:
    """YAML 地址 → 文件偏移（接受 0x08 VMA 或文件偏移）。"""
    a = parse_addr(addr)
    if a >= BASE:
        a -= BASE
    return a


def _parse_original_text_items(
    val: Any,
) -> list[tuple[str, int | None, int | None]]:
    """解析 original_text_filter.value → [(原文, lo|None, hi|None), ...]。

    - 字符串：任意地址
    - ``{original, address}``：单地址
    - ``{original, start, end}``：闭区间带
    """
    if not isinstance(val, (list, tuple)):
        return []
    out: list[tuple[str, int | None, int | None]] = []
    for item in val:
        if item is None:
            continue
        if isinstance(item, str):
            s = item
            if s:
                out.append((s, None, None))
            continue
        if isinstance(item, dict):
            orig = item.get("original")
            if orig is None:
                orig = item.get("text")
            if orig is None:
                continue
            # address/start-end 绑定：保留尾部空格（盒子菜单填充槽「やめる   」）
            # 无地址短词：strip 空白，避免误扫
            raw_s = str(orig)
            if item.get("address") is not None:
                if not raw_s.strip():
                    continue
                fo = _file_off_from_yaml_addr(item.get("address"))
                out.append((raw_s, fo, fo))
                continue
            if item.get("start") is not None or item.get("end") is not None:
                if not raw_s.strip():
                    continue
                lo = _file_off_from_yaml_addr(item.get("start") or item.get("end"))
                hi = _file_off_from_yaml_addr(item.get("end") or item.get("start"))
                if hi < lo:
                    lo, hi = hi, lo
                out.append((raw_s, lo, hi))
                continue
            s = raw_s.strip()
            if not s:
                continue
            out.append((s, None, None))
            continue
        s = str(item)
        if s:
            out.append((s, None, None))
    return out


def _original_text_matches(ctx: FilterContext, key: str) -> bool:
    o = ctx.original or ""
    plain = ctx.original_plain or ""
    if o == key or plain == key:
        return True
    kn = _norm_original_key(key)
    if not kn:
        return False
    return _norm_original_key(o) == kn or _norm_original_key(plain) == kn


def _addr_in_item_band(
    fo: int, lo: int | None, hi: int | None
) -> bool:
    if lo is None and hi is None:
        return True
    if lo is None:
        return fo == hi
    if hi is None:
        return fo == lo
    return lo <= fo <= hi


class OriginalTextFilter(TextFilter):
    type_name = "original_text_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        items = _parse_original_text_items(self.value)
        if not items:
            return False
        for key, lo, hi in items:
            if not _original_text_matches(ctx, key):
                continue
            if _addr_in_item_band(ctx.address, lo, hi):
                return True
        return False


# msg_filter 语料加载见下方 _load_msg_filter_sets（缓存定义在 plain_original 旁）


def _util_work_root() -> Path:
    return Path(__file__).resolve().parent / "work"


def _resolve_msg_filter_file(file_spec: str) -> Path:
    p = Path(str(file_spec))
    if p.is_file():
        return p.resolve()
    cand = CONFIGS_DIR / p
    if cand.is_file():
        return cand.resolve()
    raise SystemExit(f"msg_filter 找不到语料文件: {file_spec!r} (试过 {cand})")


def _apply_msg_mapping(text: str, mapping: dict[str, str]) -> str:
    s = text or ""
    # 长键优先，避免短替换打断长 tag
    for src in sorted(mapping.keys(), key=len, reverse=True):
        s = s.replace(src, mapping[src])
    return s


def _load_msg_filter_sets(
    file_spec: str, mapping: dict[str, str]
) -> tuple[frozenset[str], frozenset[str], frozenset[str], tuple[str, ...]]:
    """返回 (exact, norms, softs, mapped_lines)。无后缀展开。"""
    path = _resolve_msg_filter_file(file_spec)
    map_items = tuple(sorted((str(k), str(v)) for k, v in mapping.items()))
    cache_key = (str(path), path.stat().st_mtime_ns, map_items)
    hit = _MSG_FILTER_CACHE.get(cache_key)
    if hit is not None:
        return hit
    exact: set[str] = set()
    norms: set[str] = set()
    softs: set[str] = set()
    mapped_list: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        mapped = _apply_msg_mapping(line, mapping)
        if not mapped.strip():
            continue
        exact.add(mapped)
        mapped_list.append(mapped)
        nk = _norm_original_key(mapped)
        if nk:
            norms.add(nk)
        sk = _msg_soft_key(mapped)
        if sk:
            softs.add(sk)
    out = (
        frozenset(exact),
        frozenset(norms),
        frozenset(softs),
        tuple(mapped_list),
    )
    _MSG_FILTER_CACHE[cache_key] = out
    return out


def _msg_soft_equal_after_fuzz(
    rom_text: str,
    softs: frozenset[str],
    mapped_lines: tuple[str, ...],
) -> bool:
    """剥占位后 soft_key 全等（集合查找）。

    旧路径曾用 rapidfuzz Top-K 再比 soft_key；若 soft_key 真相等，
    语料 softs 集合已含该键，fuzz 召回无法多检出，却把指针优先扫拖成
    O(目标数×语料行数)。故只保留集合命中。
    """
    del mapped_lines  # 兼容旧签名；不再做 fuzz 召回
    sk = _msg_soft_key(rom_text)
    return bool(sk) and sk in softs


class MsgFilter(TextFilter):
    """语料白名单：精确 → norm → soft_key 集合全等；可 min_plain_chars。"""

    type_name = "msg_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        val = self.value
        if not isinstance(val, dict):
            return None
        file_spec = val.get("file")
        if not file_spec:
            return None
        try:
            min_plain = int(val.get("min_plain_chars", 0) or 0)
        except (TypeError, ValueError):
            min_plain = 0
        plain = ctx.original_plain or ""
        if min_plain > 0 and len(plain) < min_plain:
            return False
        raw_map = val.get("mapping") or {}
        if not isinstance(raw_map, dict):
            raise SystemExit(f"msg_filter.mapping 须为对象 id={self.id!r}")
        mapping = {str(k): str(v) for k, v in raw_map.items()}
        exact, norms, softs, mapped_lines = _load_msg_filter_sets(
            str(file_spec), mapping
        )
        o = ctx.original or ""
        if o in exact or plain in exact:
            return True
        for candidate in (o, plain):
            nk = _norm_original_key(candidate)
            if nk and nk in norms:
                return True
        for candidate in (o, plain):
            if candidate and _msg_soft_equal_after_fuzz(
                candidate, softs, mapped_lines
            ):
                return True
        return False


class ControlOrShortFilter(TextFilter):
    """UI 归属：\\CC 控制符开头，或去控制符后短标签（可设 min/max_plain_chars）。"""

    type_name = "control_or_short_filter"

    def hit(self, ctx: FilterContext) -> bool | None:
        val = self.value
        if val is None:
            return None
        if not isinstance(val, dict):
            # value: true → 默认 control_prefix + max_plain_chars 12
            if not bool(val):
                return None
            val = {"control_prefix": True, "max_plain_chars": 12}
        control_prefix = bool(val.get("control_prefix", True))
        try:
            max_plain = int(val.get("max_plain_chars", 12))
        except (TypeError, ValueError):
            max_plain = 12
        try:
            min_plain = int(val.get("min_plain_chars", 1))
        except (TypeError, ValueError):
            min_plain = 1
        if min_plain < 0:
            min_plain = 0
        o = ctx.original or ""
        plain = ctx.original_plain or ""
        # 仅 \\CC…（含行首换行）；\\01–\\06 玩家/变量占位不算 UI 控制符
        if control_prefix and re.match(r"^[\n]*\\CC", o):
            return True
        if max_plain > 0 and min_plain <= len(plain) <= max_plain:
            return True
        return False


FILTER_TYPES: dict[str, type[TextFilter]] = {
    CharacterFilter.type_name: CharacterFilter,
    DialogueShapeFilter.type_name: DialogueShapeFilter,
    MinByteLengthFilter.type_name: MinByteLengthFilter,
    MaxByteLengthFilter.type_name: MaxByteLengthFilter,
    RequirePointerFilter.type_name: RequirePointerFilter,
    StoryPointerFilter.type_name: StoryPointerFilter,
    GarbageHeuristicFilter.type_name: GarbageHeuristicFilter,
    AnimCmdFilter.type_name: AnimCmdFilter,
    ImeKeyboardFilter.type_name: ImeKeyboardFilter,
    AddressFilter.type_name: AddressFilter,
    OriginalTextFilter.type_name: OriginalTextFilter,
    MsgFilter.type_name: MsgFilter,
    ControlOrShortFilter.type_name: ControlOrShortFilter,
}


def build_filter(spec: dict[str, Any]) -> TextFilter:
    t = str(spec.get("type") or "").strip()
    cls = FILTER_TYPES.get(t)
    if cls is None:
        raise SystemExit(f"未知 filter type: {t!r}")
    return cls(spec)


def apply_one_filter(ctx: FilterContext, spec: dict[str, Any]) -> bool:
    """True=保留，False=拒绝。"""
    return build_filter(spec).keep(ctx)


def apply_filters(ctx: FilterContext, filters: list[dict[str, Any]]) -> bool:
    for spec in filters:
        if not apply_one_filter(ctx, spec):
            return False
    return True


def make_filter_context(
    *,
    fo: int,
    raw: bytes,
    original: str,
    ptrs: list[int],
    module_id: str,
    module_type: str,
    byte_length: int | None = None,
) -> FilterContext:
    return FilterContext(
        address=fo,
        address_vma=BASE + fo,
        raw=raw,
        byte_length=len(raw) if byte_length is None else int(byte_length),
        original=original,
        original_plain=plain_original(original),
        is_pointer_based=bool(ptrs),
        pointer_offs=list(ptrs),
        module_id=module_id,
        module_type=module_type,
    )


def _merge_legacy_length_filters(
    mod: dict, filters: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """旧模块字段 min/max_byte_length → filter；不覆盖已有同 type。"""
    filt = list(filters or [])
    if mod.get("min_byte_length") is not None and not any(
        str(f.get("type")) == "min_byte_length_filter" for f in filt
    ):
        filt.append(
            {"type": "min_byte_length_filter", "value": int(mod["min_byte_length"])}
        )
    if mod.get("max_byte_length") is not None and not any(
        str(f.get("type")) == "max_byte_length_filter" for f in filt
    ):
        filt.append(
            {"type": "max_byte_length_filter", "value": int(mod["max_byte_length"])}
        )
    if mod.get("require_pointer") and not any(
        str(f.get("type")) == "require_pointer_filter" for f in filt
    ):
        filt.append({"type": "require_pointer_filter", "value": True})
    return filt


def _entry_passes_filters(
    *,
    fo: int,
    raw: bytes,
    original: str,
    ptrs: list[int],
    mod: dict,
    filters: list[dict[str, Any]] | None,
    byte_length: int | None = None,
) -> bool:
    """任意 extract 类型共用：无 filter 则保留；否则构造上下文后层层过滤。"""
    filt = _merge_legacy_length_filters(mod, filters)
    if not filt:
        return True
    ctx = make_filter_context(
        fo=fo,
        raw=raw,
        original=original,
        ptrs=ptrs,
        module_id=str(mod.get("id") or ""),
        module_type=str(mod.get("type") or "scan"),
        byte_length=byte_length,
    )
    return apply_filters(ctx, filt)


def _original_include_items(
    filters: list[dict[str, Any]],
) -> list[tuple[str, int | None, int | None]] | None:
    """包含模式 original_text_filter → [(原文, lo, hi), ...]；否则 None。"""
    for spec in filters or []:
        if str(spec.get("type") or "") != "original_text_filter":
            continue
        if bool(spec.get("filter", True)):
            return None
        items = _parse_original_text_items(spec.get("value"))
        return items or None
    return None


# msg_filter 语料 → PCS 体缓存（按 file+mtime+mapping）
_MSG_BODY_CACHE: dict[tuple[Any, ...], set[bytes]] = {}


def _msg_needle_variants(mapped: str) -> set[str]:
    """语料整行变体（禁止句中切段）：mapping 全文 / 去 tag / 去行首变量 / 去行尾 CC。"""
    out: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip("\n")
        if not s:
            return
        out.add(s)
        t = re.sub(r"(\\CC[0-9A-Fa-f]+)+$", "", s)
        if t and t != s:
            out.add(t)
        t = re.sub(r"\[PAUSE[^\]]*\]$", "", s)
        if t and t != s:
            out.add(t.strip("\n"))

    add(mapped)
    no_tag = re.sub(r"\[[^\]]*\]", "", mapped)
    add(no_tag)
    for base in (mapped, no_tag):
        t = re.sub(r"^\\0[1-6][はがのもを]?", "", base)
        t = re.sub(r"^[\n ]+", "", t)
        add(t)
    return out


def _msg_include_needle_bodies(
    filters: list[dict[str, Any]] | None,
) -> set[bytes]:
    """msg_filter 包含模式：语料变体编成 PCS（含 FF），供按 EOS 反查。"""
    out: set[bytes] = set()
    for spec in filters or []:
        if not isinstance(spec, dict):
            continue
        if str(spec.get("type") or "") != "msg_filter":
            continue
        if bool(spec.get("filter", True)):
            continue
        val = spec.get("value")
        if not isinstance(val, dict):
            continue
        file_spec = val.get("file")
        if not file_spec:
            continue
        raw_map = val.get("mapping") or {}
        if not isinstance(raw_map, dict):
            raise SystemExit(f"msg_filter.mapping 须为对象 id={spec.get('id')!r}")
        mapping = {str(k): str(v) for k, v in raw_map.items()}
        path = _resolve_msg_filter_file(str(file_spec))
        map_items = tuple(sorted((str(k), str(v)) for k, v in mapping.items()))
        # v3：整行针 + 与 msg min_plain 对齐（跳过过短/纯控制）
        cache_key = ("v3", str(path), path.stat().st_mtime_ns, map_items)
        hit = _MSG_BODY_CACHE.get(cache_key)
        if hit is not None:
            out |= hit
            continue
        try:
            min_plain = int(val.get("min_plain_chars", 0) or 0)
        except (TypeError, ValueError):
            min_plain = 0
        chunk: set[bytes] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            mapped = _apply_msg_mapping(line, mapping)
            if not mapped.strip():
                continue
            for text in _msg_needle_variants(mapped):
                if min_plain > 0 and len(plain_original(text)) < min_plain:
                    continue
                body = _encode_jp_needle(text)
                if body and len(body) >= 2:
                    chunk.add(body)
        _MSG_BODY_CACHE[cache_key] = chunk
        out |= chunk
    return out


def _encode_jp_needle(text: str) -> bytes | None:
    """把抽出原文编码为 JP PCS（含 FF）。失败返回 None。"""
    from meowth.jp_pcs import CHAR_TO_BYTE

    if not text:
        return None
    out = bytearray()
    i = 0
    n = len(text)
    while i < n:
        # \\CC + hex args (from decode_pcs)
        if text.startswith("\\CC", i):
            hexpart = ""
            j = i + 3
            while j < n and text[j] in "0123456789abcdefABCDEF":
                hexpart += text[j]
                j += 1
            if len(hexpart) < 2 or len(hexpart) % 2:
                return None
            out.append(0xFC)
            try:
                out.extend(bytes.fromhex(hexpart))
            except ValueError:
                return None
            i = j
            continue
        if text.startswith("\\l", i):
            out.append(0xFA)
            i += 2
            continue
        if text.startswith("\\p", i):
            out.append(0xFB)
            i += 2
            continue
        if text.startswith("\\n", i):
            out.append(0xFE)
            i += 2
            continue
        # \\XX variable / control (FD xx) — two hex digits
        if text[i] == "\\" and i + 3 <= n and text[i + 1] != "\\":
            hx = text[i + 1 : i + 3]
            if all(c in "0123456789abcdefABCDEF" for c in hx):
                out.append(0xFD)
                out.append(int(hx, 16))
                i += 3
                continue
        ch = text[i]
        if ch == "\n":
            # 单换行 FE；连续两个 \n\n → FB（与 decode 对称不完美，优先 FE）
            if i + 1 < n and text[i + 1] == "\n":
                out.append(0xFB)
                i += 2
            else:
                out.append(0xFE)
                i += 1
            continue
        b = CHAR_TO_BYTE.get(ch)
        if b is None:
            return None
        out.append(b)
        i += 1
    out.append(0xFF)
    return bytes(out)


# msg_reader 语料 needle 缓存：(file, mtime, mapping) → 非空 needle 列表
_MSG_READER_CACHE: dict[tuple[Any, ...], tuple[bytes, ...]] = {}


class ReaderHit(NamedTuple):
    """reader 修整后的候选内容（address/hex/original/ptrs）。"""

    fo: int
    raw: bytes
    original: str
    ptrs: list[int]


class MsgReader:
    """reader=msg_reader：scan 读取时用语料 needle 在 raw 内定位「垃圾前缀 + msg 文本」
    的真实正文起点（如「べえねくぽえ…ママ『ほら…」整段垃圾前缀）。

    filter 返回 Boolean 决定是否采用；reader 返回**修整后的内容**（ReaderHit，含
    address/hex/original），或返回 None 表示不采用。配置样式同 msg_filter：
    value.file / value.mapping / value.min_plain_chars。
    """

    type_name = "msg_reader"

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.value = spec.get("value") or spec.get("reader_value")
        if not isinstance(self.value, dict):
            raise SystemExit(
                f"msg_reader 须提供 value.file/value.mapping id={spec.get('id')!r}"
            )
        self.file = str(self.value.get("file") or "")
        if not self.file:
            raise SystemExit(f"msg_reader 缺 value.file id={spec.get('id')!r}")
        raw_map = self.value.get("mapping") or {}
        if not isinstance(raw_map, dict):
            raise SystemExit(f"msg_reader.mapping 须为对象 id={spec.get('id')!r}")
        self.mapping = {str(k): str(v) for k, v in raw_map.items()}
        self._needles: tuple[bytes, ...] | None = None

    def needles(self) -> tuple[bytes, ...]:
        """语料行 mapping 后编码为 JP PCS needle（剥尾换行/EOS、跳过全空白）。

        语料每行末尾的 ``\\n`` 在 ROM 里是正文结束的 FF（EOS），不是真实换行，
        故编码后去掉尾部 0xFE；整体再剥 0xFF，使 needle 可作为正文子串匹配。
        """
        if self._needles is not None:
            return self._needles
        path = _resolve_msg_filter_file(self.file)
        map_items = tuple(sorted((str(k), str(v)) for k, v in self.mapping.items()))
        cache_key = (str(path), path.stat().st_mtime_ns, map_items)
        hit = _MSG_READER_CACHE.get(cache_key)
        if hit is not None:
            self._needles = hit
            return hit
        out: list[bytes] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            mapped = _apply_msg_mapping(line, self.mapping)
            if not mapped.strip():
                continue
            for v in _msg_needle_variants(mapped):
                if not (plain_original(v) or "").strip(" \t\n"):
                    continue
                needle = _encode_jp_needle(v)
                if needle is None:
                    continue
                body = needle.rstrip(b"\xff").rstrip(b"\xfe")
                if len(body) >= 4 and body not in out:
                    out.append(body)
        res = tuple(out)
        _MSG_READER_CACHE[cache_key] = res
        self._needles = res
        return res

    def read(
        self,
        rom: bytes,
        a: int,
        raw: bytes,
        ptrs_map: dict[int, list[int]],
        pcs_maxlen: int = 512,
    ) -> ReaderHit | None:
        """在 raw 内定位 msg 语料 needle 的真实起点；命中返回修整内容，否则 None。

        取 raw 内**最早命中**的 needle 偏移 i；正文起点 = a+i。i==0 表示 raw 本就以
        msg 开头（无垃圾前缀），i>0 表示剥掉垃圾前缀。命中后以起点重新 read_pcs 取
        到 EOS 的完整正文。若正文剥离控制码后**全为空白**（对齐填充误匹配），返回 None。
        """
        best_i = -1
        for body in self.needles():
            i = raw.find(body)
            if i >= 0 and (best_i < 0 or i < best_i):
                best_i = i
        if best_i < 0:
            return None
        real_a = a + best_i
        real_raw = read_pcs(rom, real_a, pcs_maxlen)
        if real_raw is None:
            return None
        from meowth.jp_pcs import decode_pcs

        text = decode_pcs(real_raw)
        if not (plain_original(text) or "").strip(" \t\n"):
            return None
        return ReaderHit(
            fo=real_a,
            raw=real_raw,
            original=text,
            ptrs=list(ptrs_map.get(real_a, [])),
        )


def extract_scan(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
    omit_ranges: list[tuple[int, int]] | None = None,
    exclude_ranges: list[tuple[int, int]] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    # 只用 jp_pcs + 本地 read_pcs / SCRIPT_BANK_MIN；禁止 import meowth.extract
    #（extract 会 load_game_config → 读流水线 texts.json，与 util 导出死锁）。
    from meowth.jp_pcs import decode_pcs, looks_like_jp_text

    filt = _merge_legacy_length_filters(mod, filters)
    mid = mod["id"]
    mtype = str(mod.get("type") or "scan")
    # 模块级开关：默认 false。true 时才在 FF 扫描路径调 looks_like_jp_text 做
    # 形态预校验。该函数误判率高，后续新模块尽量不用（用地址带/语料白名单/结构定址）。
    use_looks_like = bool(mod.get("looks_like_jp_text", False))
    # reader=msg_reader：scan 读取内容改为用 msg 语料 needle 定位「垃圾前缀 + msg
    # 文本」的真实起点（如「べえねくぽえ…ママ『ほら…」）。返回修整内容或 None。
    msg_reader: MsgReader | None = None
    if str(mod.get("reader") or "") == "msg_reader":
        msg_reader = MsgReader({"id": "msg_reader", "value": mod.get("reader_value")})
    bands = effective_module_bands(mod, omit_ranges or [])
    if not bands:
        return []

    def _parse(v: object) -> int:
        if isinstance(v, int):
            return v
        s = str(v).strip().lower().replace("0x", "")
        return int(s, 16) if s else 0

    rom_last = max(0, len(rom) - 1)
    band_pairs: list[tuple[int, int]] = []
    for lo_s, hi_s in bands:
        lo, hi = _parse(lo_s), _parse(hi_s)
        if hi < lo:
            continue
        lo = max(0, min(lo, rom_last))
        hi = max(0, min(hi, rom_last))
        if hi >= lo:
            band_pairs.append((lo, hi))
    if not band_pairs:
        return []

    def _in_bands(a: int) -> bool:
        return any(lo <= a <= hi for lo, hi in band_pairs)

    excl = exclude_ranges or []

    def _in_exclude(a: int, length: int) -> bool:
        """候选 [a, a+length) 是否与「已导出地址带」重叠（跨模块 FCFS 认领）。"""
        if not excl or length <= 0:
            return False
        return any(a < hi and lo < a + length for lo, hi in excl)

    ptrs_map = ptr_index or {}

    include_items = _original_include_items(filt)
    out: list[dict] = []
    seen: set[int] = set()
    pins_only_fallthrough = False

    def _try_accept(
        a: int, body: bytes | None, *, pinned: bool = False
    ) -> None:
        if a in seen:
            return
        if not _in_bands(a):
            return
        if a < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= a < TITLE_LZ_BAND[1]:
            return
        raw = read_pcs(rom, a, 512)
        if raw is None and body is not None:
            raw = body
        if raw is None:
            return
        if _in_exclude(a, len(raw)):
            return
        # pinned（yaml 地址钉）：跳过 looks_like；形态闸交给其它 filter
        if use_looks_like and not pinned:
            if not looks_like_jp_text(raw):
                if body is None or not (
                    body.endswith(b"\xff")
                    and rom[a : a + len(body)] == body
                ):
                    return
                raw = body
        text = decode_pcs(raw)
        ptrs = list(ptrs_map.get(a, []))
        ctx = make_filter_context(
            fo=a,
            raw=raw,
            original=text,
            ptrs=ptrs,
            module_id=str(mid),
            module_type=mtype,
        )
        # yaml 白名单绑了 address/start-end 时允许无指针；跳过 UI 归属短标闸
        use_filt = filt
        if pinned and filt:
            skip = {
                "require_pointer_filter",
                "control_or_short_filter",
            }
            use_filt = [
                f
                for f in filt
                if str(f.get("type") or "") not in skip
            ]
        if use_filt and not apply_filters(ctx, use_filt):
            return
        seen.add(a)
        out.append(
            _stamp(
                {
                    "address": f"0x{BASE + a:08X}",
                    "original": text,
                    "original_hex": raw.hex(" "),
                    "byte_length": len(raw),
                    "is_pointer_based": bool(ptrs),
                    "pointer_sources": [
                        f"0x{BASE + q:08X}" for q in ptrs
                    ],
                    "pointer_addresses": [
                        f"0x{BASE + q:08X}" for q in ptrs
                    ],
                },
                mid=mid,
                game_code=game_code,
            )
        )

    if include_items is not None:
        # 包含模式：无地址绑定时 band 内 find；有地址时只读指定点/带
        for text, lo, hi in include_items:
            needle = _encode_jp_needle(text)
            needles: list[bytes] = []
            if needle and len(needle) >= 2:
                needles.append(needle)
            compact = _norm_original_key(text)
            if compact and compact != text:
                n2 = _encode_jp_needle(compact)
                if n2 and len(n2) >= 2 and n2 not in needles:
                    needles.append(n2)
            if not needles:
                continue

            if lo is not None and hi is not None:
                # 指定地址/窄带：只在该范围找，禁止全 ROM find 短词
                for body in needles:
                    a = lo
                    while a <= hi:
                        if a + len(body) <= len(rom) and rom[a : a + len(body)] == body:
                            _try_accept(a, body, pinned=True)
                        elif a == lo == hi:
                            # 单点：即使编码不完全一致也试 read_pcs + filter
                            _try_accept(a, body, pinned=True)
                        a += 1
                continue

            for body in needles:
                start = 0
                while True:
                    a = rom.find(body, start)
                    if a < 0:
                        break
                    start = a + 1
                    _try_accept(a, body)
        # 全部为地址钉：合并进常规 scan（msg_filter 等仍扫 band）
        # 含无地址白名单短词：保持旧行为，仅白名单命中
        pins_only_fallthrough = all(
            lo is not None and hi is not None for _t, lo, hi in include_items
        )
        if not pins_only_fallthrough:
            return out

    # msg_filter 白名单：不再「指针优先」——直接落入下方全盘 FF 针扫，
    # 由 msg_filter / dialogue_shape / control_or_short 等闸门逐条判定。
    # （原实现只验收「有 ROM 指针指向」的正文，会漏掉靠偏移索引、无指针的
    #   定址文本表，如 0x083B29C0 的「ドラゴン」随机词表。）

    def _start_rank(text: str, ptrs: list[int]) -> tuple[int, int]:
        """同 EOS 多起点时择优：(分, 长度)；分高优先，同分取更长（更早对齐）。"""
        score = 0
        if ptrs:
            score += 100
        t = (text or "").lstrip("\n")
        if t.startswith(("ママ『", "パパ『", "『", "「")) or t.startswith("\\"):
            score += 50
        elif t and (
            "\u3040" <= t[0] <= "\u30ff" or "\u4e00" <= t[0] <= "\u9fff"
        ):
            score += 20
        head = t[:12]
        if head.startswith("とく") or "とくけ" in head:
            score -= 40
        return (score, len(text or ""))

    def _scan_candidate(
        a: int, raw: bytes
    ) -> tuple[int, bytes, str, list[int]] | None:
        """a 处候选；同 EOS 内按对白起点质量择优（去掉垃圾前缀 / 句中误切）。"""
        if a < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= a < TITLE_LZ_BAND[1]:
            return None
        if a in seen:
            return None
        if use_looks_like and not looks_like_jp_text(raw):
            return None
        text = decode_pcs(raw)
        ptrs = list(ptrs_map.get(a, []))
        ctx = make_filter_context(
            fo=a,
            raw=raw,
            original=text,
            ptrs=ptrs,
            module_id=str(mid),
            module_type=mtype,
        )
        end = a + len(raw) - 1
        # 起点通过 filter → best 默认起点；否则置空，仅靠择优内的 valid 起点
        #（剥掉垃圾前缀 / 句中误切：如「べえねくぽえ…ママ『ほら…」整段垃圾前缀，
        #  起点被拒，但消息内部含真实对白，应让择优选中它而不是整段丢弃。）
        best_a, best_raw, best_text, best_ptrs = None, None, None, None
        best_rank: int | None = None
        if not filt or apply_filters(ctx, filt):
            best_a, best_raw, best_text, best_ptrs = a, raw, text, ptrs
            best_rank = _start_rank(text, ptrs)
        for a2 in range(a + 1, min(end, a + 96) + 1):
            b2 = rom[a2]
            if b2 == 0xFF or b2 == 0x00 or (b2 >= 0xF7 and b2 != 0xFC):
                continue
            raw2 = read_pcs(rom, a2, 512)
            if raw2 is None or a2 + len(raw2) - 1 != end:
                continue
            if a2 in seen or (use_looks_like and not looks_like_jp_text(raw2)):
                continue
            if a2 < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= a2 < TITLE_LZ_BAND[1]:
                continue
            text2 = decode_pcs(raw2)
            ptrs2 = list(ptrs_map.get(a2, []))
            ctx2 = make_filter_context(
                fo=a2,
                raw=raw2,
                original=text2,
                ptrs=ptrs2,
                module_id=str(mid),
                module_type=mtype,
            )
            if filt and not apply_filters(ctx2, filt):
                continue
            rank2 = _start_rank(text2, ptrs2)
            if best_rank is None or rank2 > best_rank:
                best_a, best_raw, best_text, best_ptrs = a2, raw2, text2, ptrs2
                best_rank = rank2
        if best_a is None:
            return None
        return best_a, best_raw, best_text, best_ptrs

    pcs_maxlen = 512
    for lo, hi in band_pairs:
        a = lo
        while a <= hi:
            b = rom[a]
            # 0xFC = 扩展控制码前缀；勿与 F7–FB / FE / FF 一并跳过
            if b == 0xFF or b == 0x00 or (b >= 0xF7 and b != 0xFC):
                a += 1
                continue
            raw = read_pcs(rom, a, pcs_maxlen)
            if raw is None:
                ff = rom.find(b"\xff", a + pcs_maxlen, hi + 1)
                if ff < 0:
                    break
                a = max(a + 1, ff - (pcs_maxlen - 1))
                continue
            end = a + len(raw) - 1
            if msg_reader is not None:
                # reader=msg_reader：用语料 needle 定位真实正文起点；命中返回修整
                # 内容（ReaderHit），未命中/全空白返回 None。以修整后的 fo/raw 走
                # 单点 filter 闸门后输出，不做择优（择优会污染 msg 语料锚定）。
                hit = msg_reader.read(rom, a, raw, ptrs_map, pcs_maxlen)
                if hit is None:
                    a = end + 1
                    continue
                if _in_exclude(hit.fo, len(hit.raw)):
                    a = end + 1
                    continue
                hctx = make_filter_context(
                    fo=hit.fo,
                    raw=hit.raw,
                    original=hit.original,
                    ptrs=hit.ptrs,
                    module_id=str(mid),
                    module_type=mtype,
                )
                if filt and not apply_filters(hctx, filt):
                    a = end + 1
                    continue
                seen.add(hit.fo)
                out.append(
                    _stamp(
                        {
                            "address": f"0x{BASE + hit.fo:08X}",
                            "original": hit.original,
                            "original_hex": hit.raw.hex(" "),
                            "byte_length": len(hit.raw),
                            "is_pointer_based": bool(hit.ptrs),
                            "pointer_sources": [
                                f"0x{BASE + q:08X}" for q in hit.ptrs
                            ],
                            "pointer_addresses": [
                                f"0x{BASE + q:08X}" for q in hit.ptrs
                            ],
                        },
                        mid=mid,
                        game_code=game_code,
                    )
                )
                a = end + 1
                continue
            cand = _scan_candidate(a, raw)
            if cand is None:
                a = end + 1
                continue
            best_a, best_raw, best_text, best_ptrs = cand
            if _in_exclude(best_a, len(best_raw)):
                a = end + 1
                continue
            seen.add(best_a)
            out.append(
                _stamp(
                    {
                        "address": f"0x{BASE + best_a:08X}",
                        "original": best_text,
                        "original_hex": best_raw.hex(" "),
                        "byte_length": len(best_raw),
                        "is_pointer_based": bool(best_ptrs),
                        "pointer_sources": [
                            f"0x{BASE + q:08X}" for q in best_ptrs
                        ],
                        "pointer_addresses": [
                            f"0x{BASE + q:08X}" for q in best_ptrs
                        ],
                    },
                    mid=mid,
                    game_code=game_code,
                )
            )
            a = end + 1
    return out


def extract_module(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
    omit_ranges: list[tuple[int, int]] | None = None,
    exclude_ranges: list[tuple[int, int]] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    rtype = str(mod.get("type") or "scan")
    if rtype == "stride":
        return extract_stride(rom, mod, game_code, filters=filters)
    if rtype == "struct":
        return extract_struct(rom, mod, game_code, filters=filters)
    if rtype in ("stride_ptr", "ptr_stride"):
        return extract_stride_ptr(rom, mod, game_code, filters=filters)
    if rtype in ("scan", "addr_bands"):
        return extract_scan(
            rom,
            mod,
            game_code,
            ptr_index=ptr_index,
            omit_ranges=omit_ranges,
            exclude_ranges=exclude_ranges,
            filters=filters,
        )
    # needle/prefix/pointer: corpus already in texts.json; no Meowth re-scan
    return []


def _build_ptr_index(rom: bytes) -> dict[int, list[int]]:
    """ROM 内 LE 指针 → 目标正文偏移。

    - 对齐扫（步长 4）：常规指针表 / loadword 池。
    - 非对齐扫：脚本里嵌的 ``xx <ptr>``（高字节须为 0x08/0x09）。
    跳过标题 LZ 带内的假指针槽。
    """
    ptr_index: dict[int, list[int]] = {}
    n = len(rom)
    tlz_lo, tlz_hi = TITLE_LZ_BAND

    def _add(o: int) -> None:
        if tlz_lo <= o < tlz_hi:
            return
        v = struct.unpack_from("<I", rom, o)[0]
        if BASE <= v < BASE + n:
            so = v - BASE
            if so >= SCRIPT_BANK_MIN and so < n:
                ptr_index.setdefault(so, []).append(o)

    o = 0
    while o + 4 <= n:
        _add(o)
        o += 4
    # 非对齐：仅当高字节像 ROM 指针，避免 O(n) 全解
    for o in range(1, n - 3):
        if (o & 3) == 0:
            continue
        if rom[o + 3] not in (0x08, 0x09):
            continue
        _add(o)
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
    from util._script_walk import set_script_roots

    set_script_roots((cfg.get("texts") or {}).get("script_roots") or {})
    rom_code = identify_rom(rom)
    if rom_code.upper() != game_code.upper():
        print(
            f"[!] ROM game_code {rom_code!r} != config {game_code!r}",
            file=sys.stderr,
        )

    all_modules = list(cfg["texts"]["modules"] or [])
    modules_dict_full = _modules_as_dict(all_modules)
    omit_ranges = get_texts_omit_ranges(cfg)
    if omit_ranges:
        print(
            f"[i] texts.omit_ranges ×{len(omit_ranges)} "
            f"(bytes={sum(b - a + 1 for a, b in omit_ranges)})"
        )

    target_idx: int | None = None
    claimed_by: dict[str, str] = {}
    if module:
        for i, m in enumerate(all_modules):
            if (m.get("id") or "") == module:
                target_idx = i
                break
        if target_idx is None:
            known = list(modules_dict_full.keys())
            raise SystemExit(
                f"module not found: {module!r}; known={known}"
            )
        modules = [all_modules[target_idx]]
        modules_dict = _modules_as_dict(modules)
        # 单模块：干跑前序，模拟整表 FCFS 归属
        scan_scope = all_modules[: target_idx + 1]
    else:
        modules = all_modules
        modules_dict = modules_dict_full
        scan_scope = all_modules

    need_ptr = any(
        str(m.get("type") or "scan") in ("scan", "addr_bands") for m in scan_scope
    )
    ptr_index: dict[int, list[int]] | None = None
    if need_ptr:
        print("[i] building pointer index…")
        ptr_index = _build_ptr_index(rom)

    if target_idx is not None and target_idx > 0:
        print(f"[i] FCFS dry-run: {target_idx} earlier module(s)…")
        for pred in all_modules[:target_idx]:
            pid = str(pred.get("id") or "")
            rtype = str(pred.get("type") or "scan")
            chunk = extract_module(
                rom,
                pred,
                game_code,
                ptr_index=ptr_index,
                omit_ranges=omit_ranges,
                filters=resolve_filters(cfg, pred),
            )
            if not chunk and rtype in ("needle", "prefix", "pointer"):
                continue
            n_new = 0
            for e in chunk:
                addr = e.get("address") or ""
                if not addr or addr in claimed_by:
                    continue
                claimed_by[addr] = pid
                n_new += 1
            print(f"  (claim) [{pid}] type={rtype} -> +{n_new}")

    entries: list[dict] = []
    seen_addr: set[str] = set()
    skipped: dict[str, int] = {}
    shadow_counts: dict[str, int] = {}
    # 已导出的字节带（跨模块 FCFS 认领）：后扫描的模块跳过落在这些带内的候选，
    # 防止「带颜色码完整文本」与「剥码假名起点」被两模块重复导出造成地址重叠。
    exported_bands: list[tuple[int, int]] = []

    for mod in modules:
        mid = mod.get("id") or ""
        rtype = str(mod.get("type") or "scan")
        chunk = extract_module(
            rom,
            mod,
            game_code,
            ptr_index=ptr_index,
            omit_ranges=omit_ranges,
            exclude_ranges=exported_bands,
            filters=resolve_filters(cfg, mod),
        )
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
                bl = e.get("byte_length") or 0
                if bl > 0:
                    lo = _to_file_offset(parse_int(addr), len(rom), default=0)
                    exported_bands.append((lo, lo + bl))
            if addr and addr in claimed_by:
                by = claimed_by[addr]
                e = dict(e)
                e["shadowed_by"] = by
                shadow_counts[by] = shadow_counts.get(by, 0) + 1
            entries.append(_order_entry(e))
            n += 1
        print(f"  [{mid}] type={rtype} -> {n}")

    if skipped:
        print(f"[i] skipped module types (not implemented): {skipped}")
    if shadow_counts:
        n_shadow = sum(shadow_counts.values())
        by_s = ", ".join(f"{k}×{v}" for k, v in sorted(shadow_counts.items()))
        print(
            f"[i] FCFS shadow: {n_shadow}/{len(entries)} entries "
            f"would be claimed earlier ({by_s})"
        )

    out_path = refuse_pipeline_write(
        output or default_output_path(game_id, module=module)
    )
    # modules / styles 只来自 yaml（不与旧 texts.json 合并，避免改 label/id 后残留）
    styles_dict = _yaml_styles_dict(cfg)
    doc = {
        "game": game_id,
        "game_id": game_id,
        "source_lang": "ja",
        "styles": styles_dict,
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


# ---------------------------------------------------------------------------
# remove-preview / remove：整句洞 merge 进 texts.omit_ranges（不切碎模块 ranges）
# ---------------------------------------------------------------------------


def normalize_file_off(addr: int | str) -> int:
    """VMA（0x08……）或文件偏移 → 文件偏移。"""
    a = parse_addr(addr)
    if a >= BASE:
        a -= BASE
    return a


def _fmt_file_off(n: int) -> str:
    return f"0x{n:X}"


def _fmt_span(a: int, b: int) -> str:
    if a == b:
        return _fmt_file_off(a)
    return f"{_fmt_file_off(a)}–{_fmt_file_off(b)}(+{b - a + 1})"


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """合并重叠或相邻闭区间。"""
    if not spans:
        return []
    xs = sorted((min(a, b), max(a, b)) for a, b in spans)
    out: list[tuple[int, int]] = [xs[0]]
    for a, b in xs[1:]:
        la, lb = out[-1]
        if a <= lb + 1:
            out[-1] = (la, max(lb, b))
        else:
            out.append((a, b))
    return out


def split_band(
    lo: int, hi: int, spans: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """``[lo, hi]`` 挖掉与 spans 相交的整段 → 若干闭区间。"""
    if hi < lo:
        return []
    clipped: list[tuple[int, int]] = []
    for a, b in spans:
        if b < lo or a > hi:
            continue
        clipped.append((max(a, lo), min(b, hi)))
    clipped = merge_spans(clipped)
    if not clipped:
        return [(lo, hi)]
    out: list[tuple[int, int]] = []
    cur = lo
    for a, b in clipped:
        if a > cur:
            out.append((cur, a - 1))
        cur = b + 1
    if cur <= hi:
        out.append((cur, hi))
    return [(a, b) for a, b in out if b >= a]


def parse_addrs_arg(s: str | None, *, allow_empty: bool = False) -> list[int]:
    """``0xA,0xB`` → 文件偏移列表（去重保序）。"""
    seen: set[int] = set()
    out: list[int] = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        fo = normalize_file_off(part)
        if fo in seen:
            continue
        seen.add(fo)
        out.append(fo)
    if not out and not allow_empty:
        raise SystemExit("--addrs 不能为空")
    return out


def load_404_originals(path: Path) -> set[str]:
    """读 texts_translated.json，收集 status==404 的 original。"""
    if not path.is_file():
        raise SystemExit(f"texts_translated.json 不存在: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"无法读取 texts_translated.json: {path}: {e}") from e
    if not isinstance(raw, list):
        raise SystemExit(
            f"texts_translated.json 应为 status 数组: {path}"
        )
    out: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            st = int(item.get("status") or 0)
        except (TypeError, ValueError):
            continue
        if st != 404:
            continue
        orig = item.get("original")
        if isinstance(orig, str) and orig:
            out.add(orig)
    return out


def _load_texts_span_index(texts_path: Path) -> dict[int, int]:
    """address(file_off) → byte_length（取最大，防重复）。"""
    if not texts_path.is_file():
        return {}
    try:
        doc = json.loads(texts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    idx: dict[int, int] = {}
    for e in doc.get("entries") or []:
        if not isinstance(e, dict):
            continue
        addr = e.get("address") or ""
        if not addr:
            continue
        fo = normalize_file_off(addr)
        try:
            bl = int(e.get("byte_length") or 0)
        except (TypeError, ValueError):
            bl = 0
        if bl < 1:
            bl = 1
        prev = idx.get(fo, 0)
        if bl > prev:
            idx[fo] = bl
    return idx


def span_for_start(
    fo: int,
    *,
    texts_index: dict[int, int],
    rom: bytes | None,
) -> tuple[int, int]:
    """起点 → 整句闭区间 ``[fo, fo+L-1]``。优先 texts.json，其次 ROM PCS。"""
    bl = texts_index.get(fo, 0)
    if bl >= 1:
        return (fo, fo + bl - 1)
    if rom is not None and 0 <= fo < len(rom):
        raw = read_pcs(rom, fo, MAX_PCS)
        if raw:
            return (fo, fo + len(raw) - 1)
    return (fo, fo)


def expand_starts_to_spans(
    starts: list[int],
    *,
    texts_path: Path,
    rom: bytes | None,
) -> list[tuple[int, int]]:
    idx = _load_texts_span_index(texts_path)
    spans = [span_for_start(fo, texts_index=idx, rom=rom) for fo in starts]
    return merge_spans(spans)


def addrs_from_translated(
    translated_path: Path, texts_path: Path
) -> tuple[list[int], dict[str, Any]]:
    """404 originals → texts.json 反查起点地址（整句长度在 expand 时取）。"""
    bad = load_404_originals(translated_path)
    if not texts_path.is_file():
        raise SystemExit(f"texts.json 不存在（无法反查地址）: {texts_path}")
    try:
        doc = json.loads(texts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"无法读取 texts.json: {texts_path}: {e}") from e

    seen: set[int] = set()
    addrs: list[int] = []
    matched_origs: set[str] = set()
    for e in doc.get("entries") or []:
        if not isinstance(e, dict):
            continue
        orig = e.get("original")
        if not isinstance(orig, str) or orig not in bad:
            continue
        addr = e.get("address") or ""
        if not addr:
            continue
        fo = normalize_file_off(addr)
        matched_origs.add(orig)
        if fo in seen:
            continue
        seen.add(fo)
        addrs.append(fo)

    unmatched = sorted(bad - matched_origs)
    stats: dict[str, Any] = {
        "n_404": len(bad),
        "n_addrs": len(addrs),
        "n_unmatched": len(unmatched),
        "unmatched_sample": unmatched[:5],
        "translated_path": str(translated_path),
        "texts_path": str(texts_path),
    }
    return addrs, stats


def resolve_remove_starts(
    addrs_arg: str | None,
    from_translated: str | None,
    game_id: str,
) -> tuple[list[int], dict[str, Any] | None]:
    """合并 ``--addrs`` 与 ``--from-translated`` → 坏句起点列表。"""
    starts: list[int] = []
    seen: set[int] = set()
    if addrs_arg is not None and str(addrs_arg).strip():
        for fo in parse_addrs_arg(addrs_arg, allow_empty=True):
            if fo not in seen:
                seen.add(fo)
                starts.append(fo)

    translated_stats: dict[str, Any] | None = None
    if from_translated is not None:
        tpath = (
            default_translated_path(game_id)
            if str(from_translated).strip() == ""
            else Path(from_translated)
        )
        texts_path = default_output_path(game_id)
        extra, translated_stats = addrs_from_translated(tpath, texts_path)
        for fo in extra:
            if fo not in seen:
                seen.add(fo)
                starts.append(fo)

    return starts, translated_stats


def _span_overlaps(lo: int, hi: int, a: int, b: int) -> bool:
    return not (b < lo or a > hi)


def _fo_in_spans(spans: list[tuple[int, int]], fo: int) -> bool:
    return any(a <= fo <= b for a, b in spans)


def spans_hitting_modules(
    modules: list[dict], spans: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """只保留至少落在某个模块粗带内的 omit span。"""
    spans = merge_spans(spans)
    hit: list[tuple[int, int]] = []
    for a, b in spans:
        for mod in modules:
            for lo, hi in module_band_tuples(mod):
                if _span_overlaps(lo, hi, a, b):
                    hit.append((a, b))
                    break
            else:
                continue
            break
    return merge_spans(hit)


def module_hit_summary(
    modules: list[dict], spans: list[tuple[int, int]]
) -> list[dict[str, Any]]:
    """预览：每个模块被哪些洞命中（不改 ranges）。"""
    spans = merge_spans(spans)
    rows: list[dict[str, Any]] = []
    for mod in modules:
        mid = mod.get("id") or ""
        bands = module_band_tuples(mod)
        if not bands:
            continue
        hits: list[tuple[int, int]] = []
        for lo, hi in bands:
            for a, b in spans:
                if _span_overlaps(lo, hi, a, b):
                    hits.append((max(a, lo), min(b, hi)))
        hits = merge_spans(hits)
        if hits:
            rows.append({"id": mid, "hits": hits, "bands": bands})
    return rows


def preview_lost_rom_strings(
    rom: bytes, spans: list[tuple[int, int]]
) -> list[dict[str, Any]]:
    """坏句起点的 PCS 解码（对照挖掉的整段）。"""
    from meowth.jp_pcs import decode_pcs

    rows: list[dict[str, Any]] = []
    for fo, end in spans:
        span_len = end - fo + 1
        if fo < 0 or fo >= len(rom):
            rows.append(
                {
                    "address": f"0x{BASE + fo:08X}",
                    "file_off": _fmt_file_off(fo),
                    "span": _fmt_span(fo, end),
                    "ok": False,
                    "reason": "地址超出 ROM",
                }
            )
            continue
        raw = read_pcs(rom, fo, MAX_PCS)
        if raw is None:
            rows.append(
                {
                    "address": f"0x{BASE + fo:08X}",
                    "file_off": _fmt_file_off(fo),
                    "span": _fmt_span(fo, end),
                    "ok": False,
                    "reason": "非 PCS 起点 / 解码失败",
                    "omit_length": span_len,
                }
            )
            continue
        text = decode_pcs(raw)
        rows.append(
            {
                "address": f"0x{BASE + fo:08X}",
                "file_off": _fmt_file_off(fo),
                "span": _fmt_span(fo, end),
                "ok": True,
                "byte_length": len(raw),
                "omit_length": span_len,
                "original": text,
                "original_hex": raw.hex(" "),
            }
        )
    return rows


def preview_texts_json_hits(
    texts_path: Path, spans: list[tuple[int, int]]
) -> list[dict[str, Any]]:
    """texts.json 中起点落在剔除区间内的条目。"""
    if not texts_path.is_file():
        return []
    try:
        doc = json.loads(texts_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    hits: list[dict[str, Any]] = []
    for e in doc.get("entries") or []:
        addr = e.get("address") or ""
        if not addr:
            continue
        fo = normalize_file_off(addr)
        if not _fo_in_spans(spans, fo):
            continue
        hits.append(
            {
                "id": e.get("id") or "",
                "module": e.get("module") or "",
                "address": addr,
                "original": (e.get("original") or "")[:80],
            }
        )
    return hits


def _print_omit_plan(
    *,
    old_omit: list[tuple[int, int]],
    new_omit: list[tuple[int, int]],
    added: list[tuple[int, int]],
    module_rows: list[dict[str, Any]],
    rom_lost: list[dict[str, Any]],
    json_hits: list[dict[str, Any]],
) -> None:
    print(
        f"[i] texts.omit_ranges: {len(old_omit)} → {len(new_omit)} "
        f"(+{len(added)} merged spans)"
    )
    if added:
        sample = [_fmt_span(a, b) for a, b in added[:12]]
        if len(added) > 12:
            sample.append(f"…(+{len(added) - 12})")
        print(f"[i] new holes: {sample}")

    if not module_rows:
        print("[i] 无模块粗带命中这些地址（仍会写入全局 omit）")
    else:
        print(f"[i] 命中 {len(module_rows)} 个模块粗带（ranges 不切开）：")
        for p in module_rows:
            hits = p["hits"]
            if len(hits) <= 12:
                hits_s = [_fmt_span(a, b) for a, b in hits]
            else:
                hits_s = [_fmt_span(a, b) for a, b in hits[:8]] + [
                    f"…(+{len(hits) - 8})"
                ]
            print(f"  ## {p['id']}  hits={hits_s}")

    print("\n## ROM 将少掉的内容（整句区间）")
    for r in rom_lost[:50]:
        if r.get("ok"):
            orig = (r.get("original") or "").replace("\n", "\\n")
            if len(orig) > 100:
                orig = orig[:100] + "…"
            print(
                f"  {r.get('span') or r['address']}  "
                f"len={r.get('omit_length') or r.get('byte_length')}  {orig!r}"
            )
        else:
            print(
                f"  {r.get('span') or r['address']}  [{r.get('reason')}]"
            )
    if len(rom_lost) > 50:
        print(f"  … 另有 {len(rom_lost) - 50} 条")

    print(f"\n## texts.json 将删除的条目：{len(json_hits)}")
    for h in json_hits[:50]:
        print(
            f"  [{h.get('module')}] {h.get('address')}  "
            f"{(h.get('original') or '')!r}"
        )
    if len(json_hits) > 50:
        print(f"  … 另有 {len(json_hits) - 50} 条")


def apply_omit_to_yaml(
    cfg: dict, new_omit: list[tuple[int, int]]
) -> dict:
    set_texts_omit_ranges(cfg, new_omit)
    return cfg


def save_yaml_config(path: Path, cfg: dict) -> None:
    try:
        import yaml
    except ImportError as e:
        raise SystemExit("需要 PyYAML：pip install pyyaml") from e

    class _Dumper(yaml.SafeDumper):
        pass

    def _str_representer(dumper, data):
        if isinstance(data, str) and data.startswith("0x"):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)
        return dumper.represent_str(data)

    _Dumper.add_representer(str, _str_representer)
    text = yaml.dump(
        cfg,
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    path.write_text(text, encoding="utf-8")


def sync_texts_json_omit(
    texts_path: Path,
    *,
    spans: list[tuple[int, int]],
    omit_all: list[tuple[int, int]],
    cfg: dict,
) -> tuple[int, int]:
    """同步全局 omit 与 modules 元数据；只删除本次 ``spans`` 命中的条目。"""
    if not texts_path.is_file():
        return 0, 0
    doc = json.loads(texts_path.read_text(encoding="utf-8"))
    doc["omit_ranges"] = omit_ranges_to_yaml(omit_all)

    styles_dict = _yaml_styles_dict(cfg)
    if styles_dict:
        doc["styles"] = styles_dict

    mods_obj = doc.get("modules")
    if not isinstance(mods_obj, dict):
        mods_obj = {}
        doc["modules"] = mods_obj

    n_mod = 0
    for mod in cfg.get("texts", {}).get("modules") or []:
        mid = mod.get("id") or ""
        if not mid:
            continue
        meta = dict(mods_obj.get(mid) or {})
        if mod.get("start") is not None:
            meta["start"] = mod["start"]
        if mod.get("end") is not None:
            meta["end"] = mod["end"]
        if mod.get("ranges"):
            meta["ranges"] = list(mod["ranges"])
        else:
            meta.pop("ranges", None)
        for k in (
            "label",
            "group",
            "default",
            "description",
            "type",
            "style",
            "relocate",
            "hook",
            "reuse_slot_padding",
        ):
            if k in mod:
                meta[k] = mod[k]
        if "style" in mod:
            meta.pop("left", None)
        elif "left" in mod:
            meta["left"] = mod["left"]
        mods_obj[mid] = meta
        n_mod += 1

    kill = merge_spans(spans)
    entries = doc.get("entries") or []
    kept: list[dict] = []
    n_del = 0
    for e in entries:
        addr = e.get("address") or ""
        if not addr:
            kept.append(e)
            continue
        fo = normalize_file_off(addr)
        if kill and _fo_in_spans(kill, fo):
            n_del += 1
            continue
        kept.append(e)
    doc["entries"] = kept
    doc["count"] = len(kept)
    refuse_pipeline_write(texts_path)
    texts_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return n_del, n_mod


def _print_cuts_summary(spans: list[tuple[int, int]]) -> None:
    if len(spans) <= 20:
        print(f"[i] omit(spans)={[ _fmt_span(a, b) for a, b in spans ]}")
    else:
        sample = ", ".join(_fmt_span(a, b) for a, b in spans[:8])
        total_bytes = sum(b - a + 1 for a, b in spans)
        print(
            f"[i] omit(spans)=[{sample}, …] "
            f"spans={len(spans)} bytes={total_bytes}"
        )


def merge_nearby_ranges(
    pieces: list[tuple[int, int]], *, max_gap: int = 32
) -> list[tuple[int, int]]:
    """合并间距 ≤ max_gap 的碎段；大缝保留为多段 ranges（不进 omit）。"""
    if not pieces:
        return []
    xs = sorted((min(a, b), max(a, b)) for a, b in pieces)
    out: list[tuple[int, int]] = [xs[0]]
    for a, b in xs[1:]:
        la, lb = out[-1]
        gap = a - lb - 1
        if gap <= max_gap:
            out[-1] = (la, max(lb, b))
        else:
            out.append((a, b))
    return out


def coalesce_module_to_cover(
    mod: dict,
    *,
    max_gap: int = 32,
) -> list[tuple[int, int]] | None:
    """碎 ranges → 邻近合并后的粗带列表。不产生 omit 洞。"""
    rtype = str(mod.get("type") or "scan")
    if rtype not in ("scan", "addr_bands"):
        return None
    pieces = module_band_tuples(mod)
    if len(pieces) <= 1:
        return None
    merged = merge_nearby_ranges(pieces, max_gap=max_gap)
    if merged == sorted((min(a, b), max(a, b)) for a, b in pieces):
        if len(merged) == len(pieces):
            return None
    return merged


def migrate_fragmented_ranges(
    cfg: dict, *, max_gap: int = 32
) -> dict[str, int]:
    """碎 ranges 邻近合并；确保 texts.omit_ranges 存在。大缝不进 omit。"""
    texts = cfg.setdefault("texts", {})
    if "omit_ranges" not in texts:
        texts["omit_ranges"] = list(texts.get("omit_ranges") or [])
    mods = list(texts.get("modules") or [])
    n_mod = 0
    n_ranges_before = 0
    n_ranges_after = 0
    for mod in mods:
        pieces = module_band_tuples(mod)
        n_before = len(pieces) if pieces else (1 if mod.get("start") else 0)
        n_ranges_before += n_before
        merged = coalesce_module_to_cover(mod, max_gap=max_gap)
        if not merged:
            n_ranges_after += n_before
            continue
        mod["start"] = _fmt_file_off(merged[0][0])
        mod["end"] = _fmt_file_off(merged[-1][1])
        mod["ranges"] = [
            {"start": _fmt_file_off(a), "end": _fmt_file_off(b)}
            for a, b in merged
        ]
        n_mod += 1
        n_ranges_after += len(merged)
    # 保留已有 omit，不因合并而追加大缝
    omit = get_texts_omit_ranges(cfg)
    set_texts_omit_ranges(cfg, omit)
    return {
        "modules_coalesced": n_mod,
        "ranges_before": n_ranges_before,
        "ranges_after": n_ranges_after,
        "omit_before": len(omit),
        "omit_after": len(omit),
        "holes_added": 0,
        "max_gap": max_gap,
    }


def sync_texts_json_modules_meta(texts_path: Path, cfg: dict) -> int:
    """只同步 modules / styles 元数据 / omit_ranges 快照，不删条目。"""
    if not texts_path.is_file():
        return 0
    doc = json.loads(texts_path.read_text(encoding="utf-8"))
    doc["omit_ranges"] = omit_ranges_to_yaml(get_texts_omit_ranges(cfg))
    styles_dict = _yaml_styles_dict(cfg)
    if styles_dict:
        doc["styles"] = styles_dict
    mods_obj = doc.get("modules")
    if not isinstance(mods_obj, dict):
        mods_obj = {}
        doc["modules"] = mods_obj
    n_mod = 0
    for mod in cfg.get("texts", {}).get("modules") or []:
        mid = mod.get("id") or ""
        if not mid:
            continue
        meta = dict(mods_obj.get(mid) or {})
        if mod.get("start") is not None:
            meta["start"] = mod["start"]
        if mod.get("end") is not None:
            meta["end"] = mod["end"]
        if mod.get("ranges"):
            meta["ranges"] = list(mod["ranges"])
        else:
            meta.pop("ranges", None)
        for k in (
            "label",
            "group",
            "default",
            "description",
            "type",
            "style",
            "relocate",
            "hook",
            "reuse_slot_padding",
        ):
            if k in mod:
                meta[k] = mod[k]
        # style 取代模块顶栏 left
        if "style" in mod:
            meta.pop("left", None)
        elif "left" in mod:
            meta["left"] = mod["left"]
        else:
            meta.pop("left", None)
        mods_obj[mid] = meta
        n_mod += 1
    refuse_pipeline_write(texts_path)
    texts_path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return n_mod


def cmd_migrate_omit(
    rom_path: Path | None = None,
    *,
    config_path: Path | None = None,
    max_gap: int = 32,
) -> int:
    if config_path is not None:
        cfg_path = config_path
    elif rom_path is not None:
        cfg_path = resolve_config(rom_path, None)
    else:
        cfg_path = CONFIGS_DIR / "POKEMON_RUBY_AXVJ00.yaml"
    cfg = load_yaml_config(cfg_path)
    stats = migrate_fragmented_ranges(cfg, max_gap=max_gap)
    save_yaml_config(cfg_path, cfg)
    print(f"[ok] migrate-omit → {cfg_path}")
    print(
        f"     modules_coalesced={stats['modules_coalesced']}  "
        f"ranges {stats['ranges_before']}→{stats['ranges_after']}  "
        f"omit={stats['omit_after']}  max_gap={stats['max_gap']}"
    )
    game_id = str(cfg.get("game_id") or "POKEMON_RUBY_AXVJ00")
    texts_path = default_output_path(game_id)
    if texts_path.is_file():
        n_mod = sync_texts_json_modules_meta(texts_path, cfg)
        print(f"[ok] synced texts.json modules meta ×{n_mod} (entries unchanged)")
    return 0


def cmd_remove_preview(
    rom_path: Path,
    addrs: str | None,
    *,
    from_translated: str | None = None,
    config_path: Path | None = None,
) -> int:
    cfg_path = resolve_config(rom_path, config_path)
    cfg = load_yaml_config(cfg_path)
    game_id = str(cfg.get("game_id") or rom_path.stem)
    starts, tstats = resolve_remove_starts(addrs, from_translated, game_id)
    print(f"[i] config={cfg_path}")
    if tstats is not None:
        print(
            f"[i] from-translated: 404={tstats['n_404']} → "
            f"addrs={tstats['n_addrs']} (unmatched={tstats['n_unmatched']}) "
            f"path={tstats['translated_path']}"
        )
        for s in tstats.get("unmatched_sample") or []:
            preview = s.replace("\n", "\\n")
            if len(preview) > 60:
                preview = preview[:60] + "…"
            _safe_print(f"    unmatched: {preview!r}")
    if not starts:
        print("[i] 无剔除地址，无需修改")
        return 0
    texts_path = default_output_path(game_id)
    rom = rom_path.read_bytes()
    spans = expand_starts_to_spans(starts, texts_path=texts_path, rom=rom)
    spans = spans_hitting_modules(list(cfg["texts"]["modules"] or []), spans)
    _print_cuts_summary(spans)
    old_omit = get_texts_omit_ranges(cfg)
    new_omit = merge_spans(old_omit + spans)
    added: list[tuple[int, int]] = []
    for a, b in spans:
        added.extend(split_band(a, b, old_omit))
    added = merge_spans(added)
    module_rows = module_hit_summary(list(cfg["texts"]["modules"] or []), spans)
    rom_lost = preview_lost_rom_strings(rom, spans)
    json_hits = preview_texts_json_hits(texts_path, spans)
    _print_omit_plan(
        old_omit=old_omit,
        new_omit=new_omit,
        added=added,
        module_rows=module_rows,
        rom_lost=rom_lost,
        json_hits=json_hits,
    )
    return 0


def cmd_remove(
    rom_path: Path,
    addrs: str | None,
    *,
    from_translated: str | None = None,
    config_path: Path | None = None,
) -> int:
    cfg_path = resolve_config(rom_path, config_path)
    cfg = load_yaml_config(cfg_path)
    game_id = str(cfg.get("game_id") or rom_path.stem)
    starts, tstats = resolve_remove_starts(addrs, from_translated, game_id)
    print(f"[i] config={cfg_path}")
    if tstats is not None:
        print(
            f"[i] from-translated: 404={tstats['n_404']} → "
            f"addrs={tstats['n_addrs']} (unmatched={tstats['n_unmatched']}) "
            f"path={tstats['translated_path']}"
        )
        for s in tstats.get("unmatched_sample") or []:
            preview = s.replace("\n", "\\n")
            if len(preview) > 60:
                preview = preview[:60] + "…"
            _safe_print(f"    unmatched: {preview!r}")
    if not starts:
        print("[i] 无剔除地址，未写入")
        return 0
    texts_path = default_output_path(game_id)
    rom = rom_path.read_bytes()
    spans = expand_starts_to_spans(starts, texts_path=texts_path, rom=rom)
    spans = spans_hitting_modules(list(cfg["texts"]["modules"] or []), spans)
    if not spans:
        print("[i] 无模块粗带命中，未写入")
        return 0
    _print_cuts_summary(spans)
    old_omit = get_texts_omit_ranges(cfg)
    new_omit = merge_spans(old_omit + spans)
    added: list[tuple[int, int]] = []
    for a, b in spans:
        added.extend(split_band(a, b, old_omit))
    added = merge_spans(added)
    module_rows = module_hit_summary(list(cfg["texts"]["modules"] or []), spans)
    rom_lost = preview_lost_rom_strings(rom, spans)
    json_hits = preview_texts_json_hits(texts_path, spans)
    _print_omit_plan(
        old_omit=old_omit,
        new_omit=new_omit,
        added=added,
        module_rows=module_rows,
        rom_lost=rom_lost,
        json_hits=json_hits,
    )

    apply_omit_to_yaml(cfg, new_omit)
    save_yaml_config(cfg_path, cfg)
    print(f"\n[ok] wrote yaml omit_ranges → {cfg_path}")

    n_del, n_mod = sync_texts_json_omit(
        texts_path, spans=spans, omit_all=new_omit, cfg=cfg
    )
    if texts_path.is_file():
        print(
            f"[ok] synced texts.json → {texts_path} "
            f"(modules={n_mod}, deleted_entries={n_del})"
        )
    else:
        print(f"[i] texts.json 不存在，跳过同步: {texts_path}")
    return 0


# ---------------------------------------------------------------------------
# mark-404：脏译文标 404 / 清洗
# ---------------------------------------------------------------------------

_GARBLED_MARK_RE = re.compile(r"这是一段(?:明显)?乱码")


def _translated_has_garbled_mark(tr: str) -> bool:
    return bool(_GARBLED_MARK_RE.search(tr or ""))


def _has_useful_zh(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]{2,}", s or ""))


def clean_garbled_translated(tr: str) -> str | None:
    """去掉乱码标记与空 ||| 段；无可用汉字则返回 None。"""
    parts = re.split(r"\s*\|\|\|\s*", tr or "")
    kept: list[str] = []
    for p in parts:
        rest = _GARBLED_MARK_RE.sub("", p)
        rest = re.sub(r"^[|\\\s]+|[|\\\s]+$", "", rest)
        rest = rest.strip()
        if not rest:
            continue
        if _has_useful_zh(rest):
            kept.append(rest)
    if not kept:
        return None
    if len(kept) == 1:
        return kept[0]
    return "\n".join(kept)


def mark_404_in_translated(
    translated_path: Path,
) -> dict[str, int]:
    """改写 texts_translated.json。返回统计。"""
    if not translated_path.is_file():
        raise SystemExit(f"texts_translated.json 不存在: {translated_path}")
    try:
        rows = json.loads(translated_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"无法读取: {translated_path}: {e}") from e
    if not isinstance(rows, list):
        raise SystemExit(f"应为 status 数组: {translated_path}")

    n_404 = 0
    n_cleaned = 0
    n_unchanged = 0
    out: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            st = int(item.get("status") or 0)
        except (TypeError, ValueError):
            continue
        orig = item.get("original")
        if not isinstance(orig, str) or not orig:
            continue
        if st == 404:
            out.append({"status": 404, "original": orig})
            n_unchanged += 1
            continue
        if st != 200:
            out.append(item)
            n_unchanged += 1
            continue
        tr = item.get("translated") or ""
        if not isinstance(tr, str):
            tr = ""
        if not _translated_has_garbled_mark(tr):
            if GarbageHeuristicFilter.looks_garbage(orig):
                out.append({"status": 404, "original": orig})
                n_404 += 1
                continue
            out.append(
                {"status": 200, "original": orig, "translated": tr}
            )
            n_unchanged += 1
            continue

        cleaned = clean_garbled_translated(tr)
        if cleaned is None or not _has_useful_zh(cleaned):
            out.append({"status": 404, "original": orig})
            n_404 += 1
            continue
        if GarbageHeuristicFilter.looks_garbage(orig):
            out.append({"status": 404, "original": orig})
            n_404 += 1
            continue
        out.append(
            {"status": 200, "original": orig, "translated": cleaned}
        )
        n_cleaned += 1

    refuse_pipeline_write(translated_path)
    translated_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "total": len(out),
        "to_404": n_404,
        "cleaned": n_cleaned,
        "unchanged": n_unchanged,
    }


def cmd_mark_404(
    *,
    translated: Path | None = None,
    game_id: str | None = None,
) -> int:
    path = translated
    if path is None:
        gid = (game_id or "POKEMON_RUBY_AXVJ00").strip()
        path = default_translated_path(gid)
    stats = mark_404_in_translated(path)
    print(f"[ok] mark-404 → {path}")
    print(
        f"     →404={stats['to_404']}  cleaned={stats['cleaned']}  "
        f"unchanged={stats['unchanged']}  total={stats['total']}"
    )
    return 0


# ---------------------------------------------------------------------------
# guess：由一段地址反推模块配置（start/end/type/read）
# ---------------------------------------------------------------------------

_STRIDE_CANDIDATES = (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 16, 19, 32, 40, 56)
_ENTRY_SIZE_CANDIDATES = (5, 20, 28, 32, 36, 40, 44, 48, 56)


def _slot_text_ok(rom: bytes, off: int, window: int) -> bool:
    """槽 ``[off, off+window)`` 是否读得到有意义的 PCS 文本。

    定长表常有「？？？」占位符（ac ac ac）等单字节符号构成的名，严格的
    ``looks_like_jp_text`` 会误杀；故此处只看「FF 结尾、体非全空、解码非空
    且不混入未识别 <xx> 垃圾」。再要求至少 2 个非空格/非ー 的有效字形，
    以排除邻接结构的 1 字残片（き/ス）与纯填充（ー、空格）。"""
    from meowth.jp_pcs import decode_pcs

    if off < 0 or off + window > len(rom):
        return False
    slot = rom[off : off + window]
    marker = slot.find(0xFF)
    if marker < 0:
        return False
    body = slot[:marker]
    if len(body) < 1 or all(b in (0xFF, 0x00) for b in body):
        return False
    if any(b >= 0xF7 for b in body):
        return False
    text = decode_pcs(slot[: marker + 1]).strip()
    if not text:
        return False
    if "<" in text:
        return False
    # 有效字形（排除空格/全角空格/长音ー/中点・等填充）
    sig = [c for c in text if c not in (" ", "\u3000", "ー", "・", "‥", "…", "-")]
    if len(sig) < 2:
        # 允许「？」占位槽（ac）单独构成一槽；拒绝单字假名残片（き/ス）
        if text not in ("？", "？？", "？？？"):
            return False
    return True


def _is_slot_start(rom: bytes, p: int, step: int) -> bool:
    """``p`` 是定长槽起点：前驱为分界(FF/00)，槽内 FF 结尾且文本非空。"""
    if p <= 0 or p + step > len(rom):
        return False
    if rom[p - 1] not in (0xFF, 0x00):
        return False
    if rom[p] == 0xFF:
        return False
    return _slot_text_ok(rom, p, step)


def _has_slot_text(rom: bytes, p: int, step: int) -> bool:
    """``p`` 处有定长文本槽（不要求前驱分界；用于表头首槽）。"""
    if p < 0 or p + step > len(rom):
        return False
    return rom[p] != 0xFF and _slot_text_ok(rom, p, step)


def _find_slot_start(rom: bytes, addr: int, step: int) -> int | None:
    """找 ``addr`` 所属槽起点：文本槽落在 [addr-step+1, addr]。

    优先前驱为分界（内部槽）；否则退而取首个文本槽（表头）。"""
    for p in range(addr, addr - step, -1):
        if _is_slot_start(rom, p, step):
            return p
    for p in range(addr, addr - step, -1):
        if _has_slot_text(rom, p, step):
            return p
    return None


def _scan_table_bounds(
    rom: bytes, slot: int, step: int
) -> tuple[int, int] | None:
    """以 ``slot`` 为锚，沿 step 回/前推连续有效槽，返回 (start, end 含尾)。

    end 语义与 extract_stride 一致（含尾）。表头首槽不要求前驱分界。"""
    # 前推：后续槽须前驱为分界（定长槽填充特征）
    end = slot
    cur = slot + step
    while cur < len(rom) and _is_slot_start(rom, cur, step):
        end = cur
        cur += step
    # 回推：内部槽须前驱为分界；允许最后一次是表头（前驱无要求）
    start = slot
    cur = slot - step
    while cur >= 0 and _is_slot_start(rom, cur, step):
        start = cur
        cur -= step
    if cur >= 0 and _has_slot_text(rom, cur, step) and not _is_slot_start(rom, cur, step):
        # cur 是表头首槽（前驱非分界但仍有文本）
        start = cur
    count = (end - start) // step + 1
    if count < 2:
        return None
    return start, end + step - 1


def _guess_stride(rom: bytes, addr: int) -> dict | None:
    """反推 type=stride 表（start/end/stride）。"""
    best: dict | None = None
    for step in _STRIDE_CANDIDATES:
        slot = _find_slot_start(rom, addr, step)
        if slot is None:
            continue
        b = _scan_table_bounds(rom, slot, step)
        if b is None:
            continue
        start, end = b
        count = (end - start + 1) // step
        # 定长表应较长（占位/短表如属性名也有 18 槽）；过短即是变长串块的假周期
        if count < 8:
            continue
        filled = sum(
            1 for i in range(count) if _slot_text_ok(rom, start + i * step, step)
        )
        ratio = filled / count
        cand = {
            "start": start,
            "end": end,
            "stride": step,
            "count": count,
            "filled": filled,
            "ratio": ratio,
        }
        # 定长表槽首前驱必为 FF/00，且内部全覆盖：要求比值极高
        if ratio < 0.95:
            continue
        # 更短 stride 往往是真正的固定槽宽（stride 的倍数也会误配成假周期）
        if best is None or (step, -count) < (best["stride"], -best["count"]):
            best = cand
    return best


def _struct_row_desc_ptr(rom: bytes, o: int, es: int, dpo: int) -> int | None:
    """行 ``[o, o+es)`` 的 ``dpo`` 处 desc_ptr；无效/越界/指向空返回 None。"""
    if dpo is None or o + dpo + 4 > len(rom):
        return None
    v = struct.unpack_from("<I", rom, o + dpo)[0]
    if not (BASE <= v < BASE + len(rom)):
        return None
    so = v - BASE
    if not (0 <= so < len(rom)):
        return None
    if rom[so : so + 1] in (b"\xFF", b"\x00", b""):
        return None
    return so


def _guess_struct(rom: bytes, addr: int) -> dict | None:
    """反推 type=struct 表（start/end/entry_size/desc_ptr_offset）。

    结构行：行首 4 对齐且前驱为分界；名称 FF 结尾；其后某 4-align 位置是
    稳定的 desc_ptr（逐行指向前方说明串区）。表边界由 desc_ptr 有效性驱动，
    遇到 desc_ptr 重复（列表尾哨兵）或失效即停。"""
    best: dict | None = None
    for es in _ENTRY_SIZE_CANDIDATES:
        for probe in (addr, addr - (addr % 4)):
            slot = _find_slot_start(rom, probe, es)
            if slot is None:
                continue
            # 先确定 desc_ptr 相对行首的稳定偏移
            dpo_cand: dict[int, int] = {}
            # 采样：从 slot 向前后各看几行，统计各 4-align 位置作为指针的频率
            for off in range(slot - es * 2, slot + es * 3, es):
                if off < 0 or off + es > len(rom):
                    continue
                row = rom[off : off + es]
                name_end = row.find(0xFF)
                if name_end < 0:
                    continue
                for p in range((name_end + 1 + 3) & ~3, es - 3, 4):
                    if _struct_row_desc_ptr(rom, off, es, p) is not None:
                        dpo_cand[p] = dpo_cand.get(p, 0) + 1
            if not dpo_cand:
                continue
            dpo = max(dpo_cand.items(), key=lambda kv: kv[1])[0]

            def _row_ok(o: int) -> bool:
                return _struct_row_desc_ptr(rom, o, es, dpo) is not None

            # 已在 slot 处；先回推表头（desc_ptr 有效 + 文本非空）
            start = slot
            cur = slot - es
            while cur >= 0 and _row_ok(cur) and _slot_text_ok(rom, cur, es):
                start = cur
                cur -= es
            # 前推表尾：desc_ptr 有效即继续（占位「？？？」共指 0x39A63F 属正常）
            end = slot
            cur = slot + es
            while cur < len(rom):
                dp = _struct_row_desc_ptr(rom, cur, es, dpo)
                if dp is None or not _slot_text_ok(rom, cur, es):
                    break
                end = cur
                cur += es
            count = (end - start) // es + 1
            if count < 8:
                continue
            filled = sum(
                1
                for i in range(count)
                if _row_ok(start + i * es) and _slot_text_ok(rom, start + i * es, es)
            )
            ratio = filled / count
            if ratio < 0.9:
                continue
            cand = {
                "start": start,
                "end": end + es - 1,
                "entry_size": es,
                "count": count,
                "filled": filled,
                "ratio": ratio,
                "desc_ptr_offset": dpo,
            }
            if best is None or (cand["ratio"], cand["filled"]) > (
                best["ratio"],
                best["filled"],
            ):
                best = cand
    if best is None:
        return None
    if best.get("desc_ptr_offset") is None:
        return None
    return best


def _guess_stride_ptr(rom: bytes, addr: int) -> dict | None:
    """反推 type=stride_ptr 指针表（默认 stride 4）。"""
    from meowth.jp_pcs import decode_pcs

    step = 4

    def _is_ptr_slot(o: int) -> bool:
        if o < 0 or o + 4 > len(rom):
            return False
        v = struct.unpack_from("<I", rom, o)[0]
        if not (BASE <= v < BASE + len(rom)):
            return False
        so = v - BASE
        raw = read_pcs(rom, so, 64)
        if not raw:
            return False
        return bool(decode_pcs(raw).strip())

    base = addr - (addr % step)
    if not _is_ptr_slot(base):
        nxt = None
        for d in (-step, step, -2 * step, 2 * step):
            if _is_ptr_slot(base + d):
                nxt = base + d
                break
        if nxt is None:
            return None
        base = nxt

    start = cur = base
    while cur - step >= 0 and _is_ptr_slot(cur - step):
        cur -= step
        start = cur
    end = cur = base
    while cur + step <= len(rom) and _is_ptr_slot(cur + step):
        cur += step
        end = cur
    count = (end - start) // step + 1
    if count < 2:
        return None
    return {"start": start, "end": end, "stride": step, "count": count}


def _varlen_block_hint(rom: bytes, addr: int) -> dict | None:
    """兜底：addr 落在 FF 结尾变长串块，给近似边界（无定长语义）。"""
    from meowth.jp_pcs import decode_pcs

    n = len(rom)

    def _dec(o: int, e: int) -> str:
        try:
            return decode_pcs(rom[o : e + 1]).strip()
        except Exception:
            return ""

    start = addr
    cur = addr
    while cur > 0:
        prev_ff = rom.rfind(0xFF, 0, cur)
        so = prev_ff + 1 if prev_ff >= 0 else 0
        nxt = rom.find(0xFF, so, min(n, so + 64))
        if nxt < 0 or so >= nxt:
            break
        if not _dec(so, nxt):
            break
        start = so
        cur = so - 1 if so > 0 else 0

    end = addr
    cur = addr
    guard = 0
    while cur < n and guard < 100000:
        nxt = rom.find(0xFF, cur, min(n, cur + 64))
        if nxt < 0 or cur >= nxt:
            break
        if not _dec(cur, nxt):
            break
        end = nxt
        cur = nxt + 1
        guard += 1
    if end <= start:
        return None
    return {"start": start, "end": end, "kind": "varlen"}


def _fmt_guess(d: dict, typ: str) -> None:
    """打印一条推测模块 yaml 片段（不写盘）。"""
    lines = [
        f"- id: 模块名",
        f"  start: '0x{d['start']:x}'",
        f"  end: '0x{d['end']:x}'",
        f"  type: {typ}",
    ]
    if typ == "stride":
        lines += ["  read:", f"    stride: {d['stride']}"]
    elif typ == "struct":
        lines += ["  read:", f"    entry_size: {d['entry_size']}"]
        if d.get("desc_ptr_offset") is not None:
            lines.append(f"    desc_ptr_offset: {d['desc_ptr_offset']}")
    elif typ == "stride_ptr":
        lines += ["  read:", f"    stride: {d['stride']}"]
    for ln in lines:
        _safe_print(ln)


def cmd_guess(rom_path: Path, addr_s: str, *, config_path: Path | None = None) -> int:
    """由一段地址反推模块配置（start/end/type/read），只读不写盘。"""
    rom = rom_path.read_bytes()
    if len(rom) < 0x200:
        raise SystemExit("ROM too small")
    addr = parse_addr(addr_s)
    fo = _to_file_offset(addr, len(rom), default=0)
    print(f"[i] input={addr_s!r} -> file_offset=0x{fo:X}")

    if TITLE_LZ_BAND[0] <= fo < TITLE_LZ_BAND[1]:
        _safe_print(
            f"[!] 0x{fo:X} 落在标题 LZ 带 "
            f"0x{TITLE_LZ_BAND[0]:X}..0x{TITLE_LZ_BAND[1]:X}，不宜作文本模块"
        )

    results: list[tuple[dict, str]] = []
    s = _guess_stride(rom, fo)
    if s:
        results.append((s, "stride"))
    st = _guess_struct(rom, fo)
    if st:
        results.append((st, "struct"))
    sp = _guess_stride_ptr(rom, fo)
    if sp:
        results.append((sp, "stride_ptr"))

    if not results:
        hint = _varlen_block_hint(rom, fo)
        if hint:
            _safe_print(
                f"[i] 0x{fo:X} 落在变长 FF 串块（非定长/结构表）；"
                f"近似边界 0x{hint['start']:X}..0x{hint['end']:X}（含）"
            )
            _safe_print("    建议按 type: scan + ranges: 处理，而非 stride/struct")
        else:
            _safe_print(f"[i] 0x{fo:X} 无法推断为定长/结构表，也无稳定变长串块")
        return 0

    # 优先级：struct（最具体，有 desc_ptr）> stride_ptr > stride
    _type_rank = {"struct": 0, "stride_ptr": 1, "stride": 2}
    results.sort(key=lambda r: (_type_rank.get(r[1], 9), -r[0].get("ratio", 1.0)))
    d, typ = results[0]
    print()
    _safe_print(f"# 推测 type={typ}")
    _fmt_guess(d, typ)
    print()
    _safe_print(
        f"[i] 槽数={d.get('count')} 命中={d.get('filled', d.get('count'))} "
        f"覆盖率={d.get('ratio', 1.0):.0%}"
    )
    if d.get("desc_ptr_offset") is not None:
        _safe_print(f"[i] 检测到 desc_ptr 在行内 +{d['desc_ptr_offset']}")
    _safe_print("[i] 只读：未修改 ROM / yaml / texts.json")
    return 0


def _add_remove_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--addrs",
        default=None,
        help='逗号分隔地址（VMA 或文件偏移）；PowerShell 请加引号: --addrs "0x08376A3C,0x086F0B14"',
    )
    p.add_argument(
        "--from-translated",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help=(
            "从 texts_translated.json 的 status=404 经 texts.json 反查地址；"
            "省略 PATH 则用 src/util/work/<game_id>/texts_translated.json"
        ),
    )
    p.add_argument("--config", type=Path, default=None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="texts_patcher: export / scan / mark-404 / remove-preview / remove"
    )
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
        help="输出路径（默认 src/util/work/<game_id>/texts.json；禁止写流水线 configs/）",
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

    p_rp = sub.add_parser(
        "remove-preview",
        help="预览：整句洞 merge 进 texts.omit_ranges（不写盘）",
    )
    p_rp.add_argument("rom", type=Path)
    _add_remove_args(p_rp)

    p_rm = sub.add_parser(
        "remove",
        help="执行：merge texts.omit_ranges 并同步 texts.json（不切碎模块 ranges）",
    )
    p_rm.add_argument("rom", type=Path)
    _add_remove_args(p_rm)

    p_m4 = sub.add_parser(
        "mark-404",
        help="乱码标记/假200垃圾原文→404，清洗污染译文；写回 texts_translated.json",
    )
    p_m4.add_argument(
        "--translated",
        type=Path,
        default=None,
        help="texts_translated.json（默认 src/util/work/<game_id>/texts_translated.json）",
    )
    p_m4.add_argument(
        "--game-id",
        default="POKEMON_RUBY_AXVJ00",
        help="未指定 --translated 时用此 game_id 解析默认路径",
    )

    p_mig = sub.add_parser(
        "migrate-omit",
        help="碎 ranges 并回粗带，缝写入 texts.omit_ranges",
    )
    p_mig.add_argument(
        "rom",
        type=Path,
        nargs="?",
        default=None,
        help="可选 ROM（用于 resolve 配置）；省略则默认 AXVJ yaml",
    )
    p_mig.add_argument("--config", type=Path, default=None)
    p_mig.add_argument(
        "--max-gap",
        type=int,
        default=32,
        help="邻近 ranges 合并的最大缝隙字节数（默认 32；大缝保留为多段）",
    )

    p_gu = sub.add_parser(
        "guess",
        help="由一段地址反推模块配置（start/end/type/read），只读不写盘",
    )
    p_gu.add_argument("rom", type=Path)
    p_gu.add_argument("addr", help="任一地址（0x08xxxxxx 或文件偏移 0x…；大小写不敏感）")
    p_gu.add_argument("--config", type=Path, default=None)

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
    if args.cmd in ("remove-preview", "remove"):
        if args.addrs is None and args.from_translated is None:
            ap.error("需要 --addrs 和/或 --from-translated")
        fn = cmd_remove_preview if args.cmd == "remove-preview" else cmd_remove
        return fn(
            args.rom,
            args.addrs,
            from_translated=args.from_translated,
            config_path=args.config,
        )
    if args.cmd == "mark-404":
        return cmd_mark_404(
            translated=args.translated,
            game_id=args.game_id,
        )
    if args.cmd == "migrate-omit":
        return cmd_migrate_omit(
            args.rom, config_path=args.config, max_gap=args.max_gap
        )
    if args.cmd == "guess":
        return cmd_guess(args.rom, args.addr, config_path=args.config)
    ap.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
