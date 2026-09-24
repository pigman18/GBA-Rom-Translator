"""摸清 NAK 的规律：同一包反复发，看什么时候被接受。"""
import socket, time

s = socket.create_connection(("127.0.0.1", 2345), timeout=6)
s.settimeout(0.4)


def drain(secs=0.5):
    t0 = time.time()
    got = b""
    while time.time() - t0 < secs:
        try:
            d = s.recv(8192)
            if not d:
                got += b"<EOF>"
                break
            got += d
        except socket.timeout:
            pass
        except OSError:
            break
    return got


def send(p):
    s.sendall(b"$" + p + b"#%02X" % (sum(p) & 0xFF))


print("greeting:", repr(drain(0.8)))

print("\n--- A) 同一写包连发 12 次，间隔 0.35s，回 + ---")
for i in range(12):
    send(b"+" )
    send(b"M8000468,4:00009008")
    time.sleep(0.35)
    print("  #%d %r" % (i, drain(0.5)))

print("\n--- B) 读回确认 ---")
send(b"m8000468,4")
time.sleep(0.3)
print("  ", repr(drain(0.6)))

print("\n--- C) 写键值 @0x08900000 ---")
for i in range(6):
    send(b"+" )
    send(b"M8900000,2:ff03")
    time.sleep(0.35)
    print("  #%d %r" % (i, drain(0.5)))

print("\n--- D) 读回 ---")
send(b"m8900000,2")
time.sleep(0.3)
print("  ", repr(drain(0.6)))
s.close()
