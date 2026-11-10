"""调研(220) 修正：白屏不算稳定，必须等到真实画面。

═══ 219 的错误 ═══
s08 和 s09 的 sha 相同（3d8eea0c）= **白屏**。
我在白屏上就判定「进入回顾」，然后狂按 B，把读档取消了。

根因：稳定判据只看「VRAM 前 0x4000 不变」，白屏满足这个条件！

修正：
 ① 白屏判定：VRAM 前 0x4000 全 0 或全同一值 -> 视为「未就绪」，不计数
 ② 只有画面**有内容且稳定**才算就绪
 ③ 就绪后按 A；连续多次 A 后若出现回顾，等它自己播完

更简单可靠的做法：
 ① 读档后一直按 A（A 是「继续/确认」，不会取消读档）
 ② 每按一次 A 截一张，直到出现「地图」（有主角、可移动）
 ③ 地图判据：画面稳定 + 有 OBJ 精灵

但 A 在回顾里是「下一页」，按多次就能翻完回顾，最后自然进入地图。

→ 就用「一直按 A，最多 40 次，每次截图」。
   不按 B，避免取消读档。

用法：python scripts/research/firered/220_only_a.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT = ROOT / "work" / "_probe" / "party220"

LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local A, B, START = 1, 2, 8
local HOLDN = 16
local hold, wait = 0, 0
local shotn = 0
local lastv, stable = nil, 0
local acnt = 0
local MAXA = 40

local function setk(m) emu:setKeys(m) end
local function rd(a, l)
    local ok, b = pcall(function() return emu:readRange(a, l) end)
    if ok and b then return b end
    return nil
end
local function wr(n, d)
    local f = assert(io.open(OUTP .. "/" .. n, "wb"))
    f:write(d); f:close()
end
-- 判断画面是否「有内容」（非全白/非全黑）
local function has_content(v)
    if not v then return false end
    local nz = 0
    for i = 1, #v, 7 do
        if v:byte(i) ~= 0 then nz = nz + 1 end
    end
    return nz > (#v / 7) * 0.05
end
local function snap(tag)
    shotn = shotn + 1
    local n = string.format("%02d", shotn)
    local v = rd(0x06000000, 0x18000)
    if v then wr("s" .. n .. "_" .. tag .. "_vram.bin", v) end
    local e = rd(0x02000000, 0x40000)
    if e then wr("s" .. n .. "_" .. tag .. "_ewram.bin", e) end
    local i = rd(0x03000000, 0x8000)
    if i then wr("s" .. n .. "_" .. tag .. "_iwram.bin", i) end
    emu:screenshot(OUTP .. "/s" .. n .. "_" .. tag .. ".png")
    RL("[SNAP] " .. n .. " " .. tag .. " f=" .. RUN.f)
end

callbacks:add("frame", WRAP("main", function()
    RUN.f = RUN.f + 1
    local f = RUN.f
    if hold > 0 then hold = hold - 1; if hold == 0 then setk(0) end; return end
    if wait > 0 then wait = wait - 1; return end

    local v = rd(0x06000000, 0x4000)
    local ready = has_content(v)
    if ready and lastv and v == lastv then stable = stable + 1
    else stable = 0 end
    lastv = v

    -- 有内容 + 稳定 55 帧 = 就绪
    if stable >= 55 then
        acnt = acnt + 1
        stable = 0
        snap("a" .. string.format("%02d", acnt))
        if acnt > MAXA then
            RL("[DONE-MAX] acnt=" .. acnt)
            DS_DONE(0, "maxA")
            return
        end
        hold = HOLDN
        setk(A)
        RL("[A] " .. acnt)
        return
    end

    if f > 24000 then DS_DONE(1, "late") end
end))
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    r = run_lua(LUA, OUT, expect_files=["s01_a01.png"], min_frames=800,
                rom=ROM_ZH, save=SAVE_FR, timeout=560)
    print(r.report())
    print(r.log_text[-2500:])
    print("\n截图：")
    for s in sorted(OUT.glob("s*.png")):
        h = hashlib.sha256(s.read_bytes()).hexdigest()[:8]
        sz = s.stat().st_size
        print(f"  {s.name:<26} {h} {sz:>6}B")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
