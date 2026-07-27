"""Font generation and management panel."""

import re
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

try:
    from PIL import Image, ImageDraw
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# ---------------------------------------------------------------------------
# BDF parsing helpers
# ---------------------------------------------------------------------------

GLYPH_W = 16
GLYPH_H = 16
BYTES_PER_GLYPH = 128


def _parse_bdf_for_preview(path: Path) -> tuple[dict, int]:
    """Quick BDF parse returning {encoding: data_tuple} and font_ascent."""
    glyphs: dict = {}
    font_ascent = 13
    text = path.read_text("utf-8", errors="replace")
    m = re.search(r"^FONT_ASCENT\s+(\d+)", text, re.MULTILINE)
    if m:
        font_ascent = int(m.group(1))

    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("STARTCHAR"):
            encoding = 0
            bbx_w = bbx_h = bbx_x = bbx_y = 0
            bitmap: list[bytearray] = []
            i += 1
            while i < n and not lines[i].startswith("BITMAP"):
                l = lines[i]
                if l.startswith("ENCODING"):
                    encoding = int(l.split()[1])
                elif l.startswith("BBX"):
                    parts = l.split()
                    bbx_w, bbx_h, bbx_x, bbx_y = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                i += 1
            if i < n:
                i += 1
            while i < n and not lines[i].startswith("ENDCHAR"):
                hex_str = lines[i].strip()
                if hex_str:
                    row_bytes = bytearray()
                    for j in range(0, len(hex_str), 2):
                        row_bytes.append(int(hex_str[j:j+2], 16))
                    bitmap.append(row_bytes)
                i += 1
            if encoding > 0 and bitmap:
                glyphs[encoding] = (bitmap, bbx_w, bbx_h, bbx_x, bbx_y)
        i += 1

    return glyphs, font_ascent


def _bdf_to_grid(glyph_data: tuple, font_ascent: int) -> list[list[int]]:
    """Convert BDF glyph data to 16x16 preview grid (12px ink + pad)."""
    bitmap_rows, bbx_w, bbx_h, bbx_x, bbx_y = glyph_data
    grid = [[0] * GLYPH_W for _ in range(GLYPH_H)]

    for row_idx in range(bbx_h):
        if row_idx >= len(bitmap_rows):
            break
        row_bytes = bitmap_rows[row_idx]
        py = font_ascent - bbx_y - bbx_h + 1 + row_idx
        if py < 0 or py >= GLYPH_H:
            continue
        for col in range(bbx_w):
            byte_idx = col // 8
            bit_idx = 7 - (col % 8)
            if byte_idx < len(row_bytes) and (row_bytes[byte_idx] & (1 << bit_idx)):
                px = bbx_x + col
                if 0 <= px < GLYPH_W:
                    grid[py][px] = 1

    return grid


# ---------------------------------------------------------------------------
# .bin file preview
# ---------------------------------------------------------------------------

def _bin_to_grid(glyph_bytes: bytearray, glyph_index: int) -> list[list[int]]:
    """Extract a 16x16 grid from a 128B TL/BL/TR/BR 4bpp glyph."""
    grid = [[0] * GLYPH_W for _ in range(GLYPH_H)]
    off = glyph_index * BYTES_PER_GLYPH
    if off + BYTES_PER_GLYPH > len(glyph_bytes):
        return grid
    for tile_col in range(2):
        for tile_row in range(2):
            ti = tile_col * 2 + tile_row
            tile_off = off + ti * 32
            for ty in range(8):
                for tx in range(4):
                    byte_idx = tile_off + ty * 4 + tx
                    byte = glyph_bytes[byte_idx]
                    # left = high nibble (Font_Patch / Meowth engine)
                    px = tile_col * 8 + tx * 2
                    py = tile_row * 8 + ty
                    if (byte >> 4) & 0x0F:
                        grid[py][px] = 1
                    if byte & 0x0F:
                        grid[py][px + 1] = 1
    return grid


def _lookup_slot(ch: str, charmap_text: str) -> int | None:
    """Look up the charmap slot index for a Unicode character."""
    pat = re.compile(r"^([0-9A-Fa-f]+)=" + re.escape(ch) + r"$", re.MULTILINE)
    m = pat.search(charmap_text)
    if not m:
        return None
    hex_val = int(m.group(1), 16)
    lead = (hex_val >> 8) & 0xFF
    trail = hex_val & 0xFF
    lead_adj = lead - 1
    if lead >= 6:
        lead_adj -= 1
    if lead >= 0x1B:
        lead_adj -= 1
    return lead_adj * 256 + trail


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_DEFAULT_GAME = "POKEMON_RUBY_AXVJ00"


def _root() -> Path:
    return Path(__file__).resolve().parents[4]


def _game_id() -> str:
    from ...config_loader import load_game_config
    return load_game_config(_DEFAULT_GAME)["game_id"]


def _font_patch_cfg() -> dict:
    from ...config_loader import load_game_config
    return load_game_config(_DEFAULT_GAME).get("font_patch", {})


def _font_prefix() -> str:
    return _font_patch_cfg().get("font_bin_prefix", "PokeRSFontChs")


def _font_slot_name(i: int) -> str:
    slots = _font_patch_cfg().get("font_slots", [])
    return slots[i]["label"] if i < len(slots) else f"Slot{i}"


def _font_slot_size(i: int) -> int:
    slots = _font_patch_cfg().get("font_slots", [])
    if i >= len(slots):
        return 0xE0000
    sl = slots[i]
    if "slot_size" in sl:
        return sl["slot_size"]
    return sl.get("glyph_count", 7168) * sl.get("bytes_per_glyph", 128)


def _font_normal_bin_name() -> str:
    prefix = _font_prefix()
    return f"{prefix}Normal(0x{_font_slot_size(0):X}).bin"


def _font_small_bin_name() -> str:
    prefix = _font_prefix()
    return f"{prefix}Small(0x{_font_slot_size(1) if len(_font_patch_cfg().get('font_slots', [])) > 1 else 0xE0000:X}).bin"


def _get_fonts_dir() -> Path:
    return _root() / "work" / _game_id() / "graphic" / "fonts"


def _get_font_selection_file() -> Path:
    return _root() / "work" / _game_id() / ".active_font"


def _get_build_chinese_font_script() -> Path:
    return _root() / "scripts" / "build_chinese_font.py"


def _get_charmap() -> Path:
    from ...config_loader import get_charmap_path
    return get_charmap_path(_game_id())


def _list_generated_fonts() -> list[dict]:
    fonts_dir = _get_fonts_dir()
    active = _load_active_font()
    results: list[dict] = []

    results.append({
        "name": "(默认内置)",
        "dir": ".",
        "is_active": active in (None, "", "default"),
    })

    if fonts_dir.is_dir():
        for entry in sorted(fonts_dir.iterdir()):
            if not entry.is_dir():
                continue
            normal = entry / _font_normal_bin_name()
            results.append({
                "name": entry.name,
                "dir": entry.name,
                "has_normal": normal.is_file(),
                "is_active": entry.name == active,
            })

    return results


def _load_active_font() -> str | None:
    f = _get_font_selection_file()
    if f.is_file():
        return f.read_text("utf-8").strip()
    return None


def _save_active_font(name: str) -> None:
    _get_font_selection_file().write_text(name.strip(), "utf-8")


def _activate_font(font_dir: str) -> str:
    fonts_dir = _get_fonts_dir()

    prefix = _font_prefix()
    normal_name = _font_normal_bin_name()
    small_name = _font_small_bin_name()

    copied = 0
    if font_dir == "." or font_dir == "default":
        for slot_label, dst_name in [("Normal", normal_name), ("Small", small_name)]:
            us_name = f"{prefix}{slot_label}_unshadow(0x{_font_slot_size(0 if slot_label == 'Normal' else 1):X}).bin"
            src = _root() / "graphic" / "fonts" / us_name
            dst = fonts_dir / dst_name
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
                copied += 1
    else:
        src = fonts_dir / font_dir
        src_files = {
            normal_name: fonts_dir / normal_name,
            small_name: fonts_dir / small_name,
        }
        if not (src / small_name).is_file():
            src_files.pop(small_name, None)
        for src_name, dst in src_files.items():
            f = fonts_dir / font_dir / src_name
            if f.is_file():
                dst.write_bytes(f.read_bytes())
                copied += 1

    if copied == 0:
        return "未找到有效的字库文件"
    _save_active_font(font_dir if font_dir != "." else "default")
    return f"已激活字库: {font_dir} ({copied}个文件)"


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------

_PREVIEW_CHARS = "宝可梦"


def _make_preview_image(grids: list, avail_w: int) -> Image.Image:
    """Build a PIL image from (char, grid) tuples (vertical layout)."""
    if not _HAS_PIL:
        return Image.new("RGB", (10, 10))

    n = len(grids)
    if avail_w < 100:
        avail_w = 600

    px_per_char = min(10, (avail_w - 18) // GLYPH_W)
    PIXEL = max(3, px_per_char)
    cell_w = GLYPH_W * PIXEL
    cell_h = GLYPH_H * PIXEL + 20
    SEP = 4

    canvas_w = cell_w + 12
    canvas_h = n * cell_h + (n - 1) * SEP + 12

    img = Image.new("RGB", (canvas_w, canvas_h), (30, 30, 30))
    draw = ImageDraw.Draw(img)

    BG = (16, 24, 40)
    FG = (200, 216, 240)
    GRID = (50, 60, 80)

    for i, (ch, grid) in enumerate(grids):
        ox = 6
        oy = 6 + i * cell_h + i * SEP

        for y in range(GLYPH_H):
            for x in range(GLYPH_W):
                color = FG if grid[y][x] else BG
                draw.rectangle(
                    [ox + x * PIXEL, oy + y * PIXEL + 20,
                     ox + x * PIXEL + PIXEL - 1, oy + y * PIXEL + PIXEL - 1 + 20],
                    fill=color,
                )

        for y in range(GLYPH_H + 1):
            py = oy + y * PIXEL + 20 - 1
            draw.line([ox - 1, py, ox + cell_w - 1, py], fill=GRID, width=1)
        for x in range(GLYPH_W + 1):
            px = ox + x * PIXEL - 1
            draw.line([px, oy + 20 - 1, px, oy + cell_h], fill=GRID, width=1)

        try:
            lx = ox + cell_w // 2
            _, _, tw, _ = draw.textbbox((0, 0), ch, font=None)
            draw.text((lx - tw // 2, oy + 2), ch, fill=(160, 170, 190))
        except Exception:
            pass

    return img


# ---------------------------------------------------------------------------
# FontPanel UI
# ---------------------------------------------------------------------------

class FontPanel(ctk.CTkFrame):
    """Tab content for font generation and selection."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._generating = False
        self._build_ui()
        self._refresh_font_list()

    def _build_ui(self):
        # ---- Top: Generation section ----
        ctk.CTkLabel(
            self, text="生成自定义字库",
            font=("", 16, "bold"),
        ).pack(anchor="w", pady=(8, 8))

        # BDF path
        bdf_row = ctk.CTkFrame(self, fg_color="transparent")
        bdf_row.pack(fill="x", pady=3)
        ctk.CTkLabel(bdf_row, text="BDF 字体:", width=70).pack(side="left")
        self.bdf_path_var = ctk.StringVar()
        ctk.CTkEntry(bdf_row, textvariable=self.bdf_path_var, width=240).pack(
            side="left", padx=(0, 6))
        ctk.CTkButton(
            bdf_row, text="浏览", width=60,
            command=self._browse_bdf,
        ).pack(side="left")

        # Name + preview + generate + progress
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x", pady=3)
        ctk.CTkLabel(action_row, text="名称:", width=35).pack(side="left")
        self.font_name_var = ctk.StringVar()
        ctk.CTkEntry(action_row, textvariable=self.font_name_var, width=140).pack(
            side="left", padx=(0, 6))
        ctk.CTkButton(
            action_row, text="预览", width=60, height=28,
            command=self._preview_bdf,
            fg_color="#7c3aed", hover_color="#6d28d9",
        ).pack(side="left", padx=(0, 6))
        self.gen_button = ctk.CTkButton(
            action_row, text="生成字库", height=28,
            command=self._generate_font,
            fg_color="#2563eb", hover_color="#1d4ed8",
        )
        self.gen_button.pack(side="left", padx=(0, 6))
        self.gen_progress = ctk.CTkProgressBar(action_row, width=80)
        self.gen_progress.pack(side="left", padx=(0, 4))
        self.gen_progress.set(0)
        self.gen_status = ctk.CTkLabel(action_row, text="", font=("", 11))
        self.gen_status.pack(side="left")

        # ---- Bottom: Left (font list) | Right (preview) ----
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="both", expand=True, pady=(0, 4))

        # -- Left: Font selection --
        left = ctk.CTkFrame(bottom, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 8))

        title_row = ctk.CTkFrame(left, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(title_row, text="选择字库",
                      font=("", 14, "bold")).pack(side="left")
        self.use_button = ctk.CTkButton(
            title_row, text="使用所选字库", height=26,
            command=self._activate_selected_font,
            fg_color="#059669", hover_color="#047857",
        )
        self.use_button.pack(side="left", padx=(8, 4))
        self.font_status = ctk.CTkLabel(
            title_row, text="", font=("", 11), text_color="#22c55e")
        self.font_status.pack(side="left")

        self.font_list_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.font_list_frame.pack(fill="both", expand=True, pady=(0, 0))
        self._font_radio_var = ctk.StringVar(value="default")

        # -- Right: Preview --
        self.preview_frame = ctk.CTkFrame(
            bottom, fg_color="#1e1e2e", border_width=1, border_color="#3b3b4a")
        self.preview_frame.pack(side="right", fill="both", expand=True)

        self._update_active_label()

    def _show_preview(self, grids: list):
        """Render grids in the right preview panel."""
        for w in self.preview_frame.winfo_children():
            w.destroy()
        if not grids:
            return
        self.preview_frame.update_idletasks()
        avail_w = self.preview_frame.winfo_width() - 12
        img = _make_preview_image(grids, avail_w)
        from customtkinter import CTkImage
        ctk_img = CTkImage(img, size=img.size)
        ctk.CTkLabel(self.preview_frame, image=ctk_img, text="").pack(padx=4, pady=4)

    def _preview_bdf(self):
        """Preview BDF file from the browser."""
        if not _HAS_PIL:
            self.gen_status.configure(text="需要 Pillow: pip install Pillow")
            return
        bdf_path = self.bdf_path_var.get().strip()
        if not bdf_path or not Path(bdf_path).is_file():
            self.gen_status.configure(text="请先选择 BDF 文件")
            return

        try:
            glyphs, font_ascent = _parse_bdf_for_preview(Path(bdf_path))
            grids = []
            for ch in _PREVIEW_CHARS:
                enc = ord(ch)
                if enc in glyphs:
                    grid = _bdf_to_grid(glyphs[enc], font_ascent)
                else:
                    grid = [[0] * GLYPH_W for _ in range(GLYPH_H)]
                grids.append((ch, grid))
            self._show_preview(grids)
        except Exception as e:
            self.gen_status.configure(text=f"预览错误: {e}")

    def _preview_font_dir(self, font_dir: str):
        """Preview a font from the list by reading its .bin file."""
        if not _HAS_PIL:
            return

        fonts_dir = _get_fonts_dir()
        if font_dir == "." or font_dir == "default":
            bin_path = fonts_dir / _font_normal_bin_name()
        else:
            bin_path = fonts_dir / font_dir / _font_normal_bin_name()

        if not bin_path.is_file():
            return

        try:
            data = bin_path.read_bytes()
            charmap_path = _get_charmap()
            charmap_text = charmap_path.read_text("utf-8") if charmap_path.is_file() else ""

            grids = []
            for ch in _PREVIEW_CHARS:
                slot = _lookup_slot(ch, charmap_text)
                if slot is not None:
                    grid = _bin_to_grid(data, slot)
                else:
                    grid = [[0] * GLYPH_W for _ in range(GLYPH_H)]
                grids.append((ch, grid))

            self._show_preview(grids)
        except Exception:
            pass

    def _browse_bdf(self):
        path = filedialog.askopenfilename(
            title="选择 BDF 位图字体文件",
            filetypes=[("BDF Bitmap Font", "*.bdf"), ("All", "*.*")],
        )
        if path:
            self.bdf_path_var.set(path)
            stem = Path(path).stem
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
            if not self.font_name_var.get().strip():
                self.font_name_var.set(safe)

    def _generate_font(self):
        if self._generating:
            return
        bdf = self.bdf_path_var.get().strip()
        if not bdf or not Path(bdf).is_file():
            self.gen_status.configure(text="请选择有效的 BDF 文件")
            return
        name = self.font_name_var.get().strip()
        if not name:
            self.gen_status.configure(text="请输入字体名称")
            return

        self._generating = True
        self.gen_button.configure(state="disabled", text="生成中...")
        self.gen_progress.set(0.2)
        self.gen_status.configure(text="正在生成...")

        threading.Thread(
            target=self._do_generate,
            args=(bdf, name),
            daemon=True,
        ).start()

    def _do_generate(self, bdf: str, name: str):
        try:
            output_dir = _get_fonts_dir() / name
            output_dir.mkdir(parents=True, exist_ok=True)
            script = _get_build_chinese_font_script()

            self.after(0, self.gen_progress.set, 0.5)

            prefix = _font_prefix()
            args = [
                sys.executable, str(script),
                "--bdf", bdf,
                "--charmap", str(_get_charmap()),
                "--output-dir", str(output_dir),
                "--prefix", prefix,
                "--bytes-per-glyph", str(BYTES_PER_GLYPH),
            ]

            result = subprocess.run(args, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "未知错误"
                self.after(0, lambda e=err: self._gen_error(e))
                return

            self.after(0, self.gen_progress.set, 1.0)
            self.after(0, lambda: self.gen_status.configure(text=f"字库 [{name}] 生成成功"))
            self.after(0, self._refresh_font_list)
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._gen_error("生成超时 (120s)"))
        except Exception as e:
            self.after(0, lambda e=e: self._gen_error(str(e)))
        finally:
            self.after(0, self._gen_done)

    def _gen_error(self, msg: str):
        self.gen_status.configure(text=f"错误: {msg}", text_color="#ef4444")
        self.gen_progress.set(0)

    def _gen_done(self):
        self._generating = False
        self.gen_button.configure(state="normal", text="生成字库")

    def _refresh_font_list(self):
        for w in self.font_list_frame.winfo_children():
            w.destroy()
        fonts = _list_generated_fonts()
        if not fonts:
            ctk.CTkLabel(self.font_list_frame, text="无可用字库", text_color="gray").pack(pady=12)
            return
        for f in fonts:
            row = ctk.CTkFrame(self.font_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            rb = ctk.CTkRadioButton(
                row, text=f["name"],
                variable=self._font_radio_var,
                value=f["dir"],
                state="normal" if f.get("has_normal", True) else "disabled",
            )
            rb.pack(side="left", padx=(4, 0))

            if f.get("is_active"):
                ctk.CTkLabel(row, text="✓",
                             font=("", 11), text_color="#22c55e"
                             ).pack(side="right", padx=(0, 2))

            preview_btn = ctk.CTkButton(
                row, text="预览", width=36, height=20,
                font=("", 10),
                fg_color="#7c3aed", hover_color="#6d28d9",
                command=lambda d=f["dir"]: self._preview_font_dir(d),
            )
            preview_btn.pack(side="right", padx=(0, 4))

        active = _load_active_font()
        if active:
            self._font_radio_var.set(active)

    def _activate_selected_font(self):
        font = self._font_radio_var.get()
        if not font:
            self.font_status.configure(text="请选择一个字库", text_color="#f59e0b")
            return
        msg = _activate_font(font)
        self.font_status.configure(
            text=msg,
            text_color="#22c55e" if "激活" in msg else "#ef4444",
        )
        self._refresh_font_list()
        self._update_active_label()

    def _update_active_label(self):
        active = _load_active_font()
        if active and active != "default":
            self.font_status.configure(text=f"✓ {active}", text_color="#22c55e")
        else:
            self.font_status.configure(text="✓ 默认内置", text_color="#22c55e")
