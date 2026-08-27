#!/usr/bin/env python3
"""从 AXVJ 模板 + module_map JSON + ROM 扫描生成 util 游戏 yaml。

用法（仓库根目录）:
  python src/util/bootstrap_game_yaml.py
  python src/util/bootstrap_game_yaml.py POKEMON_SAPP_AXPJ00 POKEMON_FIRE_BPRJ00
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

UTIL_DIR = Path(__file__).resolve().parent
REPO_ROOT = UTIL_DIR.parent.parent
CONFIGS = UTIL_DIR / "configs"
TEMPLATE_ID = "POKEMON_RUBY_AXVJ00"

# yaml module id -> json module_map id
YAML_TO_JSON_ID = {
    "宝可梦名": "物种名",
}

RS_ONLY_MODULE_IDS = frozenset(
    {
        "属性名-华丽大赛",
        "招式名-华丽大赛",
        "招式说明-华丽大赛",
        "秘密基地装饰名",
        "树果名",
        "图鉴分类名",
        "补漏剧情",
    }
)

CORPUS_BY_FAMILY = {
    "RS": "reference_corpus/RubySapphire/ja-Hrkt_msg.txt",
    "FRLG": "reference_corpus/FireRedLeafGreen/ja-Hrkt_msg.txt",
    "Emerald": "reference_corpus/Emerald/ja-Hrkt_msg.txt",
}

GAMES: list[tuple[str, str, str, str]] = [
    ("POKEMON_SAPP_AXPJ00", "AXPJ", "RS", "roms/origin/POKEMON_SAPP_AXPJ00.gba"),
    ("POKEMON_FIRE_BPRJ00", "BPRJ", "FRLG", "roms/origin/POKEMON_FIRE_BPRJ00.gba"),
    ("POKEMON_LEAF_BPGJ00", "BPGJ", "FRLG", "roms/origin/POKEMON_LEAF_BPGJ00.gba"),
    (
        "POKEMON_EMERALD_BPEJ00",
        "BPEJ",
        "Emerald",
        "roms/origin/Pokemon Emerald Version(JP).gba",
    ),
]

TYPE_ICONS_BANK_LIST = [
    0,
    0,
    1,
    1,
    0,
    0,
    2,
    1,
    0,
    2,
    0,
    1,
    2,
    0,
    1,
    1,
    2,
    0,
    0,
    1,
    1,
    2,
    0,
]


def _load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _json_mods(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for mod in doc.get("modules") or []:
        mid = mod.get("id") or ""
        if mid:
            out[mid] = mod
    return out


def _norm_hex(val: str | int | None) -> str | None:
    if val is None:
        return None
    if isinstance(val, int):
        return f"0x{val:x}"
    s = str(val).strip()
    if not s:
        return None
    if not s.startswith("0x"):
        s = f"0x{s}"
    return s.lower()


def _merge_json_band(yaml_mod: dict, json_mod: dict) -> None:
    for key in ("start", "end", "label", "group", "default", "description"):
        if key in json_mod and json_mod[key] is not None:
            yaml_mod[key] = (
                _norm_hex(json_mod[key])
                if key in ("start", "end")
                else json_mod[key]
            )
    if json_mod.get("ranges"):
        yaml_mod["ranges"] = [
            {k: _norm_hex(r[k]) for k in ("start", "end") if k in r}
            for r in json_mod["ranges"]
        ]
    elif "ranges" in yaml_mod and _is_zero_band(json_mod):
        yaml_mod.pop("ranges", None)


def _is_zero_band(mod: dict) -> bool:
    start = _norm_hex(mod.get("start"))
    end = _norm_hex(mod.get("end"))
    return start in ("0x0", None) and end in ("0x0", None)


def _patch_modules(cfg: dict, json_mods: dict[str, dict], family: str) -> None:
    modules = cfg.get("texts", {}).get("modules") or []
    for mod in modules:
        mid = mod.get("id") or ""
        json_id = YAML_TO_JSON_ID.get(mid, mid)
        jmod = json_mods.get(json_id)
        if jmod:
            _merge_json_band(mod, jmod)
        elif family != "RS" and mid in RS_ONLY_MODULE_IDS:
            mod["start"] = "0x0"
            mod["end"] = "0x0"
            mod.pop("ranges", None)


def _patch_corpus(cfg: dict, family: str) -> None:
    corpus = CORPUS_BY_FAMILY.get(family)
    if not corpus:
        return
    for mod in cfg.get("texts", {}).get("modules") or []:
        reader = mod.get("reader")
        if not isinstance(reader, dict):
            continue
        val = reader.get("value")
        if isinstance(val, dict) and "file" in val:
            val["file"] = corpus


def _patch_gdb_charmap(cfg: dict, game_id: str) -> None:
    charmap = f"configs/{game_id}/charmap.txt"
    for pt in cfg.get("gdb") or []:
        pt_cfg = pt.get("cfg")
        if isinstance(pt_cfg, dict) and "charmap" in pt_cfg:
            pt_cfg["charmap"] = charmap


def _scan_type_icons_preset(rom_path: Path) -> dict | None:
    sys.path.insert(0, str(UTIL_DIR))
    from _scan_tiles import scan, pal_near  # noqa: WPS433
    from tiles_patcher import (  # noqa: WPS433
        detect_palette_bank_table,
        lz77_decompress,
        offset_to_gba_address,
        _detect_bpp,
        _infer_sprite_size,
    )

    if not rom_path.is_file():
        return None
    rom = rom_path.read_bytes()
    for off, _csize, dsize, comp in scan(rom):
        if dsize != 5888:
            continue
        dec = lz77_decompress(rom[off:], swap=(comp == "lz77_swap"))
        bpp = _detect_bpp(dec)
        w, h, cnt = _infer_sprite_size(dsize, bpp)
        if w != 32 or h != 16 or cnt != 23 or bpp != 4:
            continue
        _bank_off, _base, bank_list = detect_palette_bank_table(rom, cnt, 3)
        if not bank_list:
            bank_list = TYPE_ICONS_BANK_LIST
        pb = pal_near(rom, off)
        pal_gba = offset_to_gba_address(pb[1]) if pb else None
        preset: dict = {
            "id": "type_icons",
            "label": "属性图标",
            "default": True,
            "address": f"0x{offset_to_gba_address(off):08X}",
            "format": "4bpp",
            "compression": comp,
            "sprite_size": "32x16",
            "count": 23,
            "bank_list": bank_list,
        }
        if pal_gba:
            preset["palette"] = f"0x{pal_gba:08X}"
        return preset
    return None


def _build_tiles(cfg: dict, family: str, rom_path: Path, template: dict) -> None:
    tiles = copy.deepcopy(template.get("tiles") or {})
    if family == "RS":
        cfg["tiles"] = tiles
        return

    presets: list[dict] = []
    # 非 RS：仅保留扫描到的 type_icons + 待人工 compose 占位说明
    scanned = _scan_type_icons_preset(rom_path)
    if scanned:
        presets.append(scanned)
    else:
        presets.append(
            {
                "id": "type_icons",
                "label": "属性图标（待扫描定址）",
                "default": False,
                "address": "0x0",
                "format": "4bpp",
                "compression": "lz77_swap",
                "sprite_size": "32x16",
                "count": 23,
                "note": "ROM 静态扫描未命中 32x16×23 4bpp；需 gdb_patcher 或人工补 preset",
            }
        )
    tiles["presets"] = presets
    cfg["tiles"] = tiles


def _build_gdb(cfg: dict, family: str, template: dict, game_id: str) -> None:
    if family == "RS":
        cfg["gdb"] = copy.deepcopy(template.get("gdb") or [])
        _patch_gdb_charmap(cfg, game_id)
        return

    # FRLG / Emerald 文本引擎地址与日版 RS 不同；先留最小占位，避免误挂 RS 断点。
    cfg["gdb"] = [
        {
            "name": "_bootstrap_note",
            "address": "0x0",
            "description": (
                f"{family} 日版 gdb 断点需单独定址（勿沿用 AXVJ 0x080032F8 等 RS 地址）。"
                "参考 src/util/configs/POKEMON_RUBY_AXVE.yaml 美版对照 + 运行时 gdb_patcher 采集。"
            ),
            "default": False,
        }
    ]


def _patch_filters(cfg: dict, family: str) -> None:
    if family == "RS":
        return
    filters = cfg.get("texts", {}).get("filters") or []
    for flt in filters:
        if flt.get("id") == "global_title_lz_filter":
            flt["value"] = {"start": "0x0", "end": "0x0"}


def bootstrap_game(game_id: str, game_code: str, family: str, rom_rel: str) -> Path:
    sys.path.insert(0, str(UTIL_DIR))
    from texts_patcher import save_yaml_config  # noqa: WPS433

    template = _load_yaml(CONFIGS / f"{TEMPLATE_ID}.yaml")
    json_path = CONFIGS / f"{game_id}.json"
    if not json_path.is_file():
        raise FileNotFoundError(json_path)

    cfg = copy.deepcopy(template)
    cfg["game_id"] = game_id
    cfg["game_code"] = game_code

    json_mods = _json_mods(json_path)
    _patch_modules(cfg, json_mods, family)
    _patch_corpus(cfg, family)
    _patch_filters(cfg, family)
    _build_tiles(cfg, family, REPO_ROOT / rom_rel, template)
    _build_gdb(cfg, family, template, game_id)

    out = CONFIGS / f"{game_id}.yaml"
    header = (
        f"# Generated by bootstrap_game_yaml.py from {TEMPLATE_ID}.yaml + "
        f"{game_id}.json + ROM scan ({family}).\n"
        f"# Re-run: python src/util/bootstrap_game_yaml.py {game_id}\n"
    )
    save_yaml_config(out, cfg)
    text = out.read_text(encoding="utf-8")
    if not text.startswith("# Generated by bootstrap_game_yaml"):
        out.write_text(header + text, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    targets = {g[0] for g in GAMES}
    if argv:
        unknown = [a for a in argv if a not in targets]
        if unknown:
            print("未知 game_id:", ", ".join(unknown))
            print("可选:", ", ".join(sorted(targets)))
            return 2
        run = [g for g in GAMES if g[0] in argv]
    else:
        run = [g for g in GAMES if g[0] != TEMPLATE_ID]

    for game_id, code, family, rom_rel in run:
        out = bootstrap_game(game_id, code, family, rom_rel)
        print(f"Wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
