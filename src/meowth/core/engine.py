"""Core translation engine - refactored from Pipeline with callback support."""

import json
import os
import shutil
import subprocess
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..charmap import Charmap
from ..control_codes import format_original, protect, restore, unwrap_quotes
from ..config_loader import (
    load_game_config,
    get_game_patch_dir,
    get_charmap_path,
    load_modules,
    module_translate_rules,
    module_wrap_kwargs,
    set_active_game_id,
)
from ..font_patch import apply_font_patch
from ..glossary import Glossary
from ..i18n import Messages
from ..languages import is_cjk_language
from ..pcs_codes import FD_MACROS
from ..rom_writer import RomWriter
from ..text_wrap import wrap_text
from ..translator import Translator
from .callbacks import TranslationCallbacks
from .config import TranslationConfig

from ..game_backends import UnsupportedGameError, detect_game, get_backend

# DEPRECATED empty set — corpus is unified free_texts; do not gate on module ids.
TABLE_CATEGORIES: set[str] = set()

# Hardcoded translations (FireRed + Chinese only)
_HARDCODED_TRANSLATIONS: dict[str, str] = {
    "scr_02219": (
        "你将成为主角，\n探索宝可梦的世界！"
        "\n\n通过与人们交谈并解开谜题，\n新的道路将为你敞开。"
        "\n\n与你出色的宝可梦一起，\n朝着目标努力吧！"
    ),
    "scr_02329": (
        "你好啊！\n很高兴见到你！"
        "\n\n欢迎来到宝可梦火红VX！"
        "\n\n我叫大木。"
        "\n\n人们亲切地称呼我为\n宝可梦博士。\n\n"
    ),
    "scr_02330": "这个世界",
    "scr_02331": "到处都栖息着被称为\n宝可梦的生物。\n\n",
    "scr_02332": (
        "对有些人来说，宝可梦是宠物。\n也有人用它们来对战。"
        "\n\n至于我自己……"
        "\n\n我把研究宝可梦当作职业。"
    ),
    "scr_02333": "不过首先，\n请告诉我一些关于你自己的事。",
    "scr_02334": "先从你的名字开始吧。\n你叫什么名字？",
    "scr_02335": "好的……\n\n原来你叫[player]。",
    "scr_02336": (
        "这是我的孙子。"
        "\n\n从你们还是婴儿的时候起，\n他就一直是你的劲敌。"
        "\n\n呃，他叫什么名字来着？"
    ),
    "scr_02339": "没错！我想起来了！\n他的名字是[rival]！",
    "scr_02340": (
        "[player]！"
        "\n\n属于你自己的宝可梦传奇\n即将展开！"
        "\n\n充满梦想与冒险的宝可梦世界\n正等待着你！出发吧！"
    ),
}

# Manual trainer class translations
_TRAINER_CLASS_OVERRIDES: dict[str, str] = {
    "RIVAL": "劲敌",
}

# Term overrides by original text (applied before LLM, all games, Chinese only)
_TERM_OVERRIDES: dict[str, str] = {
    "POKéDEX": "图鉴",
    "POKéMON": "宝可梦",
    "POKéNAV": "导航仪",
}


# detect_game is imported from game_backends (JP registry).

# Known font-rendering function addresses and expected THUMB prologue bytes for
# official binary ROMs. Decomp ROMs (pokeemerald, pokefirered, etc.) are
# recompiled from source, so these addresses contain completely different code.
# US titles are out of scope for this fork; kept for legacy is_decomp_rom checks.
_FONT_HOOK_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    "firered": [(0x5790, b"\x70\xb5"), (0x5ed4, b"\xf0\xb5")],
    "leafgreen": [(0x5790, b"\x70\xb5"), (0x5ed4, b"\xf0\xb5")],
    "emerald": [(0x57b4, b"\x70\xb5"), (0x5ed8, b"\xf0\xb5")],
}


def is_decomp_rom(rom_path: Path, game: str) -> bool:
    """Return True if this ROM is incompatible with the font patch.

    Checks whether the bytes at known font-rendering function addresses match
    the official binary ROM. Decomp ROMs (pokeemerald, pokefirered, etc.) are
    recompiled from source, so these addresses contain completely different code.
    Binary hacks applied on top of the original ROM preserve these bytes.
    """
    sigs = _FONT_HOOK_SIGNATURES.get(game)
    if sigs is None:
        return False  # unknown game, skip check
    with open(rom_path, "rb") as f:
        for offset, expected in sigs:
            f.seek(offset)
            if f.read(len(expected)) != expected:
                return True
    return False


def convert_format(data: dict) -> dict:
    """Normalize corpus to a single list: ``free_texts`` (``tables`` always empty).

    texts.json already carries address + JP + ``module``. Translate/build do
    not split name-tables vs dialogue — one path for all entries; inject uses
    per-module ``read``/``write``/relocate config.
    """
    entries = data.get("entries")
    if entries:
        free_texts = list(entries)
    elif "tables" in data or "free_texts" in data:
        free_texts = list(data.get("free_texts") or [])
        for t in data.get("tables") or []:
            free_texts.extend(t.get("entries") or [])
    else:
        free_texts = []
    out: dict = {
        "tables": [],
        "free_texts": free_texts,
    }
    for k in ("game", "game_id", "source_lang", "modules", "count"):
        if k in data:
            out[k] = data[k]
    return out



def _cache_map_from_data(data: dict) -> dict[str, str]:
    """Legacy: flatten entries into ``{原文: 译文}`` (upgrade path only)."""
    cache: dict[str, str] = {}
    flat: list[dict] = list(data.get("entries") or [])
    if not flat:
        for t in data.get("tables") or []:
            flat.extend(t.get("entries") or [])
        flat.extend(data.get("free_texts") or [])
    for e in flat:
        if e.get("_reject"):
            continue
        orig = e.get("original") or ""
        tr = e.get("translated") or ""
        if tr and tr != orig:
            key = format_original(orig)
            cache[key] = tr
            if orig and orig != key:
                cache.setdefault(orig, tr)
            unwrapped = unwrap_quotes(orig)
            if unwrapped and unwrapped != key and unwrapped != orig:
                cache.setdefault(unwrapped, tr)
    return cache


# texts_translated.json status codes
CACHE_STATUS_OK = 200
CACHE_STATUS_GARBLED = 404
GARBLED_MARKERS = frozenset({"这是一段乱码", "这是一段明显乱码"})


def _is_garbled_marker(text: str) -> bool:
    return (text or "").strip() in GARBLED_MARKERS


def _cache_key(original: str) -> str:
    return format_original(original or "")


def _put_cache_rec(
    cache: dict[str, dict],
    original: str,
    *,
    status: int,
    translated: str | None = None,
) -> None:
    """Upsert one record keyed by formatted original."""
    if not original:
        return
    key = _cache_key(original)
    rec: dict = {"status": int(status), "original": original}
    if status == CACHE_STATUS_OK and translated:
        rec["translated"] = translated
    cache[key] = rec


def _lookup_cache_rec(cache: dict[str, dict], original: str) -> dict | None:
    if not original or not cache:
        return None
    for cand in (original, unwrap_quotes(original), format_original(original)):
        if cand and cand in cache:
            return cache[cand]
    return None


def _zh_from_cache(cache: dict[str, dict], original: str, usable) -> str | None:
    """Return usable Chinese for original if status==200."""
    rec = _lookup_cache_rec(cache, original)
    if not rec or rec.get("status") != CACHE_STATUS_OK:
        return None
    tr = rec.get("translated") or ""
    orig = rec.get("original") or original
    if usable(orig, tr) or usable(original, tr) or usable(format_original(original), tr):
        return tr
    return None


def _is_cache_resolved(cache: dict[str, dict], original: str, usable) -> bool:
    """True if we should not call LLM (200 with ZH, or 404 garbled)."""
    rec = _lookup_cache_rec(cache, original)
    if not rec:
        return False
    st = rec.get("status")
    if st == CACHE_STATUS_GARBLED:
        return True
    if st == CACHE_STATUS_OK:
        return _zh_from_cache(cache, original, usable) is not None
    return False


def _is_status_cache_list(data) -> bool:
    return isinstance(data, list)


def _is_cache_map(data: dict) -> bool:
    """Legacy pure ``{原文: 译文}`` map (no entries/tables/free_texts)."""
    return isinstance(data, dict) and bool(data) and not any(
        k in data for k in ("entries", "free_texts", "tables")
    )


def _load_translation_cache(
    path: Path,
    usable,
    *,
    fallback_path: Path | None = None,
) -> dict[str, dict]:
    """Load texts_translated.json → ``{fmt_orig: {status, original, translated?}}``.

    Supports: status array (new), legacy ``{原文:译文}`` map, legacy entries shapes.
    """
    paths = [path]
    if fallback_path is not None and fallback_path != path:
        paths.append(fallback_path)

    raw = None
    for p in paths:
        if not p.is_file():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            continue
    if raw is None:
        return {}

    out: dict[str, dict] = {}

    # New: [{status, original, translated?}, ...]
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            orig = item.get("original")
            if not isinstance(orig, str) or not orig:
                continue
            try:
                st = int(item.get("status") or 0)
            except (TypeError, ValueError):
                continue
            if st == CACHE_STATUS_GARBLED:
                _put_cache_rec(out, orig, status=CACHE_STATUS_GARBLED)
            elif st == CACHE_STATUS_OK:
                tr = item.get("translated") or ""
                if isinstance(tr, str) and (usable(orig, tr) or usable(format_original(orig), tr)):
                    _put_cache_rec(out, orig, status=CACHE_STATUS_OK, translated=tr)
        return out

    if not isinstance(raw, dict):
        return {}

    # Legacy map {原文: 译文}
    if _is_cache_map(raw) or (
        raw and not any(k in raw for k in ("entries", "free_texts", "tables"))
    ):
        for orig, tr in raw.items():
            if not isinstance(orig, str) or not isinstance(tr, str):
                continue
            if usable(orig, tr) or usable(format_original(orig), tr):
                _put_cache_rec(out, orig, status=CACHE_STATUS_OK, translated=tr)
        return out

    # Legacy entries / free_texts / tables
    for orig, tr in _cache_map_from_data(raw).items():
        if usable(orig, tr) or usable(format_original(orig), tr):
            _put_cache_rec(out, orig, status=CACHE_STATUS_OK, translated=tr)
    return out


def _save_translation_cache(path: Path, cache: dict[str, dict], usable=None) -> None:
    """Write status array to texts_translated.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    seen: set[str] = set()
    for key, rec in cache.items():
        if not isinstance(rec, dict):
            continue
        orig = rec.get("original") or key
        if not isinstance(orig, str) or not orig:
            continue
        canon = _cache_key(orig)
        if canon in seen:
            continue
        seen.add(canon)
        try:
            st = int(rec.get("status") or 0)
        except (TypeError, ValueError):
            continue
        if st == CACHE_STATUS_GARBLED:
            rows.append({"status": CACHE_STATUS_GARBLED, "original": orig})
            continue
        if st != CACHE_STATUS_OK:
            continue
        tr = rec.get("translated") or ""
        if not isinstance(tr, str) or not tr:
            continue
        if usable is not None and not (
            usable(orig, tr) or usable(canon, tr)
        ):
            continue
        rows.append({
            "status": CACHE_STATUS_OK,
            "original": orig,
            "translated": tr,
        })
    rows.sort(key=lambda r: r.get("original") or "")
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _merge_lexicon_into_cache(
    cache: dict[str, dict], lexicon: dict[str, str], usable=None
) -> int:
    """Merge lexicon as status=200; lexicon wins. Skips non-usable / 未变更。

    Returns number of rows newly written or whose ``translated`` changed.
    """
    n = 0
    for orig, tr in (lexicon or {}).items():
        if not isinstance(orig, str) or not isinstance(tr, str):
            continue
        # Empty tr = intentional blank (rare); still merge so inject can EOS-only.
        if usable is not None and tr and not usable(orig, tr) and not usable(
            format_original(orig), tr
        ):
            continue
        prev = _lookup_cache_rec(cache, orig)
        if (
            prev
            and prev.get("status") == CACHE_STATUS_OK
            and prev.get("translated") == tr
        ):
            continue
        _put_cache_rec(cache, orig, status=CACHE_STATUS_OK, translated=tr)
        n += 1
    return n


def _strip_llm_newlines(text: str) -> str:
    """Remove literal newlines inserted by the LLM for formatting."""
    _PARA = "\x00PARA\x00"
    text = text.replace("\n\n", _PARA)
    text = text.replace("\n", "")
    text = text.replace(_PARA, "\n\n")
    return text


def _postprocess_fd_macros(json_path: Path):
    """Replace HMA's raw FD escape sequences with named macros."""
    _HMA_KNOWN = {0x01, 0x02, 0x03, 0x04, 0x06}
    replacements = {}
    for code, name in FD_MACROS.items():
        if code not in _HMA_KNOWN:
            replacements[f"\\\\\\\\{code:02X}"] = name
    if not replacements:
        return
    text = json_path.read_text(encoding="utf-8")
    for raw, macro in replacements.items():
        text = text.replace(raw, macro)
    json_path.write_text(text, encoding="utf-8")


class TranslationEngine:
    """Core translation engine with callback support.

    This is the refactored version of Pipeline that uses callbacks
    instead of print() statements, enabling both CLI and GUI interfaces.
    """

    def __init__(
        self,
        config: TranslationConfig,
        callbacks: TranslationCallbacks | None = None,
        charmap: Charmap | None = None,
        glossary: Glossary | None = None,
        translator: Translator | None = None,
    ):
        """Initialize the translation engine.

        Args:
            config: Translation configuration
            callbacks: Callback handler for progress and logging
            charmap: Character mapping (auto-created if None)
            glossary: Glossary for term translation (auto-created if None)
            translator: LLM translator (auto-created if None)
        """
        self.config = config
        self.callbacks = callbacks or TranslationCallbacks()

        # Detect game early when ROM path is known (avoid loading wrong charmap)
        if config.rom_path and Path(config.rom_path).exists():
            try:
                detected = detect_game(Path(config.rom_path))
            except UnsupportedGameError:
                raise
            if detected != "unknown":
                self.config.game = detected
                set_active_game_id(detected)
                try:
                    get_backend(detected).prepare_config(self.config)
                except KeyError:
                    pass

        # Try to load game config for charmap settings; fallback if not ready
        if self.config.game:
            set_active_game_id(self.config.game)
        _cfg = {}
        try:
            _cfg = load_game_config(config.game)
            self._log("info", f"[配置] 读取游戏配置: {config.game}")
        except Exception:
            pass
        _charmap_cfg = dict(_cfg.get("charmap") or {})
        try:
            from ..config_loader import load_codec
            codec_cm = (load_codec(config.game) or {}).get("charmap") or {}
            if isinstance(codec_cm, dict):
                _charmap_cfg = {**codec_cm, **_charmap_cfg}
        except Exception:
            pass
        _charmap_cfg = self._resolve_charmap_cfg_path(_charmap_cfg, config.game)
        self.charmap = charmap or Charmap(
            target_lang=config.target_lang,
            charmap_cfg=_charmap_cfg,
        )
        self.glossary = glossary or Glossary(
            source_lang=self.config.source_lang,
            target_lang=config.target_lang
        )
        self._translator = translator
        self.translator = translator  # may stay None until LLM is needed
        self._custom_translations: dict[str, str] = {}
        self._fonts_from_bdf = False

    def _resolve_charmap_cfg_path(self, charmap_cfg: dict, game_id: str) -> dict:
        """Resolve shared ``charmap.txt`` (beside game.json; used by patch encode)."""
        path = get_charmap_path(game_id)
        charmap_cfg["charmap_path"] = str(path)
        self._log("info", f"[配置] charmap: {path}")
        return charmap_cfg

    # JP Gen3 pipeline defaults when ``features`` omitted from game.json
    _FEATURE_DEFAULTS: dict = {
        "seed_translate": True,
        "garbage_filter": True,
        "seed_on_no_key": True,
        "flat_entry_format": True,
        "failed_zh_detection": True,
        "module_filter": True,
        "lz_scan": True,
        "name_tables": True,
    }

    def _feature(self, key: str, default=False):
        """Read optional ``features`` override; else built-in JP defaults."""
        try:
            cfg = load_game_config(self.config.game)
            feats = cfg.get("features") or {}
            if key in feats:
                return feats[key]
        except Exception:
            pass
        if key in self._FEATURE_DEFAULTS:
            return self._FEATURE_DEFAULTS[key]
        return default

    @staticmethod
    def _usable_zh(original: str, translated: str) -> bool:
        import re

        from ..seed_translate import looks_like_failed_zh_translation

        if translated == original:
            return False
        # Intentional blank / spacer (memo particle な → " ")
        if translated == "" or translated == " ":
            return True
        if not translated:
            return False
        if looks_like_failed_zh_translation(original, translated):
            return False
        if re.search(r"[\u4e00-\u9fff]", translated):
            return True
        # Short menu labels / color-prefixed options
        if translated in {"是", "否"} or "\\CC" in translated:
            return True
        return False

    @staticmethod
    def _has_translatable_jp(original: str) -> bool:
        """False for placeholders like 「？」「？？？」with no kana/kanji to translate."""
        import re

        s = unwrap_quotes(original or "").strip()
        if not s:
            return False
        return bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s))

    def _apply_cache_to_data(self, data: dict, cache: dict[str, dict]) -> int:
        """Fill entry.translated from status=200 cache. Returns how many filled."""
        n = 0

        def _one(e: dict) -> None:
            nonlocal n
            if e.get("_reject"):
                return
            orig = e.get("original") or ""
            rec = _lookup_cache_rec(cache, orig)
            if rec and rec.get("status") == CACHE_STATUS_GARBLED:
                # Keep original for inject; mark so plan can keep
                if not (e.get("translated") or "").strip():
                    e["translated"] = orig
                e["_cache_status"] = CACHE_STATUS_GARBLED
                return
            zh = _zh_from_cache(cache, orig, self._usable_zh)
            if not zh:
                return
            if e.get("translated") != zh:
                e["translated"] = zh
                n += 1
            e["_cache_status"] = CACHE_STATUS_OK

        for e in data.get("entries") or []:
            _one(e)
        for e in data.get("free_texts") or []:
            _one(e)
        for t in data.get("tables") or []:
            for e in t.get("entries") or []:
                _one(e)
        return n

    def _append_batch_to_cache(
        self,
        cache: dict[str, dict],
        output_path: Path,
        batch: list[dict],
        lock: threading.Lock,
    ) -> int:
        """Append batch 200/404 results into cache and write disk."""
        updates: list[tuple[str, int, str | None]] = []
        for e in batch:
            orig = e.get("original") or ""
            if e.get("_cache_status") == CACHE_STATUS_GARBLED or _is_garbled_marker(
                e.get("translated") or ""
            ):
                updates.append((orig, CACHE_STATUS_GARBLED, None))
                continue
            tr = e.get("translated") or ""
            if self._cacheable_pair(orig, tr):
                updates.append((orig, CACHE_STATUS_OK, tr))
        if not updates:
            return 0
        with lock:
            for orig, st, tr in updates:
                if st == CACHE_STATUS_GARBLED:
                    _put_cache_rec(cache, orig, status=CACHE_STATUS_GARBLED)
                else:
                    _put_cache_rec(
                        cache, orig, status=CACHE_STATUS_OK, translated=tr or ""
                    )
            _save_translation_cache(output_path, cache, self._usable_zh)
        return len(updates)

    def _cacheable_pair(self, original: str, translated: str) -> bool:
        """True if this pair should be persisted as status=200."""
        if not translated or not translated.strip():
            return False
        if _is_garbled_marker(translated):
            return False
        if self._usable_zh(original, translated):
            return True
        u = unwrap_quotes(original)
        if u != original and self._usable_zh(u, translated):
            return True
        key = format_original(original)
        if key != original and self._usable_zh(key, translated):
            return True
        return False

    def _harvest_into_cache(self, data: dict, cache: dict[str, dict]) -> int:
        """Pull entry translations / 404 markers into the cache map."""
        n = 0

        def _one(e: dict) -> None:
            nonlocal n
            if e.get("_reject"):
                return
            orig = e.get("original") or ""
            if e.get("_cache_status") == CACHE_STATUS_GARBLED or _is_garbled_marker(
                e.get("translated") or ""
            ):
                prev = _lookup_cache_rec(cache, orig)
                if not prev or prev.get("status") != CACHE_STATUS_GARBLED:
                    _put_cache_rec(cache, orig, status=CACHE_STATUS_GARBLED)
                    n += 1
                return
            tr = e.get("translated") or ""
            if not self._cacheable_pair(orig, tr):
                return
            prev = _lookup_cache_rec(cache, orig)
            if (
                prev
                and prev.get("status") == CACHE_STATUS_OK
                and prev.get("translated") == tr
            ):
                return
            _put_cache_rec(cache, orig, status=CACHE_STATUS_OK, translated=tr)
            n += 1

        for e in data.get("entries") or []:
            _one(e)
        for e in data.get("free_texts") or []:
            _one(e)
        for t in data.get("tables") or []:
            for e in t.get("entries") or []:
                _one(e)
        return n

    def _ensure_translator(self) -> Translator:
        if self.translator is None:
            self.translator = Translator(
                source_lang=self.config.source_lang,
                target_lang=self.config.target_lang,
                provider=self.config.provider,
                base_url=self.config.api_base,
                api_key=self.config.api_key,
                api_key_env=self.config.api_key_env,
                model=self.config.model,
                cache_dir=self.config.work_dir / "cache",
            )
        return self.translator

    def _log(self, level: str, message: str):
        """Internal helper to send log messages via callbacks."""
        self.callbacks.on_log(level, message)

    def translate_texts(
        self, texts_path: Path, output_path: Path
    ) -> Path:
        """Translate texts.json against texts_translated.json cache.

        Pipeline:
          1. Load texts_translated.json
          2. **翻译开始前**合并 lexicon → 覆盖缓存（仅译文变更时写盘）
          3. Diff texts.json vs cache → pending (skipped when seed_only)
          4. LLM; on success append 200/404 into cache (skipped when seed_only)
          5. Join texts.json + cache → translate.build.json
        """
        from ..config_loader import load_custom_translations, texts_translated_path
        from ..modules import resolve_modules, stamp_entry_module

        # Prefer configs/.../texts_translated.json; fall back to work/ for load
        gid = self.config.game or ""
        try:
            cfg_cache_path = texts_translated_path(gid) if gid else output_path
        except Exception:
            cfg_cache_path = output_path
        output_path = cfg_cache_path
        work_fallback = (
            Path(self.config.work_dir) / gid / "texts_translated.json"
            if gid
            else None
        )

        # --- 1. Load cache ---
        cache = _load_translation_cache(
            output_path, self._usable_zh, fallback_path=work_fallback
        )
        self._log(
            "info",
            f"[翻译缓存] 加载 {output_path}: {len(cache)} 条",
        )

        # --- 2. 翻译开始前：lexicon 覆盖 texts_translated（仅变更写盘）---
        self._custom_translations = load_custom_translations(self.config.game)
        n_lex = _merge_lexicon_into_cache(
            cache, self._custom_translations or {}, self._usable_zh
        )
        if n_lex > 0:
            _save_translation_cache(output_path, cache, self._usable_zh)
            self._log(
                "info",
                f"[翻译缓存] 翻译前 lexicon 变更 {n_lex} 条 → {output_path}",
            )
        else:
            self._log(
                "info",
                "[翻译缓存] 翻译前 lexicon 无变更，跳过写入 texts_translated.json",
            )

        # Load corpus（此后才 seed/LLM；缓存已含 lexicon）
        data = json.loads(texts_path.read_text(encoding="utf-8"))

        # rejects / allows
        if data.get("entries"):
            from ..policy import rejects_ids, allows_ids

            gid2 = self.config.game or data.get("game_id") or data.get("game") or ""
            if rejects_ids(gid2) or allows_ids(gid2):
                active_modules = None
                if self._feature("module_filter"):
                    preset = (
                        getattr(self.config, "preset", None)
                        or getattr(self.config, "funnel", None)
                    )
                    active_modules = set(
                        resolve_modules(
                            modules=self.config.modules,
                            preset=preset,
                            game_id=gid2,
                        )
                    )
                self._apply_check_reject(
                    data["entries"],
                    data,
                    active_modules=active_modules,
                )

        data = convert_format(data)

        # Active modules for pending + build filter
        if self._feature("module_filter") or data.get("game_id") == self.config.game:
            preset = (
                getattr(self.config, "preset", None)
                or getattr(self.config, "funnel", None)
            )
            self._axvj_active_modules = set(
                resolve_modules(
                    modules=self.config.modules,
                    preset=preset,
                    game_id=self.config.game,
                )
            )
        else:
            self._axvj_active_modules = None

        has_key = bool(self.config.api_key) or bool(
            self.config.api_key_env and os.environ.get(self.config.api_key_env)
        )
        seed_only = self.config.seed_only or (
            self._feature("seed_on_no_key") and not has_key
        )
        active = getattr(self, "_axvj_active_modules", None)

        if not seed_only:
            # --- 3. Diff: texts.json vs cache ---
            free_texts = data.get("free_texts") or []

            def _needs_llm(e: dict) -> bool:
                if e.get("_reject"):
                    return False
                orig = e.get("original") or ""
                # Placeholders (？ / ？？？) — keep JP as-is, never call API
                if not self._has_translatable_jp(orig):
                    if not (e.get("translated") or "").strip():
                        e["translated"] = orig
                    return False
                # 200 with ZH or 404 garbled → skip
                if _is_cache_resolved(cache, orig, self._usable_zh):
                    return False
                if active is not None:
                    mid = stamp_entry_module(e, game_id=self.config.game)
                    if mid is None or mid not in active:
                        return False
                return True

            skipped_placeholder = 0
            skipped_resolved = 0
            for e in free_texts:
                if e.get("_reject"):
                    continue
                if active is not None:
                    mid = stamp_entry_module(e, game_id=self.config.game)
                    if mid is None or mid not in active:
                        continue
                orig = e.get("original") or ""
                if not self._has_translatable_jp(orig):
                    if not (e.get("translated") or "").strip():
                        e["translated"] = orig
                    skipped_placeholder += 1
                elif _is_cache_resolved(cache, orig, self._usable_zh):
                    skipped_resolved += 1

            pending = [e for e in free_texts if _needs_llm(e)]
            extra = []
            if skipped_placeholder:
                extra.append(f"占位 {skipped_placeholder}")
            if skipped_resolved:
                extra.append(f"已缓存/404 {skipped_resolved}")
            self._log(
                "info",
                f"[翻译差集] 待翻 {len(pending)} / free_texts {len(free_texts)}"
                + (f"（跳过 {'、'.join(extra)}）" if extra else ""),
            )

            # --- 4. LLM by module, then batch_size within each module ---
            cache_lock = threading.Lock()
            by_mod: dict[str, list[dict]] = defaultdict(list)
            for e in pending:
                mid = (
                    stamp_entry_module(e, game_id=self.config.game)
                    or e.get("module")
                    or "_none"
                )
                by_mod[str(mid)].append(e)

            mod_order: list[str] = []
            if self.config.game:
                try:
                    mod_order = list(load_modules(self.config.game).keys())
                except FileNotFoundError:
                    mod_order = []
            ordered_mids = [m for m in mod_order if m in by_mod]
            for m in sorted(by_mod.keys()):
                if m not in ordered_mids:
                    ordered_mids.append(m)

            # jobs: (global_idx, module_id, batch, extra_rules)
            jobs: list[tuple[int, str, list[dict], list[str]]] = []
            gi = 0
            bs = max(1, int(self.config.batch_size))
            for mid in ordered_mids:
                entries = by_mod[mid]
                entries.sort(
                    key=lambda e: (e.get("address") or "", e.get("original") or "")
                )
                rules = module_translate_rules(self.config.game or "", mid)
                mod_batches = [
                    entries[i : i + bs] for i in range(0, len(entries), bs)
                ]
                self._log(
                    "info",
                    f"[翻译] 模块={mid} pending={len(entries)} "
                    f"batches={len(mod_batches)} rules={len(rules)}",
                )
                for b in mod_batches:
                    jobs.append((gi, mid, b, rules))
                    gi += 1

            total = len(jobs)
            if total:
                self._ensure_translator()
                self._log(
                    "info",
                    Messages.BATCH_PROGRESS.format(
                        total=total, workers=self.config.max_workers
                    ),
                )
                done_count = 0

                def process_batch(job):
                    idx, _mid, batch, rules = job
                    self._translate_free_batch(batch, extra_rules=rules)
                    appended = self._append_batch_to_cache(
                        cache, output_path, batch, cache_lock
                    )
                    return idx, batch, appended

                with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                    futures = {
                        executor.submit(process_batch, job): job[0]
                        for job in jobs
                    }
                    for future in as_completed(futures):
                        done_count += 1
                        idx, batch, appended = future.result()
                        self._log(
                            "info",
                            Messages.BATCH_COMPLETE.format(
                                current=done_count,
                                total=total,
                                batch_id=idx + 1,
                            )
                            + (f" (+cache {appended})" if appended else ""),
                        )
                        sample = next(
                            (
                                e
                                for e in batch
                                if self._usable_zh(
                                    e.get("original") or "",
                                    e.get("translated") or "",
                                )
                            ),
                            None,
                        )
                        if sample:
                            try:
                                print(
                                    f"  e.g. {sample['original']!r} → "
                                    f"{sample['translated']!r}"
                                )
                            except UnicodeEncodeError:
                                print(f"  batch {idx + 1} done")
                        self.callbacks.on_progress(
                            "translate",
                            done_count,
                            total,
                            f"Batch {idx + 1} completed",
                        )
        else:
            self._log(
                "info",
                "[翻译] seed_only：跳过 API（流程 1→2→5）",
            )

        # --- 4b/5 prep: harvest + always flush disk ---
        harvested = self._harvest_into_cache(data, cache)
        _save_translation_cache(output_path, cache, self._usable_zh)
        try:
            disk_raw = json.loads(output_path.read_text(encoding="utf-8"))
            disk_n = len(disk_raw) if isinstance(disk_raw, list) else len(disk_raw)
        except (OSError, json.JSONDecodeError):
            disk_n = 0
        self._log(
            "info",
            f"[翻译缓存] 落盘 {output_path.name}: {disk_n} 条"
            + (f"（本轮新收获 {harvested}）" if harvested else ""),
        )

        # --- 5. texts.json + cache → translate.build.json ---
        filled = self._apply_cache_to_data(data, cache)
        self._log("info", f"[翻译缓存] 回填 entries {filled} 条")

        if self._feature("flat_entry_format") or data.get("game_id") == self.config.game:
            flat = []
            for table in data.get("tables") or []:
                flat.extend(table.get("entries") or [])
            flat.extend(data.get("free_texts") or [])
            data = {
                "game": self.config.game,
                "game_id": self.config.game,
                "source_lang": self.config.source_lang,
                "modules": self.config.modules,
                "count": len(flat),
                "entries": flat,
                "tables": data.get("tables") or [],
                "free_texts": data.get("free_texts") or [],
            }

        try:
            self._write_translate_build(data)
        except Exception as e:  # pragma: no cover
            self._log("warning", f"[翻译通路] translate.build.json 生成失败: {e}")

        return output_path

    def _write_translate_build(self, data: dict) -> None:
        """决策每条目的注入 type 并编码 target_hex，写 translate.build.json。

        短语码（词典 + 自动 upgrade 预分配）在此阶段确定并写入 phrases，
        build 阶段据此生成 PhraseTable 并按 type 注入。

        勾选了模块时（``_axvj_active_modules``）只写入勾选模块条目，
        避免未勾选模块（如高风险混杂）出现在 build 里误导验收。
        """
        from ..translate_plan import dedupe_entries_by_id, plan_entries

        flat = dedupe_entries_by_id(data.get("entries") or [])
        if not flat:
            return

        active = getattr(self, "_axvj_active_modules", None)
        active_list: list[str] | None = None
        if active is not None and self._feature("module_filter"):
            from ..modules import filter_entries_by_modules

            before = len(flat)
            active_list = sorted(active)
            flat = filter_entries_by_modules(
                flat, active_list, game_id=self.config.game
            )
            dropped = before - len(flat)
            if dropped:
                self._log(
                    "info",
                    f"[翻译通路] 按勾选模块收窄 build: {before} → {len(flat)} "
                    f"（去掉未勾选 {dropped}）[modules={active_list}]",
                )
            if not flat:
                self._log("warning", "[翻译通路] 勾选模块下无条目，跳过 translate.build.json")
                return

        # 分配词典短语码（build 阶段不再重新分配，共享同一码表）
        self.charmap._phrase_codes = {}
        if self._custom_translations:
            phrases = sorted(
                {
                    self.charmap._sanitize(v)
                    for v in self._custom_translations.values()
                    if len(v) > 1
                },
                key=lambda s: (len(s), s),
            )
            for code, s in enumerate(phrases):
                self.charmap._phrase_codes[s] = code

        phrase_codes = self.charmap._phrase_codes
        # 编排期用原盘校验指针；build.json 直入，不再在 inject 时改路径
        rom_bytes = None
        rom_path = getattr(self.config, "rom_path", None)
        if rom_path:
            try:
                rp = Path(rom_path)
                if rp.is_file():
                    rom_bytes = rp.read_bytes()
            except OSError as exc:
                self._log(
                    "warning",
                    f"[翻译通路] 无法读取 ROM 做指针校验 ({rom_path}): {exc}",
                )
        if rom_bytes is None:
            self._log(
                "warning",
                "[翻译通路] 无 ROM，跳过指针校验（relocate/hook 仅用登记指针）",
            )
        plans = plan_entries(
            flat,
            self.charmap,
            phrase_codes,
            game_id=self.config.game,
            rom=rom_bytes,
        )

        phrases_by_code = [None] * len(phrase_codes)
        for s, code in phrase_codes.items():
            phrases_by_code[code] = s

        from ..translate_plan import module_write_build_meta
        from ..config_loader import (
            alloc_style_channels,
            collect_module_left_px,
            load_styles,
            module_left_px,
            module_phrase_channel,
            module_style_id,
        )

        game_id = self.config.game or ""
        entry_rows = []
        for e, p in zip(flat, plans):
            mid = e.get("module") or e.get("_axvj_module") or ""
            row = {
                "id": e.get("id", ""),
                "type": p["type"],
                "address": p.get("address") or e.get("address", ""),
                "byte_length": p.get("byte_length", e.get("byte_length", 0)),
                "module": mid,
                "original": e.get("original", ""),
                "translated": e.get("translated", ""),
                "original_hex": e.get("original_hex", ""),
                "target_hex": p.get("target_hex", ""),
                "_reject": bool(e.get("_reject")),
            }
            if p.get("fd_rebased"):
                row["fd_rebased"] = True
            ptrs = p.get("pointer_sources") or []
            if ptrs:
                row["pointer_sources"] = ptrs
            if p.get("phrase_code") is not None:
                row["phrase_code"] = p["phrase_code"]
            if p.get("reason"):
                row["reason"] = p["reason"]
            if e.get("check_score") is not None:
                row["check_score"] = e.get("check_score")
            hits = list(e.get("check_hits") or [])
            if hits:
                row["check_hits"] = hits
            wmeta = module_write_build_meta(game_id, mid)
            if wmeta is not None:
                row["write"] = wmeta
            sid = module_style_id(game_id, mid)
            if sid:
                row["style"] = sid
                row["f9"] = module_phrase_channel(game_id, mid)
            left_px = module_left_px(game_id, mid)
            if left_px:
                row["left"] = left_px
            entry_rows.append(row)

        style_alloc = alloc_style_channels(game_id)
        payload = {
            "game_id": self.config.game,
            "modules": list(self.config.modules or []) if self.config.modules else active_list,
            "active_modules": active_list,
            "count": len(flat),
            "phrases": phrases_by_code,
            "styles": load_styles(game_id),
            "style_alloc": {k: f"0x{v:02X}" for k, v in style_alloc.items()},
            "module_left": collect_module_left_px(game_id),
            "entries": entry_rows,
        }
        build_dir = Path(self.config.work_dir) / self.config.game
        build_dir.mkdir(parents=True, exist_ok=True)
        build_path = build_dir / "translate.build.json"
        build_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        from collections import Counter as _C

        _types = _C(row["type"] for row in entry_rows)
        self._log(
            "info",
            "[翻译通路] translate.build.json → "
            + ", ".join(f"{t}={n}" for t, n in _types.most_common()),
        )

    def _translate_table(self, table: dict):
        """Legacy table bucket — corpus is unified; prefer free_texts path.

        Kept so old ``tables``-shaped JSON still gets glossary/seed treatment
        if anything still passes a non-empty table (convert_format normally
        flattens everything into free_texts).
        """
        needs_llm: list[dict] = []
        active = getattr(self, "_axvj_active_modules", None)
        from ..modules import stamp_entry_module

        ct_hit = 0
        for entry in table["entries"]:
            original = entry["original"].strip('"')
            if active is not None:
                mid = stamp_entry_module(entry, game_id=self.config.game)
                if mid is None:
                    continue
                if mid not in active:
                    continue
                if (entry.get("translated") or "") == original and not self.config.seed_only:
                    entry["translated"] = ""
                elif self._usable_zh(original, entry.get("translated") or ""):
                    continue
            if self.config.target_lang == "zh-Hans" and original in _TERM_OVERRIDES:
                entry["translated"] = _TERM_OVERRIDES[original]
                continue
            if (
                self.config.target_lang == "zh-Hans"
                and original in _TRAINER_CLASS_OVERRIDES
            ):
                entry["translated"] = _TRAINER_CLASS_OVERRIDES[original]
                continue
            ct_zh = self._custom_translations.get(original)
            if ct_zh:
                entry["translated"] = ct_zh
                ct_hit += 1
                continue
            zh = self.glossary.lookup(original)
            if zh:
                ok, _bad = self.charmap.can_encode(zh)
                if ok:
                    entry["translated"] = zh
                    continue
            needs_llm.append(entry)

        if needs_llm:
            self._translate_table_llm_batch(needs_llm)
            if ct_hit:
                msg = f"[自定义翻译] 命中: {ct_hit}/{len(table['entries'])} 条 (跳过 API)"
                self._log("info", msg)
                print(msg)

        for entry in table["entries"]:
            original = entry["original"].strip('"')
            translated = entry.get("translated", "")
            if translated and translated != original:
                self.glossary.add_term(original, translated, "dynamic")

    def _translate_table_llm_batch(self, entries: list[dict]):
        """Batch LLM translate table entries (descriptions, map names, battle text).

        Filters out entries that are pure control codes (nothing for LLM to
        translate), then sends the rest in batches of batch_size, same as
        free-text processing.
        """
        self._ensure_translator()
        if not self.translator:
            # No LLM — do not wipe existing ZH; only fill blanks with original
            for entry in entries:
                orig = entry.get("original", "")
                tr = entry.get("translated") or ""
                if self._usable_zh(orig.strip('"'), tr):
                    continue
                if not tr.strip():
                    entry["translated"] = orig
            return
        import re

        # Separate: entries with real text vs pure control-code entries
        to_translate: list[tuple[dict, str, list]] = []  # (entry, protected, codes)
        for entry in entries:
            original = entry["original"].strip('"')
            protected, codes = protect(original)
            # Count actual alphabetic letters after stripping {C0}-style placeholders
            cleaned = re.sub(r"\{C\d+\}", "", protected)
            if sum(c.isalpha() for c in cleaned) >= 2:
                to_translate.append((entry, protected, codes))
            else:
                # Pure control codes – keep original, nothing to translate
                entry["translated"] = original

        if not to_translate:
            return

        # Batch translate in groups of batch_size (same as free texts)
        batch_size = self.config.batch_size
        for i in range(0, len(to_translate), batch_size):
            chunk = to_translate[i : i + batch_size]
            protected_list = [p for _, p, _ in chunk]
            all_text = " ".join(e["original"] for e, _, _ in chunk)
            glossary_ctx = self._format_glossary(all_text)

            try:
                results = self.translator.translate_batch(protected_list, glossary_ctx)
            except Exception as e:
                print(f"[Table batch LLM failed: {e}, keeping previous translations]")
                # Do not write JP as fake「译文」— leave prior / empty for next run
                continue

            for (entry, _, codes), result in zip(chunk, results):
                clean = _strip_llm_newlines(result)
                translated = restore(clean, codes)
                if _is_garbled_marker(translated):
                    entry["translated"] = ""
                    entry["_cache_status"] = CACHE_STATUS_GARBLED
                else:
                    entry["translated"] = translated

    def _translate_free_batch(
        self, batch: list[dict], extra_rules: list[str] | None = None
    ):
        """Translate a batch of free text entries via LLM."""
        # Apply hardcoded overrides
        remaining = []
        for entry in batch:
            entry_id = entry.get("id", "")
            original = entry.get("original", "").strip('"')
            if (self.config.target_lang == "zh-Hans" and
                original in _TERM_OVERRIDES):
                entry["translated"] = _TERM_OVERRIDES[original]
            elif (self.config.game == "firered" and
                self.config.target_lang == "zh-Hans" and
                entry_id in _HARDCODED_TRANSLATIONS):
                entry["translated"] = _HARDCODED_TRANSLATIONS[entry_id]
            elif original in self._custom_translations:
                entry["translated"] = self._custom_translations[original]
            else:
                remaining.append(entry)

        if not remaining:
            return

        originals = [unwrap_quotes(e.get("original") or "") for e in remaining]

        # Protect control codes
        protected_list = []
        codes_list = []
        for text in originals:
            protected, codes = protect(text)
            protected_list.append(protected)
            codes_list.append(codes)

        # Build glossary context
        all_text = " ".join(originals)
        glossary_ctx = self._format_glossary(all_text)

        # Translate
        try:
            results = self.translator.translate_batch(
                protected_list, glossary_ctx, extra_rules=extra_rules
            )
        except Exception as e:
            print(f"[Batch failed after retries: {e}, keeping previous translations]")
            # Do not overwrite with JP original — empty stays empty for retry
            return

        # Restore and wrap
        for i, entry in enumerate(remaining):
            clean = _strip_llm_newlines(results[i])
            # Detect fixed garbled marker BEFORE restore/wrap (marker has no codes)
            if _is_garbled_marker(clean) or _is_garbled_marker(results[i]):
                entry["translated"] = ""
                entry["_cache_status"] = CACHE_STATUS_GARBLED
                continue
            translated = restore(clean, codes_list[i])
            if _is_garbled_marker(translated):
                entry["translated"] = ""
                entry["_cache_status"] = CACHE_STATUS_GARBLED
                continue
            translated = wrap_text(
                translated,
                target_lang=self.config.target_lang,
                **module_wrap_kwargs(
                    self.config.game,
                    entry.get("module") or entry.get("_axvj_module"),
                ),
            )
            if (
                self._feature("failed_zh_detection")
                and self.config.target_lang.startswith("zh")
            ):
                from ..seed_translate import looks_like_failed_zh_translation

                if looks_like_failed_zh_translation(entry.get("original", ""), translated):
                    # Leave empty so a later retry can pick it up; do not keep JP stubs
                    entry["translated"] = ""
                    continue
            entry["translated"] = translated

        # One retry pass for entries the model echoed back in Japanese
        if (
            self._feature("failed_zh_detection")
            and self.config.target_lang.startswith("zh")
        ):
            retry = [
                e
                for e in remaining
                if not e.get("translated")
                and e.get("_cache_status") != CACHE_STATUS_GARBLED
            ]
            if retry and len(retry) < len(remaining):
                self._translate_free_batch_once(retry, extra_rules=extra_rules)

    def _translate_free_batch_once(
        self, remaining: list[dict], extra_rules: list[str] | None = None
    ):
        """Single-shot LLM batch without nested retry (used after failed ja→zh)."""
        if not remaining:
            return
        originals = [unwrap_quotes(e.get("original") or "") for e in remaining]
        protected_list = []
        codes_list = []
        for text in originals:
            protected, codes = protect(text)
            protected_list.append(protected)
            codes_list.append(codes)
        all_text = " ".join(originals)
        glossary_ctx = self._format_glossary(all_text)
        try:
            results = self.translator.translate_batch(
                protected_list, glossary_ctx, extra_rules=extra_rules
            )
        except Exception as e:
            print(f"[Retry batch failed: {e}]")
            return
        from ..seed_translate import looks_like_failed_zh_translation

        for i, entry in enumerate(remaining):
            clean = _strip_llm_newlines(results[i])
            if _is_garbled_marker(clean) or _is_garbled_marker(results[i]):
                entry["translated"] = ""
                entry["_cache_status"] = CACHE_STATUS_GARBLED
                continue
            translated = restore(clean, codes_list[i])
            if _is_garbled_marker(translated):
                entry["translated"] = ""
                entry["_cache_status"] = CACHE_STATUS_GARBLED
                continue
            translated = wrap_text(
                translated,
                target_lang=self.config.target_lang,
                **module_wrap_kwargs(
                    self.config.game,
                    entry.get("module") or entry.get("_axvj_module"),
                ),
            )
            if looks_like_failed_zh_translation(entry.get("original", ""), translated):
                entry["translated"] = ""
            else:
                entry["translated"] = translated

    def _format_glossary(self, text: str) -> str:
        terms = self.glossary.get_context_terms(text)
        if not terms:
            return ""
        return "\n".join(f"  {src} = {tgt}" for src, tgt in terms.items())

    def run_full(self) -> Path:
        """Run full pipeline: translate → tile → hook → build.

        Stage packs under configs/<game_id>/: game.json, translate/,
        tile/, hook/. ``build`` is abstract (armips + injection, no folder).
        """
        rom_path = self.config.rom_path
        output_dir = self.config.output_dir
        work_dir = self.config.work_dir
        if not rom_path:
            raise ValueError("rom_path is required in config")
        if not output_dir:
            raise ValueError("output_dir is required in config")

        try:
            # --- translate stage: extract texts + build fonts + translate ---
            self.callbacks.on_stage_change("translate", "started")
            texts_path = self._extract_texts(rom_path, work_dir)

            from ..config_loader import load_custom_translations, texts_translated_path
            self._custom_translations = load_custom_translations(self.config.game)

            self._fonts_from_bdf = False
            if self.config.bdf_font_path and is_cjk_language(self.config.target_lang):
                self._build_font_from_bdf(work_dir)
                self._ensure_default_fonts(
                    work_dir, overwrite_bins=not bool(self._fonts_from_bdf)
                )
            elif is_cjk_language(self.config.target_lang):
                self._ensure_default_fonts(work_dir)

            try:
                translated_path = texts_translated_path(self.config.game)
            except Exception:
                translated_path = work_dir / self.config.game / "texts_translated.json"
            translated_path = self.translate_texts(texts_path, translated_path)
            self.callbacks.on_stage_change("translate", "completed")

            # --- hook + build, then tile (tiles must not run before fonts) ---
            output_rom = output_dir / f"{rom_path.stem}_translated.gba"
            built = self.build_rom(rom_path, translated_path, output_rom)

            if self.config.tiles_dir or self._default_tiles_dir(rom_path).is_dir():
                self.callbacks.on_stage_change("tile", "started")
                built = self._run_tiles(built, work_dir)
                # Ensure final deliverable path is the tile-patched ROM
                if built.resolve() != output_rom.resolve():
                    output_rom.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(built, output_rom)
                        built = output_rom
                    except OSError as exc:
                        alt = output_rom.with_name(
                            f"{output_rom.stem}_new{output_rom.suffix}"
                        )
                        if built.resolve() != alt.resolve():
                            shutil.copy2(built, alt)
                            built = alt
                        self._log(
                            "warn",
                            f"output {output_rom.name} locked ({exc}); "
                            f"deliverable is {built.name} — close mGBA and rename",
                        )
                self.callbacks.on_stage_change("tile", "completed")
            return built
        except Exception as e:
            self.callbacks.on_error(e)
            raise

    def _default_tiles_dir(self, rom_path: Path) -> Path:
        """Default tiles dir: configs/<game_id>/tiles (or tile), else util/works."""
        from ..config_loader import game_config_dir

        try:
            base = game_config_dir(self.config.game or rom_path.stem)
            for name in ("tiles", "tile"):
                cfg_tiles = base / name
                if cfg_tiles.is_dir() and (
                    list(cfg_tiles.glob("*_meta.json"))
                    or list((cfg_tiles / "meta").glob("*_meta.json"))
                ):
                    return cfg_tiles
        except Exception:
            pass
        return (
            Path(__file__).resolve().parent.parent.parent / "util" / "works"
            / rom_path.stem / "tiles"
        )

    def _tiles_new_palette_addr(self, rom_path: Path) -> str | None:
        """Optional ``tiles.new_palette`` from util yaml (e.g. 0x09200000)."""
        try:
            import yaml
        except ImportError:
            return None
        game_id = self.config.game or rom_path.stem
        yaml_path = (
            Path(__file__).resolve().parent.parent.parent
            / "util"
            / "configs"
            / f"{game_id}.yaml"
        )
        if not yaml_path.is_file():
            return None
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            addr = (data.get("tiles") or {}).get("new_palette")
            return str(addr) if addr else None
        except Exception:
            return None

    def _tiles_safe_alloc_base(self, rom_path: Path) -> str:
        """GBA addr for tiles palette/LZ after text+font inject.

        Util yaml often sets ``new_palette=0x09200000``, but post-build that
        range is font/text expand (sparse 0x00 looks "free" and is unsafe).
        Always append past the current ROM end for the pipeline tiles stage.
        """
        end_off = (rom_path.stat().st_size + 3) & ~3
        return f"0x{end_off + 0x08000000:08X}"

    def _run_tiles(self, rom_path: Path, work_dir: Path) -> Path:
        """Tiles stage: import PNG edits into an already-built ROM.

        Must run **after** ``build_rom``. Palette/LZ go past ROM end — never
        reuse util yaml ``0x09200000`` (shared with font/text expand).
        """
        tiles_dir = self.config.tiles_dir or self._default_tiles_dir(rom_path)
        if not tiles_dir.is_dir():
            self._log("info", f"tiles dir not found, skipping: {tiles_dir}")
            return rom_path
        meta_dir = tiles_dir / "meta" if (tiles_dir / "meta").is_dir() else tiles_dir
        meta_files = sorted(meta_dir.glob("*_meta.json"))
        if not meta_files:
            self._log("info", f"no *_meta.json in tiles dir, skipping: {meta_dir}")
            return rom_path

        tmp_out = Path(work_dir) / f"{Path(rom_path).stem}_tiles{Path(rom_path).suffix}"
        tmp_out.parent.mkdir(parents=True, exist_ok=True)
        script = (
            Path(__file__).resolve().parent.parent.parent / "util" / "tiles_patcher.py"
        )
        args = [
            sys.executable,
            str(script),
            "import",
            str(rom_path),
            str(tiles_dir),
            "-o",
            str(tmp_out),
        ]
        alloc = self._tiles_safe_alloc_base(rom_path)
        yaml_pal = self._tiles_new_palette_addr(rom_path)
        args.extend(["--new-palette", alloc, "--reloc-base", alloc])
        self._log(
            "info",
            f"tiles: {len(meta_files)} meta(s) from {tiles_dir} -> {tmp_out.name}"
            f", new_palette={alloc}"
            + (f" (ignore yaml {yaml_pal})" if yaml_pal else ""),
        )
        r = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"tiles_patcher import failed:\n{r.stdout}\n{r.stderr}"
            )
        self._log("info", f"tiles patched from {tiles_dir}")
        try:
            shutil.copy2(tmp_out, rom_path)
            return Path(rom_path)
        except OSError as exc:
            # mGBA 等占用目标文件时保留 *_tiles 产物，避免整次 full 失败
            self._log(
                "warn",
                f"tiles: cannot overwrite {rom_path.name} ({exc}); "
                f"left {tmp_out.name}",
            )
            return Path(tmp_out)

    def extract_texts(
        self,
        rom_path: Path,
        output_path: Path | None = None,
        *,
        modules: list[str] | None = None,
    ) -> Path:
        """Load curated ``configs/<game_id>/translate/texts.json`` (no ROM dump).

        ``modules`` is ignored (entries already stamped). If ``output_path`` is
        set and differs from the config file, copies there for CLI convenience.
        """
        import shutil

        from ..config_loader import texts_json_path
        from ..game_backends import detect_game

        game_id = detect_game(rom_path)
        if game_id == "unknown":
            raise ValueError(f"Unknown ROM: {rom_path}")
        self.config.game = game_id
        set_active_game_id(game_id)
        src = texts_json_path(game_id)
        if not src.is_file():
            raise FileNotFoundError(
                f"缺少语料 {src}；请用 util texts_patcher export 后晋升到 "
                f"configs/{game_id}/translate/texts.json"
            )
        self._log("info", f"[texts] 读取 {src}")
        if output_path is None:
            return src
        output_path = Path(output_path)
        if output_path.resolve() != src.resolve():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, output_path)
            return output_path
        return src

    def _extract_texts(self, rom_path: Path, output_dir: Path) -> Path:
        """Load ``translate/texts.json`` (no ROM extract)."""
        return self.extract_texts(rom_path, output_path=None)

    def _apply_check_reject(
        self,
        entries: list[dict],
        data: dict,
        *,
        active_modules: set[str] | None = None,
    ) -> int:
        """按 ``rejects`` / ``allows`` 标记 ``_reject``（不写额外文件）。

        - id ∈ rejects 且 id ∉ allows → 拒绝
        - 若给定 ``active_modules``：先按模块勾选收窄
        """
        from ..policy import allows_ids, rejects_ids

        game_id = (
            self.config.game
            or data.get("game_id")
            or data.get("game")
            or ""
        )
        allows = allows_ids(game_id)
        rejects = rejects_ids(game_id)

        candidates = entries
        if active_modules is not None:
            from ..modules import stamp_entry_module

            candidates = []
            for e in entries:
                e.pop("_reject", None)
                e.pop("check_score", None)
                e.pop("check_hits", None)
                mid = stamp_entry_module(e, game_id=game_id)
                if mid is not None and mid in active_modules:
                    candidates.append(e)

        rejected = 0
        for e in candidates:
            eid = e.get("id") or ""
            if eid in rejects and eid not in allows:
                e["_reject"] = True
                e["translated"] = ""
                e["check_hits"] = ["rejects"]
                rejected += 1

        scope = (
            f"模块内 {len(candidates)}/{len(entries)}"
            if active_modules is not None
            else f"{len(candidates)}"
        )
        self._log(
            "info",
            f"[校验] rejects/allows: 拒绝 {rejected}/{len(candidates)} 条"
            f"（候选 {scope}）",
        )
        return rejected

    @staticmethod
    def _decompress_4bpp_glyph(glyph_data: bytes) -> bytearray:
        """128 bytes 4bpp tiles → 256 bytes 16×16 pixel array (row-major, 0-15 per pixel)."""
        pixels = bytearray(256)
        for tile_col in range(2):
            for tile_row in range(2):
                tile_idx = tile_col * 2 + tile_row  # TL=0, BL=1, TR=2, BR=3
                off = tile_idx * 32
                for ty in range(8):
                    py = tile_row * 8 + ty
                    for tx in range(4):
                        byte = glyph_data[off + ty * 4 + tx]
                        px = tile_col * 8 + tx * 2
                        pixels[py * 16 + px] = (byte >> 4) & 0x0F
                        pixels[py * 16 + px + 1] = byte & 0x0F
        return pixels

    @staticmethod
    def _compress_4bpp_glyph(pixels: bytearray) -> bytes:
        """256 bytes pixel array → 128 bytes 4bpp glyph data."""
        glyph = bytearray(128)
        for tile_col in range(2):
            for tile_row in range(2):
                tile_idx = tile_col * 2 + tile_row  # TL=0, BL=1, TR=2, BR=3
                off = tile_idx * 32
                for ty in range(8):
                    py = tile_row * 8 + ty
                    for tx in range(4):
                        px = tile_col * 8 + tx * 2
                        byte = ((pixels[py * 16 + px] & 0x0F) << 4) | (pixels[py * 16 + px + 1] & 0x0F)
                        glyph[off + ty * 4 + tx] = byte
        return bytes(glyph)

    def _ensure_default_fonts(
        self, work_dir: Path | None = None, *, overwrite_bins: bool = True
    ):
        """Copy project-level default font .bin files to work dir, then generate phrase lookup table.

        ``overwrite_bins=False`` keeps bins already produced by ``_build_font_from_bdf``
        (GUI/CLI ``--bdf``); still refreshes phrase_data.asm and fills missing slots.
        """
        game_work = (work_dir or Path("work")) / self.config.game
        fonts_dir = game_work / "graphic" / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)

        src_dir = Path(__file__).resolve().parents[3] / "graphic" / "fonts"
        if not src_dir.is_dir():
            self._log("warning", "No default fonts found in project graphic/fonts/")
        else:
            copied = 0
            kept = 0
            for f in src_dir.glob("*.bin"):
                dst = fonts_dir / f.name
                if not overwrite_bins and dst.is_file() and dst.stat().st_size > 0:
                    kept += 1
                    continue
                dst.write_bytes(f.read_bytes())
                copied += 1
            if not overwrite_bins and kept:
                self._log(
                    "info",
                    f"Keep BDF-built fonts: {kept} existing bin(s); "
                    f"synced {copied} missing -> {fonts_dir}",
                )
            else:
                self._log("info", f"Default fonts synced: {copied} files -> {fonts_dir}")

        # PhraseTable early write; pack 阶段以 translate.build.json 为准重生
        if not self._custom_translations:
            return
        sideload_encode = getattr(self.charmap, "_sideload_encode", None)
        if sideload_encode is None:
            sideload_encode = self.charmap.encode

        pc = getattr(self.charmap, "_phrase_codes", None)
        if pc:
            entries = sorted(pc.items(), key=lambda kv: kv[1])
            phrases = [s for s, _ in entries]
        else:
            phrases = sorted(
                {self.charmap._sanitize(v) for v in self._custom_translations.values() if len(v) > 1},
                key=lambda s: (len(s), s),
            )
        if not phrases:
            return

        from ..build_rom_data import write_phrase_data_asm

        phrase_asm = fonts_dir / "phrase_data.asm"
        _, n_ph, nbytes = write_phrase_data_asm(phrases, sideload_encode, phrase_asm)
        self._log("info", f"[短语] PhraseTable {n_ph} 条流, {nbytes}B -> {phrase_asm.name}")

    def _build_font_from_bdf(self, work_dir: Path | None = None):
        """Generate font .bin from config's BDF path or auto-detect."""
        import shutil
        from ..config_loader import load_game_config

        cfg = load_game_config(self.config.game)
        fp_cfg = cfg.get("font_patch", {})
        if not fp_cfg or not fp_cfg.get("font_slots"):
            return

        game_work = (work_dir or Path("work")) / self.config.game
        game_work.mkdir(parents=True, exist_ok=True)

        bdf_path = self.config.bdf_font_path
        if not bdf_path or not bdf_path.exists():
            for f in sorted(Path("fonts").glob("*.bdf")):
                bdf_path = f
                break
        if not bdf_path or not bdf_path.exists():
            self._log("warning", "No BDF font found, skipping font build")
            return

        try:
            src = get_charmap_path(self.config.game)
            if src.exists():
                shutil.copy2(src, game_work / "charmap.txt")

            fonts_dir = game_work / "graphic" / "fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)

            slots = fp_cfg.get("font_slots", [])
            labels = [s.get("label", "Unknown") for s in slots]
            sizes = [s.get("slot_size", s.get("glyph_count", 7168) * s.get("bytes_per_glyph", 128)) for s in slots]
            bpg = int(slots[0].get("bytes_per_glyph", 128)) if slots else 128
            prefix = fp_cfg.get("font_bin_prefix", "PokeRSFontChs")

            _scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
            args = [
                sys.executable,
                str(_scripts_dir / "build_chinese_font.py"),
                "--bdf", str(bdf_path),
                "--charmap", str(game_work / "charmap.txt"),
                "--output-dir", str(fonts_dir),
                "--slot-labels", *labels,
                "--slot-sizes", *(str(s) for s in sizes),
                "--prefix", prefix,
                "--bytes-per-glyph", str(bpg),
            ]
            if fp_cfg.get("shadow") is False:
                args.append("--no-shadow")
            else:
                args.append("--shadow")
            r = subprocess.run(args, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                raise RuntimeError(f"Font generation failed:\n{r.stderr}\n{r.stdout}")
            self._fonts_from_bdf = True
            self._log("info", f"Font generated from {bdf_path.name} -> {fonts_dir}")

            # Patch punctuation glyphs: baseline alignment + no pass-2 right spill.
            # build_chinese_font places all glyphs via bdf_to_ink12 which ignores BDF
            # baseline (bbx_y) and doesn't restrict glyphs to slot cols 0-7, causing
            # narrow characters like ? to show as ?? at end of sentence.
            try:
                _charmap_path = get_charmap_path(self.config.game)
                if _charmap_path.exists():
                    _no_shadow = fp_cfg.get("shadow") is False
                    _bdf_punct = Path("fonts/firefly-bdf-bitmap/fireflyR12.bdf")
                    if not _bdf_punct.exists():
                        # also check repo root
                        _alt = Path(__file__).resolve().parents[3] / "fonts" / "firefly-bdf-bitmap" / "fireflyR12.bdf"
                        if _alt.exists():
                            _bdf_punct = _alt
                        else:
                            _bdf_punct = None
                    for _bin in sorted(fonts_dir.glob("*.bin")):
                        _args_patch = [
                            sys.executable,
                            str(_scripts_dir / "patch_font_punct.py"),
                            "--font", str(_bin),
                            "--charmap", str(_charmap_path),
                            "--bdf", str(bdf_path),
                        ]
                        if _bdf_punct:
                            _args_patch += ["--bdf-punct", str(_bdf_punct)]
                        if _no_shadow:
                            _args_patch.append("--no-shadow")
                        subprocess.run(_args_patch, capture_output=True, text=True, timeout=60)
                    self._log("info", "Punctuation glyphs patched (baseline + no right spill)")
            except Exception as _e:
                self._log("warning", f"Punctuation patch failed: {_e}")
        except (FileNotFoundError, OSError) as e:
            self._fonts_from_bdf = False
            self._log("warning", f"Font generation skipped: {e}")
        except RuntimeError:
            self._fonts_from_bdf = False
            raise

    def _rebuild_data_from_build_plan(self, cache: dict[str, dict]) -> dict:
        """从 translate.build.json 重建注入数据，用 status 缓存覆盖翻译。"""
        build_path = (
            Path(self.config.work_dir) / self.config.game / "translate.build.json"
        )
        if not build_path.is_file():
            self._log(
                "warning",
                "texts_translated.json 是翻译缓存，但缺少 translate.build.json，"
                "无法重建注入条目（请先运行 translate/full）",
            )
            return {"tables": [], "free_texts": []}
        try:
            bp = json.loads(build_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._log(
                "warning",
                f"translate.build.json 读取失败: {build_path}",
            )
            return {"tables": [], "free_texts": []}
        entries = bp.get("entries") or []
        n = 0
        for e in entries:
            orig = e.get("original") or ""
            rec = _lookup_cache_rec(cache, orig)
            if rec and rec.get("status") == CACHE_STATUS_GARBLED:
                e["translated"] = orig
                continue
            tr = _zh_from_cache(cache, orig, self._usable_zh)
            if tr:
                e["translated"] = tr
                n += 1
        self._log(
            "info",
            f"从 translate.build.json 重建 {len(entries)} 条注入数据，"
            f"缓存覆盖 {n} 条翻译",
        )
        return {"entries": entries}

    def build_rom(
        self,
        original_rom: Path,
        translations_path: Path,
        output_path: Path,
    ) -> Path:
        """Build final translated ROM."""
        # Auto-detect game
        detected = detect_game(original_rom)
        if detected != "unknown":
            self.config.game = detected
            set_active_game_id(detected)
            self._log("info", Messages.DETECTED_GAME.format(game=self.config.game))

        data = json.loads(translations_path.read_text(encoding="utf-8"))
        if _is_status_cache_list(data) or (
            isinstance(data, dict) and _is_cache_map(data)
        ):
            cache = _load_translation_cache(translations_path, self._usable_zh)
            data = self._rebuild_data_from_build_plan(cache)
        data = convert_format(data)

        # Load game config (for charmap, expansion decision, font patch, etc.)
        cfg = {}
        fp_cfg = {}
        game_work = None
        try:
            cfg = load_game_config(self.config.game)
            fp_cfg = cfg.get("font_patch", {})
            game_work = Path(self.config.work_dir) / self.config.game
        except (FileNotFoundError, KeyError) as e:
            self._log("warning", f"[配置] 加载失败: {e}")

        # lexicon 仅作短语表；texts_translated 合并在 translate 开始前完成
        from ..config_loader import load_custom_translations, load_codec

        self._custom_translations = load_custom_translations(self.config.game)
        if self._custom_translations:
            self._log(
                "info",
                f"[配置] lexicon 已加载: {len(self._custom_translations)} 条",
            )

        # Refresh encoder from config (charmap with escape bytes, punct map, etc.)
        _charmap_cfg = dict(cfg.get("charmap") or {})
        codec_cm = (load_codec(self.config.game) or {}).get("charmap") or {}
        if isinstance(codec_cm, dict):
            _charmap_cfg = {**codec_cm, **_charmap_cfg}
        _charmap_cfg = self._resolve_charmap_cfg_path(_charmap_cfg, self.config.game)
        self.charmap = Charmap(
            target_lang=self.config.target_lang,
            charmap_cfg=_charmap_cfg,
        )

        # Assign 2-byte codes (0x0000-0xFFFF) to custom_translation phrases (>1 char)
        # 优先复用 translate 阶段的 translate.build.json phrases（含 upgrade 自动
        # 分配短语），保证 PhraseTable 与 translate.build.json 的 f980 码一致。
        self.charmap._phrase_codes: dict[str, int] = {}
        _bp_phrases: list | None = None
        try:
            _bp_path = (game_work or Path(self.config.work_dir) / self.config.game) / "translate.build.json"
            if _bp_path.exists():
                _bp_data = json.loads(_bp_path.read_text(encoding="utf-8"))
                _bp_phrases = _bp_data.get("phrases") or []
        except Exception:
            _bp_phrases = None
        if _bp_phrases:
            for code, s in enumerate(_bp_phrases):
                if s:
                    self.charmap._phrase_codes[s] = code
            self._log(
                "info",
                f"[短语] 复用 translate.build.json 码表: {len(_bp_phrases)} 条",
            )
        elif self._custom_translations:
            phrases = sorted(
                {self.charmap._sanitize(v) for v in self._custom_translations.values() if len(v) > 1},
                key=lambda s: (len(s), s),
            )
            for code, s in enumerate(phrases):
                self.charmap._phrase_codes[s] = code
            if phrases:
                self._log(
                    "info",
                    f"[短语] F9 XX 分配: {len(phrases)} 条码位 0x0000-0x{len(phrases)-1:04X} "
                    f"(默认通道 XX=80；write.op 改 XX，范围 01..7E)",
                )


        # Auto-switch F9 00 → F9 80: ONLY fixed-slot modules (stride/struct).
        # Trusted-ptr modules (scan/剧情/…) keep full F9 00 and relocate.
        # See docs/模块参数定义.md inject_body / module_is_fixed_slot.
        self._auto_phrase_extra: list[dict] = []
        if is_cjk_language(self.config.target_lang) and data:
            from ..modules import module_is_fixed_slot

            _pc = self.charmap._phrase_codes
            _raw_enc = self.charmap.encode  # pre-wrap: raw per-char encode
            _gid = self.config.game
            _all_inject = []
            for tbl in data.get("tables") or []:
                for en in tbl.get("entries") or []:
                    if "translated" in en:
                        _all_inject.append(en)
            _all_inject.extend(en for en in data.get("free_texts") or [] if "translated" in en)

            for en in _all_inject:
                t = (en.get("translated") or "").strip('"')
                o = (en.get("original") or "").strip('"')
                if not t or t == o:
                    continue
                mid = en.get("_axvj_module") or en.get("module")
                if not module_is_fixed_slot(_gid, mid):
                    continue
                bl = en.get("byte_length", 0)
                if bl < 5:
                    continue  # too small for even F9 80; keep original
                s = self.charmap._sanitize(t)
                if s in _pc:
                    continue
                raw_len = len(_raw_enc(t))
                if raw_len > bl:
                    code = len(_pc)
                    _pc[s] = code
                    self._auto_phrase_extra.append({
                        "original": o,
                        "translated": t,
                        "module": mid,
                        "byte_length": bl,
                        "raw_encoded_len": raw_len,
                    })
            if self._auto_phrase_extra:
                self._log(
                    "info",
                    f"[短语] 自动进 F9 80: {len(self._auto_phrase_extra)} 条 "
                    f"(仅定长槽 stride/struct 越槽)",
                )

        # Wrap encode: full-text match → F9 80 <high> <low> FF (rom_writer may patch →op)
        # else F9 00 per-char (side font, auto write).
        from ..config_loader import F9_EOS, F9_PHRASE_DEFAULT

        _orig_encode = self.charmap.encode
        self.charmap._sideload_encode = _orig_encode  # PhraseTable streams use this

        def _encode(text):
            s = self.charmap._sanitize(text)
            pc = getattr(self.charmap, "_phrase_codes", None)
            if pc and s in pc:
                code = pc[s]
                return bytes([
                    0xF9,
                    F9_PHRASE_DEFAULT,
                    (code >> 8) & 0xFF,
                    code & 0xFF,
                    F9_EOS,
                ])
            return _orig_encode(text)

        self.charmap.encode = _encode

        from ..config_loader import DEFAULT_WORD_COUNT, module_word_counts

        word_count_default = DEFAULT_WORD_COUNT
        word_count_modules = module_word_counts(self.config.game)
        writer = RomWriter(self.charmap, game=self.config.game,
                          target_lang=self.config.target_lang,
                          fp_cfg=fp_cfg,
                          word_count_default=word_count_default,
                          word_count_modules=word_count_modules)

        # Load ROM. If font patch expands itself (ARMIPS), do not pre-pad
        # (0xFF padding breaks free-space detection after armips).
        self._log("info", Messages.LOADING_ROM)
        rom = writer.load_rom(original_rom)
        if not fp_cfg.get("expands_rom", False):
            rom = writer.expand_rom(rom)
            self._log("info", Messages.ROM_EXPANDED.format(size=len(rom) // (1024 * 1024)))

        # --- hook stage: ARMIPS only (same build_rom pass as build) ---
        self.callbacks.on_stage_change("hook", "started")
        if is_cjk_language(self.config.target_lang):
            self._log("info", Messages.APPLYING_FONT_PATCH)

            # Ensure fonts + phrase_data.asm exist; do not clobber BDF-built bins.
            if fp_cfg and fp_cfg.get("font_slots"):
                self._ensure_default_fonts(
                    Path(self.config.work_dir),
                    overwrite_bins=not bool(getattr(self, "_fonts_from_bdf", False)),
                )

            temp_in = output_path.parent / "temp_fontpatch_in.gba"
            temp_out = output_path.parent / "temp_fontpatch_out.gba"
            temp_in.parent.mkdir(parents=True, exist_ok=True)
            writer.save_rom(rom, temp_in)
            apply_font_patch(temp_in, temp_out, font_patch_cfg=fp_cfg, work_dir=game_work, game_id=self.config.game)
            rom = writer.load_rom(temp_out)
            temp_in.unlink(missing_ok=True)
            temp_out.unlink(missing_ok=True)
            self._log("info", Messages.FONT_PATCH_APPLIED)
        else:
            self._log("info", Messages.SKIPPING_FONT_PATCH.format(lang=self.config.target_lang))
        self.callbacks.on_stage_change("hook", "completed")

        # --- build stage: RomWriter text injection + save ---
        self.callbacks.on_stage_change("build", "started")

        # Collect all entries
        all_entries = []
        for table in data["tables"]:
            for entry in table["entries"]:
                if entry.get("_reject"):
                    continue
                if "translated" in entry:
                    all_entries.append(entry)
        for entry in data["free_texts"]:
            if entry.get("_reject"):
                continue
            if "translated" in entry:
                all_entries.append(entry)

        # Module-filter (checkbox partitions). Corpus is texts.json only —
        # no ROM re-extract enrich.
        if self._feature("module_filter"):
            from ..geo import filter_entries_by_geo
            from ..modules import (
                filter_entries_by_modules,
                resolve_modules,
            )

            before = len(all_entries)
            preset = (
                getattr(self.config, "preset", None)
                or getattr(self.config, "funnel", None)
            )
            mods = resolve_modules(modules=self.config.modules, preset=preset, game_id=self.config.game)
            all_entries = filter_entries_by_modules(all_entries, mods, game_id=self.config.game)

            # Lexicon MUST run before empty-filter — otherwise empty cache rows
            # (队伍底栏 etc.) are dropped and never get 请选择 / F9 <op>.
            if self._custom_translations:
                n_exact = 0
                n_sub = 0
                for entry in all_entries:
                    orig_raw = entry.get("original", "")
                    if not orig_raw:
                        continue
                    orig = orig_raw.strip('"')
                    trans = entry.get("translated", "") or ""
                    if orig in self._custom_translations:
                        entry["translated"] = self._custom_translations[orig]
                        n_exact += 1
                        continue
                    if not trans:
                        continue
                    changed = False
                    for jp, zh in self._custom_translations.items():
                        if not zh or len(jp) < 2:
                            continue
                        if jp in orig and jp in trans:
                            trans = trans.replace(jp, zh)
                            changed = True
                    if changed:
                        entry["translated"] = trans
                        n_sub += 1
                if n_exact or n_sub:
                    msg = (
                        f"[自定义翻译] 精确匹配: {n_exact}, 子串替换: {n_sub}, "
                        f"总计: {n_exact + n_sub}/{len(all_entries)} 条"
                    )
                    self._log("info", msg)
                    print(msg)
                else:
                    msg = f"[自定义翻译] 无匹配 (共 {len(all_entries)} 条)"
                    self._log("info", msg)
                    print(msg)

            before_filter = len(all_entries)

            def _injectable_translation(e: dict) -> bool:
                tr = e.get("translated")
                orig = e.get("original") or ""
                if tr is None or tr == orig:
                    return False
                # Intentional blank/spacer (memo particle な → " ") must not
                # die on .strip(); otherwise in_place FF never lands.
                if tr in ("", " ", "\u3000"):
                    return True
                return bool(str(tr).strip())

            all_entries = [e for e in all_entries if _injectable_translation(e)]
            after_mod = len(all_entries)
            filtered_out = before_filter - after_mod
            if filtered_out:
                msg = f"[自定义翻译] 注入过滤: {before_filter} -> {after_mod} (去掉 {filtered_out} 条空/未翻译/跳过)"
                self._log("info", msg)
                print(msg)
            else:
                msg = f"[自定义翻译] 注入过滤: {after_mod} 条全部通过"
                self._log("info", msg)
                print(msg)
            all_entries, geo_meta = filter_entries_by_geo(all_entries)
            geo_note = ""
            if geo_meta.get("omit_band") or geo_meta.get("include") or geo_meta.get(
                "exclude"
            ):
                geo_note = (
                    f" geo={geo_meta.get('after')}/{after_mod}"
                    f" omit={geo_meta.get('omit_band') or '-'}"
                    f" ex={geo_meta.get('exclude') or '-'}"
                )
                if geo_meta.get("omit_range"):
                    orng = geo_meta["omit_range"]
                    geo_note += (
                        f" drop[{orng.get('addr_lo')}-{orng.get('addr_hi')}]"
                        f"x{orng.get('count')}"
                    )
            self._log(
                "info",
                f"AXVJ build inject set: {len(all_entries)}/{before} entries "
                f"[modules={mods}{geo_note}]",
            )
            self._axvj_inject_modules = mods
            self._axvj_geo_meta = geo_meta
        elif self._custom_translations:
            # Non-module_filter games: lexicon still applies before inject
            n_exact = 0
            n_sub = 0
            for entry in all_entries:
                orig_raw = entry.get("original", "")
                if not orig_raw:
                    continue
                orig = orig_raw.strip('"')
                trans = entry.get("translated", "") or ""
                if orig in self._custom_translations:
                    entry["translated"] = self._custom_translations[orig]
                    n_exact += 1
                    continue
                if not trans:
                    continue
                changed = False
                for jp, zh in self._custom_translations.items():
                    if not zh or len(jp) < 2:
                        continue
                    if jp in orig and jp in trans:
                        trans = trans.replace(jp, zh)
                        changed = True
                if changed:
                    entry["translated"] = trans
                    n_sub += 1
            if n_exact or n_sub:
                msg = (
                    f"[自定义翻译] 精确匹配: {n_exact}, 子串替换: {n_sub}, "
                    f"总计: {n_exact + n_sub}/{len(all_entries)} 条"
                )
                self._log("info", msg)
                print(msg)

        # Load manual entries (FireRed-specific)
        if self.config.game == "firered":
            manual_path = Path(__file__).parent.parent / "manual_entries.json"
            if manual_path.exists():
                manual = json.loads(manual_path.read_text(encoding="utf-8"))
                all_entries.extend(manual)
                self._log("info", Messages.ADDED_MANUAL_ENTRIES.format(count=len(manual)))

        # Inject texts
        self._log("info", Messages.INJECTING_TEXTS.format(count=len(all_entries)))
        if self._feature("lz_scan"):
            self._log("info", "Scanning LZ bands once (a few seconds), then injecting…")

        def _inject_progress(cur: int, total: int) -> None:
            self._log("info", f"Inject progress {cur}/{total}")
            self.callbacks.on_progress(
                "build", cur, total, f"Inject {cur}/{total}"
            )

        if self._feature("name_tables"):
            writer.axvj_name_tables = True

        # --- 翻译通路：读 translate.build.json，把 plan（type/target_hex）附加到条目 ---
        # rom_writer 据此按 type 注入；无 plan 的条目回退原逻辑。
        try:
            build_plan_path = (game_work or Path(self.config.work_dir) / self.config.game) / "translate.build.json"
            if build_plan_path.exists():
                from ..translate_plan import build_plan_map_by_id, dedupe_entries_by_id

                _bp = json.loads(build_plan_path.read_text(encoding="utf-8"))
                _plan_map = build_plan_map_by_id(_bp.get("entries") or [])
                all_entries = dedupe_entries_by_id(all_entries)
                for _entry in all_entries:
                    _p = _plan_map.get(_entry.get("id") or "")
                    if _p:
                        _entry["_plan"] = _p
                self._log(
                    "info",
                    f"[翻译通路] 载入 translate.build.json: {len(_plan_map)} 条决策"
                    f"（条目去重后 {len(all_entries)}）",
                )
        except Exception as e:  # pragma: no cover
            self._log("warning", f"[翻译通路] 载入 translate.build.json 失败: {e}")

        rom, stats = writer.inject_texts(
            rom, all_entries, on_progress=_inject_progress
        )
        self._log("info", Messages.INJECTION_STATS.format(
            in_place=stats['in_place'],
            relocated=stats['relocated'],
            skipped=0,
            partial_ptr=stats.get('skipped_partial_ptrs', 0),
            unsafe_ptr=0
        ))
        if self._feature("name_tables"):
            table_stats = stats.get("name_tables") or {}
            if table_stats:
                parts = []
                for key, tbl in table_stats.items():
                    parts.append(f"{key}: ptr={tbl.get('ptr_patched', 0)} mul={tbl.get('mul_patched', 0)}")
                if parts:
                    self._log("info", "AXVJ name tables: " + " | ".join(parts))

        # Save (if emulator locks the file, write sibling *_new.gba)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            writer.save_rom(rom, output_path)
        except OSError as e:
            alt = output_path.with_name(output_path.stem + "_new" + output_path.suffix)
            writer.save_rom(rom, alt)
            self._log(
                "warning",
                f"Could not write {output_path.name} ({e}); wrote {alt.name} instead — "
                f"close the emulator and rename if needed",
            )
            output_path = alt
        self._log("info", Messages.SAVED_ROM.format(path=output_path))

        # Auto-switch review dump (view-only; not part of any pipeline stage).
        auto_extra = getattr(self, "_auto_phrase_extra", None)
        extra_path = (game_work or Path(self.config.work_dir) / self.config.game) / "lexicon.extra.json"
        if auto_extra:
            try:
                extra_data = {
                    e.get("original") or "": e.get("translated") or ""
                    for e in auto_extra
                }
                extra_path.parent.mkdir(parents=True, exist_ok=True)
                extra_path.write_text(
                    json.dumps(extra_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self._log("info", f"[短语] 自动进 F9 80 记录 → {extra_path} ({len(extra_data)} 条)")
            except Exception as e:
                self._log("warning", f"lexicon.extra.json 写失败 (non-fatal): {e}")
        else:
            # Drop stale auto-upgrade dump from prior builds.
            try:
                if extra_path.is_file():
                    extra_path.unlink()
            except OSError:
                pass

        self.callbacks.on_stage_change("build", "completed")
        return output_path
