#!/usr/bin/env python3
"""bot/run.py — 双 ROM 场景采集驱动（从零重写 2026-10-06）

契约（用户口径）：
  1) 场景脚本 bot/scenes/{gameId}/{scene}.lua，经 main.lua 执行
  2) 截图落 work/{gameId}/bot/{scene}/{时间}/{origin|translated}/{number}.png
  3) 两侧使用**同一份 .sav**，且**不是即时存档**（savestate 基于内存，
     会让 hook 改动不被加载，验收失真）
  4) 采集后由 verify.py 对比截图判：已汉化 + 无撞 UI + 无乱码
  5) 像素级判据：origin 中不存在的字形像素出现在 translated ⇒ 判乱码

用法：
  python bot/run.py <gameId> <scene> [--save PATH] [--origin X] [--translated Y]
                                    [--verify] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # 仓库根
BOT = Path(__file__).resolve().parent              # bot/
sys.path.insert(0, str(BOT))

# 日志里有 ⇒ ★ 这类非 GBK 字符；Windows 控制台默认 GBK 会让 print 直接抛
# UnicodeEncodeError 把整个 run 打断（实测踩过）。统一改 UTF-8 + replace。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from winhide import popen_hidden, wait_hidden      # noqa: E402

sys.path.insert(0, str(BOT / "tools"))
try:
    from savlib import rebuild as sav_rebuild, parse_position   # noqa: E402
except ImportError:                                             # pragma: no cover
    sav_rebuild = None
    parse_position = None


def save_identity(sav_path: Path):
    """从 .sav 解出「存档身份」与游戏内位置。

    身份 = SaveBlock2 开头的 8 字节（玩家名 + 0xFF 填充）。
    它被传给 bot.lua，在 EWRAM 里做**原样字节搜索**：
      命中 ⇒ 这份存档确实被游戏加载进内存了（读档成功）。
      未命中 ⇒ 只是「文件哈希相同」，游戏其实在新开局 —— 明确报错。
    返回 (ident_hex, pos_dict)；解析失败返回 (None, None)。
    """
    if sav_rebuild is None:
        return None, None
    try:
        logical, _info = sav_rebuild(sav_path.read_bytes())
    except Exception:
        return None, None
    if logical is None:
        return None, None
    return logical[0:8].hex(" "), parse_position(logical)


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def shoots_root(game: str) -> Path:
    """场景截图根目录：work/{gameId}/bot/{scene}/{stamp}/{origin|translated}/

    2026-11-02 由 bot/shoots 迁到 work/{gameId}/bot，与流水线产物同域
    （work/{gameId}/ 下已有 build/、graphic/、translate.build.json），
    一次清理只丢一个 work 目录。
    """
    return ROOT / "work" / game / "bot"


def find_mgba() -> Path | None:
    # 1) 开发版（bot 首选，带 Lua 脚本支持）
    search_roots = [
        ROOT / "tools" / "mgba_dev",
        # sibling checkout used during Rom-Translator bootstrap
        ROOT.parent / "GBA-Rom-Translator" / "tools" / "mgba_dev",
    ]
    for base in search_roots:
        if base.is_dir():
            cands = sorted(base.glob("mGBA-build-*/mGBA.exe"))
            if cands:
                return cands[-1]
    # 2) 发行版（无 --script，不能跑 bot；仅作最后回落）
    cands = sorted((ROOT / "tools").glob("mGBA-*/mGBA.exe"))
    if cands:
        return cands[-1]
    return None


def scene_default_save(game: str, scene: str):
    """场景自带的默认存档（bot/scenes/{game}/saves/scene_saves.json）。

    ★ 为什么需要：不同场景对起点地图有硬要求 ——
      野外场景要 Route118，对话场景必须**室内**（野外草丛按 A 会触发野生
      遭遇，RNG 会让两侧分岔，对照直接失效）。
      把「场景 → 存档」写进仓库，回归时就不用每次记 --save 用哪一份。
    """
    p = BOT / "scenes" / game / "saves" / "scene_saves.json"
    if not p.is_file():
        return None
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    fn = (m.get("scenes") or {}).get(scene)
    if not fn:
        return None
    q = p.parent / fn
    return q if q.is_file() else None


def resolve_shared_save(args, original: Path, translated: Path):
    """两侧必须用同一份 .sav。返回 (path, sha256, ident_hex, pos_dict)。

    1) --save 显式指定 ⇒ 用它
    2) 场景自带默认存档（scene_saves.json）⇒ 用它
    3) 否则按各自 ROM 推导同名 .sav；**内容不同则直接报错拒绝运行**
    """
    if args.save:
        p = Path(args.save)
        if not p.is_file():
            raise SystemExit(f"[ERR] --save 指定的存档不存在: {p}")
        ident, pos = save_identity(p)
        return p, file_hash(p), ident, pos

    default = scene_default_save(args.gameId, args.scene)
    if default is not None:
        print(f"[bot] 使用场景默认存档: {default.name}")
        ident, pos = save_identity(default)
        return default, file_hash(default), ident, pos

    o_sav = original.with_suffix(".sav")
    t_sav = translated.with_suffix(".sav")
    o_ok, t_ok = o_sav.is_file(), t_sav.is_file()

    if o_ok and t_ok:
        ho, ht = file_hash(o_sav), file_hash(t_sav)
        if ho != ht:
            raise SystemExit(
                f"[ERR] 两侧同名 .sav 内容不同，无法证明同一场景。\n"
                f"      origin     {o_sav} sha256={ho[:12]}\n"
                f"      translated {t_sav} sha256={ht[:12]}\n"
                f"      请用 --save <同一份.sav> 重新采集")
        ident, pos = save_identity(o_sav)
        return o_sav, ho, ident, pos
    if o_ok or t_ok:
        raise SystemExit("[ERR] 只有一侧有 .sav，无法证明同一场景；请用 --save")
    print("[bot] 警告：两侧均无 .sav（全新开局），无法证明同一场景")
    return None, None, None, None


def prepare_rom(src: Path, workdir: Path, shared_save: Path | None):
    """把 ROM（和共用的 .sav）复制进本侧独立目录，互不污染。

    ★ 存档尺寸必须对齐到 mGBA 认的规格，否则**静默不加载**（游戏从冷启动跑，
      看起来像"按键没用"，实测表现为「一直停在标题/开场」）。
      GBA flash 存档 = **131072 字节（128KB）**；
      实测 road.sav 是 131088 字节（多 16 字节元数据）⇒ 必须裁掉。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    staged = workdir / "run.gba"
    shutil.copyfile(src, staged)

    save_sha = None
    if shared_save is not None:
        raw = shared_save.read_bytes()
        FLASH = 131072                      # 128KB，GBA flash 标准尺寸

        if len(raw) > FLASH:
            # 常见情形：工具写了 16 字节头 ⇒ 去掉尾部多余（元数据通常在末尾）
            raw = raw[:FLASH]
        elif len(raw) < FLASH:
            raw = raw + bytes(FLASH - len(raw))

        dst = workdir / "run.sav"
        dst.write_bytes(raw)
        save_sha = file_hash(dst)
        print(f"[bot] 存档已对齐: {shared_save.name} "
              f"{shared_save.stat().st_size}B -> {len(raw)}B")

    return staged, save_sha


def run_side(side, source, output_dir, scene, game, mgba,
             ident_hex=None, pos_desc=None, timeout=900,
             gdb_points=None, gdb_port=2345, gdb_timeout=90.0, gdb_watch=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        BOT_ROOT=str(BOT),
        BOT_GAME_ID=game,
        BOT_SCENE=scene,
        BOT_SIDE=side,
        BOT_OUTPUT=str(output_dir),
        BOT_SAV_PROOF=ident_hex or "",
        BOT_SAV_POS=pos_desc or "",
    )
    entry = BOT / "scenes" / game / "main.lua"
    # 静音：命令行覆盖优先于 config.ini。volume=0 是兜底 —— 个别版本 mute 只在
    # 音频设备初始化时读一次，被 -C 覆盖后仍会按 volume 出声。
    command = [str(mgba), "--script", str(entry),
               "-C", "fpsTarget=600",
               "-C", "mute=1",
               "-C", "volume=0",
               "-C", "audioSync=0"]
    if gdb_points or gdb_watch:
        # -g：启动即开 GDB stub 并**暂停**等连接（mGBA 语义），
        # 所以探针线程必须马上连上并 cont，否则 Lua 脚本一帧都推不动。
        # ★ `-g` 在 mGBA 里是**无参数开关**（`-g, --gdb  Start GDB session
        #  (default port 2345)`）。写成 `-g 2345` 会把 "2345" 当成 ROM 路径，
        # mGBA 直接报错退出、stub 根本没起来（2026-11-11 实测踩过）。
        command += ["-g"]
        if gdb_port != 2345:
            command += ["-C", f"gdb.port={gdb_port}"]
    command.append(str(source))
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    print(f"[bot] {side}: {source} -> {output_dir}", flush=True)

    probe = None
    if gdb_points or gdb_watch:
        from gdbprobe import ProbeSession, load_origin
        probe = ProbeSession(
            out_dir=output_dir,
            game=game,
            functions=gdb_points or "",
            port=gdb_port,
            origin=load_origin(game),
            watch_addrs=gdb_watch,
        )

    proc = popen_hidden(command, cwd=str(output_dir), env=env)
    if probe is not None:
        probe.start()
        print(f"[bot] {side} GDB 探针: {gdb_points} @127.0.0.1:{gdb_port}"
              f" -> {output_dir / 'gdb_probe.log'}", flush=True)
    try:
        rc = wait_hidden(proc, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        if probe is not None:
            probe.stop()
        raise SystemExit(f"[ERR] {side} emulator timeout ({timeout}s)")
    if probe is not None:
        # mGBA 已退出：给探针把最后一条 cont 的错误收掉，再确认它真的连上过
        probe.wait(proc, timeout=gdb_timeout)
        if not probe.connected:
            detail = "；".join(probe.errors) or "(无错误信息)"
            raise SystemExit(
                f"[ERR] {side} GDB 探针没连上 stub（因此这一侧没有跑起来）：{detail}")
        print(f"[bot] {side} GDB 命中 {probe.hits} 次 -> {output_dir / 'gdb_probe.log'}",
              flush=True)

    log = output_dir / "scene.log"
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""

    # ── Lua 脚本失败识别（2026-11-05 新增）───────────────────────────────
    # 存在理由：`emu_run.py` 那套三层校验是给研究脚本用的，bot 这边只查
    # "done f="。实测踩过的坑：
    #   · mGBA 的 emu:exit/stop/pause 在这个版本里是 nil，脚本报错后**进程
    #     不会自己退出**，只能靠外部超时终止 —— 于是「跑到超时」和「正常
    #     跑完」在返回码上分不出来；
    #   · 脚本 xpcall 捕获到错误后仍可能写出部分截图，目录非空 ⇒ 不能只看
    #     「有没有 png」。
    # 所以这里做三重显式判据，任一命中就报错退出，不静默继续。
    lua_err = [l.strip() for l in text.splitlines()
               if re.search(r"\[ERR\]|\[LUA-ERROR\]|xpcall|attempt to (call|index)",
                            l, re.I)]
    if lua_err:
        raise SystemExit(
            f"[ERR] {side} Lua 脚本报错（{len(lua_err)} 行）：\n      "
            + "\n      ".join(lua_err[:5]))

    if "done f=" not in text:
        tail = "\n".join(text.splitlines()[-6:])
        raise SystemExit(f"[ERR] {side} did not finish (rc={rc})\n{tail}")

    # 截图数校验：manifest 尚未生成，这里先按 index.csv 行数比
    idx = output_dir / "index.csv"
    n_shots = len([p for p in output_dir.glob("*.png")])
    n_index = 0
    if idx.is_file():
        n_index = sum(1 for l in idx.read_text(encoding="utf-8", errors="replace")
                      .splitlines() if l.split(",")[0:1] and l.split(",")[0].isdigit())
    if n_index and n_shots < n_index:
        raise SystemExit(
            f"[ERR] {side} 截图缺失：index.csv 记了 {n_index} 步，"
            f"目录里只有 {n_shots} 张 png（脚本中途失败）")

    # ── 读档证明：没有它，这一侧的每一张截图都是可疑的 ──────────────────
    if ident_hex:
        if "[PROVE] OK" in text:
            line = next((l for l in text.splitlines() if "[PROVE] OK" in l), "")
            print(f"[bot] {side} 读档证明通过: {line.strip()}")
        else:
            reason = next((l for l in text.splitlines() if "[PROVE]" in l),
                          "(scene.log 里没有 [PROVE] 记录 —— 场景脚本没调用 prove())")
            raise SystemExit(
                f"[ERR] {side} 读档证明失败：存档没有被游戏加载，"
                f"本侧对照无效。\n      {reason.strip()}")

    # ── settle 超时统计：超时的截图是过渡帧，不应作为验收依据 ─────────────
    to = sum(1 for l in text.splitlines() if "[SETTLE] TIMEOUT" in l)
    if to:
        print(f"[bot] {side} 警告：{to} 次 settle 超时（画面持续变化，按超时继续）")
    return rc


def read_side(folder: Path):
    """读一侧的 index.csv（列名固定）。"""
    p = folder / "index.csv"
    if not p.is_file():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(",")
        if len(parts) < 9 or not parts[0].isdigit():
            continue
        out[int(parts[0])] = {"frame": int(parts[1]), "name": parts[2]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("gameId")
    ap.add_argument("scene")
    ap.add_argument("--origin")
    ap.add_argument("--translated")
    ap.add_argument("--save", help="两侧共用的 .sav 路径（非即时存档）")
    ap.add_argument("--mgba")
    ap.add_argument("--verify", action="store_true",
                    help="[旧行为] 采集后跑 verify.py；现在默认就会跑，保留此参数仅为兼容")
    ap.add_argument("--no-verify", action="store_true",
                    help="采集后跳过 verify.py（默认会跑并写出 verdict.json）")
    ap.add_argument("--check", action="store_true", help="只校验输入，不起模拟器")
    ap.add_argument("--no-prove", action="store_true",
                    help="跳过读档证明闸门（仅用于不采集对照的诊断场景）")
    ap.add_argument("--timeout", type=int, default=900,
                    help="单侧模拟器超时（秒）")
    ap.add_argument("--gdb", dest="gdb_points", default=None, metavar="点[,点]",
                    help="同时跑 GDB 探针：逗号分隔的监听点名（须在 "
                         "src/util/configs/{game}.yaml 的 gdb: 里定义，"
                         "如 InitTextPrinter）。起 mGBA 时自动加 -g 并由 "
                         "bot/gdbprobe.py 连上，命中落 {side}/gdb_probe.log")
    ap.add_argument("--gdb-port", type=int, default=2345,
                    help="GDB stub 端口（默认 2345，两侧串行复用）")
    ap.add_argument("--gdb-watch", default=None, metavar="ADDR[,ADDR]",
                    help="对这些地址下写 watchpoint（Z2），记录「谁写的、写成什么」。"
                         "用来确认寄存器/字段是否每帧被重设，例如 BG2CNT=0x0400000A")
    ap.add_argument("--gdb-side", choices=["origin", "translated", "both"],
                    default="both", help="只在某一侧跑 GDB 探针（默认 both）")
    args = ap.parse_args()

    game, scene = args.gameId, args.scene
    for v in (game, scene):
        if not all(c.isalnum() or c in "_-" for c in v):
            raise SystemExit(f"[ERR] 非法标识符: {v}")

    original = Path(args.origin) if args.origin else ROOT / "roms" / "origin" / f"{game}.gba"
    if args.translated:
        translated = Path(args.translated)
    else:
        primary = ROOT / "roms" / "outputs" / f"{game}_translated.gba"
        alt = ROOT / "roms" / "outputs" / f"{game}_translated_new.gba"
        cands = [p for p in (primary, alt) if p.is_file()]
        translated = (
            max(cands, key=lambda p: p.stat().st_mtime) if cands else primary
        )
    scene_script = BOT / "scenes" / game / f"{scene}.lua"
    entry = BOT / "scenes" / game / "main.lua"
    mgba = Path(args.mgba) if args.mgba else find_mgba()

    if not original.is_file():
        raise SystemExit(f"[ERR] origin ROM 不存在: {original}")
    if not translated.is_file():
        raise SystemExit(f"[ERR] translated ROM 不存在: {translated}")
    if not scene_script.is_file():
        raise SystemExit(f"[ERR] 场景脚本不存在: {scene_script}")
    if not entry.is_file():
        raise SystemExit(f"[ERR] 入口不存在: {entry}")
    if mgba is None or not mgba.is_file():
        raise SystemExit("[ERR] 未找到 mGBA.exe（tools/mgba_dev/mGBA-build-*/）")

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    run_dir = shoots_root(game) / scene / stamp
    shared_save, shared_sha, ident_hex, pos = resolve_shared_save(
        args, original, translated)
    pos_desc = None
    if pos:
        pos_desc = f"{pos['map_name']}:{pos['x']}:{pos['y']}"

    if args.check:
        print(f"[check] origin     : {original}")
        print(f"[check] translated : {translated}")
        print(f"[check] scene      : {scene_script}")
        print(f"[check] entry      : {entry}")
        print(f"[check] mGBA       : {mgba}")
        print(f"[check] 输出目录   : {run_dir}")
        if shared_save:
            print(f"[check] shared sav : {shared_save} sha256={shared_sha[:16]}")
        if ident_hex:
            print(f"[check] 存档身份   : {ident_hex}  （用于读档证明）")
        if pos_desc:
            print(f"[check] 存档位置   : {pos_desc}")
        return 0

    manifest = {
        "schema": 3,
        "gameId": game,
        "scene": scene,
        "timestamp": stamp,
        "scene_script": str(scene_script),
        "contract": {
            "root": str(shoots_root(game)),
            "pattern": "work/{gameId}/bot/{scene}/{YYYYmmddTHHMMSS_ffffff}"
                       "/{origin|translated}/{NNN}.png",
            "number": "场景步骤序号，001 起，两侧同号为一对",
            "timing": "状态驱动：每步之后等画面连续 K 帧不变（settle）才推进",
        },
        # schema 3 起：ram.bin 改为全量内存，布局必须由这里声明，
        # 不能再靠约定俗成（schema 2 的 ram.bin 是
        # EWRAM 0x02020000+0x20000 | IWRAM+0x800，共 133120 字节）。
        "dumps": {
            "vram": {"addr": "0x06000000", "len": 0x18000},
            "pal": {"addr": "0x05000000", "len": 0x400},
            "io": {"addr": "0x04000000", "len": 0x60},
            "oam": {"addr": "0x07000000", "len": 0x400},
            "ram": [
                {"addr": "0x02000000", "len": 0x40000, "name": "EWRAM"},
                {"addr": "0x03000000", "len": 0x8000, "name": "IWRAM"},
            ],
            "ram_note": "ram.bin = 上面 ram 数组按顺序拼接，共 294912 字节",
        },
        "shared_save": {
            "path": str(shared_save) if shared_save else None,
            "sha256": shared_sha,
            "identity_hex": ident_hex,
            "position": pos_desc,
            "note": "同一份 .sav 复制到两侧，非即时存档；"
                    "identity_hex 在 EWRAM 里被搜索以证明存档确实被加载",
        },
        "roms": {},
        "pairs": [],
    }

    for side, src in (("origin", original), ("translated", translated)):
        side_dir = run_dir / side
        # ★ 暂存目录**必须落在仓库内**，不能用系统临时目录：
        #   mGBA 会检测「ROM 来自临时目录」并弹模态框
        #   （"Temporary file loaded … Would you like to copy the ROM…"），
        #   模态框一出，Lua 脚本就再也推不动，采集直接死在那里。
        tmp = ROOT / "bot" / ".stage" / f"{side}_{stamp}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            staged, save_sha = prepare_rom(src, tmp, shared_save)
            run_side(side, staged, side_dir, scene, game, mgba,
                     ident_hex=None if args.no_prove else ident_hex,
                     pos_desc=pos_desc,
                     timeout=args.timeout,
                     gdb_points=((args.gdb_points or "") or None)
                                 if args.gdb_side in ("both", side) else None,
                     gdb_watch=([int(x, 16) for x in args.gdb_watch.split(",") if x.strip()]
                                if (args.gdb_watch and args.gdb_side in ("both", side))
                                else None),
                     gdb_port=args.gdb_port,
                     gdb_timeout=max(60.0, float(args.timeout) / 4))
            manifest["roms"][side] = {
                "path": str(src), "sha256": file_hash(src),
                "save_sha256": save_sha,
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    o_idx = read_side(run_dir / "origin")
    t_idx = read_side(run_dir / "translated")
    for seq in sorted(set(o_idx) & set(t_idx)):
        manifest["pairs"].append({
            "number": seq,
            "scene_step": t_idx[seq].get("name") or o_idx[seq].get("name"),
            "origin_frame": o_idx[seq].get("frame"),
            "translated_frame": t_idx[seq].get("frame"),
            "origin": f"origin/{seq:03d}.png",
            "translated": f"translated/{seq:03d}.png",
        })
    manifest["status"] = "captured"

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(manifest["pairs"])
    print(f"[bot] {n} frame-aligned pairs: {run_dir / 'manifest.json'}")
    if n == 0:
        return 1

    # 默认就验收。历史上 --verify 是可选的，结果实际运行的批次大多没带它，
    # 采集了大量截图却没有 verdict —— 验收数据存在但从未被使用。
    # 用 --no-verify 显式跳过。
    if args.no_verify:
        print("[bot] verify SKIPPED (--no-verify)")
        return 0
    return subprocess.call([sys.executable, "-X", "utf8",
                            str(BOT / "verify.py"), str(run_dir)])


if __name__ == "__main__":
    raise SystemExit(main())
