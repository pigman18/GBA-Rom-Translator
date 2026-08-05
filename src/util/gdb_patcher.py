#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gdb_patcher.py
==============
汉化 ROM 崩溃排查：坏指针值 <-> 存放槽地址；连 mGBA GDB 抓现场。

不做 jump 到非法地址。不改 ROM、不代开模拟器。

用法：
  # 崩后已 Pause：直接读现场（会识别 Thumb 近邻 F909F6A5/A6）
  python gdb_patcher.py listen 0xF909F6A4 --gdb 127.0.0.1:2345 --now

  # 可选：强制把 PC 跳到坏地址再炸一次（不能代替找注入源）
  python gdb_patcher.py goto 0xF909F6A4 --gdb 127.0.0.1:2345

  python gdb_patcher.py find 0xF909F6A4 --rom path\\to\\zh.gba --origin path\\to\\origin.gba
  python gdb_patcher.py regs --gdb
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

BASE = 0x08000000
DEFAULT_GDB = "127.0.0.1:2345"

# GBA ARM 寄存器在 g 包中的常见布局（mGBA）：r0-r15 + cpsr，各 4 字节 LE
REG_NAMES = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "cpsr",
]


# ---------------------------------------------------------------------------
# 地址 / 扫描
# ---------------------------------------------------------------------------


def parse_u32(text: str) -> int:
    s = text.strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16) & 0xFFFFFFFF
    return int(s, 16) & 0xFFFFFFFF


def to_gba_ptr(file_off: int) -> int:
    return (BASE + file_off) & 0xFFFFFFFF


def looks_like_rom_ptr(word: int) -> bool:
    hi = (word >> 24) & 0xFF
    return hi in (0x08, 0x09)


def scan_bytes_for_word(
    data: bytes,
    value: int,
    *,
    base_addr: int = 0,
    unaligned: bool = False,
) -> List[int]:
    """返回命中的绝对地址列表。"""
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    step = 1 if unaligned else 4
    hits: List[int] = []
    lim = len(data) - 4
    off = 0
    while off <= lim:
        if data[off : off + 4] == needle:
            hits.append((base_addr + off) & 0xFFFFFFFF)
        off += step
    return hits


def scan_rom_for_word(
    data: bytes,
    value: int,
    *,
    unaligned: bool = False,
) -> List[int]:
    """返回 file offset 列表。"""
    return [
        h - BASE
        for h in scan_bytes_for_word(data, value, base_addr=BASE, unaligned=unaligned)
        if h >= BASE
    ]


def filter_hits_with_origin(
    hits: List[int],
    value: int,
    origin: bytes,
    *,
    keep_same: bool = False,
    origin_ptr_only: bool = True,
) -> List[int]:
    out: List[int] = []
    for off in hits:
        if off + 4 > len(origin):
            continue
        ow = struct.unpack_from("<I", origin, off)[0]
        if not keep_same and ow == (value & 0xFFFFFFFF):
            continue
        if origin_ptr_only and not looks_like_rom_ptr(ow):
            continue
        out.append(off)
    return out


def load_build_index(
    path: Path,
) -> Tuple[dict, dict, List[Tuple[int, int, dict]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_addr: dict[int, list] = {}
    by_ps: dict[int, list] = {}
    ranges: List[Tuple[int, int, dict]] = []

    def summary(e: dict) -> dict:
        return {
            "id": e.get("id"),
            "type": e.get("type"),
            "module": e.get("module"),
            "address": e.get("address"),
            "translated": (e.get("translated") or "")[:40],
        }

    for e in data.get("entries") or []:
        raw_a = e.get("address")
        try:
            a = parse_u32(str(raw_a)) if raw_a is not None else None
        except ValueError:
            a = None
        sm = summary(e)
        if a is not None:
            by_addr.setdefault(a & 0xFFFFFFFF, []).append(sm)
            bl = int(e.get("byte_length") or 0)
            if bl > 0:
                ranges.append((a & 0xFFFFFFFF, (a + bl) & 0xFFFFFFFF, sm))
        for src in e.get("pointer_sources") or []:
            if isinstance(src, dict):
                raw = src.get("address") or src.get("addr") or src.get("offset")
            else:
                raw = src
            if raw is None:
                continue
            try:
                sa = parse_u32(str(raw))
            except ValueError:
                continue
            by_ps.setdefault(sa & 0xFFFFFFFF, []).append(sm)
    return by_addr, by_ps, ranges


def match_build(
    gba_addr: int,
    by_addr: dict,
    by_ps: dict,
    ranges: Optional[List[Tuple[int, int, dict]]] = None,
) -> List[dict]:
    a = gba_addr & 0xFFFFFFFF
    seen = set()
    out: List[dict] = []

    def add(sm: dict) -> None:
        key = (sm.get("id"), sm.get("type"), sm.get("address"))
        if key in seen:
            return
        seen.add(key)
        out.append(sm)

    for sm in by_addr.get(a) or []:
        add(sm)
    for sm in by_ps.get(a) or []:
        add(sm)
    if ranges:
        for lo, hi, sm in ranges:
            if lo <= a < hi:
                add(sm)
    return out


# ---------------------------------------------------------------------------
# 最小 GDB Remote Serial Protocol 客户端（mGBA stub）
# ---------------------------------------------------------------------------


class GdbError(RuntimeError):
    pass


class GdbClient:
    """mGBA GDB stub 客户端。默认保持 ACK（不用 QStartNoAckMode）。"""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self._buf = bytearray()
        self._no_ack = False

    def connect(self) -> None:
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise GdbError(
                f"无法连接 GDB {self.host}:{self.port} ({e}). "
                "请先在 mGBA 打开 ROM，再 Tools -> Start GDB Server（默认 2345）。"
            ) from e
        self.sock.settimeout(self.timeout)
        self._buf.clear()
        self._no_ack = False
        try:
            self.cmd("qSupported:swbreak+;hwbreak+")
        except GdbError:
            pass
        try:
            why = self.cmd("?")
            print(f"GDB 已连接，停因={why}")
        except GdbError as e:
            print(f"警告: '?' 失败 ({e})，继续尝试")

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def __enter__(self) -> "GdbClient":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _checksum(self, data: bytes) -> int:
        return sum(data) & 0xFF

    def _fill(self, min_bytes: int = 1) -> None:
        assert self.sock
        while len(self._buf) < min_bytes:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise GdbError(
                    "GDB 连接已断开。"
                    "常见原因：mGBA 停了 GDB Server、模拟器崩溃、"
                    "或对该地址的 watch 不被支持。"
                    "请改用: python gdb_patcher.py listen <坏值> --gdb ..."
                )
            self._buf.extend(chunk)

    def _recv_byte(self) -> int:
        self._fill(1)
        return self._buf.pop(0)

    def _send_packet(self, payload: str) -> None:
        if not self.sock:
            raise GdbError("未连接")
        body = payload.encode("ascii")
        pkt = b"$" + body + b"#" + f"{self._checksum(body):02x}".encode("ascii")
        self.sock.sendall(pkt)
        if not self._no_ack:
            b = self._recv_byte()
            if b == ord("+"):
                return
            if b == ord("-"):
                self.sock.sendall(pkt)
                b2 = self._recv_byte()
                if b2 == ord("+"):
                    return
                if b2 == ord("$"):
                    self._buf.insert(0, b2)
                    return
                raise GdbError(f"GDB 未 ACK，收到 {bytes([b2])!r}")
            if b == ord("$"):
                self._buf.insert(0, b)
                return
            raise GdbError(f"GDB 未 ACK，收到 {bytes([b])!r}")

    def _recv_packet(self) -> str:
        while True:
            b = self._recv_byte()
            if b == ord("$"):
                break
            if b in (ord("+"), ord("-")):
                continue
        data = bytearray()
        while True:
            b = self._recv_byte()
            if b == ord("#"):
                break
            data.append(b)
        c0 = self._recv_byte()
        c1 = self._recv_byte()
        csum = bytes([c0, c1])
        expect = f"{self._checksum(bytes(data)):02x}".encode("ascii")
        if csum.lower() != expect.lower():
            if self.sock and not self._no_ack:
                self.sock.sendall(b"-")
            raise GdbError(f"校验和错误: got {csum!r} expect {expect!r}")
        if self.sock and not self._no_ack:
            self.sock.sendall(b"+")
        return data.decode("ascii", errors="replace")

    def cmd(self, payload: str) -> str:
        self._send_packet(payload)
        return self._recv_packet()

    def read_regs(self) -> dict[str, int]:
        raw = self.cmd("g")
        if raw.startswith("E") or not raw:
            raise GdbError(f"读寄存器失败: {raw}")
        out: dict[str, int] = {}
        for i, name in enumerate(REG_NAMES):
            start = i * 8
            chunk = raw[start : start + 8]
            if len(chunk) < 8:
                break
            out[name] = int.from_bytes(bytes.fromhex(chunk), "little")
        return out

    def read_mem(self, addr: int, length: int) -> bytes:
        raw = self.cmd(f"m{addr:x},{length:x}")
        if raw.startswith("E") or not raw:
            raise GdbError(f"读内存失败 @0x{addr:08X}: {raw}")
        try:
            return bytes.fromhex(raw)
        except ValueError as e:
            raise GdbError(f"内存 hex 解析失败: {raw[:64]}") from e

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read_mem(addr, 4))[0]

    def write_reg(self, reg_index: int, value: int) -> None:
        """P 包写寄存器；value 按 LE hex（与 g 包一致）。"""
        le = struct.pack("<I", value & 0xFFFFFFFF).hex()
        resp = self.cmd(f"P{reg_index:x}={le}")
        if resp not in ("OK", ""):
            # 部分 stub 回空也算成功
            if resp.startswith("E"):
                raise GdbError(f"写寄存器 r{reg_index} 失败: {resp}")

    def write_pc(self, addr: int, *, thumb: Optional[bool] = None) -> None:
        """设置 PC。thumb=True 时置 bit0；None 时若 addr 偶数则保持 ARM。"""
        a = addr & 0xFFFFFFFF
        if thumb is True:
            a |= 1
        elif thumb is False:
            a &= ~1
        self.write_reg(15, a)

    def set_watch(self, kind: int, addr: int, size: int = 4) -> None:
        """Z2=write Z3=read Z4=access。"""
        resp = self.cmd(f"Z{kind},{addr:x},{size}")
        if resp != "OK":
            raise GdbError(f"断点失败 (Z{kind} @0x{addr:08X}): {resp!r}")

    def clear_watch(self, kind: int, addr: int, size: int = 4) -> None:
        try:
            self.cmd(f"z{kind},{addr:x},{size}")
        except GdbError:
            pass

    def set_write_watch(self, addr: int, size: int = 4) -> None:
        self.set_watch(2, addr, size)

    def clear_write_watch(self, addr: int, size: int = 4) -> None:
        self.clear_watch(2, addr, size)

    def continue_and_wait(self, timeout: Optional[float] = None) -> str:
        """发送 continue。mGBA 对 'c' 不立即回包，直到下次停下。"""
        assert self.sock
        old = self.sock.gettimeout()
        self.sock.settimeout(self.timeout)
        try:
            self._send_packet("c")
        except GdbError:
            self.sock.settimeout(old)
            raise
        self.sock.settimeout(timeout if timeout is not None else 3600.0)
        try:
            return self._recv_packet()
        except socket.timeout as e:
            raise GdbError(
                f"等待停下超时（{timeout}s）。"
                "请在 mGBA 复现，或加大 --timeout；"
                "也可先手动 Pause 再: listen ... --now"
            ) from e
        finally:
            self.sock.settimeout(old)


def parse_gdb_hostport(s: str) -> Tuple[str, int]:
    s = (s or DEFAULT_GDB).strip()
    if ":" in s:
        host, port_s = s.rsplit(":", 1)
        return host or "127.0.0.1", int(port_s)
    return "127.0.0.1", int(s)


def related_values(value: int) -> List[int]:
    """坏指针常带 Thumb bit / ±1±2，精确相等会漏报。"""
    v = value & 0xFFFFFFFF
    base = v & ~1
    cands = {v, base, base | 1, base + 1, base + 2, base - 1, base - 2, v ^ 1}
    return sorted(x & 0xFFFFFFFF for x in cands)


def classify_reg_hit(reg_val: int, value: int) -> Optional[str]:
    rv = reg_val & 0xFFFFFFFF
    v = value & 0xFFFFFFFF
    base = v & ~1
    if rv == v:
        return "exact"
    if rv == (base | 1):
        return "thumb(+1)"
    if rv == (base + 2) or rv == ((base | 1) + 1):
        return "lr-ish(+2)"
    if rv in related_values(v):
        return "near"
    return None


def format_regs(regs: dict[str, int], highlight: Optional[int] = None) -> str:
    lines = []
    for name in REG_NAMES:
        if name not in regs:
            continue
        v = regs[name]
        mark = ""
        if highlight is not None:
            kind = classify_reg_hit(v, highlight)
            if kind:
                mark = f"  <== {kind}"
        lines.append(f"  {name:>4}: {v:08X}{mark}")
    return "\n".join(lines)


def dump_code_words(client: GdbClient, pc: int, count: int = 4) -> str:
    base = pc & ~1
    lines = []
    try:
        raw = client.read_mem(base, count * 4)
    except GdbError as e:
        return f"  (无法读代码: {e})"
    for i in range(count):
        off = i * 4
        if off + 4 > len(raw):
            break
        w = struct.unpack_from("<I", raw, off)[0]
        lines.append(f"  {base + off:08X}:  {w:08X}")
    return "\n".join(lines)


def scan_ram_for_value(
    client: GdbClient,
    value: int,
    *,
    unaligned: bool = False,
    limit: int = 50,
    also_related: bool = True,
) -> List[Tuple[str, int, int]]:
    """(region, addr, word_found)。"""
    targets = related_values(value) if also_related else [value & 0xFFFFFFFF]
    needle_regions = [
        ("EWRAM", 0x02000000, 0x40000),
        ("IWRAM", 0x03000000, 0x8000),
    ]
    found: List[Tuple[str, int, int]] = []
    seen_addr = set()
    for name, base, size in needle_regions:
        chunk = 0x1000
        for off in range(0, size, chunk):
            n = min(chunk, size - off)
            try:
                mem = client.read_mem(base + off, n)
            except GdbError:
                continue
            for tv in targets:
                for hit in scan_bytes_for_word(
                    mem, tv, base_addr=base + off, unaligned=unaligned
                ):
                    if hit in seen_addr:
                        continue
                    seen_addr.add(hit)
                    found.append((name, hit, tv))
                    if len(found) >= limit:
                        return found
    return found


def report_value_context(
    client: GdbClient,
    value: int,
    stop: Optional[str],
    *,
    unaligned: bool = False,
    limit: int = 50,
    rom_path: Optional[Path] = None,
) -> None:
    if stop is not None:
        print(f"停包: {stop}")
    regs = client.read_regs()
    print(format_regs(regs, highlight=value))
    pc = regs.get("r15", 0)
    lr = regs.get("r14", 0)
    print(f"\nPC=0x{pc:08X}  LR=0x{lr:08X}")

    hits = []
    for n, v in regs.items():
        kind = classify_reg_hit(v, value)
        if kind:
            hits.append(f"{n}=0x{v:08X}({kind})")
    if hits:
        print(f"与 0x{value:08X} 相关的寄存器: {', '.join(hits)}")
    else:
        print(f"当前寄存器中没有接近 0x{value:08X} 的值")

    # 已在异常向量：说明已经因坏指针炸过，再 goto 无意义
    if (pc & ~1) <= 0x20:
        print(
            "\n[解读] PC 落在 BIOS/异常向量附近 —— 游戏已经因坏指针崩过一次。\n"
            "  不要再 jump 到 F9…；现场里的 r1/LR（Thumb 形态）才是线索。\n"
            "  下一步应找「谁把该值写进寄存器/谁当函数指针用」，"
            "而不是再次触发同样的炸。"
        )

    print("PC 附近指令字:")
    print(dump_code_words(client, pc, 4))

    # 顺手 dump 几个像指针的寄存器附近，方便人眼看
    print("\n疑似指针寄存器附近字:")
    for name in ("r1", "r3", "r5", "r6", "r7", "r9", "r14"):
        if name not in regs:
            continue
        a = regs[name] & ~1
        if not (0x02000000 <= a < 0x04000000 or 0x08000000 <= a < 0x0A000000):
            continue
        try:
            words = struct.unpack("<IIII", client.read_mem(a, 16))
            print(
                f"  {name} -> 0x{a:08X}: "
                + " ".join(f"{w:08X}" for w in words)
            )
        except GdbError:
            print(f"  {name} -> 0x{a:08X}: (读失败)")

    print(f"\n扫描 RAM 中存放 0x{value:08X} 及近邻的槽:")
    ram_hits = scan_ram_for_value(
        client, value, unaligned=unaligned, limit=limit, also_related=True
    )
    if not ram_hits:
        print("  (RAM 无命中 — 坏值可能从未写成完整字，而是指令/错位读出来的)")
    else:
        for name, addr, word in ram_hits:
            print(f"  [{name}] 0x{addr:08X} = 0x{word:08X}")

    if rom_path and rom_path.is_file():
        print(f"\n扫描 ROM 文件 {rom_path}:")
        data = rom_path.read_bytes()
        any_hit = False
        for tv in related_values(value):
            offs = scan_rom_for_word(data, tv, unaligned=unaligned)
            for off in offs[: max(1, limit // 4)]:
                any_hit = True
                print(f"  word=0x{tv:08X} file=0x{off:06X} gba=0x{to_gba_ptr(off):08X}")
        if not any_hit:
            print("  (ROM 静态无命中)")


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------


def cmd_find(args: argparse.Namespace) -> int:
    value = parse_u32(args.value)
    rom_path = Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM 不存在: {rom_path}", file=sys.stderr)
        return 1
    data = rom_path.read_bytes()
    origin: Optional[bytes] = None
    if args.origin:
        op = Path(args.origin)
        if not op.is_file():
            print(f"原盘不存在: {op}", file=sys.stderr)
            return 1
        origin = op.read_bytes()

    by_addr: dict = {}
    by_ps: dict = {}
    ranges: list = []
    if args.build:
        bp = Path(args.build)
        if not bp.is_file():
            print(f"build 不存在: {bp}", file=sys.stderr)
            return 1
        print(f"加载 translate.build.json: {bp}")
        by_addr, by_ps, ranges = load_build_index(bp)

    needle = struct.pack("<I", value)
    print(f"查找 LE 字 {value:08X} 字节={needle.hex(' ')}")
    print(f"ROM: {rom_path} ({len(data)} bytes), step={'1' if args.unaligned else '4'}")

    hits = scan_rom_for_word(data, value, unaligned=args.unaligned)
    raw_count = len(hits)
    if origin is not None:
        hits = filter_hits_with_origin(
            hits,
            value,
            origin,
            keep_same=args.keep_same,
            origin_ptr_only=args.origin_ptr_only,
        )
        print(f"原始命中 {raw_count}，origin 过滤后 {len(hits)}")

    if not hits:
        print(
            "ROM 静态无此字（或已被 --origin 过滤掉）。"
            "坏值可能只在运行时出现，请用: listen / watch / regs"
        )
        return 0

    print(f"命中 {len(hits)} 处:\n")
    max_show = args.limit
    for i, off in enumerate(hits[:max_show]):
        gba = to_gba_ptr(off)
        ow_s = ""
        if origin is not None and off + 4 <= len(origin):
            ow = struct.unpack_from("<I", origin, off)[0]
            ow_s = f"  origin={ow:08X}"
            if looks_like_rom_ptr(ow):
                ow_s += " (rom_ptr)"
        print(f"[{i}] file=0x{off:06X}  gba=0x{gba:08X}{ow_s}")
        if by_addr or by_ps or ranges:
            matches = match_build(gba, by_addr, by_ps, ranges)
            for m in matches[:5]:
                print(
                    f"     build: id={m.get('id')} type={m.get('type')} "
                    f"module={m.get('module')} addr={m.get('address')} "
                    f"tr={m.get('translated')!r}"
                )
    if len(hits) > max_show:
        print(f"\n... +{len(hits) - max_show} more (limit={max_show})")
    return 0


def cmd_regs(args: argparse.Namespace) -> int:
    host, port = parse_gdb_hostport(args.gdb)
    try:
        with GdbClient(host, port) as gdb:
            regs = gdb.read_regs()
            print(f"GDB {host}:{port}")
            print(format_regs(regs))
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    slot = parse_u32(args.slot)
    host, port = parse_gdb_hostport(args.gdb)
    print(f"写断点 @ 0x{slot:08X}，连接 {host}:{port} ...")
    print("在 mGBA 里复现写入该槽的操作；命中后会打印 PC/LR。Ctrl+C 取消。")
    print("若立刻断连，请改用 listen <坏值>（不要对 ROM 指针槽硬 watch）。")
    try:
        with GdbClient(host, port) as gdb:
            try:
                before = gdb.read_u32(slot)
                print(f"当前槽内字: 0x{before:08X}")
            except GdbError as e:
                print(f"警告: 读槽失败 ({e})，仍尝试下断点")

            gdb.set_write_watch(slot, 4)
            watch_kind = 2
            try:
                stop = gdb.continue_and_wait(timeout=args.timeout)
            except KeyboardInterrupt:
                print("\n已取消")
                return 130
            finally:
                gdb.clear_watch(watch_kind, slot, 4)

            print(f"停包: {stop}")
            regs = gdb.read_regs()
            print(format_regs(regs))
            pc = regs.get("r15", 0)
            lr = regs.get("r14", 0)
            print(f"\n写入方候选 PC=0x{pc:08X}  LR=0x{lr:08X}")
            try:
                now = gdb.read_u32(slot)
                print(f"槽内现字: 0x{now:08X}")
            except GdbError:
                pass
            print("PC 附近指令字:")
            print(dump_code_words(gdb, pc, 4))
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_listen(args: argparse.Namespace) -> int:
    """输入坏值 -> 等访问/停下 -> 输出 PC 与存放该值的槽地址。"""
    value = parse_u32(args.value)
    host, port = parse_gdb_hostport(args.gdb)
    rom_path = Path(args.rom) if args.rom else None

    print(f"listen 0x{value:08X} @ {host}:{port}")
    print("流程: 对坏地址下访问/读断点 -> 你在 mGBA 复现 -> 停下后反查寄存器与 RAM 槽")
    print("Ctrl+C 取消。\n")

    try:
        with GdbClient(host, port) as gdb:
            # 已停下且 --now：直接抓现场
            if args.now:
                print("--now: 抓取当前停机现场（不下断、不 continue）")
                report_value_context(
                    gdb,
                    value,
                    stop=None,
                    unaligned=args.unaligned,
                    limit=args.limit,
                    rom_path=rom_path,
                )
                return 0

            # 先看寄存器是否已持有坏值
            try:
                regs = gdb.read_regs()
                already = [n for n, v in regs.items() if v == value]
                if already:
                    print(f"连接时寄存器已有坏值: {', '.join(already)}")
                    report_value_context(
                        gdb,
                        value,
                        stop=None,
                        unaligned=args.unaligned,
                        limit=args.limit,
                        rom_path=rom_path,
                    )
                    return 0
            except GdbError as e:
                print(f"警告: 读寄存器失败 ({e})")

            # 对「坏值当作地址」下断：谁去读/碰 F909F6A4 就停
            armed: Optional[int] = None
            for kind, label in ((4, "access Z4"), (3, "read Z3")):
                try:
                    gdb.set_watch(kind, value, 4)
                    armed = kind
                    print(f"已下 {label} @ 0x{value:08X}")
                    break
                except GdbError as e:
                    print(f"  {label} 失败: {e}")

            if armed is None:
                print(
                    "无法对坏地址下 watch。"
                    "改为：continue 后等任意停下（请在 mGBA 复现崩溃或手动 Pause）。"
                )

            print("continue 中，请复现…")
            try:
                stop = gdb.continue_and_wait(timeout=args.timeout)
            except KeyboardInterrupt:
                print("\n已取消")
                return 130
            finally:
                if armed is not None:
                    gdb.clear_watch(armed, value, 4)

            report_value_context(
                gdb,
                value,
                stop=stop,
                unaligned=args.unaligned,
                limit=args.limit,
                rom_path=rom_path,
            )
    except GdbError as e:
        print(str(e), file=sys.stderr)
        print(
            "\n提示: 若复现时 GDB 被断开，请在崩溃前于 mGBA 点 Pause，"
            "再跑: python gdb_patcher.py listen 0x%08X --gdb %s --now"
            % (value, args.gdb),
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_goto(args: argparse.Namespace) -> int:
    """把 PC 设到指定地址并 continue（仅验证会炸；不能代替找注入槽）。"""
    addr = parse_u32(args.addr)
    host, port = parse_gdb_hostport(args.gdb)
    print(
        f"goto 0x{addr:08X} @ {host}:{port}\n"
        "注意: 这只会再次触发非法取指/访问，一般看不到「是谁注入的」。\n"
        "若已像 listen --now 那样停在异常向量，请不要再用 goto。\n"
    )
    try:
        with GdbClient(host, port) as gdb:
            regs = gdb.read_regs()
            pc = regs.get("r15", 0)
            if (pc & ~1) <= 0x20:
                print(
                    f"当前 PC=0x{pc:08X} 已在异常向量，拒绝 goto。"
                    "请重新加载 ROM/读档到崩溃前，再用 listen --now。"
                )
                return 2
            thumb = None if args.arm else True
            # 默认按 Thumb 跳（GBA 游戏代码多为 Thumb）；--arm 可关
            gdb.write_pc(addr, thumb=False if args.arm else True)
            print(f"已写 PC -> 0x{gdb.read_regs().get('r15', 0):08X}，continue…")
            try:
                stop = gdb.continue_and_wait(timeout=args.timeout if args.timeout else 5.0)
            except KeyboardInterrupt:
                print("\n已取消")
                return 130
            report_value_context(
                gdb,
                addr & ~1,
                stop=stop,
                limit=args.limit,
                rom_path=Path(args.rom) if args.rom else None,
            )
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def cmd_find_live(args: argparse.Namespace) -> int:
    value = parse_u32(args.value)
    host, port = parse_gdb_hostport(args.gdb)
    try:
        with GdbClient(host, port) as gdb:
            print(f"运行时扫描值 0x{value:08X} @ {host}:{port}")
            hits = scan_ram_for_value(
                gdb, value, unaligned=args.unaligned, limit=args.limit
            )
            if not hits:
                print("运行时可见 RAM 无此字。")
            else:
                for name, addr, word in hits:
                    print(f"  [{name}] 0x{addr:08X} = 0x{word:08X}")
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "gdb_patcher: map bad pointer value to slot address; "
            "mGBA GDB listen/watch"
        ),
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_listen = sub.add_parser(
        "listen",
        help="listen for bad value: watch access then report PC + slots",
    )
    p_listen.add_argument("value", help="bad value/address, e.g. 0xF909F6A4")
    p_listen.add_argument("--gdb", default=DEFAULT_GDB, help="host:port")
    p_listen.add_argument(
        "--now",
        action="store_true",
        help="do not continue; dump current halted state only",
    )
    p_listen.add_argument("--rom", help="optional .gba to also scan statically")
    p_listen.add_argument("--timeout", type=float, default=None)
    p_listen.add_argument("--unaligned", action="store_true")
    p_listen.add_argument("--limit", type=int, default=50)
    p_listen.set_defaults(func=cmd_listen)

    p_goto = sub.add_parser(
        "goto",
        help="set PC to addr and continue (re-trigger crash; not for finding inject slot)",
    )
    p_goto.add_argument("addr", help="e.g. 0xF909F6A4")
    p_goto.add_argument("--gdb", default=DEFAULT_GDB)
    p_goto.add_argument("--arm", action="store_true", help="jump as ARM (default Thumb)")
    p_goto.add_argument("--rom", help="optional .gba scan after stop")
    p_goto.add_argument("--timeout", type=float, default=5.0)
    p_goto.add_argument("--limit", type=int, default=50)
    p_goto.set_defaults(func=cmd_goto)

    p_find = sub.add_parser("find", help="scan ROM for LE word slots holding <value>")
    p_find.add_argument("value", help="bad value, e.g. 0xF909F6A4")
    p_find.add_argument("--rom", required=True, help="translated/test .gba")
    p_find.add_argument("--origin", help="JP origin ROM for filtering")
    p_find.add_argument(
        "--origin-ptr-only",
        action="store_true",
        default=True,
        help="with --origin, keep only slots that look like 08/09 ptrs in origin",
    )
    p_find.add_argument(
        "--no-origin-ptr-only",
        action="store_false",
        dest="origin_ptr_only",
        help="with --origin, keep all slots where origin != value",
    )
    p_find.add_argument(
        "--keep-same",
        action="store_true",
        help="with --origin, do not drop slots already equal in origin",
    )
    p_find.add_argument("--build", help="translate.build.json for cross-ref")
    p_find.add_argument("--unaligned", action="store_true", help="scan step=1")
    p_find.add_argument("--limit", type=int, default=50, help="max printed hits")
    p_find.set_defaults(func=cmd_find)

    p_watch = sub.add_parser("watch", help="GDB write-watch: slot -> writer PC")
    p_watch.add_argument("slot", help="pointer slot GBA address, e.g. 0x080ECDDC")
    p_watch.add_argument("--gdb", default=DEFAULT_GDB, help="host:port")
    p_watch.add_argument("--timeout", type=float, default=None)
    p_watch.set_defaults(func=cmd_watch)

    p_regs = sub.add_parser("regs", help="dump registers via GDB")
    p_regs.add_argument("--gdb", default=DEFAULT_GDB, help="host:port")
    p_regs.set_defaults(func=cmd_regs)

    p_live = sub.add_parser(
        "find-live",
        help="GDB-scan EWRAM/IWRAM for bad value",
    )
    p_live.add_argument("value", help="bad value, e.g. 0xF909F6A4")
    p_live.add_argument("--gdb", default=DEFAULT_GDB)
    p_live.add_argument("--unaligned", action="store_true")
    p_live.add_argument("--limit", type=int, default=50)
    p_live.set_defaults(func=cmd_find_live)

    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_stdio()
    ap = build_parser()
    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
