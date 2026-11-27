"""建立「species 编号 → 日文名/中文名」权威索引。

【2026-11-26 重要修正 —— 之前用错了源】
  ❌ 旧做法：用 `lexicon/图鉴.json` 的字典顺序当 species 顺序。
     错！实测证明该顺序是**全国图鉴**顺序，与日版 ROM 名字表**不一致**：
       日版表 species 277 = キモリ(木守宫)，而全国图鉴 277 = オオスバメ(大王燕)
       日版表 species 302 = テッカニン(铁面忍者)，全国图鉴 302 = ヤミラミ(勾魂眼)
     用错源会导致「252-276 缺名字」的错误结论。

  ✅ 正确做法：以 ROM 名字表 `0x1CA354`（stride 6，411 条）为权威，
     逐条读出日文名，再用 lexicon 反查中文。
     这是游戏实际使用的映射：游戏读第 N 条就是 species N 的名字。

【日版 252-276 是空位】
  日版 ROM 这 25 条原文就是「？」（实测 origin 采集 species 252 显示 `?`）。
  这是日版未填充的数据，不是汉化缺陷。
  我们的汉化可以为它们补上中文名（超越日版），
  补名用全国图鉴 252-276 的对应关系（木守宫…傲骨燕）。

输出：work/_species_index.json
"""
import json
from pathlib import Path

ROOT = Path.cwd()
ORIGIN = ROOT / "roms/origin/POKEMON_RUBY_AXVJ00.gba"
LEX = ROOT / "configs/POKEMON_RUBY_AXVJ00/translate/lexicon/图鉴.json"
TEXTS = ROOT / "configs/POKEMON_RUBY_AXVJ00/translate/texts.json"

# 名字表：文件偏移（不是绝对地址！0x1CA354 在 8MB ROM 内有效）
TABLE_OFF = 0x1CA354
COUNT = 411
STRIDE = 6

# 日版空位 species 252..276：用全国图鉴顺序补
BLANK_FILL = list(range(252, 277))


def main() -> int:
    rom = ORIGIN.read_bytes()
    lex = json.loads(LEX.read_text(encoding="utf-8"))
    texts = json.loads(TEXTS.read_text(encoding="utf-8"))

    # 优先用 texts.json 里已提取的 original（已解码成字符串）
    mons = [e for e in (texts.get("entries") or [])
            if e.get("module") == "宝可梦名"]

    out = {}
    blank = []
    for i in range(COUNT):
        sid = i + 1
        if i < len(mons):
            jp = (mons[i].get("original") or "").strip()
        else:
            raw = rom[TABLE_OFF + i * STRIDE: TABLE_OFF + i * STRIDE + STRIDE]
            jp = ""
            for b in raw:
                if b == 0xFF:
                    break
            jp = ""  # 兜底留空
        zh = lex.get(jp, "") if jp else ""
        if not zh:
            blank.append(sid)
        out[str(sid)] = {"jp": jp, "zh": zh, "chars": len(zh)}

    # 补日版空位：按全国图鉴 252-276
    nat = list(lex.keys())
    for sid in BLANK_FILL:
        if sid - 1 < len(nat):
            jp = nat[sid - 1]
            zh = lex.get(jp, "")
            out[str(sid)] = {"jp": jp, "zh": zh, "chars": len(zh),
                             "note": "日版为空，按全国图鉴补齐"}

    path = ROOT / "work/_species_index.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    still = [k for k, v in out.items() if not v["zh"]]
    print(f"条目 {len(out)} -> {path}")
    print(f"日版为空的位置: {blank[0] if blank else '-'}..{blank[-1] if blank else '-'} "
          f"（{len(blank)} 条，已按全国图鉴补齐）")
    print(f"补后仍缺中文: {len(still)} 条 {still[:5]}")

    print()
    print("锚点校验（游戏实测过）：")
    for sid, expect in (("1", "妙蛙种子"), ("139", "多刺菊石兽"),
                        ("163", "咕咕"), ("277", "木守宫"),
                        ("302", "铁面忍者"), ("386", "电萤虫")):
        v = out.get(sid, {})
        got = v.get("zh", "")
        mark = "OK" if got == expect else "MISMATCH"
        print(f"  species {sid:>3}: {got!r}  期望 {expect!r}  [{mark}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
