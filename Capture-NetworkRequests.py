#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取指定进程ID的网络请求（Windows）。

抓包后用 pktmon 抓原始包，再自行解析 pcapng：重组 TCP 流，提取
HTTP 请求/响应的方法、URL、Host、Headers、Body；HTTPS 解密前至少
解析 TLS ClientHello 的 SNI 得到目标域名。

用法:
  python Capture-NetworkRequests.py --pid 6404 --monitor
      仅实时监视该进程连接（无需管理员），不抓包。
  python Capture-NetworkRequests.py --pid 6404 --duration 60
      抓包 60 秒并按该进程连接生成 pktmon 过滤器，结束解析输出请求。
  python Capture-NetworkRequests.py --pid 6404 --full --duration 60
      全量抓包（不按连接过滤），解析出请求后按进程连接高亮。
  python Capture-NetworkRequests.py --pid 6404 --duration 0
      抓包直到 Ctrl+C。
  python Capture-NetworkRequests.py --analyze file.pcapng
      只解析已有的 pcapng，不抓包。

说明:
  * 抓包模式需要管理员权限（Windows 10 1809+ / Server 2019+，系统自带 pktmon）。
  * pktmon 抓不到 127.0.0.1 回环流量；纯本机进程请用 --analyze 喂入
    其它方式抓到的 pcapng（如 Wireshark）。
  * HTTPS 为加密流量，明文需配合 SSLKEYLOGFILE 抓包后再解密；
    本脚本会先给出每条连接的 SNI 域名与握手信息。
"""

import argparse
import ctypes
import datetime
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time

TCP_STATES = {
    1: 'CLOSED', 2: 'LISTEN', 3: 'SYN_SENT', 4: 'SYN_RCVD', 5: 'ESTAB',
    6: 'FIN_WAIT1', 7: 'FIN_WAIT2', 8: 'CLOSE_WAIT', 9: 'CLOSING',
    10: 'LAST_ACK', 11: 'TIME_WAIT', 12: 'DELETE_TCB',
}
ERROR_INSUFFICIENT_BUFFER = 122
TCP_TABLE_OWNER_PID_ALL = 5
UDP_TABLE_OWNER_PID = 1
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MAX_STREAM_BYTES = 2 * 1024 * 1024      # 单方向流缓冲上限
MAX_BODY_SHOW = 4096                     # body 展示上限
MAX_MSG_PER_STREAM = 50                  # 单连接最多输出的消息数

# --------------------------------------------------------------------------
# 进程信息 / 连接枚举（ctypes + IP Helper API，无需第三方库）
# --------------------------------------------------------------------------

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def process_info(pid):
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(h)
    return None


def _fmt_addr(family, raw):
    if family == socket.AF_INET:
        return socket.inet_ntop(socket.AF_INET, bytes(raw[:4]))
    return socket.inet_ntop(socket.AF_INET6, bytes(raw[:16]))


def _fill_table(fn, family, table_class):
    size = ctypes.c_ulong(0)
    fn(None, ctypes.byref(size), False, family, table_class, 0)
    buf = ctypes.create_string_buffer(max(size.value, 1))
    for _ in range(3):
        rc = fn(buf, ctypes.byref(size), False, family, table_class, 0)
        if rc == 0:
            return buf
        if rc != ERROR_INSUFFICIENT_BUFFER:
            return None
        buf = ctypes.create_string_buffer(max(size.value, 1))
    return None


def _get_tcp(pid, family):
    iphlpapi = ctypes.windll.iphlpapi
    buf = _fill_table(iphlpapi.GetExtendedTcpTable, family, TCP_TABLE_OWNER_PID_ALL)
    if not buf:
        return []
    n = struct.unpack_from('<I', buf.raw, 0)[0]
    rows = []
    if family == socket.AF_INET:
        off, step = 4, 24
        for _ in range(n):
            state = struct.unpack_from('<I', buf.raw, off)[0]
            local = _fmt_addr(family, buf.raw[off + 4:off + 8])
            lport = int.from_bytes(buf.raw[off + 8:off + 10], 'big')
            remote = _fmt_addr(family, buf.raw[off + 12:off + 16])
            rport = int.from_bytes(buf.raw[off + 16:off + 18], 'big')
            owner = struct.unpack_from('<I', buf.raw, off + 20)[0]
            if owner == pid and rport != 0:
                rows.append((state, local, lport, remote, rport))
            off += step
    else:
        off, step = 4, 56
        for _ in range(n):
            local = _fmt_addr(family, buf.raw[off:off + 16])
            lport = int.from_bytes(buf.raw[off + 20:off + 22], 'big')
            remote = _fmt_addr(family, buf.raw[off + 24:off + 40])
            rport = int.from_bytes(buf.raw[off + 44:off + 46], 'big')
            state = struct.unpack_from('<I', buf.raw, off + 48)[0]
            owner = struct.unpack_from('<I', buf.raw, off + 52)[0]
            if owner == pid and rport != 0:
                rows.append((state, local, lport, remote, rport))
            off += step
    return rows


def _get_udp(pid, family):
    iphlpapi = ctypes.windll.iphlpapi
    buf = _fill_table(iphlpapi.GetExtendedUdpTable, family, UDP_TABLE_OWNER_PID)
    if not buf:
        return []
    n = struct.unpack_from('<I', buf.raw, 0)[0]
    rows = []
    if family == socket.AF_INET:
        off, step = 4, 12
        for _ in range(n):
            local = _fmt_addr(family, buf.raw[off:off + 4])
            lport = int.from_bytes(buf.raw[off + 4:off + 6], 'big')
            owner = struct.unpack_from('<I', buf.raw, off + 8)[0]
            if owner == pid:
                rows.append((local, lport))
            off += step
    else:
        off, step = 4, 28
        for _ in range(n):
            local = _fmt_addr(family, buf.raw[off:off + 16])
            lport = int.from_bytes(buf.raw[off + 20:off + 22], 'big')
            owner = struct.unpack_from('<I', buf.raw, off + 24)[0]
            if owner == pid:
                rows.append((local, lport))
            off += step
    return rows


def _reverse(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def get_connections(pid, resolve=False):
    conns = []
    for state, local, lport, remote, rport in _get_tcp(pid, socket.AF_INET):
        conns.append({'proto': 'TCP', 'state': TCP_STATES.get(state, str(state)),
                      'local': '{}:{}'.format(local, lport),
                      'remote_ip': remote, 'remote_port': rport,
                      'remote': '{}:{}'.format(remote, rport)})
    for state, local, lport, remote, rport in _get_tcp(pid, socket.AF_INET6):
        conns.append({'proto': 'TCP', 'state': TCP_STATES.get(state, str(state)),
                      'local': '{}:{}'.format(local, lport),
                      'remote_ip': remote, 'remote_port': rport,
                      'remote': '{}:{}'.format(remote, rport)})
    for local, lport in _get_udp(pid, socket.AF_INET):
        conns.append({'proto': 'UDP', 'state': 'UDP', 'local': '{}:{}'.format(local, lport),
                      'remote_ip': None, 'remote_port': None, 'remote': '-'})
    for local, lport in _get_udp(pid, socket.AF_INET6):
        conns.append({'proto': 'UDP', 'state': 'UDP', 'local': '{}:{}'.format(local, lport),
                      'remote_ip': None, 'remote_port': None, 'remote': '-'})
    if resolve:
        for c in conns:
            if c['remote_ip'] and c['remote_ip'] not in ('0.0.0.0', '127.0.0.1', '::', '::1'):
                name = _reverse(c['remote_ip'])
                if name:
                    c['remote'] = '{} [{}]'.format(c['remote_ip'], name)
    return conns


def show_connections(conns):
    if not conns:
        print('  (当前无活动连接)')
        return
    print('  {:<5} {:<12} {:<46} {}'.format('Proto', 'State', 'Local', 'Remote'))
    for c in sorted(conns, key=lambda x: (x['proto'], x['remote'])):
        print('  {:<5} {:<12} {:<46} {}'.format(c['proto'], c['state'], c['local'], c['remote']))


# --------------------------------------------------------------------------
# pcapng 解析（pktmon 输出：linktype 0，混合 802.11 QoS 数据帧与以太网帧）
# --------------------------------------------------------------------------

def parse_pcapng(path):
    """逐块读 pcapng，产出 (timestamp, 原始帧字节)。"""
    with open(path, 'rb') as f:
        data = f.read()
    pos, n = 0, len(data)
    while pos + 12 <= n:
        btype, blen = struct.unpack_from('<II', data, pos)
        if blen < 12 or pos + blen > n:
            break
        if btype == 0x00000006:  # Enhanced Packet Block
            _ifid, tshi, tslo, caplen, _pktlen = struct.unpack_from('<IIIII', data, pos + 8)
            yield (tshi << 32) | tslo, data[pos + 28:pos + 28 + caplen]
        elif btype == 0x00000003:  # Simple Packet Block
            pktlen = struct.unpack_from('<I', data, pos + 8)[0]
            yield 0, data[pos + 16:pos + 16 + pktlen]
        pos += blen


def parse_ip(ip):
    if len(ip) < 20:
        return None
    ver = ip[0] >> 4
    if ver == 4:
        ihl = (ip[0] & 0xF) * 4
        if len(ip) < ihl + 4:
            return None
        return (socket.inet_ntop(socket.AF_INET, bytes(ip[12:16])),
                socket.inet_ntop(socket.AF_INET, bytes(ip[16:20])),
                ip[9], ip[ihl:])
    if ver == 6:
        if len(ip) < 40:
            return None
        return (socket.inet_ntop(socket.AF_INET6, bytes(ip[8:24])),
                socket.inet_ntop(socket.AF_INET6, bytes(ip[24:40])),
                ip[6], ip[40:])
    return None


def decode_l2(pkt):
    """把原始帧解成 (src_ip, dst_ip, proto, 传输层载荷)；解不了返回 None。"""
    if len(pkt) < 14:
        return None
    fc = struct.unpack('<H', pkt[0:2])[0]
    if (fc & 0x000C) == 0x0008:  # 802.11 Data 帧
        subtype = (fc >> 4) & 0xF
        off = 24  # FC+Dur+A1+A2+A3+Seq
        if (fc >> 8) & 0x1 and (fc >> 9) & 0x1:
            off += 6  # Addr4
        if subtype & 0x8:
            off += 2  # QoS Control
        if off + 8 <= len(pkt) and pkt[off:off + 2] == b'\xaa\xaa':
            et = struct.unpack('>H', pkt[off + 6:off + 8])[0]
            if et in (0x0800, 0x86DD):
                return parse_ip(pkt[off + 8:])
        return None
    if (pkt[0] >> 4) in (4, 6):
        # 兜底：裸 IP
        r = parse_ip(pkt)
        if r:
            return r
    et = struct.unpack('>H', pkt[12:14])[0]
    if et == 0x8100 and len(pkt) >= 18:          # 802.1Q VLAN
        et = struct.unpack('>H', pkt[16:18])[0]
        ip = pkt[18:]
    elif et in (0x0800, 0x86DD):                  # Ethernet II
        ip = pkt[14:]
    elif pkt[14:16] == b'\xaa\xaa' and len(pkt) >= 22:  # 802.3 LLC/SNAP
        et = struct.unpack('>H', pkt[20:22])[0]
        ip = pkt[22:]
    else:
        ip = None
    if ip and et in (0x0800, 0x86DD):
        r = parse_ip(ip)
        if r:
            return r
    if (pkt[0] >> 4) in (4, 6):
        # 兜底：裸 IP（无二层头）
        return parse_ip(pkt)
    return None


# --------------------------------------------------------------------------
# TCP 流重组 / HTTP / TLS-SNI
# --------------------------------------------------------------------------

class StreamDir:
    __slots__ = ('next_seq', 'pending', 'data', 'capped')

    def __init__(self):
        self.next_seq = None
        self.pending = {}
        self.data = bytearray()
        self.capped = False

    def feed(self, seq, flags, seg):
        if flags & 0x02:  # SYN
            self.next_seq = seq + 1
            return
        if not seg:
            return
        if self.next_seq is None:
            self.next_seq = seq
        start, end = seq, seq + len(seg)
        if end <= self.next_seq:
            return  # 重传 / 同包多层级视图，重叠去重
        if start < self.next_seq:
            seg = seg[self.next_seq - start:]
            start = self.next_seq
        if start > self.next_seq:
            self.pending[start] = seg  # 乱序暂存
            return
        if not self.capped:
            if len(self.data) + len(seg) <= MAX_STREAM_BYTES:
                self.data += seg
            else:
                self.capped = True
        self.next_seq = end
        while True:
            p = self.pending.pop(self.next_seq, None)
            if p is None:
                break
            if not self.capped and len(self.data) + len(p) <= MAX_STREAM_BYTES:
                self.data += p
            self.next_seq += len(p)


class TcpStream:
    __slots__ = ('a', 'b', 'ta', 'tb', 'sni', 'tls_version')

    def __init__(self, a, b):
        self.a, self.b = a, b
        self.ta, self.tb = StreamDir(), StreamDir()
        self.sni = None
        self.tls_version = None


def tls_sni(payload):
    """从 ClientHello 记录里解析 SNI 域名。"""
    try:
        if len(payload) < 6 or payload[0] != 0x16 or payload[5] != 0x01:
            return None
        rlen = struct.unpack('>H', payload[3:5])[0]
        hs = payload[5:5 + rlen + 4]
        if len(hs) < 8:
            return None
        hlen = (hs[1] << 16) | (hs[2] << 8) | hs[3]
        body = hs[4:4 + hlen]
        p = 2 + 32
        sid_len = body[p]; p += 1 + sid_len
        cs_len = struct.unpack('>H', body[p:p + 2])[0]; p += 2 + cs_len
        p += 1 + body[p]
        ext_len = struct.unpack('>H', body[p:p + 2])[0]; p += 2
        end = min(p + ext_len, len(body))
        while p + 4 <= end:
            etype, elen = struct.unpack('>HH', body[p:p + 4])
            p += 4
            if etype == 0 and p + elen <= len(body):  # server_name
                ext = body[p:p + elen]
                if ext[2] == 0 and len(ext) >= 5:
                    nlen = struct.unpack('>H', ext[3:5])[0]
                    if len(ext) >= 5 + nlen:
                        name = ext[5:5 + nlen]
                        try:
                            return name.decode('ascii')
                        except UnicodeDecodeError:
                            return None
            p += elen
    except (IndexError, struct.error):
        return None
    return None


def feed_packet(streams, src_ip, dst_ip, proto, payload):
    if proto != 6 or len(payload) < 20:
        return
    sport, dport, seq, _ack, oflags = struct.unpack('>HHIIH', payload[:14])
    doff = (oflags >> 12) * 4
    flags = oflags & 0x1FF
    seg = payload[doff:]
    a = (src_ip, sport)
    b = (dst_ip, dport)
    key = tuple(sorted([a, b]))
    st = streams.get(key)
    if st is None:
        st = TcpStream(key[0], key[1])
        streams[key] = st
    d = st.ta if a == st.a else st.tb
    d.feed(seq, flags, seg)
    if dport == 443 and seg and seg[0] == 0x16:
        sni = tls_sni(seg)
        if sni and not st.sni:
            st.sni = sni


REQ_RE = re.compile(rb'^([A-Z]{3,9}) ([^ \r\n]+) HTTP/1\.[01][^\r\n]*', re.M)
RESP_RE = re.compile(rb'^HTTP/1\.[01] (\d{3})[^\r\n]*', re.M)


def _parse_headers(block):
    hdrs = {}
    for line in block.split(b'\r\n')[1:]:
        if b':' in line:
            k, v = line.split(b':', 1)
            hdrs[k.strip().lower().decode('latin1', 'replace')] = v.strip().decode('latin1', 'replace')
    return hdrs


def _fmt_body(body):
    if not body:
        return ''
    txt = body.decode('utf-8', 'replace')
    if all(c in '\r\n\t' or ord(c) >= 32 for c in txt):
        return txt
    return '<binary {} bytes: {}>'.format(len(body), body[:64].hex())


def extract_http(data):
    """在单向重组流里找 HTTP 请求/响应。"""
    msgs = []
    for m in REQ_RE.finditer(data):
        start = m.start()
        he = data.find(b'\r\n\r\n', start)
        if he == -1:
            he = min(start + 2048, len(data))
        head = data[start:he]
        hdrs = _parse_headers(head)
        clen = int(hdrs.get('content-length', '0') or 0)
        body = b''
        if he + 4 <= len(data):
            body = data[he + 4:he + 4 + min(clen, MAX_BODY_SHOW)]
        msgs.append({'kind': 'request', 'method': m.group(1).decode('latin1', 'replace'),
                     'target': m.group(2).decode('latin1', 'replace'),
                     'headers': hdrs, 'body': body, 'head': head.decode('latin1', 'replace')})
    for m in RESP_RE.finditer(data):
        start = m.start()
        he = data.find(b'\r\n\r\n', start)
        if he == -1:
            he = min(start + 2048, len(data))
        head = data[start:he]
        hdrs = _parse_headers(head)
        clen = int(hdrs.get('content-length', '0') or 0)
        body = b''
        if he + 4 <= len(data):
            body = data[he + 4:he + 4 + min(clen, MAX_BODY_SHOW)]
        status = head.split(b'\r\n', 1)[0].decode('latin1', 'replace')
        msgs.append({'kind': 'response', 'code': m.group(1).decode(),
                     'status': status, 'headers': hdrs, 'body': body})
    return msgs


def build_streams(packets):
    streams = {}
    for src, dst, proto, payload in packets:
        feed_packet(streams, src, dst, proto, payload)
    return streams


def format_streams(streams, highlight=None):
    """把流整理成可读行列表。highlight: {(ip,port)...} 目标端点集合，标为进程相关。"""
    lines = []
    highlight = highlight or set()
    for key, st in sorted(streams.items(), key=lambda kv: str(kv[0])):
        a, b = key
        rel = ' ★进程' if (a in highlight or b in highlight) else ''
        if st.sni is None:
            # SNI 懒提取：用重组后的完整客户端流（ClientHello 可能跨多个 TCP 段）
            for d in (st.ta, st.tb):
                buf = bytes(d.data)
                if buf[:1] == b'\x16' and len(buf) >= 9:
                    s = tls_sni(buf)
                    if s:
                        st.sni = s
                        break
        msgs_a = extract_http(bytes(st.ta.data))
        msgs_b = extract_http(bytes(st.tb.data))
        if st.sni:
            tag, meta = 'TLS', ' SNI=' + st.sni
        elif msgs_a or msgs_b:
            tag, meta = 'HTTP', ' HTTP'
        else:
            tag, meta = 'TCP', ''
        lines.append('[{}] {} <-> {}{}{}'.format(
            tag, '{}:{}'.format(*a), '{}:{}'.format(*b), meta, rel))
        if tag != 'HTTP':
            continue
        n = 0
        for d, arrow in ((st.ta, '→'), (st.tb, '←')):
            for msg in extract_http(bytes(d.data)):
                if n >= MAX_MSG_PER_STREAM:
                    break
                n += 1
                if msg['kind'] == 'request':
                    url = msg['target']
                    host = msg['headers'].get('host')
                    if host and url.startswith('/'):
                        url = 'http://{}{}'.format(host, url)
                    lines.append('    {} {}'.format(arrow, msg['method']) + ' ' + url)
                    hdrs = '  '.join('{}={}'.format(k, v) for k, v in list(msg['headers'].items())[:8])
                    lines.append('        Headers: ' + hdrs)
                else:
                    lines.append('    {} {}'.format(arrow, msg['status']))
                if msg['body']:
                    body = _fmt_body(msg['body'])
                    lines.append('        Body: {}'.format(body[:300]))
    return lines


# --------------------------------------------------------------------------
# 抓包（pktmon）与主流程
# --------------------------------------------------------------------------

def _run(cmd):
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def monitor(pid, resolve):
    print('监视模式，每 2 秒刷新一次，Ctrl+C 退出。')
    first = True
    try:
        while True:
            if not first:
                print('\n--- 刷新 ---')
            first = False
            show_connections(get_connections(pid, resolve))
            time.sleep(2)
    except KeyboardInterrupt:
        print('\n退出。')
    return 0


def capture(args):
    if not is_admin():
        print('抓包需要管理员权限。请用管理员终端重新运行；或加 --monitor 仅监视。', file=sys.stderr)
        return 1
    if not shutil.which('pktmon'):
        print('当前系统没有 pktmon（需要 Windows 10 1809 / Server 2019 及以上）。', file=sys.stderr)
        return 1

    conns = [] if args.full else get_connections(args.pid, args.resolve)
    print('\n进程当前连接：')
    show_connections(conns)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(args.output, exist_ok=True)
    etl = os.path.join(args.output, 'proc_{}_{}.etl'.format(args.pid, ts))
    pcapng = os.path.join(args.output, 'proc_{}_{}.pcapng'.format(args.pid, ts))
    txt = os.path.join(args.output, 'proc_{}_{}.requests.txt'.format(args.pid, ts))

    filter_added = False
    if not args.full:
        seen = set()
        filters = []
        for c in conns:
            ip, port = c['remote_ip'], c['remote_port']
            if not ip or not port:
                continue
            key = (ip, port)
            if key not in seen:
                seen.add(key)
                filters.append((c['proto'], ip, port))
        if filters:
            print('\n添加 pktmon 过滤器（{} 个）：'.format(len(filters)))
            _run(['pktmon', 'filter', 'remove'])
            for i, (proto, ip, port) in enumerate(filters):
                if i >= 30:
                    print('达到 pktmon 上限（32），仅保留前 30 个过滤器。', file=sys.stderr)
                    break
                dl = 'IPv6' if ':' in ip else 'IPv4'
                if _run(['pktmon', 'filter', 'add', 'pf{}'.format(i),
                         '-d', dl, '-t', proto, '-i', ip, '-p', str(port)]) == 0:
                    print('  - {} {}:{}'.format(proto, ip, port))
                else:
                    print('添加过滤器 {} {}:{} 失败'.format(proto, ip, port), file=sys.stderr)
            filter_added = True
        else:
            print('未找到该进程的活动连接，改为全量抓包。', file=sys.stderr)
    else:
        print('\n全量抓包模式。')

    started = False
    try:
        print('\n开始抓包...')
        if _run(['pktmon', 'start', '-c', '--pkt-size', '0',
                 '-f', etl, '-s', '512', '-m', 'circular']) != 0:
            print('pktmon start 失败（可能已有抓包在运行，请先执行 pktmon stop）。', file=sys.stderr)
            return 1
        started = True

        if args.duration > 0:
            deadline = time.time() + args.duration
            while time.time() < deadline:
                remain = max(0, int(deadline - time.time()))
                done = args.duration - remain
                print('  [{}] 已抓取 {}/{} 秒（剩余 {}）'.format(
                    datetime.datetime.now().strftime('%H:%M:%S'), done, args.duration, remain))
                time.sleep(1)
        else:
            print('抓包进行中，按 Ctrl+C 停止...')
            time.sleep(1 << 30)
    except KeyboardInterrupt:
        pass
    finally:
        if started:
            print('\n停止抓包...')
            _run(['pktmon', 'stop'])
        if filter_added:
            _run(['pktmon', 'filter', 'remove'])

    if not os.path.exists(etl):
        print('未生成 ETL 文件，抓包可能失败。', file=sys.stderr)
        return 1

    print('转换 pcapng...')
    _run(['pktmon', 'etl2pcap', etl, '-o', pcapng])

    print('\n完成！')
    print('  原始日志: {}'.format(etl))
    print('  pcapng  : {}'.format(pcapng))
    print('  请求导出: {}'.format(txt))

    print('\n=== 请求解析 ===')
    packets = []
    for _t, pkt in parse_pcapng(pcapng):
        d = decode_l2(pkt)
        if d:
            packets.append(d)
    streams = build_streams(packets)
    highlight = set((c['remote_ip'], c['remote_port']) for c in conns if c['remote_ip'])
    lines = format_streams(streams, highlight)
    if not lines:
        print('  未抓到任何 HTTP/TLS 流量。')
    else:
        for line in lines:
            print(line)
    try:
        with open(txt, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except OSError as e:
        print('写请求导出文件失败: {}'.format(e), file=sys.stderr)
    return 0


def analyze_only(path):
    print('解析 {} ...'.format(path))
    packets = []
    for _t, pkt in parse_pcapng(path):
        d = decode_l2(pkt)
        if d:
            packets.append(d)
    streams = build_streams(packets)
    lines = format_streams(streams)
    if not lines:
        print('  未抓到任何 HTTP/TLS 流量。')
    for line in lines:
        print(line)
    return 0


def main():
    ap = argparse.ArgumentParser(
        prog='Capture-NetworkRequests.py',
        description='抓取指定进程ID的网络请求并解析 HTTP/TLS（Windows，抓包基于系统自带 pktmon）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument('--pid', type=int, help='目标进程ID')
    ap.add_argument('--duration', type=int, default=30, help='抓包持续秒数，默认 30；0 表示直到 Ctrl+C')
    ap.add_argument('--output', default='captures', help='抓包输出目录，默认 ./captures')
    ap.add_argument('--monitor', action='store_true', help='仅实时监视连接，不抓包（无需管理员）')
    ap.add_argument('--full', action='store_true', help='全量抓包，不按该进程连接生成过滤器')
    ap.add_argument('--resolve', action='store_true', help='对连接做 DNS 反向解析，显示域名')
    ap.add_argument('--analyze', metavar='FILE', help='只解析已有的 pcapng 文件，不抓包')
    args = ap.parse_args()

    if args.analyze:
        return analyze_only(args.analyze)

    if not args.pid:
        ap.error('需要 --pid 或 --analyze')

    name = process_info(args.pid)
    if not name:
        print('找不到进程 ID {}'.format(args.pid), file=sys.stderr)
        return 1
    print('目标进程: {} (PID {})'.format(name, args.pid))

    if args.monitor:
        return monitor(args.pid, args.resolve)
    return capture(args)


if __name__ == '__main__':
    sys.exit(main())