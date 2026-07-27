"""GUI application for Meowth GBA Translator.

Lazy exports so ``python -m meowth.gui.app`` does not double-import ``app``.
"""

__all__ = ["MeowthGUI", "main"]


def __getattr__(name: str):
    if name in ("MeowthGUI", "main"):
        from .app import MeowthGUI, main

        return MeowthGUI if name == "MeowthGUI" else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
