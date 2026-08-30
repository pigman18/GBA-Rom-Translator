"""离线验证战斗动画 handler：mock 一个 GdbClient + Ctx，喂真实 EWRAM 布局。

不启模拟器，纯静态验证：_anim_state 偏移、命令名映射、VRAM 分区、日志格式。
"""
import struct
import sys
import io

sys.path.insert(0, "src")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import util.gdb_patcher as gp  # noqa: E402

# ---- 构造假内存 ------------------------------------------------------------
ANIM_BASE = gp.A_SCRIPT_PTR          # 0x0202F7A4
SCRIPT = 0x081D36DC                  # 真实动画脚本区起点
SCRIPT_BYTES = bytes([0x00, 0x34, 0x12,        # cmd0 loadspritegfx, tileTag=0x1234
                      0x02, 0x11, 0x22, 0x33,  # cmd2 createsprite
                      0x14, 0x01,              # cmd20 fadetobg
                      0xFF, 0xFF])


class FakeGdb:
    """只实现 read_mem；内存 = EWRAM 状态块 + 脚本区 + 若干 sheet/调色板。"""

    def __init__(self, move=33, cmd_off=0, active=1, wait=0, vis=2, snd=0,
                 turn=1, bgfade=3):
        self.mem = {}
        st = bytearray(0x28)
        struct.pack_into("<I", st, 0x00, SCRIPT + cmd_off)   # sBattleAnimScriptPtr
        struct.pack_into("<I", st, 0x04, SCRIPT + 0x40)      # ret addr
        struct.pack_into("<I", st, 0x08, 0x08072048)         # callback
        st[0x0C] = wait
        st[0x0D] = active
        st[0x0E] = vis
        st[0x0F] = snd
        st[0x20] = turn
        st[0x21] = bgfade
        struct.pack_into("<H", st, 0x22, move)               # sAnimMoveIndex
        st[0x24] = 0                                         # attacker
        st[0x25] = 1                                         # target
        self.mem[ANIM_BASE] = bytes(st)
        self.mem[SCRIPT] = SCRIPT_BYTES
        # 一个 sheet：{data=0x08100000, size=0x800, tag=0x1234}
        self.mem[0x02000000] = struct.pack("<IHH", 0x08100000, 0x800, 0x1234)

    def read_mem(self, addr, n):
        out = bytearray()
        for i in range(n):
            a = addr + i
            base = None
            for k in self.mem:
                if k <= a < k + len(self.mem[k]):
                    base = k
                    break
            out.append(self.mem[base][a - base] if base is not None else 0)
        return bytes(out)


class FakeCtx:
    def __init__(self):
        self.lines = []
        self._seen = set()
        self.origin = None          # _rom_head 会读它；None 时该段自动跳过

    def log(self, msg=""):
        self.lines.append(str(msg))

    def _hit(self, key):
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


def run(name, fn, gdb, regs=None):
    ctx = FakeCtx()
    fn(gdb, regs or {}, ctx, {})
    print(f"\n--- {name} ---")
    for ln in ctx.lines:
        print(ln)
    return ctx


print("=" * 70)
print("战斗动画 handler 离线验证（mock 数据，不启模拟器）")
print("=" * 70)

g = FakeGdb(move=33, cmd_off=0)
run("AnimScriptCmd @cmd0=loadspritegfx", gp.HANDLERS["AnimScriptCmd"], g)

g2 = FakeGdb(move=33, cmd_off=0)
run("AnimLoadSpriteGfx (应解析出 tileTag=0x1234)", gp.HANDLERS["AnimLoadSpriteGfx"], g2)

g3 = FakeGdb(move=33, cmd_off=7, bgfade=0)      # SCRIPT_BYTES[7] = 0x14 = cmd20
run("AnimFadeToBg @cmd20(fadetobg)", gp.HANDLERS["AnimFadeToBg"], g3)

g4 = FakeGdb(move=33, cmd_off=0)
run("MoveAnimEntry", gp.HANDLERS["MoveAnimEntry"], g4, {"r0": 33, "r14": 0x08123456})

g5 = FakeGdb(move=33, cmd_off=0)
run("LaunchAnim (表=0x081D997C, move=33)", gp.HANDLERS["LaunchAnim"], g5,
    {"r0": 0x081D997C, "r1": 33, "r2": 1, "r14": 0x08123700})

g6 = FakeGdb(move=33, cmd_off=0)
run("LZDecompressVram (dest=BG-cb1，应带动画上下文)", gp.HANDLERS["LZDecompressVram"], g6,
    {"r0": 0x08100000, "r1": 0x06004000})

g7 = FakeGdb(move=33, cmd_off=0)
run("LoadSpriteSheet (应带动画上下文)", gp.HANDLERS["LoadSpriteSheet"], g7,
    {"r0": 0x02000000})

g8 = FakeGdb(move=33, cmd_off=0)
run("LoadPalette (应带动画上下文)", gp.HANDLERS["LoadPalette"], g8,
    {"r0": 0x08100000, "r1": 0, "r2": 0x200})

# 动画未激活时，tile handler 只出原有日志、不追加动画上下文（平时日志不受影响）
g9 = FakeGdb(move=33, cmd_off=0, active=0)
c9 = run("LoadSpriteSheet 但动画未激活（不应追加动画上下文）",
         gp.HANDLERS["LoadSpriteSheet"], g9, {"r0": 0x02000000})
has_anim = any("动画" in ln for ln in c9.lines)
print(f"  → 含动画上下文: {has_anim}（期望 False）")
print(f"  → 仍出原有日志: {any('LoadSpriteSheet' in ln for ln in c9.lines)}（期望 True）")

# VRAM 分区
print("\n--- _vram_zone 分区校验 ---")
for a in (0x06000000, 0x06004000, 0x06008000, 0x0600C000, 0x06010000, 0x07000000, 0x05000000):
    print(f"  0x{a:08X} → {gp._vram_zone(a)}")
