"""把「确定不是玩家可见文本」的条目从 texts.json 移到 dropped.json。

判据（只看 ROM 里解出来的实际串，不看译文）：

* ``A_u16data``  —— 解码后是「字 空格 字 空格」形态，即 ``xx 00 yy 00`` 的
  u16 数据表（坐标/属性表），扫描器把它当列对齐文本切了。
* ``B_debug``    —— 全角 ASCII 占比 ≥60%，且几乎不含假名（``ー`` 不算假名）。
  典型：``ＤＯＯＲＯーＸ１`` / ``ＭＡＣＨＩーＳ２`` / ``ＯＢＪテキストＡＤＤ``。
* ``C_question`` —— 只剩 ``？``/空白。

保留的一律不动，例如 ``ふつふつと わきあがる…フエン おんせん``（真宣传语，
只是列对齐空格多）、``わざマシン３２ １５００まい``、``１３５えん``、
``レベル１００``、``かち まけ ひきわけ``。

被删的条目**不丢**，全部写进 ``dropped.json``（含地址/原文/译文/原因），
随时可以捞回来。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from meowth.jp_pcs import decode_pcs  # noqa: E402

GID = "POKEMON_RUBY_AXVJ00"
CFG = Path("configs") / GID / "translate"
ROOT = Path(".")


def _kana_only(c: str) -> bool:
    o = ord(c)
    if 0x3041 <= o <= 0x3096:  # 平假名
        return True
    if 0x30A1 <= o <= 0x30FA:  # 片假名（排除 ー U+30FC / ・ U+30FB）
        return True
    return False


def _norm(addr: str) -> str:
    """``0x0839a63f`` / ``0X0839A63F`` 统一成 ``0x0839A63F``。"""
    v = int(str(addr), 16)
    return f"0x{v:08X}"


def classify(text: str, *, strict: bool = False) -> str | None:
    """``strict=True`` 用于 ``no_translation``：只认「结构表/调试串」这两类。

    为什么更保守：``no_translation`` 里的条目只是「还没翻」，不能因为长得不像
    对话就删。只归档两种**确定不是文本**的：

    * ``seq_ids``  —— 连续字形 id（``bb bc bd be …`` / ``ＡＢＣＤ…``），是
      名字输入界面的字符表，翻了会破坏输入。
    * ``B_debug``  —— 纯全角 ASCII 的调试串（``ＰＲＯＧＲＥＳＳ‥``）。
    """
    core = text.replace("\n", "")
    if not strict and not core.strip("？?　 "):
        return "C_question"
    if strict:
        b = [ord(c) for c in core]
        if len(b) >= 12:
            seq = sum(
                1 for i in range(len(b) - 1) if b[i + 1] == b[i] + 1 and 0xBB <= b[i] <= 0xF6
            )
            if seq * 100 >= len(b) * 80:
                return "seq_ids"
    if not strict:
        # A：xx 00 yy 00 —— 非空格字符之间全部隔一个空格（尾部空格要容忍）
        a = core.rstrip(" ")
        body = [c for c in a if c != " "]
        if len(body) >= 2 and len(a) == len(body) * 2 - 1:
            if all(a[i] == " " for i in range(1, len(a), 2)):
                return "A_u16data"
    fw = sum(1 for c in core if 0xFF01 <= ord(c) <= 0xFF5E)
    kana = sum(1 for c in core if _kana_only(c))
    # 只要含一点假名就放行：``１００００ぽ`` 这类「点数」是真 UI，
    # 调试串（ＭＥーＡＳＡ / ＰＣーＯＦＦ）的 ``ー`` 不算假名，不受影响。
    if fw and fw * 100 >= len(core) * 60 and kana * 100 < len(core) * 10:
        return "B_debug"
    return None


def main() -> int:
    apply = "--apply" in sys.argv
    rom = (ROOT / "roms" / "origin" / f"{GID}.gba").read_bytes()
    plan = json.loads(
        (ROOT / "work" / GID / "write.plan.json").read_text(encoding="utf-8")
    )
    build = json.loads(
        (ROOT / "work" / GID / "translate.build.json").read_text(encoding="utf-8")
    )
    by_id = {e["id"]: e for e in build["entries"] if e.get("id")}

    # 两种来源：
    #   bad_text_target —— 已判「目标不像文本」，用完整判据（A/B/C）
    #   no_translation  —— 只是「还没翻」，只用保守判据（结构表 / 调试串）
    targets: dict[str, tuple[str, str]] = {}
    for s in plan["skip"]:
        why = s.get("reason")
        if why not in ("bad_text_target", "no_translation"):
            continue
        e = by_id.get(s["id"]) or {}
        addr = e.get("address")
        if not addr:
            continue
        off = int(addr, 16)
        if off >= 0x08000000:
            off -= 0x08000000
        end = rom.find(0xFF, off, min(off + 600, len(rom)))
        txt = decode_pcs(rom[off : end + 1]) if end > off else ""
        if why == "no_translation":
            # 只动 0x3Axxxx 那片调试参数表（ＶＯＬＵＭＥ‥ / ＫＡＣＨＩ２２ 这类）
            # 与字符表。放宽到全 ROM 会误删「２Ｐｏｋ」这种联机提示。
            reason = classify(txt, strict=True) if 0x3A0000 <= off < 0x3C0000 else None
        else:
            reason = classify(txt)
        if reason:
            targets[_norm(addr)] = (e.get("original") or "", reason)

    texts_path = CFG / "texts.json"
    texts = json.loads(texts_path.read_text(encoding="utf-8"))
    keep, dropped = [], []
    for e in texts["entries"]:
        raw_addr = e.get("address") or ""
        addr = _norm(raw_addr) if raw_addr else ""
        hit = targets.get(addr)
        if hit and (e.get("original") or "") == hit[0]:
            dropped.append(
                {
                    "address": addr,
                    "module": e.get("module"),
                    "original": e.get("original"),
                    "translated": e.get("translated") or "",
                    "reason": hit[1],
                }
            )
            continue
        keep.append(e)

    from collections import Counter

    stat = Counter(d["reason"] for d in dropped)
    print(f"计划删除 {len(dropped)} 条：{dict(stat)}")
    print(f"texts.json 条目 {len(texts['entries'])} → {len(keep)}")
    if not apply:
        print("（dry-run，加 --apply 才写盘）")
        return 0

    out = CFG / "dropped.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"entries": []}
    seen = {(d["address"], d["original"]) for d in old["entries"]}
    for d in dropped:
        if (d["address"], d["original"]) not in seen:
            old["entries"].append(d)
    old["note"] = (
        "从 texts.json 移出的「非玩家可见文本」：调试串（ＤＯＯＲＯーＸ１ 这类）、"
        "u16 数据表被误切的 xx 00 yy 00、纯？占位。保留证据，可随时捞回。"
    )
    old["count"] = len(old["entries"])
    out.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    texts["entries"] = keep
    if "count" in texts:
        texts["count"] = len(keep)
    texts_path.write_text(
        json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已写 {out}（累计 {old['count']} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
