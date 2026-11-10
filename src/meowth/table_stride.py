"""定长表 stride 改写（v4：基于符号执行的 K 值）。

核心（回答用户疑问「这不该是猜的」）：
  站点集合**确定**（扫字面量 + 找 ldr）
  每个站点的 stride K **确定**（符号执行算出）
  K == 旧 stride 的才改；K == 0 或其它值的不改（它们不是本表的 index 索引）

v4 相比此前：
  - 不再用「窗口内找 lsls」的启发式
  - 直接用 thumb_symexec.solve_site() 算出的 K
  - 由 solve_site 同时返回「产生该 K 的那条移位指令」
    → 精确改写，不会改错指令

用法::

    from meowth.table_stride import plan_stride_rewrite

    plan = plan_stride_rewrite(rom, base=0x1CBC44, old_stride=8, new_stride=32)
    for p in plan.patches:
        rom[p.offset:p.offset + 2] = p.data
    # plan.skipped 里是「K != 旧stride」的站点，附理由
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .thumb_symexec import SymResult, solve_site, solve_site_auto, decode

GBA_BASE = 0x08000000


@dataclass
class Patch:
    offset: int
    data: bytes
    label: str = ""

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"Patch(0x{self.offset:06X}, {self.data.hex(' ')}, {self.label})"


@dataclass
class Skipped:
    ldr_off: int
    stride: int | None
    reason: str


@dataclass
class StridePlan:
    base: int
    old_stride: int
    new_stride: int
    patches: list[Patch] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    n_ldrs: int = 0

    @property
    def n_patches(self) -> int:
        return len(self.patches)

    @property
    def n_modified_sites(self) -> int:
        """实际要改的站点数（K == 旧stride）。"""
        return self.n_patches

    def describe(self) -> str:
        lines = [
            f"0x{self.base:06X}: stride {self.old_stride}→{self.new_stride}",
            f"  ldr 站点 {self.n_ldrs}  要改 {self.n_patches}  "
            f"不改 {len(self.skipped)}",
        ]
        for p in self.patches:
            lines.append(f"    ✅ 0x{p.offset:06X}: {p.data.hex(' ')}  {p.label}")
        for s in self.skipped:
            lines.append(f"    ⏭  0x{s.ldr_off:06X}: K={s.stride}  ({s.reason})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 找站点
# ---------------------------------------------------------------------------
def find_literal_sites(rom: bytes, gba_addr: int) -> list[int]:
    needle = struct.pack("<I", gba_addr)
    out: list[int] = []
    s = 0
    while True:
        i = rom.find(needle, s)
        if i < 0:
            break
        if i % 4 == 0:
            out.append(i)
        s = i + 1
    return out


def find_ldrs(rom: bytes, base: int, back: int = 4096) -> list[int]:
    """找全部 ldr 站点（去重，保序）。"""
    gba = base + GBA_BASE
    ldrs: list[int] = []
    seen: set[int] = set()
    for lit in find_literal_sites(rom, gba):
        for off in range(max(0, lit - back), lit, 2):
            hw = struct.unpack_from("<H", rom, off)[0]
            if (hw & 0xF800) != 0x4800:
                continue
            imm = (hw & 0xFF) * 4
            if ((off + 4) & ~3) + imm == lit:
                if off not in seen:
                    seen.add(off)
                    ldrs.append(off)
                break
    return sorted(ldrs)


# ---------------------------------------------------------------------------
# 编码
# ---------------------------------------------------------------------------
def thumb_shift(mn: str, rd: int, rs: int, imm: int) -> bytes:
    top = {"lsls": 0x0000, "lsrs": 0x0800, "asrs": 0x1000}[mn]
    return struct.pack("<H", top | (imm << 6) | (rs << 3) | rd)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def _find_mov_imm_mul_stride(
    rom: bytes, ldr_off: int, old_stride: int
) -> list[tuple[int, int]]:
    """找 ldr 前 ``movs rd, #old_stride`` + ``muls``（训练家 class 名等）。

    乘法常在 ``ldr =base`` **之前**完成，symexec 在 ldr 处只能看到
    ``base+const`` / ``base+index``，定位不到移位指令。此时改 movs 立即数即可。
    """
    if not (1 <= old_stride <= 255):
        return []
    hits: list[tuple[int, int]] = []
    lo = max(0, ldr_off - 0x40)
    for off in range(lo, ldr_off, 2):
        h = struct.unpack_from("<H", rom, off)[0]
        if (h & 0xF800) != 0x2000:  # movs rd, #imm8
            continue
        if (h & 0xFF) != (old_stride & 0xFF):
            continue
        rd = (h >> 8) & 7
        for off2 in range(off + 2, min(off + 10, ldr_off + 1), 2):
            h2 = struct.unpack_from("<H", rom, off2)[0]
            # muls rd, rm  → 010000 1101 mm m ddd
            if (h2 & 0xFFC0) != 0x4340:
                continue
            hits.append((off, rd))
            break
    return hits



# ---------------------------------------------------------------------------
# 同函数内的补充扫描
# ---------------------------------------------------------------------------
def _func_bounds(rom: bytes, off: int, limit: int = 0x800) -> tuple[int, int]:
    """以 push {.., lr} / pop {.., pc} / bx 为界，估出 off 所在函数的范围。

    尾跳 epilogue 的常见写法是 ``pop {r1}; bx r1``（不是 ``pop {pc}``），
    只认 pop-pc 会把下一个函数包进来 —— 图鉴列表 0x0808AD44 与相邻的
    清屏函数 0x0808ADEC 就会连成一片，于是后者的 ``(参数+i)<<1`` 被
    当成 ``i*6`` 误改，列表清屏步长变 ×8 → 整屏噪声。
    """
    n = len(rom)
    start = max(0, off - limit)
    for i in range(off, start, -2):
        h = struct.unpack_from("<H", rom, i)[0]
        if (h & 0xFE00) == 0xB400 and (h & 0x0100):
            start = i
            break
    end = min(n - 2, off + limit)
    for i in range(off, end, 2):
        h = struct.unpack_from("<H", rom, i)[0]
        if (h & 0xFE00) == 0xBC00 and (h & 0x0100):
            end = i + 2
            break
        if (h & 0xFF00) == 0x4700:          # bx rX —— 尾跳即函数结束
            end = i + 2
            break
    return start, end


def _scan_mul_sites(
    rom: bytes, lo: int, hi: int, stride: int, *, allow_sub: bool = False,
) -> list[tuple[int, int, int, int]]:
    """在 [lo, hi) 里找 ``i*stride`` 的三连，两种等价形态都认：

        lsls rA,rB,#n / adds rC,rA,rB / lsls rC,rC,#m   → ((1<<n)+1)<<m
        lsls rA,rB,#n / subs rC,rA,rB / lsls rC,rC,#m   → ((1<<n)-1)<<m

    返回 (h2 偏移, rd, rs, imm2)。K 必须**精确等于** stride 才收，
    所以这不是「窗口内瞎找 lsls」，是模式 + 常数双重校验。

    减法形态是 2026-11-10 补齐的：装饰名表 0x3C2A44 的步长 28 就是
    ``lsls #3 / subs / lsls #2``（(8-1)<<2），只认加法时那一处步长没改，
    整表索引错位 → 模拟器 input callback 停摆。
    """
    out: list[tuple[int, int, int, int]] = []
    hi = min(hi, len(rom) - 6)
    for a in range(lo, hi, 2):
        h0, h1, h2 = struct.unpack_from("<HHH", rom, a)
        if (h0 & 0xF800) != 0x0000:          # lsls
            continue
        imm0 = (h0 >> 6) & 0x1F
        rd0 = h0 & 7
        rs0 = (h0 >> 3) & 7
        op = h1 & 0xFE00
        if op not in ((0x1800, 0x1A00) if allow_sub else (0x1800,)):
            continue
        rd1 = h1 & 7
        rn1 = (h1 >> 3) & 7
        rm1 = (h1 >> 6) & 7
        if rd1 != rd0:
            continue
        if op == 0x1800:
            if not ((rn1 == rd0 and rm1 == rs0) or (rn1 == rs0 and rm1 == rd0)):
                continue
            base_k = (1 << imm0) + 1
        else:
            # subs rC, rn, rm：必须是「移位值 - 原值」= ((1<<n)-1)
            if not (rn1 == rd0 and rm1 == rs0):
                continue
            base_k = (1 << imm0) - 1
        if base_k <= 0:
            continue
        if (h2 & 0xF800) != 0x0000:          # lsls rC, rC, #m
            continue
        imm2 = (h2 >> 6) & 0x1F
        rd2 = h2 & 7
        rs2 = (h2 >> 3) & 7
        if rd2 != rd1 or rs2 != rd1:
            continue
        k = base_k << imm2
        if k == stride:
            out.append((a + 4, rd2, rs2, imm2))
    return out



def _scan_split_mul(rom: bytes, lo: int, hi: int, stride: int) -> list[tuple[int, int, int, int]]:
    """分离式 ``i*stride``：``lsls rA,rB,#1`` 与 ``adds/lsls`` 不连续。

    图鉴列表就是这么写的::

        0808AD84: lsls r3, r5, #1      ; r3 = i*2   （在判空分支里算的）
        0808AD88: lsls r0, r0, #3      ; 另一条链，已被上面改成 ×24
        0808AD98: adds r1, r3, r5      ; r1 = i*2 + i = i*3
        0808AD9A: lsls r1, r1, #1      ; i*6      ← 这一处以前完全没被改

    连续三连的扫描抓不到它（两段之间隔着 0x14 字节），于是一直按 ×6 索引
    新的 ×24 表，读到上一条目的尾巴：图鉴名字空/乱、光标一动就撞字。
    """
    if not (1 <= stride <= 255):
        return []
    hi = min(hi, len(rom) - 4)
    # 收集「rX = rY << 1」（要求 rX != rY，排除自移位）
    doubled: dict[int, list[tuple[int, int]]] = {}
    for a in range(lo, hi, 2):
        h = struct.unpack_from("<H", rom, a)[0]
        if (h & 0xF800) != 0x0000:
            continue
        if ((h >> 6) & 0x1F) != 1:
            continue
        rd = h & 7
        rs = (h >> 3) & 7
        if rd != rs:
            doubled.setdefault(rd, []).append((rs, a))

    out: list[tuple[int, int, int, int]] = []
    for a in range(lo, hi - 2, 2):
        h1, h2 = struct.unpack_from("<HH", rom, a)
        if (h1 & 0xFE00) != 0x1800:          # adds rD, rn, rm
            continue
        rd = h1 & 7
        rn = (h1 >> 3) & 7
        rm = (h1 >> 6) & 7
        if (h2 & 0xF800) != 0x0000:          # lsls rD, rD, #m
            continue
        if (h2 & 7) != rd or ((h2 >> 3) & 7) != rd:
            continue
        imm2 = (h2 >> 6) & 0x1F
        # rn 是否是「rm 的两倍」（且那条 lsls 在本条之前）
        ok = False
        for src, pos in doubled.get(rn, ()):
            if src == rm and pos < a:
                ok = True
                break
        if not ok:
            for src, pos in doubled.get(rm, ()):
                if src == rn and pos < a:
                    ok = True
                    break
        if not ok:
            continue
        if (3 << imm2) == stride:
            out.append((a + 2, rd, rd, imm2))
    return out


def plan_stride_rewrite(
    rom: bytes,
    base: int,
    old_stride: int,
    new_stride: int,
) -> StridePlan:
    """规划 stride 改写：只改 K == old_stride 的站点。"""
    if new_stride <= old_stride:
        raise ValueError(f"new_stride {new_stride} <= old {old_stride}")
    ratio = new_stride // old_stride
    if ratio & (ratio - 1):
        raise ValueError(f"倍数 {ratio} 不是 2 的幂")
    if new_stride > 255:
        raise ValueError(f"new_stride {new_stride} 超出 movs imm8")

    plan = StridePlan(base=base, old_stride=old_stride, new_stride=new_stride)
    ldrs = find_ldrs(rom, base)
    plan.n_ldrs = len(ldrs)
    seen_mov: set[int] = set()

    for ldr in ldrs:
        # ⚠️ 用 solve_site_auto（三档起点兜底），不是裸 solve_site。
        #    实测 9 张表 158 个可改写站点：裸 solve_site 只识别 88%，
        #    auto 版本 100%。差别在「函数参数符号化 / 函数入口起点 /
        #    调用者传参兜底」三处（详见 thumb_symexec 注释）。
        r = solve_site_auto(rom, ldr, expect=old_stride)
        if r.stride == old_stride and r.insn_off is not None and r.insn_mn:
            # 计算新立即数：lsls 加、lsrs 减
            delta = ratio.bit_length() - 1
            if r.insn_mn == "lsls":
                new_imm = r.insn_imm + delta
            elif r.insn_mn == "lsrs":
                new_imm = r.insn_imm - delta
            else:
                plan.skipped.append(Skipped(
                    ldr_off=ldr, stride=r.stride,
                    reason=f"不支持的移位 {r.insn_mn}",
                ))
                continue

            if not (0 <= new_imm <= 31):
                plan.skipped.append(Skipped(
                    ldr_off=ldr, stride=r.stride,
                    reason=f"新立即数 {new_imm} 越界",
                ))
                continue

            plan.patches.append(Patch(
                offset=r.insn_off,
                data=thumb_shift(r.insn_mn, r.insn_rd, r.insn_rs, new_imm),
                label=f"K={r.stride} {r.insn_mn} #{r.insn_imm}→#{new_imm} "
                      f"(stride {old_stride}→{new_stride}) ← ldr 0x{ldr:06X}",
            ))
            continue

        # 回落：movs #old + muls（乘法在 ldr 之前）
        movs = _find_mov_imm_mul_stride(rom, ldr, old_stride)
        if movs:
            for mov_off, rd in movs:
                if mov_off in seen_mov:
                    continue
                seen_mov.add(mov_off)
                plan.patches.append(Patch(
                    offset=mov_off,
                    data=struct.pack("<H", 0x2000 | (rd << 8) | (new_stride & 0xFF)),
                    label=(
                        f"movs r{rd}, #{old_stride}→#{new_stride} "
                        f"(muls stride) ← ldr 0x{ldr:06X}"
                    ),
                ))
            continue

        plan.skipped.append(Skipped(
            ldr_off=ldr, stride=r.stride,
            reason=r.reason or "K 不等于旧 stride 且无 movs+muls",
        ))

    # ---- 同函数补扫：一个 ldr 站点常有多条 ×old_stride 计算链 ----
    # 典型：图鉴先算 species×6 判空，再算一次取名字。solve_site_auto 只
    # 返回其中一条链，另一条保持 ×6 —— 于是「判空按 ×24、取值按 ×6」，
    # 读到上一条目的尾巴：名字一半空一半乱，光标一移动还撞字。
    if plan.patches:
        seen_off = {p.offset for p in plan.patches}
        extra_delta = ratio.bit_length() - 1
        for ldr in ldrs:
            fstart, fend = _func_bounds(rom, ldr)
            cand = (_scan_mul_sites(rom, fstart, fend, old_stride)
                    + _scan_split_mul(rom, fstart, fend, old_stride))
            for off2, rd2, rs2, imm2 in cand:
                if off2 in seen_off:
                    continue
                new_imm2 = imm2 + extra_delta
                if not (0 <= new_imm2 <= 31):
                    continue
                seen_off.add(off2)
                plan.patches.append(Patch(
                    offset=off2,
                    data=thumb_shift("lsls", rd2, rs2, new_imm2),
                    label=(f"K={old_stride} lsls #{imm2}→#{new_imm2} "
                           f"(同函数补扫) ← ldr 0x{ldr:06X}"),
                ))

    return plan


def verify_applied(
    rom: bytes, base: int, old_stride: int, new_stride: int,
) -> tuple[int, int, int]:
    """验证：改完后重扫，确认全部要改的站点已生效。

    返回 (原应改数, 已改数, 仍是旧值的数)。
    """
    before = plan_stride_rewrite(rom, base, old_stride, new_stride)
    # 应用后重新求 K（应该都变成 new_stride）
    sim = bytearray(rom)
    for p in before.patches:
        sim[p.offset:p.offset + len(p.data)] = p.data

    changed = 0
    stale = 0
    for ldr in find_ldrs(rom, base):
        r = solve_site(bytes(sim), ldr)
        if r.stride == new_stride:
            changed += 1
        elif r.stride == old_stride:
            stale += 1
    return before.n_patches, changed, stale
