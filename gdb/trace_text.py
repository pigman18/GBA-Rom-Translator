#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_text.py — 追踪游戏正在打印的文本 + 文本所在地址。

连接 mGBA GDB stub（127.0.0.1:2345），断在 InitTextPrinter，逐条 dump：

  - 文本地址（r1 → TextPrinter+0x10 WIN_TEXT_PTR）与内存区域分类
    （ROM 0x08 / EWRAM 0x02 / IWRAM 0x03 / 其它）
  - 原始字节 hex + 两种解码：
      * 渲染字形（charmap.txt，F9 00 lead trail → 中文；含 \\n/\\CC 控制码）
      * JP 语义（jp_pcs.decode_pcs，日文原串可读）
  - 若地址在 ROM：报告文件偏移；若原盘同址仍是合法日文串，附原盘字节
  - 调用方 LR（谁触发的打印）

可选 --chars 模式断在 ProcessCurrentChar_RegularGlyph，逐字符追踪
（看 F9 中文短语跳转 / 实际消耗的字符）。默认只断 InitTextPrinter
（一次文本块一停，不易刷屏）。

用法：
  mGBA 打开 ROM，Tools → Start GDB stub（2345），Pause。
  python gdb/trace_text.py [--chars] [--match-texts] [--no-dedup]
  到想查的界面操作，Ctrl-C 结束，分析 gdb/text_trace.log。
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from util.gdb_patcher import GdbClient, GdbError
from meowth.jp_pcs import decode_pcs, BYTE_TO_CHAR as JP_SINGLE

HOST, PORT = "127.0.0.1", 2345
LOGDIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(LOGDIR, "text_trace.log")

REPO_ROOT = os.path.dirname(LOGDIR)
CHARMPATH = os.path.join(
    REPO_ROOT, "configs", "POKEMON_RUBY_AXVJ00", "charmap.txt"
)
ORIGIN_ROM = os.path.join(
    REPO_ROOT, "roms", "origin", "POKEMON_RUBY_AXVJ00.gba"
)
TEXTS_JSON = os.path.join(
    REPO_ROOT, "configs", "POKEMON_RUBY_AXVJ00", "translate", "texts_translated.json"
)

# AXVJ JP 权威地址（configs/POKEMON_RUBY_AXVJ00/hook/game_addrs.asm）
BP_INIT_TEXT = 0x08002C68  # InitTextPrinter(win, str, tile_base, cur_x)
BP_CHAR = 0x0800336E       # ProcessCurrentChar_RegularGlyph（r4=win, r3=char）

STR_MAX = 512


def u16(b, o):
    return b[o] | (b[o + 1] << 8)


def u32(b, o):
    return (
        b[o]
        | (b[o + 1] << 8)
        | (b[o + 2] << 16)
        | (b[o + 3] << 24)
    )


def load_charmap(path):
    """charmap.txt → (single, double)。single: byte→str；double: (lead<<8|trail)→str。"""
    single: dict[int, str] = {}
    double: dict[int, str] = {}
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"警告: 读 charmap 失败 {path}: {e}")
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
        if not ch:
            continue
        if v <= 0xFF:
            single[v] = ch
        else:
            double[v] = ch
    return single, double


def decode_text(data, single, double):
    """解码 FF 结尾文本：F9 00 lead trail → 中文；控制码 → \\n/\\l/\\CC/\\v。"""
    out = []
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
                code = (data[i + 1] << 8) | data[i + 2]
                out.append(f"{{F9→短语0x{code:04X}}}")
                break  # 短语内容在 phrase 流（WIN_TEXT_PTR 已重定向），本缓冲余下不打印
            out.append("<F9>")
            i += 1
            continue
        if b == 0xFE:
            out.append("\n"); i += 1; continue
        if b == 0xFA:
            out.append("\\l"); i += 1; continue
        if b == 0xFB:
            out.append("\n\n"); i += 1; continue
        if b == 0xFD and i + 1 < n:
            out.append(f"\\{data[i + 1]:02X}"); i += 2; continue
        if b == 0xFC and i + 1 < n:
            try:
                from meowth.pcs_codes import fc_arg_count
                end = i + 2 + fc_arg_count(data[i + 1])
                if end <= n:
                    out.append("\\CC" + "".join(f"{x:02X}" for x in data[i + 1:end]))
                    i = end
                    continue
            except Exception:
                pass
            out.append(f"[0x{b:02X}]"); i += 1; continue
        if b >= 0xFC:
            out.append(f"[0x{b:02X}]"); i += 1; continue
        if b in single:
            out.append(single[b])
        elif b in JP_SINGLE:
            out.append(JP_SINGLE[b])
        else:
            out.append(f"<{b:02X}>")
        i += 1
    return "".join(out)


def region_of(addr):
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


def _norm(s):
    """匹配用归一化：只留 CJK/假名/字母/数字/常用标点。"""
    s = re.sub(r"\\(?:l|p|n|pn|CC[0-9A-Fa-f]+|[0-9A-Fa-f]{2})", "", s)
    s = re.sub(r"[\s{}【】\[\]]", "", s)
    return "".join(re.findall(r"[\u3000-\u9fffA-Za-z0-9！？。，、：；（）]", s))


def load_texts():
    try:
        import json
        doc = json.load(open(TEXTS_JSON, encoding="utf-8"))
    except OSError as e:
        print(f"警告: 读 {TEXTS_JSON} 失败: {e}")
        return []
    if not isinstance(doc, list):
        return []
    return [e for e in doc if isinstance(e, dict) and e.get("original")]


def match_texts(decoded, entries):
    """在 texts_translated.json 里按归一化子串反查条目。返回 [(original, translated), ...]"""
    if not entries:
        return []
    d = _norm(decoded)
    if len(d) < 2:
        return []
    hits = []
    for e in entries:
        for field in ("original", "translated"):
            v = _norm(e.get(field) or "")
            if len(v) >= 2 and (d in v or v in d):
                hits.append((e.get("original"), e.get("translated")))
                break
        if len(hits) >= 4:
            break
    return hits


def log(msg):
    with open(LOG, "a", encoding="utf-8", errors="replace") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


class Tracer:
    def __init__(self, gdb, single, double, origin, texts, match, dedup):
        self.gdb = gdb
        self.single = single
        self.double = double
        self.origin = origin
        self.texts = texts if match else []
        self.dedup = dedup
        self._last = None
        self._skipped = 0

    def _hit(self, key):
        if not self.dedup:
            return True
        if key == self._last:
            self._skipped += 1
            return False
        if self._skipped:
            log(f"  …以上重复 {self._skipped} 次（--no-dedup 关闭去重）")
            self._skipped = 0
        self._last = key
        return True

    def dump_string(self, addr):
        try:
            data = self.gdb.read_mem(addr, STR_MAX)
        except GdbError as e:
            log(f"  读文本失败 @0x{addr:08X}: {e}")
            return None
        data = bytes(data)
        return data[: STR_MAX]

    def report(self, addr, label=""):
        region = region_of(addr)
        data = self.dump_string(addr)
        if data is None:
            return
        end = data.find(0xFF)
        body = data[: end + 1] if end >= 0 else data
        dec = decode_text(body, self.single, self.double)
        key = (addr, dec)
        if not self._hit(key):
            return

        hdr = f"\n[{label}] 文本地址: 0x{addr:08X} ({region})"
        if region == "ROM" and 0x08000000 <= addr:
            fo = addr - 0x08000000
            hdr += f"  文件偏移+0x{fo:X}"
        log(hdr)
        log(f"  原始字节: {body[:64].hex(' ')}")
        log(f"  渲染字形: {dec!r}")
        # JP 语义只在没有 F9 中文逃逸、疑似日文原串时展示
        if 0xF9 not in body and end >= 0:
            try:
                jp = decode_pcs(body)
                if jp.replace("\\l", "") != dec.replace("\\l", ""):
                    log(f"  JP 语义: {jp!r}")
            except Exception:
                pass

        # 原盘同址若仍是合法日文串 → 附原盘字节（指针重定向前的日文原文）
        if region == "ROM":
            fo = addr - 0x08000000
            if self.origin and 0 <= fo < len(self.origin):
                ob = self.origin[fo : fo + STR_MAX]
                end = ob.find(0xFF)
                body = ob[:end] if end >= 0 else ob
                if body and looks_jp(body) and bytes(body) != bytes(data)[: len(body)]:
                    log(
                        f"  原盘同址: {ob[: min(len(body) + 1, STR_MAX)].hex(' ')}"
                        f"  → {decode_pcs(ob[: min(len(body) + 1, STR_MAX)])!r}"
                    )

        if self.texts:
            hits = match_texts(dec, self.texts)
            for orig, tr in hits:
                log(f"  → texts_translated: {orig!r} / {tr!r}")

    def on_init_text(self, regs):
        win = regs.get("r0", 0)
        sp = regs.get("r1", 0)
        tb = regs.get("r2", 0) & 0xFFFF
        cx = regs.get("r3", 0) & 0xFF
        lr = regs.get("r14", 0) & ~1
        try:
            wb = self.gdb.read_mem(win, 0x20)
        except GdbError:
            wb = None
        meta = f"  win=0x{win:08X}"
        if wb and len(wb) >= 0x1E:
            meta += (
                f" textMode={wb[0x0A]} fontNum={wb[0x0B]}"
                f" TILE_BASE=0x{tb:04X} TILE_OFF=0x{u16(wb, 0x18):04X}"
                f" curX={cx} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
            )
        log(meta)
        log(f"  调用方 LR=0x{lr:08X}")
        self.report(sp, label="InitTextPrinter")

    def on_char(self, regs):
        win = regs.get("r4", 0)
        ch = regs.get("r3", 0) & 0xFF
        try:
            wb = self.gdb.read_mem(win, 0x20)
        except GdbError:
            return
        if len(wb) < 0x1E:
            return
        tptr = u32(wb, 0x10)
        index = u16(wb, 0x14)
        cur = (tptr + index - 1) & 0xFFFFFFFF
        ch_txt = decode_text(bytes([ch]), self.single, self.double)
        if not self._hit((win, cur, ch)):
            return
        log(
            f"\n[char] win=0x{win:08X} 字符=0x{ch:02X}({ch_txt!r})"
            f" 位置=0x{cur:08X}({region_of(cur)}) index={index}"
            f" textMode={wb[0x0A]} fontNum={wb[0x0B]}"
            f" curX={wb[0x1A]} curTX={wb[0x1B]} curY={wb[0x1C]} curTY={wb[0x1D]}"
        )


def looks_jp(body):
    try:
        from meowth.jp_pcs import looks_like_jp_text
        return looks_like_jp_text(bytes(body) + b"\xff")
    except Exception:
        return False


def main():
    import argparse

    ap = argparse.ArgumentParser(description="追踪游戏正在打印的文本与文本地址")
    ap.add_argument("--gdb", default=f"{HOST}:{PORT}")
    ap.add_argument("--chars", action="store_true", help="逐字符模式（ProcessCurrentChar）")
    ap.add_argument("--match-texts", action="store_true",
                    help="用 texts_translated.json 反查匹配条目")
    ap.add_argument("--no-dedup", action="store_true", help="关闭连续重复去重")
    ap.add_argument("--limit", type=int, default=3000)
    args = ap.parse_args()

    host, port = args.gdb.rsplit(":", 1)
    port = int(port)

    single, double = load_charmap(CHARMPATH)
    origin = None
    if os.path.isfile(ORIGIN_ROM):
        origin = open(ORIGIN_ROM, "rb").read()
    texts = load_texts() if args.match_texts else []
    if args.match_texts:
        print(f"已载入 texts_translated.json 条目数: {len(texts)}")

    with open(LOG, "a", encoding="utf-8", errors="replace") as f:
        f.write(f"\n===== 文本追踪 @ {time.strftime('%H:%M:%S')}"
                f"{' [逐字符]' if args.chars else ''} =====")

    gdb = GdbClient(host, port, timeout=5.0)
    for _ in range(200):
        try:
            gdb.close(); gdb.connect(); break
        except GdbError:
            gdb.close(); time.sleep(0.5)
    else:
        print("无法连接 mGBA GDB stub（先 mGBA 开 ROM + Start GDB stub + Pause）")
        return 2

    log(f"已连接，停因={gdb.cmd('?')}")
    bps = [("InitTextPrinter", BP_INIT_TEXT)] + ([("ProcessCurrentChar", BP_CHAR)] if args.chars else [])
    for name, addr in bps:
        try:
            gdb.set_sw_break(addr)
            log(f"  断点 {name} @0x{addr:08X} OK")
        except GdbError as e:
            log(f"  断点 {name} @0x{addr:08X} 失败: {e}")

    log("追踪中：到目标界面操作，Ctrl-C 结束。结果在 " + LOG)
    tracer = Tracer(gdb, single, double, origin, texts,
                    match=args.match_texts, dedup=not args.no_dedup)
    n = 0
    try:
        while n < args.limit:
            try:
                gdb.cont(timeout=600)
            except GdbError as e:
                log(f"\n[停止] {e}")
                break
            regs = gdb.read_regs()
            pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF
            n += 1
            if pc == BP_INIT_TEXT:
                tracer.on_init_text(regs)
            elif pc == BP_CHAR:
                tracer.on_char(regs)
            else:
                log(f"\n[{n}] 意外 PC=0x{pc:08X}")
    except KeyboardInterrupt:
        log("\n[用户中断]")
    finally:
        for _, addr in bps:
            try:
                gdb.clear_sw_break(addr)
            except GdbError:
                pass
        gdb.close()
    log(f"追踪结束，共 {n} 次命中。结果在 {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())