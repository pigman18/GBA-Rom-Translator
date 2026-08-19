#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_patcher.py
==============
1) 崩后 Pause（坏址还在 PC/寄存器里）：
     python src/util/debug_patcher.py 0xD8004286

2) SoftReset / 进 BIOS（CallVia 拦不到时优先用 romscan）：
     python src/util/debug_patcher.py romscan 0x5F0A00F9
     python src/util/debug_patcher.py trap 0x5F0A00F9 --any-f9

不改 ROM、不代开模拟器。trap 会设断 / continue；romscan / 事后只读不下断。
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

DEFAULT_GDB = "127.0.0.1:2345"

REG_NAMES = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
    "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "cpsr",
]

# EWRAM / IWRAM（对齐扫 4 字节槽）
RAM_BANDS: list[tuple[str, int, int]] = [
    ("EWRAM", 0x02000000, 0x00040000),
    ("IWRAM", 0x03000000, 0x00008000),
]

# AXVJ：CallViaR0..R3（bx rN），AnimCmd 等走这里
CALLVIA_BPS: list[tuple[str, int, str]] = [
    ("CallViaR0", 0x081B12D4, "r0"),
    ("CallViaR1", 0x081B12D8, "r1"),
    ("CallViaR2", 0x081B12DC, "r2"),
    ("CallViaR3", 0x081B12E0, "r3"),
]

# SoftReset stub（DoSoftReset 末尾 bl 目标）— 重启前最后能抓的现场
SOFTRESET_BP = 0x081B12B0

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ORIGIN = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
DEFAULT_TRANSLATED = REPO_ROOT / "roms" / "outputs" / "POKEMON_RUBY_AXVJ00_translated.gba"
DEFAULT_BUILD_JSON = REPO_ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "translate.build.json"

# AnimCmd：CallViaR1 返回点（bx r1 之后），见 0x080015E2 bl → LR=0x080015E7
ANIMCMD_LR = 0x080015E7
ANIMCMD_LR_LO = 0x08001580
ANIMCMD_LR_HI = 0x08001620


class GdbError(RuntimeError):
    pass


def parse_u32(text: str) -> int:
    s = text.strip().lower().replace("_", "")
    if s.startswith("0x"):
        return int(s, 16) & 0xFFFFFFFF
    return int(s, 16) & 0xFFFFFFFF


def parse_gdb_hostport(s: str) -> tuple[str, int]:
    s = (s or DEFAULT_GDB).strip()
    if ":" in s:
        host, port_s = s.rsplit(":", 1)
        return host or "127.0.0.1", int(port_s)
    return "127.0.0.1", int(s)


def match_kinds(word: int, value: int) -> list[str]:
    """精确 / Thumb 近邻。"""
    w = word & 0xFFFFFFFF
    v = value & 0xFFFFFFFF
    tags: list[str] = []
    if w == v:
        tags.append("exact")
    if w == ((v + 1) & 0xFFFFFFFF) or w == ((v - 1) & 0xFFFFFFFF):
        tags.append("thumb±1")
    return tags


def looks_code_ptr(w: int) -> bool:
    """合法可执行目标：ROM/扩展 ROM/EWRAM/IWRAM（含 Thumb bit）。"""
    p = w & ~1
    hi = (p >> 24) & 0xFF
    if hi in (0x02, 0x03):
        return True
    if hi in (0x08, 0x09):
        return True
    return False


def in_bios(pc: int) -> bool:
    return (pc & 0xFFFFFFFF) < 0x00004000


class GdbClient:
    """mGBA GDB stub。"""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self._buf = bytearray()

    def connect(self) -> None:
        try:
            self.sock = socket.create_connection(
                (self.host, self.port), timeout=self.timeout
            )
        except OSError as e:
            raise GdbError(
                f"无法连接 GDB {self.host}:{self.port} ({e}). "
                "请先在 mGBA 打开 ROM，Tools → Start GDB stub（默认 2345），并 Pause。"
            ) from e
        self.sock.settimeout(self.timeout)
        self._buf.clear()
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
                raise GdbError("GDB 连接已断开（mGBA 关了 stub 或已崩）。")
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
            if self.sock:
                self.sock.sendall(b"-")
            raise GdbError(f"校验和错误: got {csum!r} expect {expect!r}")
        if self.sock:
            self.sock.sendall(b"+")
        return data.decode("ascii", errors="replace")

    def cmd(self, payload: str) -> str:
        self._send_packet(payload)
        return self._recv_packet()

    def cont(self, timeout: float) -> str:
        """continue，等到下一次停（或超时）。"""
        self._send_packet("c")
        assert self.sock
        old = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            return self._recv_packet()
        except socket.timeout as e:
            raise GdbError(
                f"等待停机超时（{timeout:.0f}s）。"
                "确认已播到会重启的动画，且 GDB stub 仍开着。"
            ) from e
        finally:
            self.sock.settimeout(old)

    def set_sw_break(self, addr: int, kind: int = 2) -> None:
        """Thumb 软件断点 Z0,addr,2。"""
        r = self.cmd(f"Z0,{addr & 0xFFFFFFFF:x},{kind}")
        if r not in ("OK", ""):
            raise GdbError(f"设断点失败 @0x{addr:08X}: {r}")

    def clear_sw_break(self, addr: int, kind: int = 2) -> None:
        r = self.cmd(f"z0,{addr & 0xFFFFFFFF:x},{kind}")
        if r not in ("OK", ""):
            # 清理失败不致命
            print(f"警告: 清断点 @0x{addr:08X}: {r}")

    def read_regs(self) -> dict[str, int]:
        raw = self.cmd("g")
        if raw.startswith("E") or not raw:
            raise GdbError(f"读寄存器失败: {raw}")
        out: dict[str, int] = {}
        for i, name in enumerate(REG_NAMES):
            chunk = raw[i * 8 : i * 8 + 8]
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


def scan_ram_slots(gdb: GdbClient, value: int, *, limit: int = 32) -> list[tuple[str, int]]:
    """返回 [(区域名, 槽地址), ...]。"""
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    hits: list[tuple[str, int]] = []
    chunk = 0x1000
    for name, base, size in RAM_BANDS:
        off = 0
        while off < size and len(hits) < limit:
            n = min(chunk, size - off)
            try:
                data = gdb.read_mem(base + off, n)
            except GdbError:
                off += n
                continue
            pos = 0
            while pos + 4 <= len(data) and len(hits) < limit:
                abs_addr = base + off + pos
                if abs_addr & 3:
                    pos += 1
                    continue
                if data[pos : pos + 4] == needle:
                    hits.append((name, abs_addr))
                    pos += 4
                else:
                    pos += 4
            off += n
    return hits


def _hex_words(data: bytes, base: int) -> str:
    parts: list[str] = []
    for i in range(0, len(data) - 3, 4):
        w = struct.unpack_from("<I", data, i)[0]
        parts.append(f"0x{base + i:08X}=0x{w:08X}")
    return " ".join(parts)


def _hex_bytes(data: bytes) -> str:
    return data.hex(" ")


def _looks_ptr(w: int) -> bool:
    hi = (w >> 24) & 0xFF
    return hi in (0x02, 0x03, 0x08, 0x09)


def dump_animcmd_context(gdb: GdbClient, regs: dict[str, int]) -> None:
    """LR 落在 AnimCmd/CallViaR1 一带时，dump r4 精灵结构与命令游标。"""
    lr = regs.get("r14", 0) & ~1
    if not (ANIMCMD_LR_LO <= lr <= ANIMCMD_LR_HI):
        return

    r4 = regs.get("r4", 0) & 0xFFFFFFFF
    r5 = regs.get("r5", 0) & 0xFFFFFFFF
    print(
        f"AnimCmd 现场 (LR≈0x{ANIMCMD_LR:08X}): "
        f"r4=0x{r4:08X} r5=0x{r5:08X}"
    )

    if _looks_ptr(r4):
        try:
            body = gdb.read_mem(r4, 64)
        except GdbError as e:
            print(f"  [r4] 读失败: {e}")
            body = b""
        if body:
            print(f"  [r4] +0..+3F:")
            print(f"       {_hex_words(body, r4)}")
            idx_2a = body[0x2A] if len(body) > 0x2B else None
            idx_2b = body[0x2B] if len(body) > 0x2B else None
            anim_tbl = struct.unpack_from("<I", body, 0x08)[0] if len(body) >= 0x0C else 0
            if idx_2a is not None and idx_2b is not None:
                print(
                    f"  [r4+8] anim_tbl=0x{anim_tbl:08X}  "
                    f"[+0x2A]=0x{idx_2a:02X} [+0x2B]=0x{idx_2b:02X}"
                )
            else:
                print(f"  [r4+8] anim_tbl=0x{anim_tbl:08X}")
            if _looks_ptr(anim_tbl):
                try:
                    n_entries = 8
                    tbl = gdb.read_mem(anim_tbl, n_entries * 4)
                    print(f"  anim_tbl[0..{n_entries - 1}]: {_hex_words(tbl, anim_tbl)}")
                    script_set = idx_2a if idx_2a is not None else 0
                    if script_set < n_entries:
                        script_ptr = struct.unpack_from("<I", tbl, script_set * 4)[0]
                        print(f"  anim_tbl[{script_set}]=0x{script_ptr:08X}")
                        if _looks_ptr(script_ptr):
                            cmd = gdb.read_mem(script_ptr, 32)
                            print(f"  命令流 @0x{script_ptr:08X}: {_hex_bytes(cmd)}")
                            if 0xF9 in cmd:
                                print("  !! 命令流含 F9（疑似中文 PCS 污染）")
                except GdbError as e:
                    print(f"  anim_tbl 读失败: {e}")

    if _looks_ptr(r5):
        base = r5 & ~1
        try:
            around = gdb.read_mem(base, 32)
            print(f"  [r5] @0x{base:08X}: {_hex_bytes(around)}")
            if 0xF9 in around:
                print("  !! r5 附近含 F9")
            halves = [
                f"0x{struct.unpack_from('<H', around, i)[0]:04X}"
                for i in range(0, min(16, len(around) - 1), 2)
            ]
            print(f"  [r5] s16: {' '.join(halves)}")
        except GdbError as e:
            print(f"  [r5] 读失败: {e}")


def report(
    value: int,
    regs: dict[str, int],
    slots: list[tuple[str, int]],
    *,
    gdb: Optional[GdbClient] = None,
    hint_trap: bool = True,
) -> None:
    v = value & 0xFFFFFFFF
    print(f"坏值 0x{v:08X}")

    reg_hits: list[str] = []
    for name in REG_NAMES:
        if name == "cpsr":
            continue
        w = regs.get(name)
        if w is None:
            continue
        tags = match_kinds(w, v)
        if not tags:
            continue
        label = name
        if name == "r14":
            label = "r14(LR)"
        elif name == "r15":
            label = "r15(PC)"
        reg_hits.append(f"{label}={tags[0]}")

    if reg_hits:
        print("寄存器:", ", ".join(reg_hits))
    else:
        print("寄存器: (无命中)")

    pc = regs.get("r15", 0)
    lr = regs.get("r14", 0)
    print(f"LR=0x{lr:08X} PC=0x{pc:08X}")

    if slots:
        parts = [f"0x{addr:08X}[{band}]" for band, addr in slots]
        print("RAM 槽:", ", ".join(parts))
    else:
        print("RAM 槽: (无)")

    if not reg_hits and not slots:
        print("现场已无此值（多半已 SoftReset 进 BIOS）。")
        if hint_trap and in_bios(pc):
            print(
                "请改用 trap（动画播完前接好 GDB，工具会在 CallViaR* 拦住坏指针）：\n"
                f"  python src/util/debug_patcher.py trap 0x{v:08X}"
            )
        elif hint_trap:
            print(
                "请在 PC 仍为坏址时 Pause 再跑本命令；"
                "或改用 trap 在跳转前拦截。"
            )
    elif gdb is not None:
        dump_animcmd_context(gdb, regs)


def _target_matches(target: int, want: int, *, any_bad: bool, any_f9: bool) -> Optional[str]:
    tags = match_kinds(target, want)
    if tags:
        return tags[0]
    if any_f9 and (target & 0xFF) == 0xF9:
        return "low-byte-F9"
    if any_bad and not looks_code_ptr(target):
        return "not-code-ptr"
    return None


def run_romscan(
    value: int,
    *,
    origin_path: Path = DEFAULT_ORIGIN,
    translated_path: Path = DEFAULT_TRANSLATED,
    build_json: Path = DEFAULT_BUILD_JSON,
    limit: int = 16,
) -> int:
    """
    不连 GDB：在成品 ROM 里找坏值字面量，对照原盘看被谁 in_place/relocate 写坏，
    并反查 translate.build.json 条目。适合 SoftReset 类、CallVia trap 拦不到的情况。
    """
    v = value & 0xFFFFFFFF
    if not translated_path.is_file():
        print(f"找不到成品 ROM: {translated_path}", file=sys.stderr)
        return 2
    if not origin_path.is_file():
        print(f"找不到原盘: {origin_path}", file=sys.stderr)
        return 2

    origin = origin_path.read_bytes()
    transl = translated_path.read_bytes()
    needle = struct.pack("<I", v)
    print(f"romscan 坏值 0x{v:08X}（LE {needle.hex(' ')}）")
    print(f"  origin: {origin_path}")
    print(f"  translated: {translated_path}")

    hits: list[int] = []
    start = 0
    while len(hits) < limit:
        j = transl.find(needle, start)
        if j < 0:
            break
        # 对齐到字更可能是指针槽；也报告非对齐（正文里的 F9 流）
        hits.append(j)
        start = j + 1

    if not hits:
        print("成品 ROM 中未找到该字面量。")
        return 1

    entries: list[dict[str, Any]] = []
    if build_json.is_file():
        try:
            doc = json.loads(build_json.read_text(encoding="utf-8"))
            entries = list(doc.get("entries") or [])
        except (OSError, json.JSONDecodeError) as e:
            print(f"警告: 无法读 {build_json}: {e}")

    for fo in hits:
        mem = 0x08000000 + fo
        ow = struct.unpack_from("<I", origin, fo)[0] if fo + 4 <= len(origin) else None
        tw = struct.unpack_from("<I", transl, fo)[0]
        aligned = (fo & 3) == 0
        print(f"\n@ 文件+0x{fo:X} / 内存 0x{mem:08X}  aligned={aligned}")
        if ow is not None:
            print(f"  原盘字: 0x{ow:08X}  →  成品字: 0x{tw:08X}")
            if ow != tw:
                print("  !! 相对原盘被改写（疑似 in_place 盖指针表 / 误注入）")
        # 上下文
        lo = max(0, fo - 8)
        hi = min(len(transl), fo + 16)
        print(f"  原盘附近: {origin[lo:hi].hex(' ')}")
        print(f"  成品附近: {transl[lo:hi].hex(' ')}")

        # 反查 build 条目：address 落在此字，或指针站覆盖此址
        matched = False
        for e in entries:
            try:
                addr = int(str(e.get("address", "0")), 16)
            except ValueError:
                continue
            if addr == mem or (aligned and addr == (mem & ~3)):
                print(
                    f"  → entry {e.get('id')}  module={e.get('module')}  "
                    f"type={e.get('type')}  addr=0x{addr:08X}"
                )
                print(f"     original={e.get('original', '')!r}")
                matched = True
            for p in e.get("pointers") or []:
                try:
                    pa = int(str(p), 16)
                except ValueError:
                    continue
                if pa == mem:
                    print(
                        f"  → entry {e.get('id')}  pointer_site  "
                        f"module={e.get('module')} type={e.get('type')}"
                    )
                    print(f"     original={e.get('original', '')!r}")
                    matched = True
        if not matched and entries:
            # 回退：找 address 落在 [fo-32, fo] 的 in_place（正文盖过来）
            for e in entries:
                if e.get("type") != "in_place":
                    continue
                try:
                    addr = int(str(e.get("address", "0")), 16)
                except ValueError:
                    continue
                if mem - 64 <= addr <= mem:
                    print(
                        f"  → 邻近 in_place {e.get('id')}  "
                        f"module={e.get('module')}  addr=0x{addr:08X}"
                    )
                    print(f"     original={e.get('original', '')!r}")
                    matched = True
                    break
        if not matched:
            print("  （build.json 无直接条目；可把该址附近 in_place 扫进 rejects）")

    print(
        "\n处置：把误扫 anim/指针表的 entry id 写入 "
        "configs/<game>/translate/config.json → rejects，再打包。"
    )
    return 0


def run_inspect(value: int, host: str, port: int, limit: int) -> int:
    with GdbClient(host, port) as gdb:
        regs = gdb.read_regs()
        slots = scan_ram_slots(gdb, value, limit=max(1, limit))
        for delta in (1, -1):
            if len(slots) >= limit:
                break
            extra = scan_ram_slots(
                gdb, (value + delta) & 0xFFFFFFFF, limit=limit - len(slots)
            )
            for band, addr in extra:
                if (band, addr) not in slots:
                    slots.append((band, addr))
        report(value, regs, slots[:limit], gdb=gdb)
    return 0


def run_trap(
    value: int,
    host: str,
    port: int,
    *,
    timeout: float,
    any_bad: bool,
    any_f9: bool,
    limit: int,
) -> int:
    """
    CallViaR0..R3 + SoftReset 下断。
    每次停机扫全部寄存器是否握有坏值（不限 CallVia 目标寄存器）。
    """
    print(
        "trap 模式：CallViaR0..R3 + SoftReset。\n"
        "请先：mGBA 加载会重启的 ROM → Start GDB stub → Pause（开场/动画前）→ 再跑。\n"
        "命令会 continue。若 CallVia 拦不到，先试：\n"
        f"  python src/util/debug_patcher.py romscan 0x{value & 0xFFFFFFFF:08X}"
    )
    with GdbClient(host, port) as gdb:
        regs0 = gdb.read_regs()
        pc0 = regs0.get("r15", 0)
        if in_bios(pc0):
            print(
                f"当前已在 BIOS (PC=0x{pc0:08X})。请重置/重开 ROM，"
                "Pause 在开场，再重新运行 trap。"
            )
            return 2

        addrs = [a for _, a, _ in CALLVIA_BPS] + [SOFTRESET_BP]
        try:
            for name, addr, reg in CALLVIA_BPS:
                gdb.set_sw_break(addr)
                print(f"  断点 {name} @0x{addr:08X}（看 {reg}）")
            gdb.set_sw_break(SOFTRESET_BP)
            print(f"  断点 SoftReset @0x{SOFTRESET_BP:08X}")
        except GdbError:
            for addr in addrs:
                try:
                    gdb.clear_sw_break(addr)
                except GdbError:
                    pass
            raise

        t_end = time.monotonic() + timeout
        hits_ignored = 0
        try:
            while True:
                remain = t_end - time.monotonic()
                if remain <= 0:
                    raise GdbError(
                        f"等待命中超时（{timeout:.0f}s）。"
                        "CallVia/SoftReset 未见坏值 —— 请改用 romscan：\n"
                        f"  python src/util/debug_patcher.py romscan 0x{value & 0xFFFFFFFF:08X}"
                    )
                why = gdb.cont(timeout=max(1.0, remain))
                regs = gdb.read_regs()
                pc = regs.get("r15", 0) & ~1

                # SoftReset：重启前 dump + 扫寄存器/RAM
                if pc == (SOFTRESET_BP & ~1):
                    print(f"命中 SoftReset @0x{pc:08X} 停因={why}（即将重启）")
                    slots = scan_ram_slots(gdb, value, limit=max(1, limit))
                    report(value, regs, slots[:limit], gdb=gdb, hint_trap=False)
                    print(
                        "若仍无坏值，坏址多半只在 ROM 指针表里被 in_place 盖掉；"
                        f"请跑: python src/util/debug_patcher.py romscan 0x{value & 0xFFFFFFFF:08X}"
                    )
                    return 0

                which: Optional[tuple[str, str, int]] = None
                for name, addr, reg in CALLVIA_BPS:
                    if pc == (addr & ~1):
                        which = (name, reg, regs.get(reg, 0) & 0xFFFFFFFF)
                        break

                if which is None:
                    if in_bios(pc):
                        print(f"已进 BIOS（停因={why}）。")
                        report(value, regs, [], gdb=gdb, hint_trap=False)
                        print(
                            f"请改用: python src/util/debug_patcher.py romscan "
                            f"0x{value & 0xFFFFFFFF:08X}"
                        )
                        return 3
                    hits_ignored += 1
                    if hits_ignored <= 3:
                        print(f"  忽略停机 PC=0x{pc:08X} 停因={why}")
                    continue

                name, reg, tgt = which

                # 先扫全部寄存器是否握有坏值（Load 坏址不一定经 CallVia 目标）
                all_hits: list[str] = []
                for rn in REG_NAMES:
                    if rn == "cpsr":
                        continue
                    w = regs.get(rn, 0) & 0xFFFFFFFF
                    reason = _target_matches(
                        w, value, any_bad=False, any_f9=False
                    )
                    if reason:
                        all_hits.append(f"{rn}=0x{w:08X}({reason})")
                    elif any_f9 and (w & 0xFF) == 0xF9 and not looks_code_ptr(w):
                        all_hits.append(f"{rn}=0x{w:08X}(bad-F9)")
                    elif any_bad and not looks_code_ptr(w) and (w >> 24) not in (0, 0x04):
                        # 排除 0 与 IO；保留像 0x5F.... 的假指针
                        if w > 0x1000:
                            all_hits.append(f"{rn}=0x{w:08X}(any-bad)")

                reason = _target_matches(tgt, value, any_bad=any_bad, any_f9=any_f9)
                if reason is None and not all_hits:
                    hits_ignored += 1
                    if hits_ignored <= 8 or hits_ignored % 50 == 0:
                        print(
                            f"  {name}: {reg}=0x{tgt:08X}（非目标，继续） "
                            f"[{hits_ignored}]"
                        )
                    continue

                if all_hits and reason is None:
                    print(
                        f"命中 {name}（CallVia 目标正常，但其它寄存器有坏值） "
                        f"停因={why}"
                    )
                    print("  寄存器坏值:", ", ".join(all_hits))
                else:
                    print(
                        f"命中 {name} @0x{pc:08X}: {reg}=0x{tgt:08X} ({reason}) "
                        f"停因={why}"
                    )
                    if all_hits:
                        print("  另有:", ", ".join(all_hits))

                slots = scan_ram_slots(gdb, value, limit=max(1, limit))
                if (tgt & 0xFFFFFFFF) != (value & 0xFFFFFFFF):
                    for band, addr in scan_ram_slots(gdb, tgt, limit=8):
                        if (band, addr) not in slots:
                            slots.append((band, addr))
                report(value, regs, slots[:limit], gdb=gdb, hint_trap=False)
                return 0
        finally:
            for addr in addrs:
                try:
                    gdb.clear_sw_break(addr)
                except GdbError:
                    pass
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="GDB 坏址现场 / trap / romscan（成品 ROM 反查误注入）",
    )
    ap.add_argument(
        "cmd_or_value",
        help="坏地址，或子命令 trap / romscan",
    )
    ap.add_argument(
        "value",
        nargs="?",
        help="trap/romscan 模式下的坏地址",
    )
    ap.add_argument("--gdb", default=DEFAULT_GDB, help="host:port（默认 127.0.0.1:2345）")
    ap.add_argument("--limit", type=int, default=32, help="最多列出多少个命中")
    ap.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="trap 最长等待秒数（默认 300）",
    )
    ap.add_argument(
        "--any-bad",
        action="store_true",
        help="trap：任意非 ROM/RAM 可执行目标都停（不限给定坏值）",
    )
    ap.add_argument(
        "--any-f9",
        action="store_true",
        help="trap：目标低字节为 F9 即停（PCS 污染特征）",
    )
    ap.add_argument(
        "--rom",
        default=str(DEFAULT_TRANSLATED),
        help="romscan 用的成品 ROM 路径",
    )
    ap.add_argument(
        "--origin",
        default=str(DEFAULT_ORIGIN),
        help="romscan 用的原盘路径",
    )
    ap.add_argument(
        "--build-json",
        default=str(DEFAULT_BUILD_JSON),
        help="romscan 用的 translate.build.json",
    )
    args = ap.parse_args(argv)

    host, port = parse_gdb_hostport(args.gdb)
    first = args.cmd_or_value.strip().lower()

    try:
        if first == "trap":
            if not args.value:
                print(
                    "trap 需要坏地址，例如: python src/util/debug_patcher.py trap 0x5F0A00F9",
                    file=sys.stderr,
                )
                return 2
            value = parse_u32(args.value)
            return run_trap(
                value,
                host,
                port,
                timeout=max(5.0, args.timeout),
                any_bad=args.any_bad,
                any_f9=args.any_f9,
                limit=max(1, args.limit),
            )

        if first == "romscan":
            if not args.value:
                print(
                    "romscan 需要坏地址，例如: "
                    "python src/util/debug_patcher.py romscan 0x5F0A00F9",
                    file=sys.stderr,
                )
                return 2
            value = parse_u32(args.value)
            return run_romscan(
                value,
                origin_path=Path(args.origin),
                translated_path=Path(args.rom),
                build_json=Path(args.build_json),
                limit=max(1, min(args.limit, 64)),
            )

        value = parse_u32(args.cmd_or_value)
        return run_inspect(value, host, port, max(1, args.limit))
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
