#!/usr/bin/env python3
"""把 bikeshop 改回普通 counter，并去掉 counter 模板里的「侧移重试」。

── 决定性的实测对照 ────────────────────────────────────────────────────
bikeshop_mauville 两种配置的位置与结果：
  · 先 UP 4 格 → 站到 **(6,5)** → 四方向 talk → **137/139 帧** ✅
  · 先 RIGHT 2 格 → 站到 **(9,2)** → talk 全超时 → 1 帧 ❌
⇒ 侧移把它带到墙边 (9,2)，反而更远。**侧移是错的，必须去掉。**

而 gamecorner 的成功是另一回事：它的侧移发生在**四方向 talk 失败之后**
（fallback 段），站的位置和 bikeshop 不同，所以两者并不矛盾。

结论：counter 模板只保留「先 UP 4 格 + 四方向 talk」，
去掉我先前加的「侧移后重试」fallback；bikeshop 也回到 counter。

用法：python scripts/_patch_counter_v3.py
"""
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "scripts" / "gen_scenes.py"


def main() -> int:
    s = P.read_text(encoding="utf-8")

    # 1) 去掉 counter 里的「侧移重试」fallback 段
    retry_block = '''
-- 后备：若四方向都没开框，侧移一段再重试（游戏厅这类紧贴柜台的场景）
api.roam{{ seq = {{ "RIGHT", "RIGHT" }}, steps = 2 }}
api.shot("{prefix}_side_retry")
for _, d in ipairs(probe) do
    api.tap(d, 5, 20)
    api.talk{{ timeout = 120, soft = true }}
    api.burst(string.format("{prefix}_r_%s_f", d), 8, 5)
    api.shot(string.format("{prefix}_r_%s", d))
    for i = 1, 2 do api.tap("A", 5, 35) end
    api.tap("B", 4, 25)
end
'''
    if retry_block in s:
        s = s.replace(retry_block, "", 1)
        print("[OK] 去掉 counter 的侧移重试")
    else:
        print("[warn] 未找到侧移重试段（可能已去掉）")

    # 2) bikeshop 回到 counter；gamecorner 改用 counter_left（侧移优先）
    pairs = [
        ('"bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter_left"),',
         '"bikeshop_mauville": ("10:1", 6, 8,  "Mauville 自行车店", "counter"),'),
        ('"gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter"),',
         '"gamecorner_mauville": ("10:3", 8, 10, "Mauville 游戏厅", "counter_left"),'),
    ]
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
            print(f"[OK] {new.split(':')[0]}")
        else:
            print(f"[warn] 未匹配：{old[:46]}")

    P.write_text(s, encoding="utf-8")
    print("[done]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
