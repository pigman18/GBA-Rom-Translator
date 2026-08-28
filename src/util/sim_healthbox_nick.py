#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sim_healthbox_nick.py — 用 gdb_patcher 血条昵称 dump 仿真「中文上半有没有被挡」。

输入：src/util/work/{game}/gdb_patcher_log.log 里
  [NickAfterRender] / [NickObjCopy] 的 colN + colN_raw64（或旧日志的 top8/bot8）

输出：同目录 healthbox_nick_sim/ 下 PNG
  - 每列 8×16 的 4bpp 展开（左=chrome前 AfterRender，右=chrome后 ObjCopy）
  - 红框标出 chrome 覆盖带 row0..5（P03：24B；OBJ 仍满拷 32B）
  - 统计：覆盖带内有多少墨水像素 → 被挡比例

用法：
  set PYTHONPATH=%cd%\\src
  C:\\Python314\\python.exe src\\util\\sim_healthbox_nick.py
  C:\\Python314\\python.exe src\\util\\sim_healthbox_nick.py --log path\\to\\gdb_patcher_log.log
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # pragma: no cover
    raise SystemExit("需要 Pillow：pip install Pillow") from e

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LOG = REPO / "src" / "util" / "work" / "POKEMON_RUBY_AXVJ00" / "gdb_patcher_log.log"
BG_NIB = 2
CHROME_ROWS = 6  # P03：24B = row0..5（勿再按 8 行估挡字）
COLS = 7
SCALE = 8

# 4bpp 索引 → 可视色（0 透明底、2 底色偏白、1/3 墨水）
PAL = {
    0: (40, 40, 48),
    1: (240, 240, 255),
    2: (200, 200, 210),  # bg 铺底 ≈ 白块
    3: (160, 160, 200),
    0xA: (80, 200, 80),
    0xB: (255, 220, 40),
}


def _pal(n: int) -> tuple[int, int, int]:
    if n in PAL:
        return PAL[n]
    # 其它当墨水
    return (220, 220, 230) if n else PAL[0]


def _row_bytes(col64: bytes, y: int) -> bytes:
    if y < 8:
        return col64[y * 4 : y * 4 + 4]
    return col64[32 + (y - 8) * 4 : 32 + (y - 8) * 4 + 4]


def _get_px(col64: bytes, x: int, y: int) -> int:
    b = _row_bytes(col64, y)[x // 2]
    return (b & 0xF) if (x & 1) else (b >> 4)


def _is_ink(n: int, bg: int = BG_NIB) -> bool:
    return n != 0 and n != bg


def col_from_raw64(hexstr: str) -> bytes:
    h = re.sub(r"\s+", "", hexstr)
    b = bytes.fromhex(h)
    if len(b) < 64:
        b = b + bytes(64 - len(b))
    return b[:64]


def col_from_top_bot(top8: str, bot8: str) -> bytes:
    """旧日志只有 top8/bot8：拼出不完整列（中间行填 0），仍可看上半白块与下半墨水。"""
    t = bytes.fromhex(re.sub(r"\s+", "", top8))
    b = bytes.fromhex(re.sub(r"\s+", "", bot8))
    col = bytearray(64)
    col[0:8] = (t + bytes(8))[:8]
    col[32:40] = (b + bytes(8))[:8]
    return bytes(col)


def parse_last_session_pairs(log_text: str) -> list[dict]:
    """返回 [{tag, buf, after: [7 cols], obj: [7 cols]|None}, ...] 按 AfterRender 配对后续 ObjCopy。"""
    lines = log_text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith("===== gdb_patcher log")]
    chunk = lines[starts[-1] :] if starts else lines

    events: list[dict] = []
    i = 0
    while i < len(chunk):
        l = chunk[i]
        tag = None
        if "[NickAfterRender]" in l:
            tag = "after"
        elif "[NickObjCopy]" in l:
            tag = "obj"
        if not tag:
            i += 1
            continue
        mbuf = re.search(r"buf=0x([0-9A-Fa-f]+)", l)
        buf = int(mbuf.group(1), 16) if mbuf else 0
        cols: list[bytes | None] = [None] * COLS
        meta: list[dict] = [{} for _ in range(COLS)]
        i += 1
        while i < len(chunk):
            line = chunk[i]
            # 跳过串内容等非 col 行，直到离开本块
            if not line.startswith("  "):
                break
            mr = re.match(
                r"  col(\d+): ink_rows=(-?\d+)\.\.(-?\d+) ink_px=(\d+) "
                r"top8=([0-9a-f ]+) bot8=([0-9a-f ]+)\s*$",
                line,
            )
            if mr:
                ci = int(mr.group(1))
                if 0 <= ci < COLS:
                    meta[ci] = {
                        "fi": int(mr.group(2)),
                        "li": int(mr.group(3)),
                        "ink_px": int(mr.group(4)),
                        "top8": mr.group(5).strip(),
                        "bot8": mr.group(6).strip(),
                    }
                    cols[ci] = col_from_top_bot(meta[ci]["top8"], meta[ci]["bot8"])
                i += 1
                continue
            mraw = re.match(r"  col(\d+)_raw64:\s*([0-9a-fA-F]+)\s*$", line)
            if mraw:
                ci = int(mraw.group(1))
                if 0 <= ci < COLS:
                    cols[ci] = col_from_raw64(mraw.group(2))
                i += 1
                continue
            # 其它缩进行（串: …）跳过，继续找 col
            i += 1
            continue
        events.append({"tag": tag, "buf": buf, "cols": cols, "meta": meta})
        continue
    pairs = []
    for j, ev in enumerate(events):
        if ev["tag"] != "after":
            continue
        obj = None
        for k in range(j + 1, len(events)):
            if events[k]["tag"] == "obj" and events[k]["buf"] == ev["buf"]:
                obj = events[k]
                break
        pairs.append({"buf": ev["buf"], "after": ev, "obj": obj})
    return pairs


def ink_stats(col: bytes | None, meta: dict | None = None, bg: int = BG_NIB) -> tuple[int, int, int, int]:
    """(zone_ink, total_ink, fi, li)。无 raw 时用 meta.ink_rows 估算覆盖带相交。"""
    if col:
        zone, total = 0, 0
        fi, li = -1, -1
        for y in range(16):
            for x in range(8):
                n = _get_px(col, x, y)
                if _is_ink(n, bg):
                    total += 1
                    if fi < 0:
                        fi = y
                    li = y
                    if y < CHROME_ROWS:
                        zone += 1
        # 旧日志只有 top8/bot8：用 meta 的 ink_rows 修正「覆盖带是否与墨水相交」
        if meta and meta.get("fi", -1) >= 0:
            mfi, mli = meta["fi"], meta["li"]
            if total == 0 and meta.get("ink_px", 0) > 0:
                total = int(meta["ink_px"])
                fi, li = mfi, mli
            # 覆盖带 [0,8) 与 [mfi,mli] 相交 → 认为会被挡
            if mfi >= 0 and mfi < CHROME_ROWS and mli >= mfi:
                overlap = max(0, min(mli + 1, CHROME_ROWS) - mfi)
                if overlap > 0 and zone == 0:
                    # 按行比例粗估
                    span = max(1, mli - mfi + 1)
                    zone = max(1, total * overlap // span)
        return zone, total, fi, li
    if meta and meta.get("fi", -1) >= 0:
        mfi, mli = meta["fi"], meta["li"]
        total = int(meta.get("ink_px") or 0)
        overlap = max(0, min(mli + 1, CHROME_ROWS) - mfi) if mfi < CHROME_ROWS else 0
        span = max(1, mli - mfi + 1)
        zone = (total * overlap // span) if overlap else 0
        return zone, total, mfi, mli
    return 0, 0, -1, -1


def render_col(col: bytes | None, label: str) -> Image.Image:
    w, h = 8 * SCALE, 16 * SCALE
    im = Image.new("RGB", (w + 4, h + 18), (20, 20, 24))
    dr = ImageDraw.Draw(im)
    if col:
        for y in range(16):
            for x in range(8):
                c = _pal(_get_px(col, x, y))
                x0, y0 = 2 + x * SCALE, 16 + y * SCALE
                dr.rectangle([x0, y0, x0 + SCALE - 1, y0 + SCALE - 1], fill=c)
    # chrome 带红框
    dr.rectangle(
        [2, 16, 2 + 8 * SCALE - 1, 16 + CHROME_ROWS * SCALE - 1],
        outline=(255, 60, 60),
        width=2,
    )
    dr.text((2, 1), label, fill=(220, 220, 220))
    return im


def render_pair(pair: dict, idx: int, out_dir: Path) -> Path:
    after_cols = pair["after"]["cols"]
    after_meta = pair["after"]["meta"]
    obj_cols = pair["obj"]["cols"] if pair["obj"] else [None] * COLS
    obj_meta = pair["obj"]["meta"] if pair["obj"] else [{} for _ in range(COLS)]
    cell_w = 8 * SCALE + 8
    cell_h = 16 * SCALE + 24
    img = Image.new("RGB", (cell_w * COLS * 2 + 40, cell_h + 100), (16, 16, 20))
    dr = ImageDraw.Draw(img)
    title = (
        f"buf=0x{pair['buf']:08X}  L=AfterRender R=ObjCopy  "
        f"red=chrome zone row0..5 (24B)"
    )
    dr.text((8, 8), title, fill=(240, 240, 240))

    report = []
    for ci in range(COLS):
        a = after_cols[ci]
        o = obj_cols[ci]
        za, ta, fi, li = ink_stats(a, after_meta[ci])
        zo, to, _, _ = ink_stats(o, obj_meta[ci])
        report.append(
            f"col{ci}: after ink={ta} rows={fi}..{li} in_zone={za}  "
            f"obj ink={to} in_zone={zo}  BLOCKED~={za}"
        )
        ia = render_col(a, f"A{ci}")
        io = render_col(o, f"O{ci}")
        x = 8 + ci * cell_w * 2
        img.paste(ia, (x, 40))
        img.paste(io, (x + cell_w, 40))

    y = cell_h + 44
    for line in report:
        dr.text((8, y), line, fill=(200, 200, 200))
        y += 12

    out = out_dir / f"nick_sim_{idx:02d}_0x{pair['buf']:08X}.png"
    img.save(out)
    out.with_suffix(".txt").write_text("\n".join(report), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="血条昵称缓冲仿真：中文上半是否被 chrome 挡")
    ap.add_argument("--log", default=str(DEFAULT_LOG), help="gdb_patcher_log.log")
    ap.add_argument(
        "--out",
        default="",
        help="输出目录，默认与 log 同级 healthbox_nick_sim/",
    )
    args = ap.parse_args()
    log_path = Path(args.log)
    if not log_path.is_file():
        raise SystemExit(f"找不到日志: {log_path}")
    out_dir = Path(args.out) if args.out else log_path.parent / "healthbox_nick_sim"
    out_dir.mkdir(parents=True, exist_ok=True)

    text = log_path.read_text(encoding="utf-8", errors="replace")
    pairs = parse_last_session_pairs(text)
    if not pairs:
        raise SystemExit("未解析到 NickAfterRender；请先按埋点抓一轮战斗昵称")

    print(f"log: {log_path}")
    print(f"pairs AfterRender<->ObjCopy: {len(pairs)}")
    print(f"out: {out_dir}")
    print("note: PCS source may look JP; slot makes Chinese in buffer ink.")
    print("      ink inside red box (row0..5) = blocked by chrome.\n")

    for i, pair in enumerate(pairs):
        path = render_pair(pair, i, out_dir)
        after = pair["after"]["cols"]
        meta = pair["after"]["meta"]
        total_zone = total_ink = 0
        for ci in range(COLS):
            z, t, _, _ = ink_stats(after[ci], meta[ci])
            total_zone += z
            total_ink += t
        pct = (100.0 * total_zone / total_ink) if total_ink else 0.0
        print(
            f"[{i}] buf=0x{pair['buf']:08X}  "
            f"ink_before={total_ink} in_chrome_zone={total_zone} ({pct:.0f}% blocked)  "
            f"-> {path.name}"
        )


if __name__ == "__main__":
    main()
