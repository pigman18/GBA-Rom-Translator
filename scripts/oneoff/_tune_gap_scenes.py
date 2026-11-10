#!/usr/bin/env python3
"""按截图微调两个缺口场景的落点。

── 观察（003.png 放大后）──────────────────────────────────────────────
contest_lilycove (13:5)：
  warp 到 (10,12) 时，主角在画面中央偏下，**右上角有一位深衣 NPC**，
  画面上方还有几个 NPC。左上角是展示台。
  ⇒ 把落点往右上挪：约 (12,9) 一带，或直接用「先走上几格」的策略。

gamecorner_mauville (10:3)：
  warp 到 (8,10) 时，主角在画面下方中央，**正上方 2 格就有绿帽女性 NPC**，
  左侧是老虎机区（有多个 NPC），右侧有柜台和告示牌。
  ⇒ 落点 (8,10) 其实不错，只要**先把 UP 走通**（之前 UP 被挡是因为
    落点紧贴老虎机）。改成往**右侧**绕一点再上去。

用法：python scripts/_tune_gap_scenes.py
"""
from pathlib import Path

GEN = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = GEN.read_text(encoding="utf-8")
    repl = {
        # 游戏厅：往右挪一点，避开紧贴的老虎机
        '"gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter"),':
            '"gamecorner_mauville": ("10:3", 12, 10, "Mauville 游戏厅", "counter"),',
        # 大赛会场：往右上靠近 NPC
        '"contest_lilycove": ("13:5", 10, 12, "Lilycove 华丽大赛会场", "interior"),':
            '"contest_lilycove": ("13:5", 12, 8, "Lilycove 华丽大赛会场", "interior"),',
    }
    n = 0
    for old, new in repl.items():
        if old in s:
            s = s.replace(old, new)
            n += 1
        else:
            print(f"[warn] 未找到：{old[:50]}")
    GEN.write_text(s, encoding="utf-8")
    print(f"[OK] 调整 {n} 个落点")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
