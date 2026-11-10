#!/usr/bin/env python3
"""清点 texts.json 里所有 write.* 字段，为「自动划分」重设计做准备。

目标（用户 2026-11-04 指示）：
  texts.json 未来只存「模块 + 待翻译文本」
  组装（扩表/搬移/指针改写）由 Python 侧读 texts_translated.json 自动完成
  → write.* 这类「人工指定的写入策略」字段要全部退场

本脚本统计现有 write.* 字段及其取值，作为重设计的输入。

用法：
    python scripts/research/ruby/texts_write_fields.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"


def walk(obj, prefix="", out=None):
    """递归收集所有 write.* 键。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                walk(v, key, out)
            else:
                out.append((key, v))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{prefix}[{i}]", out)
    return out


def main() -> int:
    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = data.get("modules") or {}
    print(f"模块数: {len(mods)}\n")

    # 1. 所有 write.* 字段
    print("=== 所有 write.* 字段及取值分布 ===")
    write_keys: dict[str, Counter] = defaultdict(Counter)
    for mid, meta in mods.items():
        w = meta.get("write") or {}
        for k, v in w.items():
            write_keys[k][json.dumps(v, ensure_ascii=False)] += 1

    for k, vals in sorted(write_keys.items()):
        print(f"  write.{k}:")
        for v, c in vals.most_common():
            print(f"    {v}  × {c}")

    # 2. 其他「写入相关」字段
    print()
    print("=== 其他可能影响组装的字段 ===")
    other = Counter()
    for mid, meta in mods.items():
        for k in meta:
            if k in ("write", "filters", "read"):
                continue
            other[k] += 1
    for k, c in other.most_common():
        print(f"  {k}: 出现 {c} 次")

    # 3. 每模块完整 write 块
    print()
    print("=== 每模块的 write 块 ===")
    print(f"  {'模块':<20} {'type':<12} write.*")
    for mid, meta in mods.items():
        w = meta.get("write") or {}
        ws = json.dumps(w, ensure_ascii=False) if w else "(无)"
        print(f"  {mid:<20} {str(meta.get('type','?')):<12} {ws}")

    # 4. read 块（几何来源）
    print()
    print("=== 每模块的 read 块（几何）===")
    for mid, meta in mods.items():
        r = meta.get("read") or {}
        print(f"  {mid:<20} {json.dumps(r, ensure_ascii=False) if r else '(无)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
