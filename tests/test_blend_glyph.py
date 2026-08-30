#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_blend_glyph.py — blend_glyph 对拍（设计稿 §5 步骤 1）

三层验证：
  1. C selftest：blend_glyph_1bpp vs vendored 官方 refpr_draw_tile_unshadowed
     （reference/pokeruby/draw_glyph_tile.c，shim 头编译）随机逐位对拍；
  2. Python 参考实现 vs C：eval 通道随机 fuzz（含 (width,startPixel) 全覆盖）；
  3. Python 掩码表不转录——直接从 vendored 官方源码解析 sGlyphMasks /
     sGlyphShiftAmounts，杜绝转录走样。

用法：python tests/test_blend_glyph.py
退出码 0 = 全绿。
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "work" / "POKEMON_RUBY_AXVJ00" / "build"
BLEND_C = HOOK / "src" / "text" / "blend_glyph.c"
BLEND_H_DIR = HOOK / "include"
OFFICIAL_C = HOOK / "reference" / "pokeruby" / "draw_glyph_tile.c"
HOST = ROOT / "tests" / "host"
BUILD = HOST / "_build"

M32 = 0xFFFFFFFF


# ---------------------------------------------------------------- 官方表解析
def parse_official_tables():
    src = OFFICIAL_C.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"sGlyphMasks\s*\[9\]\[8\]\[3\]\s*=\s*\{", src)
    if not m:
        raise RuntimeError("sGlyphMasks not found in vendored official source")
    tail = src[m.end():m.end() + 20000]
    vals = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{1,8}", tail)]
    if len(vals) < 9 * 8 * 3:
        raise RuntimeError(f"sGlyphMasks parse short: {len(vals)}")
    masks = [vals[i * 3:(i + 1) * 3] for i in range(9 * 8)]
    masks = [[masks[w * 8 + s] for s in range(8)] for w in range(9)]

    m = re.search(r"sGlyphShiftAmounts\[8\]\s*=\s*\{", src)
    if not m:
        raise RuntimeError("sGlyphShiftAmounts not found")
    tail = src[m.end():m.end() + 2000]
    pairs = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*\}", tail)
    if len(pairs) < 8:
        raise RuntimeError(f"sGlyphShiftAmounts parse short: {len(pairs)}")
    shifts = [(int(a), int(b)) for a, b in pairs[:8]]
    return masks, shifts


MASKS, SHIFTS = parse_official_tables()


# ------------------------------------------------------- Python 参考实现
def expand_row_1bpp(rows, r, width, colors):
    bits = rows[r]
    val = 0
    # 上游怪癖（照抄）：官方 Width3 特化函数实际展开 4 像素（"XXX: why 4?"）
    n = 4 if width == 3 else width
    for p in range(n):
        val |= colors[(bits >> (7 - p)) & 1] << (p * 4)
    return val


def expand_row_2bpp(rows, r, width, colors):
    row = rows[r * 2:(r + 1) * 2]
    val = 0
    for p in range(width):
        px = (row[p >> 2] >> ((p & 3) * 2)) & 3
        val |= colors[px] << (p * 4)
    return val


def blend_ref(fmt, dest, spill, rows, width, start_pixel, colors):
    """官方语义参考实现。dest/spill: list[8] u32；返回 (adv, dest, spill)。"""
    width = min(width, 8) if width else 0
    start_pixel = min(start_pixel, 7)
    if width == 0:
        return start_pixel // 8, list(dest), list(spill)

    m1 = MASKS[width][start_pixel][0] | MASKS[width][start_pixel][2]
    m2 = MASKS[width][start_pixel][1]
    left, right = SHIFTS[start_pixel]
    do_spill = spill is not None and (start_pixel + width > 8)
    exp = expand_row_1bpp if fmt == 1 else expand_row_2bpp

    out1, out2 = [], []
    for r in range(8):
        val = exp(rows, r, width, colors)
        out1.append(((dest[r] & m1) | ((val << left) & M32)) & M32)
        if do_spill:
            out2.append((spill[r] & m2) | (val >> right))
    if do_spill:
        spill = out2
    return (start_pixel + width) // 8, out1, list(spill)


# ------------------------------------------------------------------ harness
def find_clang():
    for cand in (shutil.which("clang"),
                 r"C:\Program Files\LLVM\bin\clang.exe",
                 shutil.which("gcc")):
        if cand:
            return cand
    raise RuntimeError("host compiler (clang/gcc) not found")


def build_harness():
    BUILD.mkdir(parents=True, exist_ok=True)
    cc = find_clang()
    exe = BUILD / "blend_harness.exe"

    # vendored 官方文件引号包含 "../../include/text_render.h"（相对每个搜索
    # 目录拼接）——在临时目录镜像出 ref/pokeruby + ref/include 布局（与
    # reference/pokeruby → include 的相对深度一致），shim 放 include/。
    mirror_src = BUILD / "m" / "ref" / "pokeruby"
    mirror_inc = BUILD / "m" / "include"
    mirror_src.mkdir(parents=True, exist_ok=True)
    mirror_inc.mkdir(parents=True, exist_ok=True)
    official_copy = mirror_src / "draw_glyph_tile.c"
    official_copy.write_bytes(OFFICIAL_C.read_bytes())
    shutil.copyfile(HOST / "text_render.h", mirror_inc / "text_render.h")

    objs = []
    for src, extra in ((BLEND_C, ["-I", str(BLEND_H_DIR)]),
                       (official_copy, []),
                       (HOST / "blend_glyph_harness.c",
                        ["-I", str(mirror_inc), "-I", str(BLEND_H_DIR)])):
        obj = BUILD / (src.stem + ".o")
        cmd = [cc, "-O1", "-Wall", "-c", str(src), "-o", str(obj)] + extra
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"compile failed: {src}\n{r.stderr}")
        objs.append(obj)

    r = subprocess.run([cc, "-O1", *[str(o) for o in objs],
                        "-o", str(exe)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"link failed:\n{r.stderr}")
    return exe


def run_selftest(exe, n=2000):
    r = subprocess.run([str(exe), "selftest", str(n)],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr)
        raise AssertionError("C selftest vs official FAILED")
    assert "SELFTEST OK" in r.stdout


def run_eval_fuzz(exe, n=800, seed=20260831):
    import random
    rng = random.Random(seed)

    lines, expects, covered = [], [], set()
    # 1) (width,startPixel) 全覆盖 × 3 组随机底图
    params = [(w, s) for w in range(9) for s in range(8)] * 3
    # 2) 随机补样
    params += [(rng.randrange(9), rng.randrange(8)) for _ in range(n)]
    for w, s in params:
        fmt = 1 if rng.random() < 0.5 else 2
        covered.add((fmt, w, s))
        bg, fg = rng.randrange(16), rng.randrange(16)
        dest = [rng.getrandbits(32) for _ in range(8)]
        spill = [rng.getrandbits(32) for _ in range(8)]
        nrows = 16 if fmt == 2 else 8
        rows = [rng.randrange(256) for _ in range(nrows)]
        cols = [bg, fg, fg, fg] if fmt == 2 else [bg, fg]

        adv_exp, d_exp, s_exp = blend_ref(fmt, dest, spill, rows, w, s, cols)
        lines.append(" ".join(
            [str(fmt), str(w), str(s), str(bg), str(fg)]
            + [f"{x:08x}" for x in dest] + [f"{x:08x}" for x in spill]
            + [f"{x:02x}" for x in rows]))
        expects.append((adv_exp, d_exp, s_exp, fmt, w, s))

    inp = "\n".join(lines) + "\n"
    r = subprocess.run([str(exe), "eval"], input=inp,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        raise AssertionError("eval harness exited nonzero")

    got = r.stdout.strip().splitlines()
    assert len(got) == len(expects), f"line count {len(got)} != {len(expects)}"

    bad = 0
    for line, (adv_exp, d_exp, s_exp, fmt, w, s) in zip(got, expects):
        parts = line.split()
        adv = int(parts[0])
        d_got = [int(x, 16) for x in parts[1:9]]
        s_got = [int(x, 16) for x in parts[9:17]]
        if adv != adv_exp or d_got != d_exp or s_got != s_exp:
            bad += 1
            if bad <= 5:
                print(f"MISMATCH fmt={fmt} w={w} sp={s}\n"
                      f"  adv  C={adv} py={adv_exp}\n"
                      f"  dst  C={[f'{x:08x}' for x in d_got]}\n"
                      f"       py={[f'{x:08x}' for x in d_exp]}\n"
                      f"  spl  C={[f'{x:08x}' for x in s_got]}\n"
                      f"       py={[f'{x:08x}' for x in s_exp]}")
    if bad:
        raise AssertionError(f"{bad}/{len(expects)} eval cases FAILED")
    print(f"EVAL OK ({len(expects)} cases, "
          f"{len(covered)} (fmt,width,sp) combos, python vs C)")


def visual_demo():
    """ASCII 眼验：3 个假 16px 字形（每字左右两列、各 adv=1）混合写入共享画布，
    画布只取每列 tile 的上 8 行（下 8 行同理不另画）。验证相邻字共享 tile 时
    互不踩踏（混合写入核心卖点）。"""
    W = 8  # 8 列 tile，够 3 个 16px 字 + 间距
    dest = [[0x11111111] * 8 for _ in range(W)]  # bg 色号=1

    glyphs = []
    for k, seed in enumerate((0xA5, 0x5A, 0xC3)):
        rows = [(((seed * (r + 1) * 37 + k * 11) ^ (r * 7)) >> 8) & 0xFF
                for r in range(8)]  # 每字 1 个 8 行×8px 列（示意半字）
        glyphs.append(rows)

    px = 0
    for rows8 in glyphs:
        tile_col = px // 8
        sp = px % 8
        adv, d2, _ = blend_ref(1, dest[tile_col], [0] * 8, rows8, 8, sp, [1, 12])
        dest[tile_col] = d2
        px += adv * 8
        px += 8  # 字间距 8px（下一字列）
        if tile_col + 1 < W:
            adv, d2, _ = blend_ref(1, dest[tile_col + 1], [0] * 8,
                                   [r for r in rows8], 8, 0, [1, 6])
            dest[tile_col + 1] = d2

    print("\nVISUAL DEMO (bg=., fg=#):")
    for r in range(8):
        line = ""
        for t in range(W):
            word = dest[t][r]
            for nib in range(8):
                line += "#" if ((word >> (nib * 4)) & 0xF) != 1 else "."
        print("  " + line)


def main():
    print(f"official masks parsed: {len(MASKS)}x{len(MASKS[0])}x3, "
          f"shifts={SHIFTS[0]}...{SHIFTS[7]}")
    exe = build_harness()
    print(f"harness: {exe}")
    run_selftest(exe)
    run_eval_fuzz(exe)
    visual_demo()
    print("\nALL GREEN")


if __name__ == "__main__":
    sys.exit(main())
