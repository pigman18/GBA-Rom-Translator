#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gdb_shot.py — 通过 mGBA GDB stub 抓一帧，并在本地把 VRAM 合成成 PNG。

为什么自己渲染：mGBA 的 GUI 截图无法在无人交互下触发；VRAM/PAL/OAM/IO 全都能
从 GDB 读到，自己合成 = 完全可控、可重复、可附带内存账本。

用法：
    python scripts/gdb_shot.py --out .tmp/shot.png [--wait 4] [--state FILE]
                              [--exe qt|sdl] [--win 0x0202E658 ...]

前提：必须在**脱离沙箱**的环境下运行（沙箱禁止 mGBA 绑定 2345 端口）。
Qt 版（mGBA.exe）可用；SDL 版 -g 实测不开端口。
"""
from __future__ import annotations

import argparse
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools" / "mGBA-0.10.5-win32"
EXES = {"qt": BASE / "mGBA.exe", "sdl": BASE / "mgba-sdl.exe"}
PORT = 2345

# ---- GBA 内存图 ----------------------------------------------------------
A_IO = 0x04000000
A_PAL = 0x05000000
A_VRAM = 0x06000000
A_OAM = 0x07000000


class RSP:
    """GDB Remote Serial Protocol 最小客户端（够 mGBA 用）。"""

    def __init__(self, host="127.0.0.1", port=PORT, timeout=20.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        # mGBA 0.10.5 stub 对单包长度敏感：0x400 会超时，0x40 实测稳定。
        self.chunk = 0x40

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _send(self, payload: bytes):
        csum = sum(payload) & 0xFF
        self.sock.sendall(b"$" + payload + b"#%02X" % csum)

    def recv_packet(self) -> bytes:
        buf = bytearray()
        # 跳到 '$'（顺手吞掉 ACK/NAK 与主动上报包）
        while True:
            c = self.sock.recv(1)
            if not c:
                raise RuntimeError("socket closed")
            if c == b"$":
                break
        while True:
            c = self.sock.recv(1)
            if not c:
                raise RuntimeError("socket closed")
            if c == b"#":
                break
            buf += c
        self.sock.recv(2)          # checksum
        self.sock.sendall(b"+")    # ACK
        return bytes(buf)

    def cmd(self, payload: bytes) -> bytes:
        self._send(payload)
        return self.recv_packet()

    def drain(self, t=0.4):
        """吃掉 stub 主动发的包（连接后必有一条 stop reply）。"""
        old = self.sock.gettimeout()
        self.sock.settimeout(t)
        try:
            while True:
                self.recv_packet()
        except (socket.timeout, TimeoutError):
            pass
        except OSError:
            pass
        finally:
            self.sock.settimeout(old)

    def cont(self):
        self._send(b"c")

    def interrupt(self) -> bytes:
        self.sock.sendall(b"\x03")
        return self.recv_packet()

    def read_regs(self) -> dict[str, int]:
        r = self.cmd(b"g")
        if r.startswith(b"E"):
            raise RuntimeError("regs failed")
        h = r.decode()
        return {f"r{i}": struct.unpack("<I", bytes.fromhex(h[i * 8:i * 8 + 8]))[0]
                for i in range(16)}

    def read_mem(self, addr: int, size: int) -> bytes:
        out = bytearray()
        off = 0
        guard = 0
        while off < size:
            guard += 1
            if guard > 100000:
                raise RuntimeError("read_mem 死循环")
            n = min(self.chunk, size - off)
            try:
                resp = self.cmd(b"m%x,%x" % (addr + off, n))
            except Exception:
                if self.chunk > 0x40:
                    self.chunk = 0x40
                    continue
                raise
            if resp.startswith(b"E"):
                if self.chunk > 0x40:
                    self.chunk = 0x40
                    continue
                raise RuntimeError(f"read 0x{addr + off:X} 失败: {resp}")
            out += bytes.fromhex(resp.decode())
            off += n
        return bytes(out)


# ---- 渲染器 --------------------------------------------------------------
def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8)


def bgr555_to_rgb(v: int) -> tuple[int, int, int]:
    r = (v & 0x1F) << 3
    g = ((v >> 5) & 0x1F) << 3
    bl = ((v >> 10) & 0x1F) << 3
    return (r | r >> 5, g | g >> 5, bl | bl >> 5)


SIZES_TEXT = [(256, 256), (512, 256), (256, 512), (512, 512)]
OBJ_SIZES = {
    0: [(8, 8), (16, 16), (32, 32), (64, 64)],
    1: [(16, 8), (32, 8), (32, 16), (64, 32)],
    2: [(8, 16), (8, 32), (16, 32), (32, 64)],
}


class Screen:
    def __init__(self, vram: bytes, pal: bytes, oam: bytes, io: bytes):
        self.vram = vram
        self.pal = pal
        self.oam = oam
        self.io = io
        self.dispcnt = u16(io, 0x00)
        self.blank = (self.dispcnt & 0x80) != 0
        self.mode = self.dispcnt & 7
        self.bgcnt = [u16(io, 0x08 + 2 * i) for i in range(4)]
        self.hoff = [u16(io, 0x10 + 4 * i) for i in range(4)]
        self.voff = [u16(io, 0x12 + 4 * i) for i in range(4)]
        self.prio_buf: list[tuple[int, int]] = []   # (prio, layer_id)

    # --- 调色板 ---
    def col_bg(self, idx: int):
        if idx == 0:
            return None
        o = idx * 2
        if o + 1 >= len(self.pal):
            return None
        return bgr555_to_rgb(u16(self.pal, o))

    def col_obj(self, idx: int):
        if idx == 0:
            return None
        o = 0x200 + idx * 2
        if o + 1 >= len(self.pal):
            return None
        return bgr555_to_rgb(u16(self.pal, o))

    def is_affine_bg(self, i: int) -> bool:
        return (self.mode == 1 and i == 2) or (self.mode == 2 and i in (2, 3))

    def render(self):
        w, h = 240, 160
        px = [(0, 0, 0)] * (w * h)
        if self.blank:
            return px

        layers = []   # (prio, kind, index)
        for i in range(4):
            if (self.dispcnt >> (8 + i)) & 1:
                layers.append((self.bgcnt[i] & 3, "bg", i))
        if (self.dispcnt >> 12) & 1:
            for j in range(4):
                layers.append((j, "obj", j))
        layers.sort(key=lambda t: t[0])

        for prio, kind, idx in layers:
            if kind == "bg":
                self._render_bg(idx, px, w, h)
            else:
                self._render_obj_prio(idx, px, w, h)
        return px

    def _bg_pixel(self, i: int, x: int, y: int):
        cnt = self.bgcnt[i]
        char_base = ((cnt >> 2) & 3) * 0x4000
        screen_base = ((cnt >> 8) & 0x1F) * 0x800
        size = (cnt >> 14) & 3
        bpp8 = (cnt >> 7) & 1
        bw, bh = SIZES_TEXT[size]
        sx = (x + self.hoff[i]) % bw
        sy = (y + self.voff[i]) % bh
        tm_x, tm_y = sx >> 3, sy >> 3
        blocks_per_row = bw // 256
        sb = (tm_y >> 5) * blocks_per_row + (tm_x >> 5)
        addr = screen_base + sb * 0x800 + ((tm_y & 31) * 32 + (tm_x & 31)) * 2
        if addr + 1 >= len(self.vram):
            return None
        entry = u16(self.vram, addr)
        tile = entry & 0x3FF
        if entry & 0x400:
            fx = 7 - (sx & 7)
        else:
            fx = sx & 7
        if entry & 0x800:
            fy = 7 - (sy & 7)
        else:
            fy = sy & 7
        if bpp8:
            a = char_base + tile * 64 + fy * 8 + fx
            if a >= len(self.vram):
                return None
            return self.col_bg(self.vram[a])
        a = char_base + tile * 32 + fy * 4 + (fx >> 1)
        if a >= len(self.vram):
            return None
        byte = self.vram[a]
        ci = (byte >> 4) if (fx & 1) == 0 else (byte & 0xF)
        if ci == 0:
            return None
        return self.col_bg(((entry >> 12) & 0xF) * 16 + ci)

    def _render_bg(self, i: int, px, w, h):
        if self.is_affine_bg(i):
            self._render_bg_affine(i, px, w, h)
            return
        for y in range(h):
            for x in range(w):
                c = self._bg_pixel(i, x, y)
                if c is not None:
                    px[y * w + x] = c

    def _render_bg_affine(self, i: int, px, w, h):
        cnt = self.bgcnt[i]
        char_base = ((cnt >> 2) & 3) * 0x4000
        screen_base = ((cnt >> 8) & 0x1F) * 0x800
        size = (cnt >> 14) & 3
        bpp8 = (cnt >> 7) & 1
        dim = 128 << size            # 128/256/512/1024
        o = 0x20 + (i - 2) * 16
        pa = struct.unpack("<h", self.io[o:o + 2])[0]
        pb = struct.unpack("<h", self.io[o + 2:o + 4])[0]
        pc = struct.unpack("<h", self.io[o + 4:o + 6])[0]
        pd = struct.unpack("<h", self.io[o + 6:o + 8])[0]
        rx = struct.unpack("<i", self.io[o + 8:o + 12])[0] >> 8
        ry = struct.unpack("<i", self.io[o + 12:o + 16])[0] >> 8
        cx, cy = 120, 80
        for y in range(h):
            for x in range(w):
                dx, dy = x - cx, y - cy
                ux = (rx + pa * dx + pb * dy) >> 8
                uy = (ry + pc * dx + pd * dy) >> 8
                if not (0 <= ux < dim and 0 <= uy < dim):
                    continue
                ma = screen_base + ((uy >> 3) * (dim >> 3) + (ux >> 3))
                if ma >= len(self.vram):
                    continue
                tile = self.vram[ma]
                fx, fy = ux & 7, uy & 7
                if bpp8:
                    a = char_base + tile * 64 + fy * 8 + fx
                    if a < len(self.vram):
                        c = self.col_bg(self.vram[a])
                        if c is not None:
                            px[y * w + x] = c
                else:
                    a = char_base + tile * 32 + fy * 4 + (fx >> 1)
                    if a < len(self.vram):
                        byte = self.vram[a]
                        ci = (byte >> 4) if (fx & 1) == 0 else (byte & 0xF)
                        if ci:
                            c = self.col_bg(ci)
                            if c is not None:
                                px[y * w + x] = c

    def _render_obj_prio(self, want_prio: int, px, w, h):
        """按 1D 映射渲染普通（非仿射）OBJ。"""
        bpp8 = (self.dispcnt >> 6) & 1        # OBJ 1D 映射在 bit6? 实际 bit6=OBJ 字符映射
        one_d = (self.dispcnt >> 6) & 1
        for i in range(128):
            o = i * 8
            if o + 7 >= len(self.oam):
                break
            a0 = u16(self.oam, o)
            a1 = u16(self.oam, o + 2)
            a2 = u16(self.oam, o + 4)
            if a0 & 1:
                continue
            if ((a0 >> 8) & 1):
                continue                       # 仿射 OBJ 暂不渲染
            if ((a0 >> 9) & 1):
                continue                       # 双倍尺寸/禁用
            if ((a0 >> 10) & 3) == 2:
                continue                       # 隐藏
            if ((a2 >> 10) & 3) != want_prio:
                continue
            shape = (a0 >> 14) & 3
            size = (a1 >> 14) & 3
            if shape == 3:
                continue
            ow, oh = OBJ_SIZES[shape][size]
            ox = a1 & 0x1FF
            if ox >= 256:
                ox -= 512
            oy = a0 & 0xFF
            if oy >= 160:
                oy -= 256
            hf = (a1 >> 12) & 1
            vf = (a1 >> 13) & 1
            c256 = (a0 >> 13) & 1
            tile = a2 & 0x3FF
            palbank = (a2 >> 12) & 0xF
            for yy in range(oh):
                sy = oy + yy
                if not (0 <= sy < 160):
                    continue
                ty = (oh - 1 - yy) if vf else yy
                for xx in range(ow):
                    sx = ox + xx
                    if not (0 <= sx < 240):
                        continue
                    tx = (ow - 1 - xx) if hf else xx
                    if c256:
                        if one_d:
                            t = tile + (ty // 8) * (ow // 8) + (tx // 8)
                        else:
                            t = tile + (ty // 8) * 32 + (tx // 8)
                        a = t * 64 + (ty & 7) * 8 + (tx & 7)
                        if a >= len(self.vram):
                            continue
                        c = self.col_obj(self.vram[a])
                    else:
                        if one_d:
                            t = tile + (ty // 8) * (ow // 8) * 2 + (tx // 8) * 2
                        else:
                            t = tile + (ty // 8) * 32 + (tx // 8) * 2
                        fx = tx & 7
                        a = t * 32 + (ty & 7) * 4 + (fx >> 1)
                        if a >= len(self.vram):
                            continue
                        byte = self.vram[a]
                        ci = (byte >> 4) if (fx & 1) == 0 else (byte & 0xF)
                        if ci == 0:
                            continue
                        c = self.col_obj(palbank * 16 + ci)
                    if c is not None:
                        px[sy * 240 + sx] = c


def save_png(px, path: Path):
    from PIL import Image
    img = Image.new("RGB", (240, 160))
    img.putdata(px)
    img = img.resize((720, 480), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"截图 -> {path}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".tmp/shot.png")
    ap.add_argument("--wait", type=float, default=4.0)
    ap.add_argument("--state", default=None)
    ap.add_argument("--exe", default="qt", choices=["qt", "sdl"])
    ap.add_argument("--rom", default=str(ROOT / "roms" / "outputs" /
                                        "POKEMON_RUBY_AXVJ00_translated.gba"))
    ap.add_argument("--win", action="append", default=[])
    ap.add_argument("--no-cont", action="store_true",
                    help="不 continue（savestate 直读）。cont 之后 mGBA 只响应"
                         "一次内存读，故默认配 --state 使用")
    ap.add_argument("--dump", default=None, help="把 VRAM/PAL/OAM 存到该目录前缀")
    args = ap.parse_args()

    cmd = [str(EXES[args.exe]), "-g", "-1"]
    if args.state:
        cmd += ["-t", args.state]
    cmd.append(args.rom)
    print("启动:", " ".join(cmd), flush=True)
    log = ROOT / ".tmp" / "gdb_shot_emu.out"
    fo = open(log, "wb")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                            stdout=fo, stderr=fo, close_fds=True)

    g = None
    try:
        for i in range(40):
            if proc.poll() is not None:
                print(f"模拟器提前退出 rc={proc.returncode}", flush=True)
                return 1
            try:
                g = RSP()
                break
            except OSError:
                time.sleep(0.5)
        if g is None:
            print("stub 未就绪", flush=True)
            return 1
        print("stub 已连上，drain 初始包", flush=True)
        g.drain()
        if args.no_cont:
            print("跳过 continue（savestate 直读模式）", flush=True)
        else:
            g.cont()
            time.sleep(args.wait)
            print("interrupt:", g.interrupt()[:40], flush=True)

        regs = g.read_regs()
        print(f"PC=0x{regs['r15']:08X} LR=0x{regs['r14']:08X} "
              f"sp=0x{regs['r13']:08X}", flush=True)

        io = g.read_mem(A_IO, 0x60)
        pal = g.read_mem(A_PAL, 1024)   # 512 BG + 512 OBJ
        vram = g.read_mem(A_VRAM, 0x18000)     # 96 KB
        oam = g.read_mem(A_OAM, 0x400)
        print(f"读到 IO {len(io)} / PAL {len(pal)} / VRAM {len(vram)} / "
              f"OAM {len(oam)}", flush=True)

        if args.dump:
            pre = Path(args.dump)
            pre.parent.mkdir(parents=True, exist_ok=True)
            Path(str(pre) + "_vram.bin").write_bytes(vram)
            Path(str(pre) + "_pal.bin").write_bytes(pal)
            Path(str(pre) + "_oam.bin").write_bytes(oam)
            Path(str(pre) + "_io.bin").write_bytes(io)
            print(f"原始内存 dump -> {pre}_*.bin", flush=True)

        screen = Screen(vram, pal, oam, io)
        print(f"DISPCNT=0x{screen.dispcnt:04X} mode={screen.mode} "
              f"blank={screen.blank}", flush=True)
        for i in range(4):
            c = screen.bgcnt[i]
            print(f"  BG{i}: cnt=0x{c:04X} prio={c & 3} "
                  f"charBase=0x{((c >> 2) & 3) * 0x4000:05X} "
                  f"screenBase=0x{((c >> 8) & 0x1F) * 0x800:05X} "
                  f"size={(c >> 14) & 3} {'8bpp' if c & 0x80 else '4bpp'} "
                  f"en={(screen.dispcnt >> (8 + i)) & 1} "
                  f"hofs={screen.hoff[i]} vofs={screen.voff[i]}", flush=True)

        px = screen.render()
        save_png(px, ROOT / args.out)

        for spec in args.win:
            addr = int(spec, 16)
            wb = g.read_mem(addr, 0x20)
            tpl = struct.unpack("<I", wb[0:4])[0]
            print(f"win=0x{addr:08X} tpl=0x{tpl:08X} "
                  f"mode={wb[9] if tpl else '?'} "
                  f"TILE_BASE=0x{u16(wb, 0x16):04X} "
                  f"TILE_OFF=0x{u16(wb, 0x18):04X} "
                  f"curX={wb[0x1A]} curTX={wb[0x1B]} "
                  f"curY={wb[0x1C]} curTY={wb[0x1D]} "
                  f"font={wb[0x0B]} txtId={u16(wb, 0x14)}", flush=True)
        return 0
    finally:
        if g:
            g.close()
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        fo.close()


if __name__ == "__main__":
    raise SystemExit(main())
