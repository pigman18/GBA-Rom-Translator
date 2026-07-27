"""AXVJ intro / early-UI address registry — S1 data for ``policy``.

These are NOT ordinary mid-ROM ``loadword`` story lines. Birch's new-game
speech loads text from **Thumb literal pools** in low ROM; some strings even
live in the UI bank and can sit inside false LZ streams.

This module is a **pointer registry** (funnel stage S1), not a parallel
inject policy. Rewrite safety lives in ``policy``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntroAddr:
    """One known intro-related site."""

    ptr_off: int | None
    """Pointer site ROM offset (None if string-only / no rewrite)."""

    string_off: int | None
    """String body ROM offset when fixed."""

    category: str
    """birch_pool | ui_bank | menu_tile | story_loadword"""

    label: str
    jp_sample: str
    notes: str = ""


# Pointer sites in Task_NewGameSpeech* literal pools (must stay rewriteable).
BIRCH_EARLY_POOL: tuple[IntroAddr, ...] = (
    IntroAddr(
        0x7968,
        0x19799E,
        "birch_pool",
        "Welcome",
        "いやー おまたせ…",
        "Normal Birch dialogue; mid-ROM string via early pool.",
    ),
    IntroAddr(
        0x79B8,
        0x3E9670,
        "ui_bank",
        "ThisIsPokemon",
        "ポケットモンスター / すなわち ポケモン",
        "SPECIAL: string in UI bank 0x3E9670 (not 0x14xxxx). "
        "Poké Ball throw demo. Easy to skip if false-LZ rejects UI targets.",
    ),
    IntroAddr(
        0x7AFC,
        0x197A0B,
        "birch_pool",
        "WorldInhabited",
        "この せかいには…",
        "Long Birch exposition.",
    ),
    IntroAddr(
        0x7B44,
        0x197AFD,
        "birch_pool",
        "AndYouAre",
        "ところで きみは‥‥？",
        "",
    ),
    IntroAddr(
        0x7D34,
        0x197B09,
        "birch_pool",
        "BoyOrGirl",
        "おとこのこ？ / おんなのこ？",
        "Dialogue line; gender *menu* tiles are separate (おとこ/おんな).",
    ),
    IntroAddr(
        0x7F44,
        0x197B1C,
        "birch_pool",
        "WhatsYourName",
        "なまえも おしえて くれるかい！",
        "CJK ok in font; garbled glyphs → ClearWindow/ChineseTileState.",
    ),
    IntroAddr(
        0x80BC,
        0x197B2D,
        "birch_pool",
        "SoItsPlayer",
        "\\01\\05 だね？",
        "Has FD player-name vars.",
    ),
    IntroAddr(
        0x82CC,
        0x197B36,
        "birch_pool",
        "AhOkayYouArePlayer",
        "‥‥そうか！ きみが…",
        "",
    ),
    IntroAddr(
        0x8454,
        0x197B6E,
        "birch_pool",
        "AreYouReady",
        "よーし じゅんびは いいかい？",
        "",
    ),
)

# Mid-ROM UI pointer tables (safe rewrite) → UI-bank labels.
TRAINER_UI_PTRS: tuple[IntroAddr, ...] = (
    IntroAddr(
        0x13E1F0,
        0x3E9A27,
        "ui_bank",
        "TrainerCard_Name",
        "なまえ",
        "Trainer card label.",
    ),
    IntroAddr(
        0x13E204,
        0x3E9620,
        "ui_bank",
        "TrainerCard_PlayTime",
        "プレイじかん",
        "Trainer card label.",
    ),
)

# Gender / naming chrome (often tile or short menu_ui).
INTRO_MENU_UI: tuple[IntroAddr, ...] = (
    IntroAddr(
        None,
        0x3E9630,
        "menu_tile",
        "Gender_Male",
        "おとこ",
        "Left menu on boy/girl screen; may be tile-backed in some builds.",
    ),
    IntroAddr(
        None,
        0x3E9634,
        "menu_tile",
        "Gender_Female",
        "おんな",
        "",
    ),
    IntroAddr(
        None,
        0x3E9638,
        "menu_tile",
        "Name_DecideYourself",
        "じぶんできめる",
        "No ASCII space in ROM; screen font may look spaced.",
    ),
)

ALL_INTRO: tuple[IntroAddr, ...] = (
    BIRCH_EARLY_POOL + TRAINER_UI_PTRS + INTRO_MENU_UI
)


def birch_ptr_allowlist() -> frozenset[int]:
    return frozenset(a.ptr_off for a in BIRCH_EARLY_POOL if a.ptr_off is not None)


def trainer_ui_ptr_allowlist() -> frozenset[int]:
    """Safe mid-ROM UI pointer sites (trainer card, naming, けってい/もどる)."""
    from_registry = {a.ptr_off for a in TRAINER_UI_PTRS if a.ptr_off is not None}
    # Extra naming / confirm sites not yet modeled as IntroAddr rows.
    extras = {
        0x3A3310,
        0x3A331C,
        0x397B3C,  # けってい
        0x3A68B0,  # もどる
    }
    return frozenset(from_registry | extras)


def summary_lines() -> list[str]:
    lines = ["AXVJ intro address registry:", ""]
    for a in ALL_INTRO:
        ptr = f"ptr=0x{a.ptr_off:X}" if a.ptr_off is not None else "ptr=—"
        so = f"str=0x{a.string_off:X}" if a.string_off is not None else "str=—"
        lines.append(
            f"- [{a.category}] {a.label}: {ptr} {so}  jp={a.jp_sample!r}"
        )
        if a.notes:
            lines.append(f"    {a.notes}")
    return lines
