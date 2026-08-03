"""Progress view: horizontal stage timeline aligned with config packs.

  translate/ → translate (extract + fonts + texts)
  tile/ → tile (row_patcher sprite import)
  hook/ → hook (ARMIPS function injection)
  build → build (abstract: text injection + pack, no config folder)
"""

from __future__ import annotations

import customtkinter as ctk

STAGES: list[tuple[str, str, str]] = [
    ("translate", "translate", "翻译"),
    ("tile", "tile", "贴图"),
    ("hook", "hook", "注入"),
    ("build", "build", "打包"),
]


class ProgressView(ctk.CTkFrame):
    """Horizontal timeline: one active stage at a time."""

    def __init__(self, master):
        super().__init__(master, corner_radius=10)

        ctk.CTkLabel(
            self, text="进度", font=("", 13, "bold")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        timeline = ctk.CTkFrame(self, fg_color="transparent")
        timeline.pack(fill="x", padx=12, pady=(0, 2))
        timeline.grid_columnconfigure(tuple(range(len(STAGES) * 2 - 1)), weight=1)

        self._icons: dict[str, ctk.CTkLabel] = {}
        self._labels: dict[str, ctk.CTkLabel] = {}
        self._status: dict[str, str] = {sid: "pending" for sid, _, _ in STAGES}

        col = 0
        for i, (sid, folder, zh) in enumerate(STAGES):
            cell = ctk.CTkFrame(timeline, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=2)
            icon = ctk.CTkLabel(cell, text="○", font=("", 14), text_color="gray")
            icon.pack()
            label = ctk.CTkLabel(
                cell,
                text=f"{folder}\n{zh}",
                font=("", 11),
                text_color="gray",
                justify="center",
            )
            label.pack()
            self._icons[sid] = icon
            self._labels[sid] = label
            col += 1
            if i < len(STAGES) - 1:
                dash = ctk.CTkLabel(
                    timeline, text="—", font=("", 14), text_color=("gray50", "gray50")
                )
                dash.grid(row=0, column=col, sticky="ew")
                col += 1

        bar_row = ctk.CTkFrame(self, fg_color="transparent")
        bar_row.pack(fill="x", padx=12, pady=(2, 2))

        self._stage_hint = ctk.CTkLabel(
            bar_row, text="等待开始", font=("", 11), text_color="gray", width=90, anchor="w"
        )
        self._stage_hint.pack(side="left", padx=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            bar_row, height=8, corner_radius=4, progress_color="#2563eb",
        )
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_bar.set(0)

        self.batch_label = ctk.CTkLabel(
            bar_row, text="0/0", text_color="gray", font=("", 11), width=70, anchor="e",
        )
        self.batch_label.pack(side="right")

        ctk.CTkFrame(self, fg_color="transparent", height=6).pack()

        self._active: str | None = None

    def update(self, stage: str, current: int, total: int, message: str):
        if stage in self._status and total > 0:
            self.progress_bar.set(current / total)
            self.batch_label.configure(text=f"{current}/{total}")
            if message:
                self._stage_hint.configure(text=message[:24])

    def set_stage(self, stage: str, status: str):
        if stage not in self._icons:
            return

        if status == "started":
            self._start_stage(stage)
            return

        self._apply_status(stage, status)

        if status == "completed":
            if self._active == stage:
                self.progress_bar.set(1.0)
                self.batch_label.configure(text="完成")
        elif status == "failed" and self._active == stage:
            self._active = None

    def _start_stage(self, sid: str):
        if self._active and self._active != sid and self._status.get(self._active) == "started":
            self._finish_stage(self._active)
        self._apply_status(sid, "started")
        self._active = sid
        folder = next(f for s, f, _ in STAGES if s == sid)
        zh = next(z for s, _, z in STAGES if s == sid)
        self._stage_hint.configure(text=f"{folder} · {zh}")
        self.progress_bar.set(0)
        self.batch_label.configure(text="…")

    def _finish_stage(self, sid: str):
        self._apply_status(sid, "completed")
        if self._active == sid:
            self.progress_bar.set(1.0)
            self.batch_label.configure(text="完成")

    def _apply_status(self, sid: str, status: str):
        self._status[sid] = status
        icon = self._icons[sid]
        label = self._labels[sid]
        if status == "started":
            icon.configure(text="◉", text_color="#2563eb")
            label.configure(text_color="#e5e7eb")
        elif status == "completed":
            icon.configure(text="✓", text_color="#16a34a")
            label.configure(text_color="#16a34a")
        elif status == "failed":
            icon.configure(text="✗", text_color="#dc2626")
            label.configure(text_color="#dc2626")
        else:
            icon.configure(text="○", text_color="gray")
            label.configure(text_color="gray")

    def reset(self):
        self.progress_bar.set(0)
        self.batch_label.configure(text="0/0")
        self._stage_hint.configure(text="等待开始")
        self._active = None
        for sid, _, _ in STAGES:
            self._apply_status(sid, "pending")
