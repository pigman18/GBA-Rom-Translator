#!/usr/bin/env python3
"""mGBA GDB stub 客户端：无头动态分析用。

用法:
  python _gba_gdb.py dump <rom> [--wait N] [--addr ADDR=SIZE ...]
    - 启动 mgba-sdl -g（无头 stub），等 N 秒让游戏跑到目标画面，
      interrupt 后 dump 指定内存区（默认 0x05000000 调色板 RAM 512B、
      0x04000000 DISPCNT、0x06000000 VRAM 16KB）
"""
import argparse
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

MGBA_SDL = Path(r"C:\code\GBA-Rom-Translator\tools\mGBA-0.10.5-win32\mgba-sdl.exe")
PORT = 2345


class RSP:
    def __init__(self, host="127.0.0.1", port=PORT):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(10)

    def _send(self, payload: bytes):
        csum = sum(payload) & 0xFF
        pkt = b"$" + payload + b"#%02X" % csum
        self.sock.sendall(pkt)

    def _recv_packet(self) -> bytes:
        while True:
            b = self.sock.recv(1)
            if b == b"+":
                continue
            if b == b"-":
                raise RuntimeError("target NAK")
            if b != b"$":
                continue
            buf = bytearray()
            while True:
                c = self.sock.recv(1)
                if c == b"#":
                    break
                buf += c
            ck = self.sock.recv(2)
            # GDB RSP 双向 ack：收包后回 '+'，否则目标对后续包 NAK
            try:
                self.sock.sendall(b"+")
            except OSError:
                pass
            return bytes(buf)

    def exec(self, payload: bytes) -> bytes:
        self._send(payload)
        return self._recv_packet()

    def read_mem(self, addr: int, size: int, chunk: int = 0x40) -> bytes:
        """分段读内存（mGBA 0.10.5 stub 单包上限约 0x40，超限返回 E06/NAK）。"""
        out = bytearray()
        for off in range(0, size, chunk):
            n = min(chunk, size - off)
            resp = self.exec(b"m%x,%x" % (addr + off, n))
            if resp.startswith(b"E"):
                raise RuntimeError(f"read_mem 0x{addr + off:X} failed: {resp}")
            out += bytes.fromhex(resp.decode())
        return bytes(out)

    def write_mem(self, addr: int, data: bytes):
        resp = self.exec(b"M%x,%x:%s" % (addr, len(data), data.hex()))
        if resp != b"OK":
            raise RuntimeError(f"write_mem 0x{addr:X} failed: {resp}")

    def cont(self):
        self._send(b"c")
        # continue 不等待响应

    def interrupt(self):
        self.sock.sendall(b"\x03")
        return self._recv_packet()

    def step(self):
        return self.exec(b"s")

    def regs(self) -> dict:
        resp = self.exec(b"g")
        if resp.startswith(b"E"):
            raise RuntimeError("regs failed")
        hexs = resp.decode()
        # ARM GDB: 16 GPR (4B) + 6 status (4B) = 22 regs
        out = {}
        for i in range(16):
            out[f"r{i}"] = struct.unpack("<I", bytes.fromhex(hexs[i * 8 : i * 8 + 8]))[0]
        return out

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def start_emu(rom: Path, gdb_port: int = PORT):
    env = dict(os.environ)
    proc = subprocess.Popen(
        [str(MGBA_SDL), "-g", str(rom)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    # 等待 stub 就绪
    for _ in range(50):
        try:
            r = RSP(port=gdb_port)
            r.close()
            return proc
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("mGBA GDB stub 未就绪")


def dump_mem(rom: Path, wait_s: float, regions: list[tuple[int, int]]) -> dict:
    proc = start_emu(rom)
    try:
        r = RSP()
        # 游戏初始暂停于 GDB stub；先继续跑
        r.cont()
        time.sleep(wait_s)
        stop = r.interrupt()
        print(f"interrupt: {stop}")
        out = {}
        for addr, size in regions:
            out[addr] = r.read_mem(addr, size)
            print(f"读 0x{addr:08X} {size} bytes OK")
        return out
    finally:
        try:
            proc.terminate()
        except OSError:
            pass


def fmt_gba555(data: bytes) -> str:
    vals = []
    for i in range(0, len(data), 2):
        v = struct.unpack("<H", data[i : i + 2])[0]
        vals.append(f"0x{v:04X}")
    return " ".join(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--wait", type=float, default=6.0)
    ap.add_argument("--addr", action="append", default=[])
    ap.add_argument("--out", default=None, help="输出文件前缀")
    args = ap.parse_args()

    regions = []
    for spec in args.addr:
        a, s = spec.split("=")
        regions.append((int(a, 16), int(s)))
    if not regions:
        regions = [
            (0x04000000, 4),   # DISPCNT
            (0x05000000, 512),  # 调色板 RAM (16 bank × 32B)
            (0x06000000, 0x4000),  # VRAM 前 16KB
        ]
    mem = dump_mem(Path(args.rom), args.wait, regions)

    out = args.out or "work/gba_dump"
    Path(out).mkdir(parents=True, exist_ok=True)
    for addr, data in mem.items():
        Path(f"{out}/mem_{addr:08X}.bin").write_bytes(data)
    # 打印调色板 RAM 各 bank
    if 0x05000000 in mem:
        pal = mem[0x05000000]
        for b in range(len(pal) // 32):
            bank = pal[b * 32 : b * 32 + 32]
            nz = sum(1 for i in range(0, 32, 2) if struct.unpack("<H", bank[i : i + 2])[0])
            print(f"bank {b:2d}: {nz:2d}/16 非零色  {fmt_gba555(bank[:16])}")
    print("DISPCNT:", hex(struct.unpack("<I", mem.get(0x04000000, b"\x00" * 4))[0]))
    print(f"输出目录: {out}")


if __name__ == "__main__":
    main()
