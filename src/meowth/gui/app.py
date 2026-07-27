"""Main CustomTkinter GUI — config left, API + modules right."""

import sys
import threading
from pathlib import Path

import customtkinter as ctk

from ..core import TranslationEngine
from .callbacks import GUICallbacks
from .components import ApiPanel, ConfigForm, LogView, ModulePanel, ProgressView

# app.py → gui → meowth → src → tool root
_TOOL_ROOT = Path(__file__).resolve().parents[3]


def _quote_win(path: str | Path) -> str:
    """Quote a path for cmd.exe / PowerShell copy-paste."""
    s = str(path)
    if not s:
        return '""'
    if any(c in s for c in ' \t&|()<>^"'):
        return '"' + s.replace('"', '\\"') + '"'
    return s


class MeowthGUI(ctk.CTk):
    """ROM 汉化器主窗口。"""

    def __init__(self):
        super().__init__()
        self.title("ROM汉化器")
        self.geometry("1080x700")
        self.minsize(960, 640)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.engine = None
        self.translation_thread = None
        self.is_running = False
        self._build_ui()

    def _build_ui(self):
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=20, pady=(0, 14))

        self.start_button = ctk.CTkButton(
            bottom, text="开始汉化",
            command=self._start_translation,
            height=40, font=("", 14, "bold"),
            corner_radius=8, fg_color="#2563eb", hover_color="#1d4ed8",
        )
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.copy_cmd_button = ctk.CTkButton(
            bottom,
            text="复制命令",
            command=self._copy_build_command,
            height=40,
            font=("", 13),
            corner_radius=8,
            fg_color="#0f766e",
            hover_color="#0d9488",
            width=110,
        )
        self.copy_cmd_button.pack(side="left", padx=(0, 8))

        self.stop_button = ctk.CTkButton(
            bottom, text="停止", command=self._stop_translation,
            height=40, font=("", 13), corner_radius=8,
            fg_color="#4b5563", hover_color="#6b7280",
            state="disabled", width=100,
        )
        self.stop_button.pack(side="right")

        # Fixed body (no outer scrollbar on default launch)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(12, 8))

        ctk.CTkLabel(
            body, text="ROM汉化器",
            font=("", 20, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        split = ctk.CTkFrame(body, fg_color="transparent")
        split.pack(fill="both", expand=True)

        left = ctk.CTkFrame(split, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = ctk.CTkFrame(split, fg_color="transparent", width=400)
        right.pack(side="right", fill="both", padx=(8, 0))
        right.pack_propagate(False)

        self.config_form = ConfigForm(
            left,
            on_rom_selected=lambda game_id: self.module_panel.load_game(game_id),
        )
        self.config_form.pack(fill="x", pady=(0, 6))

        self.progress_view = ProgressView(left)
        self.progress_view.pack(fill="x", pady=(0, 6))

        self.log_view = LogView(left)
        self.log_view.pack(fill="both", expand=True)

        self.api_panel = ApiPanel(right)
        self.api_panel.pack(fill="x", pady=(0, 6))

        self.module_panel = ModulePanel(right, game_id=None)
        self.module_panel.pack(fill="both", expand=True)

    def _format_build_command(self) -> str:
        """Build a pasteable ``python -m meowth full …`` matching current GUI options."""
        rom = self.config_form.rom_entry.get().strip()
        out = self.config_form.output_entry.get().strip()
        bdf = self.config_form.font_entry.get().strip()
        modules = self.module_panel.selected_modules()
        seed_only = bool(self.api_panel.seed_only_var.get())
        provider = self.api_panel.provider.get().strip()
        model = self.api_panel.model_entry.get().strip()
        batch = self.api_panel.batch_size.get().strip() or "30"
        workers = self.api_panel.max_workers.get().strip() or "10"
        api_key = self.api_panel.api_key_entry.get().strip()

        py = _quote_win(sys.executable)
        root = _quote_win(_TOOL_ROOT)
        lines = [
            f"cd /d {root}",
            "set PYTHONPATH=%cd%\\src",
        ]

        parts = [py, "-m", "meowth", "full"]
        if rom:
            parts.append(_quote_win(rom))
        else:
            parts.append(_quote_win(r"C:\path\to\rom.gba"))
        parts.extend(["-o", _quote_win(out or "outputs")])
        parts.extend(["--work-dir", "work"])
        parts.extend(["--source", "ja", "--target", "zh-Hans"])
        if seed_only:
            parts.append("--seed-only")
        if bdf:
            parts.extend(["--bdf", _quote_win(bdf)])
        if modules:
            parts.extend(["--modules", _quote_win(",".join(modules))])
        if not seed_only:
            if provider:
                parts.extend(["--provider", provider])
            if model:
                parts.extend(["--model", _quote_win(model)])
            if api_key:
                # --api-key=xxx so paste-and-run; quote if needed
                parts.append(f"--api-key={_quote_win(api_key)}")
            else:
                lines.append("rem 未填写 API 密钥：复制前请在 GUI 填入，或手动补 --api-key=xxx")

        lines.append(" ".join(parts))

        if batch != "30" or workers != "10":
            lines.append(
                f"rem GUI 批大小={batch} 并发={workers}（CLI full 未暴露，仅 translate 子命令有）"
            )
        return "\n".join(lines)

    def _copy_build_command(self):
        cmd = self._format_build_command()
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.update_idletasks()
        except Exception as e:
            self.log_view.append("error", f"复制失败: {e}")
            return
        preview = cmd.replace("\n", " | ")
        if len(preview) > 180:
            preview = preview[:177] + "…"
        self.log_view.append("info", f"已复制构建命令: {preview}")

    def _start_translation(self):
        is_valid, error_message = self.config_form.validate()
        if not is_valid:
            self.log_view.append("error", error_message)
            return
        api_ok, api_msg = self.api_panel.validate()
        if not api_ok:
            self.log_view.append("error", api_msg)
            return
        if error_message:
            self.log_view.append("info", error_message)

        config = self.config_form.get_config()
        self.api_panel.apply_to(config)
        config.modules = self.module_panel.selected_modules()

        self.progress_view.reset()
        self.log_view.append("info", "开始汉化…")

        self.start_button.configure(state="disabled", fg_color="#4b5563")
        self.stop_button.configure(state="normal", fg_color="#dc2626", hover_color="#b91c1c")
        self.is_running = True

        callbacks = GUICallbacks(self, self.progress_view, self.log_view)

        try:
            self.engine = TranslationEngine(config, callbacks)
        except Exception as e:
            self.log_view.append("error", f"初始化失败: {e}")
            self._reset_buttons()
            return

        self.translation_thread = threading.Thread(
            target=self._run_translation, args=(config,), daemon=True,
        )
        self.translation_thread.start()

    def _run_translation(self, config):
        try:
            output_path = self.engine.run_full()
            self.after(0, self._on_translation_complete, output_path)
        except Exception as e:
            self.after(0, self._on_translation_error, e)

    def _on_translation_complete(self, output_path: Path):
        self.log_view.append("info", f"汉化完成！输出: {output_path}")
        self._reset_buttons()

    def _on_translation_error(self, error: Exception):
        self.log_view.append("error", f"汉化失败: {error}")
        self._reset_buttons()

    def _stop_translation(self):
        if self.engine and self.is_running:
            self.log_view.append("warning", "正在停止…")
            self.is_running = False
            self._reset_buttons()

    def _reset_buttons(self):
        self.start_button.configure(state="normal", fg_color="#2563eb")
        self.stop_button.configure(state="disabled", fg_color="#4b5563")
        self.is_running = False


def main():
    app = MeowthGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
