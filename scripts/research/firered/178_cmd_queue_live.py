#!/usr/bin/env python3
"""调研(178) 一次启动抓「谁把中文写进 VRAM」+ 命令队列源地址。

═══════════════════════════════════════════════════════════════════════════
【(176)(177) 建立的新事实（本轮离线确证）】
═══════════════════════════════════════════════════════════════════════════
F1 tilemap(0xF000) 里 pal=15 的文字项，**相邻项 tile 序号差 100% 等于 +1**
   ⇒ 整行文字在 charBase 里是**连续 tile 序列**，不存在跨 tile 拼字。
F2 汉字 = **1 个 8x8 4bpp tile = 32 字节**（不是 13px 变宽字）。
   检查点里「13px 步进 / 12 高」的旧结论作废。
F3 VRAM 含笔画的 tile 只有 **103 个**（tilemap 引用了 288 个，其余全空）。
F4 中文首行字位于 **0x06000020..0x060000E0**（tile 1..7，7 个字）。
F5 空间账重算：2299 字 x 32B = **73,568 B**，远小于可用 30 万字节。

【为什么不用 watchpoint（改方案）】
GBA 硬件 watchpoint 监视的是 **CPU 总线**；DMA 传输不经 CPU，
**DMA 写 VRAM 不会触发 Z2**。(152) 把 watchpoint 设在 charBase 起点，
抓到的 r3=0x020047F0 是 tileset 数据，正是画地图的 DMA 残留，不是画字。

【本脚本的做法：打函数入口断点，当场读命令队列】
(24)(107)(109) 反汇编确证：
  · 0x08000C34 是**每帧执行**的绘制命令分发函数
  · 0x08000C4E: ldr r1,[pc,#100] → 字面量 0x08000CB4 = **0x030000C8**（命令数组基址）
  · 0x08000C50: ldr r2,[pc,#100] → 字面量 0x08000CB8 = **0x030008C9**（索引指针）
  · 0x08000C6C: ldr r7,[pc,#76]  → 字面量 0x08000CBC = **0x040000D4**（DMA3）
  · 命令项 16 字节：+0x00 源地址 / +0x04 目标 VRAM / +0x08 长度 / +0x0A 类型 / +0x0C 额外

之前 (154)~(157) 读队列全 0，原因是**在错误的时刻读**（队列每帧建完即被清）。
⇒ 本脚本在 **0x08000C34 断点命中后立刻**读整段 IWRAM(0x03000000..0x03000900)，
   并连续命中多次（每帧一次），取真正非零的那几帧。

【单次启动纪律】(152 的教训)
 · 只启动一次 mGBA，STARTUPINFO+SW_HIDE，**不起** 150ms 轮询隐藏线程（避免闪屏）
 · --script 驱动 Lua 读档 + 按键推进，--gdb 旁路观察（E1/E2 已证可共存）
 · GDB 连上后必须立即 continue，Lua 才会跑
 · finally 里确保 terminate，不残留进程

【输出】
 work/_probe/cmdq/drive.log        Lua 推进日志
 work/_probe/cmdq/hitNN_*.bin      每次命中的 IWRAM 快照 + 寄存器
 work/_probe/cmdq/hits.json        命中记录（PC/LR/寄存器/队列摘要）

用法：python scripts/research/firered/178_cmd_queue_live.py
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from util.debug_patcher import GdbClient, GdbError   # noqa: E402

OUT = ROOT / "work" / "_probe" / "cmdq"
ROM = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
SAVE = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"

SW_HIDE = 0

ENTRY = 0x08000C34          # 每帧绘制分发函数入口（(24)(107)(109) 确证）
QUEUE_BASE = 0x030000C8     # 命令数组基址（字面量 0x08000CB4）
QUEUE_IDX = 0x030008C9      # 索引指针（字面量 0x08000CB8）
LANE_LEN = 0x900            # 0x03000000..0x03000900 覆盖队列全段
GLYPH_VRAM = 0x06000020     # tile 1 起点（(176)(177) 确证是中文首字）


def find_mgba() -> Path:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    for pat in ("tools/mGBA-*/mGBA.exe", "tools/**/mGBA.exe"):
        c = sorted(ROOT.glob(pat))
        if c:
            return c[0]
    raise SystemExit("找不到 mGBA.exe")


def launch_hidden(cmd, cwd, env):
    """SW_HIDE 启动，**不起**轮询隐藏线程（避免闪屏）。"""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=si,
    )


def parse_regs(g: str) -> list[int] | None:
    """GDB `g` 包是小端字节序（(151) 的教训）。"""
    hp = "".join(ch for ch in g if ch in "0123456789abcdefABCDEF")
    n = len(hp) // 8
    if n < 16:
        return None
    return [int.from_bytes(bytes.fromhex(hp[k * 8:(k + 1) * 8]), "little")
            for k in range(n)]


# ── Lua：读档 → 到菜单 → 之后反复 A/B 逼重画，让断点有料 ───────────────
LUA = r'''
local OUTP = os.getenv("EMU_OUT") or "."
local function unhex(s)
    local t = {}
    for h in s:gmatch("%x%x") do t[#t+1] = string.char(tonumber(h, 16)) end
    return table.concat(t)
end
local IDENT = unhex(os.getenv("EMU_IDENT") or "")
local A, B = 1, 2
local proved, hold = false, 0
local last_dc, stable = -1, 0
local pressed = {}
local tick = 0
local logf = assert(io.open(OUTP .. "/drive.log", "w"))
local function log(s) logf:write(s .. "\n"); logf:flush() end
local function setk(m) emu:setKeys(m) end

callbacks:add("frame", function()
    local f = emu:currentFrame()
    if hold > 0 then
        hold = hold - 1
        if hold == 0 then setk(0) end
        return
    end

    -- 读档判定：存档前 8 字节出现在 EWRAM
    if (not proved) and f > 200 and f % 30 == 0 and #IDENT == 8 then
        local ew = emu:readRange(0x02000000, 0x40000)
        if ew and ew:find(IDENT, 1, true) then
            proved = true
            log("[PROVE] f=" .. f)
            -- 读档瞬间 dump 一份 VRAM，供离线核对字形地址
            local v = emu:readRange(0x06000000, 0x18000)
            local g = assert(io.open(OUTP .. "/vram_prove.bin", "wb"))
            g:write(v); g:close()
        end
    end

    if not proved then
        local dc = emu:read16(0x04000000)
        if dc == last_dc then stable = stable + 1
        else last_dc = dc; stable = 1 end
        if stable == 40 and not pressed[dc] then
            pressed[dc] = true
            hold = 12
            setk(A)
        end
        if f > 5000 then log("[FAIL] no-save f=" .. f) end
        return
    end

    -- 已进菜单：周期性 A / B，让文字反复重画（保证断点有命中）
    tick = tick + 1
    local r = tick % 180
    if r == 1 then
        setk(A); hold = 8
        log("[A] f=" .. f)
    elseif r == 80 then
        setk(B); hold = 8
        log("[B] f=" .. f)
    end
end)
'''


def sum_queue(raw: bytes) -> dict:
    """解析 0x03000000 起的 IWRAM 段里的命令队列。"""
    idx = raw[QUEUE_IDX - 0x03000000] if QUEUE_IDX - 0x03000000 < len(raw) else 0
    base_off = QUEUE_BASE - 0x03000000
    items = []
    for i in range(0, min(idx, 64)):
        o = base_off + i * 16
        if o + 16 > len(raw):
            break
        src, dst, ln, typ, extra = struct.unpack_from("<IIHHI", raw, o) if False \
            else (struct.unpack_from("<I", raw, o)[0],
                  struct.unpack_from("<I", raw, o + 4)[0],
                  struct.unpack_from("<H", raw, o + 8)[0],
                  struct.unpack_from("<H", raw, o + 10)[0],
                  struct.unpack_from("<I", raw, o + 12)[0])
        items.append({"i": i, "src": src, "dst": dst, "len": ln,
                      "type": typ, "extra": extra})
    return {"index": idx, "items": items}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    rom_copy = OUT / (ROM.stem + ".gba")
    shutil.copy2(ROM, rom_copy)
    shutil.copy2(SAVE, OUT / (ROM.stem + ".sav"))
    lua_path = OUT / "drive.lua"
    lua_path.write_text(LUA, encoding="utf-8")

    env = dict(os.environ)
    env["EMU_OUT"] = str(OUT).replace("\\", "/")
    env["EMU_IDENT"] = SAVE.read_bytes()[:8].hex()

    mgba = find_mgba()
    print(f"[1/6] 启动 mGBA（隐藏，单次）: {mgba.name}")
    proc = launch_hidden([str(mgba), "--script", str(lua_path),
                          "--gdb", str(rom_copy)], str(OUT), env)
    time.sleep(5)

    hits: list[dict] = []
    phase = {"v": "init"}
    stop = {"v": False}

    def gdb_worker():
        c = None
        try:
            c = GdbClient("127.0.0.1", 2345, timeout=15.0)
            c.connect()

            # E1：连上必须立刻 continue，Lua 才会跑
            try:
                c.cont(timeout=0.3)
            except GdbError:
                pass
            print("[2/6] continue 已发出，等 Lua 读档")

            # 等 Lua 报告读档完成
            logf = OUT / "drive.log"
            t0 = time.time()
            proved = False
            while time.time() - t0 < 80:
                if logf.exists() and "[PROVE]" in logf.read_text(
                        encoding="utf-8", errors="replace"):
                    proved = True
                    break
                try:
                    c.cont(timeout=2.0)
                except GdbError:
                    pass
            if not proved:
                phase["v"] = "timeout-prove"
                return
            print("[3/6] 已读档进菜单，设函数入口断点")

            # 入口断点：Z0（软件断点，Thumb 2 字节）
            try:
                r = c.cmd(f"Z0,{ENTRY:x},2")
                if r not in ("OK", ""):
                    phase["v"] = f"bp-fail:{r}"
                    return
            except GdbError as e:
                phase["v"] = f"bp-err:{e}"
                return
            phase["v"] = "break-set"
            print(f"[4/6] 断点 @0x{ENTRY:08X} 就绪，开始收集")

            deadline = time.time() + 150
            while not stop["v"] and time.time() < deadline and len(hits) < 40:
                try:
                    why = c.cont(timeout=2.5)
                except GdbError:
                    continue
                if "T05" not in str(why) and "T02" not in str(why) \
                        and "break" not in str(why).lower():
                    continue

                regs = None
                try:
                    regs = c.read_regs()
                except GdbError:
                    pass

                lane = None
                try:
                    lane = c.read_mem(0x03000000, LANE_LEN)
                except GdbError:
                    pass

                n = len(hits)
                rec = {"why": str(why), "regs": regs or {}}
                if lane:
                    (OUT / f"iwram_hit{n:02d}.bin").write_bytes(lane)
                    rec["queue"] = sum_queue(lane)
                    (OUT / f"iwram_hit{n:02d}.bin").write_bytes(lane)

                if regs:
                    rec["pc"] = regs.get("pc", 0)
                    rec["lr"] = regs.get("lr", 0)
                hits.append(rec)

                q = rec.get("queue") or {}
                ni = len(q.get("items", []))
                if n < 12 or n % 5 == 0:
                    pcs = f"PC=0x{(regs or {}).get('pc', 0):08X}"
                    print(f"      #{n} {pcs} 队列项={ni} idx={q.get('index')}")

            phase["v"] = "done"
        except Exception as e:
            phase["v"] = f"error: {e}"
        finally:
            if c:
                try:
                    c.close()
                except Exception:
                    pass

    t = threading.Thread(target=gdb_worker, daemon=True)
    t.start()
    t.join(timeout=260)
    stop["v"] = True
    time.sleep(1)

    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    print("\n[5/6] 汇总")
    print(f"  阶段: {phase['v']}")
    print(f"  命中: {len(hits)}")
    (OUT / "hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    if not hits:
        print("  没有命中 —— 见下方 drive.log")
        lg = OUT / "drive.log"
        if lg.exists():
            print(lg.read_text(encoding="utf-8", errors="replace")[-2000:])
        return 1

    # 队列分析：找出目标落在 VRAM 字形区的项
    print("\n[6/6] 命令队列分析")
    glyph_srcs: Counter[int] = Counter()
    dst_hist: Counter[int] = Counter()
    for h in hits:
        for it in (h.get("queue") or {}).get("items", []):
            dst, src = it["dst"], it["src"]
            dst_hist[dst & 0xFFFFFF00] += 1
            # 目标落在 0x06000000..0x06000100（中文首行字形区）
            if 0x06000000 <= dst < 0x06000200 and 0x08000000 <= src < 0x0A000000:
                glyph_srcs[src] += 1

    print("  队列目标地址（高 24 位）Top10：")
    for d, n in dst_hist.most_common(10):
        print(f"    0x{d:08X}xx  x{n}")

    if glyph_srcs:
        print("\n  ★ 写入中文字形区的 ROM 源地址（这就是字库）：")
        for a, n in glyph_srcs.most_common(20):
            print(f"    0x{a:08X}  x{n}")
    else:
        print("\n  未在队列里找到「目标=字形区 且 源=ROM」的项 —— 见 hits.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
