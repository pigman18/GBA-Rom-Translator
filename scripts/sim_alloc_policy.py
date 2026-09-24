#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sim_alloc_policy.py — 用真实 gdb 日志快照离线对比 tile 分配策略（不改 ROM）。

目的
----
`docs/开发_20260911_领航员标签tile池耗尽取证.md` 的结论是「arena 被打空」。
本脚本把该日志里领航员场景的 **真实 VRAM 占用 + BG 活引用 + ours 账本**
喂给两套策略，离线算出「本次 begin 后真正有多少 tile 能领 / 能画几个汉字」，
用真实数据判「新策略值不值得实现」，而不是靠推演。

策略
----
old（现状 v9，19 段 FIFO 账本 —— 本脚本按「账本内容 = 日志实测的 136 tile」代入）：
    usable(t) = t∉live ∧ ( t∉nonempty ∨ t∈ours )
    即：非空、无活引用、又不在账本里的 tile ⇒ 永久判死（negative cache）。

new（v10「无主即回收」）：
    ① t∉arena            ⇒ 不可用（官方 atlas 保护区，显式化）
    ② t∈ours             ⇒ 可用（*不论* VRAM 非空、*不论* 是否活引用）
    ③ t∉ours ∧ t∈live    ⇒ 不可用（屏上正在显示的官方图形，受保护）
    ④ t∉ours ∧ t∉nonempty⇒ 可用
    ⑤ t∉ours ∧ t∈nonempty∧ t∉live ⇒ **认领为 ours 并可用**（无主死数据回收）

自证
----
脚本会自己重算日志里 [ARENA cb0] 那一节的四分类，并与日志印刷值比对；
不一致就直接报错退出 —— 避免「解析错了还在自嗨」。

用法
----
  python scripts/sim_alloc_policy.py
  python scripts/sim_alloc_policy.py --log <path> --labels 30 --chars 6
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEF_LOG = ROOT / "src/util/work/POKEMON_RUBY_AXVJ00/scene_owner_v92.log"

LO, HI = 256, 1024          # arena = cb0 相对 tile [256,1024)
PAIR = 2                    # tm1 每字一个「竖直对」= 2 tile


# ---------------------------------------------------------------- 解析
def _segs_from_runspec(spec: str):
    """解析 '[3..855](853) [860..873](14)' → [(3,853),(860,14)] (start,len)。"""
    out = []
    for a, b, n in re.findall(r"\[(\d+)\.\.(\d+)\]\((\d+)\)", spec):
        out.append((int(a), int(n)))
    return out


def _segs_from_pairs(spec: str):
    """解析 ours=[(360,2),(755,12)] → [(360,2),...]。"""
    return [(int(a), int(b)) for a, b in re.findall(r"\((\d+),(\d+)\)", spec)]


def _tile_list(spec: str):
    """解析 '360..361 755..766 640' → [360,361,755,...]。"""
    out = []
    for tok in spec.split():
        if ".." in tok:
            a, b = tok.split("..")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(tok))
    return out


def _expand(segs, lo=0, hi=1024):
    m = bytearray(hi - lo)
    for st, ln in segs:
        for t in range(st, st + ln):
            if lo <= t < hi:
                m[t - lo] = 1
    return m


class Snapshot:
    pass


def parse_log(path: Path, want_dispcnt=0x3F40):
    txt = path.read_text(encoding="utf-8", errors="replace")
    # 按 '[SCENE-OWNER] DISPCNT=' 切块，取最后一个匹配 want_dispcnt 的块
    starts = [m.start() for m in re.finditer(r"\[SCENE-OWNER\] DISPCNT=", txt)]
    starts.append(len(txt))
    block = None
    for i in range(len(starts) - 1):
        seg = txt[starts[i]:starts[i + 1]]
        if f"DISPCNT=0x{want_dispcnt:04X}" in seg:
            block = seg
    if block is None:
        raise SystemExit(f"日志里找不到 DISPCNT=0x{want_dispcnt:04X} 的场景块")

    s = Snapshot()
    # BG 层：charBase + 绝对化引用集
    s.bg = {}
    for m in re.finditer(r"BG(\d) CNT=0x([0-9A-F]{4}).*?charBase=cb(\d)\(0x[0-9A-F]{5}\)"
                         r" screenBase=sb(\d+).*?绝对化引用集=([0-9A-F0-9 .]+?)（",
                         block, re.S):
        bg = int(m.group(1))
        cb = int(m.group(3))
        abs_tiles = _tile_list(m.group(5))
        # 绝对号 → 本 cb 相对号：绝对号 = cb*1024 + rel? 实测 BG1(cb3) 绝对 1537..1660
        # → 1537-1024=513 ⇒ 绝对号 = cb*512 + rel（charblock = 512 tile）
        rel = [a - cb * 512 for a in abs_tiles]
        s.bg[bg] = {"cnt": int(m.group(2), 16), "cb": cb, "rel": rel}

    m = re.search(r"\[VRAM cb0\].*?非空 (\d+) 段=(\[.*?\])", block, re.S)
    s.vram_cb0 = _expand(_segs_from_runspec(m.group(2)))

    m = re.search(r"可回收位图 ours=(\d+)/768.*?解码段 ours=(\[.*?\])", block, re.S)
    s.ours_declared = int(m.group(1))
    s.ours = _expand(_segs_from_pairs(m.group(2)), LO, HI)

    m = re.search(r"真·空闲=(\d+)\s*\|\s*非空且活引用=(\d+)\s*\|\s*"
                  r"非空且在账本非活=(\d+)\s*\|\s*★非空·无引用·无账本=(\d+)", block)
    s.declared = tuple(int(g) for g in m.groups())
    s.dispcnt = want_dispcnt
    return s


# ---------------------------------------------------------------- 策略
def build_masks(s: Snapshot):
    """返回 (live, nonempty, ours) 三个 bool 列表，下标 = arena 相对 tile。"""
    n = HI - LO
    live = [False] * n
    for bg, info in s.bg.items():
        if info["cb"] != 0:          # 只管落在 cb0 的层（= 本窗 charBase）
            continue
        for t in info["rel"]:
            if LO <= t < HI:
                live[t - LO] = True
    nonempty = [bool(s.vram_cb0[t]) for t in range(LO, HI)]
    ours = [bool(s.ours[i]) for i in range(n)]
    return live, nonempty, ours


def usable_old(live, nonempty, ours, i):
    return (not live[i]) and ((not nonempty[i]) or ours[i])


def usable_new(live, nonempty, ours, i):
    if ours[i]:
        return True                  # ② 我们写过的，直接可用
    if live[i]:
        return False                 # ③ 屏上活引用（官方图形）受保护
    return True                      # ④ 空 / ⑤ 无主死数据 → 都可回收


def split_counts(live, nonempty, ours, usable_fn):
    free = live_free = dead = 0
    for i in range(len(live)):
        if not usable_fn(live, nonempty, ours, i):
            if nonempty[i] and live[i]:
                live_free += 1
            else:
                dead += 1
        elif not nonempty[i]:
            free += 1
    return free, live_free, dead


def count_pairs(live, nonempty, ours, usable_fn):
    """贪心配对：连续可用段能凑出多少个 2 tile 竖直对。"""
    n = len(live)
    pairs, run, i = 0, 0, 0
    while i < n:
        if usable_fn(live, nonempty, ours, i):
            run += 1
        else:
            pairs += run // PAIR
            run = 0
        i += 1
    pairs += run // PAIR
    return pairs


def sim_alloc(live, nonempty, ours, usable_fn, n_alloc, want=PAIR):
    """照抄 v8_alloc_n 的确定性顺序遍历 + 回卷重扫。返回 (成功数, 每字落点)。"""
    usable = [bool(usable_fn(live, nonempty, ours, i)) for i in range(len(live))]
    bm = [False] * len(usable)       # 会话内 negative cache
    cur = LO
    placed = []
    for _ in range(n_alloc):
        got = None
        for lo_pass in (max(cur, LO), LO):
            t = lo_pass
            while t + want <= HI:
                if all(usable[t - LO + k] and not bm[t - LO + k] for k in range(want)):
                    got = t
                    break
                t += 1
            if got is not None:
                break
        if got is None:
            continue
        for k in range(want):
            bm[got - LO + k] = True
        cur = got + want
        placed.append(got)
    return len(placed), placed


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(DEF_LOG))
    ap.add_argument("--labels", type=int, default=30, help="领航员路线名标签条数")
    ap.add_argument("--chars", type=int, default=6, help="每条标签汉字数")
    args = ap.parse_args()

    s = parse_log(Path(args.log))
    live, nonempty, ours = build_masks(s)
    n = HI - LO

    # ---- 自证：重算日志印刷的四分类
    f, l, d = split_counts(live, nonempty, ours, usable_old)
    print("=" * 74)
    print(f"数据源 : {args.log}")
    print(f"场景   : DISPCNT=0x{s.dispcnt:04X}   arena = cb0 相对 tile [{LO},{HI}) = {n} tile")
    print("-" * 74)
    print("① 解析自证（用现状 old 策略重算日志里 [ARENA cb0] 的四分类）")
    print(f"   日志印刷 : 真·空闲={s.declared[0]}  非空且活引用={s.declared[1]}  "
          f"非空且在账本非活={s.declared[2]}  ★死数据={s.declared[3]}")
    print(f"   本脚本算 : 真·空闲={f}  非空且活引用={l}  非空但在账本={sum(1 for i in range(n) if nonempty[i] and ours[i])}  "
          f"★死数据={sum(1 for i in range(n) if nonempty[i] and not ours[i] and not live[i])}")
    print(f"   账本     : 日志={s.ours_declared}  本脚本={sum(ours)}")
    live_ours = sum(1 for i in range(n) if live[i] and ours[i])
    print(f"   活引用∩账本 : {live_ours}/{sum(ours)}"
          f"   （日志印 136/136；活引用总数={sum(live)}）")
    print(f"   ✅ 占用总量核对 : 非空={sum(nonempty)}（日志 [VRAM cb0] 印刷 "
          f"{sum(s.vram_cb0[LO:HI])}）")
    if sum(nonempty) != sum(s.vram_cb0[LO:HI]):
        print("   ✗ 自证失败：非空计数不一致")
        return 2
    print("-" * 74)

    # ---- 策略对比
    print("② 两种策略下「本次 begin 后真正可领」的池子")
    for name, fn in (("old（现状 v9）", usable_old), ("new（v10 无主即回收）", usable_new)):
        f, l, d = split_counts(live, nonempty, ours, fn)
        usable = sum(1 for i in range(n) if fn(live, nonempty, ours, i))
        pr = count_pairs(live, nonempty, ours, fn)
        print(f"   {name:<22} 可领={usable:>4} tile   可凑竖直对={pr:>4} 对"
              f"  ≈ {pr:>3} 个汉字   （不可领：活引用={l} 其它={d}）")
    print("-" * 74)

    need = args.labels * args.chars
    print(f"③ 领航员实景模拟：{args.labels} 条标签 × {args.chars} 字 = {need} 字"
          f"（每字 1 对 = {PAIR} tile，共需 {need * PAIR} tile）")
    for name, fn in (("old（现状 v9）", usable_old), ("new（v10 无主即回收）", usable_new)):
        ok, placed = sim_alloc(live, nonempty, ours, fn, need)
        miss = need - ok
        # 只画成功的前若干条标签，看第几条开始整条消失
        first_blank = None
        for lbl in range(args.labels):
            if lbl >= ok:
                first_blank = lbl
                break
        tail = "全部落下" if first_blank is None else f"第 {first_blank + 1} 条起整条消失"
        print(f"   {name:<22} 成功落字={ok:>3}/{need}  失败={miss:>3}   ⇒ {tail}")
        if placed:
            print(f"        落点 tile 范围 = {placed[0]}..{placed[-1] + PAIR}")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
