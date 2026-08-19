#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gdb_patcher.py — 基于 mGBA GDB stub 的运行时追踪工具。

提供 `log` 命令：按「函数」监听指定游戏函数的每次进入，每个函数由
独立 handler 负责读取寄存器/内存并输出日志。函数通过注册表登记
（名字 → 断点地址 + handler），'--functions' 选择要监听的函数，
未注册的名字会被跳过并警告；缺省只监听 InitTextPrinter（文本块级，
一次解码整段，逐字符 ProcessCurrentChar 属冗余，需显式指定才监听）。

文本类 handler（InitTextPrinter / ProcessCurrentChar）：
  - 指定 --charmap：查表解码文本（如 CHS 中文 F9 00 lead trail）
  - 未指定：按原始字节 hex + 可读转义原样输出
未来图标类 handler（图块/调色板加载）只需注册新名字与地址。

用法：
  mGBA 打开 ROM，Tools → Start GDB stub（2345），Pause。
  python src/util/gdb_patcher.py log
  python src/util/gdb_patcher.py log --functions InitTextPrinter
  python src/util/gdb_patcher.py log --functions InitTextPrinter,ProcessCurrentChar \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt
  到目标界面操作，Ctrl-C 结束，分析 work/gdb_patcher_log.log。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from util.debug_patcher import GdbClient, GdbError, parse_gdb_hostport  # noqa: E402

DEFAULT_GDB = "127.0.0.1:2345"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ORIGIN = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
DEFAULT_LOG = REPO_ROOT / "work" / "gdb_patcher_log.log"

STR_MAX = 512

# InitTextPrinter(win, str, tile_base, cur_x) / ProcessCurrentChar_RegularGlyph（r4=win, r3=char）
BP_INIT_TEXT = 0x08002C68
BP_CHAR = 0x0800336E

# 缺省（未传 --functions）监听的函数：文本块级，一次解码整段。
DEFAULT_FUNCTIONS = ["InitTextPrinter"]


def u16(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8)


def u32(b: bytes, o: int) -> int:
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)


def region_of(addr: int) -> str:
    if 0x08000000 <= addr < 0x0A000000:
        return "ROM"
    if 0x02000000 <= addr < 0x02040000:
        return "EWRAM"
    if 0x03000000 <= addr < 0x03008000:
        return "IWRAM"
    if 0x05000000 <= addr < 0x05000400:
        return "VRAM"
    if 0x04000000 <= addr < 0x04000400:
        return "IO"
    if addr < 0x04000000:
        return "BIOS/低"
    return "其它"


def load_charmap(path: str) -> tuple[dict[int, str], dict[int, str]]:
    """charmap.txt → (single, double)。single: byte→字；double: (lead<<8|trail)→字。"""
    single: dict[int, str] = {}
    double: dict[int, str] = {}
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"警告: 读 charmap 失败 {path}: {e}", file=sys.stderr)
        return single, double
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        hx, ch = line.split("=", 1)
        try:
            v = int(hx.strip(), 16)
        except ValueError:
            continue
        if v <= 0xFF:
            single[v] = ch
        else:
            double[v] = ch
    return single, double


def decode_text(data: bytes, single: dict[int, str], double: dict[int, str]) -> str:
    """解码 FF 结尾文本：F9 00 lead trail → 查表；控制码 → \\n/\\l/\\CC/\\v。"""
    out: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0xFF:
            break
        if b == 0xF9:
            if i + 3 < n and data[i + 1] == 0x00:
                key = (data[i + 2] << 8) | data[i + 3]
                out.append(double.get(key, f"<F9:{key:04X}>"))
                i += 4
                continue
            if i + 2 < n:
                out.append(f"{{F9→短语0x{(data[i + 1] << 8) | data[i + 2]:04X}}}")
                break
            out.append("<F9>")
            i += 1
            continue
        if b == 0xFE:
            out.append("\n")
            i += 1
            continue
        if b == 0xFA:
            out.append("\\l")
            i += 1
            continue
        if b == 0xFB:
            out.append("\n\n")
            i += 1
            continue
        if b == 0xFD and i + 1 < n:
            out.append(f"\\{data[i + 1]:02X}")
            i += 2
            continue
        if b >= 0xFC:
            if b == 0xFC and i + 1 < n:
                out.append(f"\\CC{data[i + 1]:02X}")
                i += 2
                continue
            out.append(f"[0x{b:02X}]")
            i += 1
            continue
        if b in single:
            out.append(single[b])
        else:
            out.append(f"<{b:02X}>")
        i += 1
    return "".join(out)


def raw_dump(data: bytes) -> str:
    """未指定字库时的原样输出：可打印字符原样，控制码/高位字节标注。"""
    rep: list[str] = []
    for b in data:
        if 0x20 <= b < 0x7F:
            rep.append(chr(b))
        elif b == 0xFF:
            rep.append("•FF")
        elif b == 0xFE:
            rep.append("\\n")
        else:
            rep.append(f"<{b:02X}>")
    return "".join(rep)


class Ctx:
    """handler 共享的上文：日志、去重、字库解码开关。"""

    def __init__(
        self,
        gdb: GdbClient,
        logpath: str,
        single: dict[int, str],
        double: dict[int, str],
        origin: Optional[bytes],
        dedup: bool,
    ):
        self.gdb = gdb
        self.logpath = logpath
        self.single = single
        self.double = double
        self.origin = origin
        self.dedup = dedup
        self._last: object = None
        self._skipped = 0

    def log(self, msg: object = "") -> None:
        line = str(msg)
        with open(self.logpath, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def _hit(self, key: object) -> bool:
        if not self.dedup:
            return True
        if key == self._last:
            self._skipped += 1
            return False
        if self._skipped:
            self.log(f"  …以上重复 {self._skipped} 次（--no-dedup 关闭去重）")
            self._skipped = 0
        self._last = key
        return True

    def text_of(self, data: bytes) -> str:
        """有字库查表，无字库原样字节转义。"""
        if self.single or self.double:
            return decode_text(data, self.single, self.double)
        return raw_dump(data)

    def char_of(self, b: int) -> str:
        if self.single:
            return self.single.get(b, f"<{b:02X}>")
        return raw_dump(bytes([b]))


class Hook:
    """一个被监听函数的登记：断点地址 + 命中 handler。"""

    def __init__(self, name: str, bp: int, desc: str, handler):
        self.name = name
        self.bp = bp
        self.desc = desc
        self.handler = handler

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Hook {self.name} @0x{self.bp:08X}>"


FUNCTIONS: dict[str, Hook] = {}


def register(name: str, bp: int, desc: str = ""):
    def deco(handler):
        FUNCTIONS[name] = Hook(name, bp, desc, handler)
        return handler

    return deco


def _read_win(gdb: GdbClient, win: int) -> bytes:
    try:
        b = bytes(gdb.read_mem(win, 0x20))
    except GdbError:
        return b""
    return b[:0x20]


def _read_ff_text(gdb: GdbClient, addr: int) -> bytes:
    try:
        data = bytes(gdb.read_mem(addr, STR_MAX))
    except GdbError:
        return b""
    end = data.find(0xFF)
    return data[: end + 1] if end >= 0 else data


@register("InitTextPrinter", BP_INIT_TEXT, "文本块开始（r0=win, r1=文本指针, r2=tile_base, r3=cur_x）")
def _on_init_text(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    win = regs.get("r0", 0)
    sp = regs.get("r1", 0)
    tb = regs.get("r2", 0) & 0xFFFF
    cx = regs.get("r3", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    data = _read_ff_text(gdb, sp)
    if not ctx._hit((sp, data[:64])):
        return
    ctx.log(f"\n[InitTextPrinter] win=0x{win:08X} 文本=0x{sp:08X} ({region_of(sp)}) LR=0x{lr:08X}")
    wb = _read_win(gdb, win)
    if len(wb) >= 0x1E:
        ctx.log(
            f"  TILE_BASE=0x{tb:04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
            f" curX={cx} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            f" textMode={wb[0x0A]} fontNum={wb[0x0B]}"
        )
    ctx.log(f"  原始字节: {data[:64].hex(' ')}")
    ctx.log(f"  内容: {ctx.text_of(data)!r}")
    if b"\xff" not in data:
        ctx.log(f"  （前 {len(data)} 字节未遇 0xFF 结束符，可能超长）")
    if region_of(sp) == "ROM" and ctx.origin:
        fo = sp - 0x08000000
        if 0 <= fo < len(ctx.origin):
            ob = ctx.origin[fo : fo + STR_MAX]
            end = ob.find(0xFF)
            ob = ob[: end + 1] if end >= 0 else ob
            if ob:
                ctx.log(f"  原盘同址: {ob[:64].hex(' ')}")


@register("ProcessCurrentChar", BP_CHAR, "逐字符（r4=win, r3=char）")
def _on_char(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    win = regs.get("r4", 0)
    ch = regs.get("r3", 0) & 0xFF
    wb = _read_win(gdb, win)
    tptr = u32(wb, 0x10) if len(wb) >= 0x14 else 0
    index = u16(wb, 0x14) if len(wb) >= 0x16 else 0
    cur = (tptr + index - 1) & 0xFFFFFFFF
    if not ctx._hit((win, cur, ch)):
        return
    ctx.log(
        f"\n[char] win=0x{win:08X} 字符=0x{ch:02X} → {ctx.char_of(ch)!r}"
        f" 位置=0x{cur:08X}({region_of(cur)}) index={index}"
    )
    if len(wb) >= 0x1E:
        ctx.log(
            f"  curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            f" textMode={wb[0x0A]} fontNum={wb[0x0B]}"
        )


def _select_hooks(names: Optional[str]) -> list[Hook]:
    """--functions 逗号分隔；未注册的跳过并警告。缺省 DEFAULT_FUNCTIONS。"""
    picked = [s.strip() for s in (names or "").split(",") if s.strip()]
    if not picked:
        return [FUNCTIONS[n] for n in DEFAULT_FUNCTIONS if n in FUNCTIONS]
    hooks: list[Hook] = []
    missing: list[str] = []
    for n in picked:
        if n in FUNCTIONS:
            hooks.append(FUNCTIONS[n])
        else:
            missing.append(n)
    if missing:
        print(
            f"警告: 未注册的函数，跳过: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            f"已注册: {', '.join(sorted(FUNCTIONS))}",
            file=sys.stderr,
        )
    return hooks


def run_log(args: argparse.Namespace) -> int:
    logpath = args.log or str(DEFAULT_LOG)
    Path(logpath).parent.mkdir(parents=True, exist_ok=True)

    hooks = _select_hooks(args.functions)
    if not hooks:
        print("没有可监听的函数（--functions 全部未注册？）。", file=sys.stderr)
        return 2

    single, double = {}, {}
    if args.charmap:
        single, double = load_charmap(args.charmap)
        mode = f"字库解码 {args.charmap}（{len(single)} 单字节 / {len(double)} 双字节）"
    else:
        mode = "原样输出原始字节（未指定 --charmap）"

    origin = None
    if os.path.isfile(args.origin):
        origin = open(args.origin, "rb").read()

    host, port = parse_gdb_hostport(args.gdb)
    gdb = GdbClient(host, port, timeout=5.0)
    for _ in range(200):
        try:
            gdb.close()
            gdb.connect()
            break
        except GdbError:
            gdb.close()
            time.sleep(0.5)
    else:
        print("无法连接 mGBA GDB stub（先 mGBA 开 ROM + Start GDB stub + Pause）", file=sys.stderr)
        return 2

    ctx = Ctx(gdb, logpath, single, double, origin, dedup=not args.no_dedup)
    ctx.log(
        f"\n===== gdb_patcher log @ {time.strftime('%H:%M:%S')}"
        f" [{', '.join(h.name for h in hooks)}] {mode} ====="
    )

    armed = [h for h in hooks if _arm(ctx, h)]
    if not armed:
        print("所有断点设置失败，退出。", file=sys.stderr)
        gdb.close()
        return 2
    by_pc = {h.bp: h for h in armed}

    ctx.log("追踪中：到目标界面操作，Ctrl-C 结束。日志: " + logpath)
    n = 0
    try:
        while n < args.limit:
            try:
                gdb.cont(timeout=args.cont_timeout)
            except GdbError as e:
                ctx.log(f"\n[停止] {e}")
                break
            regs = gdb.read_regs()
            pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
            n += 1
            hook = by_pc.get(pc)
            if hook is None:
                ctx.log(f"\n[{n}] 意外 PC=0x{pc:08X}")
            else:
                hook.handler(gdb, regs, ctx)
    except KeyboardInterrupt:
        ctx.log("\n[用户中断]")
    finally:
        for h in armed:
            try:
                gdb.clear_sw_break(h.bp)
            except GdbError:
                pass
        gdb.close()
    ctx.log(f"追踪结束，共 {n} 次命中。日志: {logpath}")
    return 0


def _arm(ctx: Ctx, hook: Hook) -> bool:
    try:
        ctx.gdb.set_sw_break(hook.bp)
    except GdbError as e:
        ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} 失败: {e}")
        return False
    ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} OK")
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="基于 mGBA GDB stub 的运行时追踪（log 命令，按函数监听）",
    )
    ap.add_argument("cmd", choices=["log"], help="log：追踪指定函数")
    ap.add_argument(
        "--functions",
        default=None,
        help="逗号分隔要监听的函数名，如 InitTextPrinter,ProcessCurrentChar；"
        "缺省只监听 InitTextPrinter",
    )
    ap.add_argument(
        "--charmap",
        default=None,
        help="字库映射路径（如 configs/POKEMON_RUBY_AXVJ00/charmap.txt）；"
        "指定则查表解码文本，未指定按原始字节输出",
    )
    ap.add_argument("--gdb", default=DEFAULT_GDB, help="host:port（默认 127.0.0.1:2345）")
    ap.add_argument("--limit", type=int, default=3000, help="最多命中次数")
    ap.add_argument("--cont-timeout", type=float, default=600.0, help="每次 continue 等待秒数")
    ap.add_argument("--no-dedup", action="store_true", help="关闭连续重复去重")
    ap.add_argument(
        "--log",
        default=None,
        help=f"日志文件路径（缺省 {DEFAULT_LOG}）",
    )
    ap.add_argument(
        "--origin",
        default=str(DEFAULT_ORIGIN),
        help="原盘 ROM 路径（InitTextPrinter 同址对照用）",
    )
    args = ap.parse_args(argv)

    try:
        return run_log(args)
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())