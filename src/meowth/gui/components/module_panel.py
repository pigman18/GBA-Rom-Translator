"""Right-side module selection panel.

Modules come from ``translate/modules.json`` (addr_bands scope).
Starts empty; call ``load_game(game_id)`` when a ROM is selected.
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ...modules import list_module_meta, list_groups


class ModulePanel(ctk.CTkFrame):
    """Vertical panel showing module checkboxes grouped by category."""

    def __init__(self, master, game_id: str | None = None):
        super().__init__(master, corner_radius=10)
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._metas: list[dict[str, Any]] = []

        self._build_placeholder()
        self._build_content()
        self._show_placeholder()

        if game_id:
            self.load_game(game_id)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _build_placeholder(self):
        self._placeholder = ctk.CTkLabel(
            self, text="请先选择 ROM", font=("", 13),
            text_color=("gray50", "gray50"),
        )

    def _build_content(self):
        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(
            self._inner, text="翻译模块",
            font=("", 13, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            self._inner,
            text="勾选要汉化的地址模块（不勾选则保留日文）",
            font=("", 10),
            text_color=("gray40", "gray60"),
        ).pack(anchor="w", pady=(0, 6))

        btn_row = ctk.CTkFrame(self._inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            btn_row, text="全选", width=70, height=24,
            command=self._preset_all,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_row, text="全选(不含脏)", width=100, height=24,
            command=self._preset_no_dirty,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btn_row, text="全不选", width=70, height=24,
            command=self._preset_none,
        ).pack(side="left")

        self._scroll = ctk.CTkScrollableFrame(self._inner, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, pady=(0, 6))

        self._stats_label = ctk.CTkLabel(
            self._inner, text="", font=("", 10),
            text_color=("gray40", "gray60"),
        )
        self._stats_label.pack(anchor="w")

    def _show_placeholder(self):
        self._inner.pack_forget()
        self._placeholder.pack(expand=True)

    def _show_content(self):
        self._placeholder.pack_forget()
        self._inner.pack(fill="both", expand=True, padx=10, pady=10)

    # ------------------------------------------------------------------
    # Load / rebuild
    # ------------------------------------------------------------------

    def load_game(self, game_id: str):
        """Load modules for the given game and rebuild the UI."""
        try:
            metas = list_module_meta(game_id)
            groups = list_groups(game_id)
        except Exception:
            self._show_placeholder()
            return

        self._metas = [m for m in metas if m.get("group") in groups]
        self._vars = {}

        # Clear scroll frame children
        for w in self._scroll.winfo_children():
            w.destroy()

        last_group = ""
        for m in self._metas:
            g = m.get("group") or ""
            if g != last_group:
                ctk.CTkLabel(
                    self._scroll, text=g, font=("", 11, "bold")
                ).pack(anchor="w", pady=(6 if last_group else 0, 2))
                last_group = g

            var = ctk.BooleanVar(value=bool(m.get("default")))
            var.trace_add("write", lambda *_: self._update_stats())
            self._vars[m["id"]] = var

            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", padx=(4, 0), pady=(1, 1))

            line1 = ctk.CTkFrame(row, fg_color="transparent")
            line1.pack(fill="x")
            ctk.CTkCheckBox(line1, text="", width=24, variable=var, font=("", 11)).pack(side="left")
            ctk.CTkLabel(line1, text=m["label"], font=("", 11)).pack(side="left")

            bands = m.get("addr_bands", [])
            if bands:
                band_str = ", ".join(f"{int(b[0], 16):08X}-{int(b[1], 16):08X}" for b in bands)
                ctk.CTkLabel(
                    line1, text=band_str, font=("", 9),
                    text_color=("gray50", "gray50"),
                ).pack(side="right")

            desc = m.get("description") or ""
            if desc:
                ctk.CTkLabel(
                    row, text=desc, font=("", 9),
                    text_color=("gray50", "gray50"),
                ).pack(anchor="w", padx=(28, 0))

        self._update_stats()
        self._show_content()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def selected_modules(self) -> list[str]:
        return [mid for mid, var in self._vars.items() if var.get()]

    # ------------------------------------------------------------------
    # Range stats
    # ------------------------------------------------------------------

    def _update_stats(self):
        checked_ids = {mid for mid, var in self._vars.items() if var.get()}
        checked_count = 0
        checked_bands = 0
        unchecked_count = 0
        unchecked_bands = 0
        for m in self._metas:
            bands = m.get("addr_bands", [])
            n_bands = len(bands)
            if m["id"] in checked_ids:
                checked_count += 1
                checked_bands += n_bands
            else:
                unchecked_count += 1
                unchecked_bands += n_bands

        self._stats_label.configure(
            text=f"已分析: {checked_count} 个模块  ({checked_bands} 段区间)   |   "
                 f"待分析: {unchecked_count} 个模块  ({unchecked_bands} 段区间)"
        )

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    def _preset_all(self) -> None:
        for var in self._vars.values():
            var.set(True)

    def _preset_none(self) -> None:
        for var in self._vars.values():
            var.set(False)

    def _preset_no_dirty(self) -> None:
        for m in self._metas:
            var = self._vars.get(m["id"])
            if var is not None:
                var.set(not m.get("dirty", False))
