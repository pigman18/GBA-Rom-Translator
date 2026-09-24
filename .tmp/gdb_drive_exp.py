"""gdb_drive_exp.py —— gdb(Python) 版输入驱动 + TILE_BASE 劫持。

在同一个 gdb 会话里做两件事（stub 只认一条连接，所以必须合并）：

  1. 断点 A `0x0800042C`（ReadKeys 入口，块起点）
     —— 按**墙钟**把当前该按的键写进 `KEYS_ADDR`。
        池字 `0x08000468` 已在 .gdb 前置脚本里改成指向 KEYS_ADDR。

  2. 断点 B `0x08800084`（InitTextPrinter_hook_C +4，唯一可靠的命中断点）
     —— 读 r0(=win)，给每个**不同的 win 实例**分配一个**不同的** TILE_BASE，
        写进 r1。因为 hook_C 在门控不过时直接 `return tile_base`，
        改 r1 == 改最终写进 win[0x16] 的值。

目的：在**原盘 ROM**（无我们的 hook）上验证「每窗口唯一 TILE_BASE」
能否让设置页这类「同屏多个文本块」的界面不再互相覆盖。

配置来自同目录 gdb_exp.json：
  schedule: [[start_sec, end_sec, keymask], ...]
  end_sec : 停止时刻（秒）
  dumps   : [[path, lo, hi], ...]  结束时 dump 的内存块
"""
import gdb
import json
import time

CFG_PATH = r"C:\code\GBA-Rom-Translator\.tmp\gdb_exp.json"
KEYS_ADDR = 0x08900000
NO_KEY = 0x3FF

with open(CFG_PATH, "r", encoding="utf-8") as fh:
    CFG = json.load(fh)

SCHED = CFG["schedule"]
END_SEC = CFG["end_sec"]
DUMPS = CFG.get("dumps", [])
HACK_BASE = CFG.get("hack_base", 0)          # 0 = 不劫持 TILE_BASE
BASE_STEP = CFG.get("base_step", 128)

t0 = [None]
state = {"done": False, "ticks": 0, "inits": 0}
bases = {}
order = []


def log(msg):
    gdb.write("[exp] %s\n" % msg)


class TickBP(gdb.Breakpoint):
    """按墙钟喂键；到点则 dump 并结束。"""

    def stop(self):
        if state["done"]:
            return True
        now = time.time()
        if t0[0] is None:
            t0[0] = now
        el = now - t0[0]
        state["ticks"] += 1

        if el >= END_SEC:
            state["done"] = True
            log("END at %.1fs ticks=%d inits=%d" % (el, state["ticks"], state["inits"]))
            log("distinct wins=%d bases=%s" % (len(bases), sorted(set(bases.values()))))
            for path, lo, hi in DUMPS:
                try:
                    gdb.execute("dump binary memory %s 0x%X 0x%X" % (path, lo, hi),
                                to_string=True)
                except Exception as exc:            # noqa: BLE001
                    log("dump failed %s: %s" % (path, exc))
            log("DUMPS_DONE")
            return True

        kv = NO_KEY
        for a, b, v in SCHED:
            if a <= el <= b:
                kv = v
                break
        try:
            gdb.execute("set {unsigned short}0x%X = %d" % (KEYS_ADDR, kv),
                        to_string=True)
        except Exception:                            # noqa: BLE001
            pass
        return False


class InitTPBP(gdb.Breakpoint):
    """给每个 win 实例分配唯一的 TILE_BASE。"""

    def stop(self):
        if not HACK_BASE:
            return False
        try:
            win = int(gdb.parse_and_eval("$r0")) & 0xFFFFFFFF
            old = int(gdb.parse_and_eval("$r1")) & 0xFFFF
        except Exception:                            # noqa: BLE001
            return False

        if win not in bases:
            idx = len(bases)
            bases[win] = HACK_BASE + idx * BASE_STEP
            order.append(win)
            log("win 0x%08X old_base=0x%X -> new_base=%d (#%d)"
                % (win, old, bases[win], idx))
        state["inits"] += 1
        try:
            gdb.execute("set $r1 = %d" % bases[win], to_string=True)
        except Exception:                            # noqa: BLE001
            pass
        return False


TickBP("*0x0800042C", internal=False)
if HACK_BASE:
    InitTPBP("*0x08800084", internal=False)
    log("TILE_BASE hack ON, base0=%d step=%d" % (HACK_BASE, BASE_STEP))
else:
    log("TILE_BASE hack OFF (control run)")

log("GO")
