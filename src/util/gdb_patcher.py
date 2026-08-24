#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gdb_patcher.py — 基于 mGBA GDB stub 的运行时追踪工具（yaml 配置驱动）。

提供 `log` 命令：按「监听点」下断点，每次命中先打通用日志（PC/LR/r0-r3），
再可选跑该点注册的增强 handler。监听点全部来自
``src/util/configs/{gameId}.yaml`` 的 ``gdb:`` 列表 —— **加新监控点只需改
yaml，不改本文件**：

    gdb:
      - name: DrawMapNamePopup          # 监听点名（gdb_patcher 按 name 找增强 handler）
        address: '0x0809F654'           # 断点地址（"0x…" 字符串或整数）
        description: 地图名弹窗绘制入口  # 可选；通用日志描述
        default: false                  # 可选；false = 未传 --functions 时不启用
        cfg:                            # 可选；传给该 name handler 的自定义参数
          charmap: configs/POKEMON_RUBY_AXVJ00/charmap.txt

Python 侧只保留「按 name 注册的可选增强 handler」（``@handler("InitTextPrinter")``）。
yaml 有条目但无同名 handler → 仅通用日志；有 → 在通用日志后追加自定义输出。
``--functions`` 按名筛选；缺省监听全部 ``default != false`` 条目。

文本类增强（InitTextPrinter / ProcessCurrentChar）：
  - 非 F9 单字节：默认按日文 PCS 假名表解码（ROM 为 AXVJ 日版底包）
  - 该点 cfg.charmap / --charmap：F9 00 lead trail 汉字 + F9 80 短语流递归查表

用法：
  mGBA 打开 ROM，Tools → Start GDB stub（2345），Pause。
  python src/util/gdb_patcher.py log            # 全部 default 点（文本+图像）
  python src/util/gdb_patcher.py log --functions LoadSpriteSheet,LoadPalette
  python src/util/gdb_patcher.py log --functions InitTextPrinter,ProcessCurrentChar
   到目标界面操作，Ctrl-C 结束，分析 work/gdb_patcher_log.log。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from util.debug_patcher import GdbClient, GdbError, parse_gdb_hostport  # noqa: E402

DEFAULT_GDB = "127.0.0.1:2345"
DEFAULT_GAME = "POKEMON_RUBY_AXVJ00"
REPO_ROOT = Path(__file__).resolve().parents[2]
UTIL_CONFIGS = REPO_ROOT / "src" / "util" / "configs"
DEFAULT_ORIGIN = REPO_ROOT / "roms" / "origin" / f"{DEFAULT_GAME}.gba"
DEFAULT_LOG = REPO_ROOT / "work" / "gdb_patcher_log.log"

STR_MAX = 512

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
    resolve_phrase: Optional[Callable] = None,
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


# ---------------------------------------------------------------------------
# 监听点配置加载（src/util/configs/{gameId}.yaml → gdb: 列表）


@dataclass
class GdbPoint:
    """一个 yaml 监听点：断点地址 + 描述 + default 开关 + handler 自定义参数。"""

    name: str
    address: int
    description: str = ""
    enabled_by_default: bool = True
    cfg: dict[str, Any] = field(default_factory=dict)


def _parse_addr(v: Any) -> int:
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def resolve_game_yaml(game_id: str) -> Path:
    path = UTIL_CONFIGS / f"{game_id}.yaml"
    if not path.is_file():
        avail = ", ".join(p.stem for p in UTIL_CONFIGS.glob("*.yaml"))
        raise SystemExit(f"找不到游戏 yaml: {path}\n可用: {avail}")
    return path


def load_gdb_points(game_id: str) -> list[GdbPoint]:
    """读 yaml 的 gdb: 列表；缺段/空列表按无监听点处理。"""
    import yaml

    data = yaml.safe_load(resolve_game_yaml(game_id).read_text(encoding="utf-8")) or {}
    entries = data.get("gdb") or []
    points: list[GdbPoint] = []
    for e in entries:
        if not isinstance(e, dict):
            raise SystemExit(f"gdb 条目必须是映射: {e!r}")
        if "name" not in e or "address" not in e:
            raise SystemExit(f"gdb 条目缺 name/address: {e!r}")
        name = str(e["name"]).strip()
        if not name:
            raise SystemExit(f"gdb 条目 name 为空: {e!r}")
        if any(p.name == name for p in points):
            raise SystemExit(f"gdb 条目重名: {name}")
        points.append(
            GdbPoint(
                name=name,
                address=_parse_addr(e["address"]),
                description=str(e.get("description") or ""),
                enabled_by_default=e.get("default") is not False,
                cfg=dict(e.get("cfg") or {}),
            )
        )
    return points


# ---------------------------------------------------------------------------
# 按 name 注册的可选增强 handler（yaml 无同名条目则不会执行）


HandlerFn = Callable[[GdbClient, dict, Ctx, dict[str, Any]], None]

HANDLERS: dict[str, HandlerFn] = {}


def handler(name: str):
    """把函数登记为监听点 ``name`` 的增强 handler（签名见 HandlerFn）。"""

    def deco(fn: HandlerFn) -> HandlerFn:
        HANDLERS[name] = fn
        return fn

    return deco


def _read_win(gdb: GdbClient, win: int) -> bytes:
    try:
        b = bytes(gdb.read_mem(win, 0x20))
    except GdbError:
        return b""
    return b[:0x20]


def _win_fields(wb: bytes) -> str:
    """TextPrinter 关键字段一行摘要（AXVJ 布局，偏移同 hook/src/game.h）。"""
    if len(wb) < 0x1E:
        return f"（win 读取失败 len={len(wb)}）"
    return (
        f"state={u16(wb, 0x04)} textMode={wb[0x0A]} fontNum={wb[0x0B]}"
        f" 色C/D/E={wb[0x0C]}/{wb[0x0D]}/{wb[0x0E]} pal={wb[0x0F]}"
        f" TILE_BASE=0x{u16(wb, 0x16):04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
        f" curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
        f" index={u16(wb, 0x14)}"
    )


def _read_win_us(gdb: GdbClient, win: int) -> bytes:
    """美版 pokeruby struct Window（0x30 字节）。"""
    try:
        b = bytes(gdb.read_mem(win, 0x30))
    except GdbError:
        return b""
    return b[:0x30]


def _win_fields_us(wb: bytes) -> str:
    """pokeruby struct Window 字段摘要（include/text.h 布局）。"""
    if len(wb) < 0x2C:
        return f"（win 读取失败 len={len(wb)}）"
    return (
        f"state={u16(wb, 0x16)} textMode={wb[0x00]} fontNum={wb[0x01]} lang={wb[0x02]}"
        f" 色fg/bg/sh={wb[0x03]}/{wb[0x04]}/{wb[0x05]} pal={wb[0x06]}"
        f" startOff=0x{u16(wb, 0x1A):04X} tileOff=0x{u16(wb, 0x1C):04X}"
        f" curX={wb[0x10]} curY={wb[0x11]} left={wb[0x12]} top={u16(wb, 0x14)}"
        f" index={u16(wb, 0x1E)}"
    )


def _win_dump_str(gdb: GdbClient, win: int, layout: str) -> str:
    """按布局读取窗口并返回摘要行。"""
    wb = _read_win_us(gdb, win) if layout == "us" else _read_win(gdb, win)
    head = _win_fields_us(wb) if layout == "us" else _win_fields(wb)
    return head


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


# 地名弹窗居中钩指纹（v4）：push{r0,lr}; bl; adds r2,r0; pop{r0,r3}; movs r1,#1; adds; ldr r3; bx
_POPUP_TRAMP_V3 = bytes.fromhex("01b501f001fd021c09bc01218918034b1847")

_STEP_TRACE_LEFT = 3  # PopupStepTrace 只细抓前 N 次命中


@handler("PopupStepTrace")
def _on_popup_step(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """跳板入口处对整个居中钩子做指令级单步跟踪（GDB 's' 包），一锤定音。"""
    global _STEP_TRACE_LEFT
    if _STEP_TRACE_LEFT <= 0:
        return
    _STEP_TRACE_LEFT -= 1
    idx = 3 - _STEP_TRACE_LEFT
    buf = regs.get("r0", 0)
    data = _read_ff_text(gdb, buf)
    ctx.log(f"[单步#{idx}] 入口 PC=0x{regs.get('r15', 0) & ~1:08X} "
            f"r0=buf@0x{buf:08X}: {data[:20].hex(' ')}")
    tramp_lo, tramp_hi = 0x08800144, 0x08800160
    c_lo, c_hi = 0x08801B4C, 0x08801C10
    lines: list[str] = []
    for i in range(600):
        try:
            gdb.cmd("s")
            rr = gdb.read_regs()
        except GdbError as e:
            lines.append(f"s{i:03d} GDB 错误: {e}")
            break
        pc = rr.get("r15", 0) & ~1
        lines.append(f"s{i:03d} PC={pc:08X} r0={rr.get('r0', 0):X} r1={rr.get('r1', 0):X}"
                     f" r2={rr.get('r2', 0):X} r3={rr.get('r3', 0):X}")
        in_hook = (tramp_lo <= pc < tramp_hi) or (c_lo <= pc < c_hi)
        if not in_hook and pc >= 0x08000000:
            lines.append(f"→ 钩子结束（回到游戏 0x{pc:08X}），共 {i+1} 步")
            break
    for l in lines:
        ctx.log("  " + l)


@handler("MapNamePopupX")
def _on_popup_x(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """MenuPrint 调用点：缓冲区内容 + 运行中 ROM 的钩子指纹比对。"""
    buf = regs.get("r0", 0)
    data = _read_ff_text(gdb, buf)
    ctx.log(f"  缓冲区@0x{buf:08X}: {data[:24].hex(' ')} 内容={ctx.text_of(data)[:40]!r}")
    tramp = _read_mem(gdb, 0x08800144, 0x20)
    if tramp.startswith(_POPUP_TRAMP_V3):
        lit = int.from_bytes(tramp[0x1C:0x20], "little")
        ctx.log(f"  运行中ROM跳板 = v3 ✓ 落点字面量=0x{lit:08X} (应为 0x0809F6CF)")
    else:
        ctx.log(f"  运行中ROM跳板 ≠ v3！实际: {tramp.hex(' ')}")
        ctx.log("  → mGBA 加载的不是最新打包 ROM（重开 ROM 再测）")
    # C 函数尾部分歧点：v4=…lsrs#1;adds#4;lsrs#3（返回格数）
    tail = _read_mem(gdb, 0x08801B6C, 10)
    ctx.log(f"  C尾部@0x08801B6C: {tail.hex(' ')} (v5期望 a0 20 40 1a 40 08 04 30 40 0b)")


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


# 日版实测（US 假值≠日版，勿用 0x0202EAC8 等）：
JP_PAL_UNFADED = 0x0202E7E8     # gPlttBufferUnfaded（LoadPalette 目标 1）
JP_PAL_DECOMP_BUF = 0x0202F0BC  # sPaletteDecompressionBuffer（LoadCompressedPalette 中转）


@handler("InitTextPrinter")
def _on_init_text(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
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
    if cfg.get("layout") == "us":
        wb = _read_win_us(gdb, win)
        if len(wb) >= 0x2C:
            ctx.log(f"  r2.startOff=0x{tb:04X} r3.left={cx}")
            ctx.log(f"  {_win_fields_us(wb)}")
            tpl = u32(wb, 0x2C)
            tplt = _read_mem(gdb, tpl, 0x18) if tpl else b""
            if len(tplt) >= 0x18:
                ctx.log(
                    f"  模板@0x{tpl:08X}: charBase={tplt[1]} screenBase={tplt[2]}"
                    f" fg/bg/sh={tplt[5]}/{tplt[6]}/{tplt[7]} pal={tplt[4]}"
                    f" font={tplt[8]} textMode={tplt[9]} spacing={tplt[10]}"
                    f" tileData=0x{u32(tplt, 0x10):08X} tilemap=0x{u32(tplt, 0x14):08X}"
                )
        return
    wb = _read_win(gdb, win)
    if len(wb) >= 0x1E:
        ctx.log(f"  r2.tile_base=0x{tb:04X} r3.cur_x={cx}")
        ctx.log(f"  {_win_fields(wb)}")
        tpl = u32(wb, 0x00)
        tplt = _read_mem(gdb, tpl, 0x14) if tpl else b""
        if len(tplt) == 0x14:
            ctx.log(
                f"  模板@0x{tpl:08X}: charBase={tplt[1]} pal={tplt[4]}"
                f" C/D/E={tplt[5]}/{tplt[6]}/{tplt[7]}"
                f" font={tplt[8]} textMode={tplt[9]} spacing={tplt[10]}"
                f" tileData=0x{u32(tplt, 0x0C):08X} tilemap=0x{u32(tplt, 0x10):08X}"
            )
        # 模板全量：本次打印真正会生效的 textMode/fontNum/颜色/tileData/tilemap
        tpl = u32(wb, 0x00)
        tplt = _read_mem(gdb, tpl, 0x14) if tpl else b""
        if len(tplt) == 0x14:
            ctx.log(
                f"  模板@0x{tpl:08X}: charBase={tplt[1]} pal={tplt[4]}"
                f" C/D/E={tplt[5]}/{tplt[6]}/{tplt[7]}"
                f" font={tplt[8]} textMode={tplt[9]} spacing={tplt[10]}"
                f" tileData=0x{u32(tplt, 0x0C):08X} tilemap=0x{u32(tplt, 0x10):08X}"
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


@handler("ProcessCurrentChar")
def _on_char(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
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
    ctx.log(f"  {_win_fields(wb)}")


@handler("PrintNextChar")
def _on_pnc_entry(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """字符处理器入口：此刻 index 未推进，text[index] 即即将处理的字符。
    FA..FF 控制码只在入口可见。JP：r0=win, index@+0x14 text@+0x10；
    US：r0=win, index@+0x1E text@+0x20。"""
    us = cfg.get("layout") == "us"
    win = regs.get("r0", 0)
    wb = _read_win_us(gdb, win) if us else _read_win(gdb, win)
    isz, tsz = (0x1E, 0x20) if us else (0x14, 0x10)
    if len(wb) >= tsz + 4:
        index = u16(wb, isz)
        tptr = u32(wb, tsz)
        cur = (tptr + index) & 0xFFFFFFFF
    else:
        index = 0
        cur = 0
    if not ctx._hit((win, cur)):
        return
    data = _read_mem(gdb, cur, 24) if cur else b""
    lr = regs.get("r14", 0) & ~1
    ctx.log(
        f"\n[PncEntry] win=0x{win:08X} LR=0x{lr:08X}"
        f" 即将处理@0x{cur:08X}({region_of(cur)}) index={index}"
    )
    ctx.log(f"  {_win_fields_us(wb) if us else _win_fields(wb)}")
    ctx.log(f"  字节流: {data.hex(' ')}")


@handler("WinDump")
def _on_win_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """通用窗口现场（控制码跳表处理器/箭头/清屏共用）。
    cfg.winreg 指定存 win 的寄存器；layout=us 走 pokeruby struct Window。"""
    wr = str(cfg.get("winreg") or "r4")
    win = regs.get(wr, 0)
    ch = regs.get("r3", 0) & 0xFF
    us = cfg.get("layout") == "us"
    wb = _read_win_us(gdb, win) if us else _read_win(gdb, win)
    pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
    ctx.log(f"\n[WinDump] PC=0x{pc:08X} {wr}=win@0x{win:08X} r3=0x{ch:02X}")
    ctx.log(f"  {_win_fields_us(wb) if us else _win_fields(wb)}")


@handler("UpdateTilemap")
def _on_update_tilemap(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """BG 表项写入总入口。JP：r0=win, r1=upperTile, r2=lowerTile；
    US：r0=win, r1=tilesWidth（pokeruby UpdateTilemap(win, tilesWidth)）。
    记录目标格/写入前现值——定位乱码格来源。"""
    us = cfg.get("layout") == "us"
    wr = str(cfg.get("winreg") or "r0")
    win = regs.get(wr, 0)
    lr = regs.get("r14", 0) & ~1
    who = "C引擎" if 0x08800000 <= lr < 0x09000000 else "原生ROM"
    if us:
        wb = _read_win_us(gdb, win)
        if len(wb) < 0x2C:
            return
        width = regs.get("r1", 0) & 0xFFFF
        tmap = u32(wb, 0x28)
        cx = wb[0x12] + wb[0x10]          # left + cursorX（像素）
        cy = u16(wb, 0x14) + wb[0x11]     # top + cursorY
        cell = (cy >> 3) * 32 + (cx >> 3)
        key = (win, cell, width)
        if not ctx._hit(key):
            return
        entry = (tmap + cell * 2) if tmap else 0
        curv = _read_mem(gdb, entry, 2) if entry else b""
        ctx.log(
            f"\n[UTM-US] win=0x{win:08X} tilesWidth={width} 调用方={who} LR=0x{lr:08X}"
            f" 格=({cx},{cy})->#{cell} pal={wb[0x06]}"
        )
        ctx.log(f"  tilemap@0x{tmap:08X} entry@0x{entry:08X} 写前现值={curv.hex(' ')}")
        return
    up = regs.get("r1", 0) & 0xFFFF
    lo = regs.get("r2", 0) & 0xFFFF
    wb = _read_win(gdb, win)
    if len(wb) < 0x1E:
        return
    tpl = u32(wb, 0x00)
    tb = _read_mem(gdb, tpl + 0x10, 4) if tpl else b""
    tbase = u32(tb, 0) if len(tb) == 4 else 0
    cx, tx = wb[0x1A], wb[0x1B]
    cy, ty = wb[0x1C], wb[0x1D]
    cell = (cy + ty) * 32 + (cx + tx)
    key = (win, cell, up, lo)
    if not ctx._hit(key):
        return
    entry_addr = (tbase + cell * 2) if tbase else 0
    curv = _read_mem(gdb, entry_addr, 2) if entry_addr else b""
    tdata = _read_mem(gdb, tpl + 0x0C, 4) if tpl else b""
    tdata_base = u32(tdata, 0) if len(tdata) == 4 else 0
    ctx.log(
        f"\n[UTM] win=0x{win:08X} u=0x{up:04X} l=0x{lo:04X}"
        f" 格=({cx}+{tx},{cy}+{ty})->#{cell} pal=0x{wb[0x0F]:X} 调用方={who} LR=0x{lr:08X}"
    )
    ctx.log(
        f"  tilemap@0x{tbase:08X} entry@0x{entry_addr:08X} 写前现值={curv.hex(' ')}"
        f" tileData@0x{tdata_base:08X} 像素落点=0x{tdata_base + up * 32:08X}"
    )
    ctx.log(
        f"  tilemap@0x{tbase:08X} entry@0x{entry_addr:08X} 写前现值={curv.hex(' ')}"
        f" tileData@0x{tdata_base:08X} 像素落点=0x{tdata_base + up * 32:08X}"
    )


@handler("RenderTextHandleBold")
def _on_render_bold(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版 RenderTextHandleBold 链（Text_InitWindow8004E3C）：
    r0=winTemplate, r1=tileData(dest), r2=text。详情页/血条缓冲观测。"""
    tpl = regs.get("r0", 0)
    dst = regs.get("r1", 0)
    text = regs.get("r2", 0)
    data = _read_ff_text(gdb, text)
    tplt = _read_mem(gdb, tpl, 0x18) if tpl else b""
    lr = regs.get("r14", 0) & ~1
    if not ctx._hit((dst, data[:32])):
        return
    ctx.log(f"\n[RenderBold] dest=0x{dst:08X} text=0x{text:08X} LR=0x{lr:08X}")
    if len(tplt) >= 0x18:
        ctx.log(
            f"  模板@0x{tpl:08X}: charBase={tplt[1]} font={tplt[8]} textMode={tplt[9]}"
            f" fg/bg/sh={tplt[5]}/{tplt[6]}/{tplt[7]} pal={tplt[4]}"
            f" tileData=0x{u32(tplt, 0x10):08X} tilemap=0x{u32(tplt, 0x14):08X}"
        )
    ctx.log(f"  文本: {data[:48].hex(' ')} 内容={ctx.text_of(data)[:40]!r}")


@handler("InitWindowTileData")
def _on_iwtd(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """分区器入口（JP 0x08002A50，与美版同址；fontNum 跳表 7 项实证）。
    r0=win 或 template（运行时定身份），r1=startOffset。
    记录分区链输入 + r0 两种解释的内存现场。"""
    r0 = regs.get("r0", 0)
    off = regs.get("r1", 0) & 0xFFFF
    r2 = regs.get("r2", 0) & 0xFFFFFFFF
    r3 = regs.get("r3", 0) & 0xFF
    if not ctx._hit(("iwtd", r0, off)):
        return
    ctx.log(
        f"\n[IWTD] r0=0x{r0:08X} startOffset(r1)=0x{off:04X}"
        f" r2=0x{r2:08X} r3=0x{r3:02X}"
    )
    b = _read_mem(gdb, r0, 0x14)
    if not b:
        ctx.log("  （r0 内存读取失败）")
        return
    ctx.log(
        f"  [r0+8/9/A/B] font?=0x{b[8]:02X} textMode?=0x{b[9]:02X}"
        f" +A=0x{b[0x0A]:02X} +B=0x{b[0x0B]:02X}"
    )
    ctx.log(f"  [r0+0xC..F] = 0x{u32(b, 0x0C):08X}（tileData 候选）")
    tpl_ptr = u32(b, 0x00)
    if 0x02000000 <= tpl_ptr < 0x03008000 or 0x08000000 <= tpl_ptr < 0x08800000:
        tplt = _read_mem(gdb, tpl_ptr, 0x14)
        if len(tplt) == 0x14:
            ctx.log(
                f"  [按win解释] 模板@0x{tpl_ptr:08X}: charBase={tplt[1]} font={tplt[8]}"
                f" textMode={tplt[9]} spacing={tplt[10]}"
                f" tileData=0x{u32(tplt, 0x0C):08X} tilemap=0x{u32(tplt, 0x10):08X}"
            )
    if len(b) >= 0x14:
        ctx.log(
            f"  [按template解释 r0] charBase={b[1]} font={b[8]} textMode={b[9]}"
            f" spacing={b[10]} tileData=0x{u32(b, 0x0C):08X} tilemap=0x{u32(b, 0x10):08X}"
        )


@handler("InitWindowTileDataRet")
def _on_iwtd_ret(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """分区器出口（JP 0x08002AEA pop{r4-r6} 前）：r0=返回值=下一空闲 offset，
    r4=入口 r0。与入口成对即可还原场景分区链。"""
    ret = regs.get("r0", 0) & 0xFFFFFFFF
    r4 = regs.get("r4", 0)
    if not ctx._hit(("iwtret", r4, ret)):
        return
    ctx.log(f"\n[IWTD-Ret] r0(下一空闲)=0x{ret:08X} r4=0x{r4:08X}")


@handler("GetGlyphTilePointers")
def _on_ggtp(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版 GetGlyphTilePointers(fontNum, language, glyph, &upper, &lower)。"""
    fn_ = regs.get("r0", 0) & 0xFFFF
    lang = regs.get("r1", 0) & 0xFFFF
    gl = regs.get("r2", 0) & 0xFFFF
    if not ctx._hit((fn_, lang, gl)):
        return
    ctx.log(f"\n[GGTP] fontNum={fn_} language={lang} glyph=0x{gl:02X}")


@handler("Text_UpdateWindow")
def _on_tuw(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版帧驱动 Text_UpdateWindow(r0=win)：state 机观测。"""
    win = regs.get("r0", 0)
    wb = _read_win_us(gdb, win)
    if len(wb) < 0x2C:
        return
    if not ctx._hit((win, u16(wb, 0x16))):
        return
    ctx.log(f"\n[TUW] win=0x{win:08X} {_win_fields_us(wb)}")


@handler("BattleBufferGlyph")
def _on_buf_glyph(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """我方 TextMode2 缓冲写入观测：r0=win, r1=&ChsGlyphTiles, r2=width。
    记录 win[0x20] 目标指针、写入前缓冲头 16B、tiles->tl 源头 16B——
    用于定位血条 Lv/HP 行闪烁残片的落点错位。"""
    wr = str(cfg.get("winreg") or "r0")
    win = regs.get(wr, 0)
    tiles = regs.get("r1", 0)
    w = regs.get("r2", 0) & 0xFFFF
    wb = _read_win(gdb, win)
    dst = u32(wb, 0x20) if len(wb) >= 0x24 else 0
    tl_ptr_b = _read_mem(gdb, tiles, 4) if tiles else b""
    tl = u32(tl_ptr_b, 0) if len(tl_ptr_b) == 4 else 0
    dst_head = _read_mem(gdb, dst, 16) if dst else b""
    src_head = _read_mem(gdb, tl, 16) if tl else b""
    lr = regs.get("r14", 0) & ~1
    if not ctx._hit((win, dst)):
        return
    ctx.log(
        f"\n[Buf2] win=0x{win:08X} w={w} dst=0x{dst:08X} LR=0x{lr:08X}"
        f" textMode={wb[0x0A] if len(wb)>0x0A else '?'} fontNum={wb[0x0B] if len(wb)>0x0B else '?'}"
    )
    ctx.log(f"  写前dst头16B: {dst_head.hex(' ')}")
    ctx.log(f"  源tl头16B:    {src_head.hex(' ')}")


_TILES_HARVESTER: Optional["TilesHarvester"] = None  # run_log 构造后由 handler 运行时读取


def _mk_sheet_handler(name: str) -> HandlerFn:
    """sheet 族加载器：r0=&{u32 data; u16 size; u16 tag}，打印 data/size/tag + 区域。"""

    @handler(name)
    def fn(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
        p = regs.get("r0", 0)
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
        if _TILES_HARVESTER is not None:
            if name in ("LoadSpriteSheet", "LoadCompressedObjectPic"):
                _TILES_HARVESTER.on_sheet(name, regs)
            elif name in ("LoadSpritePalette", "LoadCompressedObjectPalette"):
                _TILES_HARVESTER.on_sprite_palette(name, regs)

    return fn


for _sheet_name in (
    "LoadSpriteSheet",
    "LoadSpritePalette",
    "LoadCompressedObjectPic",
    "LoadCompressedObjectPalette",
):
    _mk_sheet_handler(_sheet_name)


@handler("LoadCompressedPalette")
def _on_compressed_palette(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
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


@handler("LoadPalette")
def _on_load_palette(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
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


@handler("CreateSprite")
def _on_create_sprite(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    p = regs.get("r0", 0)
    if not ctx._hit(("CreateSprite", p)):
        return
    ctx.log(
        f"\n[CreateSprite] template=0x{p:08X}({region_of(p)})"
        f" x={regs.get('r1', 0):#06x} y={regs.get('r2', 0):#06x}"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    if _TILES_HARVESTER is not None:
        _TILES_HARVESTER.on_create_sprite(regs)


@handler("LZDecompressWram")
def _on_lz_wram(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    src = regs.get("r0", 0)
    dst = regs.get("r1", 0)
    if not ctx._hit(("LZ77W", src, dst)):
        return
    ctx.log(
        f"\n[LZDecompressWram] src=0x{src:08X}({region_of(src)})"
        f" → 0x{dst:08X}({region_of(dst)}) LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, 4))


@handler("LZDecompressVram")
def _on_lz_vram(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    src = regs.get("r0", 0)
    dst = regs.get("r1", 0)
    if not ctx._hit(("LZ77V", src, dst)):
        return
    ctx.log(
        f"\n[LZDecompressVram] src=0x{src:08X}({region_of(src)})"
        f" → 0x{dst:08X}({region_of(dst)}) LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(_rom_head(ctx, src, 4))


# ---------------------------------------------------------------------------
# tiles 实时采集 v2（登记 + 绑定，反汇编定案见 docs）：
#   LoadSpriteSheet / LoadCompressedObjectPic → tag 登记像素资产
#   LoadSpritePalette / LoadCompressedObjectPalette → tag 登记调色板源
#   CreateSprite 读 SpriteTemplate{tileTag@0, paletteTag@2, oam@4}
#   （AXVJ 布局，已反汇编证实；美版布局不同勿混用）
#   三件套齐 → 权威尺寸 + 未渐变 ROM 调色板 → 导出 PNG + 写 preset；
#   缺任一环仅记日志不落盘。跨局按 preset 配置 md5 指纹去重，不一致覆盖重导。

# OAM attr0 bit14-15 形状 / attr1 bit14-15 尺寸档 → (宽, 高) 像素
# （标准 GBA 表：方形 8/16/32/64；宽形 16x8..64x32；高形 8x16..32x64）
OAM_SIZE_TABLE = {
    (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64),
}

TILE_4BPP = 32
TILE_8BPP = 64


class PendingSheet:
    """登记的 sheet 资产（tag 唯一）。"""

    def __init__(self, name: str, data_addr: int, size: int, tag: int,
                 raw: bytes, compression: str):
        self.name = name
        self.data_addr = data_addr
        self.size = size
        self.tag = tag
        self.raw = raw
        self.compression = compression


class TilesHarvester:
    """tiles 实时采集器 v2（登记 + 绑定）。

    Load* 埋点登记资产：sheets[tag]={ROM 数据}, pal_by_tag[tag]=ROM 源；
    CreateSprite 埋点读 SpriteTemplate 得 (tileTag, paletteTag, 权威 w/h/is8)
    并落 bindings。三件套齐 → 导出 PNG + 写 preset；缺环仅记日志不落盘。
    跨局按 preset 配置 md5 指纹比对，不一致覆盖重导，一致跳过。
    """

    def __init__(
        self,
        gdb: GdbClient,
        game_yaml: Path,
        out_dir: Path,
        origin: Optional[bytes],
        log: Callable[[object], None],
        enabled: bool = True,
    ):
        self.gdb = gdb
        self.game_yaml = game_yaml
        self.out_dir = out_dir
        self.origin = origin
        self.log = log
        self.enabled = enabled
        self.sheets: dict[int, PendingSheet] = {}    # tileTag → sheet 资产
        self.bindings: dict[int, tuple] = {}         # tileTag → (paletteTag, (w,h,is8)|None)
        self.pal_by_tag: dict[int, int] = {}         # paletteTag → ROM src
        self.exported_addrs: set[int] = set()        # 本局已导 ROM 地址
        self.known_md5: dict[str, Optional[str]] = self._load_known_md5()  # 跨局指纹
        self.stats = {"captured": 0, "paired": 0, "skipped": 0, "failed": 0}

    @staticmethod
    def _preset_md5(cfg: dict) -> str:
        import hashlib
        import json

        payload = json.dumps(cfg, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"))
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    def _load_known_md5(self) -> dict[str, Optional[str]]:
        """启动时读一次 yaml：地址(小写) → 已存 preset 的配置指纹（无则 None）。"""
        try:
            import yaml

            data = yaml.safe_load(self.game_yaml.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        presets = (data.get("tiles") or {}).get("presets") or []
        out: dict[str, Optional[str]] = {}
        for p in presets:
            if isinstance(p, dict) and p.get("address"):
                out[str(p["address"]).lower()] = p.get("md5")
        return out

    # ---- 断点侧 ----

    def on_sheet(self, name: str, regs: dict) -> None:
        """LoadSpriteSheet / LoadCompressedObjectPic 命中：抓 sheet。"""
        if not self.enabled:
            return
        try:
            f = _read_sheet(self.gdb, regs.get("r0", 0))
            if f is None:
                return
            data_addr, size, tag = f
            if tag in self.sheets:
                return
            if size == 0 or size > 0x20000:
                self.stats["skipped"] += 1
                return
            if region_of(data_addr) != "ROM" or not self.origin:
                return  # EWRAM 中转副本无 preset 价值
            fo = data_addr - 0x08000000
            if not (0 <= fo < len(self.origin)):
                return
            head = self.origin[fo : fo + 4]
            if head[:1] in (b"\x10", b"\x11"):
                from util.tiles_patcher import lz77_decompress

                dst_size = head[1] | (head[2] << 8) | (head[3] << 16)
                # 头字节不区分 swap（本 ROM 0x10 + swap 是常态）；两种都试，以
                # 「解压成功且长度==头内 dst_size」为准（同 detect_lz77）。
                raw = None
                compression = ""
                for swap in (head[0] == 0x11, head[0] != 0x11):
                    try:
                        cand = lz77_decompress(self.origin[fo:], swap=swap)
                    except Exception:
                        continue
                    if len(cand) == dst_size:
                        raw = cand
                        compression = "lz77_swap" if swap else "lz77"
                        break
                if raw is None:
                    self.log(f"  [tiles] 解压失败 @0x{data_addr:08X}: 标准/swap 均不匹配 (dst_size={dst_size})")
                    self.stats["failed"] += 1
                    return
            else:
                raw = self.origin[fo : fo + size]
                compression = "none"
            ps = PendingSheet(name, data_addr, size, tag, raw, compression)
            self.sheets[tag] = ps
            self.stats["captured"] += 1
            self.log(f"  [tiles] 登记 sheet tag=0x{tag:04X} @0x{data_addr:08X} raw={len(raw)}B ({compression})")
            self.try_export(tag)
        except GdbError:
            pass

    def on_sprite_palette(self, name: str, regs: dict) -> None:
        """LoadSpritePalette / LoadCompressedObjectPalette 命中：登记调色板 ROM 源。
        结构体布局按名分支（pokeruby 定案）：裸版 {data, tag} 无 size，
        压缩版 {data, size, tag}——tag 偏移分别为 +4 / +6。"""
        if not self.enabled:
            return
        try:
            p = regs.get("r0", 0)
            head = self.gdb.read_mem(p, 8)
            src = u32(head, 0)
            tag_off = 6 if name == "LoadCompressedObjectPalette" else 4
            tag = u16(head, tag_off)
            if region_of(src) != "ROM" or not self.origin:
                return
            fo = src - 0x08000000
            if not (0 <= fo < len(self.origin)):
                return
            self.pal_by_tag[tag] = src
            self.log(f"  [tiles] 登记调色板 tag=0x{tag:04X} src=0x{src:08X}")
            for t, b in list(self.bindings.items()):
                if b[0] == tag:
                    self.try_export(t)
        except GdbError:
            pass

    def on_create_sprite(self, regs: dict) -> None:
        """CreateSprite 命中：读 SpriteTemplate{tileTag@0, paletteTag@2,
        oam*@4}（AXVJ 布局，反汇编定案）落绑定；oam 可读时给权威尺寸。"""
        if not self.enabled:
            return
        try:
            p = regs.get("r0", 0)
            head = self.gdb.read_mem(p, 8)
            tile_tag = u16(head, 0)
            pal_tag = u16(head, 2)
            oam_ptr = u32(head, 4)
            dims = None
            if region_of(oam_ptr) == "ROM":
                od = self.gdb.read_mem(oam_ptr, 4)
                a0 = u16(od, 0)
                a1 = u16(od, 2)
                wh = OAM_SIZE_TABLE.get(((a0 >> 14) & 0x3, (a1 >> 14) & 0x3))
                if wh:
                    dims = (wh[0], wh[1], bool(a0 & 0x2000))
            self.bindings[tile_tag] = (pal_tag, dims)
            bpp_s = ("8bpp" if dims[2] else "4bpp") if dims else "?"
            dim_s = f"{dims[0]}x{dims[1]}" if dims else "?"
            self.log(
                f"  [tiles] 绑定 tileTag=0x{tile_tag:04X} -> paletteTag=0x{pal_tag:04X}"
                f" ({dim_s} {bpp_s})"
            )
            self.try_export(tile_tag)
        except GdbError:
            pass

    def _decode_rom_palette(self, src: int) -> Optional[list[tuple]]:
        """从 ROM 源解出首个 bank（32B）的 16 色；自动识别 LZ77 压缩。"""
        from util.tiles_patcher import decode_palette_gba555, lz77_decompress

        if not self.origin:
            return None
        fo = src - 0x08000000
        if not (0 <= fo < len(self.origin)):
            return None
        head = self.origin[fo]
        raw = None
        if head in (0x10, 0x11):
            dst_size = (self.origin[fo + 1] | (self.origin[fo + 2] << 8)
                        | (self.origin[fo + 3] << 16))
            for swap in (head == 0x11, head != 0x11):
                try:
                    cand = lz77_decompress(self.origin[fo:], swap=swap)
                except Exception:
                    continue
                if len(cand) == dst_size:
                    raw = cand
                    break
        else:
            raw = self.origin[fo : fo + 32]
        if not raw:
            return None
        pal = decode_palette_gba555(raw[:32], bank_count=1)
        return pal[0] if pal and pal[0] else None

    def try_export(self, tile_tag: int) -> None:
        """三件套（sheet/绑定/调色板）齐 → 指纹比对 → 导出。缺环静默等待。"""
        if not self.enabled:
            return
        sh = self.sheets.get(tile_tag)
        b = self.bindings.get(tile_tag)
        if not sh or not b or sh.data_addr in self.exported_addrs:
            return
        pal_src = self.pal_by_tag.get(b[0])
        dims = b[1]
        if pal_src is None or not dims:
            return  # 绑定或调色板未到齐，等后续事件补齐
        palette = self._decode_rom_palette(pal_src)
        if not palette:
            self.log(
                f"  [tiles] 缺调色板 @0x{sh.data_addr:08X}"
                f" tag=0x{tile_tag:04X}：仅登记，不导出不写配置"
            )
            return
        w, h, is8 = dims
        bpp = 8 if is8 else 4
        bps = ((w // 8) * (h // 8)) * (TILE_8BPP if is8 else TILE_4BPP)
        count = max(1, len(sh.raw) // bps)
        addr_key = f"0x{sh.data_addr:08X}".lower()
        cfg = self._build_preset(sh, bpp, count, w, h)
        md5hex = self._preset_md5(cfg)
        if self.known_md5.get(addr_key) == md5hex:
            self.stats["skipped"] += 1  # 指纹一致：无需重导
            self.exported_addrs.add(sh.data_addr)
            return
        try:
            if not self._export(sh, w, h, is8, count, palette):
                self.stats["skipped"] += 1
                return
            self._upsert_preset(sh, cfg, md5hex)
            self.known_md5[addr_key] = md5hex
            self.exported_addrs.add(sh.data_addr)
            self.stats["paired"] += 1
        except Exception as e:
            self.log(f"  [tiles] 导出失败 @0x{sh.data_addr:08X}: {e}")
            self.stats["failed"] += 1

    def flush_observed(self) -> int:
        """会话收尾：报告已登记但三件套未齐的 sheet（不导出）。"""
        pend = sorted(
            f"0x{sh.data_addr:08X}(tag=0x{t:04X})"
            for t, sh in self.sheets.items()
            if sh.data_addr not in self.exported_addrs
        )
        if pend:
            self.log(f"  [tiles] 仅登记未导出 {len(pend)} 个：{', '.join(pend)}")
        return 0

    def _export(self, sh: PendingSheet, w: int, h: int, is8: bool,
                count: int, palette: list[tuple]) -> bool:
        """纯渲染落盘：调色板已由 try_export 按 tag 绑定解析。"""
        from PIL import Image

        from util.tiles_patcher import decode_tiles

        bpp = 8 if is8 else 4
        bytes_per_sprite = ((w // 8) * (h // 8)) * (TILE_8BPP if is8 else TILE_4BPP)
        if bytes_per_sprite <= 0:
            raise ValueError(f"sprite 尺寸非法 {w}x{h}")

        prefix = f"0x{sh.data_addr:08X}"
        png_path = self.out_dir / f"{prefix}.png"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        images = decode_tiles(sh.raw, bpp, w // 8, h // 8, count=count, palette=palette)

        if count == 1:
            images[0].save(png_path)
        else:
            cols = min(8, count)
            rows = (count + cols - 1) // cols
            sheet_img = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
            for i, img in enumerate(images):
                sheet_img.paste(img, ((i % cols) * w, (i // cols) * h))
            sheet_img.save(png_path)
        self.log(
            f"  [tiles] 导出 {png_path.name} ({count}×{w}×{h} {bpp}bpp,"
            f" 调色板=ROM 绑定 tag=0x{self.bindings.get(sh.tag, (0,))[0]:04X})"
        )
        return True

    @staticmethod
    def _build_preset(sh: PendingSheet, bpp: int, count: int,
                      w: int, h: int) -> dict:
        return {
            "id": f"rt_{sh.data_addr:08X}",
            "label": f"rt tag=0x{sh.tag:04X} {sh.name}",
            "default": False,
            "address": f"0x{sh.data_addr:08X}",
            "format": f"{bpp}bpp",
            "compression": sh.compression,
            "sprite_size": f"{w}x{h}",
            "count": count,
            "raw_size": len(sh.raw),
            "source": "gdb_patcher",
        }

    def _upsert_preset(self, sh: PendingSheet, cfg: dict, md5hex: str) -> None:
        """yaml 写回 preset：同地址已有则原位覆盖（指纹不一致才走到这），否则追加。"""
        import yaml

        try:
            data = yaml.safe_load(self.game_yaml.read_text(encoding="utf-8")) or {}
        except OSError as e:
            self.log(f"  [tiles] 读 yaml 失败: {e}")
            return
        tiles = data.get("tiles")
        if not isinstance(tiles, dict):
            tiles = {}
            data["tiles"] = tiles
        presets = tiles.get("presets")
        if not isinstance(presets, list):
            presets = []
            tiles["presets"] = presets
        addr_hex = str(cfg["address"])
        entry = dict(cfg)
        entry["md5"] = md5hex
        idx = next((i for i, p in enumerate(presets)
                    if str(p.get("address") or "").lower() == addr_hex.lower()), None)
        if idx is None:
            presets.append(entry)
            action = "追加"
        else:
            presets[idx] = entry
            action = "覆盖"
        try:
            from util.texts_patcher import save_yaml_config

            save_yaml_config(self.game_yaml, data)
            self.log(f"  [tiles] preset {action}: {cfg['id']} "
                     f"({cfg['count']}×{cfg['sprite_size']}) md5={md5hex[:8]}")
        except Exception as e:
            self.log(f"  [tiles] 写 yaml 失败: {e}")


def _tiles_out_dir(game_id: str) -> Path:
    return REPO_ROOT / "src" / "util" / "work" / game_id / "tiles"


# ---------------------------------------------------------------------------


@dataclass
class Hook:
    """合并后的监听点：yaml 配置 + 可选增强 handler。"""

    point: GdbPoint
    fn: Optional[HandlerFn]

    @property
    def name(self) -> str:
        return self.point.name

    @property
    def bp(self) -> int:
        return self.point.address


def resolve_hooks(points: list[GdbPoint], functions: Optional[str]) -> list[Hook]:
    """--functions 逗号分隔点名；未在 yaml 定义的跳过并警告。
    缺省取全部 ``default != false`` 条目。"""
    picked = [s.strip() for s in (functions or "").split(",") if s.strip()]
    by_name = {p.name: p for p in points}
    unknown: list[str] = []
    if not picked:
        picked = sorted(p.name for p in points if p.enabled_by_default)
    else:
        unknown = [n for n in picked if n not in by_name]
        picked = [n for n in picked if n in by_name]
    hooks = [Hook(by_name[n], HANDLERS.get(n)) for n in picked]
    if unknown:
        print(
            f"警告: yaml 未定义的监听点，跳过: {', '.join(unknown)}\n"
            f"已定义: {', '.join(sorted(by_name))}",
            file=sys.stderr,
        )
    return hooks


def generic_log(ctx: Ctx, hook: Hook, regs: dict) -> None:
    """通用日志行：所有监听点共用；无增强 handler 时是唯一输出。"""
    lr = regs.get("r14", 0) & ~1
    r0123 = " ".join(f"{k}=0x{regs.get(k, 0) & 0xFFFFFFFF:08X}" for k in ("r0", "r1", "r2", "r3"))
    desc = f" — {hook.point.description}" if hook.point.description else ""
    pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
    ctx.log(f"\n[{hook.name}]{desc}\n  PC=0x{pc:08X} LR=0x{lr:08X} {r0123}")


def _arm(ctx: Ctx, hook: Hook) -> bool:
    try:
        ctx.gdb.set_sw_break(hook.bp)
    except GdbError as e:
        ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} 失败: {e}")
        return False
    ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} OK")
    return True


def _pick_charmap(args: argparse.Namespace, points: list[GdbPoint]) -> str:
    """CLI --charmap 优先；否则取第一个带 cfg.charmap 的监听点（相对仓库根解析）。"""
    if args.charmap:
        return args.charmap
    for p in points:
        c = (p.cfg or {}).get("charmap")
        if c:
            return str((REPO_ROOT / str(c)).resolve())
    return ""


def run_log(args: argparse.Namespace) -> int:
    # 日志按游戏分目录：src/util/work/{gameId}/gdb_patcher_log.log
    logpath = args.log or str(REPO_ROOT / "src" / "util" / "work" / args.game / "gdb_patcher_log.log")
    Path(logpath).parent.mkdir(parents=True, exist_ok=True)

    points = load_gdb_points(args.game)
    hooks = resolve_hooks(points, args.functions)
    if not hooks:
        print("没有可监听的监听点（--functions 全部未在 yaml 定义？）。", file=sys.stderr)
        return 2

    if args.game == DEFAULT_GAME:
        from meowth.jp_pcs import BYTE_TO_CHAR as JP_BYTE_TO_CHAR

        single = dict(JP_BYTE_TO_CHAR)  # AXVJ 日版底包：非 F9 单字节按日文 PCS
        decode_mode = "日文PCS"
    else:
        single = {}                     # 非日版：原样字节，不做假名解码
        decode_mode = "原始字节（非日版不解码）"
    charmap_src = _pick_charmap(args, points)
    double: dict[int, str] = {}
    if charmap_src:
        _, double = load_charmap(charmap_src)
        mode = f"{decode_mode} + F900/F980 字库 {charmap_src}"
    else:
        mode = decode_mode

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

    global _TILES_HARVESTER
    _TILES_HARVESTER = None
    if args.no_tiles:
        tiles_note = "tiles 采集关闭 (--no-tiles)"
    else:
        game_yaml = resolve_game_yaml(args.game)
        _TILES_HARVESTER = TilesHarvester(
            gdb,
            game_yaml,
            _tiles_out_dir(args.game),
            origin,
            ctx.log,
        )
        tiles_note = f"tiles 采集开 → {game_yaml.name} / {_tiles_out_dir(args.game).name}/"

    ctx.log(
        f"\n===== gdb_patcher log @ {time.strftime('%H:%M:%S')}"
        f" [{args.game}: {', '.join(h.name for h in hooks)}] {mode} ====="
    )
    ctx.log(f"  {tiles_note}")

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
                continue
            generic_log(ctx, hook, regs)
            if hook.fn is not None:
                hook.fn(gdb, regs, ctx, hook.point.cfg)
    except KeyboardInterrupt:
        ctx.log("\n[用户中断]")
    finally:
        for h in armed:
            try:
                gdb.clear_sw_break(h.bp)
            except GdbError:
                pass
            except OSError:
                pass
        try:
            gdb.close()
        except OSError:
            pass
    if _TILES_HARVESTER is not None:
        _TILES_HARVESTER.flush_observed()
        s = _TILES_HARVESTER.stats
        unexported = sum(
            1 for sh in _TILES_HARVESTER.sheets.values()
            if sh.data_addr not in _TILES_HARVESTER.exported_addrs
        )
        ctx.log(
            f"  tiles 采集: 登记 {s['captured']}，导出 {s['paired']}，"
            f"跳过 {s['skipped']}，失败 {s['failed']}；仅登记未导出 {unexported}"
        )
    ctx.log(f"追踪结束，共 {n} 次命中。日志: {logpath}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description=(
            "基于 mGBA GDB stub 的运行时追踪（log 命令）。"
            "监听点来自 src/util/configs/{game}.yaml 的 gdb: 列表；"
            "加新监控点只需在 yaml 追加条目，Python 侧可按 name 注册增强 handler。"
        ),
    )
    ap.add_argument("cmd", choices=["log"], help="log：追踪 yaml 定义的监听点")
    ap.add_argument(
        "--game",
        default=DEFAULT_GAME,
        help=f"游戏 id（读 src/util/configs/{{game}}.yaml，默认 {DEFAULT_GAME}）",
    )
    ap.add_argument(
        "--functions",
        default=None,
        help="逗号分隔要监听的点名（须在 yaml gdb: 中定义）；缺省监听全部 default != false 条目",
    )
    ap.add_argument("--charmap", default=None, help="字库映射路径；覆盖各监听点的 cfg.charmap")
    ap.add_argument("--gdb", default=DEFAULT_GDB, help="host:port（默认 127.0.0.1:2345）")
    ap.add_argument("--limit", type=int, default=3000, help="最多命中次数")
    ap.add_argument("--cont-timeout", type=float, default=600.0, help="每次 continue 等待秒数")
    ap.add_argument("--no-dedup", action="store_true", help="关闭连续重复去重")
    ap.add_argument(
        "--no-tiles",
        action="store_true",
        help="关闭 tiles 实时采集（默认开：sheet→OAM 配对→导 PNG+追加 tiles.presets）",
    )
    ap.add_argument("--log", default=None,
                    help=r"日志文件路径；缺省 src\util\work\{gameId}\gdb_patcher_log.log（按游戏分目录）")
    ap.add_argument("--origin", default=str(DEFAULT_ORIGIN), help="原盘 ROM 路径（同址对照用；美版请传美版 ROM 路径）")
    args = ap.parse_args(argv)

    try:
        return run_log(args)
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
