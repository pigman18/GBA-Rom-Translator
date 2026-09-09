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
import re
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
        vram_survey: bool = False,
        cb_survey: bool = False,
        ui_survey: bool = False,
    ):
        self.gdb = gdb
        self.logpath = logpath
        self.single = single
        self.double = double
        self.origin = origin
        self.dedup = dedup
        self.vram_survey = vram_survey
        self.cb_survey = cb_survey
        self.ui_survey = ui_survey
        self._vram_sig: object = None
        self._cb_sig: object = None
        self._ui_sig: object = None
        self._cb3tail_sig: object = None
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
        f" w×h={wb[0x09]}×{wb[0x0A]}"
        f" startOff=0x{u16(wb, 0x1A):04X} tileOff=0x{u16(wb, 0x1C):04X}"
        f" curX={wb[0x10]} curY={wb[0x11]} left={wb[0x12]} top={u16(wb, 0x14)}"
        f" index={u16(wb, 0x1E)}"
        f" tileData=0x{u32(wb, 0x24):08X} tilemap=0x{u32(wb, 0x28):08X}"
    )


def _us_cursor_tile_num(wb: bytes, x_off: int, y_off: int) -> tuple[int, str]:
    """按 pokeruby GetCursorTileNum 公式推算 tile 号（对照实机）。
    textMode==2：BASE+OFF + 行*width + 列（文本画布）。
    其它：BASE+OFF + 2*xOff + yOff（仅字形 TL/TR 相对当前游标）。"""
    if len(wb) < 0x1E:
        return -1, "win短"
    tm = wb[0x00]
    base = u16(wb, 0x1A)
    off = u16(wb, 0x1C)
    width = wb[0x09]
    if tm == 2:
        row = ((u16(wb, 0x14) + wb[0x11]) >> 3) + y_off
        col = ((wb[0x12] + wb[0x10]) >> 3) + x_off
        idx = base + off + row * width + col
        return idx, f"tm2画布 row={row} col={col} w={width}"
    idx = base + off + 2 * x_off + y_off
    return idx, f"tm{tm}线性相对 xOff={x_off} yOff={y_off}"


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


# --- 战斗动画（battle_anim）诊断链 ------------------------------------------
# 针对「放技能偶发黑屏」：技能入口 → 脚本命令流 → tile/调色板写入 全链路留痕。
# 用法：原版 ROM 与汉化 ROM 各跑一次同存档同一技能，diff 两份日志。
#
# 地址来源与可信度（重要）：
#   • EWRAM 地址日美一致（pokeruby_jp.sym 标 KEEP-US），可直接读，最可靠。
#   • 代码函数地址来自 pokeruby_jp.sym，但该表标了 UNVERIFIED，实测其地址
#     普遍偏小（前面带着上一个函数的 literal pool），且每个函数偏移量不同：
#     DoMoveAnim +0x24 / LaunchBattleAnimation +0x20 / RunAnimScriptCommand +0x4 /
#     ScriptCmd_loadspritegfx +0x44 / ScriptCmd_restorebg +0x7c（其余多为 +0）。
#     本文件用的是「向后扫到第一个 push」修正后的函数头地址，
#     并已校验原版 ROM 与汉化 ROM 在这些点代码一致（两版可共用同一断点）。
#   • 静态勘验结论（2026-08-30）：gBattleAnims_Moves 表、动画脚本本体
#     （0x081D36DC-0x081D5900）、battle_anim 代码段，原版与汉化逐字节一致
#     ⇒ 黑屏不是静态数据被改坏，而是运行时行为差异，须靠本链路抓。

A_SCRIPT_PTR = 0x0202F7A4   # sBattleAnimScriptPtr  const u8*
A_RET_ADDR   = 0x0202F7A8   # gBattleAnimScriptRetAddr
A_CALLBACK   = 0x0202F7AC   # gAnimScriptCallback
A_FRAMES_WAIT= 0x0202F7B0   # u8
A_ACTIVE     = 0x0202F7B1   # u8  gAnimScriptActive
A_VIS_TASKS  = 0x0202F7B2   # u8  gAnimVisualTaskCount
A_SND_TASKS  = 0x0202F7B3   # u8  gAnimSoundTaskCount
A_MOVE_TURN  = 0x0202F7C4   # u8  gAnimMoveTurn
A_BG_FADE    = 0x0202F7C5   # u8  sAnimBackgroundFadeState
A_MOVE_INDEX = 0x0202F7C6   # u16 sAnimMoveIndex ← 当前技能 id
A_ATTACKER   = 0x0202F7C8   # u8  gBattleAnimAttacker
A_TARGET     = 0x0202F7C9   # u8  gBattleAnimTarget

# sScriptCmdTable 顺序（src/battle_anim.c），把命令字节翻成可读名字
ANIM_CMDS = (
    "loadspritegfx", "unloadspritegfx", "createsprite", "createvisualtask",
    "delay", "waitforvisualfinish", "hang1", "hang2", "end", "playse",
    "monbg", "clearmonbg", "setalpha", "blendoff", "call", "return",
    "setarg", "choosetwoturnanim", "jumpifmoveturn", "jump", "fadetobg",
    "restorebg", "waitbgfadeout", "waitbgfadein", "changebg", "playsewithpan",
    "setpan", "panse_1B", "loopsewithpan", "waitplaysewithpan", "setbldcnt",
    "createsoundtask", "waitsound", "jumpargeq", "monbg_22", "clearmonbg_23",
    "jumpifcontest", "fadetobgfromset", "panse_26", "panse_27", "monbgprio_28",
    "monbgprio_29", "monbgprio_2A", "invisible", "visible", "doublebattle_2D",
    "doublebattle_2E", "stopsound",
)

# 动到这几条命令就是「背景/调色板/混合」类，黑屏第一嫌疑
BG_RISKY_CMDS = {"fadetobg", "restorebg", "waitbgfadeout", "waitbgfadein",
                 "changebg", "setbldcnt", "setalpha", "blendoff", "monbg",
                 "clearmonbg", "monbg_22", "clearmonbg_23", "fadetobgfromset"}


def _anim_state(gdb: GdbClient) -> dict:
    """一次读完战斗动画 EWRAM 状态块（0x0202F7A4..0x0202F7CA）。读失败返回 {}。"""
    b = _read_mem(gdb, A_SCRIPT_PTR, 0x28)
    if len(b) < 0x28:
        return {}
    return {
        "ptr": u32(b, 0x00), "ret": u32(b, 0x04), "cb": u32(b, 0x08),
        "wait": b[0x0C], "active": b[0x0D], "vis": b[0x0E], "snd": b[0x0F],
        "turn": b[0x20], "bgfade": b[0x21], "move": u16(b, 0x22),
        "atk": b[0x24], "tgt": b[0x25],
    }


def _vram_zone(a: int) -> str:
    """VRAM 地址 → 人类可读区域。BG charblock 归属是黑屏定位的关键。"""
    if 0x06000000 <= a < 0x06010000:
        return f"BG-cb{(a - 0x06000000) // 0x4000}"
    if 0x06010000 <= a < 0x06018000:
        return "OBJ"
    if 0x06000000 <= a < 0x06018000:
        return "VRAM?"
    if 0x07000000 <= a < 0x07000400:
        return "OAM"
    if 0x05000000 <= a < 0x05000400:
        return "PAL"
    return ""


@handler("MoveAnimEntry")
def _on_move_anim_entry(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """DoMoveAnim 入口（r0=move）：技能动画总入口，一次出招命中一次。
    判读：两版日志里 move id 与 LR（调用方）应完全一致；不一致说明上游选技能就分叉了。"""
    move = regs.get("r0", 0) & 0xFFFF
    lr = regs.get("r14", 0) & ~1
    st = _anim_state(gdb)
    ctx.log(f"\n[MVA] DoMoveAnim move=#{move} LR=0x{lr:08X}")
    if st:
        ctx.log(f"  进入前状态: active={st['active']} move_index={st['move']} "
                f"wait={st['wait']} vis={st['vis']} ptr=0x{st['ptr']:08X}")


@handler("LaunchAnim")
def _on_launch_anim(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """LaunchBattleAnimation 入口（r0=表基址 r1=move r2=isMoveAnim）。
    核心是查出表结果：脚本指针 = [r0 + r1*4]。
    判读：表基址两版应相同（0x081D997C）；算出的脚本指针两版应相同
    （静态已确认 gBattleAnims_Moves 与脚本本体都没被汉化改动），
    若不同则说明运行时拿到了脏的 r0/r1。"""
    tab = regs.get("r0", 0) & 0xFFFFFFFF
    move = regs.get("r1", 0) & 0xFFFF
    is_move = regs.get("r2", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    ent = tab + move * 4
    pb = _read_mem(gdb, ent, 4)
    val = u32(pb, 0) if len(pb) == 4 else 0
    ctx.log(f"\n[LNA] LaunchBattleAnimation 表=0x{tab:08X} move=#{move} "
            f"isMoveAnim={is_move} LR=0x{lr:08X}")
    ctx.log(f"  表项 [0x{ent:08X}] = 0x{val:08X}"
            + ("  ← 非 ROM 区，指针可疑！" if not (0x08000000 <= val < 0x0A000000) else ""))


@handler("AnimScriptCmd")
def _on_anim_script_cmd(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """RunAnimScriptCommand 入口：动画脚本命令流主循环，每条命令命中一次。
    这是本链路的核心——把「技能 → 命令序列」完整录下来，两版逐条 diff。
    判读：原版与汉化的命令序列应完全一致；某命令突然乱掉/跳到非 ROM 区，
    就是黑屏点。BG_RISKY 类命令（fadetobg/changebg/setbldcnt…）重点看。"""
    st = _anim_state(gdb)
    if not st:
        return
    p = st["ptr"]
    if not (0x08000000 <= p < 0x0A000000):
        ctx.log(f"\n[ASC] !!! 脚本指针越界 0x{p:08X} move=#{st['move']} "
                f"（正常应落在 0x081Dxxxx 脚本区）")
        return
    stream = _read_mem(gdb, p, 12)
    cid = stream[0] if stream else 0xFF
    name = ANIM_CMDS[cid] if cid < len(ANIM_CMDS) else f"cmd#{cid}"
    risk = "  ⚠BG类" if name in BG_RISKY_CMDS else ""
    ctx.log(f"\n[ASC] move=#{st['move']} cmd[{cid}]={name}{risk} "
            f"turn={st['turn']} bgfade={st['bgfade']} wait={st['wait']} "
            f"vis={st['vis']} snd={st['snd']}")
    ctx.log(f"  脚本@0x{p:08X}: {stream.hex(' ')}")


# 循环体埋点的跨命中状态：用于检测「脚本指针是否推进」
_loop_prev: dict[str, int] = {"ptr": 0, "n": 0}


@handler("AnimScriptLoop")
def _on_anim_script_loop(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """★真正的脚本命令循环体（0x08077C22）。

    与 AnimScriptCmd(0x08072048) 的区别：后者是符号表口径、实测常 0 命中；
    本点是实测中 loadspritegfx / changebg / waitbgfadein 的真正调用出处
    （它们的 LR=0x08077C3E 就落在这个循环里）。

    三条判据，命中即定位黑屏：
      1. 野指针  —— sBattleAnimScriptPtr 脱离 0x08xxxxxx 脚本区
      2. 指针停滞 —— 连续命中而 ptr 不变，说明脚本卡在同一条命令上死循环
      3. 非 ROM 指针推进 —— ptr 在动但不在 ROM，命令字节来自 open bus
    """
    raw = _read_mem(gdb, A_SCRIPT_PTR, 0x28)
    if len(raw) < 0x28:
        return
    st = _anim_state(gdb)
    if not st:
        return
    p = st["ptr"]
    in_rom = 0x08000000 <= p < 0x0A000000

    # 指针推进检测
    prev = _loop_prev["ptr"]
    if prev == p:
        _loop_prev["n"] += 1
    else:
        _loop_prev["n"] = 0
        _loop_prev["ptr"] = p
    stall = _loop_prev["n"] >= 3

    # 命令字节：只有指针在 ROM 内才有意义
    if in_rom:
        sb = _read_mem(gdb, p, 10)
        cid = sb[0] if sb else 0xFF
        name = ANIM_CMDS[cid] if cid < len(ANIM_CMDS) else f"cmd#{cid}"
        cmd_txt = f"cmd[{cid}]={name}"
    else:
        sb = b""
        cmd_txt = "cmd=?（指针不在 ROM，命令字节无意义）"

    flags, hard = [], False
    if not in_rom:
        flags.append("★野指针")
        hard = True
    if stall:
        flags.append(f"★指针停滞×{_loop_prev['n']}")
        hard = True
    # wait=0&active=1 只是「同帧连发」的软提示，正常动画也很常见，
    # 不列为硬异常（否则状态块会被无脑 dump 刷屏）。
    if st["wait"] == 0 and st["active"] and not hard:
        flags.append("wait=0&active=1（同帧连发）")
    flag = ("  " + " ".join(flags)) if flags else ""

    ctx.log(f"\n[ASL] move=#{st['move']} {cmd_txt} "
            f"active={st['active']} wait={st['wait']} turn={st['turn']} "
            f"bgfade={st['bgfade']} vis={st['vis']} snd={st['snd']}{flag}")
    ctx.log(f"  ptr=0x{p:08X} ret=0x{st['ret']:08X} cb=0x{st['cb']:08X} "
            f"atk={st['atk']} tgt={st['tgt']}")
    if sb:
        risk = "  ⚠BG类" if name in BG_RISKY_CMDS else ""
        ctx.log(f"  脚本@0x{p:08X}: {sb.hex(' ')}{risk}")

    # 仅在硬异常时 dump 整块状态，便于离线反查是哪个字段被踩
    if hard:
        ctx.log(f"  ★状态块 0x{A_SCRIPT_PTR:08X}+0x28:")
        for i in range(0, 0x28, 16):
            ctx.log(f"    +{i:02X}: {raw[i:i+16].hex(' ')}")


@handler("AnimLoadSpriteGfx")
def _on_anim_loadspritegfx(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """ScriptCmd_loadspritegfx：动画脚本加载 sprite 图形（tile 写入的第一站）。
    参数在脚本流里（sBattleAnimScriptPtr+1 起的 u16 tileTag），不是寄存器。"""
    st = _anim_state(gdb)
    if not st:
        return
    p = st["ptr"]
    b = _read_mem(gdb, p, 8)
    tag = u16(b, 1) if len(b) >= 3 else 0
    ctx.log(f"\n[ALG] move=#{st['move']} loadspritegfx tileTag=0x{tag:04X} "
            f"脚本@0x{p:08X}: {b.hex(' ')}")


@handler("AnimBgCmd")
def _on_anim_bg_cmd(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """背景类脚本命令（fadetobg/restorebg/changebg/setbldcnt…）通用处理器。
    黑屏第一嫌疑：背景被换掉/淡出后没淡回来。记录命令参数 + 背景状态机。
    判读：sAnimBackgroundFadeState 的演化序列两版应一致。"""
    st = _anim_state(gdb)
    if not st:
        return
    p = st["ptr"]
    b = _read_mem(gdb, p, 10)
    cid = b[0] if b else 0xFF
    name = ANIM_CMDS[cid] if cid < len(ANIM_CMDS) else f"cmd#{cid}"
    ctx.log(f"\n[ABG] move=#{st['move']} {name} bgfade={st['bgfade']} "
            f"turn={st['turn']} vis={st['vis']}")
    ctx.log(f"  参数@0x{p:08X}: {b.hex(' ')}")


# 背景类命令各有独立地址，但 yaml 的 name 必须唯一 ⇒ 一址一名，共用同一实现
@handler("AnimFadeToBg")
def _on_anim_fadetobg(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimRestoreBg")
def _on_anim_restorebg(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimChangeBg")
def _on_anim_changebg(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimSetBldCnt")
def _on_anim_setbldcnt(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimCreateSprite")
def _on_anim_createsprite(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimMonBg")
def _on_anim_monbg(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    _on_anim_bg_cmd(gdb, regs, ctx, cfg)


@handler("AnimWaitFrame")
def _on_anim_wait_frame(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """WaitAnimFrameCount：每帧都会命中，必须去重否则日志爆炸。
    只在「等待帧数/命令指针/可视任务数」三者变化时留痕，用于看脚本是否卡住。"""
    st = _anim_state(gdb)
    if not st or not st["active"]:
        return
    key = (st["wait"], st["ptr"], st["vis"], st["snd"], st["move"])
    if not ctx._hit(key):
        return
    ctx.log(f"\n[AWF] move=#{st['move']} wait={st['wait']} vis={st['vis']} "
            f"snd={st['snd']} bgfade={st['bgfade']} 脚本@0x{st['ptr']:08X}")


def _tile_anim_note(gdb: GdbClient) -> str:
    """tile/调色板写入类埋点共用的「动画上下文」附注。
    动画没激活时返回空串——这样平时日志不吵，只在放技能时才详打。"""
    st = _anim_state(gdb)
    if not st or not st["active"]:
        return ""
    p = st["ptr"]
    if 0x08000000 <= p < 0x0A000000:
        b = _read_mem(gdb, p, 6)
        cid = b[0] if b else 0xFF
        name = ANIM_CMDS[cid] if cid < len(ANIM_CMDS) else f"cmd#{cid}"
        return (f"\n  └ 动画中: move=#{st['move']} cmd[{cid}]={name} "
                f"bgfade={st['bgfade']} 脚本@0x{p:08X}: {b.hex(' ')}")
    return f"\n  └ 动画中: move=#{st['move']} 脚本指针 0x{p:08X}（越界！）"


# --- 字形镜像（Glyph Mirror）诊断链 ------------------------------------------
# 用于定位"镜像到底有没有命中"。三个点成对使用：
#   IwtdHook       InitWindowTileData_Hook 入口   r0=tpl r1=startOffset r2=glyph
#   IwtdMirrorRet  scene_tm1_mirror_src 返回后    r0=镜像dst(0=未命中)
#   Tm1MirrorRet   scene_tm1_mirror_of  返回后    r0=镜像dst(0=未命中)
# 判读：IwtdHook 与 IwtdMirrorRet 成对出现（每 glyph 一对）。
#   若所有 IwtdMirrorRet 都是"未命中" → tile0 与 kOptMirrors.src 对不上；
#   若命中了但显示仍错 → 查拷贝 / 表项改写时机。
# ⚠ 计数用模块级 _MIRROR_STAT：Ctx 没有 stats 属性（用过一次，直接 AttributeError）。
#   未命中也必须留痕，否则"从未命中"和"根本没跑到"在日志里分不清。

_MIRROR_STAT: dict[str, int] = {"iwtd_hit": 0, "iwtd_miss": 0,
                                "tm1_hit": 0, "tm1_miss": 0, "tilenum": 0}

TILE_NUM_MAX = 400            # TileNumRet 最多打印条数（防日志爆炸）


@handler("IwtdHook")
def _on_iwtd_hook(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    tpl = regs.get("r0", 0)
    so = regs.get("r1", 0) & 0xFFFF
    g = regs.get("r2", 0) & 0xFF
    ctx.log(f"[IwtdHook] tpl=0x{tpl:08X} startOffset=0x{so:X} glyph={g}"
            f" tile0={so + g * 2}")


@handler("IwtdMirrorRet")
def _on_iwtd_mirror_ret(gdb: GdbClient, regs: dict, ctx: Ctx,
                        cfg: dict[str, Any]) -> None:
    dst = regs.get("r0", 0) & 0xFFFF
    if dst:
        _MIRROR_STAT["iwtd_hit"] += 1
        ctx.log(f"[IwtdMirrorRet] 命中 → dst=0x{dst:03X} ({dst})"
                f"  [累计 命中{_MIRROR_STAT['iwtd_hit']}"
                f" / 未命中{_MIRROR_STAT['iwtd_miss']}]")
    else:
        _MIRROR_STAT["iwtd_miss"] += 1
        # 每 32 次打一条，避免刷屏又能证明"确实跑到了、只是没命中"
        if _MIRROR_STAT["iwtd_miss"] % 32 == 0:
            ctx.log(f"[IwtdMirrorRet] …未命中累计 {_MIRROR_STAT['iwtd_miss']} 次"
                    f"（命中 {_MIRROR_STAT['iwtd_hit']}）")


@handler("Tm1MirrorRet")
def _on_tm1_mirror_ret(gdb: GdbClient, regs: dict, ctx: Ctx,
                       cfg: dict[str, Any]) -> None:
    dst = regs.get("r0", 0) & 0xFFFF
    # r5 此时仍指向 tilemap 表项；读回原生写入的原始值
    raw = "-"
    try:
        b = bytes(gdb.read_mem(regs.get("r5", 0), 2))
        raw = f"0x{(b[0] | (b[1] << 8)) & 0xFFF:03X}"
    except Exception:
        pass
    if dst:
        _MIRROR_STAT["tm1_hit"] += 1
        ctx.log(f"[Tm1MirrorRet] 表项原值={raw} → 改写为 0x{dst:03X}"
                f"  [累计 命中{_MIRROR_STAT['tm1_hit']}"
                f" / 未命中{_MIRROR_STAT['tm1_miss']}]")
    else:
        _MIRROR_STAT["tm1_miss"] += 1
        if _MIRROR_STAT["tm1_miss"] % 32 == 0:
            ctx.log(f"[Tm1MirrorRet] …未命中累计 {_MIRROR_STAT['tm1_miss']} 次"
                    f"（命中 {_MIRROR_STAT['tm1_hit']}）")


@handler("TileNumRet")
def _on_tile_num_ret(gdb: GdbClient, regs: dict, ctx: Ctx,
                     cfg: dict[str, Any]) -> None:
    """chs_tile_num 返回点：r0=算出的 tile，r4=win。
    一次采集即可反推落址公式（tile 与 tm / TILE_BASE / TILE_OFFSET / curX / curY 的关系）。
    这是"中文到底落在哪"的权威数据，比反汇编推公式可靠。
    前 TILE_NUM_MAX 条有效，避免日志爆炸。"""
    n = _MIRROR_STAT.get("tilenum", 0)
    if n >= TILE_NUM_MAX:
        return
    _MIRROR_STAT["tilenum"] = n + 1
    tile = regs.get("r0", 0) & 0xFFFF
    win = regs.get("r4", 0)
    tm = tb = off = cx = cy = -1
    try:
        b = bytes(gdb.read_mem(win, 0x20))
        tm = b[0x0A]
        tb = b[0x16] | (b[0x17] << 8)
        off = b[0x18] | (b[0x19] << 8)
        cx = b[0x1A]
        cy = b[0x1C]
    except Exception:
        pass
    ctx.log(f"[TileNumRet] tile={tile} tm={tm} TB=0x{tb:X} OFF=0x{off:X}"
            f" cx={cx} cy={cy}")


@handler("GetGlyphTilePointers")
def _on_get_glyph_tile(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """官方日文字库取字（r0=fontNum, r1=glyph, r2=&upper, r3=&lower）。

    按 (fontNum, glyph) 去重打印，采集日文/半角字符实际用的字体号
    （font 0/1/2/6 = 1bpp 8B/tile；font 3/4/5 = shadowed 4bpp 32B/tile）
    与 glyph 范围——用于验证 v6 统一绘制通道 draw_jp_glyph 的取字分支。"""
    font_num = regs.get("r0", 0) & 0xFF
    glyph = regs.get("r1", 0) & 0xFFFF
    if not ctx._hit((font_num, glyph)):
        return
    kind = "4bpp" if 3 <= font_num <= 5 else "1bpp"
    ctx.log(f"[GetGlyphTilePointers] fontNum={font_num} glyph=0x{glyph:04X} ({kind})")


def _jp_canvas_budget(tb: int, tplt: bytes) -> str:
    """日版窗口若按美版 30×20 划界，需要的 tile 区间 + 落点 charblock。

    预算 span = 2 + 30×20 = 602 tile（4bpp 32B/tile = 19264B ≈ 1.18 charblock，
    故常跨 charblock 边界）。判读：start..start+602 是否与官方图集 [1,513)、
    tm3 的 602 区间、或其它窗口重叠 —— 这是 tm1 能否安全切 30×20 画布的唯一依据。
    """
    if len(tplt) < 0x14:
        return ""
    td = u32(tplt, 0x0C)
    span = 2 + 30 * 20
    end = (tb + span) & 0xFFFF
    if not (0x06000000 <= td < 0x06018000):
        return f"  预算: 30×20 span={span} tile，tileData=0x{td:08X}(非VRAM) start={tb} end={end}"
    cb_start = (td - 0x06000000) // 0x4000
    hi = td + end * 32
    cb_end = (hi - 1 - 0x06000000) // 0x4000 if hi > 0x06000000 else cb_start
    cross = " ⚠跨charblock" if cb_end != cb_start else ""
    return (
        f"  预算: 30×20划界 → tile[{tb},{end}) span={span}"
        f" 绝对VRAM=0x{td + tb * 32:08X}..0x{td + end * 32:08X}"
        f" charblock=cb{cb_start}→cb{cb_end}{cross}"
    )


@handler("InitTextPrinter")
def _on_init_text(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    win = regs.get("r0", 0)
    sp = regs.get("r1", 0)
    tb = regs.get("r2", 0) & 0xFFFF
    cx = regs.get("r3", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    data = _read_ff_text(gdb, sp)
    if ctx.cb_survey:
        # cb 区占用采集（避让带）：屏蔽文本打印后，扫 VRAM 非零 tile = 官方占用。
        # 内部按场景签名（DISPCNT+BGxCNT）去重，同页只采一次。
        _survey_cb_avoid(gdb, ctx)
    if ctx.ui_survey:
        # UI/窗口勘验（三路线采集）：atlas 引用计数 / OBJ 位图 / OAM 实测。
        _survey_ui(gdb, ctx)
        _dump_win_ext(gdb, win, ctx)
    if not ctx._hit((sp, data[:64])):
        return
    end = sp + len(data) - 1
    ctx.log(f"\n[W0-ITP] win=0x{win:08X} 文本=0x{sp:08X}~0x{end:08X} ({region_of(sp)}) LR=0x{lr:08X}")
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
            if ctx.cb_survey:
                _survey_cb3_tail(gdb, ctx, tplt[9])
            bj = _jp_canvas_budget(tb, tplt)
            if bj:
                ctx.log(bj)
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


# FD 占位符诊断用的 JP PCS 签名（src/meowth/jp_pcs.py 表硬编码）：
#   すごいキズぐすり = 0D 3B 02 57 92 39 0D 28 0D
#   ユウキ           = 75 53 57
_FD_SIGS = {
    "すごいキズぐすり": bytes([0x0D, 0x3B, 0x02, 0x57, 0x92, 0x39, 0x0D, 0x28, 0x0D]),
    "ユウキ": bytes([0x75, 0x53, 0x57]),
}


def _read_mem_big(gdb: GdbClient, addr: int, n: int) -> bytes:
    """定点读（≤0x400 字节）。mGBA 0.10.5 stub 单包上限约 0x40（超限 E06），
    read_mem 抛 RuntimeError（E 响应）/GdbError（连接）——两者都吞成空串。"""
    try:
        return bytes(gdb.read_mem(addr, n))
    except Exception:
        return b""


@handler("State7")
def _on_state7(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """FD 占位符 state7 入口（0x08002F80，win=r4——入口分派 `mov pc,r0` 占用了 r0）。

    dump win/文本/组合缓冲 + 文本引擎全局邻域（小定点读，勿加大范围扫描——
    mGBA stub 单包 ~0x40，0x8000 级盲扫会把连接拖死，2026-08-29 实证）。"""
    win = regs.get(cfg.get("winreg", "r4"), 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        ctx.log(f"\n[State7] win=0x{win:08X} 读取失败")
        return
    if not ctx._hit((win, bytes(wb[:0x20]))):
        return
    ctx.log(f"\n[State7] win=0x{win:08X} {_win_fields(wb)}")
    tptr = u32(wb, 0x10)
    index = u16(wb, 0x14)
    nb = _read_mem_big(gdb, (tptr + index) & 0xFFFFFFFF, 12)
    ctx.log(f"  text[index..]={nb.hex(' ')}（index 处应=占位符 id 字节）")
    mb = _read_mem_big(gdb, 0x0202322C, 0x60)
    ctx.log(f"  组合缓冲 0x0202322C: {mb.hex(' ')}")
    # 候选 StringVar 区定点 dump（每块 ≤0x200 = 32 包）：
    dumps = [
        ("IWRAM 文本全局邻域", 0x03000300, 0x200),
        ("EWRAM 组合缓冲邻域", 0x02023100, 0x400),
        ("EWRAM 前段", 0x02020000, 0x400),
    ]
    for tag, addr, n in dumps:
        blob = _read_mem_big(gdb, addr, n)
        if not blob:
            ctx.log(f"  [{tag}] 0x{addr:08X}..+{n:X} 读取失败")
            continue
        hits = []
        for sig_name, sig in _FD_SIGS.items():
            pos = blob.find(sig)
            while pos >= 0 and len(hits) < 4:
                hits.append(f"{sig_name}@0x{addr + pos:08X}")
                pos = blob.find(sig, pos + 1)
        ctx.log(f"  [{tag}] 0x{addr:08X}..+{n:X}: {blob.hex(' ')}"
                + (f"  ★命中: {', '.join(hits)}" if hits else ""))


@handler("State7Skip")
def _on_state7_skip(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """FD 占位符 state7 的 SKIP 处理器（0x08002F78，win=r4）：index+=1 跳过 id 字节。

    判读：若拾道具消息（FD01 发现了 FD03）里本断点命中 2 次 → 跳过路径正常，
    あ/う 碎片另有来源；若一次都不命中 → FD 没走到 state7（我们 hook 的
    state 写入或分派有问题）。"""
    win = regs.get(cfg.get("winreg", "r4"), 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        ctx.log(f"\n[State7Skip] win=0x{win:08X} 读取失败")
        return
    if not ctx._hit((win, bytes(wb[:0x20]))):
        return
    ctx.log(f"\n[State7Skip] win=0x{win:08X} {_win_fields(wb)}")
    tptr = u32(wb, 0x10)
    index = u16(wb, 0x14)
    nb = _read_mem_big(gdb, (tptr + index) & 0xFFFFFFFF, 12)
    ctx.log(f"  将跳过 text[index..]={nb.hex(' ')}")


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
    # 血条缓冲打印机：tm2 + dest 在 eBattleInterfaceGfxBuffer 一带
    if not us and len(wb) > 0x0A and wb[0x0A] == 2:
        dst = u32(wb, 0x20) if len(wb) >= 0x24 else 0
        ctx.log(f"  ※ tm2 缓冲打印机 dest@+0x20=0x{dst:08X}")


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


def _read_chunks(gdb: GdbClient, addr: int, n: int, step: int = 0x100) -> bytes:
    """mGBA stub 对大读包回 E06（0x100 实测可通过），按小块拼接。"""
    out = bytearray()
    off = 0
    while off < n:
        k = min(step, n - off)
        out += bytes(gdb.read_mem(addr + off, k))
        off += k
    return bytes(out)


def _maybe_vram_survey(gdb: GdbClient, ctx: Ctx) -> None:
    """cb3 勘验（--vram-survey）：场景签名（DISPCNT+BGxCNT×4）变化时勘一次。
    报告：各层 charbase/screenbase/8bpp/启用位；各启用层 tilemap 引用直方图
    （0x100 桶，看 charbase-2 层是否引用 ≥0x200）；cb3 (0x0600C000-
    0x0600FFFF) 1KB×16 非零块图；cb2 尾 0x1F8-0x1FF 占用。"""
    try:
        dispcnt_b = bytes(gdb.read_mem(0x04000000, 2))
        bgcnt_b = bytes(gdb.read_mem(0x04000008, 8))
    except GdbError:
        return
    if len(dispcnt_b) < 2 or len(bgcnt_b) < 8:
        return
    dispcnt = u16(dispcnt_b, 0)
    bgcnt = [u16(bgcnt_b, i * 2) for i in range(4)]
    sig = (dispcnt, tuple(bgcnt))
    if sig == ctx._vram_sig:
        return
    ctx._vram_sig = sig
    mode = dispcnt & 7
    en = (dispcnt >> 8) & 0x3F
    ctx.log(f"\n[VRAM-SURVEY] mode={mode} BG启用位=0x{en:02X} DISPCNT=0x{dispcnt:04X}")
    for layer in range(4):
        cnt = bgcnt[layer]
        ctx.log(
            f"  BG{layer}: CNT=0x{cnt:04X} charBase={(cnt >> 2) & 3}"
            f" screenBase={(cnt >> 8) & 0x1F} 8bpp={(cnt >> 7) & 1}"
            f" 启用={(en >> layer) & 1}"
        )
    for layer in range(4):
        cnt = bgcnt[layer]
        if not ((en >> layer) & 1):
            continue
        if mode >= 3 and layer >= 2:
            ctx.log(f"  BG{layer}: 位图模式 BG2/3 无 tilemap，跳过")
            continue
        affine = 1 if (mode in (1, 2) and layer >= 2) else 0
        sb = (cnt >> 8) & 0x1F
        base = 0x06000000 + sb * 0x800
        hist = [0, 0, 0, 0]
        mx = 0
        try:
            if affine:
                data = _read_chunks(gdb, base, 0x400)
                for b in data:
                    idx = b * 2
                    hist[min(idx >> 8, 3)] += 1
                    mx = max(mx, idx)
            else:
                data = _read_chunks(gdb, base, 0x800)
                for k in range(0, len(data) - 1, 2):
                    idx = (data[k] | (data[k + 1] << 8)) & 0x3FF
                    hist[idx >> 8] += 1
                    mx = max(mx, idx)
        except GdbError as e:
            ctx.log(f"  BG{layer}: tilemap@0x{base:08X} 读取失败 {e}")
            continue
        cb = (cnt >> 2) & (0xF if affine else 3)
        ctx.log(
            f"  BG{layer}: tilemap@0x{base:08X} charBase={cb}"
            f" 引用桶[0xx,1xx,2xx,3xx]={hist} maxIdx=0x{mx:03X}"
        )
    blocks = []
    try:
        for k in range(4):
            data = _read_chunks(gdb, 0x0600C000 + k * 0x1000, 0x1000)
            for j in range(4):
                blk = data[j * 0x400:(j + 1) * 0x400]
                blocks.append("X" if any(blk) else ".")
        ctx.log(f"  cb3 0x0600C000-0x0600FFFF 1KBx16 非零块图 [{''.join(blocks)}] (X=有数据 .=全零)")
    except GdbError as e:
        ctx.log(f"  cb3@0x0600C000 读取失败 {e}")
    try:
        tail = bytes(gdb.read_mem(0x0600BF00, 0x100))
        ctx.log(f"  cb2尾 0x1F8-0x1FF (0x0600BF00) 非零={'有' if any(tail) else '全零'}")
    except GdbError:
        pass


# ---------------------------------------------------------------------------
# cb 区占用采集（避让带）------------------------------------------------------
# 用途：配合「屏蔽文本打印开关」（hook 侧 ADDR_V6_BYPASS=0x0203FEB8 写 1）一起用。
#   —— 屏蔽后中文/官方字符都不再往 VRAM 写 tile，此时扫 VRAM 各 charblock 的
#   非零 tile 得到的就是「纯官方占用」= 避让带（官方预渲染 atlas + UI 图标 +
#   场景映射 + OBJ 精灵），这正是 v8 顺序分配器缺的那部分（关闭按钮/血条/状态
#   图标等不在文本 tilemap 扫描范围内的 UI 元素）。
# 采集单位：物理 charblock（cb0~cb3 是 BG 区，cb4~cb5 是 OBJ 精灵区），每个
#   cb = 16KB = 512 tile（4bpp 32B/tile）。输出每个 cb 的非零 tile 连续区间。
# 触发：挂在 InitTextPrinter handler（屏蔽开关只短路 PrintNextChar，不影响
#   InitTextPrinter 的窗口初始化 + 字形预渲染）。场景签名（DISPCNT+BGxCNT×4）
#   变化时采集一次，避免同页刷屏。

CB_SURVEY_BASE = 0x06000000
CB_SURVEY_SIZE = 0x4000          # 16KB = 512 tile
CB_SURVEY_TILE = 32              # 4bpp 每 tile 字节
CB_SURVEY_LABELS = ("cb0", "cb1", "cb2", "cb3", "cb4(OBJ)", "cb5(OBJ)")


def _cb_ranges(data: bytes) -> list[tuple[int, int]]:
    """一个 cb 的 512 tile（每 tile 32B）→ 非零 tile 连续区间 [(s,e) 左闭右开]。"""
    ranges: list[tuple[int, int]] = []
    s = None
    for t in range(512):
        tile = data[t * CB_SURVEY_TILE:(t + 1) * CB_SURVEY_TILE]
        if any(tile):
            if s is None:
                s = t
        elif s is not None:
            ranges.append((s, t))
            s = None
    if s is not None:
        ranges.append((s, 512))
    return ranges


def _fmt_cb_ranges(ranges: list[tuple[int, int]]) -> str:
    if not ranges:
        return "（全空）"
    return " ".join(f"[0x{s:03X}-0x{e-1:03X}]" for s, e in ranges)


def _cb3_tail_ranges(data: bytes) -> list[tuple[int, int]]:
    """cb3 前 91 tile（602 画布尾巴）→ 非零 tile 连续区间。"""
    ranges: list[tuple[int, int]] = []
    n = min(len(data) // 32, 91)
    s = None
    for t in range(n):
        tile = data[t * 32:(t + 1) * 32]
        if any(tile):
            if s is None:
                s = t
        elif s is not None:
            ranges.append((s, t))
            s = None
    if s is not None:
        ranges.append((s, n))
    return ranges


def _survey_cb3_tail(gdb: GdbClient, ctx: Ctx, tm: int) -> None:
    """602 画布尾巴专项采样：cb3[0x000-0x05A]（91 tile = 0x0B60B）占用。

    路线 A 判定关键 —— tm1 菜单活跃时这块是否空闲。若空闲，tm1 可直接与
    tm3 共用 cb2[1,603) 画布；若被 UI 图标占用，则退路线 B（缩画布）。
    textMode 或占用区间变化才打一行（避免 430 次 ITP 刷屏）。"""
    try:
        data = _read_chunks(gdb, 0x0600C000, 91 * 32, step=0x100)
    except GdbError:
        return
    if len(data) < 91 * 32:
        return
    ranges = _cb3_tail_ranges(data)
    sig = (tm, tuple(ranges))
    if sig == ctx._cb3tail_sig:
        return
    ctx._cb3tail_sig = sig
    ctx.log(f"[W0-CB3TAIL] tm={tm} cb3[0x000-0x05A]占用="
            f"{_fmt_cb_ranges(ranges) if ranges else '全空'}")


def _survey_cb_avoid(gdb: GdbClient, ctx: Ctx) -> None:
    """采集当前场景 cb 区占用（避让带）。场景签名变化时采集一次。"""
    try:
        dispcnt_b = bytes(gdb.read_mem(0x04000000, 2))
        bgcnt_b = bytes(gdb.read_mem(0x04000008, 8))
    except GdbError:
        return
    if len(dispcnt_b) < 2 or len(bgcnt_b) < 8:
        return
    dispcnt = u16(dispcnt_b, 0)
    bgcnt = [u16(bgcnt_b, i * 2) for i in range(4)]
    sig = (dispcnt, tuple(bgcnt))
    if sig == ctx._cb_sig:
        return
    ctx._cb_sig = sig

    mode = dispcnt & 7
    obj_on = (dispcnt >> 12) & 1
    ctx.log(f"\n[CBAVOID] 场景签名 mode={mode} DISPCNT=0x{dispcnt:04X} OBJ启用={obj_on}")
    for layer in range(4):
        cnt = bgcnt[layer]
        en = (dispcnt >> (8 + layer)) & 1
        ctx.log(f"  BG{layer}: charBase={(cnt >> 2) & 3} screenBase={(cnt >> 8) & 0x1F} "
                f"8bpp={(cnt >> 7) & 1} 启用={en}")

    for cb in range(6):
        base = CB_SURVEY_BASE + cb * CB_SURVEY_SIZE
        try:
            data = _read_chunks(gdb, base, CB_SURVEY_SIZE, step=0x100)
        except GdbError as e:
            ctx.log(f"  {CB_SURVEY_LABELS[cb]} (0x{base:08X}): 读取失败 {e}")
            continue
        if len(data) < CB_SURVEY_SIZE:
            ctx.log(f"  {CB_SURVEY_LABELS[cb]} (0x{base:08X}): 读取不足 {len(data)}B")
            continue
        ranges = _cb_ranges(data)
        ctx.log(f"  {CB_SURVEY_LABELS[cb]} (0x{base:08X}): {_fmt_cb_ranges(ranges)}")


# ---------------------------------------------------------------------------
# UI/窗口勘验（--ui-survey）：三路线落地采集 ----------------------------------
# 对应 docs/调研_20260907_三路线全网检索.md 的三个待验证问题：
#   ① 窗口区预算：由 InitWindowTileData / InitWindowTileDataRet 成对日志给出
#      （断点侧，非本勘验；区间 = [startOffset, 返回值)）。
#   ② atlas 回收可行性：各启用 BG 的 tilemap 对字库区 [0,0x210) 的引用计数。
#      判读：官方文本停印（--bypass-text）前后各采一次，引用计数差 = 官方活引用；
#      若停印后引用≈0，atlas 即可回收（cb 整块 512 tile 连续空间）。
#   ③ OBJ 文字层可行性：OBJ tile 位图（0x03002450【推定，pokeruby.sym 口径，
#      未实机验证】）+ OAM 实测（活动精灵数 / tile 基址分布）。
# 触发：挂在 InitTextPrinter / UpdateTilemap handler，场景签名变化时采一次。

OBJ_BITMAP_ADDR = 0x03002450     # sSpriteTileAllocBitmap（0x80B = 1024 bit）
OAM_ADDR = 0x07000000

_BG_SIZE_NAMES = ("32x32", "64x32", "32x64", "64x64")


def _survey_ui(gdb: GdbClient, ctx: Ctx) -> None:
    """场景签名（DISPCNT+BGxCNT×4）变化时勘一次：BG 层 / atlas 引用 / OBJ 余量。"""
    try:
        dispcnt_b = bytes(gdb.read_mem(0x04000000, 2))
        bgcnt_b = bytes(gdb.read_mem(0x04000008, 8))
    except GdbError:
        return
    if len(dispcnt_b) < 2 or len(bgcnt_b) < 8:
        return
    dispcnt = u16(dispcnt_b, 0)
    bgcnt = [u16(bgcnt_b, i * 2) for i in range(4)]
    sig = (dispcnt, tuple(bgcnt))
    if sig == ctx._ui_sig:
        return
    ctx._ui_sig = sig
    mode = dispcnt & 7
    ctx.log(f"\n[UISURVEY] 场景签名 mode={mode} DISPCNT=0x{dispcnt:04X}"
            f" OBJ1D映射={(dispcnt >> 6) & 1} OBJ启用={(dispcnt >> 12) & 1}")
    seen_cb: set[int] = set()
    for layer in range(4):
        cnt = bgcnt[layer]
        cb = (cnt >> 2) & 3
        sb = (cnt >> 8) & 0x1F
        sz = (cnt >> 14) & 3
        en = (dispcnt >> (8 + layer)) & 1
        ctx.log(f"  BG{layer}: CNT=0x{cnt:04X} charBase={cb} screenBase={sb}"
                f" size={_BG_SIZE_NAMES[sz]} 8bpp={(cnt >> 7) & 1} 启用={en}")
        if not en or (mode >= 3 and layer >= 2):
            continue
        # tilemap 引用分析（读首个 screen block 0x800 = 32x32 区域）
        tilemap_base = 0x06000000 + sb * 0x800
        data = _read_chunks(gdb, tilemap_base, 0x800, step=0x100)
        if len(data) < 0x800:
            ctx.log(f"    tilemap@0x{tilemap_base:08X} 读取失败")
            continue
        zero = 0
        hist = [0, 0, 0, 0]
        atlas_set: Counter = Counter()
        for k in range(0, 0x800, 2):
            idx = (data[k] | (data[k + 1] << 8)) & 0x3FF
            if idx == 0:
                zero += 1
                continue  # 空 entry 的 tile0 不算 atlas 引用（2026-09-07 采集勘误）
            hist[idx >> 8] += 1
            if idx < 0x210:
                atlas_set[idx] += 1
        tops = ", ".join(f"#{i:03X}x{n}" for i, n in atlas_set.most_common(5))
        ctx.log(f"    tilemap@0x{tilemap_base:08X}: 全零项={zero}/1024"
                f" 桶[0,1,2,3]xx={hist}")
        ctx.log(f"    atlas区[0,0x210) 非零引用={sum(atlas_set.values())} 次 /"
                f" {len(atlas_set)} 个不同 tile  最热: {tops or '无'}")
        # 该 charBlock 的字库 atlas 实际范围（首个非零 tile 区间）
        if cb not in seen_cb:
            seen_cb.add(cb)
            char_base_addr = 0x06000000 + cb * 0x4000
            try:
                cdata = _read_chunks(gdb, char_base_addr, 0x4000, step=0x100)
                cranges = _cb_ranges(cdata)
                note = ""
                if cranges and cranges[0][0] == 0:
                    note = f"（atlas 疑似 ≈ [0x000,0x{cranges[0][1]:03X})）"
                ctx.log(f"    cb{cb} (0x{char_base_addr:08X}) 非零 tile 区间:"
                        f" {_fmt_cb_ranges(cranges)} {note}")
            except GdbError as e:
                ctx.log(f"    cb{cb} (0x{char_base_addr:08X}) 读取失败 {e}")
    # OBJ tile 分配位图（置位语义未知，两头都报 + 原始字节供人工判读）
    bm = _read_chunks(gdb, OBJ_BITMAP_ADDR, 0x80, step=0x40)
    if len(bm) == 0x80:
        used = sum(bin(b).count("1") for b in bm)
        runs: list[tuple[int, int]] = []
        s = None
        for i in range(1024):
            bit = (bm[i >> 3] >> (i & 7)) & 1
            if not bit:
                if s is None:
                    s = i
            elif s is not None:
                runs.append((s, i))
                s = None
        if s is not None:
            runs.append((s, 1024))
        runs.sort(key=lambda r: r[1] - r[0], reverse=True)
        top = " ".join(f"[0x{a:03X},0x{b-1:03X}]({b-a})" for a, b in runs[:6])
        ctx.log(f"  OBJ位图@0x{OBJ_BITMAP_ADDR:08X}【地址待验证】: 置位={used}/1024"
                f" → 若置位=占用，最大空闲段: {top}")
        ctx.log(f"    位图头16B: {bm[:16].hex(' ')}")
    # OAM 实测：活动精灵数 + tile 基址分布（不依赖位图符号正确性）
    oam = _read_chunks(gdb, OAM_ADDR, 0x400, step=0x100)
    if len(oam) == 0x400:
        active = []
        for i in range(128):
            a0 = u16(oam, i * 8)
            a1 = u16(oam, i * 8 + 2)
            a2 = u16(oam, i * 8 + 4)
            if (a0 & 0x0300) == 0x0200:   # bit9=1 且非仿射 → 隐藏
                continue
            wh = OAM_SIZE_TABLE.get(((a0 >> 14) & 3, (a1 >> 14) & 3))
            active.append((a2 & 0x3FF, wh, (a0 >> 13) & 1))
        if active:
            tiles = [t for t, _, _ in active]
            n8 = sum(1 for _, _, b8 in active if b8)
            ctx.log(f"  OAM 实测: 活动精灵 {len(active)}/128"
                    f" tile基址范围 [0x{min(tiles):03X},0x{max(tiles):03X}]"
                    f" 8bpp×{n8}")
            ctx.log(f"    明细(tile,宽x高,8bpp): {active[:10]}")
            # 按 OAM 逐精灵估算 tile 占用上界（4bpp w*h/64，8bpp×2），给出空闲判据
            span = [t + (w * h * (2 if b8 else 1)) // 64 for t, (w, h), b8 in active]
            hi = max(span) if span else 0
            ctx.log(f"    OAM估算占用上界 ≈ tile [0x000,0x{hi:03X})"
                    f" → 空闲 ≈ {1024 - hi} tile（OBJ 文字层判据）")
        else:
            ctx.log("  OAM 实测: 无活动精灵 → OBJ VRAM 全空（1024 tile）")


# win 结构 0x40B 扩展 dump：找 width/height 真实偏移（日版布局与 pokeemerald
# 不同、模板 0x14-0x17 恒 0）。每 win 指针只打前几个不同现场，防刷屏。
_WINEXT_STATE: dict[str, Any] = {"n": 0, "keys": set()}


def _dump_win_ext(gdb: GdbClient, win: int, ctx: Ctx) -> None:
    if _WINEXT_STATE["n"] >= 200:
        return
    wb = _read_mem(gdb, win, 0x40)
    if len(wb) < 0x20:
        return
    key = (win, bytes(wb[:0x20]))
    if key in _WINEXT_STATE["keys"]:
        return
    _WINEXT_STATE["keys"].add(key)
    _WINEXT_STATE["n"] += 1
    ctx.log(f"  [win0x40] 0x{win:08X}: {wb.hex(' ')}")


# hook 侧屏蔽文本打印开关（ADDR_V6_BYPASS，见 configs/.../hook/include/game.h）。
# 非 0 → PrintNextChar_Hook 直接 return 1，连官方串都不打印。
ADDR_TEXT_BYPASS = 0x0203FEB8


def _write_bypass_text(gdb: GdbClient, ctx: Ctx) -> None:
    """写 ADDR_V6_BYPASS=1 屏蔽文本打印（配合 --cb-survey 采纯官方避让带）。"""
    try:
        r = gdb.cmd(f"M{ADDR_TEXT_BYPASS:x},1:01")
    except GdbError as e:
        ctx.log(f"  ⚠ 写屏蔽开关 0x{ADDR_TEXT_BYPASS:08X}=1 失败: {e}")
        return
    if r.startswith("E") or not r:
        ctx.log(f"  ⚠ 写屏蔽开关 0x{ADDR_TEXT_BYPASS:08X}=1 失败: {r}")
    else:
        ctx.log(f"  屏蔽文本打印开关已置位（0x{ADDR_TEXT_BYPASS:08X}=1）")


@handler("ChsFontFunc")
def _on_chs_fontfunc(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """新管线每字符入口（Chs_FontFunc_hook）：r0=win, r1=glyph, r2=is_chs。
    输出 win 关键字段 + 自定义相位（0x0203FF84=key|px，0x0203FF88=key|base_tx）。
    诊断：中英混排 / 换行后 px、base_tx、win[0x1B] 三者是否连贯演化。
    ⚠ 地址随 game.bin 重建变化（当前对应 sha 3b370e2cf4e5），重建后须更新。"""
    win = regs.get("r0", 0)
    glyph = regs.get("r1", 0) & 0xFFFF
    is_chs = regs.get("r2", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    who = "C管线" if 0x08800000 <= lr < 0x09000000 else "原生ROM"
    wb = _read_win(gdb, win)
    if len(wb) < 0x1E:
        return
    ph = _read_mem(gdb, 0x0203FF84, 48)
    genb = _read_mem(gdb, 0x0203FFB4, 1)
    slots = []
    for i in range(8):
        if len(ph) >= (i + 1) * 6:
            k = u16(ph, i * 6)
            x = u16(ph, i * 6 + 2)
            b = ph[i * 6 + 4]
            g = ph[i * 6 + 5]
            slots.append("s%d:k%04X/px%d/tx%d/g%d" % (i, k, x, b, g))
    slots.append("gen=%d" % (genb[0] if genb else -1))
    ctx.log(
        f"\n[CFF] win=0x{win:08X} tm={wb[0x0A]} font={wb[0x0B]} chs={is_chs} "
        f"glyph=0x{glyph:04X} idx={u16(wb, 0x14)} 调用方={who} LR=0x{lr:08X}"
    )
    ctx.log(
        f"  TB=0x{u16(wb, 0x16):04X} OFF=0x{u16(wb, 0x18):04X} "
        f"curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
    )
    ctx.log("  槽: " + " | ".join(slots))


@handler("ChsPrint")
def _on_chs_print(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """中文绘制主入口 chs_print(r0=win, r1=code, r2=fontSize)（地址随 game.bin 重建变化，
    以 out/game.map 为准）。resolve_draw 之后的场景决策在这里还看不到，但每字符的
    win 现场与 v8 分配器游标/last_tile 在此可见——与 UpdateTilemap 的 u/l 对联合判读。"""
    win = regs.get("r0", 0)
    code = regs.get("r1", 0) & 0xFFFFFFFF
    fs = regs.get("r2", 0) & 0xFF
    wb = _read_win(gdb, win)
    if len(wb) < 0x1E:
        return
    cur = _read_mem(gdb, 0x0203FF42, 8)   # 游标FF42/相位FF44/行标识FF46/last_tile FF48
    if not ctx._hit((win, code, wb[0x1B], wb[0x1D])):
        return
    last = u16(cur, 6) if len(cur) >= 8 else -1
    curs = u16(cur, 0) if len(cur) >= 2 else -1
    ph = u16(cur, 2) if len(cur) >= 4 else -1
    ctx.log(
        f"\n[ChsPrint] win=0x{win:08X} tpl=0x{u32(wb, 0):08X} code=0x{code:04X} fontSize={fs}"
        f" tm={wb[0x0A]} font={wb[0x0B]} TB=0x{u16(wb, 0x16):04X} OFF=0x{u16(wb, 0x18):04X}"
        f" curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
    )
    ctx.log(f"  v8: cursor=0x{curs:04X} 相位=0x{ph:04X} last_tile=0x{last:04X}")


# ---- v8 回收链路诊断（2026-09-09 领航员清 tile）--------------------------
# 目的：回答「领航员翻页到底走 InitTextPrinter 还是 Text_ClearWindow」，
# 以及「v8_release 被调用时账本里有没有该 win 的段」。地址见下方各 handler
# 与 yaml（随 game.bin 重建变化，必须按 hook/out/game.map 同步）。


def _read_mem_chunked(gdb: GdbClient, addr: int, n: int, chunk: int = 0x40) -> bytes:
    """分块读内存（mGBA 0.10.5 stub 单包上限约 0x40，超限 E06）。"""
    out = bytearray()
    for off in range(0, n, chunk):
        b = _read_mem(gdb, addr + off, min(chunk, n - off))
        if not b:
            break
        out += b
    return bytes(out)


def _wl_slots(gdb: GdbClient) -> tuple:
    """读 per-win 账本 @0x0203F800（magic + 4 槽 × 18u16）。
    返回 (magic, [(win, [(start,len)...])...])；读失败 magic=None。"""
    raw = _read_mem_chunked(gdb, 0x0203F800, 148)
    if len(raw) < 4:
        return None, []
    magic = u16(raw, 0)
    slots = []
    for i in range(4):
        b = 4 + i * 36
        win = u16(raw, b) | (u16(raw, b + 2) << 16)
        segs = []
        for s in range(8):
            st = u16(raw, b + 4 + s * 4)
            ln = u16(raw, b + 6 + s * 4)
            if ln:
                segs.append((st, ln))
        slots.append((win, segs))
    return magic, slots


def _wl_slot_of(gdb: GdbClient, win: int) -> tuple:
    """返回 (槽索引, [(start,len)...])；未找到 → (-1, [])。"""
    magic, slots = _wl_slots(gdb)
    if magic is None:
        return -1, []
    for i, (w, segs) in enumerate(slots):
        if w == win:
            return i, segs
    return -1, []


def _ours_segs(gdb: GdbClient) -> tuple:
    """读 ours 段表 @0x0203FF80（magic + 19 段 × {start,len}）。返回 (magic, [(start,len)...])。"""
    raw = _read_mem_chunked(gdb, 0x0203FF80, 80)
    if len(raw) < 2:
        return None, []
    magic = u16(raw, 0)
    segs = []
    for i in range(19):
        st = u16(raw, 4 + i * 4)
        ln = u16(raw, 6 + i * 4)
        if ln:
            segs.append((st, ln))
    return magic, segs


def _bitmap_used(gdb: GdbClient) -> int:
    """位图 @0x0203FEC0 128B 的 set bit 数（-1=读失败）。"""
    raw = _read_mem_chunked(gdb, 0x0203FEC0, 128)
    if len(raw) < 128:
        return -1
    return sum(bin(b).count("1") for b in raw)


def _vram_nonempty_runs(gdb: GdbClient, vram: int, t0: int, count: int,
                        bridge: int = 2) -> list:
    """扫 VRAM tile 区 [vram+t0*32, vram+(t0+count)*32) 的实际占用。

    返回 [(start, len), ...] 非空连续段；中间 <=bridge 个空 tile 视为同段（避免
    把字形内部空隙切断）。用于回答「官方 LZ 到底写了多少 tile」——预算 602 只是
    上界，实际占用必须实测。
    """
    raw = _read_mem_chunked(gdb, vram + t0 * 32, count * 32)
    if len(raw) < 32:
        return []
    n = len(raw) // 32
    idxs = [i for i in range(n) if any(raw[i * 32:(i + 1) * 32])]
    if not idxs:
        return []
    runs = []
    s = p = idxs[0]
    for i in idxs[1:]:
        if i - p - 1 <= bridge:
            p = i
        else:
            runs.append((t0 + s, p - s + 1))
            s = p = i
    runs.append((t0 + s, p - s + 1))
    return runs


def _fmt_runs(runs: list, limit: int = 12) -> str:
    if not runs:
        return "（全空）"
    shown = [f"[{st}..{st + ln - 1}]({ln})" for st, ln in runs[:limit]]
    tail = f" …共{len(runs)}段" if len(runs) > limit else ""
    return " ".join(shown) + tail


def _cb_of(tile_data: int) -> int:
    """VRAM tileData → charblock 序号（BG 区 0x06000000 起，每 cb 16KB）。"""
    if tile_data < 0x06000000:
        return -1
    return (tile_data - 0x06000000) // 0x4000


@handler("JpTm1Alloc")
def _on_jp_tm1_alloc(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """JP @0x080029DA：tm1 开窗分配返回点——【日版 tm1 UI 分配的诞生地】。

    ★ 为什么是 0x080029DA 而不是别的：该点是 0x08002950(TextLoadWindowTemplate)
    的唯一出口（pop {r1}; bx r1），此时
        r0 = 图集容量（返回值）   r3 = win（全程未被破坏）
    一次命中即可同时拿到「谁开窗 + 起点 + 容量」，等价于美版 InitWindowTileData
    返回的「新游标」。

    反汇编实证（源 ROM，2026-09-09）：
      8002950 push {lr}
      8002952 adds r3,r0,#0        r3 = win
      800295a ldr  r1,=0x0300032E
      800295e strh r0,[r1,#0]      ★ *0x0300032E = 0        图集装载游标归零
      8002964 str  r1,[r0,#0]      ★ *0x03000328 = win
      8002968 strh r2,[r0,#0]      ★ *0x0300032C = tileOffset(base)
      800296a strh r2,[r3,#22]     ★ win[0x16] = tileOffset  (= TILE_BASE)
      800296c ldrb r0,[r1,#9]      textMode
      8002970 beq  0x800299c       ★ textMode==1 → 图集容量分派
      800299c ldr  r0,[r3,#0] / ldrb r0,[r0,#8]   fontNum
      80029a0 cmp  r0,#5 / bhi 0x80029d8 (return 0)
      80029a8 跳表 0x080029B4[fontNum]：
               [0]=0x080029CC→r0=0x200(512)  [1]=0x080029D2→r0=0x100(256)
               [2]=0x080029D2→256            [3]=0x080029CC→512
               [4]=0x080029D2→256            [5]=0x080029D2→256
      80029da pop  {r1} / bx r1    ← 本点

    调用方 @0x0806F000（用户日志 LR=0x0806F00A 实证）：
      806f000 ldr  r0,=0x0202E6E8 ; ldr r0,[r0]     win
      806f004 ldr  r1,=0x0202E6EE ; ldrh r1,[r1]    tileOffset
      806f006 bl   0x8002950
      806f00a strh r0,=0x0202E6F0                   ★ 容量写入全局
      806f01c bl   0x80029e0                        图集步进装载

    ⇒ tm1 的「UI 分配」= 预留 [tileOffset, tileOffset+容量) 给假名图集。
      fontNum=3（日志实测全是它）→ 容量 512 → 预留 [1, 513)。
      而 v8_alloc_tile 的 lo=0x100(256) ⇒ **重叠区 [256,513) = 257 tile**，
      这正是「撞 UI」的候选根因（待 JpTm1AtlasLoad 的 VRAM 实测确证）。
    """
    cap = regs.get("r0", 0) & 0xFFFF
    win = regs.get("r3", 0)
    lr = regs.get("r14", 0) & ~1
    # EWRAM 全局账本（调用方 @0x0806F000 实证）
    e_win = _read_mem(gdb, 0x0202E6E8, 4)
    e_off = _read_mem(gdb, 0x0202E6EE, 2)
    e_cap = _read_mem(gdb, 0x0202E6F0, 2)
    g_win = u32(e_win, 0) if len(e_win) >= 4 else 0
    g_off = u16(e_off, 0) if len(e_off) >= 2 else 0
    g_cap = u16(e_cap, 0) if len(e_cap) >= 2 else 0
    # IWRAM 分配器状态块
    i_st = _read_mem(gdb, 0x03000328, 8)
    i_win = u32(i_st, 0) if len(i_st) >= 4 else 0
    i_base = u16(i_st, 4) if len(i_st) >= 6 else 0
    i_cur = u16(i_st, 6) if len(i_st) >= 8 else 0

    tpl = cb = fn = tm = -1
    tile_data = 0
    off = 0
    if win:
        wb = _read_win(gdb, win)
        if len(wb) >= 4:
            tpl = u32(wb, 0)
            off = u16(wb, 0x16)
        if tpl:
            tb = _read_mem(gdb, tpl, 0x18)
            if len(tb) >= 0x14:
                cb = tb[1]
                fn = tb[8]
                tm = tb[9]
                tile_data = u32(tb, 0x0C)
    if not ctx._hit(("tm1alloc", win, cap, tpl)):
        return
    ctx.log(f"\n[JpTm1Alloc] win=0x{win:08X} 容量={cap}(0x{cap:04X}) "
            f"LR=0x{lr:08X}  ← tm1 开窗分配")
    if tpl:
        ctx.log(f"  模板@0x{tpl:08X}: charBase={cb} font={fn} textMode={tm} "
                f"tileData=0x{tile_data:08X}")
    ctx.log(f"  win[0x16](TILE_BASE)=0x{off:04X}  ⇒ 图集预留区间 = "
            f"tile[{off}..{off + cap})(span={cap})  绝对VRAM="
            f"0x{tile_data + off * 32:08X}..0x{tile_data + (off + cap) * 32:08X}")
    ctx.log(f"  EWRAM账本: 0x0202E6E8=win 0x{g_win:08X}  "
            f"0x0202E6EE=tileOffset {g_off}(0x{g_off:04X})  "
            f"0x0202E6F0=容量 {g_cap}(0x{g_cap:04X})")
    ctx.log(f"  IWRAM状态: 0x03000328=win 0x{i_win:08X}  "
            f"0x0300032C=base 0x{i_base:04X}  0x0300032E=游标 0x{i_cur:04X}"
            f"（开窗时应已归零）")
    # v8 视角：两者是否重叠
    if 0 <= cb < 4:
        hi = min((4 - cb) * 512, 1024)
        lo = 0x100
        ov_lo, ov_hi = max(lo, off), min(hi, off + cap)
        if ov_hi > ov_lo:
            ctx.log(f"  ⚠ v8 领号区 [0x{lo:03X},0x{hi:03X}) 与图集预留 "
                    f"[{off},{off + cap}) **重叠 [{ov_lo},{ov_hi}) = "
                    f"{ov_hi - ov_lo} tile** ← 撞 UI 候选根因")
        else:
            ctx.log(f"  v8 领号区 [0x{lo:03X},0x{hi:03X}) 与图集预留无重叠")


@handler("JpTm1AtlasLoad")
def _on_jp_tm1_atlas_load(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """JP @0x080029E0：tm1 假名图集步进装载（每帧装 16 字符，游标 +16）。

    反汇编实证：
      80029f8 ldrh r4,[r0]        r4 = *0x0300032E（游标）
      8002a14 bl   0x8002a50      装载核心(win, ?, idx = r4 & 0xFF)
      8002a18 adds r4,#1
      8002a20 cmp  r4,r0          r0 = 容量上限
      8002a22 blt  0x8002a08
      8002a28 adds r1,#16 / strh r1,[r0]   ★ 游标 += 16

    装载核心 0x08002A50 的 VRAM 公式（fontNum 分派）：
      fontNum 1/2 → tileData + (base + idx)*32      （1 tile/字符）
      fontNum 3   → tileData + base*32 + idx*64     （2 tile/字符）

    ★ 用【原版日版 ROM】采集时本点活着，VRAM 是纯官方内容 —— 正是
      「屏蔽中文打印后的 cb 内容」的等价物。用汉化 ROM 采集则本点已被
      hook 停掉（MultistepInitWindowTileData → return 1），命中 0 属正常。
    """
    win = regs.get("r0", 0)
    st = _read_mem(gdb, 0x03000328, 8)
    i_win = u32(st, 0) if len(st) >= 4 else 0
    i_base = u16(st, 4) if len(st) >= 6 else 0
    i_cur = u16(st, 6) if len(st) >= 8 else 0
    cap = _read_mem(gdb, 0x0202E6F0, 2)
    g_cap = u16(cap, 0) if len(cap) >= 2 else 0
    if not i_win:
        return
    wb = _read_win(gdb, i_win)
    if len(wb) < 4:
        return
    tpl = u32(wb, 0)
    tb = _read_mem(gdb, tpl, 0x18) if tpl else b""
    if len(tb) < 0x14:
        return
    cb = tb[1]
    fn = tb[8]
    tile_data = u32(tb, 0x0C)
    # 游标按 16 步进去重，避免每帧刷屏
    if not ctx._hit(("tm1atlas", i_win, i_cur >> 4)):
        return
    ctx.log(f"\n[JpTm1AtlasLoad] win=0x{i_win:08X} 模板@0x{tpl:08X} "
            f"charBase={cb} font={fn} tileData=0x{tile_data:08X}")
    ctx.log(f"  图集装载进度: 游标=0x{i_cur:04X}({i_cur}) / 容量={g_cap}(0x{g_cap:04X}) "
            f"base=0x{i_base:04X}  "
            f"→ 已装 {i_cur} 字符 ≈ {i_cur * (2 if fn == 3 else 1)} tile")
    ctx.log(f"  占用区间 = tile[{i_base}..{i_base + i_cur * (2 if fn == 3 else 1)})")
    # 实测 VRAM：官方图集落地情况（等价于屏蔽中文打印后的 cb 内容）
    n = min(g_cap or 512, 1024 - i_base)
    runs = _vram_nonempty_runs(gdb, tile_data, i_base, n)
    tot = sum(l for _, l in runs)
    ctx.log(f"  实测 VRAM tile[{i_base}..{i_base + n})：{tot}/{n} 非空")
    ctx.log(f"     {_fmt_runs(runs, limit=16)}")
    # 整 cb 分布（找官方 UI / 窗框 / 残留）
    cb_idx = _cb_of(tile_data)
    for extra in (0, 1):
        base_cb = 0x06000000 + (cb_idx + extra) * 0x4000
        cruns = _vram_nonempty_runs(gdb, base_cb, 0, 512)
        ctot = sum(l for _, l in cruns)
        tag = "本cb" if extra == 0 else "下一cb(跨块)"
        ctx.log(f"  cb{cb_idx + extra}({tag}) 0x{base_cb:08X}：{ctot}/512 非空")
        ctx.log(f"     {_fmt_runs(cruns, limit=16)}")


@handler("V8AllocBegin")
def _on_v8_alloc_begin(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """v8_alloc_begin(r0=win) 入口 = InitTextPrinter 会话边界（重建位图前）。
    诊断领航员翻页是否走「重新开窗」：dump 上一会话位图占用 + ours 段 + 账本段。
    若翻页命中本点而非 TextClearWindow，且位图占用随翻页单调增长 → 旧 tile 未回收。"""
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x1E:
        return
    tb = u16(wb, 0x16)
    tm = wb[0x0A]
    tptr = u32(wb, 0x10)
    idx = u16(wb, 0x14)
    cur = _read_mem(gdb, 0x0203FF42, 2)
    curs = u16(cur, 0) if len(cur) >= 2 else -1
    used = _bitmap_used(gdb)
    _, osegs = _ours_segs(gdb)
    slot, segs = _wl_slot_of(gdb, win)
    if not ctx._hit((win, tb, tptr, idx)):
        return
    ctx.log(f"\n[V8AllocBegin] win=0x{win:08X} TILE_BASE=0x{tb:04X} textMode={tm} "
            f"文本=0x{tptr:08X} idx={idx} cursor=0x{curs:04X} 位图占用={used} "
            f"ours段数={len(osegs)}")
    if slot >= 0:
        ctx.log(f"  账本槽{slot} 段={[(hex(s), l) for s, l in segs]}")
    else:
        ctx.log(f"  账本无该win槽（首次开窗或已被 release 清空）")


@handler("V8Release")
def _on_v8_release(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """v8_release(r0=win) 入口 = Text_ClearWindow hook 触发回收。
    诊断 v8_release 被调用时账本里有没有该 win 的段（决定是否真释放）。"""
    win = regs.get("r0", 0)
    if not win:
        return
    wb = _read_win(gdb, win)
    tb = u16(wb, 0x16) if len(wb) >= 0x18 else 0
    tm = wb[0x0A] if len(wb) >= 0x0B else -1
    used = _bitmap_used(gdb)
    slot, segs = _wl_slot_of(gdb, win)
    if not ctx._hit((win, tb)):
        return
    if slot < 0:
        ctx.log(f"\n[V8Release] win=0x{win:08X} TILE_BASE=0x{tb:04X} textMode={tm} "
                f"★账本无槽（无 tile 可释放） 位图占用={used}")
        return
    ctx.log(f"\n[V8Release] win=0x{win:08X} TILE_BASE=0x{tb:04X} textMode={tm} "
            f"账本槽{slot} 位图占用={used}")
    for s, (st, ln) in enumerate(segs):
        ctx.log(f"  释放段[{s}] start={st}(0x{st:04X}) len={ln}")


@handler("TextClearWindow")
def _on_text_clear_window(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """Text_ClearWindow @0x08003BA8（现被 hook 桩覆盖，断在桩首条 push，r0=win）。
    诊断领航员翻页是否走清窗路径；若是，随后应命中 V8Release（同一 win）。"""
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x1E:
        return
    tb = u16(wb, 0x16)
    tm = wb[0x0A]
    if not ctx._hit((win, tb)):
        return
    ctx.log(f"\n[TextClearWindow] win=0x{win:08X} TILE_BASE=0x{tb:04X} textMode={tm}")


@handler("V8Alloc")
def _on_v8_alloc(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """v8_alloc_tile(r0=win, r1=font_px, r2=glyph_len) 入口（地址随 game.bin 重建变化）。
    记录每次领号请求与请求前游标 + ours 段数；返回值看不到，用下游 last_tile/UpdateTilemap 对账。"""
    win = regs.get("r0", 0)
    px = regs.get("r1", 0) & 0xFF
    gl = regs.get("r2", 0) & 0xFF
    cur = _read_mem(gdb, 0x0203FF42, 2)
    curs = u16(cur, 0) if len(cur) >= 2 else -1
    _, osegs = _ours_segs(gdb)
    if not ctx._hit((win, px, gl, curs, len(osegs))):
        return
    ctx.log(f"[V8Alloc] win=0x{win:08X} font_px={px} glyph_len={gl} 请求前cursor=0x{curs:04X} ours段数={len(osegs)}")


@handler("PncHook")
def _on_pnc_hook(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """PrintNextChar_Hook 入口（r0=win）：读 win 的 text[idx] 记录本字符码。
    用于识别「没走 chs_print 的字符」到底是谁（JP 路径 / SYM 路径 / 控制码）。"""
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x16:
        return
    tptr = u32(wb, 0x10)
    idx = u16(wb, 0x14)
    ch = _read_mem(gdb, tptr + idx, 1) if tptr else b""
    c = ch[0] if ch else -1
    if not ctx._hit((win, c, wb[0x1B])):
        return
    ctx.log(f"[PncHook] win=0x{win:08X} char=0x{c:02X} idx={idx} curTX={wb[0x1B]} curTY={wb[0x1D]}")


@handler("SlotDrawChs")
def _on_slot_draw_chs(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """slot 命中中文流绘制（slot_draw_chinese）：r0=win, r1=流, r2=next_index。
    诊断队伍/图鉴等 slot 名字错位：流字节 + F9 解码 + index 推进。
    可区分「哈希匹配错条目」vs「流正确但 gidx/推进错」。
    ⚠ 地址随 game.bin 重建变化（当前对应 sha 3b370e2cf4e5），重建后须更新。"""
    win = regs.get("r0", 0)
    cn = regs.get("r1", 0)
    nxt = regs.get("r2", 0) & 0xFFFF
    lr = regs.get("r14", 0) & ~1
    data = _read_mem(gdb, cn, 24)
    if not data:
        return
    dec: list[str] = []
    i = 0
    while i < len(data) and data[i] != 0xFF and len(dec) < 20:
        if data[i] == 0xF9 and i + 3 < len(data) and data[i + 1] == 0:
            dec.append(f"字({data[i + 2]:02X}{data[i + 3]:02X})")
            i += 4
        else:
            dec.append(f"{data[i]:02X}")
            i += 1
    idxb = _read_mem(gdb, win + 0x14, 2)
    idx = u16(idxb, 0) if len(idxb) == 2 else -1
    ctx.log(
        f"\n[SLT] win=0x{win:08X} cur_index={idx} next_index={nxt} LR=0x{lr:08X}"
    )
    ctx.log(f"  流@0x{cn:08X}: {data.hex(' ')}")
    ctx.log(f"  解码: {' '.join(dec)}")


@handler("UpdateTilemap")
def _on_update_tilemap(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    if ctx.vram_survey:
        _maybe_vram_survey(gdb, ctx)
    if ctx.ui_survey:
        _survey_ui(gdb, ctx)
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
        f"\n[UTM] win=0x{win:08X} tpl=0x{tpl:08X} u=0x{up:04X} l=0x{lo:04X}"
        f" 格=({cx}+{tx},{cy}+{ty})->#{cell} pal=0x{wb[0x0F]:X} 调用方={who} LR=0x{lr:08X}"
    )
    ctx.log(
        f"  tilemap@0x{tbase:08X} entry@0x{entry_addr:08X} 写前现值={curv.hex(' ')}"
        f" tileData@0x{tdata_base:08X} 像素落点=0x{tdata_base + up * 32:08X}"
    )
    # tile 对内容回读（print_glyph_px 顺序=claim→blend→UpdateTilemap，
    # 此处读到的是 blend 之后的现场：可直接渲染验证形状/叠加残留）
    if tdata_base:
        pair = _read_mem(gdb, tdata_base + up * 32, 64)
        if len(pair) == 64:
            ctx.log(f"  VRAM对内容 u@+0: {pair[:32].hex(' ')}")
            ctx.log(f"             l@+32: {pair[32:].hex(' ')}")
    # 粉框/重绘排查：记录每窗领号轨迹（claim 的 tile 对）
    prev = getattr(ctx, "_utm_track", None)
    if prev is None:
        ctx._utm_track = {}
    ctx._utm_track[win] = up


@handler("RenderTextHandleBold")
def _on_render_bold(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """RenderTextHandleBold：
    - US（cfg.layout=us）：r0=winTemplate, r1=tileData, r2=text
    - JP AXVJ（默认）：r0=像素缓冲 dest, r1=串（血条昵称/数字）
    """
    lr = regs.get("r14", 0) & ~1
    if cfg.get("layout") == "us":
        tpl = regs.get("r0", 0)
        dst = regs.get("r1", 0)
        text = regs.get("r2", 0)
        data = _read_ff_text(gdb, text)
        tplt = _read_mem(gdb, tpl, 0x18) if tpl else b""
        if not ctx._hit((dst, data[:32])):
            return
        ctx.log(f"\n[RenderBold-US] dest=0x{dst:08X} text=0x{text:08X} LR=0x{lr:08X}")
        if len(tplt) >= 0x18:
            ctx.log(
                f"  模板@0x{tpl:08X}: charBase={tplt[1]} font={tplt[8]} textMode={tplt[9]}"
                f" fg/bg/sh={tplt[5]}/{tplt[6]}/{tplt[7]} pal={tplt[4]}"
                f" tileData=0x{u32(tplt, 0x10):08X} tilemap=0x{u32(tplt, 0x14):08X}"
            )
        ctx.log(f"  文本: {data[:48].hex(' ')} 内容={ctx.text_of(data)[:40]!r}")
        return

    dst = regs.get("r0", 0)
    text = regs.get("r1", 0)
    data = _read_ff_text(gdb, text)
    if not ctx._hit(("jp-bold", dst, data[:32], lr)):
        return
    ctx.log(f"\n[RenderBold-JP] dest=0x{dst:08X} text=0x{text:08X} LR=0x{lr:08X}")
    ctx.log(f"  文本: {data[:64].hex(' ')} 内容={ctx.text_of(data)[:48]!r}")
    # 昵称链 LR 落在 Alt2/Main 附近时多打一行提示
    if 0x08042400 <= lr <= 0x08042C80:
        ctx.log("  ※ LR 在 UpdateNick 域 → 血条昵称 Render")


# IWTD 入口→出口配对状态（窗口区预算 = [startOffset, 返回值)）
_IWTD_STATE: dict[str, Any] = {"r0": 0, "start": None}


@handler("InitWindowTileData")
def _on_iwtd(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """分区器入口。
    US（cfg.layout=us）：pokeruby InitWindowTileData(win, startOffset)→下一空闲 offset；
      mode2 预留 width×height 画布，mode1 装 256 字形 atlas。
    JP：逐 glyph 装图集；W0 只在 glyph==0 打详志（避免 256 倍刷屏）。"""
    r0 = regs.get("r0", 0)
    off = regs.get("r1", 0) & 0xFFFF
    _IWTD_STATE["r0"] = r0
    _IWTD_STATE["start"] = off
    r2 = regs.get("r2", 0) & 0xFFFFFFFF
    if cfg.get("layout") == "us":
        if not ctx._hit(("iwtd_us", r0, off)):
            return
        wb = _read_win_us(gdb, r0)
        ctx.log(
            f"\n[W0-IWTD-US] win=0x{r0:08X} startOffset=0x{off:04X}"
            f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
        )
        ctx.log(f"  {_win_fields_us(wb)}")
        if len(wb) >= 0x0B:
            tm, w, h = wb[0x00], wb[0x09], wb[0x0A]
            if tm == 2:
                end = (off + 2 + w * h) & 0xFFFF
                ctx.log(
                    f"  ※ [W0-SPAN?] tm2 预期 start+2+w×h="
                    f"0x{off:04X}..0x{end:04X}（{w}×{h}；以 IWTD-Ret 为准）"
                )
            elif tm == 1:
                ctx.log("  ※ tm1 预期装 atlas（FixedWidth 256×2 tile 量级）")
            elif tm == 0:
                ctx.log("  ※ tm0 变宽线性（UNKNOWN0）")
        return
    glyph = r2 & 0xFF
    if glyph != 0:
        return
    if not ctx._hit(("iwtd_jp0", r0, off)):
        return
    ctx.log(
        f"\n[W0-IWTD-JP] r0=0x{r0:08X} start=0x{off:04X} glyph=0"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    b = _read_mem(gdb, r0, 0x14)
    if not b:
        ctx.log("  （r0 内存读取失败）")
        return
    tpl_ptr = u32(b, 0x00)
    tplt = b
    label = "template"
    if 0x02000000 <= tpl_ptr < 0x03008000 or 0x08000000 <= tpl_ptr < 0x08800000:
        nested = _read_mem(gdb, tpl_ptr, 0x14)
        if len(nested) == 0x14 and 0x06000000 <= u32(nested, 0x0C) <= 0x06018000:
            tplt = nested
            label = f"win→tpl@0x{tpl_ptr:08X}"
    if len(tplt) >= 0x14:
        cb, font, tm = tplt[1], tplt[8], tplt[9]
        td, tmap = u32(tplt, 0x0C), u32(tplt, 0x10)
        ctx.log(
            f"  [{label}] charBase={cb} font={font} textMode={tm}"
            f" tileData=0x{td:08X} tilemap=0x{tmap:08X}"
        )
        ctx.log(
            "  ※ JP 图集路径；模板无 w×h。"
            "私有预算候选：MenuFrame / tilemap 底色 / 美版同场景对照。"
        )


@handler("InitWindowTileDataRet")
def _on_iwtd_ret(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """US：pokeruby IWTD 出口（mov r0,r4 后）r0=下一空闲 tile offset，可算预算。
    JP：同名断点已作废（返回 void），见旧注释。"""
    ret = regs.get("r0", 0) & 0xFFFFFFFF
    r4 = regs.get("r4", 0)
    start = _IWTD_STATE.get("start")
    if cfg.get("layout") == "us":
        next_off = ret & 0xFFFF
        if not ctx._hit(("iwtret_us", _IWTD_STATE.get("r0"), next_off)):
            return
        span = (next_off - (start or 0)) & 0xFFFF if start is not None else 0
        ctx.log(
            f"\n[W0-SPAN] next=0x{next_off:04X}"
            f" start=0x{(start or 0):04X} span={span} tiles"
            f" win=0x{_IWTD_STATE.get('r0', 0):08X}"
        )
        if span >= 2:
            ctx.log(f"  ※ 内容网格 ≈ {span - 2} tile（tm2 可与 w×h 对拍）")
        return
    if not ctx._hit(("iwtret", r4, ret)):
        return
    ctx.log(f"\n[IWTD-Ret]（JP 断点已作废，r0 非返回值）r0=0x{ret:08X} r4=0x{r4:08X}")


@handler("GetCursorTileNum")
def _on_get_cursor_tile(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版 GetCursorTileNum(win, xOffset, yOffset)——对照 tm2 画布 vs tm1 线性。"""
    win = regs.get("r0", 0)
    x_off = regs.get("r1", 0) & 0xFF
    y_off = regs.get("r2", 0) & 0xFF
    wb = _read_win_us(gdb, win) if cfg.get("layout") == "us" else _read_win(gdb, win)
    if cfg.get("layout") != "us":
        ctx.log(f"\n[GCTN]（非 us 布局未实现公式）win=0x{win:08X} x={x_off} y={y_off}")
        return
    pred, how = _us_cursor_tile_num(wb, x_off, y_off)
    key = (win, x_off, y_off, u16(wb, 0x1A) if len(wb) >= 0x1C else 0,
           u16(wb, 0x1C) if len(wb) >= 0x1E else 0, wb[0x10] if len(wb) > 0x10 else 0,
           wb[0x11] if len(wb) > 0x11 else 0)
    if not ctx._hit(key):
        return
    ctx.log(
        f"\n[W0-GCTN] win=0x{win:08X} xOff={x_off} yOff={y_off}"
        f" → 预测 tile=0x{pred:04X} ({how})"
    )
    ctx.log(f"  {_win_fields_us(wb)}")


@handler("DrawGlyphTiles")
def _on_draw_glyph_tiles(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版 DrawGlyphTiles(win, glyph, glyphWidth)——变宽路径写 VRAM 入口（pokeRS 挂点）。"""
    win = regs.get("r0", 0)
    glyph = regs.get("r1", 0) & 0xFFFF
    width = regs.get("r2", 0) & 0xFF
    if not ctx._hit(("dgt", win, glyph, width)):
        return
    wb = _read_win_us(gdb, win) if cfg.get("layout") == "us" else b""
    ctx.log(
        f"\n[DGT] win=0x{win:08X} glyph=0x{glyph:04X} glyphWidth={width}"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    if wb:
        pred0, how0 = _us_cursor_tile_num(wb, 0, 0)
        pred1, _ = _us_cursor_tile_num(wb, 0, 1)
        ctx.log(f"  {_win_fields_us(wb)}")
        ctx.log(f"  本字 TL/BL 预测 0x{pred0:04X}/0x{pred1:04X} ({how0})")


@handler("PrintGlyph_TextMode0")
@handler("PrintGlyph_TextMode1")
@handler("PrintGlyph_TextMode2")
@handler("DrawGlyph_TextMode0")
@handler("DrawGlyph_TextMode2")
def _on_us_print_glyph(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """美版 Print/DrawGlyph_TextMode*：看谁在画、当时 textMode。"""
    win = regs.get("r0", 0)
    glyph = regs.get("r1", 0) & 0xFFFF
    pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
    if not ctx._hit(("uspg", pc, win, glyph)):
        return
    wb = _read_win_us(gdb, win) if cfg.get("layout") == "us" else b""
    ctx.log(f"\n[UsGlyph] PC=0x{pc:08X} win=0x{win:08X} glyph=0x{glyph:04X}")
    if wb:
        ctx.log(f"  {_win_fields_us(wb)}")


def _fmt_jp_template(tplt: bytes, tpl: int) -> str:
    if len(tplt) < 0x14:
        return f"（模板 0x{tpl:08X} 读取失败 len={len(tplt)}）"
    return (
        f"tpl=0x{tpl:08X} bg={tplt[0]} charBase={tplt[1]} screenBase={tplt[2]}"
        f" pal={tplt[4]} font={tplt[8]} textMode={tplt[9]} spacing={tplt[10]}"
        f" tileData=0x{u32(tplt, 0x0C):08X} tilemap=0x{u32(tplt, 0x10):08X}"
        f" （0x14B，无 w×h）"
    )


@handler("TextLoadWindowTemplate")
def _on_text_load_tpl(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """US：Text_LoadWindowTemplate(r0=template) @0x08002A34。
    JP：本点已改钉 MultistepInit 置位 @0x08002950 —— r0=window（+0=tpl 指针），
    r1=tileOffset/mode。旧址 0x080029E0 是图集步进消费方，r0 不是模板。"""
    r0 = regs.get("r0", 0)
    r1 = regs.get("r1", 0) & 0xFFFF
    lr = regs.get("r14", 0) & ~1
    if cfg.get("layout") == "us":
        if not ctx._hit(("tlwt", r0)):
            return
        ctx.log(f"\n[W0-TPL] template=0x{r0:08X} LR=0x{lr:08X}")
        tplt = _read_mem(gdb, r0, 0x20)
        if len(tplt) < 0x18:
            return
        w, h = tplt[13], tplt[14]
        td, tm = u32(tplt, 0x10), u32(tplt, 0x14)
        ctx.log(
            f"  US: bg={tplt[0]} charBase={tplt[1]} screenBase={tplt[2]}"
            f" pal={tplt[4]} font={tplt[8]} textMode={tplt[9]} spacing={tplt[10]}"
            f" left={tplt[11]} top={tplt[12]} w×h={w}×{h}"
            f" tileData=0x{td:08X} tilemap=0x{tm:08X}"
        )
        if tplt[9] == 2 and w and h:
            ctx.log(f"  ※ tm2 预算公式 2+w×h = {2 + w * h}")
        return

    # JP：r0=window
    if not ctx._hit(("tlwt_jp", r0, r1)):
        return
    wb = _read_win(gdb, r0)
    tpl = u32(wb, 0x00) if len(wb) >= 4 else 0
    ctx.log(
        f"\n[W0-TPL] win=0x{r0:08X} tileOff/mode=0x{r1:04X}"
        f" LR=0x{lr:08X}"
    )
    if len(wb) >= 0x1E:
        ctx.log(f"  win: {_win_fields(wb)}")
    if tpl:
        tplt = _read_mem(gdb, tpl, 0x14)
        ctx.log(f"  {_fmt_jp_template(tplt, tpl)}")
    else:
        ctx.log("  （win+0 无有效模板指针）")
    # 对照全局：0x03000328 将被写成 tpl（本函数体随后 STR）
    g = _read_mem(gdb, 0x03000328, 4)
    if len(g) == 4:
        ctx.log(f"  gTplSlot@0x03000328 当前=0x{u32(g, 0):08X}（本调用后应≈tpl）")


@handler("MultistepInitWindowTileData")
def _on_multistep_iwtd(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """JP 图集分帧装载入口 @0x080029E0（旧误标 TextLoadWindowTemplate）。
    入口 r0 无意义；从 gTplSlot 0x03000328 取当前模板。"""
    lr = regs.get("r14", 0) & ~1
    g = _read_mem(gdb, 0x03000328, 4)
    tpl = u32(g, 0) if len(g) == 4 else 0
    if not ctx._hit(("miwtd", tpl, lr)):
        return
    ctx.log(f"\n[W0-MULTI] gTpl=0x{tpl:08X} LR=0x{lr:08X}")
    if tpl:
        tplt = _read_mem(gdb, tpl, 0x14)
        ctx.log(f"  {_fmt_jp_template(tplt, tpl)}")
        if len(tplt) >= 0x14 and tplt[9] == 3:
            ctx.log("  ※ tm3：官方另有 +0x25A(602) 登记路径（见 JpMode3TileBudget）")
    else:
        ctx.log("  （gTplSlot 空）")


@handler("JpMode3TileBudget")
def _on_jp_mode3_budget(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """JP @0x08002C0A：tm3 路径 ADDS r0, r0, r4 之前。
    此前 LDR r1,=0x25A; ADD r0,r1,#0 → r0=0x25A；r4=tileBase。
    结果 end=base+602，与美版对话画布量级同构。"""
    addend = regs.get("r0", 0) & 0xFFFF
    base = regs.get("r4", 0) & 0xFFFF
    lr = regs.get("r14", 0) & ~1
    if addend != 0x25A:
        # 容错：若断点略偏，仍读字面量
        lit = _read_mem(gdb, 0x08002C18, 4)
        if len(lit) == 4:
            addend = u32(lit, 0) & 0xFFFF
    if not ctx._hit(("jp_m3", base, addend)):
        return
    end = (base + addend) & 0xFFFF
    ctx.log(
        f"\n[W0-SPAN-JP] tm3 base=0x{base:04X} +0x{addend:04X}"
        f" → end=0x{end:04X}（span={addend}） LR=0x{lr:08X}"
    )
    ctx.log("  ※ 对话网格类官方预算；菜单 tm1 不走此路径")


@handler("MenuDrawStdWindowFrame")
def _on_menu_frame(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """Menu_DrawStdWindowFrame(left, top, right, bottom)——四寄存器参数，无第5参。
    pokeruby menu.c 与日美 ROM 调用点一致；旧 handler 误读 [sp] 当 height。"""
    left = regs.get("r0", 0) & 0xFF
    top = regs.get("r1", 0) & 0xFF
    right = regs.get("r2", 0) & 0xFF
    bottom = regs.get("r3", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    if right < left or bottom < top:
        w = h = -1
    else:
        w = right - left + 1
        h = bottom - top + 1
    key = (left, top, right, bottom)
    if not ctx._hit(("mframe",) + key):
        return
    ctx.log(
        f"\n[W0-FRAME] left={left} top={top} right={right} bottom={bottom}"
        f" → w×h={w}×{h} tiles  LR=0x{lr:08X}"
    )
    ctx.log(
        "  ※ 框几何（tile 格）；文本私有画布可能更小。"
        "日版无模板 w×h 时，此为几何主候选。"
    )


@handler("MenuLoadStdFrameGraphics")
def _on_menu_load_frame(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """菜单窗框装载入口。"""
    r0 = regs.get("r0", 0)
    r1 = regs.get("r1", 0) & 0xFFFFFFFF
    if not ctx._hit(("mlf", r0, r1)):
        return
    ctx.log(
        f"\n[W0-FRAMEGFX] r0=0x{r0:08X} r1=0x{r1:08X}"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )


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


def _hb_col_ink_rows(col64: bytes, bg: int = 2) -> tuple[int, int, int]:
    """扫 64B 列（上32+下32）：返回 (first_ink_row, last_ink_row, ink_px)。无墨水则 (-1,-1,0)。"""
    if len(col64) < 64:
        return -1, -1, 0
    first, last, n = -1, -1, 0
    for y in range(16):
        row = col64[y * 4 : y * 4 + 4] if y < 8 else col64[32 + (y - 8) * 4 : 32 + (y - 8) * 4 + 4]
        for b in row:
            for nib in ((b >> 4) & 0xF, b & 0xF):
                if nib != 0 and nib != bg:
                    n += 1
                    if first < 0:
                        first = y
                    last = y
    return first, last, n


def _hb_dump_buf_cols(gdb: GdbClient, buf: int, cols: int = 7, bg: int = 2) -> list[str]:
    lines: list[str] = []
    if not buf:
        return ["  （buf=0）"]
    raw = _read_mem(gdb, buf, cols * 0x40)
    if len(raw) < cols * 0x40:
        return [f"  （读缓冲失败 len={len(raw)} @0x{buf:08X}）"]
    for i in range(cols):
        col = raw[i * 0x40 : (i + 1) * 0x40]
        fi, li, n = _hb_col_ink_rows(col, bg)
        top8 = col[:8].hex(" ")
        bot8 = col[32:40].hex(" ")
        lines.append(
            f"  col{i}: ink_rows={fi}..{li} ink_px={n} top8={top8} bot8={bot8}"
        )
        # 整列 64B，供 sim_healthbox_nick.py 仿真「上半是否挡住中文」
        lines.append(f"  col{i}_raw64: {col.hex()}")
    return lines


@handler("UpdateNickAlt2")
def _on_update_nick_alt2(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """JP UpdateNick Alt2 入口 0x08042408。"""
    lr = regs.get("r14", 0) & ~1
    r0 = regs.get("r0", 0) & 0xFF
    if not ctx._hit(("nick-alt2", r0, lr)):
        return
    ctx.log(f"\n[NickAlt2] 入口 spriteId?=r0={r0} LR=0x{lr:08X}")


@handler("HealthboxNickAfterRender")
def _on_hb_nick_after_render(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """Alt2 @0x08042536：RenderText 刚返回，chrome 尚未跑。
    r6=eBattleInterfaceGfxBuffer 列基址，r4=gDisplayedStringBattle，r8=StringLength-6。
    关键：每列墨水落在 row0-15 的哪一段——证明字是贴顶还是已在下半。"""
    buf = regs.get("r6", 0)
    s = regs.get("r4", 0)
    r8 = regs.get("r8", 0) & 0xFFFF
    data = _read_ff_text(gdb, s)
    if not ctx._hit(("nick-after", buf, data[:24], r8)):
        return
    ctx.log(
        f"\n[NickAfterRender] buf=0x{buf:08X} str=0x{s:08X} r8(len-6)={r8}"
        f" LR=0x{(regs.get('r14', 0) & ~1):08X}"
    )
    ctx.log(f"  串: {data[:64].hex(' ')} 内容={ctx.text_of(data)[:48]!r}")
    for line in _hb_dump_buf_cols(gdb, buf, 7, bg=2):
        ctx.log(line)


@handler("HealthboxNickChromeElem")
def _on_hb_nick_chrome_elem(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """GetHealthboxElementGfxPtr @0x08040EF8：r0=元件 id。
    昵称 chrome 会反复打 0x2B/2C/2D；计数可见盖了几列上半。"""
    eid = regs.get("r0", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    # 只关心从 UpdateNick 域打来的
    if not (0x08042400 <= lr <= 0x08042C80):
        return
    if not ctx._hit(("nick-elem", eid, lr)):
        return
    ctx.log(f"\n[NickChromeElem] id=0x{eid:02X} LR=0x{lr:08X}")


@handler("HealthboxNickObjCopy")
def _on_hb_nick_obj_copy(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """Alt2 @0x080425CC：chrome/pad 已结束，开始拷 OBJ。再 dump 一次缓冲对比 AfterRender。"""
    buf = regs.get("r6", 0)
    r8 = regs.get("r8", 0) & 0xFFFF
    r5 = regs.get("r5", 0) & 0xFFFF
    if not ctx._hit(("nick-obj", buf, r8)):
        return
    ctx.log(
        f"\n[NickObjCopy] buf=0x{buf:08X} r8(cols)={r8} r5={r5}"
        f" （chrome 之后；对照 NickAfterRender 看上半是否被 0x2B 盖掉）"
    )
    for line in _hb_dump_buf_cols(gdb, buf, 7, bg=2):
        ctx.log(line)


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
#   三件套齐 → 权威尺寸 + 未渐变 ROM 调色板 → 导出 PNG 到 work/（不写 tiles.presets）；
#   缺任一环仅记日志不落盘。跨局按 yaml 已有 preset 的 md5 指纹跳过重导。

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
    """tiles 实时采集器 v2（登记 + 绑定 → 导 PNG）。

    Load* 埋点登记资产：sheets[tag]={ROM 数据}, pal_by_tag[tag]=ROM 源；
    CreateSprite 埋点读 SpriteTemplate 得 (tileTag, paletteTag, 权威 w/h/is8)
    并落 bindings。三件套齐 → 导出 PNG 到 work/{game}/tiles/；
    **不**写回 yaml 的 tiles.presets（人工维护）。缺环仅记日志不落盘。
    跨局按已有 preset 配置 md5 指纹比对，一致则跳过重导。
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
        """仅用于指纹比对（对照 yaml 已有条目）；不写回配置。"""
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
    """通用日志行。有增强 handler 时只打短头（避免每命中重复整段 description）。"""
    lr = regs.get("r14", 0) & ~1
    r0123 = " ".join(f"{k}=0x{regs.get(k, 0) & 0xFFFFFFFF:08X}" for k in ("r0", "r1", "r2", "r3"))
    pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
    if hook.fn is not None:
        ctx.log(f"\n[{hook.name}] PC=0x{pc:08X} LR=0x{lr:08X} {r0123}")
        return
    desc = f" — {hook.point.description}" if hook.point.description else ""
    ctx.log(f"\n[{hook.name}]{desc}\n  PC=0x{pc:08X} LR=0x{lr:08X} {r0123}")


_US_CANVAS_FUNCS = (
    "TextLoadWindowTemplate,InitWindowTileData,InitWindowTileDataRet,"
    "InitTextPrinter,PrintNextChar,PrintGlyph_TextMode0,PrintGlyph_TextMode1,"
    "PrintGlyph_TextMode2,DrawGlyphTiles,GetCursorTileNum,UpdateTilemap,"
    "DrawGlyph_TextMode0,DrawGlyph_TextMode2,MenuDrawStdWindowFrame"
)

# W0 预算勘测（docs/开发_20260908_日美文本划界移植可行性.md §6.2）
# 美版：模板 w×h + IWTD 返回 span + 窗框几何 + GCTN 抽检
_W0_US_FUNCS = (
    "TextLoadWindowTemplate,InitWindowTileData,InitWindowTileDataRet,"
    "InitVariableWidthFontTileData,InitMenuWindow,InitTextPrinter,"
    "MenuDrawStdWindowFrame,GetCursorTileNum,Text_ClearWindow"
)
# 日版：模板账本 + IWTD 图集（仅 glyph0 详志）+ 窗框几何 + InitTextPrinter
# 勿挂 InitWindowTileDataRet（JP 返回 void，已作废）
_W0_JP_FUNCS = (
    "TextLoadWindowTemplate,MultistepInitWindowTileData,JpMode3TileBudget,"
    "InitWindowTileData,InitTextPrinter,"
    "MenuDrawStdWindowFrame,MenuLoadStdFrameGraphics,TextClearWindow,"
    "UpdateTilemap"
)
# tm1 → 30×20 划界预算勘测（去 UpdateTilemap 噪音；InitTextPrinter 打 [W0-BUDGET]）
_W0_TM1_FUNCS = (
    "InitTextPrinter,InitWindowTileData,JpMode3TileBudget,"
    "TextLoadWindowTemplate,MultistepInitWindowTileData,"
    "MenuDrawStdWindowFrame,MenuLoadStdFrameGraphics"
)
# v8 回收链路诊断（2026-09-09 领航员清 tile）：
# 会话边界 + 领号 + 回收 + 清窗，四路对照判断翻页走哪条路、旧 tile 是否被释放。
_V8_RECLAIM_FUNCS = (
    "InitTextPrinter,V8AllocBegin,V8Alloc,V8Release,TextClearWindow"
)
# 日版 UI 分配接管勘测（2026-09-09）：
# tm3 官方分配入口 + 解压后实测占用 + 预算登记 + 开窗/打印对照。
# 目的：确认「tm3 UI 从 tileOffset 起、预算 602」是否属实，实际占用多少，
#       以及官方 UI 与我们 v8 领号区（lo=0x100）如何重叠。
_JP_UI_ALLOC_FUNCS = (
    "JpTm1Alloc,JpTm1AtlasLoad,"
    "TextLoadWindowTemplate,InitTextPrinter,V8AllocBegin,"
    "MenuLoadStdFrameGraphics,MenuDrawStdWindowFrame"
)


def _warn_wrong_game_for_canvas_survey(game: str, functions: Optional[str],
                                        origin_path: str) -> list[str]:
    """防呆：美版画布采集却挂日版 yaml / 错 ROM 会打出垃圾字段。"""
    warns: list[str] = []
    funcs = {s.strip() for s in (functions or "").split(",") if s.strip()}
    us_markers = {"GetCursorTileNum", "DrawGlyphTiles", "PrintGlyph_TextMode2",
                  "InitVariableWidthFontTileData"}
    if funcs & us_markers and game != "POKEMON_RUBY_AXVE":
        warns.append(
            f"当前 --game={game}，但 --functions 含美版画布点 "
            f"({', '.join(sorted(funcs & us_markers))})。"
            "应对美版 1.0 使用: --game POKEMON_RUBY_AXVE "
            "（日版地址/布局不同，日志会像乱码）。"
        )
    if game == "POKEMON_RUBY_AXVE":
        op = Path(origin_path)
        if op.is_file():
            try:
                code = op.read_bytes()[0xAC:0xB0]
            except OSError:
                code = b""
            if code and code != b"AXVE":
                warns.append(
                    f"--origin 游戏码={code!r}，期望 AXVE（美版 Ruby 1.0）。"
                    "1.1/1.2 地址会漂。"
                )
        else:
            warns.append(
                "未找到 --origin 文件；请传 "
                'roms/origin/Pokemon Ruby Version(US).gba（1.0）。'
            )
    return warns


def _arm(ctx: Ctx, hook: Hook) -> bool:
    try:
        ctx.gdb.set_sw_break(hook.bp)
    except GdbError as e:
        ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} 失败: {e}")
        return False
    ctx.log(f"  断点 {hook.name} @0x{hook.bp:08X} OK")
    return True


# --- 给 tile/调色板类埋点统一叠加「动画上下文」 --------------------------------
# 必须放在所有 @handler 注册之后（本文件末尾那段 _mk_sheet_handler 循环注册
# 会覆盖同名 handler），这里对已注册的函数再包一层：先跑原逻辑，再追加动画态。
# 只在 gAnimScriptActive 为真时才追加 ⇒ 平时日志不受影响，放技能时才详打。
# 这是「放技能黑屏」的关键判据：能看出「哪个技能的第几条脚本命令触发了这次写入」。
_ANIM_AUGMENT = (
    "LoadSpriteSheet",        # sheet → OBJ VRAM
    "LoadSpritePalette",      # 调色板 → gPlttBuffer OBJ 区
    "LoadCompressedObjectPic",
    "LoadCompressedObjectPalette",
    "LoadCompressedPalette",
    "LoadPalette",            # 调色板 2× 拷贝
    "LZDecompressVram",       # LZ77 直接解压进 VRAM（dest 落在 BG 还是 OBJ 是黑屏关键）
    "CreateSprite",
)


def _augment_tile_handlers_with_anim() -> None:
    for name in _ANIM_AUGMENT:
        orig = HANDLERS.get(name)
        if orig is None or getattr(orig, "_anim_augmented", False):
            continue

        def wrapper(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any],
                    _o=orig) -> None:
            _o(gdb, regs, ctx, cfg)
            note = _tile_anim_note(gdb)
            if note:
                ctx.log(note)

        wrapper._anim_augmented = True      # type: ignore[attr-defined]
        wrapper.__doc__ = orig.__doc__
        HANDLERS[name] = wrapper


# 模块加载即生效（在 run_log 之前）
_augment_tile_handlers_with_anim()


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
    # --preset us-canvas：一键美版画布对照（防挂错日版 yaml）
    if getattr(args, "preset", None) == "us-canvas":
        args.game = "POKEMON_RUBY_AXVE"
        if not args.functions:
            args.functions = _US_CANVAS_FUNCS
        args.no_tiles = True
        default_us = REPO_ROOT / "roms" / "origin" / "Pokemon Ruby Version(US).gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_us.is_file():
            args.origin = str(default_us)

    # --preset w0-us / w0-jp：划界预算勘测（模板·IWTD·窗框·绑基址）
    if getattr(args, "preset", None) == "w0-us":
        args.game = "POKEMON_RUBY_AXVE"
        if not args.functions:
            args.functions = _W0_US_FUNCS
        args.no_tiles = True
        args.ui_survey = True
        default_us = REPO_ROOT / "roms" / "origin" / "Pokemon Ruby Version(US).gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_us.is_file():
            args.origin = str(default_us)
    if getattr(args, "preset", None) == "w0-jp":
        args.game = "POKEMON_RUBY_AXVJ00"
        if not args.functions:
            args.functions = _W0_JP_FUNCS
        args.no_tiles = True
        args.ui_survey = True
        default_jp = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_jp.is_file():
            args.origin = str(default_jp)
    if getattr(args, "preset", None) == "w0-tm1":
        args.game = "POKEMON_RUBY_AXVJ00"
        if not args.functions:
            args.functions = _W0_TM1_FUNCS
        args.no_tiles = True
        args.cb_survey = True
        default_jp = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_jp.is_file():
            args.origin = str(default_jp)
    # --preset v8-reclaim：v8 回收链路诊断（领航员清 tile）
    if getattr(args, "preset", None) == "v8-reclaim":
        args.game = "POKEMON_RUBY_AXVJ00"
        if not args.functions:
            args.functions = _V8_RECLAIM_FUNCS
        args.no_tiles = True
        default_jp = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_jp.is_file():
            args.origin = str(default_jp)
    # --preset jp-ui-alloc：日版 tm1 UI 分配勘测（主战场：textMode==1）
    if getattr(args, "preset", None) == "jp-ui-alloc":
        args.game = "POKEMON_RUBY_AXVJ00"
        if not args.functions:
            args.functions = _JP_UI_ALLOC_FUNCS
        args.no_tiles = True
        default_jp = REPO_ROOT / "roms" / "origin" / "POKEMON_RUBY_AXVJ00.gba"
        if args.origin == str(DEFAULT_ORIGIN) and default_jp.is_file():
            args.origin = str(default_jp)

    for w in _warn_wrong_game_for_canvas_survey(args.game, args.functions, args.origin):
        print(f"警告: {w}", file=sys.stderr)

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
        charmap_single, double = load_charmap(charmap_src)
        # 项目 charmap 的单字节重定义（如 SYM 标点带 36=; 37=。 3A=、 3B=，
        # 3C=！ 3D=？ 3E=：）必须覆盖日文 PCS 底包，否则日志把标点解码成
        # が/ご（2026-08-30 图鉴说明误判实证）。
        single.update(charmap_single)
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

    # 运行时再核一次：读 ROM 头游戏码（stub 映射的 0x08000000）
    if args.game == "POKEMON_RUBY_AXVE":
        try:
            live = bytes(gdb.read_mem(0x080000AC, 4))
            if live != b"AXVE":
                print(
                    f"警告: mGBA 当前 ROM 游戏码={live!r}，期望 AXVE。"
                    "请换成美版 Ruby 1.0 再采。",
                    file=sys.stderr,
                )
        except GdbError:
            pass

    ctx = Ctx(gdb, logpath, single, double, origin, dedup=not args.no_dedup,
              vram_survey=bool(getattr(args, "vram_survey", False)),
              cb_survey=bool(getattr(args, "cb_survey", False)),
              ui_survey=bool(getattr(args, "ui_survey", False)))

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
        tiles_note = f"tiles 采集开 → PNG {_tiles_out_dir(args.game).name}/（不写 presets）"

    ctx.log(
        f"\n===== gdb_patcher log @ {time.strftime('%H:%M:%S')}"
        f" [{args.game}: {', '.join(h.name for h in hooks)}] {mode} ====="
    )
    ctx.log(f"  {tiles_note}")

    if getattr(args, "bypass_text", False):
        _write_bypass_text(gdb, ctx)

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


# ---------------------------------------------------------------------------
# export-scene：把日志里的 [CBAVOID] 段反向生成 scene_cfg.c 的避让带 C 代码 ---
# ---------------------------------------------------------------------------
# 采集（log --cb-survey --bypass-text）与导出（export-scene）是一对：重采日志后
# 直接重跑 export-scene 就能重建表，不必手抄。--reuse-names 指向现有 scene_cfg.c
# 可保留人工起的语义名（kPartyAvoid 之类）与手写注释，不退化成 kTpl43C_1。
#
# 用法：
#   python src/util/gdb_patcher.py export-scene
#   python src/util/gdb_patcher.py export-scene --out scene_avoid.c \
#          --reuse-names configs/POKEMON_RUBY_AXVJ00/hook/src/text/scene_cfg.c

_CBAVOID_HDR_RE = re.compile(
    r"^\[CBAVOID\]\s+场景签名\s+mode=(\d+)\s+DISPCNT=0x([0-9A-Fa-f]{4})")
_BG_LINE_RE = re.compile(
    r"^\s*BG(\d):\s*charBase=(\d+)\s+screenBase=(\d+)\s+8bpp=(\d+)\s+启用=(\d+)")
_CB_SURVEY_LINE_RE = re.compile(
    r"^\s*cb(\d)(?:\(OBJ\))?\s*\(0x[0-9A-Fa-f]+\):\s*(.*)$")
_TPL_LINE_RE = re.compile(
    r"模板@(0x[0-9A-Fa-f]+):\s*charBase=(\d+)\s+pal=\d+\s+C/D/E=\S+\s+"
    r"font=(\d+)\s+textMode=(\d+)")

def _parse_band_ranges(text: str) -> list[tuple[int, int]]:
    """'[0x001-0x0D4] [0x0D6-0x0DC]' / '（全空）' → [(lo,hi)] 闭区间。"""
    if not text or ("全空" in text) or ("失败" in text) or ("不足" in text):
        return []
    return [(int(a, 16), int(b, 16))
            for a, b in re.findall(r"\[(0x[0-9A-Fa-f]+)-(0x[0-9A-Fa-f]+)\]", text)]


def _merge_bands_cb(ranges: list[tuple[int, int, int]],
                    gap: int = 3) -> list[tuple[int, int, int]]:
    """按 char_base 分组后合并闭区间。项为 (char_base, lo, hi)。"""
    by_cb: dict[int, list[list[int]]] = {}
    for cb, lo, hi in sorted(ranges):
        out = by_cb.setdefault(cb, [])
        if out and lo - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(cb, lo, hi) for cb, segs in sorted(by_cb.items())
            for lo, hi in segs]


def _parse_cbavoid_scenes(log_path: str, gap: int = 3) -> list[dict]:
    """从 gdb 日志抽取 [CBAVOID] 段，先按硬件签名去重，再按 tpl 并成一条。

    返回每项 dict：tpl / bands[(char_base,lo,hi)] / sources[原始签名摘要…]
    DISPCNT/BGxCNT 只进注释，不进生成的 C 结构。
    """
    with open(log_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    raw_scenes: list[dict] = []
    seen: set[tuple] = set()
    for i, line in enumerate(lines):
        if not _CBAVOID_HDR_RE.match(line):
            continue
        m = _CBAVOID_HDR_RE.match(line)
        dispcnt = int(m.group(2), 16)          # type: ignore[union-attr]
        bgs: list[tuple[int, int, int, int]] = []
        for L in range(4):
            bm = (_BG_LINE_RE.match(lines[i + 1 + L])
                  if i + 1 + L < len(lines) else None)
            bgs.append(
                (int(bm.group(2)), int(bm.group(3)),
                 int(bm.group(4)), int(bm.group(5))) if bm else (0, 0, 0, 0))
        sig = (dispcnt, tuple(bgs))
        if sig in seen:                         # 同签名只取首次出现
            continue
        seen.add(sig)

        cb_raw: dict[int, str] = {}
        for j in range(i + 5, min(i + 13, len(lines))):
            cm = _CB_SURVEY_LINE_RE.match(lines[j])
            if cm:
                cb_raw[int(cm.group(1))] = cm.group(2).strip()

        tpl = char_base = font = text_mode = None
        conts: list[str] = []
        for j in range(i, min(i + 45, len(lines))):
            tm_ = _TPL_LINE_RE.search(lines[j])
            if tm_ and tpl is None:
                tpl = int(tm_.group(1), 16)
                char_base = int(tm_.group(2))
                font = int(tm_.group(3))
                text_mode = int(tm_.group(4))
            if lines[j].startswith("  内容:") and len(conts) < 2:
                conts.append(lines[j][7:].strip())
        if char_base is None or tpl is None:
            continue

        # 每块 cb 保留自己的相对号（不再折进窗 charBase 的 0..1023）
        bands_cb: list[tuple[int, int, int]] = []
        for k, text in cb_raw.items():
            if k > 3:                           # 跳过 OBJ 区调查行
                continue
            for lo, hi in _parse_band_ranges(text):
                bands_cb.append((k, lo, hi))
        bands = _merge_bands_cb(bands_cb, gap)

        raw_scenes.append(dict(
            line=i + 1, dispcnt=dispcnt, bgs=bgs, tpl=tpl,
            char_base=char_base, font=font, text_mode=text_mode,
            cont=conts, cb_raw=cb_raw, bands=bands, raw_n=len(bands_cb)))

    # 同 tpl 并集
    by_tpl: dict[int, dict] = {}
    for sc in raw_scenes:
        tpl = sc["tpl"]
        if tpl not in by_tpl:
            by_tpl[tpl] = dict(
                tpl=tpl, bands=list(sc["bands"]), sources=[sc],
                raw_n=sc["raw_n"])
        else:
            ent = by_tpl[tpl]
            ent["bands"] = _merge_bands_cb(ent["bands"] + sc["bands"], gap)
            ent["sources"].append(sc)
            ent["raw_n"] += sc["raw_n"]
    return list(by_tpl.values())


def _parse_existing_scene_names(path: Optional[str]) -> dict[int, dict]:
    """从已有 scene_cfg.c 抽取 tpl → {scene, doc}（新格式仅按 tpl）。"""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    out: dict[int, dict] = {}
    pat = re.compile(
        r"static\s+const\s+struct\s+V8AvoidScene\s+(\w+)\s*=\s*\{(.*?)\};", re.S)
    for m in pat.finditer(src):
        name, body = m.group(1), m.group(2)
        mm = re.search(r"\.tpl\s*=\s*(0x[0-9A-Fa-f]+|\d+)u?", body)
        if not mm:
            continue
        tpl = int(mm.group(1), 0)
        doc: list[str] = []
        for ln in reversed(src[:m.start()].rstrip().split("\n")):
            s = ln.strip()
            if s.startswith("//"):
                doc.insert(0, s)
            else:
                break
        out[tpl] = dict(scene=name, doc=doc)
    return out


def _gen_avoid_c(scenes: list[dict], reuse: Optional[dict] = None,
                 gap: int = 3) -> str:
    """生成 scene_cfg.c 避让带片段：每 tpl 一条，bands 内联，band_n 写死数字。"""
    reuse = reuse or {}
    used: set[str] = set()
    names: list[str] = []

    def _fresh(tpl: int) -> str:
        base = f"kTpl{(tpl & 0xFFF):03X}Scene"
        cand, k = base, 2
        while cand in used:
            cand = f"{base}_{k}"
            k += 1
        used.add(cand)
        return cand

    def _bg_desc(sc: dict) -> str:
        parts = []
        for n, bg in enumerate(sc["bgs"]):
            cb, sb, bpp, en = bg
            parts.append(f"BG{n} cb{cb} sb{sb} {'8bpp' if bpp else '4bpp'}"
                         f"{'*' if en else ''}")
        return " | ".join(parts)

    out: list[str] = []
    for sc in scenes:
        tpl = sc["tpl"]
        old = reuse.get(tpl)
        name = old["scene"] if old else _fresh(tpl)
        used.add(name)
        names.append(name)
        if old and old.get("doc"):
            out.extend(old["doc"])
        else:
            out.append("// " + "-" * 74)
            out.append(f"//   tpl 0x{tpl:08X}（{len(sc['sources'])} 个硬件签名并集）")
            for src in sc["sources"]:
                out.append(f"//   · 行{src['line']} DISPCNT 0x{src['dispcnt']:04X} "
                           f"winCb{src['char_base']} font{src['font']} "
                           f"tm{src['text_mode']} | {_bg_desc(src)}")
                if src["cont"]:
                    out.append("//     内容: " + " / ".join(src["cont"])[:64])
            out.append(f"//   bands {len(sc['bands'])} 段"
                       f"（原 {sc['raw_n']} 段，缝隙 <= {gap} 合并）")
            out.append("// " + "-" * 74)
        out.append(f"static const struct V8AvoidScene {name} = {{")
        out.append(f"    .tpl    = 0x{tpl:08X}u,")
        out.append("    .bands  = (const struct V8AvoidBand[]) {")
        for cb, lo, hi in sc["bands"]:
            out.append(f"        {{ .char_base = {cb}u, "
                       f".lo = 0x{lo:03X}u, .hi = 0x{hi:03X}u }},")
        out.append("    },")
        out.append(f"    .band_n = {len(sc['bands'])}u,")
        out.append("};")
        out.append("")

    out.append("const struct V8AvoidScene kV8AvoidScenes[] = {")
    for name in names:
        out.append(f"    {name},")
    out.append("};")
    out.append("")
    out.append("const unsigned kV8AvoidSceneN =")
    out.append("    (unsigned)(sizeof(kV8AvoidScenes) / sizeof(kV8AvoidScenes[0]));")
    return "\n".join(out) + "\n"


def run_export_scene(args: argparse.Namespace) -> int:
    """导出日志里的避让带场景为 scene_cfg.c 片段（纯离线，不连 gdb）。"""
    logpath = args.log or str(REPO_ROOT / "src" / "util" / "work"
                              / args.game / "gdb_patcher_log.log")
    if not os.path.exists(logpath):
        print(f"[export-scene] 日志文件不存在: {logpath}", file=sys.stderr)
        print("提示：先跑 log --cb-survey --bypass-text 采集，或用 --log 指定路径。",
              file=sys.stderr)
        return 1

    scenes = _parse_cbavoid_scenes(logpath, gap=args.gap)
    if not scenes:
        print(f"[export-scene] 日志里没有 [CBAVOID] 段: {logpath}", file=sys.stderr)
        return 1

    reuse = _parse_existing_scene_names(args.reuse_names)
    code = _gen_avoid_c(scenes, reuse, gap=args.gap)

    if args.out in (None, "-"):
        sys.stdout.write(code)
    else:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        print(f"[export-scene] {len(scenes)} 个 tpl → {args.out}")

    reused = sum(1 for s in scenes if s["tpl"] in reuse)
    print(f"[export-scene] tpl {len(scenes)} 条 / "
          f"复用旧名 {reused} 条（--reuse-names={args.reuse_names or '未指定'}）",
          file=sys.stderr)
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
    ap.add_argument(
        "cmd",
        choices=["log", "export-scene"],
        help="log：追踪 yaml 定义的监听点；"
             "export-scene：把日志里的 [CBAVOID] 段导出为 scene_cfg.c 避让带代码",
    )
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
        "--vram-survey", action="store_true",
        help="cb3 勘验：场景签名变化时自动报告 BG 层 charbase/tilemap 引用/cb3 占用")
    ap.add_argument(
        "--cb-survey", action="store_true",
        help="cb 区占用采集（避让带）：配合屏蔽文本打印开关（ADDR_V6_BYPASS=1），"
        "在 InitTextPrinter 命中时扫 VRAM 6 个 charblock 非零 tile，输出官方避让带区间")
    ap.add_argument(
        "--ui-survey", action="store_true",
        help="UI/窗口勘验（三路线采集）：场景签名变化时报 BG 层 size/atlas 引用计数/"
        "cb 字库区范围/OBJ tile 位图/OAM 实测；InitTextPrinter 命中时附 win 结构 0x40B dump"
        "（找 width/height）。建议配 --functions InitTextPrinter,InitWindowTileData,"
        "InitWindowTileDataRet 使用")
    ap.add_argument(
        "--bypass-text", action="store_true",
        help="连接后写 ADDR_V6_BYPASS(0x0203FEB8)=1 屏蔽所有文本打印，"
        "让 --cb-survey 采到纯官方避让带")
    ap.add_argument(
        "--preset",
        default=None,
        choices=["us-canvas", "w0-us", "w0-jp", "w0-tm1", "v8-reclaim",
                 "jp-ui-alloc"],
        help="us-canvas：美版画布对照；"
             "w0-us / w0-jp：划界预算勘测（模板·IWTD·窗框·ITP，开 ui-survey，关 tiles）；"
             "w0-tm1：tm1→30×20 划界预算（ITP 打 [W0-BUDGET]，开 cb-survey，关 tiles）；"
             "v8-reclaim：v8 回收链路诊断（InitTextPrinter/V8AllocBegin/V8Alloc/V8Release/TextClearWindow，关 tiles）；"
             "jp-ui-alloc：日版 tm1 UI 分配勘测（JpTm1Alloc@0x080029DA 拿图集预留区间 "
             "[tileOffset,+容量)，JpTm1AtlasLoad@0x080029E0 实测官方图集落地与 cb 分布；"
             "建议用原版日版 ROM，关 tiles）",
    )
    ap.add_argument(
        "--no-tiles",
        action="store_true",
        help="关闭 tiles 实时采集（默认开：sheet→OAM 配对→导 PNG 到 work/；不写 tiles.presets）",
    )
    ap.add_argument("--log", default=None,
                    help=r"日志文件路径；缺省 src\util\work\{gameId}\gdb_patcher_log.log（按游戏分目录）")
    ap.add_argument("--origin", default=str(DEFAULT_ORIGIN), help="原盘 ROM 路径（同址对照用；美版请传美版 ROM 路径）")
    ap.add_argument(
        "--out",
        default=None,
        help="export-scene：输出文件路径；'-' 或省略则打到 stdout",
    )
    ap.add_argument(
        "--reuse-names",
        default=None,
        help="export-scene：已有 scene_cfg.c 路径，按 tpl 复用其"
             "场景名/手写注释，避免重采后退化成 kTplXXX_1Scene",
    )
    ap.add_argument(
        "--gap",
        type=int,
        default=3,
        help="export-scene：相邻避让带缝隙 <= N tile 即合并（默认 3）",
    )
    args = ap.parse_args(argv)

    try:
        if args.cmd == "export-scene":
            return run_export_scene(args)
        return run_log(args)
    except GdbError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
