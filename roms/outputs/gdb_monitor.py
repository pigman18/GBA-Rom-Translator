#!/usr/bin/env python3
"""
mGBA GDB Read-Only Monitor
===========================
Connects to mGBA GDB stub (port 2345) in READ-ONLY mode.
Sets breakpoints, logs hit info as JSON, then auto-continues.
NO memory writes, NO register modifications, NO input simulation.

Usage:
  1. Launch mGBA: mGBA -g 2345 rom.gba   (or set GDB port in Tools→Settings)
  2. Run script:  python gdb_monitor.py
  3. Interact with mGBA window
  4. Ctrl+C to stop + print font==3 summary

Protocol: GDB Remote Serial Protocol (RSP) over TCP
Deps: Python 3 stdlib only
"""

import socket, struct, sys, json, time, traceback

HOST = "127.0.0.1"
PORT = 2345

FUNCS = {
    0x080041BC: "GetBlankTileNum",
    0x08003C00: "ClearWindowTilemap",
    0x08054C48: "DMA_Setup_Function",
}

GDB_REGS = ["r0","r1","r2","r3","r4","r5","r6","r7",
            "r8","r9","r10","r11","r12","sp","lr","pc","cpsr"]

def cksum(b): return sum(b) & 0xFF

def unescape(b):
    r = bytearray()
    i = 0
    while i < len(b):
        if b[i] == 0x7D: r.append(b[i+1] ^ 0x20); i += 2
        else: r.append(b[i]); i += 1
    return bytes(r)

class RSP:
    def __init__(self, host=HOST, port=PORT):
        self.host, self.port = host, port
        self.sock = None
        self.buf = b""

    def connect(self, timeout=10):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((self.host, self.port))
        time.sleep(0.2)
        # drain any stale data
        self.sock.settimeout(0.5)
        try:
            while True: self.sock.recv(4096)
        except: pass
        self.sock.settimeout(None)
        # ask halt reason to confirm connection
        return self.cmd(b"?")

    def close(self):
        if self.sock: self.sock.close()

    def _rb(self):
        while not self.buf:
            d = self.sock.recv(4096)
            if not d: raise ConnectionError("closed")
            self.buf += d
        b = self.buf[0]; self.buf = self.buf[1:]; return b

    def send_packet(self, cmd):
        ck = cksum(cmd)
        self.sock.sendall(b"$" + cmd + b"#%02X" % ck)
        ack = self._rb()
        if ack == 0x2D:  # '-'
            self.sock.sendall(b"$" + cmd + b"#%02X" % ck)
            ack = self._rb()
        if ack == 0x2B: return True  # '+'
        self.buf = bytes([ack]) + self.buf
        return True

    def recv_packet(self):
        while True:
            # wait for '$'
            while b"$" not in self.buf:
                self.buf += self.sock.recv(4096)
            start = self.buf.find(b"$")
            # if we got notification '%' before '$', skip it
            if start > 0 and self.buf[0:1] == b"%":
                self.buf = self.buf[self.buf.find(b"%")+1:]
                continue
            self.buf = self.buf[start:]

            # find '#'
            while b"#" not in self.buf:
                self.buf += self.sock.recv(4096)
            end = self.buf.find(b"#")
            payload = self.buf[1:end]
            if len(self.buf) < end + 3:
                self.buf += self.sock.recv(4096)
                end = self.buf.find(b"#")
                payload = self.buf[1:end]
            cks = self.buf[end+1:end+3]
            self.buf = self.buf[end+3:]

            if cks.upper() != b"%02X" % cksum(payload):
                self.sock.sendall(b"-")
                continue
            self.sock.sendall(b"+")

            p = unescape(payload)
            # if it's an O (console output) packet, discard and continue
            if p and chr(p[0]) == 'O':
                continue
            return p

    def cmd(self, c):
        self.send_packet(c)
        return self.recv_packet()

    def read_regs(self):
        r = self.cmd(b"g")
        d = {}
        for i, n in enumerate(GDB_REGS):
            if (i+1)*8 <= len(r):
                d[n] = int(r[i*8:(i+1)*8], 16)
        return d

    def read_mem(self, addr, size):
        r = self.cmd(f"m{addr:x},{size:x}".encode())
        return bytes.fromhex(r.decode())

    def set_bp(self, addr, kind=2):
        return self.cmd(f"Z0,{addr:x},{kind}".encode()) == b"OK"

    def set_wp(self, addr, kind="4", length=4):
        return self.cmd(f"Z{kind},{addr:x},{length}".encode()) == b"OK"

    def cont(self):
        """continue execution, wait for stop reply (S/T/W/X)"""
        self.send_packet(b"c")
        return self.recv_packet()

    def parse_stop(self, pkt):
        """Parse stop reply into dict."""
        r = {"raw": pkt.decode(errors="replace")}
        if not pkt: return r
        kind = chr(pkt[0]) if pkt[0] in (0x53,0x54,0x57,0x58) else "?"
        r["kind"] = kind
        if len(pkt) >= 3:
            try: r["signal"] = int(pkt[1:3], 16)
            except: r["signal"] = 0
        # T packets carry key:val; pairs
        if kind == "T" and len(pkt) > 3:
            rest = pkt[3:]
            i = 0
            while i < len(rest):
                colon = rest.find(b":", i)
                if colon == -1: break
                key = rest[i:colon]
                semi = rest.find(b";", colon+1)
                val = rest[colon+1:semi] if semi != -1 else rest[colon+1:]
                i = (semi + 1) if semi != -1 else len(rest)
                try:
                    rn = int(key)
                    if rn < len(GDB_REGS): r[GDB_REGS[rn]] = int(val, 16)
                except:
                    try: r[key.decode()] = int(val, 16)
                    except: r[key.decode(errors="replace")] = val.decode(errors="replace")
        return r


def pa(v): return f"0x{v:08X}"

def main():
    c = RSP()
    recent = []
    hits = 0
    try:
        halt = c.connect()
        print(json.dumps({"event":"connected","halt":halt.decode(errors="replace")}))
        # setup
        bps = []
        for a, n in FUNCS.items():
            ok = c.set_bp(a)
            bps.append({"addr":pa(a),"name":n,"status":"ok" if ok else "FAIL"})
        # watchpoint on DMA source buffer (access watchpoint Z4)
        wp = c.set_wp(0x020219CC, kind="4")
        if not wp:
            wp = c.set_wp(0x020219CC, kind="2")  # try write-only
        bps.append({"addr":"0x020219CC","type":"watchpoint","status":"ok" if wp else "FAIL (no HW watchpoints)"})
        print(json.dumps({"event":"init","bps":bps}))
        sys.stdout.flush()

        while True:
            stop = c.cont()
            info = c.parse_stop(stop)
            regs = c.read_regs()
            pc = regs.get("pc", 0)
            pc_base = pc & ~1
            fn = FUNCS.get(pc_base, "unknown")
            report = {
                "pc": pa(pc),
                "func": fn,
                "signal": info.get("signal", 0),
                "hit": hits,
                "regs": {k: pa(regs.get(k,0)) for k in ("r0","r1","r2","r3","r4","r5","lr")},
            }
            # window data
            r0 = regs.get("r0", 0)
            if fn in ("GetBlankTileNum","ClearWindowTilemap") and 0x02000000 <= r0 <= 0x02040000:
                try:
                    m = c.read_mem(r0, 32)
                    report["window"] = {
                        "font": f"0x{m[0x0A]:02X}",
                        "tile_base": f"0x{struct.unpack_from('<H',m,0x16)[0]:04X}",
                    }
                except Exception as e:
                    report["win_err"] = str(e)
            # watchpoint (hit at unknown PC in WRAM = DMA buffer access)
            if fn == "unknown" and report.get("signal") == 5 and pc_base not in FUNCS:
                try:
                    m = c.read_mem(pc_base, 4)
                    h1, h2 = struct.unpack_from("<HH", m, 0)
                    report["wp_insn"] = f"{h1:04X} {h2:04X}"
                except: pass

            hits += 1
            report["total"] = hits
            recent.append(report)
            if len(recent) > 50: recent.pop(0)
            print(json.dumps(report))
            sys.stdout.flush()

    except KeyboardInterrupt:
        f3 = [h for h in recent if h.get("window",{}).get("font") == "0x03"]
        s = {"event":"stopped","total_hits":hits,
             "font3_count":len(f3)}
        if f3:
            s["font3_recent"] = f3[-10:]
        print(json.dumps(s, indent=2))
    except Exception as e:
        print(json.dumps({"event":"error","msg":str(e)}))
        traceback.print_exc()
    finally:
        c.close()
        print(json.dumps({"event":"disconnected"}))

if __name__ == "__main__":
    main()
