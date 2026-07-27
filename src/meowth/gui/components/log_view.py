"""Log view component using CustomTkinter."""

from datetime import datetime

import customtkinter as ctk


class LogView(ctk.CTkFrame):
    """Scrollable log viewer with color-coded messages."""

    def __init__(self, master):
        """Initialize log view."""
        super().__init__(master, corner_radius=10)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(header, text="日志", font=("", 13, "bold")).pack(side="left")
        ctk.CTkButton(
            header, text="清空", width=56, height=24,
            font=("", 11), corner_radius=6,
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray40"),
            text_color=("gray40", "gray60"),
            hover_color=("gray85", "gray25"),
            command=self.clear,
        ).pack(side="right")

        # Log text area (compact default height; expands with left column)
        self.textbox = ctk.CTkTextbox(
            self, height=120, wrap="word",
            corner_radius=6, font=("Menlo", 11),
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Color tags
        self.textbox.tag_config("info", foreground="#e5e7eb")
        self.textbox.tag_config("warning", foreground="#fbbf24")
        self.textbox.tag_config("error", foreground="#f87171")
        self.textbox.tag_config("timestamp", foreground="#6b7280")

    def append(self, level: str, message: str):
        """Append a log message."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.textbox.insert("end", f"[{ts}] ", "timestamp")
        tag = level if level in ("info", "warning", "error") else "info"
        self.textbox.insert("end", f"{message}\n", tag)
        self.textbox.see("end")

    def clear(self):
        """Clear all log entries."""
        self.textbox.delete("1.0", "end")
