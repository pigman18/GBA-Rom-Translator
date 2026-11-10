"""Japanese Generation III PCS (AXVJ) decode/encode helpers.

Table from Bulbapedia Character encoding (Generation III) — Japanese set.
0x00 = space; 0xFA–0xFF are controls on JP Ruby (not glyphs).
"""
from __future__ import annotations

import hashlib


def make_entry_id(address_hex: str, original_hex: str) -> str:
    """条目 id：``axvj_`` + md5(address + original_hex) 前 12 位 hex。

    address+hex 保证同文本唯一（同一地址不同字节也区分）。
    """
    raw = f"{address_hex}{original_hex.replace(' ', '').replace('\n', '')}"
    return "axvj_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# Bytes 0x01–0xF6 as a contiguous unicode string (index = codepoint - 1 for 0x01..)
# Built row-wise from the JP table (skipping 0x00 which is space).
_JP_01_TO_F6 = (
    # 0x01-0x0F
    "あいうえおかきくけこさしすせそ"
    # 0x10-0x1F
    "たちつてとなにぬねのはひふへほま"
    # 0x20-0x2F
    "みむめもやゆよらりるれろわをんぁ"
    # 0x30-0x3F
    "ぃぅぇぉゃゅょがぎぐげござじずぜ"
    # 0x40-0x4F
    "ぞだぢづでどばびぶべぼぱぴぷぺぽ"
    # 0x50-0x5F
    "っアイウエオカキクケコサシスセソ"
    # 0x60-0x6F
    "タチツテトナニヌネノハヒフヘホマ"
    # 0x70-0x7F
    "ミムメモヤユヨラリルレロワヲンァ"
    # 0x80-0x8F
    "ィゥェォャュョガギグゲゴザジズゼ"
    # 0x90-0x9F
    "ゾダヂヅデドバビブベボパピプペポ"
    # 0xA0-0xAF
    "ッ０１２３４５６７８９！？。ー・"
    # 0xB0-0xBF
    "‥『』「」♂♀円．×／ＡＢＣＤＥ"
    # 0xC0-0xCF
    "ＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵ"
    # 0xD0-0xDF
    "ＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋ"
    # 0xE0-0xEF
    "ｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ►"
    # 0xF0-0xF6
    "：ÄÖÜäöü"
)

assert len(_JP_01_TO_F6) == 0xF6, len(_JP_01_TO_F6)

BYTE_TO_CHAR: dict[int, str] = {0x00: " "}
for i, ch in enumerate(_JP_01_TO_F6, start=1):
    BYTE_TO_CHAR[i] = ch

CHAR_TO_BYTE: dict[str, int] = {ch: b for b, ch in BYTE_TO_CHAR.items() if ch != " "}
CHAR_TO_BYTE[" "] = 0x00
CHAR_TO_BYTE["　"] = 0x00

# JP Ruby control presentation in extracted text
_CTRL = {
    0xFA: "\\l",   # often used like prompt variants — keep opaque
    0xFB: "\\p",   # paragraph / wait
    0xFC: "\\FC",  # extended (rare on JP RS as western FC)
    0xFD: "\\v",   # variable
    0xFE: "\\n",   # newline
    0xFF: "",
}


def decode_pcs(data: bytes) -> str:
    """Decode FF-terminated (or raw) JP PCS to a readable string with \\n/\\l."""
    out: list[str] = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0xFF:
            break
        if b == 0xFE:
            out.append("\n")
            i += 1
            continue
        # AXVJ: 0xFA = ▼ continue prompt (US LINE_SCROLL). Round-trip via \\l.
        if b == 0xFA:
            out.append("\\l")
            i += 1
            continue
        if b == 0xFB:
            out.append("\n\n")
            i += 1
            continue
        if b == 0xFD and i + 1 < len(data):
            out.append(f"\\{data[i+1]:02X}")
            i += 2
            continue
        if b == 0xFC and i + 1 < len(data):
            from .pcs_codes import fc_arg_count

            cmd = data[i + 1]
            narg = fc_arg_count(cmd)
            end = i + 2 + narg
            if end > len(data):
                out.append(f"[0x{b:02X}]")
                i += 1
                continue
            out.append("\\CC" + "".join(f"{x:02X}" for x in data[i + 1 : end]))
            i = end
            continue
        if b >= 0xFC:
            out.append(f"[0x{b:02X}]")
            i += 1
            continue
        out.append(BYTE_TO_CHAR.get(b, f"<{b:02X}>"))
        i += 1
    return "".join(out)


def is_printable_pcs(s: bytes) -> bool:
    """整串字节是否全部是「可印 PCS」——不含 >0xF6 的字形码、不含未定义码位。

    与 :func:`looks_like_jp_text` 的区别：**不判语种比例**。
    ⚠️ **不要拿来当文本准入判据**（2026-11-10 实测）：它太松 ——
    ``BYTE_TO_CHAR`` 覆盖 0x00–0xF6，随机数据/结构体字节几乎全能过。
    只用它当「这条串能不能整串按 PCS 解释」的技术性检查；
    判断「是不是真文本」仍必须走 :func:`looks_like_jp_text`。

    曾被误用于放行「全角数字扎堆」的正文（``わざマシン３２  １５００まい``），
    结果把那批里的 112 条 ``xx 00`` 结构体数据也放了进来，
    指针被改到新址后战斗场景直接卡死。已回滚。
    """
    from .pcs_codes import fc_arg_count

    n = len(s) - 1 if s.endswith(bytes([0xFF])) else len(s)
    i = 0
    while i < n:
        b = s[i]
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            continue
        if b == 0xFD:
            i += 2
            continue
        if b == 0xFC:
            if i + 1 >= n:
                return False
            i += 2 + fc_arg_count(s[i + 1])
            continue
        if b >= 0xF7:
            return False
        if b not in BYTE_TO_CHAR:
            return False
        i += 1
    return True


def looks_like_jp_text(s: bytes, *, allow_space_pad: bool = False) -> bool:
    """True if ``s`` is a plausible FF-terminated JP dialogue/UI string.

    Strict enough to reject Thumb/code blobs that decode to mojibake kana.
    Allows mid-string 0xFA (▼ prompt) used by real AXVJ multi-box dialogue.

    ``allow_space_pad``：训练卡背面等列对齐标签池用 0x00 作栏间垫片
    （如「かち······まけ」），旧 00 密度规则会误杀；由模块
    ``write.space_pad`` 打开，仍靠后面 kana 比例 + ``is_struct_like_pcs`` 挡窗模板。
    """
    if not s or s[-1] != 0xFF:
        return False
    body = s[:-1]
    if not (2 <= len(body) <= 512):
        return False
    # 首尾 0x00 是空格/垫片（指针常落在正文前的 00 上）；只看内部 00 密度。
    if not allow_space_pad:
        interior = body.strip(b"\x00")
        if interior.count(0) > max(2, len(interior) // 3 if interior else 0):
            return False

    # Walk body; allow FE/FA/FB and FD xx / FC xx… as controls only.
    # 尾部完整 FC（如 おぼえられない！\\CC09 FF）与句中 FC 同样放行。
    i = 0
    glyph = 0
    kanaish = 0
    hiragana = 0
    katakana = 0
    latinish = 0
    neutral = 0  # space / JP punctuation — not counted against kana ratio
    while i < len(body):
        b = body[i]
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            continue
        if b == 0xFD:
            if i + 1 >= len(body):
                return False
            i += 2
            continue
        if b == 0xFC:
            from .pcs_codes import fc_arg_count

            if i + 1 >= len(body):
                return False
            narg = fc_arg_count(body[i + 1])
            if i + 2 + narg > len(body):
                return False
            i += 2 + narg
            continue
        if b >= 0xF7:
            return False
        if b not in BYTE_TO_CHAR:
            return False
        glyph += 1
        if b == 0x00 or 0xAB <= b <= 0xBA:
            # space, ！？。ー・‥『』「」♂♀ etc.
            neutral += 1
        elif 0x01 <= b <= 0x50:
            hiragana += 1
            kanaish += 1
        elif 0x51 <= b <= 0xA0:
            katakana += 1
            kanaish += 1
        elif 0xBB <= b <= 0xF6:
            latinish += 1
        i += 1

    if glyph < 2:
        return False
    if latinish > max(1, glyph // 8):
        return False
    # Punctuation/spaces are common in dialogue — exclude them from the ratio.
    effective = max(1, glyph - neutral)
    # Long bodies: hiragana dialogue OR katakana-heavy UI (menus / move names).
    if glyph >= 8 and hiragana < 2 and katakana < (effective + 1) // 2:
        return False
    return kanaish >= max(2, (effective * 2) // 3)
