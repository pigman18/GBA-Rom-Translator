"""Runtime translation lookup cache (mode=2) — 生成 texts_translated.asm.

统一缓存 key 格式，三处共用同一定义（严禁各自为政）：
  - 生成方（engine translate/build 阶段）：texts_translated.json → 本文档产出 asm
  - 抓取方（util/gdb_patcher.py）：has_cache 判定 + append work/<game>/texts.txt
  - 运行时（hook C TextInitWindow）：ttl_cache_lookup 二分查表

Key 定义
--------
一个 key = 原文的**整条** PCS 字节流（含控制码 FD/FC/FB/FE 等，不以控制码切分）。
记录 = (u16 key_len, key[key_len], u16 val_len, val[val_len])，按 key 字节序排序；
key_len == 0 或 key 以 EOS(0xFF) 结尾均不允许（EOS 不入 key）。

value = 译文整块的 CHS 字节流（F9 00 lead/trail 汉字 + PCS 单字节符号 +
控制字节 + FF 结尾），即 hook 可整体重定向的 PhraseTable 风格流。

布局（TEXTCACHE_VMA=0x09F00000）
--------------------------------
  .org VMA          u32 count
  .org VMA+4        u32 offsets[count+1]（指向 TextCacheBody 内记录起点）
  TextCacheBody     记录体：u16 key_len, key, u16 val_len, val
"""
from __future__ import annotations

from typing import Callable, Iterable, Iterator, Sequence

from .pcs_codes import fc_arg_count

TEXTCACHE_VMA = 0x09F00000
RUN_CONTROL_MIN = 0xF7
EOS = 0xFF
RUN_MAX = 512

_HEX = frozenset("0123456789abcdefABCDEF")


def encode_pcs(text: str) -> bytes:
    """jp_pcs.decode_pcs 的逆：含转义串 -> 精确 PCS 字节（key/源块编码依据）。"""
    from .jp_pcs import CHAR_TO_BYTE

    raw = bytearray()
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch != "\\":
            if ch in CHAR_TO_BYTE:
                raw.append(CHAR_TO_BYTE[ch])
            else:
                raise ValueError(
                    f"无法编码原文字符 {ch!r} (U+{ord(ch):04X})"
                )
            i += 1
            continue

        # \n\n = 0xFB（段落/等待清屏）；须在 \n 之前匹配
        if text.startswith("\\n\\n", i):
            raw.append(0xFB)
            i += 4
            continue
        if text.startswith("\\n", i):
            raw.append(0xFE)
            i += 2
            continue
        if text.startswith("\\p", i):
            raw.append(0xFB)
            i += 2
            continue
        if text.startswith("\\l", i):
            raw.append(0xFA)
            i += 2
            continue
        if text.startswith("\\CC", i):
            j = i + 3
            if j + 1 >= n or text[j] not in _HEX or text[j + 1] not in _HEX:
                raise ValueError(f"\\CC 后缺 hex: {text[i:i + 12]!r}")
            cmd = int(text[j:j + 2], 16)
            byte_count = 1 + fc_arg_count(cmd)
            if j + byte_count * 2 > n:
                raise ValueError(f"\\CC 序列截断: {text[i:i + 16]!r}")
            raw.append(0xFC)
            for k in range(j, j + byte_count * 2, 2):
                if text[k] not in _HEX or text[k + 1] not in _HEX:
                    raise ValueError(f"\\CC 含非 hex: {text[i:i + 16]!r}")
                raw.append(int(text[k:k + 2], 16))
            i = j + byte_count * 2
            continue
        # \XX（FD 转义，2 位 hex）
        if i + 2 < n and text[i + 1] in _HEX and text[i + 2] in _HEX:
            raw.append(0xFD)
            raw.append(int(text[i + 1:i + 3], 16))
            i += 3
            continue
        raise ValueError(f"无法识别转义: {text[i:i + 8]!r}")
    return bytes(raw)


def split_runs(raw: bytes) -> list[bytes]:
    """PCS 块的**控制感知**可打印 runs（统一 key 拆分口径）。"""
    runs: list[bytes] = []
    i = 0
    n = len(raw)
    while i < n:
        b = raw[i]
        if b == EOS:
            break
        if b < RUN_CONTROL_MIN:
            start = i
            i += 1
            while i < n and raw[i] < RUN_CONTROL_MIN:
                i += 1
            runs.append(bytes(raw[start:i]))
            continue
        if b == 0xFC:
            if i + 1 < n:
                i += 2 + fc_arg_count(raw[i + 1])
            else:
                i += 1
            continue
        if b == 0xFD:
            i += 2
            continue
        i += 1
    return runs


def iter_cache_entries(
    cache_recs: Iterable[dict],
    encode_value: Callable[[str], bytes],
) -> Iterator[tuple[bytes, bytes]]:
    """texts_translated.json 记录 -> (key, value) 对（key 首见优先、去重）。

    key = 原文**整条** PCS 字节（含控制码，到 EOS 前），不再拆 run；
    value 已 FF 结尾（Charmap.encode 自带），此处再兜底一次。
    """
    seen: set[bytes] = set()
    for rec in cache_recs:
        try:
            status = int(rec.get("status") or 200)
        except (TypeError, ValueError):
            status = 200
        if status != 200:
            continue
        orig = rec.get("original") or ""
        tr = rec.get("translated") or ""
        if not orig or not tr or tr == orig:
            continue
        try:
            raw = encode_pcs(orig)
            if not raw:
                continue
        except (ValueError, KeyError):
            continue
        try:
            value = encode_value(tr)
        except (ValueError, KeyError):
            continue
        if not value:
            continue
        if value[-1] != EOS:
            value = value + bytes([EOS])
        if raw in seen:
            continue
        seen.add(raw)
        yield raw, value


def _u16(v: int) -> bytes:
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def render_texts_translated_asm(
    entries: Sequence[tuple[bytes, bytes]],
    table_vma: int = TEXTCACHE_VMA,
) -> str:
    """按 (key, value) 列表生成 armips asm（字典序排序 + 偏移表 + 记录体）。"""
    entries = sorted(entries, key=lambda kv: kv[0])
    lines: list[str] = [
        "; auto-generated by meowth.runtime_cache — do not edit",
        f".org 0x{table_vma:08X}",
        "TextCacheCount:",
        f"  .word {len(entries)}",
        ".align 4",
        "TextCacheOffsets:",
    ]
    body = bytearray()
    offsets: list[int] = []
    for key, value in entries:
        offsets.append(len(body))
        body += _u16(len(key))
        body += key
        body += _u16(len(value))
        body += value
    offsets.append(len(body))
    for off in offsets:
        lines.append(f"  .word {off}")
    lines.append(".align 4")
    lines.append("TextCacheBody:")
    for i in range(0, len(body), 16):
        chunk = body[i:i + 16]
        lines.append("  .byte " + ", ".join(f"0x{x:02X}" for x in chunk))
    lines.append("")
    return "\n".join(lines)


def write_texts_translated_asm(
    entries: Sequence[tuple[bytes, bytes]],
    out_path,
    table_vma: int = TEXTCACHE_VMA,
) -> Path:
    """写 texts_translated.asm 文件并返回路径。"""
    import os
    from pathlib import Path

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_texts_translated_asm(entries, table_vma=table_vma),
        encoding="utf-8",
        newline="\n",
    )
    return out_path