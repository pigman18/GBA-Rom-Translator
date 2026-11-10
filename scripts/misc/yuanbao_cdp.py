#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CDP client for the Yuanbao desktop app (Edge WebView2 based).

Zero third-party deps: a minimal RFC6455 client on top of the stdlib.

The Yuanbao desktop shell hosts its UI in an Edge WebView2 control, which does
not accept --remote-debugging-port on the host command line. The supported way
to pass Chromium switches is the WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS env var,
set before the host process starts:

    set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222
    "C:\\Program Files\\Tencent\\Yuanbao\\yuanbao.exe"

Then:  python yuanbao_cdp.py list
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import urllib.request

DEFAULT_PORT = 9222
HOST = "127.0.0.1"


# --------------------------------------------------------------------------- #
# Minimal WebSocket client (RFC 6455)
# --------------------------------------------------------------------------- #
class WebSocketError(RuntimeError):
    pass


class WSClient:
    def __init__(self, url: str, timeout: float = 20.0):
        self.url = url
        self.sock: socket.socket | None = None
        self._buf = bytearray()
        self.timeout = timeout
        self._connect()

    # -- handshake ---------------------------------------------------------- #
    def _connect(self) -> None:
        assert self.url.startswith("ws://"), f"unsupported scheme: {self.url}"
        rest = self.url[len("ws://"):]
        path = rest.find("/")
        if path == -1:
            hostport, path = rest, "/"
        else:
            hostport, path = rest[:path], rest[path:]
        host, _, port = hostport.partition(":")
        port = int(port or 80)

        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        ).encode()

        s = socket.create_connection((host, port), timeout=self.timeout)
        s.settimeout(self.timeout)
        s.sendall(req)

        head = bytearray()
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            if not chunk:
                raise WebSocketError("connection closed during handshake")
            head += chunk
        status = head.split(b"\r\n", 1)[0].decode(errors="replace")
        if "101" not in status:
            raise WebSocketError(f"handshake failed: {status}")
        self.sock = s

    # -- framing ------------------------------------------------------------ #
    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        out = bytearray()
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise WebSocketError("connection closed while reading")
            out += chunk
        return bytes(out)

    def _read_frame(self):
        b0, b1 = self._recv_exact(2)
        fin = (b0 & 0x80) != 0
        opcode = b0 & 0x0F
        masked = (b1 & 0x80) != 0
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv_exact(8))[0]
        if masked:
            self._recv_exact(4)  # server frames are never masked in practice
        payload = self._recv_exact(length) if length else b""
        return fin, opcode, payload

    def recv(self) -> str:
        """Read one complete text message (handles fragmentation)."""
        chunks = []
        while True:
            fin, opcode, payload = self._read_frame()
            if opcode == 0x8:  # close
                raise WebSocketError("server sent close frame")
            if opcode == 0x9:  # ping
                continue
            if opcode == 0xA:  # pong
                continue
            chunks.append(payload)
            if fin:
                return b"".join(chunks).decode("utf-8", errors="replace")

    def send(self, text: str) -> None:
        assert self.sock is not None
        data = text.encode("utf-8")
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


# --------------------------------------------------------------------------- #
# CDP over WebSocket
# --------------------------------------------------------------------------- #
class CDP:
    def __init__(self, ws_url: str):
        self.ws = WSClient(ws_url)
        self._id = 0

    def call(self, method: str, params: dict | None = None, *, session: str | None = None):
        self._id += 1
        msg: dict = {"id": self._id, "method": method}
        if params:
            msg["params"] = params
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg, ensure_ascii=False))

        # Skip events until our response id shows up.
        while True:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self._id:
                if "error" in data:
                    raise WebSocketError(f"{method}: {data['error']}")
                return data.get("result", {})

    def evaluate(self, expr: str, *, await_promise: bool = False, return_by_value: bool = True):
        res = self.call(
            "Runtime.evaluate",
            {
                "expression": expr,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
                "userGesture": True,
                "allowUnsafeEvalBlockedByCSP": True,
            },
        )
        if res.get("exceptionDetails"):
            raise WebSocketError(f"JS exception: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def close(self) -> None:
        self.ws.close()


# --------------------------------------------------------------------------- #
# DevTools HTTP endpoints
# --------------------------------------------------------------------------- #
def http_json(path: str, port: int = DEFAULT_PORT):
    url = f"http://{HOST}:{port}{path}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def list_targets(port: int = DEFAULT_PORT):
    return http_json("/json/list", port)


def pick_yuanbao_target(targets):
    """The Yuanbao UI lives in a WebView2 page; prefer a page-ish target."""
    for t in targets:
        if t.get("type") != "page":
            continue
        if t.get("webSocketDebuggerUrl"):
            return t
    return None


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    port = int(os.environ.get("YUANBAO_CDP_PORT", DEFAULT_PORT))

    if cmd == "list":
        try:
            targets = list_targets(port)
        except Exception as exc:  # noqa: BLE001
            print(f"[x] cannot reach DevTools on port {port}: {exc}")
            print("    Is Yuanbao running with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS set?")
            return 1

        if not targets:
            print("[x] no targets")
            return 1

        print(f"[i] {len(targets)} target(s) on port {port}\n")
        for t in targets:
            print(f"  type   : {t.get('type')}")
            print(f"  title  : {t.get('title')!r}")
            print(f"  url    : {t.get('url')!r}")
            print(f"  ws     : {t.get('webSocketDebuggerUrl')}")
            print()

        chosen = pick_yuanbao_target(targets)
        if chosen:
            print(f"[i] picked: {chosen.get('title')!r} -> {chosen.get('url')}")
        else:
            print("[x] no page target with a debugger url")
            return 1
        return 0

    if cmd == "probe":
        chosen = pick_yuanbao_target(list_targets(port))
        if not chosen:
            print("[x] no usable target")
            return 1
        cdp = CDP(chosen["webSocketDebuggerUrl"])
        try:
            print("title  :", cdp.evaluate("document.title"))
            print("url    :", cdp.evaluate("location.href"))
            print("inputs :", cdp.evaluate(
                "Array.from(document.querySelectorAll('input,textarea')).map("
                "e=>e.tagName+':'+(e.type||'')+':'+(e.placeholder||'')).slice(0,20)"
            ))
        finally:
            cdp.close()
        return 0

    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
