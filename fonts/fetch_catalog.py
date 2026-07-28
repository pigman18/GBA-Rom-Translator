#!/usr/bin/env python3
"""Download third-party CJK BDF fonts into C:\\code\\gba\\fonts (catalog for GUI)."""
from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
TMP = ROOT / "_download"
UA = "gba-fonts-catalog/1.0"
# Direct github.com often hangs; local proxy (Clash etc.) preferred when available.
LOCAL_PROXY = "http://127.0.0.1:10809"
GH_MIRROR = "https://ghproxy.net/"


def _proxy_handler():
    """Prefer local HTTP proxy; fall back to direct (caller may still use GH_MIRROR)."""
    import os
    from urllib.request import ProxyHandler, build_opener

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or LOCAL_PROXY
    return build_opener(ProxyHandler({"http": proxy, "https": proxy}))


def _mirror(url: str) -> str:
    # With a working local proxy, hit GitHub directly (faster than public mirrors).
    return url


def fetch(url: str, *, retries: int = 4) -> bytes:
    last_err: Exception | None = None
    target = _mirror(url)
    opener = _proxy_handler()
    for attempt in range(1, retries + 1):
        try:
            req = Request(target, headers={"User-Agent": UA})
            with opener.open(req, timeout=300) as r:
                data = r.read()
            if len(data) < 1000:
                raise RuntimeError(f"too small ({len(data)} bytes)")
            return data
        except Exception as e:
            last_err = e
            print(f"  fetch attempt {attempt}/{retries} failed: {e}")
            # Fallback: try ghproxy without relying on broken direct path
            if attempt == 2 and url.startswith("https://github.com/"):
                target = GH_MIRROR + url
                print(f"  fallback mirror {target}")
    assert last_err is not None
    raise last_err


def save(url: str, dest: Path, *, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not force and dest.is_file() and dest.stat().st_size > 1000:
        print(f"skip exists {dest.relative_to(ROOT)}")
        return dest
    print(f"GET {url}")
    data = fetch(url)
    dest.write_bytes(data)
    print(f"  -> {dest.relative_to(ROOT)} ({len(data)} bytes)")
    return dest


def unzip_bdfs(zip_path: Path, out_dir: Path, name_map: dict[str, str] | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".bdf"):
                continue
            raw_name = Path(info.filename).name
            out_name = (name_map or {}).get(raw_name, raw_name)
            dest = out_dir / out_name
            with zf.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            written.append(dest)
            print(f"  extract {dest.relative_to(ROOT)}")
    return written


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)

    # --- Zpix 12px (tight) ---
    save(
        "https://github.com/SolidZORO/zpix-pixel-font/releases/download/v3.1.11/zpix.bdf",
        ROOT / "zpix" / "zpix-12.bdf",
    )

    # --- Ark Pixel (prefer zh_cn) ---
    ark_jobs = [
        (
            "https://github.com/TakWolf/ark-pixel-font/releases/download/2026.07.20/ark-pixel-font-12px-monospaced-bdf-v2026.07.20.zip",
            ROOT / "ark-pixel" / "12px-monospaced",
        ),
        (
            "https://github.com/TakWolf/ark-pixel-font/releases/download/2026.07.20/ark-pixel-font-12px-proportional-bdf-v2026.07.20.zip",
            ROOT / "ark-pixel" / "12px-proportional",
        ),
        (
            "https://github.com/TakWolf/ark-pixel-font/releases/download/2026.07.20/ark-pixel-font-10px-monospaced-bdf-v2026.07.20.zip",
            ROOT / "ark-pixel" / "10px-monospaced",
        ),
        (
            "https://github.com/TakWolf/ark-pixel-font/releases/download/2026.07.20/ark-pixel-font-16px-monospaced-bdf-v2026.07.20.zip",
            ROOT / "ark-pixel" / "16px-monospaced",
        ),
    ]
    for url, out in ark_jobs:
        existing = list(out.glob("*.bdf")) if out.is_dir() else []
        if existing:
            print(f"skip exists {out.relative_to(ROOT)} ({len(existing)} bdf)")
            continue
        zp = save(url, TMP / Path(url).name)
        unzip_bdfs(zp, out)

    # --- Fusion Pixel (better CJK coverage at 12px) ---
    fus_jobs = [
        (
            "https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.07.20/fusion-pixel-font-12px-monospaced-bdf-v2026.07.20.zip",
            ROOT / "fusion-pixel" / "12px-monospaced",
        ),
        (
            "https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.07.20/fusion-pixel-font-12px-proportional-bdf-v2026.07.20.zip",
            ROOT / "fusion-pixel" / "12px-proportional",
        ),
        (
            "https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.07.20/fusion-pixel-font-10px-monospaced-bdf-v2026.07.20.zip",
            ROOT / "fusion-pixel" / "10px-monospaced",
        ),
    ]
    for url, out in fus_jobs:
        existing = list(out.glob("*.bdf")) if out.is_dir() else []
        if existing:
            print(f"skip exists {out.relative_to(ROOT)} ({len(existing)} bdf)")
            continue
        zp = save(url, TMP / Path(url).name)
        unzip_bdfs(zp, out)

    # --- WenQuanYi Bitmap Song BDF ---
    wqy_out = ROOT / "wenquanyi"
    wqy_existing = list(wqy_out.glob("*.bdf")) if wqy_out.is_dir() else []
    wqy_ok = bool(wqy_existing)
    if wqy_ok:
        print(f"skip exists wenquanyi/ ({len(wqy_existing)} bdf)")
    wqy_candidates = [
        # Debian orig source (contains .bdf); CN mirrors work without proxy
        "https://mirrors.tuna.tsinghua.edu.cn/debian/pool/main/x/xfonts-wqy/xfonts-wqy_1.0.0~rc1.orig.tar.gz",
        "https://mirrors.ustc.edu.cn/debian/pool/main/x/xfonts-wqy/xfonts-wqy_1.0.0~rc1.orig.tar.gz",
        "https://deb.debian.org/debian/pool/main/x/xfonts-wqy/xfonts-wqy_1.0.0~rc1.orig.tar.gz",
        # SF BDF package (often HTML interstitial / slow)
        "https://downloads.sourceforge.net/project/wqy/wqy-bitmapfont/1.0.0-RC1/wqy-bitmapsong-bdf-1.0.0-RC1.tar.gz",
    ]
    for url in wqy_candidates:
        if wqy_ok:
            break
        try:
            import tarfile

            # Prefer direct for tuna/ustc (local proxy sometimes stalls CN CDNs)
            if "mirrors.tuna" in url or "mirrors.ustc" in url:
                from urllib.request import urlopen as _direct_open

                req = Request(url, headers={"User-Agent": UA})
                with _direct_open(req, timeout=180) as r:
                    raw = r.read()
            else:
                raw = fetch(url)
            if len(raw) < 1000 or raw[:1] == b"<":
                raise RuntimeError(f"not a tarball ({len(raw)} bytes, magic={raw[:4]!r})")
            out = wqy_out
            out.mkdir(parents=True, exist_ok=True)
            mode = "r:gz" if raw[:2] == b"\x1f\x8b" else "r:"
            with tarfile.open(fileobj=io.BytesIO(raw), mode=mode) as tf:
                for m in tf.getmembers():
                    if not m.isfile() or not m.name.lower().endswith(".bdf"):
                        continue
                    # Skip Latin Liberation samples bundled in debian orig
                    base = Path(m.name).name.lower()
                    if base.startswith("liberation"):
                        continue
                    dest = out / Path(m.name).name
                    f = tf.extractfile(m)
                    if f is None:
                        continue
                    dest.write_bytes(f.read())
                    print(f"  wqy {dest.relative_to(ROOT)}")
                    wqy_ok = True
            if wqy_ok:
                break
        except Exception as e:
            print(f"wqy fail {url}: {e}")

    if not wqy_ok:
        print("WARNING: wenquanyi BDF not fetched")

    # Prefer zh_cn / zh_hans copies at top-level shortcuts for GUI browsing
    shortcuts: list[tuple[Path, Path]] = []
    for p in (ROOT / "ark-pixel").rglob("*.bdf"):
        n = p.name.lower()
        if "zh_cn" in n or "zh_hans" in n:
            shortcuts.append((p, ROOT / "shortcuts" / f"ark-{p.parent.name}-{p.name}"))
    for p in (ROOT / "fusion-pixel").rglob("*.bdf"):
        n = p.name.lower()
        if "zh_hans" in n or "zh_cn" in n:
            shortcuts.append((p, ROOT / "shortcuts" / f"fusion-{p.parent.name}-{p.name}"))
    for src, dst in shortcuts:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"shortcut {dst.relative_to(ROOT)}")

    print("done")


if __name__ == "__main__":
    main()
