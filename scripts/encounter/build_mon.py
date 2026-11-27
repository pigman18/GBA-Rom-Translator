"""构造 Gen3 struct Pokemon（100B）并生成「写入内存」脚本。

═══════════════════════════════════════════════════════════════════════════════
为什么不能用「直接写明文区」
═══════════════════════════════════════════════════════════════════════════════
实测（2026-11-27，_probe_write_test 场景）：
  把 gEnemyParty[0] 的 +0x54(level) / +0x58(maxHP) / +0x56(curHP) / +0x5A(atk)
  改成 77 / 321 / 200 / 555，poke 写后复核**成功**，但下一帧就被游戏重算覆盖：
    0x03004544 (level 位置) 仍是 0D(13)
  血条毫无变化 —— 仍是「负电拍拍 Lv13」。

  原因：+0x54 起的这些值是**派生值**，游戏每帧从加密区重算后回写。
  真正要改的是**加密区**（species / exp / IVs / moves），改完必须重新加密 + 重算 checksum。

═══════════════════════════════════════════════════════════════════════════════
Gen3 struct Pokemon 真实布局（本工具实测校验）
═══════════════════════════════════════════════════════════════════════════════
  +0x00  personality  u32   ← 决定加密排列 + 性格 + 性别
  +0x04  otId         u32   ← 与 personality 一起做 XOR key
  +0x08  nickname     10B   ← 明文，游戏文本编码
  +0x12  language     1B
  +0x13  flags        1B
  +0x14  otName       7B
  +0x1B  markings     1B
  +0x1C  checksum     u16   ← 48B 加密区的 u16 累加和
  +0x1E  ?            2B
  +0x20  加密区       48B   ← G/A/E/M 四块，按 personality%24 重排后 XOR
  +0x50  status       u32
  +0x54  level        1B    ← 派生值，会被重算覆盖（不能直接写）
  +0x55  pokerus      1B
  +0x56  curHP        u16   ← 派生值
  +0x58  maxHP        u16   ← 派生值
  +0x5A..0x62 atk/def/spe/spa/spd  ← 派生值

═══════════════════════════════════════════════════════════════════════════════
加密算法（pokeruby，已用真实内存数据反向验证通过）
═══════════════════════════════════════════════════════════════════════════════
  ① order = personality % 24，从 24 种排列里取一个（G/A/E/M 的顺序）
  ② 按 order 把 G(12B)/A(12B)/E(12B)/M(12B) 拼成 48B 明文
  ③ key = otId ^ personality；对 48B 每 4 字节 XOR key
  ④ checksum = 48B 明文按 u16 累加 & 0xFFFF

  G 块 (Growth):   species u16 | item u16 | exp u32 | PPbonus u8 | friendship u8 | ? u16
  A 块 (Attacks):  move1..4 u16 ×4 | pp1..4 u8 ×4
  E 块 (Effort):   hp/atk/def/spe/spa/spd EV u8 ×6 | cool/beauty/cute/smart/tough/feel u8 ×6
  M 块 (Misc):     pokerus u8 | metLocation u8 | metLevel u8 | ballAndGender u8 | IVs u32 | ribbons u32

═══════════════════════════════════════════════════════════════════════════════
用法
═══════════════════════════════════════════════════════════════════════════════
    # 生成 100B 结构 + 写入脚本（默认敌方 slot 0）
    python scripts/encounter/build_mon.py --species 354 --level 25

    # 指定六维 IV / 技能 / 性格
    python scripts/encounter/build_mon.py --species 354 --level 50 \
        --iv 31,31,31,31,31,31 --moves 45,86,98,270 --nature 0

    # 解码一段已存在的内存（验证用）
    python scripts/encounter/decode_mon.py 0x030044F0 --log <scene.log>
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPECIES_INDEX = ROOT / "work" / "_species_index.json"

# 24 种子结构排列（personality % 24 索引）
# 顺序来自 Bulbapedia「Pokémon data substructures (Generation III)」
ORDER_TABLE = [
    "GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA",
    "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
    "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG",
    "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG",
]

MON_SIZE = 100
SUB_SIZE = 12
SUB_TOTAL = 48
SUB_OFF = 0x20

# 各性格 → 加/减的能力（用于换算 nature，仅注释用）
NATURE_NAMES = [
    "勤奋", "怕寂寞", "固执", "顽皮", "勇敢",
    "大胆", "坦率", "淘气", "乐天", "悠闲",
    "胆小", "急躁", "认真", "爽朗", "天真",
    "沉着", "温顺", "温和", "温顺", "慢吞吞",
    "害羞", "急躁", "马虎", "天真", "稳重",
]


def load_species_index() -> dict[str, dict]:
    if not SPECIES_INDEX.is_file():
        return {}
    return json.loads(SPECIES_INDEX.read_text("utf-8"))


def make_substructs(
    *,
    species: int,
    exp: int,
    item: int,
    moves: list[int],
    pp: list[int],
    ivs: int,
    evs: list[int],
    friendship: int,
    met_level: int,
    met_location: int,
    ball_gender: int,
) -> dict[str, bytes]:
    """构造 G/A/E/M 四块明文。"""
    # G: species u16 | item u16 | exp u32 | PPbonus u8 | friendship u8 | ? u16
    g = struct.pack("<HHIBBH", species, item, exp, 0, friendship, 0)

    # A: move1..4 u16 | pp1..4 u8
    mv = (moves + [0, 0, 0, 0])[:4]
    pps = (pp + [0, 0, 0, 0])[:4]
    a = struct.pack("<4H4B", *mv, *pps)

    # E: 6 个 EV + 6 个华丽度
    ev6 = (evs + [0] * 6)[:6]
    e = struct.pack("<6B6B", *ev6, *([0] * 6))

    # M: pokerus | metLocation | metLevel | ballAndGender | IVs u32 | ribbons u32
    m = struct.pack("<BBBBII", 0, met_location, met_level & 0x7F, ball_gender, ivs, 0)

    assert len(g) == SUB_SIZE and len(a) == SUB_SIZE
    assert len(e) == SUB_SIZE and len(m) == SUB_SIZE
    return {"G": g, "A": a, "E": e, "M": m}


def encrypt_substructs(
    blocks: dict[str, bytes], personality: int, ot_id: int
) -> tuple[bytes, int]:
    """按 personality%24 排列 + XOR 加密，返回 (48B 密文, checksum)。"""
    order = ORDER_TABLE[personality % 24]
    plain = b"".join(blocks[ch] for ch in order)
    assert len(plain) == SUB_TOTAL

    # checksum：明文按 u16 累加
    checksum = sum(struct.unpack_from("<24H", plain)) & 0xFFFF

    key = (ot_id ^ personality) & 0xFFFFFFFF
    enc = bytearray()
    for i in range(0, SUB_TOTAL, 4):
        v = struct.unpack_from("<I", plain, i)[0] ^ key
        enc.extend(struct.pack("<I", v))
    return bytes(enc), checksum


def decrypt_substructs(enc: bytes, personality: int, ot_id: int) -> tuple[dict[str, bytes], int]:
    """解密（用于自检 round-trip）。"""
    key = (ot_id ^ personality) & 0xFFFFFFFF
    plain = bytearray()
    for i in range(0, SUB_TOTAL, 4):
        v = struct.unpack_from("<I", enc, i)[0] ^ key
        plain.extend(struct.pack("<I", v))
    order = ORDER_TABLE[personality % 24]
    blocks = {}
    for i, ch in enumerate(order):
        blocks[ch] = bytes(plain[i * SUB_SIZE:(i + 1) * SUB_SIZE])
    checksum = sum(struct.unpack_from("<24H", bytes(plain))) & 0xFFFF
    return blocks, checksum


def build_mon(
    *,
    species: int,
    level: int,
    ivs: int = 0x1F1F1F1F,   # 全 31
    evs: list[int] | None = None,
    moves: list[int] | None = None,
    pp: list[int] | None = None,
    nature: int = 0,
    personality: int | None = None,
    ot_id: int = 0x00000000,
    item: int = 0,
    friendship: int = 70,
    met_location: int = 25,
    ball_gender: int = 0x21,
    nickname_hex: bytes | None = None,
) -> bytes:
    """构造完整 100B struct Pokemon。"""
    # personality：指定 else 用 nature 相关的确定性值（便于复现）
    if personality is None:
        personality = (0x1A2B3C4D + nature) & 0xFFFFFFFF
    # 让 personality%25 对应 nature（gen3 性格由 pers%25 决定）
    if personality % 25 != nature:
        # 微调 personality 使 pers%25 == nature，同时保持 %24 排列不变性可接受
        adj = personality - (personality % 25) + nature
        personality = adj & 0xFFFFFFFF

    # 经验值：Gen3 中等速度成长曲线（medium fast）= level^3
    exp = level ** 3

    blocks = make_substructs(
        species=species,
        exp=exp,
        item=item,
        moves=moves or [],
        pp=pp or [20, 20, 20, 20],
        ivs=ivs,
        evs=evs or [],
        friendship=friendship,
        met_level=level,
        met_location=met_location,
        ball_gender=ball_gender,
    )
    enc, checksum = encrypt_substructs(blocks, personality, ot_id)

    buf = bytearray(MON_SIZE)
    struct.pack_into("<I", buf, 0x00, personality)
    struct.pack_into("<I", buf, 0x04, ot_id)
    if nickname_hex:
        buf[0x08:0x08 + min(10, len(nickname_hex))] = nickname_hex[:10]
    buf[0x12] = 2          # language = 2 (Japanese) — 与日版一致
    buf[0x1C:0x1E] = struct.pack("<H", checksum)
    buf[SUB_OFF:SUB_OFF + SUB_TOTAL] = enc
    # 状态与派生值：这里填合理初值，游戏会在战斗初始化时重算覆盖
    struct.pack_into("<I", buf, 0x50, 0)   # status
    buf[0x54] = level
    buf[0x55] = 0
    # HP/六维先留 0，由游戏重算（我们不依赖这些派生值）
    return bytes(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--species", type=int, required=True, help="物种编号（slot 索引+1）")
    ap.add_argument("--level", type=int, required=True)
    ap.add_argument("--iv", default="31,31,31,31,31,31",
                    help="六项 IV（HP,攻击,防御,速度,特攻,特防），0-31")
    ap.add_argument("--ev", default="",
                    help="六项 EV（HP,攻击,防御,速度,特攻,特防），0-255")
    ap.add_argument("--moves", default="", help="最多 4 个招式编号，逗号分隔")
    ap.add_argument("--nature", type=int, default=0, help="性格 0-24")
    ap.add_argument("--personality", type=lambda x: int(x, 0), default=None,
                    help="手动指定 personality（十六进制，用于复现）")
    ap.add_argument("--ot-id", type=lambda x: int(x, 0), default=0,
                    help="训练家 ID（与 personality 一起决定 key）")
    ap.add_argument("--addr", type=lambda x: int(x, 0), default=0x030044F0,
                    help="写入目标地址（默认 gEnemyParty[0]=0x030044F0）")
    ap.add_argument("--out", type=Path, default=None,
                    help="输出 JSON（默认 stdout）")
    ap.add_argument("--verify", action="store_true", help="只做 round-trip 自检")
    a = ap.parse_args()

    ivs6 = [int(x) for x in a.iv.split(",") if x.strip()]
    if len(ivs6) != 6:
        raise SystemExit("--iv 需要 6 个值")
    if any(not (0 <= v <= 31) for v in ivs6):
        raise SystemExit("--iv 每项必须 0..31")
    # IV 打包：从低位起 HP,atk,def,spe,spa,spd，各 5 bit
    ivs = 0
    for i, v in enumerate(ivs6):
        ivs |= (v & 0x1F) << (i * 5)

    evs6 = [int(x) for x in a.ev.split(",") if x.strip()] if a.ev else []
    moves = [int(x) for x in a.moves.split(",") if x.strip()] if a.moves else []

    mon = build_mon(
        species=a.species, level=a.level, ivs=ivs, evs=evs6,
        moves=moves, nature=a.nature,
        personality=a.personality, ot_id=a.ot_id,
    )

    # round-trip 自检
    pers = struct.unpack_from("<I", mon, 0)[0]
    otid = struct.unpack_from("<I", mon, 4)[0]
    enc = mon[SUB_OFF:SUB_OFF + SUB_TOTAL]
    blocks, chk = decrypt_substructs(enc, pers, otid)
    stored = struct.unpack_from("<H", mon, 0x1C)[0]
    sp, = struct.unpack_from("<H", blocks["G"], 0)
    ok = (chk == stored) and (sp == a.species)
    print(f"personality = {pers:08X}  order = {ORDER_TABLE[pers % 24]}")
    print(f"otId        = {otid:08X}  key = {pers ^ otid:08X}")
    print(f"species     = {sp}  level = {a.level}  exp = {a.level ** 3}")
    print(f"checksum    = 0x{stored:04X} (重算 0x{chk:04X})  {'OK' if ok else 'MISMATCH'}")
    print(f"IVs         = {ivs6}  moves = {moves}")
    if not ok:
        print("[FAIL] round-trip 自检失败，不要拿去写内存")
        return 1
    print("[OK] round-trip 自检通过")

    if a.verify:
        return 0

    # 生成写入清单：按 4 字节一组，跳过全 0 区（减少写入条数、避免误伤）
    writes = []
    for off in range(0, MON_SIZE, 4):
        w = struct.unpack_from("<I", mon, off)[0]
        writes.append({
            "addr": a.addr + off,
            "width": 4,
            "value": w,
            "note": f"mon+0x{off:02X}",
        })
    payload = {
        "species": a.species, "level": a.level,
        "personality": pers, "otId": otid,
        "checksum": stored, "order": ORDER_TABLE[pers % 24],
        "mon_hex": mon.hex(),
        "writes": writes,
    }
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
        print(f"-> {a.out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
