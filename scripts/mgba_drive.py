#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mGBA 输入驱动：把键盘读取重定向到 EWRAM，再用本地脚本喂键。

**绝不模拟键盘**（不 SendKeys / 不 SendInput / 不 pyautogui / 不 PostMessage）。

为什么不用 Lua，也不用 gdb 逐帧断点
==================================
1. 本仓库 mGBA 0.10.5 的 Qt/SDL 两个前端**都没有** `--script`（Qt 的 `-s` 是
   frameskip）；Lua 5.4 虽编进了 `mGBA.exe`（`ScriptingView` 也在），但 CLI
   没有任何入口，`scripts/` 目录**不会**自动执行（实测：放探针脚本进去未执行）。
2. 项目规则 `.cursor/rules/mgba-script-input-only.mdc` 禁止键盘模拟，只允许
   「仓库内本地脚本 + 模拟器执行」⇒ 本文件即那个脚本。
3. gdb 逐帧断点可行但**极慢**（实测 ~55 ms/帧 ≈ 18 fps），因为 mGBA 的 stub
   是轮询式的。改成下面这招后**完全没有逐帧开销**。

原理：把 KEYINPUT 的指针搬进「我们自己的 ROM 区」
================================================
日版 ROM 里 `ReadKeys()` 只出现一次，逐指令如下：

    0800042c   push {lr}
    0800042e   ldr  r0, [pc, #56]  @ (0x08000468)  <- 池字 = 0x04000130
    08000430   ldrh r1, [r0]                       <- 唯一的键盘读取点
    08000432   ldr  r2, [pc, #56]  @ (0x0800046c)  = 0x000003FF
    08000438   eors r3, r1                         ; r3 = 按下位（高有效）
    0800043a   ldr  r1, [pc, #52]  @ (0x08000470)  = 0x030016E0
    08000442   strh r0, [r1, #42]                  ; gMain.newKeys = ...

GDB stub 实测**可以写 ROM**（mGBA 走 rawWrite）。于是把 `0x08000468` 这个池字
改成一个我们自己的 ROM 地址 `KEYS_ADDR`，`ldrh r1,[r0]` 就改成从那里取值 ——
之后每帧要按什么键，只需往 `KEYS_ADDR` 写一个 u16。

⚠ 为什么不用 EWRAM/IWRAM 放键值：mGBA 的 stub 对 `M`/`m` 有分区限制 ——
ROM 读写都行；IWRAM 读行写不行；**EWRAM 读写都被 NAK**（0x0203FFF0 实测）。
原盘只有 8 MB，所以 `0x08800000` 之后整片都是我们的注入区，拿来做暂存最安全。

⇒ 零逐帧开销、零行为改动（只换输入源）、**不改 ROM 文件**。

按键位（KEYINPUT 低有效，0x3FF = 全部松开）
    A=bit0  B=bit1  SELECT=bit2  START=bit3  RIGHT=bit4
    LEFT=bit5  UP=bit6  DOWN=bit7  R=bit8  L=bit9

用法
====
    python scripts/mgba_drive.py --state ss1 --schedule "START:120-140" \
        --frames 900 --tag ss1_menu

`--schedule`：`按键:起始帧-结束帧`，逗号分隔可多段，帧按 `--fps` 折算成墙钟：
    "START:120-140,DOWN:300-320,DOWN:400-420,A:600-620"
组合键用 `+`：`"DOWN+A:600-620"`。

产物
====
    .tmp/drive_<tag>.log    运行日志
    .tmp/drive_<tag>.json   verdict
    .tmp/emu_<tag>.png      **真实模拟器窗口**截图
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\code\GBA-Rom-Translator")
MGBA_DIR = ROOT / "tools" / "mGBA-0.10.5-win32"
MGBA_EXE = MGBA_DIR / "mGBA.exe"
GDB_EXE = Path(r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
               r"\14.2 rel1\bin\arm-none-eabi-gdb.exe")
ROM = ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
TMP = ROOT / ".tmp"

PORT = 2345
POOL_ADDR = 0x08000468          # ReadKeys 的池字（原值 0x04000130）
POOL_ORIG = 0x04000130
# 🔴 必须是 **ROM 区**的地址：实测 mGBA stub 对 `M`/`m` 的分区支持是
#      ROM(0x08000000+)  读写都 OK
#      IWRAM(0x03000000+) 读 OK / 写被 NAK
#      EWRAM(0x02000000+) 读写**都被 NAK**（`P`、`?` 同样被 NAK）
#   ⇒ 把键值放在我们自己的注入区（原盘只有 8 MB，0x08800000 之后全是我们的），
#     用 `M` 包改它即可；这也是唯一能「目标运行中也能写」的地方。
KEYS_ADDR = 0x08900000
NO_KEY = 0x3FF

KEYBITS = {
    "A": 0, "B": 1, "SELECT": 2, "START": 3, "RIGHT": 4,
    "LEFT": 5, "UP": 6, "DOWN": 7, "R": 8, "L": 9,
}


# ---------------------------------------------------------------- RSP 客户端
class RSP:
    """最小 GDB RSP 客户端：只用 m / M。按 token 流解析，容忍 ACK/NAK 夹杂。"""

    def __init__(self, host="127.0.0.1", port=PORT, timeout=8.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buf = bytearray()

    # --- 原始字节流 ---
    def _fill(self):
        d = self.s.recv(8192)
        if not d:
            raise IOError("stub socket closed")
        self.buf += d

    def _byte(self):
        while not self.buf:
            self._fill()
        b = self.buf[0]
        del self.buf[0]
        return bytes([b])

    def token(self):
        """返回 ('ack'|'nak', None) 或 ('pkt', payload)。"""
        while True:
            b = self._byte()
            if b == b"+":
                return ("ack", None)
            if b == b"-":
                return ("nak", None)
            if b == b"$":
                data = bytearray()
                while True:
                    c = self._byte()
                    if c == b"#":
                        break
                    data += c
                self._byte(); self._byte()      # checksum
                try:
                    self.s.sendall(b"+")        # 按 GDB 协议 ACK 对方
                except OSError:
                    pass
                return ("pkt", bytes(data))

    def send(self, payload):
        p = payload.encode() if isinstance(payload, str) else payload
        self.s.sendall(b"$" + p + b"#%02X" % (sum(p) & 0xFF))

    def cmd(self, payload, retries=6, timeout=None):
        if timeout is not None:
            self.s.settimeout(timeout)
        naks = 0
        for _ in range(retries):
            self.send(payload)
            while True:
                kind, val = self.token()
                if kind == "pkt":
                    return val
                if kind == "nak":
                    naks += 1
                    break
        raise IOError("cmd %r 反复被拒（naks=%d）" % (payload, naks))

    # --- 语义封装 ---
    def poke(self, addr, data: bytes, retries=6, timeout=None):
        return self.cmd("M%x,%x:%s" % (addr, len(data), data.hex()),
                        retries=retries, timeout=timeout)

    def peek(self, addr, n, timeout=None):
        r = self.cmd("m%x,%x" % (addr, n), timeout=timeout)
        return bytes.fromhex(r.decode())

    def fire_and_forget(self, payload):
        """目标在跑时发包，不确保有回复（超时也不报错）。"""
        try:
            self.send(payload)
        except OSError as e:
            return f"send-fail {e}"
        return "sent"

    def drain(self, secs=0.4):
        end = time.time() + secs
        got = []
        while time.time() < end:
            self.s.settimeout(max(0.05, end - time.time()))
            try:
                self.buf += self.s.recv(4096)
            except (socket.timeout, TimeoutError):
                break
            except OSError:
                break
        # 丢弃缓冲里残留的问候/停止包
        self.buf.clear()
        return got

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def u16le(v):
    return (v & 0xFFFF).to_bytes(2, "little")


def u32le(v):
    return (v & 0xFFFFFFFF).to_bytes(4, "little")


# ---------------------------------------------------------------- 计划解析
def parse_schedule(spec: str):
    out = []
    if not spec:
        return out
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part or "-" not in part:
            raise SystemExit(f"schedule 段格式应为 KEY:起-止 -> {part!r}")
        name, rng = part.split(":", 1)
        f0s, f1s = rng.split("-", 1)
        bits = 0
        for k in name.split("+"):
            k = k.strip().upper()
            if k not in KEYBITS:
                raise SystemExit(f"未知按键 {k!r}（可用: {', '.join(KEYBITS)}）")
            bits |= 1 << KEYBITS[k]
        out.append((int(f0s), int(f1s), NO_KEY & ~bits, name.strip().upper()))
    out.sort(key=lambda x: x[0])
    return out


# ---------------------------------------------------------------- 环境
def wait_port(timeout=30.0):
    """等 stub 监听 2345。

    🔴 不能用 connect 探测：mGBA 的 stub 只认一条连接，探测性 connect+close
    会把唯一槽位吃掉，真正的客户端随即超时（已实测踩坑）。改用 netstat 只看。
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = subprocess.run(["netstat", "-an"], capture_output=True, timeout=10)
            out = (r.stdout or b"").upper()
            if b":2345" in out and b"LISTENING" in out:
                time.sleep(0.6)
                return True
        except Exception:                     # noqa: BLE001
            pass
        time.sleep(0.3)
    return False


def kill_mgba():
    subprocess.run(["taskkill", "/F", "/IM", "mGBA.exe", "/T"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def capture(tag: str):
    out = TMP / f"emu_{tag}.png"
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(TMP / "cap_win.ps1"), "-Out", str(out)],
        capture_output=True, text=True, errors="replace")
    return out, (r.stdout or "").strip()


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="-", help="ss1..ss6 / 绝对路径 / -")
    ap.add_argument("--schedule", default="", help="按键计划，见文件头注释")
    ap.add_argument("--frames", type=int, default=900, help="总帧数（墙钟折算）")
    ap.add_argument("--fps", type=float, default=60.0, help="折算用的帧率")
    ap.add_argument("--tag", default="drive")
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--hold-lead", type=float, default=0.0,
                    help="每个按键提前量（秒），微调手感")
    ap.add_argument("--tail", type=float, default=2.0,
                    help="计划跑完后再等多少秒才截图")
    ap.add_argument("--shot-times", default="",
                    help="在这些秒数各截一张图（逗号分隔），用于盲开导航")
    ap.add_argument("--no-capture", action="store_true")
    ap.add_argument("--dump", action="store_true",
                    help="收工前再用 gdb dump EWRAM（分析 diag 采样块）")
    ap.add_argument("--no-redirect", action="store_true",
                    help="只截图不注入（对照组）")
    ap.add_argument("--gdb-set", default="",
                    help="Phase 1 额外 gdb 写，逗号分隔 addr=val（如 0x0203FEB8=1）；"
                         "绕过 stub 对 EWRAM 写入的 NAK")
    ap.add_argument("--keep-alive", action="store_true",
                    help="收工后不杀 mGBA（RSP 仍会关闭），供后续 gdb 断点采样")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    TMP.mkdir(exist_ok=True)
    schedule = parse_schedule(args.schedule)

    state = None
    if args.state and args.state != "-":
        p = Path(args.state)
        if not p.exists():
            p = ROOT / "roms" / "outputs" / f"POKEMON_RUBY_AXVJ00_translated.{args.state}"
        if not p.exists():
            raise SystemExit(f"找不到 savestate：{args.state}")
        state = p

    lines = []

    def log(s):
        lines.append(s)
        print(s, flush=True)

    kill_mgba()
    time.sleep(0.6)

    emu_args = [str(MGBA_EXE), "-g", "-3"]
    if state:
        emu_args += ["-t", str(state)]
    emu_args.append(args.rom)
    log(f"[drive] launch: {' '.join(emu_args)}")
    emu_log = open(TMP / f"emu_{args.tag}.log", "w", encoding="utf-8")
    subprocess.Popen(emu_args, cwd=str(MGBA_DIR),
                     stdout=emu_log, stderr=subprocess.STDOUT)

    verdict = {"tag": args.tag, "state": str(state) if state else None,
               "schedule": args.schedule, "frames": args.frames,
               "redirect": not args.no_redirect}

    rsp = None
    try:
        if not wait_port(30.0):
            raise SystemExit("mGBA GDB stub 端口未开（沙箱没关？端口被占？）")
        log("[drive] stub ready")

        # ---------------- Phase 1：用 gdb 做一次性「池字重定向」 ----------------
        # 为什么非得用 gdb：实测 mGBA stub 只接受写 **我们自己的注入区**
        # (0x08800000+)，写真正的卡带 ROM 区 (0x08000468) 会被 NAK；
        # 而 gdb 走的是另一条内部路径，能写。
        if not args.no_redirect:
            setup = TMP / f"setup_{args.tag}.gdb"
            body1 = [
                "set confirm off", "set pagination off", "set height 0",
                "set width 0", "set remotetimeout 8",
                f"target remote 127.0.0.1:{PORT}",
                'printf "SETUP pool before = "',
                f"x/1xw 0x{POOL_ADDR:08X}",
                f"set {{unsigned int}}0x{POOL_ADDR:08X} = 0x{KEYS_ADDR:08X}",
                f"set {{unsigned short}}0x{KEYS_ADDR:08X} = 0x{NO_KEY:03X}",
                'printf "SETUP pool after  = "',
                f"x/1xw 0x{POOL_ADDR:08X}",
                'printf "SETUP keys        = "',
                f"x/1xh 0x{KEYS_ADDR:08X}",
            ]
            for item in ([s for s in args.gdb_set.split(",") if s.strip()]
                         if args.gdb_set else []):
                a, v = item.split("=")
                body1.append(f"set {{unsigned char}}0x{int(a, 0):08X} = {int(v, 0)}")
                body1.append(f'printf "SETUP gdbset 0x{int(a, 0):08X} = "')
                body1.append(f"x/1xb 0x{int(a, 0):08X}")
            body1.append("continue")
            setup.write_text("\n".join(body1) + "\n",
                             encoding="ascii", newline="\n")

            g = subprocess.Popen(
                [str(GDB_EXE), "-nx", "-batch", "-x", str(setup)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace")
            time.sleep(3.0)                  # 前 3 行 echo 完就进 continue（阻塞）
            g.kill()
            out, _ = g.communicate(timeout=15)
            for ln in (out or "").splitlines():
                if ln.strip():
                    log(f"[setup] {ln.strip()}")
            if "08900000" not in (out or ""):
                raise SystemExit("池字重定向失败：gdb 回读里没看到 0x08900000")
            time.sleep(1.2)                  # 等 socket 关闭、目标继续跑

        # ---------------- Phase 2：RSP 喂键（目标保持运行） ----------------
        rsp = RSP(timeout=8.0)
        rsp.drain(0.8)
        rsp.fire_and_forget("c")
        t0 = time.time()
        log("[drive] connected; target running")

        events = []
        for f0, f1, raw, name in schedule:
            events.append((f0 / args.fps, raw, name + " press"))
            events.append((f1 / args.fps, NO_KEY, name + " release"))
        events.sort()

        # 合并时间轴：按键写入 + 中途截图（导航盲开时非常有用）
        timeline = [(t, "key", (raw, name)) for t, raw, name in events]
        shots = [float(x) for x in args.shot_times.split(",") if x.strip()]
        for s in shots:
            timeline.append((s, "shot", None))
        timeline.sort(key=lambda x: x[0])

        # 🔴 截图走 PowerShell，单次要 1~2s。若在主时间轴上同步调用，会把后面的
        # 按键写入整体推迟 ⇒ 实测「按了 3 次 DOWN 只落地 2 次」。改为后台线程抓图，
        # 主线程只负责按墙钟喂键。
        import threading
        cap_threads = []

        def _cap_async(t_off, tag):
            try:
                out, capmsg = capture(tag)
                log(f"[drive] shot t={t_off:6.2f}s -> {out.name}  ({capmsg})")
                verdict.setdefault("shots", []).append(str(out))
            except Exception as e:                 # noqa: BLE001
                log(f"[drive] shot t={t_off:6.2f}s FAILED: {e}")

        n_sent = 0
        for t_off, kind, payload in timeline:
            want = t0 + t_off + (args.hold_lead if kind == "key" else 0.0)
            dt = want - time.time()
            if dt > 0:
                time.sleep(dt)
            el = time.time() - t0
            if kind == "key":
                raw, label = payload
                rsp.fire_and_forget("M%x,2:%s" % (KEYS_ADDR, u16le(raw).hex()))
                n_sent += 1
                if args.verbose or raw != NO_KEY:
                    log(f"[drive] t={el:6.2f}s (~frame {el * args.fps:6.1f}) "
                        f"keys=0x{raw:03X}  {label}")
            else:
                th = threading.Thread(target=_cap_async,
                                      args=(t_off, f"{args.tag}_t{int(t_off)}"),
                                      daemon=True)
                th.start()
                cap_threads.append(th)
        for th in cap_threads:
            th.join(timeout=30)

        remain = args.frames / args.fps - (time.time() - t0)
        if remain > 0:
            time.sleep(remain)
        rsp.fire_and_forget("M%x,2:%s" % (KEYS_ADDR, u16le(NO_KEY).hex()))
        verdict["key_writes"] = n_sent
        verdict["seconds"] = round(time.time() - t0, 2)
        log(f"[drive] done in {verdict['seconds']}s, key writes={n_sent}")

        # ---------------- Phase 3（可选）：dump 内存供分析 ----------------
        if args.dump:
            if args.no_capture:
                log("[drive] dump (skip shot)")
            else:
                cap = capture(f"{args.tag}_final")
                log(f"[drive] final shot -> {cap[0].name}")
                verdict["screenshot"] = str(cap[0])
            rsp.close()
            rsp = None
            time.sleep(1.0)
            # 四块都抓：EWRAM（窗口/状态）、VRAM（tile 数据）、
            # IWRAM（引擎态）、PALRAM（0x05000000，值→色的唯一权威；
            # 「红/黑/阴影到底是哪个色号」必须靠它，2026-09-21 红坨排查加）
            blocks = (("ewram", 0x02000000, 0x02040000),
                      ("vram",  0x06000000, 0x06018000),
                      ("iwram", 0x03000000, 0x03008000),
                      ("pal",   0x05000000, 0x05000400),
                      # IO：BGxCNT / DISPCNT —— 「这一帧每个 BG 层的
                      # charBase/screenBase 是多少」只能从寄存器读，
                      # 撞 UI 判据（map 引用号 vs 我方槽域）必须靠它。
                      ("io",    0x04000000, 0x04000060))
            dumpgdb = TMP / f"dump_{args.tag}.gdb"
            body = ["set confirm off", "set pagination off", "set height 0",
                    "set width 0", "set remotetimeout 8",
                    f"target remote 127.0.0.1:{PORT}"]
            paths = {}
            for name, lo, hi in blocks:
                p = TMP / f"drive_{args.tag}_{name}.bin"
                paths[name] = (p, hi - lo)
                body.append(f"dump binary memory {p} 0x{lo:08X} 0x{hi:08X}")
            # IO 寄存器：判断「屏幕上真正显示文字的是哪个 BG、charBase/screenBase 各是多少」
            for nm, ad in (("DISPCNT", 0x04000000), ("BG0CNT", 0x04000008),
                           ("BG1CNT", 0x0400000A), ("BG2CNT", 0x0400000C),
                           ("BG3CNT", 0x0400000E),
                           ("BG0HOFS", 0x04000010), ("BG0VOFS", 0x04000012),
                           ("BG1HOFS", 0x04000014), ("BG1VOFS", 0x04000016),
                           ("BG2HOFS", 0x04000018), ("BG2VOFS", 0x0400001A),
                           ("BG3HOFS", 0x0400001C), ("BG3VOFS", 0x0400001E)):
                body.append(f'printf "IO {nm} "')
                body.append(f"x/1xh 0x{ad:08X}")
            body.append('printf "DUMP_DONE\\n"')
            dumpgdb.write_text("\n".join(body) + "\n",
                               encoding="ascii", newline="\n")
            g = subprocess.Popen(
                [str(GDB_EXE), "-nx", "-batch", "-x", str(dumpgdb)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace")
            try:
                dout, _ = g.communicate(timeout=180)
            except subprocess.TimeoutExpired:
                g.kill()
                dout, _ = g.communicate(timeout=10)
            got = {n: (p.exists() and p.stat().st_size == sz)
                   for n, (p, sz) in paths.items()}
            ok = "DUMP_DONE" in (dout or "") and all(got.values())
            verdict["dumps"] = {n: (str(paths[n][0]) if v else None)
                                for n, v in got.items()}
            log(f"[drive] dump {got} "
                f"({'OK' if ok else 'FAILED: ' + (dout or '').strip()[-160:]})")
            for ln in (dout or "").splitlines():
                if "IO " in ln or "0x400000" in ln:
                    log(f"[io] {ln.strip()}")
    except SystemExit as e:
        log(f"[drive] ABORT: {e}")
        verdict["error"] = str(e)
    except Exception as e:                     # noqa: BLE001
        log(f"[drive] ERROR: {type(e).__name__}: {e}")
        verdict["error"] = f"{type(e).__name__}: {e}"
    finally:
        if rsp:
            rsp.close()
        time.sleep(args.tail)
        if not args.no_capture:
            out, capmsg = capture(args.tag)
            log(f"[drive] {capmsg}")
            verdict["screenshot"] = str(out)
            verdict["capture"] = capmsg
        (TMP / f"drive_{args.tag}.log").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        (TMP / f"drive_{args.tag}.json").write_text(
            json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.keep_alive:
            log("[drive] keep-alive：mGBA 保持运行（RSP 已关），可接 gdb 采样")
        else:
            kill_mgba()
        emu_log.close()


if __name__ == "__main__":
    main()
