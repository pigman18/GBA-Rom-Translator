#!/usr/bin/env python3
"""调研(54) 自检：用**故意出错**的 Lua 验证 emu_run 的检测能力。

═══════════════════════════════════════════════════════════════════════════
【为什么必须自检】
═══════════════════════════════════════════════════════════════════════════
2026-11-04 踩到的坑：Lua 刷出几百行「attempt to use a closed file」，
mGBA 退出码 0，Python 侧当成功。

只写检测器而不**证明它能抓到**，等于把同一个坑换个地方埋。

本脚本跑 6 个用例，逐个核对「期望 vs 实测」：

  A  语法错            → FAIL（无日志/[DONE]）
  B  运行期抛错        → FAIL（有 [LUA-ERR]）
  C  早退帧数不足      → FAIL（帧数 < min_frames）
  D  正常走完但缺产出  → FAIL（expect_files 缺失）
  E  完全正常          → PASS（反证不是一路 FAIL）
  F  调用不存在的 API  → FAIL（emu:exit 是 nil）

用法：python scripts/research/firered/54_selftest_emu_run.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "research" / "common"))

from emu_run import run_lua, SAVE_FR, ROM_ZH   # noqa: E402

OUT_ROOT = ROOT / "work" / "_probe" / "emu_selftest"

# 注意：mGBA 的 emu 没有 exit/stop，脚本只能写 DS_DONE 让 Python 收尾
OK_BODY = r'''
local f = io.open(OUT .. "/ok.bin", "wb")
f:write("hello"); f:close()
local frame = 0
callbacks:add("frame", WRAP("main", function()
    frame = frame + 1
    RUN.f = frame
    if frame >= 120 then DS_DONE(0, "ok") end
end))
'''


def case(desc: str, body: str, expect_files, min_frames: int,
         want: str, timeout: int = 120) -> tuple[bool, str]:
    print("\n" + "=" * 70)
    print(f"[case] {desc}   期望 {want}")
    out = OUT_ROOT / desc.split("-")[0]
    r = run_lua(body, out, expect_files=expect_files,
                min_frames=min_frames, rom=ROM_ZH, save=SAVE_FR,
                timeout=timeout)
    print(r.report())
    got = "PASS" if r.ok else "FAIL"
    good = (got == want)
    print(f"  => 实测 {got}，{'符合' if good else '**不符合！！**'}")
    return good, desc.split("-")[0]


def main() -> int:
    results = []

    # A：语法错（未定义的语句）
    results.append(case(
        "A-syntax", "this is not lua at all @@@###\n", None, 0, "FAIL"))

    # B：运行期抛错（访问 nil 的字段）
    results.append(case(
        "B-runtime",
        'local t = nil\n'
        'callbacks:add("frame", WRAP("bad", function()\n'
        '    RUN.f = RUN.f + 1\n'
        '    local _ = t.field\n'
        'end))\n',
        None, 0, "FAIL"))

    # C：早退（10 帧就完成，达不到 200）
    results.append(case(
        "C-early",
        'callbacks:add("frame", WRAP("m", function()\n'
        '    RUN.f = RUN.f + 1\n'
        '    if RUN.f >= 10 then DS_DONE(0, "early") end\n'
        'end))\n',
        None, 200, "FAIL"))

    # D：正常但不产出期望文件
    results.append(case(
        "D-nofile", OK_BODY, ["must_not_exist.bin"], 100, "FAIL"))

    # E：完全正常
    results.append(case(
        "E-good", OK_BODY, ["ok.bin"], 100, "PASS"))

    # F：调用不存在的 API（这正是今天踩的坑）
    results.append(case(
        "F-badapi",
        'callbacks:add("frame", WRAP("m", function()\n'
        '    RUN.f = RUN.f + 1\n'
        '    if RUN.f >= 20 then\n'
        '        DS_DONE(0, "ok")\n'
        '        emu:exit()\n'          # 不存在的 API，应抛错并被抓到
        '    end\n'
        'end))\n',
        None, 10, "FAIL"))

    print("\n" + "=" * 70)
    print("自检汇总")
    print("=" * 70)
    for ok, name in results:
        print(f"  {name:<12} {'通过' if ok else '**未抓到（检测器有漏洞）**'}")
    allok = all(ok for ok, _ in results)
    print(f"\n  => {'全部符合预期，检测器可用' if allok else '有漏洞，必须先修'}")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
