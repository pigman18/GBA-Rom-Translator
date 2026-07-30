"""
GDB Remote Serial Protocol client for mGBA debug stub.
Connects to port 2345, sets watchpoints on DMA3 registers,
and traces call stack when ClearWindow-tilemap DMA is triggered.
"""
import socket
import struct
import sys
import time

class GDBClient:
    def __init__(self, host="127.0.0.1", port=2345):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.settimeout(30)
        self.buf = b""

    def send(self, cmd: str) -> bytes:
        """Send a GDB RSP packet and receive response."""
        # Packet format: $<data>#<csum>
        data = cmd.encode()
        csum = sum(data) & 0xFF
        pkt = b"$" + data + b"#%02X" % csum
        self.sock.send(pkt)
        # Read until '#' with checksum
        resp = b""
        while True:
            ch = self.sock.recv(1)
            if ch == b"$":
                resp = b""
            elif ch == b"#":
                csum_hex = self.sock.recv(2)
                # ACK
                self.sock.send(b"+")
                return resp
            elif ch == b"+":
                continue  # ACK from remote
            elif ch == b"-":
                print("NAK, retrying...")
                continue
            else:
                resp += ch

    def send_noack(self, cmd: str) -> bytes:
        """Send without expecting ACK (for packets to target)."""
        data = cmd.encode()
        csum = sum(data) & 0xFF
        pkt = b"$" + data + b"#%02X" % csum
        self.sock.send(pkt)
        return b""

    def read_register(self, reg_num: int) -> int:
        """Read a single register by number (0-15 for GBA ARM regs)."""
        # 'g' reads all registers
        resp = self.send("g")
        # Response is hex-encoded register values, 8 hex chars each
        # ARM7TDMI: r0-r15 (16 regs), each 8 hex chars = 128 hex chars
        reg_hex = resp[reg_num * 8: (reg_num + 1) * 8]
        return int(reg_hex, 16)

    def read_registers(self) -> list:
        """Read all registers."""
        resp = self.send("g")
        regs = []
        for i in range(16):
            reg_hex = resp[i * 8: (i + 1) * 8]
            regs.append(int(reg_hex, 16))
        return regs

    def read_memory(self, addr: int, length: int) -> bytes:
        """Read memory at address."""
        resp = self.send(f"m{addr:X},{length:X}")
        return bytes.fromhex(resp.decode())

    def read_word(self, addr: int) -> int:
        data = self.read_memory(addr, 4)
        return struct.unpack("<I", data)[0]

    def read_hword(self, addr: int) -> int:
        data = self.read_memory(addr, 2)
        return struct.unpack("<H", data)[0]

    def set_watchpoint(self, addr: int, kind: int = 2, size: int = 4):
        """
        Set hardware watchpoint.
        kind 2 = write watchpoint
        kind 3 = read watchpoint
        kind 4 = access watchpoint
        """
        resp = self.send(f"Z{kind},{addr:X},{size:X}")
        if resp == b"OK":
            print(f"Watchpoint set at 0x{addr:08X} (type {kind}, size {size})")
            return True
        else:
            print(f"Watchpoint failed: {resp}")
            return False

    def remove_watchpoint(self, addr: int, kind: int = 2, size: int = 4):
        self.send(f"z{kind},{addr:X},{size:X}")

    def continue_exec(self):
        self.send_noack("c")

    def wait_halt(self) -> dict:
        """Wait for target to halt (watchpoint hit)."""
        resp = b""
        while True:
            ch = self.sock.recv(1)
            if ch == b"%":
                # Notification packet
                continue
            elif ch == b"$":
                resp = b""
            elif ch == b"#":
                csum = self.sock.recv(2)
                self.sock.send(b"+")
                break
            elif ch in (b"+", b"-"):
                continue
            else:
                resp += ch
        # Parse stop reply: Txx<registers>
        sig = resp[0:2].decode()
        print(f"Stop signal: T{int(sig, 16)}")
        info = {"signal": int(sig, 16)}
        # Parse register pairs after Txx
        i = 2
        while i < len(resp) - 1:
            reg = resp[i:i + 2]
            val = resp[i + 2:i + 10]
            try:
                reg_num = int(reg, 16)
                info[f"r{reg_num}"] = int(val, 16)
            except ValueError:
                pass
            i += 10
        return info

    def trace_call_stack(self):
        """Read the call stack from the current state."""
        regs = self.read_registers()
        r0, r1, r2, r3, r4, r5, r6, r7 = regs[0:8]
        r8, r9, r10, r11, r12, sp, lr, pc = regs[8:16]
        
        print(f"\n=== CPU State ===")
        print(f"PC = 0x{pc:08X}  LR = 0x{lr:08X}  SP = 0x{sp:08X}")
        print(f"R0 = 0x{r0:08X}  R1 = 0x{r1:08X}  R2 = 0x{r2:08X}  R3 = 0x{r3:08X}")
        print(f"R4 = 0x{r4:08X}  R5 = 0x{r5:08X}  R6 = 0x{r6:08X}  R7 = 0x{r7:08X}")

        # Read DMA registers
        dma3sad = self.read_word(0x040000D4)
        dma3dad = self.read_word(0x040000D8)
        dma3cnt = self.read_word(0x040000DC)
        print(f"\n=== DMA3 State ===")
        print(f"DMA3SAD = 0x{dma3sad:08X}")
        print(f"DMA3DAD = 0x{dma3dad:08X}")
        print(f"DMA3CNT = 0x{dma3cnt:08X} (count={dma3cnt & 0xFFFF}, enable={bool(dma3cnt>>31)})")

        # Trace back through LR
        print(f"\n=== Call Stack (unwinding) ===")
        # THUMB LR contains return address, which is caller PC + 1 (thumb bit)
        return_addr = lr
        if return_addr & 1:  # THUMB mode bit
            return_addr &= ~1
        print(f"  Return address: 0x{return_addr:08X}")

        # Read LR from stack (if THUMB code was using push {lr})
        # THUMB functions typically push {lr} at entry, pop {pc} at exit
        # LR on the stack would be at SP currently
        try:
            stack_lr = self.read_word(sp)
            if 0x08000000 <= stack_lr <= 0x0A000000:  # ROM address range
                print(f"  [SP+0x00] = 0x{stack_lr:08X} (likely return addr)")
        except:
            pass
        
        # Read more stack entries for deeper trace
        print(f"\n  Stack dump:")
        for off in range(0, 0x40, 4):
            try:
                val = self.read_word(sp + off)
                marker = ""
                if 0x08000000 <= val <= 0x0A000000:
                    marker = " <-- ROM addr (possible return)"
                elif 0x02000000 <= val <= 0x02040000:
                    marker = " <-- WRAM"
                elif 0x03000000 <= val <= 0x03008000:
                    marker = " <-- IWRAM"
                print(f"  [SP+0x{off:02X}] = 0x{val:08X}{marker}")
            except:
                break

    def close(self):
        self.sock.close()

def main():
    client = GDBClient()
    
    # Step 1: Query initial status
    resp = client.send("?")
    print(f"Initial status: {resp}")
    
    # Step 2: Check if we can read DMA registers
    dma3sad = client.read_word(0x040000D4)
    dma3dad = client.read_word(0x040000D8)
    dma3cnt = client.read_word(0x040000DC)
    print(f"DMA3SAD = 0x{dma3sad:08X}")
    print(f"DMA3DAD = 0x{dma3dad:08X}")
    print(f"DMA3CNT = 0x{dma3cnt:08X}")
    
    # Step 3: Set write watchpoint on DMA3CNT (triggers on DMA start)
    # Also set on DMA3SAD to catch source address changes
    print("\nSetting watchpoints...")
    wp_sad = client.set_watchpoint(0x040000D4, kind=2, size=4)
    
    if not wp_sad:
        # Try word-sized
        wp_sad = client.set_watchpoint(0x040000D4, kind=2, size=2)
    
    if not wp_sad:
        print("Watchpoints not supported. Using stepping approach...")
        print("Reading current state for manual analysis.")
        client.trace_call_stack()
        client.close()
        return
    
    # Step 4: Continue execution and wait for watchpoint hit
    print("\nContinuing execution (press Ctrl+C to stop)...")
    print("Waiting for DMA3 register write...")
    
    timeout = time.time() + 60  # 60 second timeout
    hit_count = 0
    while time.time() < timeout:
        try:
            info = client.wait_halt()
            hit_count += 1
            
            print(f"\n=== Hit #{hit_count} ===")
            
            # Read DMA registers
            dma3sad = client.read_word(0x040000D4)
            dma3dad = client.read_word(0x040000D8)
            dma3cnt = client.read_word(0x040000DC)
            print(f"DMA3SAD = 0x{dma3sad:08X}")
            print(f"DMA3DAD = 0x{dma3dad:08X}")
            print(f"DMA3CNT = 0x{dma3cnt:08X}")
            
            # Check if this is a tilemap clear (dest = 0x0600E000 or 0x0600F000)
            is_tilemap = (dma3dad & 0xFFF00000) == 0x06000000
            is_window_tilemap = dma3dad in (0x0600E000, 0x0600F000)
            
            if is_window_tilemap:
                print("*** This is a Window tilemap DMA! ***")
                client.trace_call_stack()
            elif is_tilemap:
                print("*** This is a tilemap DMA (non-window area) ***")
            
            if hit_count >= 20:
                print("\nReached 20 hits, stopping.")
                break
                
            # Continue
            client.continue_exec()
            
        except socket.timeout:
            print("Timeout - no DMA activity")
            break
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            break
    
    client.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
