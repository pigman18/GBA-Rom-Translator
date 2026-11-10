# GDB 循环执行器（配合 mGBA GDB stub，端口 2345）
# 用法：arm-none-eabi-gdb -batch -x gdb_loop.py
#
# 关键：用异步 continue（`continue &`）让游戏在后台跑，
#       主循环轮询 cmd.txt 执行命令（interrupt/info registers 等），
#       崩溃时 continue 会停，此时 interrupt + info registers 抓现场。
#
# 命令文件约定：
#   cmd.txt      外部追加 GDB 命令（每行一条），末尾追加 __DONE__ 触发执行
#   out.txt      脚本输出（我读取）
#   cursor.txt   内部消费游标（自动维护）
import gdb
import os
import time
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CMD_FILE = os.path.join(BASE, "cmd.txt")
OUT_FILE = os.path.join(BASE, "out.txt")
CURSOR_FILE = os.path.join(BASE, "cursor.txt")
DONE_MARK = "__DONE__"

def log(msg):
    try:
        with open(OUT_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def connect():
    try:
        gdb.execute("set pagination off")
        gdb.execute("set confirm off")
        gdb.execute("target remote localhost:2345")
        log("[OK] connected to mGBA GDB stub")
        return True
    except Exception as e:
        log(f"[ERR] connect failed: {e}")
        return False

def exec_cmd(line):
    try:
        result = gdb.execute(line, to_string=True)
        if result and result.strip():
            log(result.rstrip("\n"))
    except Exception as e:
        log(f"[CMD-ERR] {line}: {e}")

def main():
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("")

    if not connect():
        log("[FATAL] 无法连接")
        return

    # 异步 continue：让游戏在后台跑，主循环继续轮询
    log("[INFO] 异步 continue 让游戏运行（`continue &`）...")
    try:
        gdb.execute("continue &")
    except Exception as e:
        log(f"[WARN] continue & 失败: {e}")

    log("[READY] 已就绪。追加 GDB 命令到 cmd.txt，末尾 __DONE__ 触发")

    if not os.path.exists(CURSOR_FILE):
        with open(CURSOR_FILE, "w") as f:
            f.write("0")

    while True:
        if not os.path.exists(CMD_FILE):
            time.sleep(0.4)
            continue
        try:
            with open(CMD_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            time.sleep(0.4)
            continue

        if not lines:
            time.sleep(0.4)
            continue

        last_done = -1
        for i, ln in enumerate(lines):
            if ln.strip() == DONE_MARK:
                last_done = i
        if last_done < 0:
            time.sleep(0.4)
            continue

        consumed = 0
        try:
            with open(CURSOR_FILE, "r") as f:
                consumed = int(f.read().strip() or "0")
        except Exception:
            consumed = 0

        for i in range(consumed, last_done):
            ln = lines[i].rstrip("\n").rstrip("\r")
            s = ln.strip()
            if s == "" or s == DONE_MARK:
                continue
            if s == "__EXIT__":
                log("[EXIT] 收到退出命令")
                return
            log(f">>> {ln}")
            exec_cmd(ln)

        try:
            with open(CURSOR_FILE, "w") as f:
                f.write(str(last_done + 1))
        except Exception:
            pass

        log("[BATCH-DONE]")
        time.sleep(0.4)

if __name__ == "__main__":
    main()
