#!/usr/bin/env python3
"""emu_run.py — mGBA + Lua 脚本的「可信执行」包装器 v2。

═══════════════════════════════════════════════════════════════════════════
【为什么需要它（2026-11-04 真实事故）】
═══════════════════════════════════════════════════════════════════════════
  · Lua 脚本刷出几百行「attempt to use a closed file」
  · mGBA 把这些错误打在**自己的脚本窗口**里，不进 stdout/stderr
  · Python 侧 subprocess 看到 **exit code 0**，就当「执行成功」

⇒ 采集脚本死了、只出一半文件、甚至零文件，全被当成功。
   这是验证流程里最危险的一类失败：**静默无效**。

═══════════════════════════════════════════════════════════════════════════
【mGBA Lua API 实测（必须遵守，否则脚本静默半死）】
═══════════════════════════════════════════════════════════════════════════
  存在: emu:reset  emu:screenshot  emu:read8/16/32  emu:readRange
        emu:setKeys  emu:currentFrame
  不存在: emu:exit   emu:stop   emu:pause       ← 调用会抛 nil 错误！
        （实测 mGBA-build-2026-10-19-win64）

  所以「跑完就退出」只能在 Python 侧 terminate 进程，
  Lua 侧靠 DS_DONE() 写完成标记 + 停止 callback。

═══════════════════════════════════════════════════════════════════════════
【三层防线】
═══════════════════════════════════════════════════════════════════════════
 L1  Lua：每个 callback 用 xpcall 包住（WRAP），出错写 `[LUA-ERR]`。
     正常收尾写 `[DONE] f=<帧> code=<0|1> reason=<...> errs=<n>`。
 L2  Python：mGBA 的 stdout/stderr 全部落盘。
 L3  校验（任一不满足即 FAIL）：
     ① _run.log 存在且非空
     ② 无错误指纹（[LUA-ERR] / attempt to / closed file / traceback）
     ③ 有 [DONE] 且 code=0
     ④ 帧数 >= min_frames
     ⑤ expect_files 逐个存在且非空
     ⑥ 产出 mtime 落在本次运行窗口内（防旧文件）
     ⑦ 进程死亡但无 [DONE] ⇒ 判为崩溃（不是超时）

── 用法 ───────────────────────────────────────────────────────────────────
    from emu_run import run_lua
    r = run_lua(lua_text, out_dir, expect_files=["d1.png"], min_frames=600)
    print(r.report())
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROM_ZH = ROOT / "roms" / "translated" / "宝可梦火红日版汉化2.2.gba"
ROM_JA = ROOT / "roms" / "origin" / "POKEMON_FIRE_BPRJ00.gba"
SAVE_FR = ROOT / "bot" / "scenes" / "POKEMON_FIRE_BPRJ00" / "saves" / "firered_zh.sav"

ERROR_MARKERS = (
    "[LUA-ERR]",
    "[ERROR]",
    "attempt to",
    "closed file",
    "stack traceback",
)


LUA_PRELUDE = r'''
-- ===== emu_run 注入的前置（勿删）=====
local OUT = assert(os.getenv("EMU_OUT"), "EMU_OUT missing")

RUN = { f = 0, done = false, code = 1, reason = "not-started", errs = 0 }
RUNLOG = {}

local function _open()
    local ok, f = pcall(io.open, OUT .. "/_run.log", "a")
    if ok then return f end
    return nil
end

function RL(s)
    local f = _open()
    if not f then return end
    pcall(function() f:write(s .. "\n"); f:flush() end)
    pcall(function() f:close() end)
end

-- 把一次 callback 包起来：抛错就记 [LUA-ERR]，绝不静默
function WRAP(name, fn)
    return function(...)
        if RUN.done then return end
        local ok, err = xpcall(fn, function(e)
            local tb = ""
            if debug and debug.traceback then
                local o, t = pcall(debug.traceback, "")
                if o then tb = "\n" .. tostring(t) end
            end
            return tostring(e) .. tb
        end, ...)
        if not ok then
            RUN.errs = RUN.errs + 1
            if RUN.errs <= 15 then
                RL("[LUA-ERR] " .. name .. ": " .. tostring(err))
            elseif RUN.errs == 16 then
                RL("[LUA-ERR] (后续同类错误已折叠)")
            end
        end
    end
end

-- 正常收尾：写 [DONE] 并置 done 标志，之后的 callback 全部空转
function DS_DONE(code, reason)
    if RUN.done then return end
    RUN.code = (code or 0)
    if RUN.errs > 0 and RUN.code == 0 then RUN.code = 1 end
    RUN.reason = reason or "ok"
    RUN.done = true
    RL(string.format("[DONE] f=%d code=%d reason=%s errs=%d",
                     RUN.f, RUN.code, tostring(RUN.reason), RUN.errs))
end
-- ===== 前置结束 =====
'''


def find_mgba() -> Path | None:
    base = ROOT / "tools" / "mgba_dev"
    if base.is_dir():
        c = sorted(base.glob("mGBA-build-*/mGBA.exe"))
        if c:
            return c[0]
    c = sorted((ROOT / "tools").glob("mGBA-*/mGBA.exe"))
    return c[0] if c else None


@dataclass
class Result:
    ok: bool = False
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    log_text: str = ""
    mgba_out: str = ""
    elapsed: float = 0.0

    def report(self) -> str:
        lines = [f"[emu_run] {'PASS' if self.ok else '**FAIL**'}  "
                 f"({self.elapsed:.1f}s)"]
        for r in self.reasons:
            lines.append(f"  x {r}")
        for n in self.notes:
            lines.append(f"  . {n}")
        return "\n".join(lines)


def run_lua(lua_text: str,
            out_dir: Path,
            expect_files: list[str] | None = None,
            min_frames: int = 0,
            rom: Path | None = None,
            save: Path | None = None,
            timeout: int = 900,
            extra_env: dict[str, str] | None = None,
            require_done: bool = True,
            clean: bool = True) -> Result:
    t0 = time.time()
    res = Result()
    mgba = find_mgba()
    if mgba is None:
        res.reasons.append("找不到 mGBA.exe（tools/mgba_dev/mGBA-build-*/）")
        return res

    out_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for f in list(out_dir.glob("*")):
            if f.is_file():
                f.unlink()

    rw = time.time()

    lua_path = out_dir / "_scene.lua"
    lua_path.write_text(LUA_PRELUDE + "\n" + lua_text, encoding="utf-8")

    rom = rom or ROM_ZH
    rom_copy = out_dir / (rom.stem + ".gba")
    shutil.copy2(rom, rom_copy)
    if save is not None and Path(save).exists():
        shutil.copy2(save, out_dir / (rom.stem + ".sav"))

    env = dict(os.environ)
    env["EMU_OUT"] = str(out_dir).replace("\\", "/")
    if extra_env:
        env.update(extra_env)

    cmd = [str(mgba), "--script", str(lua_path), str(rom_copy)]
    logp = out_dir / "_run.log"
    dead_without_done = False

    with open(out_dir / "_mgba.out", "wb") as out_f:
        p = subprocess.Popen(cmd, env=env, stdout=out_f,
                             stderr=subprocess.STDOUT, cwd=str(out_dir))
        deadline = time.time() + timeout
        while time.time() < deadline:
            exited = p.poll() is not None
            if exited:
                time.sleep(0.8)     # 让最后几个文件落盘
                break
            time.sleep(0.4)
            if logp.exists():
                try:
                    if "[DONE]" in logp.read_text(encoding="utf-8",
                                                  errors="replace"):
                        time.sleep(1.2)
                        break
                except Exception:
                    pass
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=10)
        else:
            # 进程自己退了：看它有没有写 [DONE]
            time.sleep(0.5)
            if logp.exists():
                txt = logp.read_text(encoding="utf-8", errors="replace")
                dead_without_done = "[DONE]" not in txt
            else:
                dead_without_done = True
    res.elapsed = time.time() - t0

    res.log_text = (logp.read_text(encoding="utf-8", errors="replace")
                    if logp.exists() else "")
    mo = out_dir / "_mgba.out"
    if mo.exists():
        res.mgba_out = mo.read_text(encoding="utf-8", errors="replace")

    # ① 日志
    if not logp.exists():
        res.reasons.append("没有 _run.log —— Lua 根本没执行（参数/env 错？）")
    elif not res.log_text.strip():
        res.reasons.append("_run.log 是空的 —— 脚本没跑起来")

    # ② 错误指纹
    blob = res.log_text + "\n" + res.mgba_out
    for m in ERROR_MARKERS:
        if m in blob:
            first = ""
            for line in blob.splitlines():
                if m in line:
                    first = line.strip()[:220]
                    break
            res.reasons.append(f"错误标记 {m!r} x{blob.count(m)}：{first}")
            break

    # ③ [DONE]
    done_line = ""
    for line in res.log_text.splitlines():
        if "[DONE]" in line:
            done_line = line.strip()
    if require_done:
        if not done_line:
            extra = "（进程自行退出 = 崩溃）" if dead_without_done else \
                    "（超时被杀）"
            res.reasons.append(f"没有 [DONE] —— 脚本没走完{extra}")
        elif "code=0" not in done_line:
            res.reasons.append(f"[DONE] 非零退出：{done_line}")
    if done_line:
        res.notes.append(done_line)

    # ④ 帧数
    if min_frames > 0:
        fv = -1
        for tok in done_line.split():
            if tok.startswith("f="):
                try:
                    fv = int(tok[2:])
                except ValueError:
                    pass
        if fv < 0:
            res.reasons.append("无法从 [DONE] 读到帧数 f=")
        elif fv < min_frames:
            res.reasons.append(f"帧数只到 {fv}，低于期望 {min_frames}")
        else:
            res.notes.append(f"帧数 f={fv}")

    # ⑤ 产出
    if expect_files:
        missing, empty, stale = [], [], []
        for name in expect_files:
            fp = out_dir / name
            if not fp.exists():
                missing.append(name)
            elif fp.stat().st_size <= 0:
                empty.append(name)
            elif fp.stat().st_mtime < rw - 2:
                stale.append(name)
        if missing:
            res.reasons.append(
                f"缺少产出 {len(missing)} 个：{missing[:6]}"
                + (" ..." if len(missing) > 6 else ""))
        if empty:
            res.reasons.append(f"产出是空文件：{empty[:6]}")
        if stale:
            res.reasons.append(f"产出是上次的旧文件：{stale[:6]}")

    res.ok = not res.reasons
    return res
