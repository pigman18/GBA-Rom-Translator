"""Configuration form — left-side file paths (JP→ZH fixed)."""

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ...core import TranslationConfig


class ConfigForm(ctk.CTkFrame):
    """ROM / font / output. Language fixed: Japanese → Chinese."""

    def __init__(self, master, on_rom_selected=None):
        super().__init__(master, corner_radius=10)
        self._on_rom_selected = on_rom_selected
        self._last_rom_detect_msg = ""
        self._source_lang = "ja"
        self._target_lang = "zh-Hans"

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        # --- ROM ---
        ctk.CTkLabel(inner, text="ROM 文件", font=("", 12, "bold")).pack(anchor="w")
        rom_row = ctk.CTkFrame(inner, fg_color="transparent")
        rom_row.pack(fill="x", pady=(2, 6))
        self.rom_entry = ctk.CTkEntry(
            rom_row, placeholder_text="选择日版 GBA ROM…", height=28
        )
        self.rom_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            rom_row, text="浏览", width=70, height=28, command=self._browse_rom
        ).pack(side="right")

        # --- BDF ---
        ctk.CTkLabel(inner, text="BDF 字体（可选）", font=("", 12, "bold")).pack(anchor="w")
        font_row = ctk.CTkFrame(inner, fg_color="transparent")
        font_row.pack(fill="x", pady=(2, 6))
        self.font_entry = ctk.CTkEntry(
            font_row, placeholder_text="选择 BDF 字体文件…", height=28
        )
        self.font_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            font_row, text="浏览", width=70, height=28, command=self._browse_font
        ).pack(side="right")

        # --- Output ---
        ctk.CTkLabel(inner, text="输出目录", font=("", 12, "bold")).pack(anchor="w")
        output_row = ctk.CTkFrame(inner, fg_color="transparent")
        output_row.pack(fill="x", pady=(2, 6))
        self.output_entry = ctk.CTkEntry(
            output_row, placeholder_text="选择输出目录…", height=28
        )
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            output_row, text="浏览", width=70, height=28, command=self._browse_output
        ).pack(side="right")

        ctk.CTkLabel(
            inner,
            text="语言：日文 → 简体中文（固定）",
            font=("", 11),
            text_color=("gray40", "gray60"),
        ).pack(anchor="w", pady=(0, 2))

        # --- 文本校验阈值 ---
        ctk.CTkLabel(
            inner, text="文本校验阈值（0=不启用）", font=("", 12, "bold")
        ).pack(anchor="w", pady=(8, 0))
        th_row = ctk.CTkFrame(inner, fg_color="transparent")
        th_row.pack(fill="x", pady=(2, 4))
        self._threshold = ctk.DoubleVar(value=70)
        self.threshold_slider = ctk.CTkSlider(
            th_row,
            from_=0,
            to=100,
            number_of_steps=100,
            variable=self._threshold,
            command=self._on_threshold,
        )
        self.threshold_slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.threshold_label = ctk.CTkLabel(th_row, text="70", width=36)
        self.threshold_label.pack(side="right")

    def _on_threshold(self, value):
        self.threshold_label.configure(text=f"{int(round(value))}")

    @staticmethod
    def _detect_jp_rom(path: Path) -> tuple[str | None, str]:
        from ...game_backends import UnsupportedGameError, get_backend
        from ...game_backends.registry import detect_game, read_game_code

        try:
            game_id = detect_game(path, reject_us=True)
        except UnsupportedGameError as e:
            return None, str(e)
        if game_id == "unknown":
            code = read_game_code(path)
            return None, f"未知 ROM 码: {code}"
        backend = get_backend(game_id)
        if not backend.implemented:
            return game_id, f"已识别 {backend.name}，后端尚未实现"
        return game_id, f"已识别 {backend.name} ({backend.id})"

    def _browse_rom(self):
        filename = filedialog.askopenfilename(
            title="选择 GBA ROM",
            filetypes=[("GBA ROM", "*.gba"), ("所有文件", "*.*")],
        )
        if filename:
            self.rom_entry.delete(0, "end")
            self.rom_entry.insert(0, filename)
            game_id, msg = self._detect_jp_rom(Path(filename))
            if game_id and self._on_rom_selected:
                self._on_rom_selected(game_id)
            self._last_rom_detect_msg = msg

    def _browse_output(self):
        dirname = filedialog.askdirectory(title="选择输出目录")
        if dirname:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, dirname)

    def _browse_font(self):
        filename = filedialog.askopenfilename(
            title="选择 BDF 位图字体",
            filetypes=[("BDF 字体", "*.bdf"), ("所有文件", "*.*")],
        )
        if filename:
            self.font_entry.delete(0, "end")
            self.font_entry.insert(0, filename)

    def get_config(self) -> TranslationConfig:
        output_dir = Path(self.output_entry.get()) if self.output_entry.get() else None
        work_dir = Path("work") if output_dir else None

        game = ""
        if self.rom_entry.get():
            game_id, _ = self._detect_jp_rom(Path(self.rom_entry.get()))
            if game_id:
                game = game_id

        return TranslationConfig(
            source_lang=self._source_lang,
            target_lang=self._target_lang,
            rom_path=Path(self.rom_entry.get()) if self.rom_entry.get() else None,
            output_dir=output_dir,
            work_dir=work_dir,
            game=game,
            bdf_font_path=Path(self.font_entry.get()) if self.font_entry.get() else None,
            modules=None,
            seed_first=True,
            check_threshold=int(round(self._threshold.get())),
        )

    def validate(self) -> tuple[bool, str]:
        if not self.rom_entry.get():
            return False, "请选择 ROM 文件"
        rom_path = Path(self.rom_entry.get())
        if not rom_path.exists():
            return False, f"ROM 不存在: {rom_path}"
        game_id, msg = self._detect_jp_rom(rom_path)
        if game_id is None:
            return False, msg
        from ...game_backends import get_backend

        backend = get_backend(game_id)
        if not backend.implemented:
            return False, msg
        return True, msg
