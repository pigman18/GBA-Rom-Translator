#!/usr/bin/env python3
"""逐帧描述战斗主菜单 / 四招式 / PP+类型面板（origin vs translated）。

用法：
  python bot/analyze_battle_menu_frames.py work/POKEMON_RUBY_AXVJ00/bot/battle_menu_audit/<run>

输出：
  <run>/frame_descriptions.md   — 人工可读逐帧描述 + SKILL 三项判定草稿
  <run>/frame_descriptions.json — 面板 ink/白块指标
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from PIL import Image

# 240×160 逻辑屏；mGBA 常 3× → 720×480。ROI 用逻辑坐标，读图时按 scale 映射。
ROIS = {
    "menu_tl": (120, 96, 176, 112),      # 战斗
    "menu_tr": (176, 96, 232, 112),      # 背包
    "menu_bl": (120, 112, 176, 128),     # 宝可梦
    "menu_br": (176, 112, 232, 128),     # 逃跑
    "move_tl": (8, 96, 88, 112),
    "move_tr": (88, 96, 168, 112),
    "move_bl": (8, 112, 88, 128),
    "move_br": (88, 112, 168, 128),
    "pp_row": (168, 96, 232, 112),
    "type_row": (168, 112, 232, 128),
    "dialog": (8, 128, 232, 152),
    "enemy_name": (8, 8, 96, 24),
    "player_name": (128, 56, 232, 72),
}

FOCUS_TAGS = (
    "bt_menu", "bt_menu_", "bt_move_", "bt_moves", "bt_in_battle", "bt_intro"
)

SPECIES_PLAYER = 0x02024A80
SPECIES_ENEMY = 0x02024AD8  # +0x58


def _scale(img: Image.Image) -> int:
    w, h = img.size
    if w % 240 == 0 and h % 160 == 0:
        return w // 240
    return 1


def _crop(img: Image.Image, box, scale: int) -> Image.Image:
    l, t, r, b = box
    return img.crop((l * scale, t * scale, r * scale, b * scale))


def _stats(roi: Image.Image) -> dict:
    px = list(roi.convert("RGB").getdata())
    n = len(px) or 1
    # 近白块（填充/清窗残留）
    white = sum(1 for r, g, b in px if r > 230 and g > 230 and b > 230)
    # 近灰底（网格 opaque bg）
    gray = sum(
        1 for r, g, b in px
        if 140 <= r <= 200 and 140 <= g <= 200 and 140 <= b <= 200
        and abs(r - g) < 20 and abs(g - b) < 20
    )
    # 深墨（字形）
    ink = sum(1 for r, g, b in px if r + g + b < 180)
    # 红边框噪声不计；返回比例
    return {
        "white_ratio": round(white / n, 4),
        "gray_ratio": round(gray / n, 4),
        "ink_ratio": round(ink / n, 4),
        "mean": tuple(round(sum(c[i] for c in px) / n, 1) for i in range(3)),
    }


def _describe_roi(name: str, st: dict) -> str:
    bits = []
    if st["ink_ratio"] < 0.02 and st["white_ratio"] > 0.55:
        bits.append("空/白块")
    elif st["ink_ratio"] < 0.02 and st["gray_ratio"] > 0.25:
        bits.append("灰底无字")
    elif st["gray_ratio"] > 0.15 and st["ink_ratio"] > 0.02:
        bits.append("有字+灰底")
    elif st["ink_ratio"] > 0.04:
        bits.append("有墨")
    else:
        bits.append("淡/不清")
    if st["white_ratio"] > 0.35:
        bits.append(f"白{st['white_ratio']:.0%}")
    if st["gray_ratio"] > 0.12:
        bits.append(f"灰{st['gray_ratio']:.0%}")
    return f"{name}:{','.join(bits)}"


def _read_species(ram_path: Path) -> dict | None:
    if not ram_path.is_file():
        return None
    data = ram_path.read_bytes()
    # EWRAM starts at offset 0 in ram.bin
    def u16(abs_addr: int) -> int:
        off = abs_addr - 0x02000000
        if off < 0 or off + 2 > len(data):
            return -1
        return struct.unpack_from("<H", data, off)[0]

    return {
        "player_species": u16(SPECIES_PLAYER),
        "enemy_species": u16(SPECIES_ENEMY),
    }


def _verdict_pair(o: dict, t: dict, tag: str) -> tuple[str, str]:
    """粗判：缺墨/灰底/白块 vs origin。最终仍须看图。"""
    notes = []
    fail = False
    for k in ROIS:
        if "menu" in tag and not k.startswith("menu") and k not in ("dialog", "enemy_name", "player_name"):
            if k.startswith("move") or k in ("pp_row", "type_row"):
                continue
        if "move" in tag and k.startswith("menu"):
            continue
        oi, ti = o["rois"][k]["ink_ratio"], t["rois"][k]["ink_ratio"]
        if oi > 0.05 and ti < 0.02:
            notes.append(f"{k}丢墨")
            fail = True
        if t["rois"][k]["gray_ratio"] > 0.18 and o["rois"][k]["gray_ratio"] < 0.08:
            notes.append(f"{k}灰底")
            fail = True
        if t["rois"][k]["white_ratio"] > 0.45 and o["rois"][k]["white_ratio"] < 0.25:
            notes.append(f"{k}白块")
            fail = True
    if fail:
        return "FAIL", ";".join(notes) or "panel"
    if notes:
        return "SUSPECT", ";".join(notes)
    return "PASS", "metrics_ok"


def analyze_run(run_dir: Path) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest.get("pairs") or []
    frames = []
    md = []
    md.append(f"# battle_menu_audit 逐帧描述\n")
    md.append(f"run: `{run_dir}`\n")
    md.append(f"rom_sha256: `{manifest.get('roms', {}).get('translated', {}).get('sha256', '?')}`\n")
    species_note = None

    for p in pairs:
        step = p.get("scene_step") or ""
        if not any(step.startswith(t) or t in step for t in FOCUS_TAGS):
            # 仍分析 ov / 全部关键；扩展：只要含 bt_
            if not step.startswith("bt_"):
                continue
        num = int(p["number"])
        nn = f"{num:03d}"
        op = run_dir / p["origin"]
        tp = run_dir / p["translated"]
        if not op.is_file() or not tp.is_file():
            continue
        oi, ti = Image.open(op), Image.open(tp)
        so, st_ = _scale(oi), _scale(ti)
        o_rois = {k: _stats(_crop(oi, box, so)) for k, box in ROIS.items()}
        t_rois = {k: _stats(_crop(ti, box, st_)) for k, box in ROIS.items()}
        o_desc = " ".join(_describe_roi(k, o_rois[k]) for k in (
            "menu_tl", "menu_tr", "menu_bl", "menu_br",
            "move_tl", "move_tr", "move_bl", "move_br", "pp_row", "type_row",
        ))
        t_desc = " ".join(_describe_roi(k, t_rois[k]) for k in (
            "menu_tl", "menu_tr", "menu_bl", "menu_br",
            "move_tl", "move_tr", "move_bl", "move_br", "pp_row", "type_row",
        ))
        entry = {
            "number": num,
            "step": step,
            "origin": {"rois": o_rois, "desc": o_desc},
            "translated": {"rois": t_rois, "desc": t_desc},
        }
        # species from translated dump if present
        ram = run_dir / "translated" / f"{nn}.ram.bin"
        sp = _read_species(ram)
        if sp and sp["enemy_species"] not in (-1, 0, 0xFFFF):
            entry["species"] = sp
            if species_note is None:
                species_note = sp
        verdict, note = _verdict_pair(entry["origin"], entry["translated"], step)
        entry["verdict"] = verdict
        entry["note"] = note
        frames.append(entry)
        md.append(
            f"{nn} {step} {verdict} | collide=? | jp_text=? | color=? | "
            f"note={note}\n"
            f"  origin: {o_desc}\n"
            f"  zh:     {t_desc}\n"
        )

    summary = {
        "run": str(run_dir),
        "rom_sha256": manifest.get("roms", {}).get("translated", {}).get("sha256"),
        "species": species_note,
        "counts": {
            "pass": sum(1 for f in frames if f["verdict"] == "PASS"),
            "fail": sum(1 for f in frames if f["verdict"] == "FAIL"),
            "suspect": sum(1 for f in frames if f["verdict"] == "SUSPECT"),
        },
        "frames": frames,
    }
    md.insert(
        3,
        f"species: `{species_note}`\n"
        f"frames: pass={summary['counts']['pass']} fail={summary['counts']['fail']} "
        f"suspect={summary['counts']['suspect']}\n"
        f"\n> 指标稿；最终须按 bot/SKILL.md 看图改 collide/jp_text/color。\n",
    )
    (run_dir / "frame_descriptions.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "frame_descriptions.md").write_text("".join(md), encoding="utf-8")
    print(json.dumps({"ok": True, **summary["counts"], "species": species_note,
                      "out": str(run_dir / "frame_descriptions.md")},
                     ensure_ascii=False))
    return summary


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: analyze_battle_menu_frames.py <run_dir>", file=sys.stderr)
        return 2
    analyze_run(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
