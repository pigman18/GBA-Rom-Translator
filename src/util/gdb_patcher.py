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
  - 其它单字节：默认按日文 PCS 假名表解码（ROM 为 AXVJ 日版底包）
  - 该点 cfg.charmap / --charmap：`F7 00 hi lo` 汉字查表

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

# 中文编码（hook/src/game.h + PrintNextChar_hook.c）：
#   F7 00 hi lo = 单汉字内联，4 字节，hi/lo 是 charmap 码位


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
) -> str:
    """解码 FF 结尾文本：`F7 00 hi lo` → 查表；
    控制码 → \\n/\\l/\\CC/\\v；其它单字节 → 查 single（当前字库）。"""
    out: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == 0xFF:
            break
        if b == 0xF7:
            if i + 3 < n and data[i + 1] == 0x00:
                key = (data[i + 2] << 8) | data[i + 3]
                out.append(double.get(key, f"<F7:{key:04X}>"))
                i += 4
                continue
            out.append("<F7>")
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
    ):
        self.gdb = gdb
        self.logpath = logpath
        self.single = single
        self.double = double
        self.origin = origin
        self.dedup = dedup
        self.vram_survey = vram_survey
        self._vram_sig: object = None
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
        b = bytes(gdb.read_mem(win, 0x24))
    except GdbError:
        return b""
    return b[:0x24]


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
        # +0x20 = RenderTextHandleBold 写进去的 dest buffer ptr（tm2/buffered 的基址）
        + (f" TILE_DATA=0x{u32(wb, 0x20):08X}" if len(wb) >= 0x24 else "")
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


@handler("UnusedPrintMonName")
def _on_unused_print_mon_name(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """图鉴分类覆盖入口：dump name 串 + left/top，对照 origin 5 格右对齐。"""
    name = regs.get("r0", 0)
    left = regs.get("r1", 0) & 0xFF
    top = regs.get("r2", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    data = _read_ff_text(gdb, name)
    if not ctx._hit((name, data[:64], left, top)):
        return
    ctx.log(
        f"\n[UnusedPrintMonName] name=0x{name:08X} left={left} top={top} "
        f"LR=0x{lr:08X}"
    )
    ctx.log(f"  原始字节: {data[:64].hex(' ')}")
    ctx.log(f"  内容: {ctx.text_of(data)!r}")


@handler("Menu_PrintText")
def _on_menu_print_text(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """MenuPrint：分类行 / UnusedPrintMonName / 训练家之眼详情行（LR∈EC0xx）。"""
    buf = regs.get("r0", 0)
    left = regs.get("r1", 0) & 0xFF
    top = regs.get("r2", 0) & 0xFF
    lr = regs.get("r14", 0) & ~1
    # 分类行 CATEGORY_LEFT=13,y=5；或从 UnusedPrintMonName / 我们的 hook 返回
    from_cat = left == 13 and top == 5
    from_hook = (0x0808DD60 <= lr <= 0x0808DDD2) or (0x08800000 <= lr <= 0x08810000)
    from_te_detail = 0x080EC000 <= lr <= 0x080EC200  # 详情 line stepper 打印
    if not (from_cat or from_hook or from_te_detail):
        return
    data = _read_ff_text(gdb, buf)
    if not ctx._hit((buf, data[:64], left, top, lr)):
        return
    tag = "TE_detail" if from_te_detail else "Menu_PrintText"
    ctx.log(
        f"\n[{tag}] buf=0x{buf:08X} left={left} top={top} "
        f"pxY={top * 8} LR=0x{lr:08X}"
    )
    ctx.log(f"  原始字节: {data[:64].hex(' ')}")
    ctx.log(f"  内容: {ctx.text_of(data)!r}")


@handler("TrainerEye_DetailLineY")
def _on_te_detail_line_y(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """详情行 Y：r3=line，r1=&scroll（半字）；原式 y=(line*2+2+scroll)&0x1F。"""
    line = regs.get("r3", 0) & 0xFFFF
    scroll_p = regs.get("r1", 0)
    scroll = 0
    try:
        raw = gdb.read_mem(scroll_p, 2)
        if raw and len(raw) >= 2:
            scroll = int.from_bytes(raw[:2], "little")
    except Exception:
        pass
    y16 = (scroll + 2 + line * 2) & 0x1F
    y12 = ((scroll + 2) * 8 + line * 12) // 8 & 0x1F
    phase12 = ((scroll + 2) * 8 + line * 12) & 7
    if not ctx._hit((line, scroll, y16)):
        return
    ctx.log(
        f"\n[TrainerEye_DetailLineY] line={line} scroll={scroll} "
        f"y16={y16}(px={y16 * 8}) y12_tile={y12} phase={phase12} "
        f"px12={(scroll + 2) * 8 + line * 12}"
    )


@handler("TE_PrintLocation_flag")
def _on_te_print_location_flag(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """进详情 PrintLocation 分指点：读左栏地点 tile 带(0x81..0x8E)有墨数。

    BUG-A 取证用：origin 进详情不 scrub，地点旧字模存活 → locink≈14；
    汉化 hook 的 scrub_list_arena 全池清洗 → locink=0（地点空白）。
    修复后应恢复到与列表页一致，作为可证伪预测字段。
    左栏窗 tilemap=0x0600F800，地点占屏幕 y=5/6 x=1..12。
    """
    TM = 0x0600F800
    tiles: set[int] = set()
    try:
        for y in (5, 6):
            raw = bytes(gdb.read_mem(TM + (y * 32 + 1) * 2, 24))
            for k in range(0, 24, 2):
                t = (raw[k] | (raw[k + 1] << 8)) & 0x3FF
                if t:
                    tiles.add(t)
    except Exception:
        pass
    inked = 0
    detail = []
    for t in sorted(tiles):
        try:
            d = bytes(gdb.read_mem(0x06000000 + t * 32, 32))
            n = sum(1 for b in d if b)
        except Exception:
            n = 0
        if n:
            inked += 1
            detail.append(f"{t:x}:{n}")
    flag = regs.get("r0", 0) & 0xFF
    # 切换训练家源数据取证：sel=blk[0x8772]，地点名索引=blk+0xCEEA+sel*8，
    # 重打缓冲 blk+0xD138（PrintLeftStats 0x080EC2E0 拼好的地点串）。
    blk = regs.get("r2", 0)
    sel = loc = -1
    d138 = -1
    if 0x02000000 <= blk < 0x04000000:
        try:
            sel = int.from_bytes(bytes(gdb.read_mem(blk + 0x8772, 2)), "little")
            if sel & 0x8000:
                sel -= 0x10000
            loc = int.from_bytes(bytes(gdb.read_mem(blk + 0xCEEA + sel * 8, 2)), "little")
            d138 = int.from_bytes(bytes(gdb.read_mem(blk + 0xD138, 4)), "little")
        except Exception:
            pass
    ctx.log(
        f"\n[TE_LocInk] locink={inked} flag={flag} sel={sel} loc={loc} d138={d138} "
        f"tiles={','.join(f'{t:x}' for t in sorted(tiles))} "
        f"inked_detail={' '.join(detail)}"
    )


@handler("DexRowDup")
def _on_dex_row_dup(
    gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]
) -> None:
    """图鉴列表跨行 tile 双重引用计数（BUG-B 可证伪判据）。

    根因：tile = TB+2+(row&7)*62+col*2 只有 8 个 band，图鉴列表 11 行时
    第 9~11 行 row&7 回绕到 5/6/7，与第 1~3 行同 tile，字模互相覆盖
    （顶行 No003 妙妙花 -> No011 ------）。

    统计方式：扫列表窗 tilemap（0x0600F7000），按 tile 号归并引用它的
    屏幕行；被 >1 个不同行引用即记一次 dup。排除精灵球图标 0x1FC/0x1FD
    （设计上就是所有行共用同一图标）。
    修复前 f043 实测 16 对；修复后应为 0。
    """
    TM = 0x06007000
    CB = 0x06008000
    ICON = {0x1FC, 0x1FD}
    # GDB stub 单包上限 0x100，tilemap 2048B 必须分块读
    try:
        chunks = [bytes(gdb.read_mem(TM + off, 0x100))
                  for off in range(0, 32 * 32 * 2, 0x100)]
        raw = b"".join(chunks)
    except Exception:
        ctx.log("\n[DexRowDup] 读 tilemap 失败")
        return
    if len(raw) < 32 * 32 * 2:
        ctx.log(f"\n[DexRowDup] 读 tilemap 不完整 {len(raw)}B")
        return
    own: dict[int, set[int]] = {}
    for row in range(32):
        for col in range(32):
            o = (row * 32 + col) * 2
            t = (raw[o] | (raw[o + 1] << 8)) & 0x3FF
            if t:
                own.setdefault(t, set()).add(row)
    dup = 0
    dups: list[str] = []
    for t, rows in sorted(own.items()):
        if t in ICON or len(rows) < 2:
            continue
        # 只统计「有墨」的 tile（空槽被多行引用不算撞字）
        try:
            d = bytes(gdb.read_mem(CB + t * 32, 32))
            if not any(d):
                continue
        except Exception:
            continue
        dup += 1
        dups.append(f"{t:x}@r{','.join(str(r) for r in sorted(rows))}")
    ctx.log(f"\n[DexRowDup] dup={dup} " + (" ".join(dups[:10]) if dups else ""))


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


@handler("SaveInfoDraw")
def _on_save_info(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """HandleDrawSaveWindowInfo 入口。"""
    n = int(cfg.get("n") or 32)
    ctx.log("")
    ctx.log("[SaveInfo] r0=0x%08X r1=0x%08X r2=0x%08X r3=0x%08X lr=0x%08X"
            % (regs.get("r0",0), regs.get("r1",0), regs.get("r2",0),
               regs.get("r3",0), regs.get("r14",0)))


@handler("GlyphPtr")
def _on_glyph_ptr(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """GetGlyphTilePointers(fontNum, glyph, **upper, **lower)。"""
    fn = regs.get("r0", 0) & 0xFF
    g  = regs.get("r1", 0) & 0xFFFF
    pu = regs.get("r2", 0)
    if fn != 3 or not (0xA0 <= g <= 0xAF):
        return
    key = (fn, g, pu)
    if not ctx._hit(key):
        return
    ctx.log("")
    ub = _read_mem(gdb, pu, 4) if pu else b""
    up = u32(ub, 0) if len(ub) >= 4 else 0
    first = _read_mem(gdb, up, 16) if up else b""
    ctx.log("[GlyphPtr] fn=%d glyph=0x%02X  pu=0x%08X  *upper=0x%08X"
            % (fn, g, pu, up))
    ctx.log("           字模: " + first.hex(" "))


@handler("TilemapWriter")
def _on_tilemap_writer(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """UpdateTilemap(win, upper, lower) —— 报参数与栈顶调用者。"""
    win = regs.get("r0", 0)
    up = regs.get("r1", 0) & 0xFFFF
    lo = regs.get("r2", 0) & 0xFFFF
    if not win:
        return
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        return
    cx = wb[0x1A]; ctx_ = wb[0x1B]
    cty = wb[0x1C] + wb[0x1D]
    key = (win, cx, cty, up)
    if not ctx._hit(key):
        return
    lr = regs.get("lr", 0)
    ctx.log("")
    ctx.log("[TMW] win=0x%08X upper=0x%03X lower=0x%03X curX=%d curTX=%d ty=%d lr=0x%08X"
            % (win, up, lo, cx, ctx_, cty, lr))


@handler("BandDump")
def _on_band(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """报每个窗的 curX/curY 与 grid_row/band（每 (win,ty) 只报一次）。"""
    win = regs.get("r0", 0)
    if not win:
        return
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        return
    cx = wb[0x1A]; cty = wb[0x1C] + wb[0x1D]
    row = cty >> 1
    band = row & 7
    tb = u16(wb, 0x16)
    key = (win, cty, tb)
    if not ctx._hit(key):
        return
    ctx.log("")
    ctx.log("[BAND] win=0x%08X tm=%d fn=%d TB=0x%04X curX=%d curY+TY=%d"
            % (win, wb[0x0A], wb[0x0B], tb, cx, cty))
    ctx.log("       -> row=%d  band=%d  tile_base=TB+2+%d*62+2*col"
            % (row, band, band))


@handler("PcsGlyphDump")
def _on_pcs_glyph(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """只报 glyph 在 0xA0..0xAF 的字符，附带完整串。"""
    win = regs.get("r0", 0)
    if not win:
        return
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        return
    idx = u16(wb, 0x14)
    tptr = u32(wb, 0x10)
    if not tptr:
        return
    c = _read_mem(gdb, tptr + idx, 1)
    if not c:
        return
    g = c[0]
    if not (0xA0 <= g <= 0xAF):
        return
    whole = _read_mem(gdb, tptr, 24)
    key = (win, idx, g)
    if not ctx._hit(key):
        return
    ctx.log("")
    ctx.log("[PCS] glyph=0x%02X idx=%d fn=%d tm=%d curX=%d curTX=%d curY=%d curTY=%d TB=0x%04X"
            % (g, idx, wb[0x0B], wb[0x0A], wb[0x1A], wb[0x1B], wb[0x1C], wb[0x1D], u16(wb, 0x16)))
    ctx.log("      整串: " + whole.hex(" "))


@handler("SaveBoxWinDump")
def _on_savebox_win(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """save 场景：报每个窗的 textMode / TB / curX / curY 与即将处理的字节。"""
    win = regs.get("r0", 0)
    if not win:
        return
    wb = _read_win(gdb, win)
    if len(wb) < 0x20:
        return
    tm = wb[0x0A]
    tb = u16(wb, 0x16)
    cx = wb[0x1A]; ctx_ = wb[0x1B]
    cy = wb[0x1C]; cty = wb[0x1D]
    idx = u16(wb, 0x14)
    tptr = u32(wb, 0x10)
    key = (win, idx)
    if not ctx._hit(key):
        return
    data = _read_mem(gdb, tptr + idx, 12) if tptr else b""
    ctx.log("")
    toff = u16(wb, 0x18)
    tpl = u32(wb, 0x00)
    ctx.log("[SB] win=0x%08X tm=%d fn=%d TB=0x%04X TOFF=0x%04X b1E=%d b1F=%d TPL=0x%08X ptr=0x%08X idx=%d curX=%d curTX=%d curY=%d curTY=%d"
            % (win, tm, wb[0x0B], tb, toff, wb[0x1E], wb[0x1F], tpl, tptr, idx, cx, ctx_, cy, cty))
    ctx.log("     字节: " + data.hex(" "))


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
    # ★ 缓冲起点全貌：定位「名字被固定长度截断」类问题（BUG-8）。
    #   text+index 只看到断点之后，看不到整串是从哪开始、被砍在哪。
    #   读 tptr 起 64B，配合 index 就能算出「展开后的名字占了几字节」。
    if tptr and cfg.get("bufdump"):
        whole = _read_mem(gdb, tptr, 64)
        ctx.log(f"  缓冲起点@0x{tptr:08X}: {whole.hex(' ')}")


@handler("StringCopyN")
def _on_strcpyn(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """StringCopyN(dst=r0, src=r1, n=r2) 入口：定位「固定长度截断」类 BUG。

    BUG-8「野生的雷?/蛇??」的根因就在这类硬编码长度上：
    原版日文名 ≤5 假名，代码里写死 `movs r2,#7`（6B 名槽 + FF），
    而中文名是 `F7 00 hi lo` × N，3 字要 12B，直接被截断成
    「1 个汉字 + 半个汉字」，屏幕上就是残字。
    LR 告诉我们是谁在拷贝；len 就是那个写死的上限。
    """
    dst = regs.get("r0", 0)
    src = regs.get("r1", 0)
    n = regs.get("r2", 0)
    lr = regs.get("r14", 0) & ~1
    if not ctx._hit((lr, n)):
        return
    ctx.log(f"\n[StringCopyN] LR=0x{lr:08X} n={n} dst=0x{dst:08X} src=0x{src:08X}")
    if src:
        ctx.log(f"  源串: {_read_mem(gdb, src, min(n + 8, 40)).hex(' ')}")
    if dst:
        ctx.log(f"  目标: {_read_mem(gdb, dst, min(n + 8, 40)).hex(' ')}")


@handler("NickSlotDump")
def _on_nickslot_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """NickSlot_Hook 内 GetMonData(mon,11) 返回后：r0=species, r4=mon, r5=dst。"""
    r0 = regs.get("r0", 0)
    r4 = regs.get("r4", 0)
    r5 = regs.get("r5", 0)
    n = int(cfg.get("n") or 24)
    ctx.log("")
    ctx.log("[NickSlot] species(r0)=0x%X (%d)  mon=0x%08X  dst=0x%08X"
            % (r0, r0, r4, r5))
    if r4:
        ctx.log("  mon+0 : " + _read_mem(gdb, r4, n).hex(" "))
        ctx.log("  mon+8 : " + _read_mem(gdb, r4 + 8, n).hex(" "))


@handler("SpDump")
def _on_sp_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """读当前栈指针附近内容，用于看「展开后的名字到底多长」。

    BUG-8 排查用：在 0x08042436（bl 0x8004290 截断）处下点，
    sp 里就是 0x08042430 展开出来的物种名。若这里只有 10B，
    说明截断发生在上游；若这里有 12B 而缓冲只有 10B，说明是本函数砍的。
    """
    sp = regs.get("r13", 0)
    n = int(cfg.get("n") or 40)
    if not sp:
        return
    ctx.log(f"\n[SpDump] sp=0x{sp:08X} r0=0x{regs.get('r0',0):08X} "
            f"r5=0x{regs.get('r5',0):08X} lr=0x{regs.get('r14',0)&~1:08X}")
    ctx.log(f"  栈内容: {_read_mem(gdb, sp, n).hex(' ')}")
    # 源字段：r5 是宝可梦结构指针，名字在 +8。直接读原始源，
    # 判断「是源本身就短」还是「拷贝时被砍」。
    r5 = regs.get("r5", 0)
    if r5:
        ctx.log(f"  源 r5+8 : {_read_mem(gdb, r5 + 8, n).hex(' ')}")
        ctx.log(f"  源 r5+0 : {_read_mem(gdb, r5, 24).hex(' ')}")
    for _rn in ("r4", "r6", "r7", "r8", "r9"):
        _rv = regs.get(_rn, 0)
        if _rv:
            ctx.log(f"  {_rn}=0x{_rv:08X} : {_read_mem(gdb, _rv, 20).hex(' ')}")


@handler("Param3Dump")
def _on_param3(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """param3 处理器 0x0803A1E6：r9=mon。"""
    r9 = regs.get("r9", 0)
    n = int(cfg.get("n") or 32)
    ctx.log("")
    ctx.log("[Param3] r9=0x%08X r7=0x%08X" % (r9, regs.get("r7", 0)))
    if r9:
        ctx.log("  mon+0 : " + _read_mem(gdb, r9, n).hex(" "))
        ctx.log("  mon+8 : " + _read_mem(gdb, r9 + 8, n).hex(" "))
        ctx.log("  +18/+19: " + _read_mem(gdb, r9 + 18, 4).hex(" "))


@handler("SpNameHookDump")
def _on_spname_hook(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """SpeciesNameExpand_Hook 入口：r9=mon, r7=dst。"""
    r9 = regs.get("r9", 0)
    r7 = regs.get("r7", 0)
    n = int(cfg.get("n") or 32)
    ctx.log("")
    ctx.log("[SpNameHook] r9(mon)=0x%08X r7(dst)=0x%08X" % (r9, r7))
    if r9:
        ctx.log("  mon+0  : " + _read_mem(gdb, r9, n).hex(" "))
        ctx.log("  mon+8  : " + _read_mem(gdb, r9 + 8, n).hex(" "))
    if r7:
        ctx.log("  dst    : " + _read_mem(gdb, r7, n).hex(" "))


@handler("SlotSrcDump")
def _on_slot_src(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """占位符2 else 分支入口：r9 = 源结构指针，+8 是名字槽。"""
    r9 = regs.get("r9", 0)
    r7 = regs.get("r7", 0)
    n = int(cfg.get("n") or 40)
    ctx.log("")
    ctx.log("[SlotSrcDump] r9=0x%08X r7(dst)=0x%08X" % (r9, r7))
    if r9:
        ctx.log("  r9+0  : " + _read_mem(gdb, r9, n).hex(" "))
        ctx.log("  r9+8  : " + _read_mem(gdb, r9 + 8, n).hex(" "))


@handler("NickAfterCopy")
def _on_nick_after_copy(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict) -> None:
    """StringCopy 之后：看目标缓冲 r4-3 与 sp。"""
    sp = regs.get("r13", 0)
    r4 = regs.get("r4", 0)
    n = int(cfg.get("n") or 32)
    ctx.log("")
    ctx.log("[NickAfterCopy] r4=0x%08X sp=0x%08X r6=0x%08X"
            % (r4, sp, regs.get("r6", 0)))
    if sp:
        ctx.log("  sp : " + _read_mem(gdb, sp, n).hex(" "))
    if r4:
        ctx.log("  r4-3: " + _read_mem(gdb, (r4 - 3) & 0xFFFFFFFF, n).hex(" "))


@handler("NickHookMid")
def _on_nick_hook_mid(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """NickFullName_Hook 第3步前（StringCopy 之前）：看 species 与 sp 里的完整名。"""
    sp = regs.get("r13", 0)
    n = int(cfg.get("n") or 32)
    ctx.log("")
    ctx.log("[NickHookMid] r6(species)=0x%08X r4(dst)=0x%08X sp=0x%08X"
            % (regs.get("r6", 0), regs.get("r4", 0), sp))
    if sp:
        ctx.log("  sp[0..31] : " + _read_mem(gdb, sp, n).hex(" "))
    r4 = regs.get("r4", 0)
    if r4:
        ctx.log("  r4[0..31] : " + _read_mem(gdb, r4, n).hex(" "))


@handler("SpeciesDump")
def _on_species_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """0x080424B8：GetMonData(mon, 11) 已拿到 species、正要定位结构。

    验证「这个函数内部本来就有 species」——若有，就能直接用新表查名字，
    不必依赖 gBattleTextBuff2 的 10B 槽。
    """
    # sl 是 r10，GDB g 包给 r0..r12，r10 即 sl
    slv = regs.get("r10", 0)
    sp = regs.get("r13", 0)
    n = int(cfg.get("n") or 32)
    ctx.log("\n[SpeciesDump] r10(sl)=0x%08X r5(mon)=0x%08X r4=0x%08X r6=0x%08X"
            % (slv, regs.get("r5", 0), regs.get("r4", 0), regs.get("r6", 0)))
    if sp:
        ctx.log(f"  栈 sp: {_read_mem(gdb, sp, n).hex(' ')}")
    r5 = regs.get("r5", 0)
    if r5:
        ctx.log(f"  mon+0: {_read_mem(gdb, r5, 24).hex(' ')}")
        ctx.log(f"  mon+8: {_read_mem(gdb, r5 + 8, n).hex(' ')}")


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


@handler("UpdateTilemap")
def _on_update_tilemap(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    if ctx.vram_survey:
        _maybe_vram_survey(gdb, ctx)
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
# BUG-12 血条名字调查（2026-11-24）
# 目标：实测 Alt2(sub_80451A0) 的循环次数 r8 与名字缓冲真实内容，
#       判定「日文字模二次覆盖」到底写了几格、写了什么。
#   0x0804252C = r8 定型点（r0 = StringLength(gDisplayedStringBattle)，r8 = r0）
#   0x0804253E = 图形搬运循环体入口
# ---------------------------------------------------------------------------

@handler("HgLoopCount")
def _on_hg_loop_count(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """r8 定型点：r0=StringLength(gDisplayedStringBattle)，下一步 r8=r0。"""
    r0 = regs.get("r0", 0) & 0xFFFFFFFF
    r2 = regs.get("r2", 0) & 0xFFFFFFFF
    r3 = regs.get("r3", 0) & 0xFFFFFFFF
    side = "我方" if r3 == 0x03004290 else ("敌方" if r3 == 0x030044F0 else f"r3=0x{r3:08X}")
    ctx.log(f"\n[HgLoopCount] {side}  StringLength(gDisplayedStringBattle)=r0={r0}  ⇒ r8={r0}")
    if cfg.get("buf"):
        buf = int(cfg["buf"], 0) if isinstance(cfg["buf"], str) else cfg["buf"]
        n = int(cfg.get("bufn", 32))
        data = _read_mem(gdb, buf, n)
        if data:
            ctx.log(f"  buf@0x{buf:08X}: {data.hex(' ')}")
            end = data.find(b"\xff")
            ctx.log(f"  到首个FF: {ctx.text_of(data[:end + 1] if end >= 0 else data)!r}")


@handler("HgBufDump")
def _on_hg_buf_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """名字缓冲完整 dump（含中文名是否已在 ff 之后）。"""
    r0 = regs.get("r0", 0) & 0xFFFFFFFF
    r3 = regs.get("r3", 0) & 0xFFFFFFFF
    side = "我方" if r3 == 0x03004290 else ("敌方" if r3 == 0x030044F0 else f"r3=0x{r3:08X}")
    buf = 0x0202362C
    data = _read_mem(gdb, buf, 40)
    ctx.log(f"\n[HgBufDump] {side} StringLength(gDisplayedStringBattle)=r0={r0} (r8={r0})")
    if data:
        ctx.log(f"  buf[40]: {data.hex(' ')}")
        end = data.find(b"\xff")
        ctx.log(f"  到首个FF(={end}): {ctx.text_of(data[:end + 1] if end >= 0 else data)!r}")
        tail = data[end + 1:] if end >= 0 else b""
        if tail:
            e2 = tail.find(b"\xff")
            ctx.log(f"  FF之后的内容: {ctx.text_of(tail[:e2 + 1] if e2 >= 0 else tail)!r}")


@handler("HgCopyStart")
def _on_hg_copy_start(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """图形搬运循环入口：r8 在别的寄存器/高寄存器里，dump 关键值。"""
    r2 = regs.get("r2", 0) & 0xFFFFFFFF
    ctx.log(f"\n[HgCopyStart] r2={hex(r2)} (0x04000008=原版32B / 0x04000006=被砍24B)")


@handler("HgTilePtr")
def _on_hg_tile_ptr(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """循环体内：r6=目标 tile 指针，r8=次数，r5=当前格。"""
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    ctx.log(f"\n[HgTilePtr] r6(dst ptr)=0x{r6:08X} region={region_of(r6)}")


@handler("HgPnc")
def _on_hg_pnc(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """血条名字的 PrintNextChar：只看 buffered 窗（tm=2 且 tmap=NULL）。

    ★ 2026-11-24 权威结论（pokeruby battle_interface.c:1545 + 反汇编 0x080424D8）：
      血条名字走 RenderTextHandleBold，它**强制 win[0x0A]=2**（buffered），
      并把 tileData 参数写进 win[0x20]。tileData =
        &eBattleInterfaceGfxBuffer[0x520 + battlerPos * 0x180]
        = 0x02000520 + pos*0x180   （EWRAM，不是 VRAM！）
      ⇒ 与队伍界面同一条 buffered 直写路径，**不是 12px 网格**。
      每字按 rel*64B 线性排布（1 字 = 1 个 64B 单元 = 上下两片 8x8）。
    """
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x24:
        return
    tm = wb[0x0A]
    if tm != 2:
        return                      # 只关心 buffered（血条/HP 数字）
    tpl = u32(wb, 0x00)
    tmap = 0
    if tpl:
        tb = _read_mem(gdb, tpl, 0x18)
        if len(tb) >= 0x14:
            tmap = u32(tb, 0x10)
    td = u32(wb, 0x20)
    idx = u16(wb, 0x14)
    tptr = u32(wb, 0x10)
    cur = (tptr + idx) & 0xFFFFFFFF if tptr else 0
    rel = wb[0x1B]
    if not ctx._hit(("HGPNC", win, cur, td, rel)):
        return
    ctx.log(
        f"\n[HgPnc] win=0x{win:08X} tm={tm} fn={wb[0x0B]} tpl=0x{tpl:08X} tmap=0x{tmap:08X}"
    )
    ctx.log(f"  TILE_DATA(+0x20)=0x{td:08X} region={region_of(td)} rel(curTX)={rel}")
    ctx.log(f"  ★ buffered 写址 = 0x{td + rel * 64:08X}  (td + rel*64B, 每字 64B)")
    ctx.log(f"  curX={wb[0x1A]} curY={wb[0x1C]} TOFF=0x{u16(wb, 0x18):04X}")
    if cur:
        data = _read_mem(gdb, cur, 20)
        ctx.log(f"  即将处理@0x{cur:08X}: {data.hex(' ')}")


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
        write_presets: bool = False,
    ):
        self.gdb = gdb
        self.game_yaml = game_yaml
        self.out_dir = out_dir
        self.origin = origin
        self.log = log
        self.enabled = enabled
        # 2026-11-19：`rt_*` 自动配置只按「Loader 命中」推断图集切分，
        # 实际尺寸/调色板大量判错（被用户点名删除）。默认不再写 yaml，
        # 只导出 PNG 供人工核对；需要时显式传 write_presets=True。
        self.write_presets = write_presets
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
            if self.write_presets:
                self._upsert_preset(sh, cfg, md5hex)
            else:
                self.log(f"  [tiles] 导出 PNG @0x{sh.data_addr:08X}（不写 yaml："
                         f"rt_* 自动配置已停用）")
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

        single = dict(JP_BYTE_TO_CHAR)  # AXVJ 日版底包：非 F7 单字节按日文 PCS
        decode_mode = "日文PCS"
    else:
        single = {}                     # 非日版：原样字节，不做假名解码
        decode_mode = "原始字节（非日版不解码）"
    charmap_src = _pick_charmap(args, points)
    double: dict[int, str] = {}
    if charmap_src:
        _, double = load_charmap(charmap_src)
        mode = f"{decode_mode} + F7 00 字库 {charmap_src}"
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

    ctx = Ctx(gdb, logpath, single, double, origin, dedup=not args.no_dedup,
              vram_survey=bool(getattr(args, "vram_survey", False)))

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
        "--vram-survey", action="store_true",
        help="cb3 勘验：场景签名变化时自动报告 BG 层 charbase/tilemap 引用/cb3 占用")
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


@handler("HgBeforeSkip")
def _on_hg_before_skip(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """hook B 执行前：EWRAM 名字缓冲是否已含 elem 0x2B 的 0x22 底色。"""
    buf = 0x02000520
    data = _read_mem(gdb, buf, 192)
    if not data:
        return
    if not ctx._hit(("HGBS", bytes(data[:32]))):
        return
    from collections import Counter
    ctx.log(f"\n[HgBeforeSkip] EWRAM 0x02000520 (hook B 之前)")
    for i in range(3):
        u = data[i * 64:(i + 1) * 64]
        c = Counter(u)
        top = c.most_common(3)
        ctx.log(f"  unit{i}: {u[:16].hex(' ')}  top={top}")


@handler("HgAfterSeg2")
def _on_hg_after_seg2(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """第二段结束后：EWRAM 与 VRAM 都要看。"""
    buf = 0x02000520
    data = _read_mem(gdb, buf, 192)
    if not data:
        return
    if not ctx._hit(("HGAS", bytes(data[:32]))):
        return
    from collections import Counter
    ctx.log(f"\n[HgAfterSeg2] EWRAM 0x02000520 (第二段之后)")
    for i in range(3):
        u = data[i * 64:(i + 1) * 64]
        c = Counter(u)
        ctx.log(f"  unit{i}: {u[:16].hex(' ')}  top={c.most_common(3)}")


@handler("HgFieldDump")
def _on_hg_field_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """BUG-12 现场：血条名字窗（tileData >= 0x02000520）的全部关键字段。

    重点验证：原版 textMode2 是「win[0x20] 指针自己 +64」，
    我们用「base + rel*64」。若 rel(win[0x1B]) 初值非 0，落址就整体偏移。
    """
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x24:
        return
    if wb[0x0A] != 2:
        return
    td = u32(wb, 0x20)
    if td < 0x02000520 or td >= 0x02001000:
        return                       # 只看血条名字区
    idx = u16(wb, 0x14)
    tptr = u32(wb, 0x10)
    cur = (tptr + idx) & 0xFFFFFFFF if tptr else 0
    if not ctx._hit(("HGFD", win, cur, td, wb[0x1B])):
        return
    ctx.log(f"\n[HgFieldDump] win=0x{win:08X}")
    ctx.log(f"  tm(0x0A)={wb[0x0A]} fn(0x0B)={wb[0x0B]}")
    ctx.log(f"  TILE_DATA(0x20)=0x{td:08X}   ★ 落址基址")
    ctx.log(f"  cursorX(0x1A)={wb[0x1A]}  cursorTileX(0x1B)={wb[0x1B]}  ★ rel")
    ctx.log(f"  cursorY(0x1C)={wb[0x1C]}  cursorTileY(0x1D)={wb[0x1D]}")
    ctx.log(f"  TILE_BASE(0x16)=0x{u16(wb, 0x16):04X} TILE_OFFSET(0x18)=0x{u16(wb, 0x18):04X}")
    ctx.log(f"  我们算出的写址 = 0x{td + wb[0x1B] * 64:08X}   (base + rel*64)")
    ctx.log(f"  原版等价写址 = 0x{td:08X}  （指针累加，与 rel 无关）")


@handler("HgWinId")
def _on_hg_win_id(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """区分敌我：dump 名字串内容 + 落址基址，确认哪个窗画的是谁。"""
    win = regs.get("r0", 0)
    wb = _read_win(gdb, win)
    if len(wb) < 0x24 or wb[0x0A] != 2:
        return
    td = u32(wb, 0x20)
    if td < 0x02000520 or td >= 0x02001000:
        return
    tptr = u32(wb, 0x10)
    idx = u16(wb, 0x14)
    if not tptr:
        return
    whole = _read_mem(gdb, tptr, 32)
    if not whole:
        return
    if not ctx._hit(("HGWIN", td, bytes(whole[:16]))):
        return
    end = whole.find(b"\xff")
    txt = ctx.text_of(whole[:end + 1] if end >= 0 else whole)
    ctx.log(f"\n[HgWinId] tileData=0x{td:08X} 色C/D/E={wb[0x0C]}/{wb[0x0D]}/{wb[0x0E]}")
    ctx.log(f"  串: {txt!r}")
    ctx.log(f"  bytes: {whole[:20].hex(' ')}")


@handler("HgCpuSetDst")
def _on_hg_cpuset_dst(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """第二段 CpuSet 实测：src/dst/ctrl，看敌方名字被写到哪个 tile。"""
    src = regs.get("r0", 0) & 0xFFFFFFFF
    dst = regs.get("r1", 0) & 0xFFFFFFFF
    ctrl = regs.get("r2", 0) & 0xFFFFFFFF
    if dst < 0x06000000 or dst >= 0x06018000:
        return
    if not ctx._hit(("HGCS", src, dst)):
        return
    tile = (dst - 0x06010000) // 32
    ctx.log(f"  [CpuSet] src=0x{src:08X} dst=0x{dst:08X} (tile 0x{tile:03X}) ctrl=0x{ctrl:08X}")


@handler("HgCsAlt1")
@handler("HgCsMain")
@handler("HgCsAlt2b")
def _on_hg_cs_any(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """三个平行实现的 CpuSet 统一探测：看敌方(pos1)走哪条。"""
    src = regs.get("r0", 0) & 0xFFFFFFFF
    dst = regs.get("r1", 0) & 0xFFFFFFFF
    ctrl = regs.get("r2", 0) & 0xFFFFFFFF
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGCSA", pc, src, dst)):
        return
    region = "?"
    if 0x02000520 <= src < 0x020006A0:
        region = "我方(0x520)"
    elif 0x020006A0 <= src < 0x02000820:
        region = "敌方(0x6A0)"
    elif 0x02000820 <= src < 0x020009A0:
        region = "pos2"
    tile = (dst - 0x06010000) // 32 if dst >= 0x06010000 else -1
    ctx.log(f"  [Cs@{pc:08X}] src=0x{src:08X}({region}) dst=0x{dst:08X} tile=0x{tile:03X} ctrl=0x{ctrl:08X}")


@handler("HgGuard")
def _on_hg_guard(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """第二段守卫：记录每个 battler 的状态位，判断谁被跳过。

    0x080425B2  ldrh r0,[r4,#0x3A]  -> 状态索引
    0x080425B8  bl 0x0807584C       -> (flag[r0+off] & 1)
    0x080425C0  bne skip            -> 非0 就跳过整个第二段
    """
    r4 = regs.get("r4", 0) & 0xFFFFFFFF
    if not (0x02000000 <= r4 < 0x02040000):
        return
    st = _read_mem(gdb, r4 + 0x3A, 2)
    stv = (st[0] | (st[1] << 8)) & 0xFF if len(st) >= 2 else -1
    if not ctx._hit(("HGG", r4, stv)):
        return
    # 两个守卫的实际返回值
    f1 = _read_mem(gdb, 0x02023758, 1)
    g1 = (f1[0] & 1) if f1 else -1
    ctx.log(f"\n[HgGuard] r4=0x{r4:08X} 状态索引[r4+0x3A]=0x{stv:02X}")
    ctx.log(f"  守卫2 @0x02023758 = 0x{(f1[0] if f1 else 0):02X}  bit0={g1}")
    ctx.log(f"  → bit0=1 时整个第二段被跳过（名字不进 VRAM）")


@handler("HgCsBak")
@handler("HgCsBak2")
def _on_hg_cs_bak(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """备用路径 CpuSet：pos1(敌方) 走这里。"""
    src = regs.get("r0", 0) & 0xFFFFFFFF
    dst = regs.get("r1", 0) & 0xFFFFFFFF
    ctrl = regs.get("r2", 0) & 0xFFFFFFFF
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGCB", pc, src, dst)):
        return
    tag = "我方" if 0x02000520 <= src < 0x020006A0 else ("敌方" if 0x020006A0 <= src < 0x02000820 else "?")
    tile = (dst - 0x06010000) // 32 if dst >= 0x06010000 else -1
    ctx.log(f"  [Bak@{pc:08X}] src=0x{src:08X}({tag}) dst=0x{dst:08X} tile=0x{tile:03X} ctrl=0x{ctrl:08X}")


@handler("HgR6Trace")
def _on_hg_r6(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """追踪 r6（EWRAM 名字缓冲指针）在各关键点的值。"""
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGR6", pc, r6, r8)):
        return
    tag = "我方(0x520)" if 0x520 <= r6 < 0x6A0 else ("敌方(0x6A0)" if 0x6A0 <= r6 < 0x820 else "?")
    ctx.log(f"  [r6@{pc:08X}] r6=0x{r6:08X}({tag}) r8={r8}")


@handler("HgR6Skip")
@handler("HgR6Seg2")
@handler("HgR6Bak")
def _on_hg_r6_points(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGR6P", pc, r6, r8)):
        return
    ctx.log(f"  [r6@{pc:08X}] r6=0x{r6:08X} r8={r8}")


@handler("HgEwDump")
def _on_hg_ew_dump(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """在 CpuSet 那一刻 dump EWRAM 源区：判断搬过去的是字形还是背景。

    关键：必须在真正 bl CpuSet 之前读，且读 r6 指向的区域（不是 r0）。
    """
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGEW", pc, r6)):
        return
    data = _read_mem(gdb, r6, 64)
    if not data:
        return
    nz = sum(1 for b in data if b not in (0x00, 0x22))
    tag = "我方" if r6 < 0x020006A0 else "敌方"
    ctx.log(f"  [EW@{pc:08X}] {tag} r6=0x{r6:08X} r8={r8} 非背景字节={nz}")
    ctx.log(f"      {data[:32].hex(' ')}")


@handler("HgEwSeg2")
@handler("HgEwBak")
def _on_hg_ew_pts(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    if not (0x02000000 <= r6 < 0x02040000):
        return
    if not ctx._hit(("HGEWP", pc, r6)):
        return
    data = _read_mem(gdb, r6, 32)
    if not data:
        return
    nz = sum(1 for b in data if b not in (0x00, 0x22))
    tag = "我方" if r6 < 0x020006A0 else "敌方"
    ctx.log(f"  [EWP@{pc:08X}] {tag} src=0x{r6:08X} 非背景={nz}  {data[:16].hex(' ')}")


@handler("HgAfterDraw")
def _on_hg_after_draw(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """RenderTextHandleBold 返回瞬间（0x08042536）：
    名字刚画完，EWRAM 里就是最终内容。直接 dump 两个区，不推测。
    """
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not (0x02000000 <= r6 < 0x02040000):
        return
    data = _read_mem(gdb, r6, 0x180)
    if not data:
        return
    key = (r6, bytes(data[:48]))
    if not ctx._hit(("HGAD",) + key):
        return
    tag = "我方(0x520)" if r6 < 0x020006A0 else "敌方(0x6A0)"
    ctx.log(f"\n[HgAfterDraw] {tag} r6=0x{r6:08X} r8(串长)={r8}")
    # 逐 64B 单元统计
    for i in range(4):
        unit = data[i * 64:(i + 1) * 64]
        if not unit:
            break
        nz = sum(1 for b in unit if b not in (0x00, 0x22))
        ctx.log(f"  单元{i} (0x{r6 + i * 64:08X}): 非背景={nz:2d}  {unit[:24].hex(' ')}")


@handler("HgCsTrace")
@handler("HgCsTrace2")
def _on_hg_cs_trace(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """精确记录每次 CpuSet 的 源指针 + 目标 tile + 源内容指纹。"""
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    src = regs.get("r0", 0) & 0xFFFFFFFF
    dst = regs.get("r1", 0) & 0xFFFFFFFF
    if dst < 0x06010000 or dst >= 0x06018000:
        return
    tile = (dst - 0x06010000) // 32
    # 读源前 8 字节做指纹
    head = _read_mem(gdb, src, 8) if 0x02000000 <= src < 0x02040000 else None
    sig = head.hex() if head else "????"
    if not ctx._hit(("HGCT", pc, src, dst)):
        return
    tag = "我方" if 0x02000520 <= src < 0x020006A0 else ("敌方" if 0x020006A0 <= src < 0x02000820 else "?")
    ctx.log(f"  [{pc:08X}] {tag} src=0x{src:08X} -> tile 0x{tile:03X}  src前8B={sig}")


@handler("HgAlt1")
@handler("HgAlt2")
@handler("HgMain")
def _on_hg_alt_which(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """三套平行实现入口：记录每次调用时的关键参数，判断谁在处理敌方。

    三个函数签名相同：sub_80451A0(u8 a, struct Pokemon *pkmn)
      r0 = a (healthbox sprite id)
      r1 = pkmn 指针
    我们关心的是 GetBattlerPosition 的结果，但入口处还没有，
    所以先记录调用次数 + pkmn 指针，用 pkmn 区分敌我。
    """
    pc = regs.get("r15", 0) & 0xFFFFFFFF
    a = regs.get("r0", 0) & 0xFFFFFFFF
    pkmn = regs.get("r1", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGALT", pc, a, pkmn)):
        return
    name = {0x080415A0: "Alt1", 0x08042408: "Alt2", 0x08042B14: "Main"}.get(pc, "?")
    ctx.log(f"  [{name}@{pc:08X}] a(r0)=0x{a:08X} pkmn(r1)=0x{pkmn:08X}")


@handler("HgDispatch")
def _on_hg_dispatch(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """UpdateHealthboxAttribute 分派器 @0x08042E70：r7 = 属性类型。

    pokeruby: HEALTHBOX_ALL=0, HEALTHBOX_NICK=4, HEALTHBOX_SMALL_STRING=9, ...
    最后调用的那次决定最终显示。
    """
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r7 = regs.get("r7", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGDISP", r6, r7)):
        return
    names = {0: "ALL", 1: "LEVEL", 2: "HP", 3: "MAX_HP", 4: "NICK",
             5: "STATUS", 6: "STATUS2", 7: "STATUS3", 9: "SMALL_STRING", 10: "?"}
    ctx.log(f"  [Disp] healthbox=0x{r6:08X} attr(r7)={r7}({names.get(r7,'?')})")


@handler("HgSeg2Entry")
def _on_hg_seg2(gdb: GdbClient, regs: dict, ctx: Ctx, cfg: dict[str, Any]) -> None:
    """hookB 跳转目标 @0x080425A8：证明 hookB 生效，并记录 r6/r8。"""
    r6 = regs.get("r6", 0) & 0xFFFFFFFF
    r8 = regs.get("r8", 0) & 0xFFFFFFFF
    if not ctx._hit(("HGSEG2", r6, r8)):
        return
    tag = "我方" if 0x02000520 <= r6 < 0x020006A0 else "敌方"
    ctx.log(f"  [Seg2] {tag} r6=0x{r6:08X} r8={r8}  (hookB 生效)")
