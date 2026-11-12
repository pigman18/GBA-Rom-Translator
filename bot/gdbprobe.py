#!/usr/bin/env python3
"""bot/gdbprobe.py — 把 GDB 探针并入 bot（随场景自动起停，2026-11-11）

## 为什么有这个文件

仓库里原来的 GDB 能力是三块，都假设「人已经把 mGBA 开好了」：

| 位置 | 形态 | 问题 |
|---|---|---|
| `src/util/gdb_patcher.py` | `log` 命令，监听点来自 `src/util/configs/{game}.yaml` 的 `gdb:` 列表 | 要人手起 mGBA + Start GDB stub + Pause |
| `src/util/debug_patcher.py` | `GdbClient`（RSP 客户端） | 只是传输层 |
| `scripts/GDB_README.md` | `cmd.txt` / `out.txt` 人工轮询 | 一次一轮对话，慢 |

要复现 bug 时必须「同一场景、同一存档、同一批按键」才有对照价值 —— 手工那套做不到。
所以这里把起模拟器、连 stub、下断点、抓样本、落盘合成一次调用，由 `bot/run.py --gdb`
驱动，和截图跑在同一轮里。

## 契约

- **不改动** bot 的截图 / 判定流程；探针是挂在同一进程旁边的线程。
- 命中数据落 `{side_dir}/gdb_probe.log`，与 `shot` 的五件套（png/vram/pal/io/ram）同目录，
  证据与截图是同一轮跑出来的。
- mGBA 退出后探针线程自行结束，不阻塞 `wait_hidden`。
- 断点、handler 全部来自 yaml（`gdb:` 列表），加监控点不改本文件。

## 用法

    python bot/run.py POKEMON_RUBY_AXVJ00 dex --gdb InitTextPrinter
    python bot/run.py POKEMON_RUBY_AXVJ00 dex --gdb InitTextPrinter,PrintNextChar --gdb-side translated

在代码里：

    with ProbeSession(port=2345, game="POKEMON_RUBY_AXVJ00",
                      functions="InitTextPrinter", out_dir=side_dir,
                      origin=origin_rom_bytes) as probe:
        probe.start()          # 后台线程：等 stub → 下断点 → cont 循环
        ...                    # 这里起 mGBA
        probe.wait(proc)       # mGBA 退出后收尾
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from util.debug_patcher import GdbClient, GdbError          # noqa: E402
from util.gdb_patcher import (                              # noqa: E402
    Ctx,
    generic_log,
    load_charmap,
    load_gdb_points,
    resolve_hooks,
)
import util.gdb_patcher as _gp                             # noqa: E402

DEFAULT_PORT = 2345


class ProbeSession:
    """一次 GDB 探针会话：连 stub、下断点、按命中采样本。"""

    def __init__(
        self,
        out_dir: Path,
        game: str = "POKEMON_RUBY_AXVJ00",
        functions: str = "InitTextPrinter",
        port: int = DEFAULT_PORT,
        host: str = "127.0.0.1",
        origin: Optional[bytes] = None,
        charmap: Optional[str] = None,
        limit: int = 20000,
        attach_timeout: float = 60.0,
        cont_timeout: float = 30.0,
        quiet: bool = True,
        dedup: bool = False,
        watch_addrs: Optional[list[int]] = None,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.logpath = self.out_dir / "gdb_probe.log"
        self.game = game
        self.functions = functions
        self.port = port
        self.host = host
        self.origin = origin
        self.charmap = charmap
        self.limit = limit
        self.attach_timeout = attach_timeout
        self.cont_timeout = cont_timeout
        self.quiet = quiet
        # 分析用：默认**不**去重（去重会把「连着 7 次同样的 print」吞成一行，
        # 而 bug 恰恰常藏在重复里的第 k 次）
        self.dedup = dedup
        # 写 watchpoint（Z2）：用来回答「这个寄存器/字段到底被谁写、写几次」。
        # 静态调不动的问题（比如 BGxCNT 的 charBase 位是不是每帧被重设）
        # 用这一条最快。
        self.watch_addrs = list(watch_addrs or [])
        self.watch_hits: list[tuple[int, int, int]] = []   # (addr, pc, newval)
        # 文本块归属统计：(tileData 地址, textMode, fontNum) -> 次数
        self._tile_blocks: dict[tuple[int, int, int], int] = {}

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._gdb: Optional[GdbClient] = None
        self.hits = 0
        self.errors: list[str] = []
        self.connected = False

    # -- 日志 -------------------------------------------------------------
    def log(self, msg: object = "") -> None:
        line = str(msg)
        with open(self.logpath, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
        if not self.quiet:
            print(f"[gdb] {line}", flush=True)

    # -- 生命周期 ---------------------------------------------------------
    def __enter__(self) -> "ProbeSession":
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def start(self) -> None:
        # 只有 watchpoint、没有监听点时也必须启动（否则 -g 会让 mGBA 一直暂停）
        if not self.functions and not self.watch_addrs:
            return
        self._thread = threading.Thread(target=self._run, name="gdb-probe", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None

    def wait(self, proc=None, timeout: Optional[float] = None) -> None:
        """等 mGBA 退出（或超时）后收尾。proc 为 subprocess.Popen。"""
        deadline = None if timeout is None else time.time() + timeout
        while self._thread is not None and self._thread.is_alive():
            if proc is not None and proc.poll() is not None:
                # mGBA 已经退出：给探针一点时间把 cont 的错误收掉
                time.sleep(0.3)
                break
            if deadline is not None and time.time() > deadline:
                break
            time.sleep(0.2)
        self.stop()

    # -- 内部 -------------------------------------------------------------
    def _attach(self) -> Optional[GdbClient]:
        deadline = time.time() + self.attach_timeout
        last: Optional[Exception] = None
        while time.time() < deadline and not self._stop.is_set():
            gdb = GdbClient(self.host, self.port, timeout=10.0)
            try:
                gdb.connect()
                return gdb
            except (GdbError, OSError) as e:
                last = e
                gdb.close()
                time.sleep(0.25)
        if last is not None:
            self.errors.append(f"attach 失败: {last}")
        return None

    def _run(self) -> None:
        points = load_gdb_points(self.game)
        hooks = resolve_hooks(points, self.functions) if self.functions else []
        if not hooks and not self.watch_addrs:
            self.errors.append(f"既没有监听点也没有 watchpoint: {self.functions!r}")
            self.log("[ERR] 没有任何探针目标")
            return

        gdb = self._attach()
        if gdb is None:
            self.log(f"[ERR] 连不上 GDB stub {self.host}:{self.port}")
            return
        self._gdb = gdb
        self.connected = True

        # 解码表：日版底包按 JP PCS 单字节 + charmap 双字节（F7 00 / F9 00）
        single: dict[int, str] = {}
        try:
            from meowth.jp_pcs import BYTE_TO_CHAR as JP_BYTE_TO_CHAR
            single = dict(JP_BYTE_TO_CHAR)
        except Exception:
            pass
        double: dict[int, str] = {}
        cm = self.charmap or self._pick_charmap(points)
        if cm and os.path.isfile(cm):
            _, double = load_charmap(cm)

        ctx = Ctx(gdb, str(self.logpath), single, double, self.origin,
                  dedup=self.dedup, vram_survey=False)
        # Ctx.log 每次都会重开文件并 print；这里只保留写文件
        if self.quiet:
            def _log(msg: object = "") -> None:
                with open(self.logpath, "a", encoding="utf-8", errors="replace") as f:
                    f.write(str(msg) + "\n")
            ctx.log = _log  # type: ignore[assignment]

        self.log(
            f"\n===== bot gdb probe @ {time.strftime('%H:%M:%S')}"
            f" [{self.game}: {', '.join(h.name for h in hooks)}] ====="
        )

        for wa in self.watch_addrs:
            try:
                r = gdb.cmd(f"Z2,{wa & 0xFFFFFFFF:x},2")
                self.log(f"  watchpoint 0x{wa:08X} 写监视: {r}")
            except (GdbError, OSError) as e:
                self.log(f"[ERR] watchpoint 0x{wa:08X} 失败: {e}")

        armed = []
        for h in hooks:
            try:
                gdb.set_sw_break(h.bp)
                armed.append(h)
                self.log(f"  断点 {h.name} @0x{h.bp:08X} OK")
            except (GdbError, OSError) as e:
                self.log(f"[ERR] 断点 {h.name} @0x{h.bp:08X} 失败: {e}")
        if not armed and not self.watch_addrs:
            gdb.close()
            self.errors.append("所有断点设置失败")
            return
        by_pc = {h.bp: h for h in armed}

        n = 0
        try:
            while n < self.limit and not self._stop.is_set():
                try:
                    stop = gdb.cont(timeout=self.cont_timeout)
                except GdbError as e:
                    msg = str(e)
                    # 场景跑完 mGBA 退出 ⇒ 连接断开，属正常收尾
                    if "断开" in msg or "closed" in msg.lower():
                        break
                    self.log(f"\n[停止] {msg}")
                    break
                except OSError:
                    break
                regs = gdb.read_regs()
                pc = (regs.get("r15", 0) & ~1) & 0xFFFFFFFF

                # watchpoint 停因：记一条「谁写的、写成什么」，不占命中计数
                if isinstance(stop, str) and "watch" in stop:
                    wa = self.watch_addrs[0] if self.watch_addrs else 0
                    try:
                        cur = int.from_bytes(bytes(gdb.read_mem(wa, 2)), "little")
                    except (GdbError, OSError):
                        cur = -1
                    self.watch_hits.append((wa, pc, cur))
                    if len(self.watch_hits) <= 40:
                        self.log(f"\n[WATCH] 0x{wa:08X} <- 0x{cur:04X}  "
                                 f"PC=0x{pc:08X} LR=0x{regs.get('r14', 0) & ~1:08X}")
                        # 栈回溯：BIOS SWI 包装会盖掉真实调用者（LR 只剩 svc 的返回地址），
                        # 所以把 [sp..sp+128] 里像 ROM 代码的地址都打出来。
                        self._log_stack_raw(ctx, gdb, regs)
                    elif len(self.watch_hits) % 200 == 0:
                        self.log(f"  …watch 已命中 {len(self.watch_hits)} 次")
                    continue

                n += 1
                self.hits = n
                hook = by_pc.get(pc)
                if hook is None:
                    self.log(f"\n[{n}] 意外 PC=0x{pc:08X}")
                    continue
                try:
                    generic_log(ctx, hook, regs)
                    if hook.fn is not None:
                        hook.fn(gdb, regs, ctx, hook.point.cfg)
                    self._log_textblock(ctx, gdb, hook, regs)
                    self._log_stack(ctx, gdb, hook, regs)
                except (GdbError, OSError) as e:
                    self.log(f"  handler 读取失败: {e}")
        finally:
            for h in armed:
                try:
                    gdb.clear_sw_break(h.bp)
                except Exception:
                    pass
            try:
                gdb.close()
            except Exception:
                pass
            self.log(f"\n探针结束：命中 {n} 次。日志 {self.logpath}")
            if self._tile_blocks:
                self.log("  文本块归属（tileData / charBlock / tm / fn → 次数）:")
                for (addr, tm, fn), c in sorted(self._tile_blocks.items(),
                                                key=lambda kv: -kv[1]):
                    blk = (addr - 0x06000000) >> 14
                    self.log(f"    0x{addr:08X}  block{blk}  tm={tm} fn={fn}  × {c}")

    def _log_textblock(self, ctx: Ctx, gdb: GdbClient, hook, regs: dict) -> None:
        """记录这个 text printer 的**字形 tile 落在哪块 VRAM**。

        用途（2026-11-11）：判断「文本 char block 能不能独占」。火红的字形放
        独占 block，而 Ruby 这屏是 BG2=block2、BG3=block0 混用。要知道我们的
        12px 渲染器该抢哪一块，必须先把每个场景每个文本窗口的实际 tileData 抓出来。

        数据链路（全是实测字段，别猜）：
            win = r0（InitTextPrinter 的第一个参数）
            win[0x00] = 模板指针（WIN_TEMPLATE，低位可能是 1 需 & ~1）
            模板[0x0C] = **VRAM 地址本身**（TPL_TILE_DATA）→ 0x06008000 / 0x0600C000
            VRAM 地址 → charBlock = (addr - 0x06000000) >> 14
        """
        if hook.name != "InitTextPrinter":
            return
        win = regs.get("r0", 0)
        if not (0x02000000 <= win < 0x04000000):
            return
        try:
            tpl = int.from_bytes(bytes(gdb.read_mem(win + 0x00, 4)), "little") & ~1
            if not (0x02000000 <= tpl < 0x0A000000):
                return
            addr = int.from_bytes(bytes(gdb.read_mem(tpl + 0x0C, 4)), "little")
        except (GdbError, OSError):
            return
        if not (0x06000000 <= addr < 0x06018000):
            return
        blk = (addr - 0x06000000) >> 14
        # 顺手把 textMode/fontNum 带上：两者决定走哪条渲染路径
        try:
            tm = bytes(gdb.read_mem(win + 0x0A, 1))[0]
            fn = bytes(gdb.read_mem(win + 0x0B, 1))[0]
        except (GdbError, OSError):
            tm = fn = 0
        key = (addr, tm, fn)
        self._tile_blocks[key] = self._tile_blocks.get(key, 0) + 1
        if self._tile_blocks[key] <= 3:
            ctx.log(f"  文本块: tileData=0x{addr:08X} (charBlock {blk}) "
                    f"tm={tm} fn={fn}")

    def _log_stack_raw(self, ctx: Ctx, gdb: GdbClient, regs: dict) -> None:
        """watchpoint 命中时回溯调用链（不需要 hook 对象）。

        为什么单独写一个：BIOS 的 LZ77 解压走 `svc`，停下来的 LR 只是
        `svc` 包装里的返回地址（`0x081B129A`），真实调用者在更上层。
        只能扫栈找 ROM 代码地址。
        """
        sp = regs.get("r13", 0)
        if not (0x02000000 <= sp < 0x04000000):
            return
        try:
            raw = bytes(gdb.read_mem(sp, 160))
        except (GdbError, OSError):
            return
        if len(raw) < 160:
            return
        words = []
        for i in range(0, 160, 4):
            v = int.from_bytes(raw[i:i + 4], "little")
            if 0x08000000 <= v < 0x0A000000:
                words.append(f"+{i:02X}=0x{v & ~1:08X}")
        if words:
            ctx.log("  栈回溯: " + " ".join(words))

    def _log_stack(self, ctx: Ctx, gdb: GdbClient, hook, regs: dict) -> None:
        """把栈上「看起来像 ROM 代码地址」的字标出来 —— 这就是调用链。

        为什么需要：`InitTextPrinter`（0x08002C68）只有一层 LR，而它上面的
        `AddTextPrinterParameterized`（0x08002CFC，`push {r4,lr}; sub sp,#4`）
        被**多处**调用，LR 永远是 0x08002D14。要区分「谁传的这个 x」，
        只能看 parameterized 压栈的返回地址 = `[sp+8]`。

        实测（2026-11-11）：图鉴列表的编号/名字/破折号三次 print 都从同一个
        包装进来，但 x 不同（19 / 22 或 23），差异只在更上一层。
        """
        sp = regs.get("r13", 0)
        if not (0x02000000 <= sp < 0x04000000):
            return
        try:
            raw = bytes(gdb.read_mem(sp, 128))
        except (GdbError, OSError):
            return
        if len(raw) < 128:
            return
        words = []
        for i in range(0, 128, 4):
            v = int.from_bytes(raw[i:i + 4], "little")
            if 0x08000000 <= v < 0x0A000000:
                words.append(f"+{i:02X}=0x{v:08X}")
        if words:
            ctx.log(f"  栈@0x{sp:08X} 代码地址: " + " ".join(words))

    @staticmethod
    def _pick_charmap(points) -> str:
        for p in points:
            c = (p.cfg or {}).get("charmap")
            if c:
                return str((ROOT / str(c)).resolve())
        return ""


def load_origin(game: str) -> Optional[bytes]:
    p = ROOT / "roms" / "origin" / f"{game}.gba"
    if p.is_file():
        return p.read_bytes()
    return None
