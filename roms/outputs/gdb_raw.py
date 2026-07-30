"""Raw socket test to mGBA GDB stub"""
import socket
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
try:
    sock.connect(("127.0.0.1", 2345))
    print("Connected!")
except Exception as e:
    print(f"Connect failed: {e}")
    sock.close()
    exit(1)

# Try to read any data the stub sends first
print("Reading initial data...")
sock.settimeout(2)
try:
    data = sock.recv(4096)
    print(f"Initial data ({len(data)} bytes): {data[:200]}")
except socket.timeout:
    print("No initial data")

# Send '?' packet manually
sock.settimeout(10)
pkt = b"$?#67"  # ? = 0x3F, sum = 0x3F, 0xFF & 0x3F = 0x3F = 63 = '?' need to compute
# Actually: '?' is 0x3F, so sum = 0x3F, but we need to send # and two hex digits
# $?#XX
import struct
cmd = b"?"
csum = sum(cmd) & 0xFF
pkt = b"$" + cmd + b"#%02X" % csum
print(f"Sending: {pkt}")
sock.send(pkt)

# Read response
time.sleep(0.5)
sock.settimeout(5)
try:
    resp = sock.recv(4096)
    print(f"Response ({len(resp)} bytes): {resp[:500]}")
except socket.timeout:
    print("No response to '?' packet")

# Try reading registers
cmd = b"g"
csum = sum(cmd) & 0xFF
pkt = b"$" + cmd + b"#%02X" % csum
print(f"Sending: {pkt}")
sock.send(pkt)

time.sleep(0.5)
try:
    resp = sock.recv(4096)
    print(f"Response ({len(resp)} bytes): {resp[:500]}")
except socket.timeout:
    print("No response to 'g' packet")

# Check if the stub uses + for ACK
# Try again with just recv
print("\nSending a break command")
cmd = b"\x03"  # Ctrl+C = break
sock.send(cmd)
time.sleep(0.5)
try:
    resp = sock.recv(4096)
    print(f"Break response: {resp[:500]}")
except socket.timeout:
    print("No response to break")

sock.close()
print("Done")
