#!/usr/bin/env python3
"""
OpenCode OpenAI-compatible proxy.

Runs an OpenCode headless server via `opencode serve` (the same HTTP server
the desktop app uses internally), then exposes an OpenAI /v1 API that forwards
chat requests to OpenCode and streams the assistant reply back.

No reverse-engineering of the desktop app is used: the proxy spawns its own
OpenCode server with a fixed port and a random Basic-auth password.

Typical usage:
    python opencode_openai_proxy.py --port 8080
    cloudflared tunnel --url http://127.0.0.1:8080

Endpoints:
    GET  /v1/models                       list configured models
    POST /v1/chat/completions             forward a chat request (stream supported)
    GET/POST /v1/sessions[/:id]           list / open / inspect sessions
    GET  /health                          liveness probe

Config (config.yaml next to this file, overridable with --config):
    port: 8080
    host: 127.0.0.1
    directory: C:\\code\\opencode-free
    agent: build
    default_model: opencode/deepseek-v4-flash-free
    models: [opencode/deepseek-v4-flash-free]
    opencode_port: 4096
    session: current

Overrides (skip spawning your own server):
    --url http://127.0.0.1:4096           server base URL
    --username / --password               server credentials
    env: OPENCODE_SERVER_URL, OPENCODE_SERVER_USERNAME, OPENCODE_SERVER_PASSWORD

Client hints:
    X-OpenCode-Session: <id|new|current>  pick the target session per request
    X-OpenCode-Conversation: <client-side unique id>   stable per-conversation id.
                                          Sessions are created LAZILY on the first
                                          request and mapped to (directory, id) in
                                          session-map.json, so follow-up requests
                                          reuse the same OpenCode session (pattern:
                                          the agent conversation id).
    X-OpenCode-Directory: <abs path>       project directory per request
                                          (also accepted as body `directory`).
                                          Sessions/current/chat are scoped to it;
                                          when it has no session, one is created
                                          automatically on first use.
    Per-request example:
        POST /v1/chat/completions
        X-OpenCode-Conversation: conv_abc123
        X-OpenCode-Directory: C:\\Users\\you\\Projects\\myapp
        {"messages": [{"role": "user", "content": "hi"}], "model": "opencode/deepseek-v4-flash-free"}
"""

import argparse
import atexit
import base64
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

DEFAULT_AGENT = "build"
DEFAULT_MODEL = "opencode/deepseek-v4-flash-free"
DEFAULT_DIRECTORY = os.getcwd()
READY_RE = re.compile(r"opencode server listening on http://([^:]+):(\d+)")
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

TUNNEL_URL = None
TUNNEL_PROC = None
TUNNEL_LOG = None
SERVE_PROC = None

SESSION_MAP = {}
SESSION_MAP_PATH = None


def _load_session_map(path):
    global SESSION_MAP
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        SESSION_MAP = {(item.get("directory"), item.get("id")): item.get("session") for item in data}
    except (OSError, ValueError):
        SESSION_MAP = {}


def _save_session_map():
    if not SESSION_MAP_PATH:
        return
    data = [{"directory": d, "id": cid, "session": sid} for (d, cid), sid in SESSION_MAP.items()]
    tmp = SESSION_MAP_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, SESSION_MAP_PATH)

try:
    import yaml
except ImportError:
    yaml = None

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path):
    """Load config.yaml; returns a dict (empty when the file is absent)."""
    if not path or not os.path.exists(path):
        return {}
    if yaml is None:
        raise SystemExit("config.yaml requires PyYAML:  pip install pyyaml")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# --------------------------------------------------------------------------
# OpenCode server bootstrap
# --------------------------------------------------------------------------


def _find_free_port(start=4096, attempts=20):
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port found")


def spawn_opencode_server(port=None, password=None, log_dir=None):
    """Start `opencode serve` and return (base_url, username, password)."""
    port = _find_free_port(port or 4096)
    password = password or os.environ.get("OPENCODE_SERVER_PASSWORD") or uuid.uuid4().hex
    username = "opencode"
    log_dir = log_dir or os.path.dirname(os.path.abspath(__file__))
    serve_log = os.path.join(log_dir, "oc-serve.log")
    commands = ["opencode", "serve", "--port", str(port), "--hostname", "127.0.0.1"]

    with open(serve_log, "w", encoding="utf-8") as fh:
        fh.write("")
    with open(serve_log, "a", encoding="utf-8") as log_fh:
        try:
            proc = subprocess.Popen(
                ["cmd", "/c"] + commands,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env={**os.environ, "OPENCODE_SERVER_PASSWORD": password},
            )
        except OSError:
            raise RuntimeError(
                "could not launch `opencode`; install it with:  npm install -g opencode-ai"
            ) from None
    SERVE_PROC = proc

    base_url = None
    deadline = time.time() + 40
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("opencode serve exited early:\n" + _tail(serve_log, 10))
        time.sleep(0.25)
        with open(serve_log, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            if size < 400:
                size = 400
            fh.seek(size - min(size, 4096))
            text = fh.read()
        match = READY_RE.search(text)
        if match:
            base_url = f"http://127.0.0.1:{match.group(2)}"
            break
    if not base_url:
        proc.kill()
        raise RuntimeError("timed out waiting for opencode serve:\n" + _tail(serve_log, 10))
    return base_url, username, password


def _find_cloudflared():
    env = os.environ.get("CLOUDFLARED")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("cloudflared")
    if found:
        return found
    for candidate in (
        r"C:\Windows\System32\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def spawn_cloudflared_tunnel(target_url, log_dir=None):
    """Start a quick (trycloudflare) tunnel to target_url; return the public URL."""
    global TUNNEL_PROC, TUNNEL_LOG
    binary = _find_cloudflared()
    if not binary:
        raise RuntimeError("cloudflared.exe not found (set CLOUDFLARED env var to its path)")
    log_dir = log_dir or os.path.dirname(os.path.abspath(__file__))
    TUNNEL_LOG = os.path.join(log_dir, "cf.log")
    with open(TUNNEL_LOG, "w", encoding="utf-8") as fh:
        fh.write("")
    with open(TUNNEL_LOG, "a", encoding="utf-8") as log_fh:
        TUNNEL_PROC = subprocess.Popen(
            [binary, "tunnel", "--url", target_url, "--no-autoupdate",
             "--logfile", TUNNEL_LOG, "--loglevel", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    deadline = time.time() + 120
    while time.time() < deadline:
        if TUNNEL_PROC.poll() is not None:
            raise RuntimeError("cloudflared exited early:\n" + _tail(TUNNEL_LOG, 10))
        match = TUNNEL_URL_RE.search(_tail(TUNNEL_LOG, 40))
        if match:
            return match.group(0)
        time.sleep(1)
    raise RuntimeError("timed out waiting for tunnel URL:\n" + _tail(TUNNEL_LOG, 10))


def _cleanup_child_processes():
    global TUNNEL_PROC, SERVE_PROC
    for proc in (TUNNEL_PROC, SERVE_PROC):
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def _tail(path, n):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-n:])
    except OSError:
        return ""


# --------------------------------------------------------------------------
# OpenCode API client
# --------------------------------------------------------------------------


def _request(base_url, path, method="GET", headers=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urlrequest.Request(base_url + path, data=data, headers=headers or {}, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urlerror.HTTPError as err:
        raw = err.read().decode() or "null"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return err.code, parsed
    except Exception as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc


class OpenCodeClient:
    def __init__(self, base_url, username, password, directory=DEFAULT_DIRECTORY):
        self.base_url = base_url.rstrip("/")
        self.directory = directory
        self.username = username
        self.password = password
        self.auth_header = "Basic " + base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()

    def _headers(self, directory=None):
        headers = {"Authorization": self.auth_header, "Content-Type": "application/json"}
        dirname = directory or self.directory
        if dirname:
            headers["x-opencode-directory"] = dirname
        return headers

    def get(self, path, timeout=30, directory=None):
        status, data = _request(self.base_url, path, headers=self._headers(directory), timeout=timeout)
        if status >= 400:
            raise RuntimeError(f"GET {path}: HTTP {status} {data}")
        return data

    def post(self, path, body=None, timeout=300, directory=None):
        status, data = _request(
            self.base_url, path, method="POST", headers=self._headers(directory),
            body=body, timeout=timeout,
        )
        if status >= 400:
            raise RuntimeError(f"POST {path}: HTTP {status} {data}")
        return data

    def create_session(self, title=None, model=None, agent=None, directory=None):
        body = {}
        if title:
            body["title"] = title
        if model and "/" in model:
            provider_id, model_id = model.split("/", 1)
            body["model"] = {"providerID": provider_id, "id": model_id}
        if agent:
            body["agent"] = agent
        return self.post("/session", body=body, directory=directory)

    def list_sessions(self, directory=None):
        return self.get("/session", directory=directory)

    def current_session(self, model=None, agent=None, directory=None, create=True):
        sessions = self.list_sessions(directory=directory)
        if not sessions:
            if not create:
                return None
            return self.create_session(title="opencode-proxy", model=model, agent=agent, directory=directory)
        sessions = sorted(sessions, key=lambda s: s.get("time", {}).get("updated", 0), reverse=True)
        return sessions[0]

    def session_model(self, session_id):
        info = self.get(f"/session/{session_id}")
        model = (info or {}).get("model")
        if model:
            return f"{model.get('providerID', '')}/{model.get('id', '')}"
        return None

    def prompt(self, session_id, parts, system=None, agent=None, model=None, directory=None):
        payload = {"parts": parts}
        if system:
            payload["system"] = system
        if agent:
            payload["agent"] = agent
        if model and "/" in model:
            provider_id, model_id = model.split("/", 1)
            payload["model"] = {"providerID": provider_id, "modelID": model_id}
        return self.post(f"/session/{session_id}/message", body=payload, timeout=600, directory=directory)

    def delete(self, path, timeout=30):
        status, data = _request(self.base_url, path, method="DELETE", headers=self._headers(), timeout=timeout)
        if status >= 400:
            raise RuntimeError(f"DELETE {path}: HTTP {status} {data}")
        return status


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------


def _sse_reader(client, session_id, on_event, stop):
    req = urlrequest.Request(client.base_url + "/event", headers={"Authorization": client.auth_header}, method="GET")
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(15)
    try:
        with urlrequest.urlopen(req, timeout=None) as resp:
            pending = b""
            while not stop.is_set():
                try:
                    line = resp.readline()
                except (socket.timeout, TimeoutError):
                    continue
                if not line:
                    break
                pending += line
                if pending.endswith(b"\n\n"):
                    frame = pending.decode("utf-8", "replace")
                    pending = b""
                    for block in frame.split("\n\n"):
                        for text in block.splitlines():
                            if text.startswith("data:"):
                                raw = text[5:].strip()
                                if raw:
                                    try:
                                        on_event(session_id, json.loads(raw))
                                    except json.JSONDecodeError:
                                        pass
    except Exception:
        pass
    finally:
        socket.setdefaulttimeout(previous)


def stream_prompt(client, session_id, parts, system=None, agent=None, model=None, directory=None):
    """Send a prompt and yield (delta, finish, final_message, error) tuples."""
    events = queue.Queue()
    stop = threading.Event()

    def poster():
        try:
            final = client.prompt(session_id, parts, system=system, agent=agent, model=model, directory=directory)
            events.put(("done", final))
        except Exception as exc:
            events.put(("error", str(exc)))

    def on_event(sid, payload):
        if sid != session_id:
            return
        events.put(("event", payload))

    threads = [
        threading.Thread(target=poster, daemon=True),
        threading.Thread(target=_sse_reader, args=(client, session_id, on_event, stop), daemon=True),
    ]
    for thread in threads:
        thread.start()

    emitted_text = 0
    final_message = None
    error_text = None
    while True:
        kind, value = events.get()
        if kind == "event":
            etype = value.get("type", "")
            props = value.get("properties", {})
            if etype == "message.part.delta" and props.get("field") == "text":
                delta = props.get("delta") or ""
                if delta:
                    emitted_text += len(delta)
                    yield ("delta", delta, None, None)
            elif etype == "session.error":
                if props.get("sessionID") != session_id:
                    continue
                err = props.get("error", {})
                error_text = err.get("message") if isinstance(err, dict) else str(err)
            continue
        if kind == "done":
            final_message = value
            stop.set()
            break
        if kind == "error":
            error_text = value
            stop.set()
            break

    if error_text:
        yield ("error", error_text, None, None)
        return
    if not final_message:
        yield ("error", "no response from OpenCode", None, None)
        return

    texts = [
        part.get("text", "")
        for part in (final_message or {}).get("parts", [])
        if isinstance(part, dict) and part.get("type") == "text"
    ]
    full_text = "\n".join(texts)
    finish = (final_message.get("info") or {}).get("finish") or "stop"
    if emitted_text < len(full_text):
        yield ("delta", full_text[emitted_text:], None, None)
    yield ("finish", "", final_message, finish)


# --------------------------------------------------------------------------
# OpenAI-compatible HTTP server
# --------------------------------------------------------------------------


def _extract_prompt(messages):
    """Return (prompt_text, system_text) from an OpenAI messages array."""
    system_text = ""
    prompt_text = ""
    for message in messages:
        role = message.get("role", "")
        content = message.get("content", "")
        if role == "system" and not system_text:
            if isinstance(content, str):
                system_text = content
            else:
                pieces = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                system_text = "".join(pieces)
        if role == "user":
            if isinstance(content, str):
                prompt_text = content
            else:
                pieces = []
                for chunk in content:
                    if not isinstance(chunk, dict):
                        continue
                    ctype = chunk.get("type")
                    if ctype in ("text", "input_text"):
                        pieces.append(chunk.get("text", ""))
                prompt_text = "".join(pieces)
    return prompt_text, system_text


def _sse_frame(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _split_model(model):
    if isinstance(model, str) and "/" in model:
        provider_id, model_id = model.split("/", 1)
        return provider_id, model_id
    return None, None


def _openai_session(info):
    model = None
    if info.get("model"):
        model = f"{info['model'].get('providerID', '')}/{info['model'].get('id', '')}"
    return {
        "id": info.get("id"),
        "object": "session",
        "title": info.get("title"),
        "model": model,
        "directory": info.get("directory"),
        "created_at": info.get("time", {}).get("created"),
        "updated_at": info.get("time", {}).get("updated"),
    }


ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>OpenCode 会话管理</title>
<style>
  body { font-family: "Segoe UI", system-ui, sans-serif; background: #0f1117; color: #e6e6e6; margin: 0; }
  header { padding: 16px 24px; background: #1a1f2b; border-bottom: 1px solid #2a3040; }
  header h1 { margin: 0; font-size: 18px; }
  header p { margin: 4px 0 0; color: #8b93a7; font-size: 12px; }
  main { padding: 24px; max-width: 1000px; margin: 0 auto; }
  .card { background: #171c27; border: 1px solid #2a3040; border-radius: 10px; padding: 16px; margin-bottom: 18px; }
  form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  input, select, button { padding: 8px 10px; border-radius: 6px; border: 1px solid #3a4256; background: #0f1117; color: #e6e6e6; font-size: 13px; }
  button { cursor: pointer; background: #2563eb; border-color: #2563eb; }
  button.danger { background: #b91c1c; border-color: #b91c1c; }
  button:disabled { opacity: .5; cursor: default; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #222837; vertical-align: top; }
  th { color: #8b93a7; font-weight: 600; }
  tr.clickable { cursor: pointer; }
  tr.clickable:hover td { background: #1d2330; }
  .id { font-family: Consolas, monospace; font-size: 11px; color: #5b8cff; }
  .time { color: #8b93a7; font-size: 11px; white-space: nowrap; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; background: #20304a; color: #8fb7ff; }
  .msg { border: 1px solid #2a3040; border-radius: 8px; padding: 10px 12px; margin: 8px 0; white-space: pre-wrap; font-size: 13px; line-height: 1.5; }
  .msg.user { background: #14213d; }
  .msg.assistant { background: #16251c; }
  .msg .meta { font-size: 11px; color: #8b93a7; margin-bottom: 4px; }
  #detail { display: none; }
  .spacer { flex: 1; }
  .status { color: #6ee7a0; font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>OpenCode 会话管理</h1>
  <p>代理后端: <span id="backend" class="status"></span> &nbsp;·&nbsp; 公网隧道: <span id="tunnel" class="status"></span></p>
</header>
<main>
  <div class="card">
    <form id="createForm">
      <input id="title" placeholder="会话标题（可选）" style="width: 200px;">
      <input id="dir" placeholder="工程目录（可选，留空用默认 C:\\code\\opencode-free）" style="width: 300px;">
      <select id="model"></select>
      <button type="submit">新增 Session</button>
      <span class="spacer"></span>
      <span id="status" class="status"></span>
    </form>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>标题</th><th>模型</th><th>目录</th><th>最近更新</th><th>ID</th><th>操作</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <p id="empty" style="color:#8b93a7; display:none;">暂无会话</p>
  </div>
  <div class="card" id="detail">
    <h3 id="detailTitle" style="margin:0 0 8px;"></h3>
    <div id="detailBody"></div>
  </div>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = ts => ts ? new Date(ts).toLocaleString() : "";

async function api(path, opts) {
  const dir = ($("#dir").value || "").trim();
  const headers = { ...(opts && opts.headers) };
  if (dir) headers["X-OpenCode-Directory"] = dir;
  opts = { ...opts, headers };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error?.message || r.statusText || ("HTTP " + r.status));
  return data;
}

async function loadModels() {
  const sel = $("#model");
  const d = await api("/v1/models");
  sel.innerHTML = "";
  for (const m of d.data) {
    const o = document.createElement("option");
    o.value = m.id; o.textContent = m.id;
    sel.appendChild(o);
  }
}

async function loadTunnel() {
  try {
    const t = await api("/tunnel");
    $("#tunnel").textContent = t.tunnel_url ? (t.running ? t.tunnel_url : t.tunnel_url + " (已停止)") : "未启动";
  } catch (err) { $("#tunnel").textContent = "未知"; }
}

async function loadSessions() {
  const d = await api("/v1/sessions");
  const tb = $("#rows");
  tb.innerHTML = "";
  $("#empty").style.display = d.data.length ? "none" : "block";
  for (const s of d.data) {
    const tr = document.createElement("tr");
    tr.className = "clickable";
    tr.innerHTML =
      "<td>" + esc(s.title) + "</td>" +
      "<td>" + esc(s.model || "-") + "</td>" +
      "<td style='font-size:11px;color:#8b93a7'>" + esc(s.directory) + "</td>" +
      "<td class='time'>" + fmt(s.updated_at) + "</td>" +
      "<td class='id'>" + esc(s.id) + "</td>" +
      "<td><button class='danger' data-del>" + "删除" + "</button></td>";
    tr.addEventListener("click", e => {
      if (e.target.dataset.del) return;
      showDetail(s);
    });
    tr.querySelector("[data-del]").addEventListener("click", async e => {
      e.stopPropagation();
      if (!confirm("删除会话 " + s.id + " ？")) return;
      try { await api("/v1/sessions/" + s.id, { method: "DELETE" }); await loadSessions(); }
      catch (err) { setStatus(err.message, true); }
    });
    tb.appendChild(tr);
  }
}

async function showDetail(s) {
  $("#detail").style.display = "block";
  $("#detailTitle").textContent = (s.title || s.id) + " — " + s.id;
  const body = $("#detailBody");
  body.innerHTML = '<p style="color:#8b93a7">加载中…</p>';
  try {
    const d = await api("/v1/sessions/" + s.id + "/messages");
    body.innerHTML = "";
    for (const m of d.data) {
      const div = document.createElement("div");
      div.className = "msg " + m.role;
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = (m.role === "assistant" ? "助手" : "用户") + " · " + fmt(m.created_at) + (m.tools.length ? " · 工具调用 x" + m.tools.length : "");
      div.appendChild(meta);
      div.appendChild(document.createTextNode(m.text || "(无文本)"));
      body.appendChild(div);
    }
    if (!d.data.length) body.innerHTML = '<p style="color:#8b93a7">该会话暂无消息</p>';
  } catch (err) {
    body.innerHTML = '<p style="color:#f87171">' + esc(err.message) + "</p>";
  }
}

function setStatus(msg, bad) {
  const el = $("#status");
  el.textContent = msg;
  el.style.color = bad ? "#f87171" : "#6ee7a0";
  setTimeout(() => { el.textContent = ""; }, 4000);
}

$("#createForm").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = e.target.querySelector("button");
  btn.disabled = true;
  setStatus("创建中…");
  try {
    const body = { title: $("#title").value || undefined, model: $("#model").value };
    const d = ($("#dir").value || "").trim();
    if (d) body.directory = d;
    const s = await api("/v1/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setStatus("已创建: " + s.id);
    $("#title").value = "";
    await loadSessions();
    showDetail(s);
  } catch (err) { setStatus(err.message, true); }
  finally { btn.disabled = false; }
});

(async () => {
  try { await loadModels(); await loadTunnel(); await loadSessions(); } catch (err) { setStatus(err.message, true); }
})();
</script>
</body>
</html>
"""


class OpenCodeProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OpenCodeProxy/1.0"

    client = None
    resolver = None
    default_model = DEFAULT_MODEL
    default_agent = DEFAULT_AGENT
    models = None
    model_ids = set()
    locks = {}

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json(status, {"error": {"message": message, "type": "opencode_proxy_error"}})

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("invalid JSON body")

    def _request_directory(self, body=None):
        raw = self.headers.get("X-OpenCode-Directory")
        if not raw and isinstance(body, dict) and isinstance(body.get("directory"), str):
            raw = body.get("directory")
        if not raw:
            return None
        return os.path.normpath(os.path.expanduser(raw))

    def _client_for(self, directory):
        if not directory or os.path.normpath(directory) == os.path.normpath(self.client.directory):
            return self.client
        return OpenCodeClient(self.client.base_url, self.client.username, self.client.password, directory=directory)

    def _resolve_session(self, requested, client=None, directory=None, conversation_id=None):
        client = client or self.client
        if conversation_id:
            key = (directory or client.directory, conversation_id)
            sid = SESSION_MAP.get(key)
            if sid:
                return sid
            session = client.create_session(
                title="opencode-proxy",
                model=self.default_model,
                agent=self.default_agent,
                directory=directory,
            )
            SESSION_MAP[key] = session.get("id")
            _save_session_map()
            return session.get("id")
        if requested in (None, "", "current"):
            return _resolve_current_session(client, self.default_model, self.default_agent, directory=directory)
        if requested == "new":
            session = client.create_session(
                title="opencode-proxy",
                model=self.default_model,
                agent=self.default_agent,
                directory=directory,
            )
            return session.get("id")
        return requested

    def _effective_model(self, requested):
        if isinstance(requested, str):
            if requested in self.model_ids:
                return requested
            provider_id, model_id = _split_model(requested)
            if provider_id and model_id:
                return f"{provider_id}/{model_id}"
        return self.default_model

    def _send_stream(self, generator):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            for chunk in generator:
                self.wfile.write(chunk.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
        elif path in ("/", "/admin"):
            body = ADMIN_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/v1/models":
            self.handle_models()
        elif path == "/tunnel":
            self._send_json(200, {
                "tunnel_url": TUNNEL_URL,
                "log": TUNNEL_LOG,
                "running": TUNNEL_PROC is not None and TUNNEL_PROC.poll() is None,
            })
        elif path == "/v1/sessions":
            self.handle_sessions_get()
        elif path.startswith("/v1/sessions/"):
            rest = path[len("/v1/sessions/"):]
            if rest.endswith("/messages"):
                self.handle_sessions_messages(rest[:-len("/messages")])
            else:
                self.handle_sessions_get(rest)
        else:
            self._send_error(404, f"not found: {path}")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/v1/chat/completions":
            self.handle_chat()
        elif path == "/v1/sessions":
            self.handle_sessions_post()
        else:
            self._send_error(404, f"not found: {path}")

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/v1/sessions/"):
            self.handle_sessions_delete(path[len("/v1/sessions/"):])
        else:
            self._send_error(404, f"not found: {path}")

    def handle_models(self):
        now = int(time.time())
        models = self.models or [{"id": self.default_model}]
        data = []
        for entry in models:
            if isinstance(entry, str):
                model_id, owned_by = entry, "opencode"
            else:
                model_id = entry.get("id", self.default_model)
                owned_by = entry.get("owned_by", "opencode")
            data.append({"id": model_id, "object": "model", "created": now, "owned_by": owned_by})
        self._send_json(200, {"object": "list", "data": data})

    def handle_sessions_get(self, session_id=None):
        if session_id:
            try:
                info = self.client.get(f"/session/{session_id}")
            except Exception as exc:
                self._send_error(404, str(exc))
                return
            self._send_json(200, _openai_session(info))
            return
        query = dict(pair.split("=", 1) for pair in urlparse(self.path).query.split("&") if "=" in pair)
        directory = self.headers.get("X-OpenCode-Directory") or query.get("directory")
        if directory:
            directory = os.path.normcase(os.path.normpath(os.path.expanduser(directory)))
        project_client = self._client_for(directory)
        try:
            items = project_client.list_sessions(directory=directory)
        except Exception as exc:
            self._send_error(502, str(exc))
            return
        if directory:
            items = [
                s for s in items
                if os.path.normcase(os.path.normpath((s.get("directory") or ""))) == directory
            ]
        self._send_json(200, {"object": "list", "data": [_openai_session(s) for s in items]})

    def handle_sessions_post(self):
        try:
            body = self._read_body()
        except ValueError as exc:
            self._send_error(400, str(exc))
            return
        if not isinstance(body, dict):
            body = {}
        title = body.get("title") or "opencode-proxy"
        model = self._effective_model(body.get("model"))
        agent = body.get("agent") or self.default_agent
        directory = self._request_directory(body)
        project_client = self._client_for(directory)
        try:
            info = project_client.create_session(title=title, model=model, agent=agent, directory=directory)
        except Exception as exc:
            self._send_error(502, str(exc))
            return
        self._send_json(200, _openai_session(info))

    def handle_sessions_messages(self, session_id):
        try:
            items = self.client.get(f"/session/{session_id}/message")
        except Exception as exc:
            self._send_error(404, str(exc))
            return
        out = []
        for msg in items or []:
            info = msg.get("info", {}) if isinstance(msg, dict) else {}
            parts = msg.get("parts", []) if isinstance(msg, dict) else []
            text = "".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and part.get("type") == "text"
            )
            tools = [
                part.get("tool")
                for part in parts
                if isinstance(part, dict) and part.get("type") == "tool"
            ]
            out.append({
                "id": info.get("id"),
                "role": info.get("role"),
                "text": text,
                "tools": tools,
                "created_at": info.get("time", {}).get("created"),
            })
        self._send_json(200, {"object": "list", "data": out})

    def handle_sessions_delete(self, session_id):
        try:
            self.client.delete(f"/session/{session_id}")
        except Exception as exc:
            self._send_error(502, str(exc))
            return
        self._send_json(200, {"object": "session", "id": session_id, "deleted": True})

    def handle_chat(self):
        try:
            body = self._read_body()
        except ValueError as exc:
            self._send_error(400, str(exc))
            return

        messages = body.get("messages", []) or []
        stream = bool(body.get("stream"))
        prompt_text, system_text = _extract_prompt(messages)
        if not prompt_text:
            self._send_error(400, "no user message found")
            return

        try:
            requested_session = self.headers.get("X-OpenCode-Session")
            if not requested_session and isinstance(body.get("session"), str):
                requested_session = body.get("session")
            conversation_id = self.headers.get("X-OpenCode-Conversation")
            if not conversation_id and isinstance(body.get("conversation_id"), str):
                conversation_id = body.get("conversation_id")
            directory = self._request_directory(body)
            project_client = self._client_for(directory)
            session_id = self._resolve_session(
                requested_session, client=project_client, directory=directory, conversation_id=conversation_id
            )
        except Exception as exc:
            self._send_error(503, f"cannot resolve session: {exc}")
            return

        model = self._effective_model(body.get("model"))
        lock = self.locks.setdefault(session_id, threading.Lock())
        with lock:
            parts = [{"type": "text", "text": prompt_text}]
            request_id = "chatcmpl-" + uuid.uuid4().hex[:24]
            created = int(time.time())

            def generator():
                yield _sse_frame({
                    "id": request_id, "object": "chat.completion.chunk", "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                })
                try:
                    for kind, text, final, finish in stream_prompt(
                        project_client, session_id, parts,
                        system=system_text or None,
                        agent=self.default_agent,
                        model=model,
                        directory=directory,
                    ):
                        if kind == "delta" and text:
                            yield _sse_frame({
                                "id": request_id, "object": "chat.completion.chunk", "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                            })
                        if kind == "error":
                            yield _sse_frame({
                                "id": request_id, "object": "chat.completion.chunk", "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            })
                            yield "data: [DONE]\n\n"
                            return
                    yield _sse_frame({
                        "id": request_id, "object": "chat.completion.chunk", "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": finish or "stop"}],
                    })
                except Exception as exc:
                    yield _sse_frame({
                        "id": request_id, "object": "chat.completion.chunk", "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    })
                yield "data: [DONE]\n\n"

            if stream:
                self._send_stream(generator())
                return

            collected = []
            finish = "stop"
            final = None
            for kind, text, final_msg, fin in stream_prompt(
                project_client, session_id, parts,
                system=system_text or None,
                agent=self.default_agent,
                model=model,
                directory=directory,
            ):
                if kind == "delta" and text:
                    collected.append(text)
                if kind == "error":
                    self._send_error(502, text or "OpenCode error")
                    return
                if kind == "finish":
                    finish = fin
                    final = final_msg
            usage = {}
            if final:
                tokens = (final.get("info") or {}).get("tokens") or {}
                usage = {
                    "prompt_tokens": tokens.get("input", 0),
                    "completion_tokens": tokens.get("output", 0),
                    "total_tokens": (tokens.get("input", 0) or 0) + (tokens.get("output", 0) or 0),
                }
            self._send_json(200, {
                "id": request_id, "object": "chat.completion", "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "".join(collected)},
                    "finish_reason": finish or "stop",
                }],
                "usage": usage,
            })


def _resolve_current_session(client, model=DEFAULT_MODEL, agent=DEFAULT_AGENT, directory=None):
    info = client.current_session(model=model, agent=agent, directory=directory)
    return info.get("id")


def main():
    parser = argparse.ArgumentParser(description="OpenCode OpenAI-compatible proxy")
    parser.add_argument("--config", default=os.environ.get("OPENCODE_CONFIG", DEFAULT_CONFIG_PATH))
    parser.add_argument("--port", type=int)
    parser.add_argument("--host")
    parser.add_argument("--url", help="OpenCode server base URL (skip spawning)")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--session", help="target session id ('current' by default)")
    parser.add_argument("--model")
    parser.add_argument("--agent")
    parser.add_argument("--directory")
    parser.add_argument("--opencode-port", type=int, help="port for spawned opencode serve")
    parser.add_argument("--tunnel", dest="tunnel", action="store_true", help="auto-start a cloudflared quick tunnel")
    parser.add_argument("--no-tunnel", dest="tunnel", action="store_false", help="do not start a tunnel")
    parser.set_defaults(tunnel=None)
    parser.add_argument("--check", action="store_true", help="print server info, then exit")
    args = parser.parse_args()

    cfg = load_config(args.config)
    log_dir = os.path.dirname(os.path.abspath(args.config))
    global SESSION_MAP_PATH
    SESSION_MAP_PATH = os.path.join(log_dir, "session-map.json")
    _load_session_map(SESSION_MAP_PATH)

    def pick(cli_value, env_key, cfg_key, default):
        if cli_value is not None:
            return cli_value
        if env_key and os.environ.get(env_key):
            return os.environ.get(env_key)
        value = cfg.get(cfg_key) if cfg_key is not None else None
        return default if value is None else value

    port = int(pick(args.port, "PORT", "port", 8080))
    host = pick(args.host, "HOST", "host", "127.0.0.1")
    directory = pick(args.directory, "OPENCODE_DIRECTORY", "directory", DEFAULT_DIRECTORY)
    agent = pick(args.agent, "OPENCODE_DEFAULT_AGENT", "agent", DEFAULT_AGENT)
    default_model = pick(args.model, "OPENCODE_DEFAULT_MODEL", "default_model", DEFAULT_MODEL)
    opencode_port = int(pick(args.opencode_port, None, "opencode_port", 4096))
    username_override = pick(args.username, "OPENCODE_SERVER_USERNAME", "username", None)
    password_override = pick(args.password, "OPENCODE_SERVER_PASSWORD", "password", None)
    url_override = pick(args.url, "OPENCODE_SERVER_URL", "url", None)
    session_override = pick(args.session, None, "session", None)
    if session_override == "current":
        session_override = None

    models = []
    for entry in cfg.get("models") or []:
        if isinstance(entry, str):
            models.append({"id": entry})
        elif isinstance(entry, dict) and entry.get("id"):
            models.append(entry)
    if not models:
        models = [{"id": default_model}]
    model_ids = {entry["id"] for entry in models}
    if default_model not in model_ids:
        models.append({"id": default_model})
        model_ids.add(default_model)

    tunnel_enabled = args.tunnel if args.tunnel is not None else bool(cfg.get("tunnel", True))

    base_url = url_override
    if base_url:
        base_url = base_url.rstrip("/")
        username = username_override or "opencode"
        password = password_override
        if not password:
            raise SystemExit("server url given but no password (--password / config password / OPENCODE_SERVER_PASSWORD)")
    else:
        base_url, username, password = spawn_opencode_server(port=opencode_port, password=password_override)

    client = OpenCodeClient(base_url, username, password, directory=directory)
    atexit.register(_cleanup_child_processes)
    print(f"[opencode-proxy] opencode backend (opencode serve): {base_url}", flush=True)
    print(f"[opencode-proxy] backend user: {username}", flush=True)
    print(f"[opencode-proxy] backend directory: {client.directory}", flush=True)
    print(f"[opencode-proxy] default model: {default_model}", flush=True)
    print(f"[opencode-proxy] default agent: {agent}", flush=True)
    print(f"[opencode-proxy] models: {sorted(model_ids)}", flush=True)

    if args.check:
        session = client.current_session(model=default_model, agent=agent)
        print(f"[opencode-proxy] current session: {session.get('id')}", flush=True)
        print(f"[opencode-proxy] current session model: {client.session_model(session.get('id'))}", flush=True)
        return

    if session_override:
        session_id = session_override
    else:
        info = client.current_session(model=default_model, agent=agent, create=False)
        session_id = info.get("id") if info else None
    print(f"[opencode-proxy] current session: {session_id or '(none - created lazily on first request)'}", flush=True)

    OpenCodeProxyHandler.client = client
    OpenCodeProxyHandler.default_model = default_model
    OpenCodeProxyHandler.default_agent = agent
    OpenCodeProxyHandler.models = models
    OpenCodeProxyHandler.model_ids = model_ids
    OpenCodeProxyHandler.resolver = staticmethod(
        (lambda: session_override) if session_override
        else (lambda: _resolve_current_session(client, default_model, agent))
    )

    httpd = ThreadingHTTPServer((host, port), OpenCodeProxyHandler)
    print(f"[opencode-proxy] OpenAI API listening on http://{host}:{port}  (this is the port cloudflared should target)", flush=True)
    print(f"[opencode-proxy] admin page: http://{host}:{port}/", flush=True)

    if tunnel_enabled:
        try:
            global TUNNEL_URL
            TUNNEL_URL = spawn_cloudflared_tunnel(f"http://127.0.0.1:{port}", log_dir=log_dir)
            print(f"[opencode-proxy] public tunnel: {TUNNEL_URL}   (Ctrl+C to stop)", flush=True)
        except Exception as exc:
            print(f"[opencode-proxy] tunnel not started: {exc}", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[opencode-proxy] shutdown", flush=True)
    finally:
        _cleanup_child_processes()


if __name__ == "__main__":
    main()