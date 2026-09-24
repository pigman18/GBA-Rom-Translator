#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钩子存活探针：驱动到设置页，然后给 3 个文本钩子下断点，制造重画，看谁命中。

用 scripts/mgba_drive.py 的 RSP 客户端（Z0 断点在实测里是被 stub 接受的）。
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\code\GBA-Rom-Translator\scripts")
import mgba_drive as md   # noqa: E402

HOOKS = {
    0x08800084: "hook_C +4  (控制组)",
    0x08800C5C: "chs_canvas_base_for +4",
    0x08800838: "PrintNextChar_Hook +4 (控制组)",
    0x0880064C: "chs_print +4 (控制组)",
}
STATE = r"C:\code\GBA-Rom-Translator\roms\outputs\POKEMON_RUBY_AXVJ00_translated.ss1"
TAG = "hookprobe"


def pc_of(ghex: str) -> int:
    b = bytes.fromhex(ghex)
    if len(b) < 64:
        return -1
    return int.from_bytes(b[60:64], "little")


def main():
    md.kill_mgba()
    time.sleep(0.6)
    emu_log = open(md.TMP / f"emu_{TAG}.log", "w", encoding="utf-8")
    subprocess.Popen([str(md.MGBA_EXE), "-g", "-3", "-t", STATE, str(md.ROM)],
                     cwd=str(md.MGBA_DIR), stdout=emu_log, stderr=subprocess.STDOUT)

    if not md.wait_port(30.0):
        print("stub 端口未开")
        return 1
    setup = md.TMP / f"setup_{TAG}.gdb"
    setup.write_text(
        "set confirm off\nset pagination off\nset height 0\nset width 0\n"
        f"target remote 127.0.0.1:{md.PORT}\n"
        f"set {{unsigned int}}0x{md.POOL_ADDR:08X} = 0x{md.KEYS_ADDR:08X}\n"
        f"set {{unsigned short}}0x{md.KEYS_ADDR:08X} = 0x{md.NO_KEY:03X}\n"
        f"x/1xw 0x{md.POOL_ADDR:08X}\n"
        "continue\n", encoding="ascii", newline="\n")
    g = subprocess.Popen([str(md.GDB_EXE), "-nx", "-batch", "-x", str(setup)],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace")
    time.sleep(3.0)
    g.kill()
    out, _ = g.communicate(timeout=15)
    print("[setup]", " | ".join(x.strip() for x in (out or "").splitlines()
                                if "0x8000468" in x))
    time.sleep(1.2)

    rsp = md.RSP(timeout=8.0)
    rsp.drain(0.8)
    rsp.fire_and_forget("c")
    t0 = time.time()
    print("[probe] running")

    def key_at(t, raw):
        dt = t0 + t - time.time()
        if dt > 0:
            time.sleep(dt)
        rsp.fire_and_forget("M%x,2:%s" % (md.KEYS_ADDR, md.u16le(raw).hex()))

    def pump(until, hits):
        """收集断点命中直到 until（每次命中读 g 取 PC 再 c）。"""
        rsp.s.settimeout(0.25)
        while time.time() < until:
            try:
                kind, val = rsp.token()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                return
            if kind != "pkt" or val[:1] not in (b"S", b"T"):
                continue
            try:
                gh = rsp.cmd("g")
                pc = pc_of(gh.decode())
            except Exception:                 # noqa: BLE001
                pc = -1
            hits[pc] = hits.get(pc, 0) + 1
            name = HOOKS.get(pc)
            if name:
                hits[name] = hits.get(name, 0) + 1
            rsp.fire_and_forget("c")

    # ---- 阶段 1：导航到设置页（已验证的时间表）----
    key_at(3.00, md.NO_KEY & ~(1 << md.KEYBITS["START"]))
    key_at(3.67, md.NO_KEY)
    key_at(5.33, md.NO_KEY & ~(1 << md.KEYBITS["DOWN"]))
    key_at(6.00, md.NO_KEY)
    key_at(7.67, md.NO_KEY & ~(1 << md.KEYBITS["A"]))
    key_at(8.33, md.NO_KEY)
    time.sleep(3.0)                      # 设置页画完

    # ---- 阶段 2：下断点 ----
    armed = []
    for addr in HOOKS:
        try:
            ack = rsp.cmd("Z0,%x,2" % addr, retries=4)
            armed.append((addr, ack))
        except Exception as e:            # noqa: BLE001
            armed.append((addr, f"FAIL {e}"))
    for addr, ack in armed:
        print(f"[probe] Z0 0x{addr:08X} {HOOKS[addr]:26s} -> {ack!r}")
    rsp.fire_and_forget("c")

    # ---- 阶段 3：制造重画（移动光标 / 退出 / 再进）----
    hits = {}
    base = time.time() - t0
    key_at(base + 2.0, md.NO_KEY & ~(1 << md.KEYBITS["DOWN"]))
    key_at(base + 2.6, md.NO_KEY)
    pump(time.time() + 1.5, hits)
    key_at(base + 4.6, md.NO_KEY & ~(1 << md.KEYBITS["DOWN"]))
    key_at(base + 5.2, md.NO_KEY)
    pump(time.time() + 1.5, hits)
    key_at(base + 7.2, md.NO_KEY & ~(1 << md.KEYBITS["B"]))
    key_at(base + 7.8, md.NO_KEY)
    pump(time.time() + 2.5, hits)
    key_at(base + 11.0, md.NO_KEY & ~(1 << md.KEYBITS["START"]))
    key_at(base + 11.6, md.NO_KEY)
    pump(time.time() + 3.0, hits)

    print("\n===== 断点命中统计 =====")
    if not hits:
        print("  （全部 0 命中）")
    for k, v in sorted(hits.items(), key=lambda x: -x[1]):
        if isinstance(k, str):
            print(f"  {k:30s} ×{v}")
        elif k >= 0:
            print(f"  0x{k:08X} ({HOOKS.get(k, '未登记')}) ×{v}")
        else:
            print(f"  <PC 读取失败> ×{v}")

    for addr in HOOKS:
        try:
            rsp.fire_and_forget("z0,%x,2" % addr)
        except Exception:                 # noqa: BLE001
            pass
    rsp.close()
    time.sleep(1.0)
    out, msg = md.capture(TAG)
    print("[probe]", msg)
    md.kill_mgba()
    emu_log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
