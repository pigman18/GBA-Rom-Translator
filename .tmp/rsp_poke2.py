"""逐条试写，看 mGBA stub 到底接受哪些 M 包。"""
import socket, time

s = socket.create_connection(("127.0.0.1", 2345), timeout=6)
s.settimeout(0.35)


def drain(secs=0.6):
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
        except OSError as e:
            got += b"<ERR>"
            break
    return got


def send(p):
    s.sendall(b"$" + p + b"#%02X" % (sum(p) & 0xFF))


print("greeting:", repr(drain(1.0)))

tests = [
    b"M203fff0,2:ff03",
    b"m203fff0,2",
    b"M203fff0,4:ff030000",
    b"M203ff00,2:ff03",
    b"M0203fff0,2:ff03",
    b"m203fff0,2",
    b"M8000468,4:f0ff0302",
    b"m8000468,4",
    b"M3007ff0,2:ff03",
    b"m3007ff0,2",
    b"P1=f7030000",
    b"P0=00000000",
    b"g",
    b"?",
]
for t in tests:
    send(t)
    time.sleep(0.12)
    print("%-24s -> %r" % (t.decode(), drain(0.6)))

s.close()
