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
    """结构体行表：按行 entry_size 步进，名称读到 eos（默认 FF）；byte_length=原文实际长。"""
    mid = mod["id"]
    start = parse_addr(mod.get("start"))
    end = parse_addr(mod.get("end"))
    read = mod.get("read") or {}
    entry_size = _struct_entry_size(read)
    if not entry_size or end < start:
        return []
    eos = _parse_eos_byte(read.get("eos", read.get("suffix")))
    name_window = _struct_name_window(read, entry_size)
    count = (end - start + 1) // entry_size
    out: list[dict] = []
    table_ptr = BASE + start
    for i in range(count):
        off = start + i * entry_size
        text, raw = _slot_text(rom, off, name_window, eos=eos)
        if not text or set(text) <= {"？", "ー", "-", " "}:
            continue
        e = {
            "address": f"0x{BASE + off:08X}",
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


def resolve_filters(cfg: dict, mod: dict) -> list[dict[str, Any]]:
    """texts.filters.<type> + module.filters；同 type 后写覆盖整条（含 value / filter）。

    若模块声明了 ``original_text_filter`` 且 ``filter: false``（正文包含白名单），
    **不再合并** 全局 ``texts.filters.<type>``——只使用 ``module.filters``。
    否则全局 ``min_byte_length: 8`` / ``dialogue_shape`` 等会把短 UI（如「バッグ」）全部滤掉，
    与 ``texts_patcher scan``（不跑模块 filter）行为不一致。
    """
    mtype = str(mod.get("type") or "scan")
    texts = cfg.get("texts") or {}
    by_type = texts.get("filters") or {}
    extra = list(mod.get("filters") or [])
    if _has_include_original_text_filter(extra):
        base: list[Any] = []
    else:
        base = list(by_type.get(mtype) or [])
    # 合并：先 base 再 extra，同 type 后写覆盖
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
        if t not in merged:
            order.append(t)
        merged[t] = dict(spec)
    return [merged[t] for t in order]


def _norm_original_key(s: str) -> str:
    """正文匹配用：去掉空白后比较。"""
    return re.sub(r"\s+", "", s or "")


def _original_text_hit(ctx: FilterContext, val: Any) -> bool:
    """original_text_filter：原文精确或去空白后命中 value 列表。"""
    if not isinstance(val, (list, tuple)):
        return False
    keys = [str(x) for x in val if x is not None and str(x)]
    if not keys:
        return False
    o = ctx.original or ""
    plain = ctx.original_plain or ""
    o_n = _norm_original_key(o)
    plain_n = _norm_original_key(plain)
    for k in keys:
        if o == k or plain == k:
            return True
        kn = _norm_original_key(k)
        if kn and (o_n == kn or plain_n == kn):
            return True
    return False


def _filter_hit(ctx: FilterContext, spec: dict[str, Any]) -> bool | None:
    """计算是否命中过滤条件。

    返回 ``None`` 表示本闸禁用（恒保留）。
    ``hit=True`` 表示命中「过滤模式」应丢弃的一侧；
    ``filter: true``（默认）保留 ⟺ not hit；``filter: false``（包含）保留 ⟺ hit。
    """
    t = str(spec.get("type") or "")
    val = spec.get("value")

    if t == "character_filter":
        pat = str(val or "")
        if not pat:
            return None
        return re.search(pat, ctx.original_plain or "") is not None

    if t == "dialogue_shape_filter":
        if not bool(val):
            return None
        return not _dialogue_shape_ok(ctx)

    if t == "min_byte_length_filter":
        try:
            n = int(val)
        except (TypeError, ValueError):
            return None
        return ctx.byte_length < n

    if t == "max_byte_length_filter":
        try:
            n = int(val)
        except (TypeError, ValueError):
            return None
        return ctx.byte_length > n

    if t == "require_pointer_filter":
        if not bool(val):
            return None
        return not bool(ctx.is_pointer_based)

    if t == "garbage_heuristic_filter":
        if not bool(val):
            return None
        return _looks_garbage_original(ctx.original)

    if t == "address_filter":
        if isinstance(val, dict):
            lo = normalize_file_off(val.get("start") or 0)
            hi = normalize_file_off(val.get("end") or 0)
            if hi < lo:
                lo, hi = hi, lo
            return lo <= ctx.address <= hi
        pat = str(val or "")
        if not pat:
            return None
        hex_s = f"0x{ctx.address:X}"
        vma_s = f"0x{ctx.address_vma:08X}"
        return (
            re.search(pat, hex_s) is not None
            or re.search(pat, vma_s) is not None
        )

    if t == "original_text_filter":
        return _original_text_hit(ctx, val)

    raise SystemExit(f"未知 filter type: {t!r}")


def _dialogue_shape_ok(ctx: FilterContext) -> bool:
    """对白形态：指针短标可留；否则须像真脚本句（\\n 单独不够）。"""
    o = ctx.original or ""
    plain = ctx.original_plain or ""
    if ctx.is_pointer_based:
        return True
    jp = len(re.findall(r"[\u3040-\u30ff]", o))
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
    # ！？ / \\l\\p 须带格助词，避免乱码里碰巧出现？或 \\l
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


def _looks_garbage_original(original: str) -> bool:
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
    # 去掉按钮标签后再计全角拉丁，避免误杀「Ａボタンで…」
    plain_no_btn = re.sub(r"[Ａ-Ｚａ-ｚ]ボタン", "", plain)

    latin = len(re.findall(r"[A-Za-zÄäÖöÜüß]", plain))
    jp = len(re.findall(r"[\u3040-\u30ff]", o))
    fw_letter = len(re.findall(r"[Ａ-Ｚａ-ｚ]", plain_no_btn))
    if latin >= 3 and jp >= 5:
        return True
    if fw_letter >= 3 and jp >= 3:
        return True
    if ("♂" in o or "♀" in o) and (
        fw_letter >= 1 or "Ｂ" in plain_no_btn or "Ａ" in plain_no_btn
    ):
        return True
    if len(plain.strip()) <= 8 and fw_letter >= 1 and jp >= 1:
        return True
    for block in set(re.findall(r"[ァ-ン]{2}", o)):
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
            if o.count(block) >= 2:
                return True
    return False


def apply_one_filter(ctx: FilterContext, spec: dict[str, Any]) -> bool:
    """True=保留，False=拒绝。

    ``filter`` 极性（默认 ``true``=过滤）：
    - ``true``：命中则丢（保留 ⟺ not hit）
    - ``false``：命中则留（包含模式；保留 ⟺ hit）
    """
    hit = _filter_hit(ctx, spec)
    if hit is None:
        return True
    # 未写 filter 字段时默认 true（过滤），与旧行为一致
    exclude = True if "filter" not in spec else bool(spec.get("filter"))
    if exclude:
        return not hit
    return bool(hit)


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
) -> FilterContext:
    return FilterContext(
        address=fo,
        address_vma=BASE + fo,
        raw=raw,
        byte_length=len(raw),
        original=original,
        original_plain=plain_original(original),
        is_pointer_based=bool(ptrs),
        pointer_offs=list(ptrs),
        module_id=module_id,
        module_type=module_type,
    )


def _original_include_needles(filters: list[dict[str, Any]]) -> list[str] | None:
    """若存在 ``original_text_filter`` 且 ``filter: false``，返回正文白名单；否则 None。"""
    for spec in filters or []:
        if str(spec.get("type") or "") != "original_text_filter":
            continue
        # 默认 filter=true；仅包含模式走关键字快扫
        if bool(spec.get("filter", True)):
            return None
        val = spec.get("value")
        if not isinstance(val, (list, tuple)):
            return None
        out = [str(x) for x in val if x is not None and str(x)]
        return out
    return None


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


def extract_scan(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
    omit_ranges: list[tuple[int, int]] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    # 只用 jp_pcs + 本地 read_pcs / SCRIPT_BANK_MIN；禁止 import meowth.extract
    #（extract 会 load_game_config → 读流水线 texts.json，与 util 导出死锁）。
    from meowth.jp_pcs import decode_pcs, looks_like_jp_text
    from meowth.policy import looks_like_translatable

    mid = mod["id"]
    mtype = str(mod.get("type") or "scan")
    bands = effective_module_bands(mod, omit_ranges or [])
    if not bands:
        return []
    filt = list(filters or [])
    # 兼容旧字段：并入 filter 语义（不覆盖已有同 type）
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

    ptrs_map = ptr_index or {}

    needles = _original_include_needles(filt)
    if needles is not None:
        # 包含模式：按正文关键字在 band 内 find，避免整 ROM 逐字节扫
        out: list[dict] = []
        seen: set[int] = set()
        encoded: list[bytes] = []
        for text in needles:
            raw = _encode_jp_needle(text)
            if raw and len(raw) >= 2:
                encoded.append(raw)
            compact = _norm_original_key(text)
            if compact and compact != text:
                raw2 = _encode_jp_needle(compact)
                if raw2 and len(raw2) >= 2 and raw2 not in encoded:
                    encoded.append(raw2)
        for needle in encoded:
            start = 0
            body = needle
            while True:
                a = rom.find(body, start)
                if a < 0:
                    break
                start = a + 1
                if not _in_bands(a):
                    continue
                if a in seen:
                    continue
                if a < SCRIPT_BANK_MIN or TITLE_LZ_BAND[0] <= a < TITLE_LZ_BAND[1]:
                    continue
                raw = read_pcs(rom, a, 512) or body
                if not looks_like_jp_text(raw):
                    if raw != body and not (
                        body.endswith(b"\xff") and rom[a : a + len(body)] == body
                    ):
                        continue
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
                if filt and not apply_filters(ctx, filt):
                    continue
                seen.add(a)
                e = {
                    "address": f"0x{BASE + a:08X}",
                    "original": text,
                    "original_hex": raw.hex(" "),
                    "byte_length": len(raw),
                    "is_pointer_based": bool(ptrs),
                    "pointer_sources": [f"0x{BASE + q:08X}" for q in ptrs],
                    "pointer_addresses": [f"0x{BASE + q:08X}" for q in ptrs],
                }
                out.append(_stamp(e, mid=mid, game_code=game_code))
        return out

    out: list[dict] = []
    seen: set[int] = set()
    for lo, hi in band_pairs:
        a = lo
        while a <= hi:
            b = rom[a]
            # 0xFC = 扩展控制码前缀；勿与 F7–FB / FE / FF 一并跳过
            if b == 0xFF or b == 0x00 or (b >= 0xF7 and b != 0xFC):
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
                    ptrs = list(ptrs_map.get(a, []))
                    ctx = make_filter_context(
                        fo=a,
                        raw=raw,
                        original=text,
                        ptrs=ptrs,
                        module_id=str(mid),
                        module_type=mtype,
                    )
                    if filt and not apply_filters(ctx, filt):
                        a = end + 1
                        continue
                    seen.add(a)
                    e = {
                        "address": f"0x{BASE + a:08X}",
                        "original": text,
                        "original_hex": raw.hex(" "),
                        "byte_length": len(raw),
                        "is_pointer_based": bool(ptrs),
                        "pointer_sources": [f"0x{BASE + q:08X}" for q in ptrs],
                        "pointer_addresses": [f"0x{BASE + q:08X}" for q in ptrs],
                    }
                    out.append(_stamp(e, mid=mid, game_code=game_code))
            a = end + 1
    return out


def extract_module(
    rom: bytes,
    mod: dict,
    game_code: str,
    *,
    ptr_index: dict[int, list[int]] | None = None,
    omit_ranges: list[tuple[int, int]] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> list[dict]:
    rtype = str(mod.get("type") or "scan")
    if rtype == "stride":
        return extract_stride(rom, mod, game_code)
    if rtype == "struct":
        return extract_struct(rom, mod, game_code)
    if rtype in ("stride_ptr", "ptr_stride"):
        return extract_stride_ptr(rom, mod, game_code)
    if rtype in ("scan", "addr_bands"):
        return extract_scan(
            rom,
            mod,
            game_code,
            ptr_index=ptr_index,
            omit_ranges=omit_ranges,
            filters=filters,
        )
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
    omit_ranges = get_texts_omit_ranges(cfg)
    if omit_ranges:
        print(
            f"[i] texts.omit_ranges ×{len(omit_ranges)} "
            f"(bytes={sum(b - a + 1 for a, b in omit_ranges)})"
        )
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
        chunk = extract_module(
            rom,
            mod,
            game_code,
            ptr_index=ptr_index,
            omit_ranges=omit_ranges,
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
            entries.append(_order_entry(e))
            n += 1
        print(f"  [{mid}] type={rtype} -> {n}")

    if skipped:
        print(f"[i] skipped module types (not implemented): {skipped}")

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
            if _looks_garbage_original(orig):
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
        if _looks_garbage_original(orig):
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
    ap.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
