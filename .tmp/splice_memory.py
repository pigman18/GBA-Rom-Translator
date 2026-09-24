# -*- coding: utf-8 -*-
"""按行区间替换 MEMORY.md 的某一段（保留原有行尾）——一次性维护脚本。"""
import io
import sys
from pathlib import Path

P = Path(r"C:\code\GBA-Rom-Translator\.workbuddy\memory\MEMORY.md")
raw = P.read_bytes()
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n") - crlf
nl = b"\r\n" if crlf > lf else b"\n"
print("行尾: CRLF=%d LF=%d → 用 %r" % (crlf, lf, nl))

lines = raw.split(b"\n")
# 去掉每行尾部的 \r，便于统一处理
lines = [l[:-1] if l.endswith(b"\r") else l for l in lines]

a, b = int(sys.argv[1]), int(sys.argv[2])          # 1-indexed, 含端点
new_text = Path(sys.argv[3]).read_text(encoding="utf-8")
new_lines = new_text.split("\n")
if new_lines and new_lines[-1] == "":
    new_lines = new_lines[:-1]
new_lines = [l.encode("utf-8") for l in new_lines]

print("替换前 %d 行 → 替换 %d..%d（%d 行）为 %d 行"
      % (len(lines), a, b, b - a + 1, len(new_lines)))
lines[a - 1:b] = new_lines
out = nl.join(lines)
P.write_bytes(out)
print("替换后 %d 行, %d 字节" % (len(lines), len(out)))
