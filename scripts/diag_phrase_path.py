"""诊断：把 relocate 条目改走 F980 后的可行性。

对每条 relocate 的 target_hex（= 编码后正文，也就是将存入 PhraseTable 的流），
按 hook 侧 text_translater.c 的真实判定逻辑模拟走哪条路径：

  phrase_stream_no_wait_controls():
      流中出现 CHS_ESCAPE(F9) 且第二字节 != 0   → 有控制码 → 切流
      流中出现 0xFD(占位符)                      → 继续（不阻止内联）
      流中出现 >= 0xFA                           → 有控制码 → 切流
      流长 > 256                                 → 返回 0（不走内联）
      否则                                       → 内联快径

  inline_phrase_no_controls():
      绘制单元计数 n，n > 32 即 break → 后续单元被丢弃（丢字！）
      单元定义：F9 00 xx xx = 1 单元；0xFD nn = 1 单元；其他单字节 = 1 单元

  切流（redirect_phrase_stream）：无长度限制，安全。

输出：路径分布 / 丢字风险条目 / 512B 超限 / 槽位是否装得下 5 字节引用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CHS_ESCAPE = 0xF9
MAX_PHRASE_STREAM = 512
INLINE_MAX_UNITS = 32
NO_WAIT_MAX_LEN = 256


def classify(stream: bytes) -> tuple[str, int]:
    """返回 (路径, 绘制单元数)。路径: inline / stream / inline_truncated"""
    i = 0
    units = 0
    has_wait = False
    n = len(stream)

    # --- phrase_stream_no_wait_controls 的判定 ---
    while i < n and stream[i] != 0xFF:
        b = stream[i]
        if b == CHS_ESCAPE:
            if i + 1 < n and stream[i + 1] != 0:
                has_wait = True
                break
            i += 4
            if i > NO_WAIT_MAX_LEN:
                has_wait = True
                break
            continue
        if b == 0xFD:
            i += 2
            if i > NO_WAIT_MAX_LEN:
                has_wait = True
                break
            continue
        if b >= 0xFA:
            has_wait = True
            break
        i += 1

    if has_wait:
        return "stream", -1

    # --- 内联路径：数绘制单元 ---
    i = 0
    units = 0
    while i < n and stream[i] != 0xFF:
        b = stream[i]
        if b == CHS_ESCAPE and i + 1 < n and stream[i + 1] == 0:
            i += 4
        elif b == 0xFD:
            i += 2
        else:
            i += 1
        units += 1
        if units > INLINE_MAX_UNITS:
            return "inline_truncated", units
    return "inline", units


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"work\POKEMON_RUBY_AXVJ00\build\work\POKEMON_RUBY_AXVJ00\translate.build.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [e for e in (data.get("entries") or []) if e.get("type") == "relocate"]

    from collections import Counter

    paths: Counter[str] = Counter()
    per_module: dict[str, Counter[str]] = {}
    over512 = []
    truncated = []
    small_slot = []

    for e in entries:
        raw = bytes.fromhex((e.get("target_hex") or "").replace(" ", ""))
        # 去掉尾部 EOS
        body = raw[:-1] if raw and raw[-1] == 0xFF else raw
        p, units = classify(body)
        paths[p] += 1
        mod = e.get("module") or "?"
        per_module.setdefault(mod, Counter())[p] += 1
        if len(body) + 1 > MAX_PHRASE_STREAM:
            over512.append((e, len(body) + 1))
        if p == "inline_truncated":
            truncated.append((e, units, len(body)))
        slot = int(e.get("byte_length") or 0)
        if slot < 5:
            small_slot.append((e, slot))

    total = len(entries)
    print(f"源文件: {path}")
    print(f"relocate 条目总数: {total}\n")
    print("== 改走 F980 后的运行时路径分布 ==")
    for k in ("stream", "inline", "inline_truncated"):
        print(f"  {k:18s} {paths[k]:5d}  ({100 * paths[k] / total:5.1f}%)")

    print("\n== 按模块 ==")
    for mod, c in sorted(per_module.items(), key=lambda x: -sum(x[1].values())):
        print(f"  {mod:12s} 切流={c['stream']:4d}  内联={c['inline']:4d}  内联截断={c['inline_truncated']:4d}")

    print(f"\n== 超 {MAX_PHRASE_STREAM}B 单条上限（会被静默截断）: {len(over512)} 条 ==")
    for e, ln in sorted(over512, key=lambda x: -x[1])[:10]:
        print(f"  {ln:4d}B  {e.get('module')}  addr={e.get('address')}  slot={e.get('byte_length')}")

    print(f"\n== 内联截断风险（> {INLINE_MAX_UNITS} 绘制单元且无控制码，会丢字）: {len(truncated)} 条 ==")
    for e, u, ln in sorted(truncated, key=lambda x: -x[1])[:10]:
        print(f"  units={u:3d} len={ln:4d}B  {e.get('module')}  addr={e.get('address')}")

    print(f"\n== 槽位 < 5B（放不下 F980 引用）: {len(small_slot)} 条 ==")
    for e, s in small_slot[:10]:
        print(f"  slot={s}B  {e.get('module')}  addr={e.get('address')}")

    ok = paths["stream"] + paths["inline"]
    print(f"\n结论: {ok}/{total} ({100 * ok / total:.1f}%) 可安全改走 F980；"
          f"风险 {len(truncated) + len(over512) + len(small_slot)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
