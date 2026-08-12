#!/usr/bin/env python3
"""多实例拼接读调色板 RAM（mGBA stub 每连接 2 次读 × 0x80 的限制）。

每个实例: 启动 → cont → sleep → interrupt → 读 2×0x80=256B → 关闭。
N 个实例拼接出完整区域（调色板 512B = 2 实例）。
用法: python _pal_dump.py <wait_s> <out_prefix> [--region 0x05000000] [--instances N]
"""
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gba_gdb import RSP  # noqa: E402

MGBA = Path(r"C:\code\GBA-Rom-Translator\tools\mGBA-0.10.5-win32\mgba.exe")
OUT = Path(r"C:\code\GBA-Rom-Translator\work\gba_dump")
ROM = Path(r"C:\code\GBA-Rom-Translator\roms\origin\POKEMON_RUBY_AXVJ00.gba")


def instance_read(wait_s: float, addr: int, size: int) -> bytes | None:
    """一个实例读一段内存（mGBA stub 每连接累计读取上限 0x80=128B）。"""
    proc = subprocess.Popen([str(MGBA), "-g", str(ROM)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        r = None
        for _ in range(50):
            try:
                r = RSP()
                break
            except OSError:
                time.sleep(0.2)
        if r is None:
            return None
        r.cont()
        time.sleep(wait_s)
        try:
            r.interrupt()
        except Exception:
            return None
        try:
            return r.read_mem(addr, min(size, 0x80))
        except Exception:
            return None
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
        time.sleep(1.0)


def main():
    wait = float(sys.argv[1])
    prefix = sys.argv[2]
    region = 0x05000000
    instances = 4
    args = sys.argv[3:]
    if "--region" in args:
        region = int(args[args.index("--region") + 1], 16)
    if "--instances" in args:
        instances = int(args[args.index("--instances") + 1])

    total = 0x80 * instances
    data = bytearray()
    ok = 0
    for i in range(instances):
        d = None
        for attempt in range(3):
            d = instance_read(wait, region + i * 0x80, 0x80)
            if d:
                break
            print(f"实例{i} 重试{attempt+1}", flush=True)
        if d:
            data += d
            ok += 1
            print(f"实例{i}: OK (0x{region + i*0x80:08X})", flush=True)
        else:
            print(f"实例{i}: FAIL", flush=True)
    if ok:
        f = OUT / f"{prefix}.bin"
        f.write_bytes(bytes(data[:total]))
        print(f"已保存 {len(data[:total])}B -> {f}")
        # 调色板区域打印 bank
        if region == 0x05000000:
            pal = bytes(data[:512])
            for b in range(16):
                bank = pal[b * 32 : (b + 1) * 32]
                nz = sum(1 for k in range(0, 32, 2) if struct.unpack("<H", bank[k : k + 2])[0])
                print(f"bank {b:2d}: {nz:2d}/16 色  {bank[:16].hex()}")


if __name__ == "__main__":
    main()
