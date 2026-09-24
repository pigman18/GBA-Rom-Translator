"""守门：核 `chs_cell_from_1bpp` 各调用点读的字库地址是否与 fonts.s 的落盘一致。

背景（2026-09-20 领航员乱码事故）：`graphic/fonts.s` 里有两个 Middle——
  0x09400000  128 B/字  4bpp 独占槽版
  0x09700000   13 B/字  1bpp 紧凑版  ← chs_cell_from_1bpp 必须用这个
有人把 C 代码里的宏从 ADDR_FONT_1BPP_MIDDLE 改成 ADDR_FONT_CHS_MIDDLE（名字变了、
地址也变了），拿 13B 步进读 128B 步进数据 ⇒ 整屏乱码。

本脚本从 **fonts.s（原件权威）** 反查地址，再从 **编译产物** 反查实际用的地址，
两者比对。任一处对不上就 FAIL。

用法：
  python scripts/check_font_addrs.py            # 用 hook/out/game.elf
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "configs" / "POKEMON_RUBY_AXVJ00" / "hook"
FONTS_S = HOOK / "graphic" / "fonts.s"
ELF = HOOK / "out" / "game.elf"

OBJDUMP = "arm-none-eabi-objdump"


def parse_fonts_s():
    """fonts.s → {addr: incbin文件名}"""
    txt = FONTS_S.read_text(encoding="utf-8", errors="replace")
    out = {}
    cur = None
    for line in txt.splitlines():
        line = line.strip()
        m = re.match(r"\.org\s+(0x[0-9A-Fa-f]+)", line)
        if m:
            cur = int(m.group(1), 16)
        m = re.match(r'\.incbin\s+"([^"]+)"', line)
        if m and cur is not None:
            out[cur] = Path(m.group(1)).name
            cur = None
    return out


def find_expected(layout, needle):
    hits = [(a, f) for a, f in layout.items() if needle.lower() in f.lower()]
    if len(hits) != 1:
        raise SystemExit("FAIL: fonts.s 里 %r 命中 %d 处（应为 1）: %s"
                         % (needle, len(hits), hits))
    return hits[0]


def _find_objdump():
    """objdump 常不在 PATH 里（本机工具链在 Program Files 下）⇒ 自己找。"""
    from shutil import which
    w = which(OBJDUMP) or which(OBJDUMP + ".exe")
    if w:
        return w
    import glob
    pats = [
        r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\*\bin\arm-none-eabi-objdump.exe",
        r"C:\Program Files\Arm GNU Toolchain arm-none-eabi\*\bin\arm-none-eabi-objdump.exe",
        r"C:\Program Files*\Arm*\*\bin\arm-none-eabi-objdump.exe",
        r"C:\msys64\*\bin\arm-none-eabi-objdump.exe",
    ]
    for p in pats:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[-1]
    raise SystemExit("FAIL: 找不到 arm-none-eabi-objdump（请把它加进 PATH）")


def elf_call_sites():
    """从反汇编里取 chs_cell_from_1bpp 每个 bl 之前由 movs/lsls 构造的基址。"""
    if not ELF.exists():
        raise SystemExit("FAIL: 找不到 %s（先跑 build_sh_equiv.sh）" % ELF)
    dis = subprocess.run([_find_objdump(), "-d", str(ELF)], capture_output=True,
                         check=True).stdout.decode("utf-8", "replace")
    lines = dis.splitlines()
    sites = []
    base = None
    for i, ln in enumerate(lines):
        m = re.search(r"\bmovs\s+r\d+,\s*#(\d+)\s*@\s*0x([0-9A-Fa-f]+)", ln)
        if m:
            base = None
            # 往后找 lsls rX, rX, #20
            for ln2 in lines[i + 1:i + 6]:
                m2 = re.search(r"lsls\s+\w+,\s*\w+,\s*#(\d+)", ln2)
                if m2 and int(m2.group(1)) == 20:
                    base = int(m.group(2), 16) << 20
                    break
        m = re.search(r"\bbl\s+[0-9a-f]+\s+<chs_cell_from_1bpp>", ln)
        if m:
            sites.append((ln.strip().split(":")[0], base))
            base = None
    return sites


def main():
    layout = parse_fonts_s()
    exp = {
        "Big1Bpp": find_expected(layout, "Big1Bpp"),
        "Small1Bpp": find_expected(layout, "Small1Bpp"),
        "Middle1Bpp": find_expected(layout, "Middle1Bpp"),
    }
    print("fonts.s 权威落盘：")
    for k, (a, f) in exp.items():
        print("  %-11s 0x%08X  %s" % (k, a, f))

    want = {a for a, _ in exp.values()}
    sites = elf_call_sites()
    print("\nchs_cell_from_1bpp 调用点（来自 %s）：" % ELF.name)
    got = []
    for addr, base in sites:
        got.append(base)
        tag = "OK " if base in want else "!! "
        print("  %s%s  基址 %s" % (tag, addr,
                                   "0x%08X" % base if base else "未识别"))

    missing = want - set(got)
    extra = {b for b in got if b} - want
    if missing or extra or not sites:
        print("\nRESULT: FAIL")
        if missing:
            print("  缺失（应出现却没出现）：", ["0x%08X" % a for a in sorted(missing)])
        if extra:
            print("  多余（出现了不该有的）：", ["0x%08X" % a for a in sorted(extra)])
        if not sites:
            print("  一个调用点都没识别到 —— 反汇编格式可能变了，本脚本需更新")
        return 1
    print("\nRESULT: PASS —— 三个 1bpp 字库基址与 fonts.s 完全一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
