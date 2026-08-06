"""texts.json 合法性校验：多算法检测 + 综合评分。

每条目 ``check_score`` 0-100（100=干净），文件级 ``check_meta.score`` 为全部条目平均分。
命中非法算法的权重之和从 100 扣除，多个命中可叠加，下限 0。

用法（CLI）：``meowth check-texts <texts.json> --rom <rom.gba>``
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .jp_pcs import BYTE_TO_CHAR, looks_like_jp_text

BASE = 0x08000000

# 算法非法权重（命中一项从 score 扣除；权重越大越致命）
WEIGHTS: dict[str, int] = {
    "thumb_code": 40,    # capstone 反汇编：高比例字节为 Thumb 指令（代码/数据区）
    "jp_text": 30,       # original_hex 字节流不是合法 FF 结尾日文
    "garbage_jp": 30,    # original 字符串含半角假名/符号/乱序假名
    "arm_code": 30,      # original_hex 含 Thumb 指令字节组合
    "glyph_ratio": 25,   # 合法 charmap 字形占比过低 / 非法高位字节
    "kana_stats": 25,    # 假名 bigram / 连打 / 单调五十音行可疑
    "entropy": 20,       # Shannon 熵过低（填充）或过高（近随机）
    "byte_profile": 15,  # 0x00 填充比例过高（数据而非文本）
    "repeat": 15,        # 2 字节重复模式（像素/压缩数据特征）
    "terminator": 15,    # 不以 FF/FB/FE 结尾
    "length": 15,        # byte_length 越界
    "overlap": 10,       # 与相邻条目地址差 <=2（同一文本错位副本）
    "ptr_odd": 15,       # 指针源含奇数地址（Thumb 函数指针）
    "lz_span": 30,       # 地址处是完整 LZ77 压缩流（需 ROM）
    "orig_rom": 30,      # 原 ROM 该地址字节不是文本流（需 ROM）
    "tile_map": 40,      # Gen3 地图/图块头：10 00 ?? 00 08 00 + 三连同字节
    "mod_min_len": 40,   # 低于模块 min_byte_length（空则不校验）
    "mod_max_len": 40,   # 高于模块 max_byte_length（空则不校验）
}

_TERMINATORS = (0xFF, 0xFB, 0xFE)

# 代码/数据经 charmap 解码常产生的符号与半角假名（正常日文游戏文本几乎没有）
_HALFWIDTH_GARBAGE = re.compile(r"[\u2640-\u2650\uff61-\uff9f]")


def _garbage_jp(text: str) -> bool:
    """独立实现的乱码日文判定（不依赖 policy，避免影响 extract/build）。"""
    if not text:
        return False
    if "がのく" in text or "なくけ" in text or "にくけ" in text:
        return True
    if text.count("そ ") >= 2 and "ポケモン" not in text:
        return True
    if re.search(r"[A-Za-z][ぁ-んァ-ン]{1,3}[A-Za-z]", text):
        return True
    if len(re.findall(r"[ぁ-ん]{1}\s+[ぁ-ん]{1}\s+", text)) >= 3:
        return True
    if _HALFWIDTH_GARBAGE.search(text):
        return True
    return False


def _hex_bytes(entry: dict) -> bytes:
    oh = entry.get("original_hex") or ""
    try:
        return bytes.fromhex(oh.replace(" ", "").replace("\n", ""))
    except ValueError:
        return b""


def _entry_off(entry: dict) -> int | None:
    try:
        addr = int(entry.get("address", ""), 16)
    except (ValueError, TypeError):
        return None
    return addr - BASE if addr >= BASE else addr


def _body_bytes(bs: bytes) -> bytes:
    if bs and bs[-1] in _TERMINATORS:
        return bs[:-1]
    return bs


def _walk_pcs_glyphs(body: bytes) -> tuple[list[int], int, int]:
    """Walk PCS body; return (kana_bytes, glyph_count, bad_count)."""
    from .pcs_codes import fc_arg_count

    kana: list[int] = []
    glyph = 0
    bad = 0
    i = 0
    while i < len(body):
        b = body[i]
        if b in (0xFE, 0xFA, 0xFB):
            i += 1
            continue
        if b == 0xFD:
            if i + 1 >= len(body):
                bad += 1
                break
            i += 2
            continue
        if b == 0xFC:
            if i + 1 >= len(body):
                bad += 1
                break
            narg = fc_arg_count(body[i + 1])
            if i + 2 + narg > len(body):
                bad += 1
                break
            i += 2 + narg
            continue
        if b >= 0xF7 or b not in BYTE_TO_CHAR:
            bad += 1
            i += 1
            continue
        glyph += 1
        if 0x01 <= b <= 0xA0:
            kana.append(b)
        i += 1
    return kana, glyph, bad


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    counts = Counter(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _entropy(bs: bytes) -> bool:
    """Shannon 熵过低（填充/重复）或过高（近随机二进制）。"""
    body = _body_bytes(bs)
    if len(body) < 8:
        return False
    h = _shannon_entropy(body)
    return h < 1.8 or h > 6.8


def _glyph_ratio(bs: bytes) -> bool:
    """合法 charmap 字形占比过低，或非法高位字节过多。"""
    if not bs or len(bs) < 3:
        return False
    body = _body_bytes(bs)
    if len(body) < 2:
        return False
    _kana, glyph, bad = _walk_pcs_glyphs(body)
    total = glyph + bad
    if bad >= 2:
        return True
    if total > 0 and bad / total > 0.15:
        return True
    if len(body) >= 8 and glyph / len(body) < 0.35:
        return True
    return False


def _kana_stats(bs: bytes) -> bool:
    """假名连打 / 单调五十音行（表倾倒、乱码），不使用宽松 bigram 比率以免误杀对话。"""
    body = _body_bytes(bs)
    kana, _glyph, _bad = _walk_pcs_glyphs(body)
    if len(kana) < 4:
        return False

    # Same-byte runs (mojibake / padding decoded as kana)
    run = 1
    max_run = 1
    for i in range(1, len(kana)):
        if kana[i] == kana[i - 1]:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    if max_run >= 5:
        return True

    # Strict mono ascending/descending (IME gojuon / table dump)
    asc = desc = 1
    max_mono = 1
    for i in range(1, len(kana)):
        if kana[i] == kana[i - 1] + 1:
            asc += 1
            desc = 1
        elif kana[i] == kana[i - 1] - 1:
            desc += 1
            asc = 1
        else:
            asc = desc = 1
        max_mono = max(max_mono, asc, desc)
    if max_mono >= 6:
        return True

    return False


def _arm_code(bs: bytes) -> bool:
    """2 字节对齐扫描 Thumb 指令对，避免日文 2 字节字符的 trail 字节误判。"""
    if len(bs) < 8:
        return False
    n = 0
    i = 0
    while i + 1 < len(bs):
        b0, b1 = bs[i], bs[i + 1]
        if b0 in (0xB5, 0xB4, 0xBD, 0xBC, 0xB0) and (b1 & 0xF0) == 0:
            n += 1  # push/pop {reglist}
        elif b0 == 0x46 and b1 == 0x47:
            n += 1  # mov rX, rY; bx rY
        elif b0 in (0xD0, 0xD1) and b1 <= 0x7F:
            n += 1  # beq/bne 短分支
        i += 2
    return n >= 2


def _thumb_code(rom: bytes, off: int | None, length: int) -> bool:
    """capstone 反汇编：若高比例字节连续解出 Thumb 指令 → 代码/数据区。

    来自 capstone 反汇编引擎。长日文文本覆盖率也可能很高（Thumb 几乎
    任意 2 字节都是合法指令），因此只作辅助信号，不单独触发可疑。
    """
    if off is None or off >= len(rom):
        return False
    seg = rom[off : off + min(length or 48, 160)]
    if len(seg) < 16:
        return False
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

        md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        insns = list(md.disasm(seg, 0x08000000 + off))
    except Exception:
        return False
    if not insns:
        return False
    covered = sum(i.size for i in insns)
    return covered / len(seg) > 0.8 and len(insns) >= 8


def _repeat_pattern(bs: bytes) -> bool:
    """2 字节重复模式：像素/tile 数据常有 `xx yy xx yy` 周期重复，文本没有。"""
    if len(bs) < 8:
        return False
    pairs = [bs[i : i + 2] for i in range(0, len(bs) - 1, 2)]
    if not pairs:
        return False
    top = max(Counter(pairs).values())
    return top >= len(pairs) * 0.4


def _lz77_span(rom: bytes, off: int | None) -> bool:
    """完整 LZ77 解压校验（移植 pret/pokeemerald gbagfx lz.c）。

    标准 LZ77 或 lz77_swap（字节对交换，宝石版图像格式）。比简单
    ``_lz10_span`` 严格：完整解压到声明的 dest_size 才算命中，因此
    ``0x10`` 开头的日文文本不会误判。

    只在 ``off`` 起的有界窗口内尝试（默认 64KiB），避免对每条文本
    ``bytearray(rom[off:])`` 复制整盘 ROM。
    """
    if off is None or off >= len(rom):
        return False

    window = 0x10000  # 64 KiB is enough for any plausible text-adjacent LZ blob

    def try_decompress(data: bytes, start: int) -> bool:
        if start + 4 > len(data) or data[start] != 0x10:
            return False
        dest_size = data[start + 1] | (data[start + 2] << 8) | (data[start + 3] << 16)
        if dest_size < 0x40 or dest_size > 0x40000:
            return False
        sp = start + 4
        dp = 0
        while sp < len(data):
            flags = data[sp]
            sp += 1
            for _ in range(8):
                if flags & 0x80:
                    if sp + 1 >= len(data):
                        return False
                    block_size = (data[sp] >> 4) + 3
                    block_dist = (((data[sp] & 0xF) << 8) | data[sp + 1]) + 1
                    sp += 2
                    if dp - block_dist < 0:
                        return False
                    if dp + block_size > dest_size:
                        block_size = dest_size - dp
                    dp += block_size
                else:
                    if sp >= len(data):
                        return False
                    sp += 1
                    dp += 1
                if dp == dest_size:
                    return True
                flags <<= 1
        return False

    end = min(len(rom), off + window)
    segment = rom[off:end]
    if try_decompress(segment, 0):
        return True
    # lz77_swap：仅当交换后首字节可能是 0x10 时才复制窗口
    if len(segment) >= 2 and segment[1] == 0x10:
        swapped = bytearray(segment)
        for i in range(0, len(swapped) - 1, 2):
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        return try_decompress(bytes(swapped), 0)
    return False


def _byte_profile(bs: bytes) -> bool:
    """数据特征：0x00 填充比例过高（文本空格通常 <15%，数据 >30%）。"""
    if not bs:
        return False
    return bs.count(0x00) > len(bs) * 0.3


def _tile_map(bs: bytes) -> bool:
    """Gen3 地图/图块头误当文本。

    形态：``10 00 ?? 00 08 00`` + 三连同非零字节（如 ``55 55 55``）。
    对标地点名误扫体（如 axvj_63cbab191a67 / axvj_321095ddfc34）。
    """
    if len(bs) < 16:
        return False
    if not (
        bs[0] == 0x10
        and bs[1] == 0x00
        and bs[3] == 0x00
        and bs[4] == 0x08
        and bs[5] == 0x00
    ):
        return False
    return bs[6] == bs[7] == bs[8] and bs[6] != 0


def _parse_optional_bound(val) -> int | None:
    """模块 min/max_byte_length：缺省 / 空 / null → 不校验。"""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _mod_len_hits(
    entry: dict, module_meta: dict | None
) -> list[str]:
    """按模块 ``min_byte_length`` / ``max_byte_length`` 判定。"""
    if not module_meta:
        return []
    bl = entry.get("byte_length", 0) or 0
    hits: list[str] = []
    mn = _parse_optional_bound(module_meta.get("min_byte_length"))
    mx = _parse_optional_bound(module_meta.get("max_byte_length"))
    if mn is not None and bl < mn:
        hits.append("mod_min_len")
    if mx is not None and bl > mx:
        hits.append("mod_max_len")
    return hits


def _terminator(bs: bytes) -> bool:
    if not bs:
        return False
    return bs[-1] not in _TERMINATORS


def _length(entry: dict) -> bool:
    bl = entry.get("byte_length", 0) or 0
    return not (2 <= bl <= 512)


def _ptr_odd(entry: dict) -> bool:
    for p in (entry.get("pointer_sources") or []) + (entry.get("pointer_addresses") or []):
        try:
            if int(str(p), 16) & 1:
                return True
        except (ValueError, TypeError):
            continue
    return False


def _orig_rom_text(rom: bytes, off: int | None, length: int) -> bool:
    """原 ROM 地址处的字节是否像文本流（结尾 + 0x00 密度）。"""
    if off is None:
        return True
    if off >= len(rom):
        return True
    seg = rom[off : off + (length or 64)]
    if not seg:
        return True
    if seg[-1] not in _TERMINATORS:
        return False
    if seg.count(0x00) > len(seg) * 0.25:
        return False
    return True


def _authoritative(bs: bytes, rom: bytes | None, off: int | None, length: int) -> bool:
    """权威形态：结尾控制符 + 0x00 密度低。

    仅用于抑制易误报的代码类信号（thumb/arm/ptr_odd），不再直接给满分。
    """
    if bs:
        if bs[-1] not in _TERMINATORS:
            return False
        if bs.count(0x00) > len(bs) * 0.25:
            return False
    if rom is None:
        return True
    return _orig_rom_text(rom, off, length)


def _compute_overlap(entries: list[dict]) -> set[int]:
    """标记相邻 address 差 <=2 且原文高度相似的条目（同一文本错位副本）。

    紧凑文本表里相邻短段地址差也可能很小，因此必须同时满足
    ``original_hex`` 互为子串（错位副本 = 一个比另一个少几字节前缀）。
    """
    marked: set[int] = set()
    addrs: list[tuple[int, int]] = []
    for idx, e in enumerate(entries):
        try:
            addrs.append((int(e.get("address", ""), 16), idx))
        except (ValueError, TypeError):
            continue
    addrs.sort()
    for i in range(1, len(addrs)):
        delta = addrs[i][0] - addrs[i - 1][0]
        if delta > 2:
            continue
        ia, ib = addrs[i - 1][1], addrs[i][1]
        ha = (entries[ia].get("original_hex") or "").replace(" ", "")
        hb = (entries[ib].get("original_hex") or "").replace(" ", "")
        if not ha or not hb:
            continue
        # 同地址且全文相同 = extract 重复登记，不是错位副本
        if delta == 0 and ha == hb:
            continue
        if ha in hb or hb in ha:
            marked.add(ia)
            marked.add(ib)
    return marked


def score_entries(
    entries: list[dict],
    rom: bytes | None = None,
    *,
    game_id: str | None = None,
) -> list[tuple[dict, list[str], int]]:
    """对条目列表评分，返回 ``[(entry, hits, score)]``。

    纯计算、不改动 entry。``rom`` 为 None 时跳过需要 ROM 的算法
    （thumb_code / lz_span / orig_rom）。

    权威形态只抑制 thumb/arm/ptr_odd；质量类算法（jp_text / garbage /
    entropy / glyph_ratio / kana_stats …）始终计分。

    ``game_id`` 用于读取模块 ``min_byte_length`` / ``max_byte_length``。
    """
    modules_meta: dict = {}
    if game_id:
        from .config_loader import load_modules

        modules_meta = load_modules(game_id) or {}

    overlap_set = _compute_overlap(entries)
    scored: list[tuple[dict, list[str], int]] = []
    for i, e in enumerate(entries):
        # 固定表（物种名/招式名等 stride 表）是配置声明的正常数据，跳过校验。
        if e.get("is_fixed_table"):
            scored.append((e, [], 100))
            continue

        hits: list[str] = []
        bs = _hex_bytes(e)
        off = _entry_off(e)
        length = e.get("byte_length", 0)
        auth = _authoritative(bs, rom, off, length)
        mid = str(e.get("module") or "")
        mod_meta = modules_meta.get(mid) if mid else None

        # --- 质量层：始终计分 ---
        if bs and not looks_like_jp_text(bs):
            hits.append("jp_text")
        if rom is not None and not _orig_rom_text(rom, off, length):
            hits.append("orig_rom")
        if _garbage_jp(e.get("original") or ""):
            hits.append("garbage_jp")
        if _byte_profile(bs):
            hits.append("byte_profile")
        if _repeat_pattern(bs):
            hits.append("repeat")
        if _terminator(bs):
            hits.append("terminator")
        if _length(e):
            hits.append("length")
        hits.extend(_mod_len_hits(e, mod_meta))
        if i in overlap_set:
            hits.append("overlap")
        if rom is not None and _lz77_span(rom, off):
            hits.append("lz_span")
        if bs and _tile_map(bs):
            hits.append("tile_map")
        if bs and _entropy(bs):
            hits.append("entropy")
        if bs and _glyph_ratio(bs):
            hits.append("glyph_ratio")
        if bs and _kana_stats(bs):
            hits.append("kana_stats")

        # --- 代码类：仅权威形态异常时计分 ---
        if not auth:
            if rom is not None and _thumb_code(rom, off, length):
                hits.append("thumb_code")
            if _arm_code(bs):
                hits.append("arm_code")
            if _ptr_odd(e):
                hits.append("ptr_odd")

        score = max(0, 100 - sum(WEIGHTS[h] for h in hits))
        scored.append((e, hits, score))
    return scored


def check_texts(
    texts_path: Path,
    rom_path: Path,
    *,
    threshold: int = 0,
    dry_run: bool = True,
    modules: list[str] | None = None,
) -> dict:
    """校验 texts.json：按 rejects/allows 报告拒绝条目（不写文件）。

    - 校验 ``texts.json`` 的 game_id 与 ROM 一致
    - 拒绝条件：id ∈ rejects 且 id ∉ allows
    - ``threshold > 0`` 时附带诊断评分（不改变拒绝集合）
    """
    texts_path = Path(texts_path)
    data = json.loads(texts_path.read_text(encoding="utf-8"))
    entries: list[dict] = data.get("entries") or []

    from .game_backends import detect_game

    rom_gid = detect_game(rom_path)
    texts_gid = data.get("game_id") or data.get("game")
    if texts_gid != rom_gid:
        raise ValueError(
            f"game_id mismatch: texts={texts_gid!r}, rom={rom_gid!r}"
        )

    from .policy import allows_ids, rejects_ids

    allows = allows_ids(texts_gid)
    rejects = rejects_ids(texts_gid)

    candidates = entries
    active_modules = None
    if modules is not None:
        from .modules import filter_entries_by_modules, resolve_modules

        active_modules = resolve_modules(modules=modules, game_id=texts_gid)
        candidates = filter_entries_by_modules(
            entries, active_modules, game_id=texts_gid
        )

    score_by_id: dict[str, tuple[list, float]] = {}
    total_score = None
    if threshold > 0:
        rom = rom_path.read_bytes()
        scored = score_entries(candidates, rom, game_id=texts_gid)
        for e, h, s in scored:
            score_by_id[e.get("id") or ""] = (h, s)
        total_score = (
            round(sum(s for _, _, s in scored) / len(scored), 1) if scored else 100.0
        )

    rejected: list[tuple[dict, list, float | None]] = []
    for e in candidates:
        eid = e.get("id") or ""
        if eid in rejects and eid not in allows:
            hits, sc = score_by_id.get(eid, (["rejects"], None))
            if "rejects" not in hits:
                hits = ["rejects", *hits]
            rejected.append((e, list(hits), sc))

    return {
        "total_score": total_score,
        "threshold": threshold,
        "suspicious_count": len(rejected),
        "total_count": len(candidates),
        "entries_total": len(entries),
        "module_candidates": len(candidates),
        "suspicious": rejected,
        "suspicious_path": None,
        "rom_game_id": rom_gid,
        "dry_run": True,
        "disabled": False,
    }
