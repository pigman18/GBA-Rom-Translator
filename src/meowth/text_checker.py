"""texts.json 合法性校验：多算法检测 + 综合评分。

每条目 ``check_score`` 0-100（100=干净），文件级 ``check_meta.score`` 为全部条目平均分。
命中非法算法的权重之和从 100 扣除，多个命中可叠加，下限 0。

用法（CLI）：``meowth check-texts <texts.json> --rom <rom.gba>``
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .jp_pcs import looks_like_jp_text

BASE = 0x08000000

# 算法非法权重（命中一项从 score 扣除；权重越大越致命）
WEIGHTS: dict[str, int] = {
    "jp_text": 30,       # original_hex 字节流不是合法 FF 结尾日文
    "garbage_jp": 30,    # original 字符串含半角假名/符号/乱序假名
    "arm_code": 30,      # original_hex 含 Thumb 指令字节组合
    "byte_profile": 15,  # 0x00 / 控制字节比例过高（数据而非文本）
    "terminator": 15,    # 不以 FF/FB/FE 结尾
    "length": 15,        # byte_length 越界
    "overlap": 10,       # 与相邻条目地址差 <=2（同一文本错位副本）
    "ptr_odd": 15,       # 指针源含奇数地址（Thumb 函数指针）
    "lz_span": 30,       # 地址落在 LZ10 压缩区（需 ROM）
    "orig_rom": 30,      # 原 ROM 该地址字节不是文本流（需 ROM）
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


def _byte_profile(bs: bytes) -> bool:
    """数据特征：0x00 填充比例过高（文本空格通常 <15%，数据 >30%）。"""
    if not bs:
        return False
    return bs.count(0x00) > len(bs) * 0.3


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


def _authoritative(bs: bytes, rom: bytes, off: int | None, length: int) -> bool:
    """权威判定：字节流是正常文本（结尾控制符 + 0x00 密度低）。

    乱序假名垃圾（LZ/像素数据解码）0x00 密度高，正常日文文本空格
    占少数；短片假名文本（如 マユミのパソコン）0x00 低且以 FF 结尾。
    """
    if bs:
        if bs[-1] not in _TERMINATORS:
            return False
        if bs.count(0x00) > len(bs) * 0.25:
            return False
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
        if addrs[i][0] - addrs[i - 1][0] <= 2:
            ha = (entries[addrs[i - 1][1]].get("original_hex") or "").replace(" ", "")
            hb = (entries[addrs[i][1]].get("original_hex") or "").replace(" ", "")
            if ha and hb and (ha in hb or hb in ha):
                marked.add(addrs[i - 1][1])
                marked.add(addrs[i][1])
    return marked


def check_texts(
    texts_path: Path,
    rom_path: Path,
    *,
    threshold: int = 70,
    dry_run: bool = False,
) -> dict:
    """校验 texts.json 并写回评分。

    - 校验 ``texts.json`` 的 game_id 与 ROM 一致（不一致报错）
    - 每条目写 ``check_score``，顶层写 ``check_meta``
    - score < threshold 的条目写入同级的 ``texts_suspicious.json``
    - ``dry_run=True`` 只报告不写任何文件
    """
    texts_path = Path(texts_path)
    data = json.loads(texts_path.read_text(encoding="utf-8"))
    entries: list[dict] = data.get("entries") or []

    from .game_backends import detect_game

    rom_gid = detect_game(rom_path)
    texts_gid = data.get("game_id") or data.get("game")
    if texts_gid != rom_gid:
        raise ValueError(
            f"game_id mismatch: texts.json={texts_gid!r}, rom={rom_gid!r}"
        )

    rom = rom_path.read_bytes()
    from .extract import _lz10_span

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

        # 权威判定通过（结尾控制符 + 0x00 密度低）即视为正常文本。
        # 辅助算法对正常文本易误判（省略号 b0 b0、高字节 >=0x31、
        # 0x10 开头、ptr_odd 等），只在权威失败时计入加重。
        if _authoritative(bs, rom, off, length):
            scored.append((e, hits, 100))
            continue

        if bs and not looks_like_jp_text(bs):
            hits.append("jp_text")
        if not _orig_rom_text(rom, off, length):
            hits.append("orig_rom")
        if _garbage_jp(e.get("original") or ""):
            hits.append("garbage_jp")
        if _arm_code(bs):
            hits.append("arm_code")
        if _byte_profile(bs):
            hits.append("byte_profile")
        if _terminator(bs):
            hits.append("terminator")
        if _length(e):
            hits.append("length")
        if i in overlap_set:
            hits.append("overlap")
        if _ptr_odd(e):
            hits.append("ptr_odd")
        if off is not None and _lz10_span(rom, off) is not None:
            hits.append("lz_span")

        score = max(0, 100 - sum(WEIGHTS[h] for h in hits))
        scored.append((e, hits, score))

    for e, _hits, score in scored:
        e["check_score"] = score

    total_score = (
        round(sum(s for _, _, s in scored) / len(scored), 1) if scored else 100.0
    )
    suspicious = [(e, h, s) for e, h, s in scored if s < threshold]

    check_meta = {
        "score": total_score,
        "threshold": threshold,
        "suspicious_count": len(suspicious),
        "rom_game_id": rom_gid,
        "match": texts_gid == rom_gid,
        "algorithms": list(WEIGHTS.keys()),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    data["check_meta"] = check_meta

    susp_path = texts_path.parent / "texts_suspicious.json"
    if not dry_run:
        texts_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        susp_payload = dict(data)
        susp_payload["count"] = len(suspicious)
        susp_payload["entries"] = [
            dict(e, check_hits=h) for e, h, _s in suspicious
        ]
        susp_payload["check_meta"] = check_meta
        susp_path.write_text(
            json.dumps(susp_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return {
        "total_score": total_score,
        "threshold": threshold,
        "suspicious_count": len(suspicious),
        "total_count": len(scored),
        "suspicious": suspicious,
        "suspicious_path": susp_path,
        "rom_game_id": rom_gid,
        "dry_run": dry_run,
    }
