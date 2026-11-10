#!/usr/bin/env python3
"""texts_24: D 阶段 第3步 —— 删除「为全走 replace+slt2 妥协而加」的写入策略字段。

删除范围（Chief 已确认）：
  6 个模块的 write 块：
    宝可梦名 / 训练家名 / 训练家个人名 / 秘密基地装饰名 / 图鉴分类名 / 补漏剧情
  2 个模块的 reuse_slot_padding：
    秘密基地装饰名 / 图鉴分类名

保留（重要）：
  - type：stride / struct / stride_ptr / scan —— 几何类型，新流水线 classify_entry 要用
  - read：怎么从 ROM 读出文本（stride / entry_size / name_offset / eos / desc_ptr_offset）
  - filters / ranges / reader / fallback_filters —— 读侧语义
  - write 块里的 byte_length 也一并删（写死中文槽宽，属写入策略）

代码依赖（已由 Chief 核实）：
  - 新流水线 auto_layout.py / text_pipeline.py 完全不读 write.*
  - 旧引擎 translate_plan.py 的 _write_switch(default=True)、config_loader 会走默认值，
    行为变化是预期内的（旧引擎将被替代）

用法： python scripts/research/ruby/texts_24_strip_write.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[3]
TEXTS = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "translate" / "texts.json"

WRITE_MODULES = ["宝可梦名", "训练家名", "训练家个人名",
                 "秘密基地装饰名", "图鉴分类名", "补漏剧情",
                 "UI界面"]  # 全量扫描发现的第 7 个，同类妥协产物
PADDING_MODULES = ["秘密基地装饰名", "图鉴分类名"]

GRAPHIC_KEYS = {"write", "reuse_slot_padding"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    data = json.loads(TEXTS.read_text(encoding="utf-8"))
    mods = data["modules"]

    # 先列出全量清单：到底哪些模块带这些字段
    print("=" * 100)
    print("待删字段清单（全量扫描，不只看预定名单）")
    print("=" * 100)
    for name, m in mods.items():
        got = [k for k in GRAPHIC_KEYS if k in m]
        if got:
            detail = []
            if "write" in m:
                detail.append(f"write={json.dumps(m['write'], ensure_ascii=False)}")
            if "reuse_slot_padding" in m:
                detail.append(f"reuse_slot_padding={m['reuse_slot_padding']}")
            print(f"  {name:<16} {' '.join(detail)}")

    print()
    print("=" * 100)
    print("执行删除")
    print("=" * 100)
    removed = 0
    for name in WRITE_MODULES:
        m = mods.get(name)
        if not m:
            print(f"  ⚠️ 模块不存在: {name}")
            continue
        if "write" in m:
            print(f"  [{name}] -write {json.dumps(m['write'], ensure_ascii=False)}")
            del m["write"]
            removed += 1
    for name in PADDING_MODULES:
        m = mods.get(name)
        if m and "reuse_slot_padding" in m:
            print(f"  [{name}] -reuse_slot_padding={m['reuse_slot_padding']}")
            del m["reuse_slot_padding"]
            removed += 1

    # 校验：确认没有残留，且保留字段都在
    print()
    print("=" * 100)
    print("残留检查")
    print("=" * 100)
    left = [(n, k) for n, m in mods.items() for k in GRAPHIC_KEYS if k in m]
    print(f"  残留: {left if left else '无 ✅'}")

    print()
    print("保留字段抽查（type / read 必须在）")
    for name in ("宝可梦名", "训练家个人名", "秘密基地装饰名", "图鉴分类名", "补漏剧情"):
        m = mods[name]
        has_type = "type" in m
        has_read = "read" in m or m.get("type") == "scan"
        print(f"  {name:<16} type={m.get('type')!r:<12} read={'✅' if has_read else '❌'} "
              f"type字段={'✅' if has_type else '❌'}")

    print()
    if a.apply:
        TEXTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        print(f"[ok] 已写入，删除 {removed} 处字段")
    else:
        print(f"[dry-run] 将删除 {removed} 处字段；加 --apply 生效")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
