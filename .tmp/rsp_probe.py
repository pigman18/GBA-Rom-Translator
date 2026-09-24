"""把 mGBA GDB stub 的应答逐字节看清楚：每次发送后把 socket 抽干再打印。"""
import socket, time, sys

PORT = 2345
s = socket.create_connection(("127.0.0.1", PORT), timeout=6)
s.settimeout(0.4)
print("connected", flush=True)


def drain(label, secs=1.2):
    t0 = time.time()
    got = b""
    while time.time() - t0 < secs:
        try:
            d = s.recv(4096)
            if not d:
                got += b"<EOF>"
                break
            got += d
        except socket.timeout:
            pass
        except OSError as e:
            got += b"<ERR %s>" % str(e).encode()
            break
    print("%-22s -> %r" % (label, got), flush=True)


def send(p):
    s.sendall(b"$" + p + b"#%02X" % (sum(p) & 0xFF))


drain("passive")
send(b"?");      drain("after ?")
send(b"qSupported:swbreak+;hwbreak+;QStartNoAckMode+"); drain("after qSupported")
send(b"QStartNoAckMode"); drain("after QStartNoAckMode")
send(b"Z0,8000432,2");   drain("after Z0")
send(b"c");              drain("after c")
send(b"P1=f7030000");    drain("after P1")
send(b"c");              drain("after c2")
send(b"m4000000,4");     drain("after m")
s.close()
