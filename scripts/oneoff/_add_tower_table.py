"""一次性：补全「对战塔训练家」表（0x39DF50, stride 64, name@2, count 60）。

实测依据（2026-11-11）：
  0x080A9DE6  lsls r2, r5, #6        ; idx*64
  0x080A9DF0  lsls r1, r1, #6        ; idx*64
  0x080A9DF2  adds r1, r1, r7        ; r7 = 0x0839DF50
  0x080A9DF8  bl   0x81B31A4         ; memcpy(dst, src, 64)
  literal @0xA9E30 = 0x0839DF50（被 0xA9D6C / 0xA9DD0 引用）

表内 60 条，texts.json 原有 44 条（挂错在「剧情」模块），缺 16 条短名
（ぽち/ココ/レオン 这类 2~3 字，被扫描器的长度判据跳过）。

本脚本：加模块定义 + 迁移 44 条 + 补 16 条 + 同步 texts_translated.json。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from meowth.jp_pcs import decode_pcs

GID = "POKEMON_RUBY_AXVJ00"
BASE = 0x39DF50
COUNT = 60
STRIDE = 64
NAME_OFF = 2
MODULE = "对战塔训练家"

TR = {
    "ぽち": "波奇",
    "ココ": "可可",
    "ズババ": "兹巴巴",
    "クララ": "库拉拉",
    "レオン": "雷恩",
    "ムドー": "穆德",
    "ドラー": "德拉",
    "バメコ": "巴梅子",
    "アゲハ": "扬羽",
    "バクー": "巴克",
    "キング": "金格",
    "コロロ": "科罗罗",
    "アール": "阿尔",
    "ワール": "瓦尔",
    "ネイ": "奈伊",
    "マイン": "玛茵",
}


def main() -> int:
    cfg = Path("configs") / GID / "translate"
    texts_path = cfg / "texts.json"
    tr_path = cfg / "texts_translated.json"
    rom = Path(f"roms/origin/{GID}.gba").read_bytes()

    t = json.loads(texts_path.read_text(encoding="utf-8"))
    t["modules"][MODULE] = {
        "label": "词条·对战塔训练家",
        "group": "词条",
        "default": True,
        "description": (
            "对战塔/训练家之眼个人名：基址 0x39DF50，entry=64，name@+2"
            "（前 2 字节是编号）。代码 lsls#6 索引后 memcpy 64B 到缓冲"
            "（0x080A9DF8）。名字后面还有第二个短名与队伍数据。"
        ),
        "start": f"0x{BASE:X}",
        "end": f"0x{BASE + COUNT * STRIDE - 1:X}",
        "type": "struct",
        "read": {"entry_size": STRIDE, "name_offset": NAME_OFF},
    }

    have = {int(e["address"], 16) for e in t["entries"] if e.get("address")}
    moved = 0
    added = 0
    for n in range(COUNT):
        a = BASE + n * STRIDE
        seg = rom[a:a + STRIDE]
        i = seg.find(b"\xff", NAME_OFF)
        if i < 0:
            continue
        name_off = a + NAME_OFF
        gba = 0x08000000 + name_off
        raw = seg[NAME_OFF:i + 1]
        orig = decode_pcs(raw)
        if not orig.strip():
            continue
        if gba in have:
            for e in t["entries"]:
                if e.get("address") and int(e["address"], 16) == gba:
                    if e.get("module") != MODULE:
                        e["module"] = MODULE
                        moved += 1
                    break
            continue
        eid = "axvj_" + hashlib.md5(
            f"{gba:08X}|{orig}".encode("utf-8")
        ).hexdigest()[:12]
        t["entries"].append({
            "id": eid,
            "module": MODULE,
            "address": f"0x{gba:08X}",
            "byte_length": len(raw),
            "original": orig,
            "original_hex": raw.hex(" "),
            "translated": TR.get(orig, ""),
            "is_pointer_based": False,
            "pointer_sources": [],
            "pointer_addresses": [],
        })
        added += 1

    t["count"] = len(t["entries"])
    texts_path.write_text(
        json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 翻译缓存同步
    cache = json.loads(tr_path.read_text(encoding="utf-8"))
    known = {x["original"] for x in cache}
    n_cache = 0
    for orig, zh in TR.items():
        if orig in known or not zh:
            continue
        cache.append({"status": 200, "original": orig, "translated": zh})
        n_cache += 1
    tr_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"模块 {MODULE}: 迁移 {moved} 条, 新增 {added} 条, count={t['count']}")
    print(f"texts_translated.json: 新增 {n_cache} 条, 总 {len(cache)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
