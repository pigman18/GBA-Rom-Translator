"""
Simple GDB RSP test - connect and query target
"""
import socket
import sys

def rsp_recv(sock):
    """Read a complete RSP packet ($...##)."""
    buf = b""
    while True:
        ch = sock.recv(1)
        if ch == b"$":
            buf = b""
        elif ch == b"#":
            csum_hex = sock.recv(2)
            return buf
        elif ch in (b"+", b"-"):
            continue
        else:
            buf += ch

def rsp_send(sock, cmd):
    """Send a command and get response."""
    data = cmd.encode()
    csum = sum(data) & 0xFF
    pkt = b"$" + data + b"#%02X" % csum
    sock.send(pkt)
    # Wait for ACK
    ack = sock.recv(1)
    if ack == b"+":
        pass  # OK
    elif ack == b"-":
        print("NAK received")
    # Now read response
    return rsp_recv(sock)

def hex_to_int(hex_str):
    return int(hex_str, 16)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30)
sock.connect(("127.0.0.1", 2345))
print("Connected to mGBA GDB stub")

# First, see if there's a greeting/stop packet
try:
    greeting = rsp_recv(sock)
    print(f"Greeting/initial: {greeting}")
except socket.timeout:
    print("No initial greeting")

# Query status
resp = rsp_send(sock, "?")
print(f"Status: {resp}")

# Read all registers
resp = rsp_send(sock, "g")
print(f"Registers hex ({len(resp)//8} regs):")
for i in range(16):
    reg_hex = resp[i*8:(i+1)*8]
    reg_val = int(reg_hex, 16)
    name = f"r{i}" if i < 15 else "pc"
    if i == 13:
        name = "sp"
    elif i == 14:
        name = "lr"
    elif i == 15:
        name = "pc"
    print(f"  {name}: 0x{reg_val:08X}")

# Read DMA registers
def read_word(addr):
    resp = rsp_send(sock, f"m{addr:X},4")
    return int(resp, 16)

# Try setting a breakpoint on DMA3CNT write
# Hardware watchpoint: Z2,<addr>,<kind>
# kind 2 for 4-byte write watchpoint on ARM
print("\nTrying to set write watchpoint on DMA3CNT (0x040000DC)...")
resp = rsp_send(sock, "Z2,40000DC,4")
print(f"Watchpoint result: {resp}")

# Also try on DMA3SAD
print("\nTrying to set write watchpoint on DMA3SAD (0x040000D4)...")
resp = rsp_send(sock, "Z2,40000D4,4")
print(f"Watchpoint result: {resp}")

# Read DMA registers
print("\n=== DMA3 Registers ===")
print(f"DMA3SAD: 0x{read_word(0x040000D4):08X}")
print(f"DMA3DAD: 0x{read_word(0x040000D8):08X}")
print(f"DMA3CNT: 0x{read_word(0x040000DC):08X}")

# If watchpoints work, continue and wait
if b"OK" in resp:
    print("\nWatchpoint set! Continuing execution...")
    rsp_send(sock, "c")
    print("Waiting for break...")
    while True:
        try:
            stop = rsp_recv(sock)
            print(f"Stop: {stop}")
            # Read state
            resp = rsp_send(sock, "g")
            regs = [int(resp[i*8:(i+1)*8], 16) for i in range(16)]
            print(f"PC=0x{regs[15]:08X} LR=0x{regs[14]:08X}")
            print(f"SP=0x{regs[13]:08X}")
            print(f"DMA3SAD: 0x{read_word(0x040000D4):08X}")
            print(f"DMA3DAD: 0x{read_word(0x040000D8):08X}")
            # Continue
            rsp_send(sock, "c")
        except socket.timeout:
            print("Timeout waiting for breakpoint")
            break
        except KeyboardInterrupt:
            break

sock.close()
print("\nDone")
