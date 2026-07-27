"""LLM API settings panel (right column, above modules)."""

from __future__ import annotations

import customtkinter as ctk

from ...core import TranslationConfig
from ...translator import PROVIDER_PRESETS


class ApiPanel(ctk.CTkFrame):
    """Provider / model / key / advanced — sits above the module list."""

    def __init__(self, master):
        super().__init__(master, corner_radius=10)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(inner, text="大模型 API", font=("", 12, "bold")).pack(anchor="w")

        self.seed_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            inner,
            text="跳过 API（仅缓存/种子）",
            variable=self.seed_only_var,
            font=("", 11),
        ).pack(anchor="w", pady=(4, 6))

        pm_row = ctk.CTkFrame(inner, fg_color="transparent")
        pm_row.pack(fill="x", pady=(0, 4))

        prov_frame = ctk.CTkFrame(pm_row, fg_color="transparent")
        prov_frame.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkLabel(prov_frame, text="服务商", font=("", 10)).pack(anchor="w")
        self.provider = ctk.CTkComboBox(
            prov_frame,
            values=list(PROVIDER_PRESETS.keys()),
            state="readonly",
            height=28,
            command=self._on_provider_change,
        )
        self.provider.set("deepseek")
        self.provider.pack(fill="x", pady=(1, 0))

        model_frame = ctk.CTkFrame(pm_row, fg_color="transparent")
        model_frame.pack(side="right", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(model_frame, text="模型", font=("", 10)).pack(anchor="w")
        self.model_entry = ctk.CTkEntry(model_frame, height=28)
        self.model_entry.insert(0, PROVIDER_PRESETS["deepseek"][1])
        self.model_entry.pack(fill="x", pady=(1, 0))

        ctk.CTkLabel(inner, text="API 密钥", font=("", 10)).pack(anchor="w", pady=(2, 0))
        self.api_key_entry = ctk.CTkEntry(
            inner, placeholder_text="sk-…", height=28, show="*"
        )
        self.api_key_entry.pack(fill="x", pady=(1, 0))

        self.advanced_visible = False
        self.advanced_button = ctk.CTkButton(
            inner,
            text="+ 高级选项",
            command=self._toggle_advanced,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray85", "gray25"),
            height=22,
            font=("", 11),
        )
        self.advanced_button.pack(anchor="w", pady=(4, 0))

        self.advanced_frame = ctk.CTkFrame(inner, fg_color="transparent")
        adv_row = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        adv_row.pack(fill="x", pady=(2, 0))

        bf = ctk.CTkFrame(adv_row, fg_color="transparent")
        bf.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkLabel(bf, text="批大小", font=("", 10)).pack(anchor="w")
        self.batch_size = ctk.CTkEntry(bf, height=28)
        self.batch_size.insert(0, "30")
        self.batch_size.pack(fill="x", pady=(1, 0))

        wf = ctk.CTkFrame(adv_row, fg_color="transparent")
        wf.pack(side="right", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(wf, text="并发数", font=("", 10)).pack(anchor="w")
        self.max_workers = ctk.CTkEntry(wf, height=28)
        self.max_workers.insert(0, "10")
        self.max_workers.pack(fill="x", pady=(1, 0))

    def _on_provider_change(self, provider_name: str):
        preset = PROVIDER_PRESETS.get(provider_name)
        if preset:
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, preset[1])

    def _toggle_advanced(self):
        if self.advanced_visible:
            self.advanced_frame.pack_forget()
            self.advanced_button.configure(text="+ 高级选项")
            self.advanced_visible = False
        else:
            self.advanced_frame.pack(fill="x")
            self.advanced_button.configure(text="- 收起高级选项")
            self.advanced_visible = True

    def apply_to(self, config: TranslationConfig) -> None:
        provider = self.provider.get()
        preset = PROVIDER_PRESETS.get(provider)
        api_key = self.api_key_entry.get().strip()
        config.provider = provider if provider else None
        config.model = self.model_entry.get().strip() or (preset[1] if preset else None)
        # Map retired DeepSeek ids if user left old GUI value
        from ...translator import _DEEPSEEK_MODEL_ALIASES

        if config.model in _DEEPSEEK_MODEL_ALIASES:
            config.model = _DEEPSEEK_MODEL_ALIASES[config.model]
            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, config.model)
        config.api_key_env = preset[2] if preset else None
        config.api_key = api_key if api_key else None
        config.batch_size = (
            int(self.batch_size.get()) if self.batch_size.get().isdigit() else 30
        )
        config.max_workers = (
            int(self.max_workers.get()) if self.max_workers.get().isdigit() else 10
        )
        config.seed_only = bool(self.seed_only_var.get())

    def validate(self) -> tuple[bool, str]:
        if not self.seed_only_var.get() and not self.api_key_entry.get().strip():
            return False, "请填写 API 密钥（或勾选跳过 API）"
        return True, ""
