"""Core translation engine - refactored from Pipeline with callback support."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..charmap import Charmap
from ..control_codes import protect, restore
from ..config_loader import (
    load_game_config,
    get_game_patch_dir,
    get_charmap_path,
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

# Table module ids (routed through _translate_table)
TABLE_CATEGORIES = {
    "物种名",
    "招式名",
    "特性名",
    "性格名",
    "属性名",
    "道具名",
    "训练家类名",
    "地点名",
}

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
    """Convert MeowthBridge entries format to tables + free_texts format.

    If both ``entries`` and ``tables``/``free_texts`` are present (AXVJ flatten
    often writes all three), prefer rebuilding from ``entries`` so Build sees
    the latest translations.
    """
    entries = data.get("entries")
    if entries:
        tables_by_key: dict[str, list] = {}
        free_texts: list = []
        for e in entries:
            mid = e.get("module") or e.get("_axvj_module") or e.get("category") or ""
            if mid in TABLE_CATEGORIES:
                tables_by_key.setdefault(mid, []).append(e)
            else:
                free_texts.append(e)
        out = {
            "tables": [
                {"module": k, "category": k, "entries": es}
                for k, es in tables_by_key.items()
            ],
            "free_texts": free_texts,
        }
        for k in ("game", "game_id", "source_lang", "modules", "count"):
            if k in data:
                out[k] = data[k]
        return out
    if "tables" in data:
        return data
    return {
        "tables": [],
        "free_texts": [],
    }


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
        """Resolve ``font/charmap.txt`` (font stage; used later by patch encode)."""
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
        "llm_table_categories": [
            "物种名",
            "招式名",
            "特性名",
            "道具名",
            "属性名",
            "性格名",
        ],
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

        if not translated or translated == original:
            return False
        if looks_like_failed_zh_translation(original, translated):
            return False
        if re.search(r"[\u4e00-\u9fff]", translated):
            return True
        # Short menu labels / color-prefixed options
        if translated in {"是", "否"} or "\\CC" in translated:
            return True
        return False

    def _merge_prior_translations(self, data: dict) -> int:
        """Fill blanks from work_dir/texts_translated.json (GUI re-runs)."""
        prior_path = Path(self.config.work_dir) / self.config.game / "texts_translated.json"
        if not prior_path.exists():
            return 0
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        by_addr: dict[str, str] = {}
        by_orig: dict[str, str] = {}
        for e in prior.get("entries") or []:
            orig = e.get("original") or ""
            zh = e.get("translated") or ""
            if not self._usable_zh(orig, zh):
                continue
            addr = (e.get("address") or "").upper()
            if addr:
                by_addr[addr] = zh
            by_orig[orig] = zh
        # Also scan free_texts / tables shapes
        for e in prior.get("free_texts") or []:
            orig = e.get("original") or ""
            zh = e.get("translated") or ""
            if self._usable_zh(orig, zh):
                by_orig[orig] = zh
                addr = (e.get("address") or "").upper()
                if addr:
                    by_addr[addr] = zh
        for table in prior.get("tables") or []:
            for e in table.get("entries") or []:
                orig = e.get("original") or ""
                zh = e.get("translated") or ""
                if self._usable_zh(orig, zh):
                    by_orig[orig] = zh

        n = 0
        for e in data.get("entries") or []:
            if self._usable_zh(e.get("original") or "", e.get("translated") or ""):
                continue
            orig = e.get("original") or ""
            addr = (e.get("address") or "").upper()
            zh = by_addr.get(addr) or by_orig.get(orig)
            if zh and self._usable_zh(orig, zh):
                e["translated"] = zh
                n += 1
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
        """Translate extracted texts JSON with parallel workers."""
        data = json.loads(texts_path.read_text(encoding="utf-8"))

        # 文本校验阈值：score < threshold 的条目标记 _reject，seed/LLM 跳过，
        # 并生成 {原文件名}_reject_{阈值}.json（texts.json 侧，无 translated）。
        threshold = getattr(self.config, "check_threshold", 0) or 0
        if threshold > 0 and data.get("entries"):
            rom_path = self.config.rom_path
            if rom_path and Path(rom_path).exists():
                reject_path = Path(texts_path).with_name(
                    f"{Path(texts_path).stem}_reject_{threshold}.json"
                )
                self._apply_check_reject(
                    data["entries"], Path(rom_path), threshold, reject_path, data
                )

        # Reload custom translations (game ID may have changed since __init__)
        from ..config_loader import load_custom_translations
        self._custom_translations = load_custom_translations(self.config.game)

        # Offline seeds first (config: seed_translate)
        if self.config.seed_first and (
            self._feature("seed_translate") or data.get("game_id") == self.config.game
        ):
            from ..seed_translate import (
                looks_like_failed_zh_translation,
                seed_translate_entry,
            )

            # Keep prior GUI/CLI Chinese across re-extract (only fill blanks)
            merged = self._merge_prior_translations(data)
            if merged:
                self._log("info", f"Merged {merged} prior Chinese strings from work cache")

            seeded = 0
            held_failed = 0
            ct = self._custom_translations or {}
            for e in data.get("entries") or []:
                if e.get("_reject"):
                    continue
                orig = e.get("original", "")
                if self._usable_zh(orig, e.get("translated") or ""):
                    continue
                zh = seed_translate_entry(orig) or ct.get(orig) or ct.get(orig.strip('"'))
                if zh:
                    e["translated"] = zh
                    seeded += 1
                    continue
                # looks_like_failed: skip LLM later; never wipe cache to "" (seed-only
                # would leave permanent JP holes).
                if (
                    self.config.target_lang.startswith("zh")
                    and looks_like_failed_zh_translation(orig, e.get("translated") or "")
                ):
                    held_failed += 1
            self._log(
                "info",
                f"Applied AXVJ offline seeds ({seeded}); "
                f"held {held_failed} failed ja→zh stubs (not cleared)",
            )

        data = convert_format(data)

        # Seed free_texts/tables after convert (config: seed_translate)
        if self._feature("seed_translate") or data.get("game_id") == self.config.game:
            from ..modules import resolve_modules, stamp_entry_module
            from ..seed_translate import seed_translate_entry

            preset = (
                getattr(self.config, "preset", None)
                or getattr(self.config, "funnel", None)
            )
            active = set(
                resolve_modules(modules=self.config.modules, preset=preset, game_id=self.config.game)
            )
            self._axvj_active_modules = active
            seeded2 = 0
            skipped_mod = 0

            def _seed_or_hold(e: dict) -> None:
                nonlocal seeded2, skipped_mod
                if e.get("_reject"):
                    return
                mid = stamp_entry_module(e, game_id=self.config.game)
                # Unresolved geo: keep existing translation; do not wipe / LLM
                if mid is None:
                    skipped_mod += 1
                    return
                if mid not in active:
                    # Unchecked: do not wipe usable Chinese
                    skipped_mod += 1
                    return
                orig = e.get("original") or ""
                tr = e.get("translated") or ""
                # Keep real Chinese; only clear JP-hold stubs for LLM retry
                if tr and tr != orig and self._usable_zh(orig, tr):
                    return
                if tr == orig and not self.config.seed_only:
                    e["translated"] = ""
                ct = self._custom_translations or {}
                zh = seed_translate_entry(orig) or ct.get(orig) or ct.get(orig.strip('"'))
                if zh:
                    e["translated"] = zh
                    seeded2 += 1

            for table in data.get("tables") or []:
                for e in table.get("entries") or []:
                    _seed_or_hold(e)
            for e in data.get("free_texts") or []:
                _seed_or_hold(e)
            if seeded2 or skipped_mod:
                self._log(
                    "info",
                    f"AXVJ seeds={seeded2}; hold JP (unchecked modules)={skipped_mod} "
                    f"[modules={sorted(active)}]",
                )
        else:
            self._axvj_active_modules = None

        # Re-merge from texts_translated.json after module seeding (address-based)
        from ..modules import _get_modules
        dirty_mods = {
            mid for mid, m in _get_modules(self.config.game).items()
            if m.get("dirty")
        }
        prior_path = Path(self.config.work_dir) / self.config.game / "texts_translated.json"
        if prior_path.exists():
            try:
                prior = json.loads(prior_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                prior = None
            if prior:
                by_addr: dict[str, str] = {}
                for e in prior.get("free_texts") or []:
                    addr = (e.get("address") or "").upper()
                    zh = e.get("translated") or ""
                    if addr and zh and self._usable_zh(e.get("original", ""), zh):
                        by_addr[addr] = zh
                for t in prior.get("tables") or []:
                    for e in t.get("entries") or []:
                        addr = (e.get("address") or "").upper()
                        zh = e.get("translated") or ""
                        if addr and zh and self._usable_zh(e.get("original", ""), zh):
                            by_addr[addr] = zh
                n = 0
                for entry in data.get("free_texts") or []:
                    if entry.get("translated"):
                        continue
                    if entry.get("_axvj_module") in dirty_mods:
                        continue
                    zh = by_addr.get((entry.get("address") or "").upper())
                    if zh:
                        entry["translated"] = zh
                        n += 1
                for t in data.get("tables") or []:
                    for entry in t.get("entries") or []:
                        if entry.get("translated"):
                            continue
                        if entry.get("_axvj_module") in dirty_mods:
                            continue
                        zh = by_addr.get((entry.get("address") or "").upper())
                        if zh:
                            entry["translated"] = zh
                            n += 1
                if n:
                    self._log("info", f"Merged {n} entries from prior texts_translated.json")

        # Translate table entries (glossary)
        for table in data["tables"]:
            self._translate_table(table)

        free_texts = data["free_texts"]
        # IME kana rows: keep Japanese (input method grid)
        import re

        for e in free_texts:
            if e.get("translated"):
                continue
            from ..modules import entry_matches

            if not entry_matches(e, "姓名输入", game_id=self.config.game):
                continue
            orig = e.get("original", "")
            compact = orig.replace(" ", "")
            if re.fullmatch(r"[ぁ-んァ-ン]{5}", compact):
                e["translated"] = orig
            elif compact in ("やゆよわをん",):
                e["translated"] = orig

        # 垃圾/假文本过滤已统一由文本校验阈值（check_threshold + allows/rejects）
        # 在 translate 开头评分时处理（score < threshold → _reject，不填充翻译）。
        import os

        has_key = bool(self.config.api_key) or bool(
            self.config.api_key_env and os.environ.get(self.config.api_key_env)
        )
        seed_only = self.config.seed_only or (
            self._feature("seed_on_no_key") and not has_key
        )
        # Pending = empty translation, or stale JP-hold (translated == original)
        # once the entry's module is active.
        active = getattr(self, "_axvj_active_modules", None)

        def _needs_llm(e: dict) -> bool:
            if e.get("_reject"):
                return False
            orig = e.get("original") or ""
            tr = e.get("translated") or ""
            if tr.strip() and tr.strip() != orig.strip():
                return False
            if active is not None:
                from ..modules import stamp_entry_module

                mid = stamp_entry_module(e, game_id=self.config.game)
                # None / unchecked → do not call API
                if mid is None or mid not in active:
                    return False
            # empty or JP-hold on an active module
            return True

        pending = [e for e in free_texts if _needs_llm(e)]
        # Stable sort by address so the same ROM region always forms the same batches
        pending.sort(key=lambda e: (e.get("address") or "", e.get("original") or ""))
        if seed_only:
            # Lexicon/custom only — never mass-clear; refill empties once more
            from ..seed_translate import seed_translate_entry as _seed_fill

            ct = self._custom_translations or {}
            refilled = 0
            for e in free_texts:
                if e.get("_reject"):
                    continue
                orig = e.get("original") or ""
                if self._usable_zh(orig, e.get("translated") or ""):
                    continue
                zh = _seed_fill(orig) or ct.get(orig) or ct.get(orig.strip('"'))
                if zh:
                    e["translated"] = zh
                    refilled += 1
            for table in data.get("tables") or []:
                for e in table.get("entries") or []:
                    if e.get("_reject"):
                        continue
                    orig = e.get("original") or ""
                    if self._usable_zh(orig, e.get("translated") or ""):
                        continue
                    zh = _seed_fill(orig) or ct.get(orig) or ct.get(orig.strip('"'))
                    if zh:
                        e["translated"] = zh
                        refilled += 1
            still = sum(
                1
                for e in free_texts
                if not self._usable_zh(e.get("original") or "", e.get("translated") or "")
            )
            self._log(
                "info",
                f"seed_only: lexicon refill +{refilled}; "
                f"{still}/{len(free_texts)} free texts still empty (no mass clear)",
            )
        else:
            batches = [
                pending[i : i + self.config.batch_size]
                for i in range(0, len(pending), self.config.batch_size)
            ]
            total = len(batches)
            if total:
                self._ensure_translator()
                self._log("info", Messages.BATCH_PROGRESS.format(
                    total=total, workers=self.config.max_workers
                ))
                done_count = 0

                def process_batch(idx_batch):
                    idx, batch = idx_batch
                    self._translate_free_batch(batch)
                    return idx, batch

                with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                    futures = {
                        executor.submit(process_batch, (i, b)): i
                        for i, b in enumerate(batches)
                    }
                    for future in as_completed(futures):
                        done_count += 1
                        idx, batch = future.result()
                        self._log("info", Messages.BATCH_COMPLETE.format(
                            current=done_count, total=total, batch_id=idx + 1
                        ))
                        sample = next((e for e in batch if e.get("translated")), None)
                        if sample:
                            try:
                                print(f"  e.g. {sample['original']!r} → {sample['translated']!r}")
                            except UnicodeEncodeError:
                                print(f"  batch {idx + 1} done")
                        self.callbacks.on_progress("translate", done_count, total,
                            f"Batch {idx + 1} completed")

        # Flatten back to entries for inject compatibility (config: flat_entry_format)
        if self._feature("flat_entry_format") or data.get("game_id") == self.config.game:
            flat = []
            for table in data["tables"]:
                flat.extend(table.get("entries") or [])
            flat.extend(data["free_texts"])
            data = {
                "game": self.config.game,
                "game_id": self.config.game,
                "source_lang": self.config.source_lang,
                "modules": self.config.modules,
                "count": len(flat),
                "entries": flat,
                "tables": data["tables"],
                "free_texts": data["free_texts"],
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # --- 翻译通路规划：决策 type + 编码 target_hex → translate.build.json ---
        # translate 阶段不注入 ROM，只产出 build 中间产物；texts_translated.json
        # 降级为翻译缓存文件。
        try:
            self._write_translate_build(data)
        except Exception as e:  # pragma: no cover
            self._log("warning", f"[翻译通路] translate.build.json 生成失败: {e}")

        return output_path

    def _write_translate_build(self, data: dict) -> None:
        """决策每条目的注入 type 并编码 target_hex，写 translate.build.json。

        短语码（词典 + 自动 upgrade 预分配）在此阶段确定并写入 phrases，
        build 阶段据此生成 PhraseTable 并按 type 注入。
        """
        from ..translate_plan import plan_entries

        flat = data.get("entries") or []
        if not flat:
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
        plans = plan_entries(flat, self.charmap, phrase_codes, game_id=self.config.game)

        phrases_by_code = [None] * len(phrase_codes)
        for s, code in phrase_codes.items():
            phrases_by_code[code] = s

        payload = {
            "game_id": self.config.game,
            "count": len(flat),
            "phrases": phrases_by_code,
            "entries": [
                {
                    "id": e.get("id", ""),
                    "type": p["type"],
                    "address": e.get("address", ""),
                    "byte_length": e.get("byte_length", 0),
                    "module": e.get("module") or e.get("_axvj_module") or "",
                    "original": e.get("original", ""),
                    "translated": e.get("translated", ""),
                    "original_hex": e.get("original_hex", ""),
                    "target_hex": p.get("target_hex", ""),
                    "pointer_sources": p.get("pointer_sources") or [],
                    "phrase_code": p.get("phrase_code"),
                    "reason": p.get("reason"),
                }
                for e, p in zip(flat, plans)
            ],
        }
        build_dir = Path(self.config.work_dir) / self.config.game
        build_dir.mkdir(parents=True, exist_ok=True)
        build_path = build_dir / "translate.build.json"
        build_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        from collections import Counter as _C

        _types = _C(p["type"] for p in plans)
        self._log(
            "info",
            "[翻译通路] translate.build.json → "
            + ", ".join(f"{t}={n}" for t, n in _types.most_common()),
        )

    def _translate_table(self, table: dict):
        """Translate a table's entries using glossary lookup."""
        category = table.get("module") or table.get("category") or ""
        needs_llm: list[dict] = []  # entries deferred to batch LLM call
        active = getattr(self, "_axvj_active_modules", None)
        from ..modules import entry_matches, stamp_entry_module

        ct_hit = 0
        for entry in table["entries"]:
            original = entry["original"].strip('"')
            if active is not None:
                mid = stamp_entry_module(entry, game_id=self.config.game)
                if mid is None:
                    continue
                if mid not in active:
                    # Unchecked: keep usable Chinese; do not wipe
                    continue
                # Clear stale JP-hold so glossary/LLM can run (not under seed_only)
                if (entry.get("translated") or "") == original and not self.config.seed_only:
                    entry["translated"] = ""
                elif self._usable_zh(original, entry.get("translated") or ""):
                    continue
            # Check term overrides (all games, Chinese only)
            if self.config.target_lang == "zh-Hans" and original in _TERM_OVERRIDES:
                entry["translated"] = _TERM_OVERRIDES[original]
                continue
            # Check manual overrides
            if (
                entry_matches(
                    {"module": category, "category": category},
                    "训练家类名",
                    game_id=self.config.game,
                )
                and self.config.target_lang == "zh-Hans"
                and original in _TRAINER_CLASS_OVERRIDES
            ):
                entry["translated"] = _TRAINER_CLASS_OVERRIDES[original]
                continue
            # Check custom_translations from folder (skip API if found)
            ct_zh = self._custom_translations.get(original)
            if ct_zh:
                entry["translated"] = ct_zh
                ct_hit += 1
                continue
            # Try glossary lookup
            zh = self.glossary.lookup(original)
            if zh:
                ok, bad = self.charmap.can_encode(zh)
                if ok:
                    entry["translated"] = zh
                    continue
            # Descriptions, map names without glossary match, and battle text:
            # defer to batch LLM call instead of one-by-one to avoid 500+ API calls
            if (
                "说明" in category
                or "description" in category
                or (
                    entry_matches(
                        {"module": category, "category": category},
                        "地点名",
                        game_id=self.config.game,
                    )
                    and not zh
                )
                or entry_matches(
                    {"module": category, "category": category},
                    "战斗提示",
                    game_id=self.config.game,
                )
            ):
                needs_llm.append(entry)
            elif category in self._feature("llm_table_categories", []):
                needs_llm.append(entry)
            elif zh:
                entry["translated"] = zh
            else:
                entry["translated"] = original

        # Batch translate all deferred LLM entries
        if needs_llm:
            self._translate_table_llm_batch(needs_llm)

            if ct_hit:
                msg = f"[自定义翻译] 命中: {ct_hit}/{len(table['entries'])} 条 (跳过 API)"
                self._log("info", msg)
                print(msg)

        # Inject map / species names into glossary for free-text consistency
        if entry_matches(
            {"module": category, "category": category},
            "地点名",
            "物种名",
            game_id=self.config.game,
        ):
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
            # No LLM available — keep originals
            for entry in entries:
                entry["translated"] = entry.get("original", "")
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
                print(f"[Table batch LLM failed: {e}, keeping originals]")
                for entry, _, _ in chunk:
                    entry["translated"] = entry["original"].strip('"')
                continue

            for (entry, _, codes), result in zip(chunk, results):
                clean = _strip_llm_newlines(result)
                entry["translated"] = restore(clean, codes)

    def _translate_free_batch(self, batch: list[dict]):
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

        originals = [e["original"] for e in remaining]

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
            results = self.translator.translate_batch(protected_list, glossary_ctx)
        except Exception as e:
            print(f"[Batch failed after retries: {e}, keeping originals]")
            for entry in remaining:
                entry["translated"] = entry["original"]
            return

        # Restore and wrap
        for i, entry in enumerate(remaining):
            clean = _strip_llm_newlines(results[i])
            translated = restore(clean, codes_list[i])
            translated = wrap_text(translated, target_lang=self.config.target_lang)
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
            retry = [e for e in remaining if not e.get("translated")]
            if retry and len(retry) < len(remaining):
                self._translate_free_batch_once(retry)

    def _translate_free_batch_once(self, remaining: list[dict]):
        """Single-shot LLM batch without nested retry (used after failed ja→zh)."""
        if not remaining:
            return
        originals = [e["original"] for e in remaining]
        protected_list = []
        codes_list = []
        for text in originals:
            protected, codes = protect(text)
            protected_list.append(protected)
            codes_list.append(codes)
        all_text = " ".join(originals)
        glossary_ctx = self._format_glossary(all_text)
        try:
            results = self.translator.translate_batch(protected_list, glossary_ctx)
        except Exception as e:
            print(f"[Retry batch failed: {e}]")
            return
        from ..seed_translate import looks_like_failed_zh_translation

        for i, entry in enumerate(remaining):
            clean = _strip_llm_newlines(results[i])
            translated = restore(clean, codes_list[i])
            translated = wrap_text(translated, target_lang=self.config.target_lang)
            if looks_like_failed_zh_translation(entry.get("original", ""), translated):
                entry["translated"] = ""
            else:
                entry["translated"] = translated

    def _format_glossary(self, text: str) -> str:
        terms = self.glossary.get_context_terms(text)
        if not terms:
            return ""
        return "\n".join(f"  {src} = {tgt}" for src, tgt in terms.items())

    def _enrich_axvj_build_entries(
        self,
        rom: bytes | bytearray,
        entries: list[dict],
    ) -> list[dict]:
        """Merge option/UI extract + offline seeds into the Build inject list.

        GUI users often click Build alone with an older ``texts_translated.json``
        that predates options-menu extract. Seeds (menu pad, house, options)
        must still land in the ROM.
        """
        from ..extract_pipeline import extract_modules
        from ..seed_translate import seed_translate_entry

        by_addr: dict[str, dict] = {}
        for e in entries:
            addr = e.get("address") or ""
            if not addr:
                continue
            by_addr[addr] = dict(e)

        rom_bytes = bytes(rom)
        game_id = self.config.game
        _enrich_list = extract_modules(
            rom_bytes, game_id, hidden_only=True, include_scripts=False
        )
        for e in _enrich_list:
            addr = e.get("address") or ""
            if not addr:
                continue
            prev = by_addr.get(addr)
            if prev is None:
                by_addr[addr] = dict(e)
                prev = by_addr[addr]
            else:
                for k in (
                    "pointer_sources",
                    "pointer_addresses",
                    "original_hex",
                    "byte_length",
                    "module",
                    "category",
                    "original",
                ):
                    if not e.get(k):
                        continue
                    if k.startswith("pointer"):
                        old = list(prev.get(k) or [])
                        new = list(e.get(k) or [])
                        prev[k] = list(dict.fromkeys(old + new))
                    else:
                        prev[k] = e[k]

        out: list[dict] = []
        from ..modules import stamp_entry_module

        ct = self._custom_translations or {}
        for e in by_addr.values():
            stamp_entry_module(e, game_id=game_id)
            orig = e.get("original") or ""
            seeded = seed_translate_entry(orig)
            if not seeded:
                seeded = ct.get(orig) or ct.get(orig.strip('"'))
            if seeded:
                e["translated"] = seeded
            tr = (e.get("translated") or "").strip()
            if not tr or tr == orig:
                continue
            out.append(e)
        return out

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

            from ..config_loader import load_custom_translations
            self._custom_translations = load_custom_translations(self.config.game)

            self._fonts_from_bdf = False
            if self.config.bdf_font_path and is_cjk_language(self.config.target_lang):
                self._build_font_from_bdf(work_dir)
                self._ensure_default_fonts(
                    work_dir, overwrite_bins=not bool(self._fonts_from_bdf)
                )
            elif is_cjk_language(self.config.target_lang):
                self._ensure_default_fonts(work_dir)

            translated_path = self.translate_texts(
                texts_path, work_dir / self.config.game / "texts_translated.json"
            )
            self.callbacks.on_stage_change("translate", "completed")

            # --- tile stage: patch sprites on a ROM copy (input untouched) ---
            base_rom = rom_path
            if self.config.tiles_dir or self._default_tiles_dir(rom_path).is_dir():
                self.callbacks.on_stage_change("tile", "started")
                base_rom = self._run_tiles(rom_path, work_dir)
                self.callbacks.on_stage_change("tile", "completed")

            # --- hook + build stages: emitted inside build_rom ---
            output_rom = output_dir / f"{rom_path.stem}_translated.gba"
            return self.build_rom(base_rom, translated_path, output_rom)
        except Exception as e:
            self.callbacks.on_error(e)
            raise

    def _default_tiles_dir(self, rom_path: Path) -> Path:
        """Default tiles dir: configs/<game_id>/tile, else row_patcher's
        legacy export dir src/util/works/{romId}/tiles."""
        from ..config_loader import game_config_dir

        try:
            cfg_tiles = game_config_dir(self.config.game or rom_path.stem) / "tile"
            if cfg_tiles.is_dir():
                return cfg_tiles
        except Exception:
            pass
        return (
            Path(__file__).resolve().parent.parent.parent / "util" / "works"
            / rom_path.stem / "tiles"
        )

    def _run_tiles(self, rom_path: Path, work_dir: Path) -> Path:
        """Tiles stage: run row_patcher import on the built ROM, in place.

        Reads PNG/raw edits from ``config.tiles_dir`` (fallback to row_patcher's
        default works dir) and patches them into ``rom_path`` (the build_rom
        output), returning the same path. Must run after build_rom — the font
        patch incbins fonts at 0x09000000, which collides with row_patcher's
        default free-space relocation address.
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

        tile_rom = Path(work_dir) / f"{rom_path.stem}_tiles{rom_path.suffix}"
        tile_rom.parent.mkdir(parents=True, exist_ok=True)
        script = (
            Path(__file__).resolve().parent.parent.parent / "util" / "row_patcher.py"
        )
        args = [
            sys.executable,
            str(script),
            "import",
            str(rom_path),
            str(tiles_dir),
            "-o",
            str(tile_rom),
        ]
        self._log("info", f"tiles: {len(meta_files)} meta(s) -> {tile_rom.name}")
        r = subprocess.run(args, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(
                f"row_patcher import failed:\n{r.stdout}\n{r.stderr}"
            )
        self._log("info", f"tiles patched: {tile_rom.name}")
        # row_patcher writes to *_tiles.gba; return it as the tile-patched base
        # for build_rom (input ROM stays untouched).
        return tile_rom

    def extract_texts(
        self,
        rom_path: Path,
        output_path: Path | None = None,
        *,
        modules: list[str] | None = None,
    ) -> Path:
        """Extract texts from ``rom_path`` into ``output_path``.

        Defaults to ``work/<game_id>/texts.json``. Discovery is config-driven
        (``configs/<game_id>/translate/modules.json``), so ``modules`` is only
        a scope hint for backends that accept it.
        """
        from ..game_backends import detect_game, get_backend

        game_id = detect_game(rom_path)
        if game_id == "unknown":
            raise ValueError(f"Unknown ROM: {rom_path}")
        self.config.game = game_id
        set_active_game_id(game_id)
        if output_path is None:
            output_path = Path(self.config.work_dir) / game_id / "texts.json"
        backend = get_backend(game_id)
        return backend.extract(rom_path, output_path, modules=modules)

    def _apply_check_reject(
        self,
        entries: list[dict],
        rom_path: Path,
        threshold: int,
        reject_path: Path,
        data: dict,
    ) -> int:
        """评分条目并把 score < threshold 的条目标记 ``_reject``。

        同时写 ``{原文件名}_reject_{阈值}.json``（只含被拒条目 + check_meta），
        不改动输入文件。返回被拒条目数。
        """
        from ..text_checker import score_entries
        from ..policy import allows_ids, rejects_ids

        allows = allows_ids(self.config.game)
        rejects = rejects_ids(self.config.game)
        rom = rom_path.read_bytes()
        scored = score_entries(entries, rom)
        rejected: list[dict] = []
        for e, hits, s in scored:
            eid = e.get("id") or ""
            e["check_score"] = s
            # 无条件拒绝（rejects），或被拒但不在 allows（放行）
            if eid in rejects or (s < threshold and eid not in allows):
                e["_reject"] = True
                rejected.append(dict(e, check_hits=hits, _reject=True))

        total = (
            round(sum(s for _, _, s in scored) / len(scored), 1) if scored else 100.0
        )
        meta = {
            "score": total,
            "threshold": threshold,
            "rejected_count": len(rejected),
            "total_count": len(scored),
            "rom_game_id": data.get("game_id") or data.get("game"),
            "algorithms": sorted(
                __import__("meowth.text_checker", fromlist=["WEIGHTS"]).WEIGHTS
            ),
            "checked_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        reject_path.parent.mkdir(parents=True, exist_ok=True)
        reject_path.write_text(
            json.dumps(
                {
                    "game": data.get("game"),
                    "game_id": data.get("game_id") or data.get("game"),
                    "source_lang": data.get("source_lang"),
                    "count": len(rejected),
                    "entries": rejected,
                    "check_meta": meta,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._log(
            "info",
            f"[校验] 阈值 {threshold}: 拒绝 {len(rejected)}/{len(scored)} 条 "
            f"→ {reject_path.name}",
        )
        return len(rejected)

    def _extract_texts(self, rom_path: Path, output_dir: Path) -> Path:
        """Extract texts using the game backend."""
        from ..game_backends import detect_game, get_backend

        game_id = detect_game(rom_path)
        if game_id == "unknown":
            raise ValueError(f"Unknown ROM: {rom_path}")
        self.config.game = game_id
        set_active_game_id(game_id)
        output_path = output_dir / game_id / "texts.json"
        backend = get_backend(game_id)
        return backend.extract(rom_path, output_path, modules=self.config.modules)

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

        # PhraseTable: expanded PCS streams (F9 00×N + FE/FB/… + FF).
        # PrintNextChar redirects to the stream and reuses F9 00 / vanilla controls.
        if not self._custom_translations:
            return
        # Must not use F9 80 phrase wrap (installed in _build_rom).
        sideload_encode = getattr(self.charmap, "_sideload_encode", None)
        if sideload_encode is None:
            sideload_encode = self.charmap.encode

        # Unified phrase set: lexicon + auto-switch (contiguous codes = table index).
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

        MAX_PHRASE_STREAM = 512
        offsets: list[int] = []
        table_lines: list[str] = ['.align 4', 'PhraseTable:']
        byte_cursor = 0
        truncated = 0
        for text in phrases:
            offsets.append(byte_cursor)
            stream = bytearray(sideload_encode(text))
            if not stream or stream[-1] != 0xFF:
                stream.append(0xFF)
            if len(stream) > MAX_PHRASE_STREAM:
                stream = stream[: MAX_PHRASE_STREAM - 1]
                stream.append(0xFF)
                truncated += 1
            for i in range(0, len(stream), 16):
                chunk = stream[i : i + 16]
                hex_bytes = ", ".join(f"0x{b:02X}" for b in chunk)
                suffix = f"  ; {len(stream)}B" if i == 0 else ""
                table_lines.append(f"  .byte {hex_bytes}{suffix}")
            byte_cursor += len(stream)
        offsets.append(byte_cursor)  # sentinel = total size

        # Fixed VMA for C (game.h ADDR_PHRASE_*); must match game_addrs.asm
        # Stream table can exceed 64KB → offsets must be u32 (.word), hook uint32_t*.
        asm_lines = ['.org 0x08810000', '.align 4', 'PhraseOffsets:']
        for off in offsets:
            asm_lines.append(f'  .word {off}')
        asm_lines.append('')
        asm_lines.append('.org 0x08820000')
        asm_lines.extend(table_lines)

        phrase_asm = fonts_dir / "phrase_data.asm"
        phrase_asm.write_text('\n'.join(asm_lines), encoding="utf-8")
        msg = (
            f"[短语] PhraseTable {len(phrases)} 条流, {byte_cursor}B data + "
            f"{len(offsets) * 4}B offsets(u32) -> {phrase_asm.name}"
        )
        if truncated:
            msg += f" ({truncated} 条截断至 {MAX_PHRASE_STREAM}B)"
        self._log("info", msg)

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
        data = convert_format(data)

        # 文本校验阈值：score < threshold 的条目标记 _reject，注入时跳过，
        # 并生成 {原文件名}_reject_{阈值}.json（含 translated 内容）。
        threshold = getattr(self.config, "check_threshold", 0) or 0
        if threshold > 0:
            check_entries = [e for t in data.get("tables") or [] for e in t["entries"]] + list(data.get("free_texts") or [])
            if check_entries:
                reject_path = Path(translations_path).with_name(
                    f"{Path(translations_path).stem}_reject_{threshold}.json"
                )
                self._apply_check_reject(
                    check_entries, Path(original_rom), threshold, reject_path, data
                )

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

        # Load custom translations from folder (reload in case game ID changed since __init__)
        from ..config_loader import load_custom_translations, load_codec
        self._custom_translations = load_custom_translations(self.config.game)
        if self._custom_translations:
            self._log("info", f"[配置] 自定义翻译缓存已加载: {len(self._custom_translations)} 条")

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

        from ..config_loader import DEFAULT_LINE_WIDTH, module_line_widths

        line_width_default = DEFAULT_LINE_WIDTH
        line_width_modules = module_line_widths(self.config.game)
        writer = RomWriter(self.charmap, game=self.config.game,
                          target_lang=self.config.target_lang,
                          fp_cfg=fp_cfg,
                          line_width_default=line_width_default,
                          line_width_modules=line_width_modules)

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

        # Enrich seeds, then module-filter (checkbox partitions).
        if self._feature("module_filter"):
            from ..geo import filter_entries_by_geo
            from ..modules import (
                filter_entries_by_modules,
                resolve_modules,
            )

            all_entries = self._enrich_axvj_build_entries(rom, all_entries)
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
                    ct_zh = self._custom_translations.get(orig)
                    if ct_zh:
                        entry["translated"] = ct_zh
                        n_exact += 1
                        continue
                    if not trans:
                        continue
                    changed = False
                    for jp, zh in self._custom_translations.items():
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
            all_entries = [
                e
                for e in all_entries
                if (e.get("translated") or "").strip()
                and (e.get("translated") or "").strip() != (e.get("original") or "")
            ]
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
                ct_zh = self._custom_translations.get(orig)
                if ct_zh:
                    entry["translated"] = ct_zh
                    n_exact += 1
                    continue
                if not trans:
                    continue
                changed = False
                for jp, zh in self._custom_translations.items():
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
                _bp = json.loads(build_plan_path.read_text(encoding="utf-8"))
                _plan_map = {e.get("id"): e for e in _bp.get("entries") or [] if e.get("type")}
                for _entry in all_entries:
                    _p = _plan_map.get(_entry.get("id"))
                    if _p:
                        _entry["_plan"] = _p
                self._log(
                    "info",
                    f"[翻译通路] 载入 translate.build.json: {len(_plan_map)} 条决策",
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

        # Critical dialogue must be non-empty ZH and in the inject set (seed-only gate)
        _critical_needles = (
            "その ほかに",
            "あ！ やせいの",
            "ポケモンを えらんで ください",
        )
        for needle in _critical_needles:
            hits = [
                e
                for e in all_entries
                if needle in (e.get("original") or "")
                and self._usable_zh(e.get("original") or "", e.get("translated") or "")
            ]
            if hits:
                self._log(
                    "info",
                    f"critical OK: {needle!r} → {len(hits)} injected "
                    f"(eg {hits[0].get('translated', '')[:24]!r})",
                )
            else:
                self._log(
                    "warning",
                    f"critical MISSING from inject set: {needle!r} "
                    f"(lexicon/seed empty or filtered)",
                )

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

        try:
            import os

            from ..build_record import record_build

            rec = record_build(
                output_rom=output_path,
                game=self.config.game,
                inject_stats={
                    "in_place": stats.get("in_place"),
                    "relocated": stats.get("relocated"),
                    "skipped": 0,
                    "entry_count": len(all_entries),
                    "name_tables": stats.get("name_tables") or {},
                    "modules": list(getattr(self, "_axvj_inject_modules", []) or []),
                    "geo": getattr(self, "_axvj_geo_meta", None) or {},
                },
                notes=os.environ.get("MEOWTH_AXVJ_BUILD_NOTES", ""),
            )
            self._log(
                "info",
                f"Build record {rec['build_id']} "
                f"(patch={rec['patch_tree_sha256'][:12]}…) "
                f"→ {output_path.name}.build.json",
            )
        except Exception as e:
            self._log("warning", f"Build record failed (non-fatal): {e}")
        self.callbacks.on_stage_change("build", "completed")
        return output_path
