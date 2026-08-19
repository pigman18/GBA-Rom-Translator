#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gdb_patcher.py — 基于 mGBA GDB stub 的运行时追踪工具。

提供 `log` 命令：按「函数」监听指定游戏函数的每次进入，每个函数由
独立 handler 负责读取寄存器/内存并输出日志。函数通过注册表登记
（名字 → 断点地址 + handler），'--functions' 按函数名选择要监听的
函数，未注册的名字会被跳过并警告；缺省（不带 --functions）监听全部
已注册函数（文本 + 图像）。ProcessCurrentChar 逐字符输出与
InitTextPrinter 块级解码冗余，默认排除、需显式指定。

文本类 handler（InitTextPrinter / ProcessCurrentChar）：
  - 非 F9 单字节：默认按日文 PCS 假名表解码（ROM 为 AXVJ 日版底包，原日文/未翻译文本）
  - 指定 --charmap：F9 00 lead trail 汉字 + F9 80 短语流递归 查表
  - 未指定：按原始字节 hex + 可读转义原样输出
图像类 handler（图块/调色板加载器）：追踪 logo、图标等素材的加载，
打印 sheet 的 data/size/tag 与数据所在区域（ROM 源给出原盘偏移与头字节）。
全部地址已在日版 AXVJ 上经反汇编行为核实（见 tools/pokeruby-jp/ADDRS.md）。

用法：
  mGBA 打开 ROM，Tools → Start GDB stub（2345），Pause。
  python src/util/gdb_patcher.py log            # 全部函数（文本+图像）
  python src/util/gdb_patcher.py log --functions LoadSpriteSheet,LoadPalette
  python src/util/gdb_patcher.py log --functions InitTextPrinter \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt
  python src/util/gdb_patcher.py log --functions InitTextPrinter,ProcessCurrentChar \
      --charmap configs/POKEMON_RUBY_AXVJ00/charmap.txt   # 单字节=日文PCS + F900/F980
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

# 图像加载器断点 —— 全部在日版 AXVJ 上反汇编行为核实（tools/pokeruby-jp/ADDRS.md）：
BP_LZ_WRAM = 0x0800A764   # LZDecompressWram → 0x081B129C（svc 0x11）
BP_LZ_VRAM = 0x0800A770   # LZDecompressVram → 0x081B1298（svc 0x12）
BP_SPRITE_SHEET = 0x080021C4    # LoadSpriteSheet: AllocSpriteTiles(0x08001074)
                                # + AllocSpriteTileRange(0x08002390) + CpuCopy16→0x06010000
BP_SPRITE_PALETTE = 0x08002410  # LoadSpritePalette: IndexOfSpritePaletteTag(0x080024D0)
                                # + CopyPalette(0x08002488)→gPlttBuffer* OBJ 区
BP_COMPRESSED_PIC = 0x0800A77C  # LoadCompressedObjectPic: LZ77W→0x02000000 + LoadSpriteSheet
BP_COMPRESSED_PAL = 0x0800A7D0  # LoadCompressedObjectPalette: LZ77W→0x02000000 + LoadSpritePalette
BP_COMPRESSED_PALETTE = 0x08070A4C  # LoadCompressedPalette: LZ→0x0202F0BC + 2×CpuCopy16
BP_LOAD_PALETTE = 0x08070A90        # LoadPalette: 2×CpuCopy16→gPlttBufferUnfaded/Faded

# 日版实测（US 假值≠日版，勿用 0x0202EAC8 等）：
JP_PAL_UNFADED = 0x0202E7E8     # gPlttBufferUnfaded（LoadPalette 目标 1）
JP_PAL_FADED = 0x0202EBE8       # gPlttBufferFaded（LoadPalette 目标 2）
JP_PAL_DECOMP_BUF = 0x0202F0BC  # sPaletteDecompressionBuffer（LoadCompressedPalette 中转）
JP_EWRAM_SCRATCH = 0x02000000   # LoadCompressedObject* 解压目标

# 缺省（未传 --functions）监听全部已注册函数，仅排除 ProcessCurrentChar：
# 它逐字符输出与 InitTextPrinter 块级解码冗余，需显式指定。
DEFAULT_EXCLUDE = {"ProcessCurrentChar"}

# F9 通道 / 短语表（hook/src/game.h + PrintNextChar_hook.c）：
#   F9 00 lead trail   = F900 通道，双字节汉字（查 charmap double）
#   F9 80 hi lo [FF]   = F980 通道，短语引用，code=(hi<<8)|lo
F9_PHRASE_DEFAULT = 0x80
ADDR_PHRASE_OFFSETS = 0x08810000   # u32[code] → 流内偏移（sentinel = total_size）
ADDR_PHRASE_TABLE = 0x08820000     # 短语流：F9 00×N + PCS 单字节 + 控制符 + FF


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


def decode_text(
    data: bytes,
    single: dict[int, str],
    double: dict[int, str],
    resolve_phrase: Optional[callable] = None,
    _depth: int = 0,
) -> str:
    """解码 FF 结尾文本：F9 00 lead trail → 查表；F9 80 → 短语流递归；
    控制码 → \\n/\\l/\\CC/\\v；非 F9 单字节 → 查 single（当前字库）。"""
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
            if i + 2 < n and resolve_phrase is not None and data[i + 1] == F9_PHRASE_DEFAULT:
                code = (data[i + 2] << 8) | data[i + 3]
                if _depth >= 4:
                    out.append(f"{{F9 80→短语{code:04X}(深度超限)}}")
                else:
                    stream = resolve_phrase(code)
                    if stream:
                        sub = decode_text(stream, single, double, resolve_phrase, _depth + 1)
                        out.append(f"{{F9 80→短语{code:04X}:{sub}}}")
                    else:
                        out.append(f"{{F9 80→短语{code:04X}:<查表失败>}}")
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
                from meowth.pcs_codes import fc_arg_count
                cmd = data[i + 1]
                end = i + 2 + fc_arg_count(cmd)
                if end <= n:
                    out.append("\\CC" + "".join(f"{x:02X}" for x in data[i + 1 : end]))
                    i = end
                    continue
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
        """有字库查表，无字库原样字节转义。F9 80 短语经 GDB 读短语表递归解码。"""
        if self.single or self.double:
            return decode_text(data, self.single, self.double, self._resolve_phrase)
        return raw_dump(data)

    def _resolve_phrase(self, code: int) -> Optional[bytes]:
        """从 GDB 实时 ROM 读短语流：PhraseOffsets[code] → PhraseTable+off → FF 结尾流。"""
        try:
            off_b = bytes(self.gdb.read_mem(ADDR_PHRASE_OFFSETS + code * 4, 4))
            if len(off_b) < 4:
                return None
            off = u32(off_b, 0)
            if off >= 0x01000000:
                return None
            stream = bytes(self.gdb.read_mem(ADDR_PHRASE_TABLE + off, STR_MAX))
        except GdbError:
            return None
        end = stream.find(0xFF)
        return stream[: end + 1] if end >= 0 else stream

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


def _read_mem(gdb: GdbClient, addr: int, n: int) -> bytes:
    try:
        return bytes(gdb.read_mem(addr, n))
    except GdbError:
        return b""


def _read_sheet(gdb: GdbClient, p: int) -> Optional[tuple[int, int, int]]:
    """读 {u32 data; u16 size; u16 tag}，失败返回 None。"""
    b = _read_mem(gdb, p, 8)
    if len(b) < 8:
        return None
    return u32(b, 0), u16(b, 4), u16(b, 6)


def _rom_head(ctx: Ctx, data: int, size: int) -> str:
    """ROM 源数据：给出原盘偏移与头字节，LZ77 头（0x10/0x11）标注。"""
    if region_of(data) != "ROM" or not ctx.origin:
        return ""
    fo = data - 0x08000000
    if not (0 <= fo < len(ctx.origin)):
        return ""
    n = min(max(size, 4), 32)
    h = ctx.origin[fo : fo + n]
    lz = " LZ77头" if h[:1] in (b"\x10", b"\x11") else ""
    return f"  原盘源 @0x{fo:08X}: {h.hex(' ')}{lz}"


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
    end = sp + len(data) - 1
    ctx.log(f"\n[InitTextPrinter] win=0x{win:08X} 文本=0x{sp:08X}~0x{end:08X} ({region_of(sp)}) LR=0x{lr:08X}")
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


def _mk_sheet_hook(name: str, bp: int, desc: str, rn: int = 0) -> None:
    """sheet 族加载器：r0/rn=&{u32 data; u16 size; u16 tag}，打印 data/size/tag + 区域。"""

    @register(name, bp, desc)
    def handler(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
        p = regs.get(f"r{rn}", 0)
        f = _read_sheet(gdb, p)
        if f is None:
            ctx.log(f"\n[{name}] 读 sheet 指针 0x{p:08X} 失败")
            return
        data, size, tag = f
        if not ctx._hit((name, data, size, tag)):
            return
        ctx.log(
            f"\n[{name}] sheet=0x{p:08X} data=0x{data:08X}({region_of(data)})"
            f" size=0x{size:04X} tag=0x{tag:04X} LR=0x{(regs.get('r14', 0) & ~1):08X}"
        )
        ctx.log(_rom_head(ctx, data, size))

    return handler


_mk_sheet_hook("LoadSpriteSheet", BP_SPRITE_SHEET, "图块 sheet → OBJ VRAM", 0)
_mk_sheet_hook("LoadSpritePalette", BP_SPRITE_PALETTE, "调色板 sheet → gPlttBuffer OBJ 区", 0)
_mk_sheet_hook("LoadCompressedObjectPic", BP_COMPRESSED_PIC,
               "LZ77→0x02000000 后 LoadSpriteSheet（r0=&压缩图）", 0)
_mk_sheet_hook("LoadCompressedObjectPalette", BP_COMPRESSED_PAL,
               "LZ77→0x02000000 后 LoadSpritePalette（r0=&压缩调色板）", 0)


@register("LoadCompressedPalette", BP_COMPRESSED_PALETTE,
          "压缩调色板：LZ→0x0202F0BC + 2×拷贝→gPlttBuffer*（r0=src, r1=offset, r2=size）")
def _on_compressed_palette(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    src = regs.get("r0", 0)
    off = regs.get("r1", 0) & 0xFFFF
    size = regs.get("r2", 0) & 0xFFFF
    if not ctx._hit(("LoadCompressedPalette", src, off, size)):
        return
    ctx.log(
        f"\n[LoadCompressedPalette] src=0x{src:08X}({region_of(src)})"
        f" offset=0x{off:04X} size=0x{size:04X} → 解压@0x{JP_PAL_DECOMP_BUF:08X}"
        f" → gPlttBuffer+0x{off:04X} LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, size))


@register("LoadPalette", BP_LOAD_PALETTE,
          "调色板 2×CpuCopy16→gPlttBufferUnfaded/Faded（r0=src, r1=offset, r2=size）")
def _on_load_palette(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    src = regs.get("r0", 0)
    off = regs.get("r1", 0) & 0xFFFF
    size = regs.get("r2", 0) & 0xFFFF
    if not ctx._hit(("LoadPalette", src, off, size)):
        return
    ctx.log(
        f"\n[LoadPalette] src=0x{src:08X}({region_of(src)})"
        f" offset=0x{off:04X} size=0x{size:04X} → 0x{JP_PAL_UNFADED + off:08X}"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, size))


@register("LZDecompressWram", BP_LZ_WRAM, "LZ77 解压到 EWRAM（r0=src, r1=dest）")
def _on_lz_wram(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    src = regs.get("r0", 0)
    dst = regs.get("r1", 0)
    if not ctx._hit(("LZ77W", src, dst)):
        return
    ctx.log(
        f"\n[LZDecompressWram] src=0x{src:08X}({region_of(src)})"
        f" → 0x{dst:08X}({region_of(dst)}) LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, 4))


@register("LZDecompressVram", BP_LZ_VRAM, "LZ77 解压到 VRAM（r0=src, r1=dest）")
def _on_lz_vram(gdb: GdbClient, regs: dict, ctx: Ctx) -> None:
    src = regs.get("r0", 0)
    dst = regs.get("r1", 0)
    if not ctx._hit(("LZ77V", src, dst)):
        return
    ctx.log(
        f"\n[LZDecompressVram] src=0x{src:08X}({region_of(src)})"
        f" → 0x{dst:08X}({region_of(dst)}) LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, 4))


def _select_hooks(names: Optional[str]) -> list[Hook]:
    """--functions 逗号分隔函数名；未注册的跳过并警告。缺省监听全部已注册函数
    （ProcessCurrentChar 除外，逐字符与 InitTextPrinter 冗余）。"""
    picked = [s.strip() for s in (names or "").split(",") if s.strip()]
    if not picked:
        return [FUNCTIONS[n] for n in sorted(FUNCTIONS) if n not in DEFAULT_EXCLUDE]
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
    from meowth.jp_pcs import BYTE_TO_CHAR as JP_BYTE_TO_CHAR
    single = dict(JP_BYTE_TO_CHAR)  # AXVJ 日版底包：非 F9 单字节一律按日文 PCS（假名）
    if args.charmap:
        _, double = load_charmap(args.charmap)
        mode = f"单字节=日文PCS + F900/F980 字库 {args.charmap}"
    else:
        mode = "单字节=日文PCS（未指定 --charmap 则 F900 双字节/短语不查表）"
    if args.jp:
        mode = mode.replace("单字节=日文PCS", "单字节=日文PCS(--jp 显式)")

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
        help="逗号分隔要监听的函数名，如 LoadSpriteSheet,LoadPalette / InitTextPrinter,"
        "ProcessCurrentChar；未指定则监听全部已注册函数（文本+图像，"
        "ProcessCurrentChar 除外）",
    )
    ap.add_argument(
        "--charmap",
        default=None,
        help="字库映射路径（如 configs/POKEMON_RUBY_AXVJ00/charmap.txt）；"
        "指定则查表解码文本，未指定按原始字节输出",
    )
    ap.add_argument(
        "--jp",
        action="store_true",
        help="(已为默认) 日文 PCS 单字节解码；因 ROM 为 AXVJ 日版底包，非 F9 单字节"
        "默认即按日文假名表转换，此开关仅为显式标注",
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