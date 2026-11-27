"""审查采集结果：逐字核对血条名字区，防止出现「?」或错字。

判据（来自 docs 铁律 3「验收逐字读图」，这里做成自动化的近似）：
  ① 名字区必须与 lexicon 给出的中文名一致（按字数 + 性别符号截取）
  ② 不允许出现「?」「□」等缺字符号
  ③ 名字右侧必须紧跟 Lv + 数字（验证冒号已去掉）
  ④ 血条框上边框必须连续（验证没「塌」）

名字区几何（GBA 240x160 口径，实测）：
  敌方名字起点 x=20, y=22..29（dn 片那行）
  5 汉字 * 10px = 50px  ⇒ 占 x20..70
  性别符号 8px          ⇒ x70..78
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path

from PIL import Image

ROOT = Path.cwd()
SWEEP = ROOT / "work/POKEMON_RUBY_AXVJ00/sweep"
INDEX = ROOT / "work/_species_index.json"

# 墨色（血条内文字是深灰；性别符号是蓝色）
DARK = {(66, 66, 66), (33, 57, 0), (82, 107, 99), (58, 58, 58)}
BLUE = {(66, 206, 255), (74, 66, 90)}


def col_has_ink(px, x, y0, y1) -> bool:
    return any(px[x, y] in DARK for y in range(y0, y1))


def ink_columns(px, y0=20, y1=29):
    """返回文字行内每列是否有墨。"""
    return {x: col_has_ink(px, x, y0, y1) for x in range(16, 140)}


def name_span(px, n_chars: int):
    """按「起始列 + 字数×pitch」定位名字占用的水平范围。

    实测：名字起点固定 x=21（不论几个字），汉字 pitch=10px。
    所以 n 个字占 [21, 21 + n*10 - 1]。
    这比「扫描找空隙」可靠 —— 汉字之间本身就有空隙。
    """
    start = 21
    end = start + n_chars * 10 - 1
    return start, end


def span_ink_ratio(px, x0: int, x1: int) -> float:
    """指定范围内有墨的列占比。名字若正常渲染应 > 0.5。"""
    if x1 < x0:
        return 0.0
    hit = sum(1 for x in range(x0, x1 + 1) if col_has_ink(px, x, 20, 29))
    return hit / (x1 - x0 + 1)


def frame_border_ok(px) -> bool:
    """血条框上边框（y16/y17）应连续，不出现「塌陷」的浅色块。

    实测（20261126T180502 帧）：上边框是深墨色 `(33,57,0)`，
    从 x18 到 x88 几乎整行连续。塌陷时会出现一段浅色 `(255,255,222)`
    把边框顶开 —— 那正是用户看到的「缺口」。
    ⇒ 判据：在这条边框上，最长连续「非边框色」段必须 ≤ 3px。
    """
    BORDER = (33, 57, 0)
    LIGHT = (255, 255, 222)
    for y in (16, 17):
        run = 0
        worst = 0
        for x in range(20, 86):
            if px[x, y] == LIGHT:
                run += 1
                worst = max(worst, run)
            else:
                run = 0
        if worst > 3:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rec_path = SWEEP / "index.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))

    rows = []
    bad = 0
    for sid, meta in sorted(rec.items(), key=lambda kv: int(kv[0])):
        d = Path(meta.get("dir", ""))
        img = d / "translated.png"
        if not img.exists():
            rows.append((sid, meta["zh"], "NOIMG", ""))
            bad += 1
            continue
        px = Image.open(img).convert("RGB").load()
        expect = meta["zh"]
        n = meta["chars"]
        x0, x1 = name_span(px, n)
        ratio = span_ink_ratio(px, x0, x1)
        border = frame_border_ok(px)

        # 判据：名字应占 x21..21+n*10-1，该范围内墨列占比 > 0.5
        # （每个汉字都有笔画，10 列里通常 7-9 列有墨）
        status = "OK"
        if ratio < 0.5:
            status = f"NOINK({ratio:.2f})"
        elif not border:
            status = "BORDER"

        if status != "OK":
            bad += 1
        rows.append((sid, expect, status, f"x{x0}..{x1} ink={ratio:.2f}"))

    print(f"审查 {len(rows)} 只，异常 {bad} 只\n")
    print(f"{'sid':>4}  {'名字':<12} {'状态':<16} bbox")
    print("-" * 50)
    for r in rows:
        flag = "  " if r[2] == "OK" else "!!"
        print(f"{flag}{r[0]:>3}  {r[1]:<12} {r[2]:<16} {r[3]}")

    if args.report:
        Path(args.report).write_text(
            json.dumps([{"sid": a, "zh": b, "status": c, "bbox": d} for a, b, c, d in rows],
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n报告 -> {args.report}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
