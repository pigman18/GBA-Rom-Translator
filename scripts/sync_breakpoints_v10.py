"""把 POKEMON_RUBY_AXVJ00.yaml 里四个 hook 断点地址同步到 `hook/out/game.map` 的真值。

为什么改成「从 map 取地址」
---------------------------
初版把 (旧地址, 新地址) 硬编码在脚本里 —— 每重编一次就自己过期一次，而且
过期后**不会报错**，只会把断点写到错位置（gdb 埋点全错位，本轮已踩过）。
现在唯一的地址来源是 `configs/POKEMON_RUBY_AXVJ00/hook/out/game.map`
（arm-none-eabi-ld 产出，和 game.bin 同一次编译），脚本只做「读 map → 写 yaml」。

自证（脚本自带，逐项比对，任一项不符即 return 2）
------------------------------------------------
  1. map 里必须找到全部 4 个符号；
  2. 写回后重新解析 yaml，每一项地址必须 == map 值；
  3. 报告每项的变化（旧 → 新）。

用法
----
  python sync_breakpoints_v10.py            # 同步
  python sync_breakpoints_v10.py --check    # 只检查，不写盘
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(r"C:\code\GBA-Rom-Translator")
MAP = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook" / "out" / "game.map"
YAML = ROOT / "src" / "util" / "configs" / "POKEMON_RUBY_AXVJ00.yaml"

# yaml 断点名 -> game.map 里的符号名
SYMS = {
    "ChsPrint":     "chs_print",
    "PncHook":      "PrintNextChar_Hook",
    "V8Alloc":      "v8_alloc_tile",
    "V8AllocBegin": "v8_alloc_begin",
}

DATE_TAG = "2026-09-20"


def map_addrs():
    """从 game.map 抓 符号 -> 0x08XXXXXX。map 行形如
       '                0x08801068                v8_alloc_begin'"""
    txt = MAP.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(r"^\s+0x(08[0-9a-fA-F]{6})\s+(\S+)\s*$", txt, re.M):
        out.setdefault(m.group(2), int(m.group(1), 16))
    return out


def block_span(text, name):
    """返回 yaml 中 `- name: <name>` 块的 [start, end) 字符区间（到下一个 "- name:" 为止）。"""
    m = re.search(r"^- name: " + re.escape(name) + r"\s*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^- name: ", text[m.end():], re.M)
    return (m.start(), m.end() + (nxt.start() if nxt else len(text)))


def get_yaml_addr(text, name):
    span = block_span(text, name)
    if not span:
        return None
    blk = text[span[0]:span[1]]
    m = re.search(r"\n  address: '([^']+)'", blk)
    return int(m.group(1), 16) if m else None


def main():
    check = "--check" in sys.argv
    addrs = map_addrs()
    if not addrs:
        print("FAIL: game.map 未解析到任何符号（%s）" % MAP)
        return 2
    text = YAML.read_text(encoding="utf-8")
    orig = text
    print("源: %s" % MAP)
    print("目标: %s%s" % (YAML, "  [--check 只读]" if check else ""))

    missing = [n for n, s in SYMS.items() if s not in addrs]
    if missing:
        print("FAIL: map 缺符号 %s（先编译 hook: build_sh_equiv.sh）"
              % ", ".join(SYMS[n] for n in missing))
        return 2

    changes = []
    for name, sym in SYMS.items():
        new = addrs[sym]
        old = get_yaml_addr(text, name)
        if old is None:
            print("FAIL: yaml 找不到断点条目 %s" % name)
            return 2
        span = block_span(text, name)
        blk = text[span[0]:span[1]]
        new_hex = "0x%08x" % new
        blk2 = re.sub(r"address: '0x[0-9a-fA-F]+'", "address: '%s'" % new_hex, blk)
        # 描述里引用的同一个 hook 的旧地址（0x0880xxxx）一并改掉；ROM 侧地址
        # （0x0800xxxx）与其它 hook 的 0x0880xxxx 不动（描述里只出现本 hook 的号）。
        blk2 = re.sub(r"0x0880[0-9a-fA-F]{4}", new_hex, blk2)
        blk2 = blk2.replace("2026-09-20 v10 重编", DATE_TAG + " v10.1 重编")
        if blk2 != blk:
            text = text[:span[0]] + blk2 + text[span[1]:]
        changes.append((name, sym, old, new))

    print("-" * 68)
    for name, sym, old, new in changes:
        mark = "  " if old == new else ("同步" if old != new else "  ")
        print("  %-14s %-20s 0x%08x -> 0x%08x %s"
              % (name, sym, old, new, "" if old == new else "← 已更新"))

    if not check and text != orig:
        YAML.write_text(text, encoding="utf-8")

    # ---- 自证：逐项回读比对，任一项不符即失败（教训：不许比恒等量）----
    ok = True
    back = YAML.read_text(encoding="utf-8")
    for name, sym, _old, new in changes:
        got = get_yaml_addr(back, name)
        good = (got == new)
        ok = ok and good
        print("  [自证] %-14s yaml=0x%08x map=0x%08x %s"
              % (name, got if got is not None else -1, new,
                 "OK" if good else "FAIL"))
        if not good:
            return 2
    print("-" * 68)
    n_upd = sum(1 for a, _s, o, n in changes if o != n)
    print("结论: %s（%d/%d 项需更新）"
          % ("PASS" if ok else "FAIL", n_upd, len(changes)))
    if check and n_upd:
        print("提示: --check 未写盘；去掉 --check 即同步")
        return 1
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
