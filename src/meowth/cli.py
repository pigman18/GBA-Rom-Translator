"""Meowth CLI - GBA Pokemon translation tool."""

import json
from pathlib import Path

import click

from .core import TranslationCallbacks, TranslationConfig, TranslationEngine
from .languages import validate_language
from .translator import PROVIDER_PRESETS


def _default_translated_path(texts_json: Path) -> Path:
    """Infer ``configs/<game_id>/translate/texts_translated.json``."""
    from .config_loader import texts_translated_path

    try:
        meta = json.loads(texts_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    gid = meta.get("game_id") or meta.get("game") or "AXVJ"
    try:
        return texts_translated_path(str(gid))
    except Exception:
        return Path("configs") / str(gid) / "translate" / "texts_translated.json"


def _load_env():
    """Load .env file if present."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                import os
                os.environ.setdefault(key.strip(), val.strip())


def _load_config() -> dict:
    """Load meowth.toml config if present."""
    config_path = Path(__file__).parent.parent.parent / "meowth.toml"
    if not config_path.exists():
        return {}
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def _provider_kwargs(provider, api_base, api_key_env, model, api_key=None) -> dict:
    """Build provider kwargs from CLI options, falling back to meowth.toml."""
    cfg = _load_config()
    t = cfg.get("translation", {})
    api_cfg = t.get("api", {})

    return {
        "provider": provider or t.get("provider"),
        "api_base": api_base or api_cfg.get("base_url"),
        "api_key_env": api_key_env or api_cfg.get("key_env"),
        "api_key": api_key or None,
        "model": model or t.get("model"),
    }


def _get_language(cli_value, cli_default, config_key) -> str:
    """Get language from CLI or config, preferring config if CLI is default."""
    cfg = _load_config()
    t = cfg.get("translation", {})
    if cli_value != cli_default:
        return cli_value
    return t.get(config_key, cli_default)


_provider_options = [
    click.option("--provider", default=None, type=click.Choice(sorted(PROVIDER_PRESETS.keys()), case_sensitive=False),
                 help="LLM provider preset (e.g. openai, deepseek, google)"),
    click.option("--api-base", default=None, help="Custom API base URL (OpenAI-compatible)"),
    click.option("--api-key", default=None, help="API key (pasteable; prefer env in shared logs)"),
    click.option("--api-key-env", default=None, help="Environment variable name for API key"),
    click.option("--model", default=None, help="Model name to use"),
]


def add_provider_options(func):
    for option in reversed(_provider_options):
        func = option(func)
    return func


def _modules_option(func):
    return click.option(
        "--modules",
        default=None,
        help="Ignored (AXVJ always extracts/translates all texts)",
    )(func)


class CLICallbacks(TranslationCallbacks):
    def on_log(self, level: str, message: str):
        if level == "error":
            click.secho(message, fg="red", err=True)
        elif level == "warning":
            click.secho(message, fg="yellow")
        else:
            click.echo(message)

    def on_progress(self, stage: str, current: int, total: int, message: str):
        pass

    def on_stage_change(self, stage: str, status: str):
        pass

    def on_error(self, error: Exception):
        click.secho(f"Error: {error}", fg="red", err=True)


@click.group()
def main():
    """Meowth - GBA Pokemon ROM translation tool."""
    _load_env()


@main.command("check-texts")
@click.argument("texts_json", type=click.Path(exists=True))
@click.option("--rom", "rom_path", required=True, type=click.Path(exists=True),
              help="原版 ROM（校验 game_id + LZ/原地址算法）")
@click.option("--threshold", default=0, type=click.IntRange(0, 100),
              help="仅诊断评分用；拒绝清单只看 rejects/allows（默认 0=不按分拒绝）")
@click.option("--modules", default=None,
              help="逗号分隔模块名；给定后先模块筛选再应用 rejects/allows")
@click.option("--top", default=20, type=int, help="终端显示的可疑条目数")
def check_texts(texts_json, rom_path, threshold, modules, top):
    """校验 texts.json：rejects/allows 拒绝清单（仅报告，不写文件）。"""
    from collections import Counter
    from .modules import parse_modules_csv
    from .text_checker import check_texts as run_check

    src = Path(texts_json)
    report = run_check(
        src,
        Path(rom_path),
        threshold=threshold,
        modules=parse_modules_csv(modules),
    )
    click.echo(f"texts.json : {src}")
    click.echo(
        f"ROM        : {rom_path}  (game_id={report['rom_game_id']}, match=OK)"
    )
    if report.get("total_score") is not None and threshold > 0:
        click.echo(
            f"总评分     : {report['total_score']} / 100  (诊断用，不参与拒绝)"
        )
    scope = ""
    if report.get("module_candidates") is not None and report.get("entries_total") is not None:
        scope = f"  模块候选 {report['module_candidates']}/{report['entries_total']}"
    click.echo(
        f"拒绝条目   : {report['suspicious_count']} / {report['total_count']}"
        f"（rejects/allows）{scope}"
    )

    sus = report["suspicious"]
    if sus:
        click.echo(f"\nTop {min(top, len(sus))} 拒绝条目:")
        click.echo(f"  {'id':<22} {'address':<12} {'module':<10} {'score':>5}  hits")
        for e, hits, score in sorted(sus, key=lambda x: (x[2] is None, x[2] if x[2] is not None else 0))[:top]:
            sc = "" if score is None else f"{score:>5}"
            click.echo(
                f"  {e.get('id',''):<22} {e.get('address',''):<12} "
                f"{(e.get('module') or ''):<10} {sc:>5}  {','.join(hits)}"
            )
        mod_tot = Counter(e[0].get("module") for e in report["suspicious"])
        click.echo("\n按模块统计（拒绝数/总数）:")
        all_mod = Counter()
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            all_mod = Counter(e.get("module") for e in data.get("entries") or [])
        except (OSError, ValueError):
            pass
        for m, n in mod_tot.most_common(10):
            click.echo(f"  {m}: {n}/{all_mod.get(m, 0)}")
    else:
        click.echo("\n未发现拒绝条目。")


@main.command()
@click.argument("rom_path", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Copy to path (default: return configs/.../translate/texts.json)")
@click.option("--source", default="en", help="Source language code (default: from config or en)")
@click.option("--target", default="zh-Hans", help="Target language code (default: from config or zh-Hans)")
@_modules_option
def extract(rom_path, output, source, target, modules):
    """Load curated translate/texts.json (no ROM dump; modules ignored)."""
    from .modules import parse_modules_csv
    from .config_loader import list_available_games
    from .core.engine import detect_game

    source = _get_language(source, "en", "source_language")
    target = _get_language(target, "zh-Hans", "target_language")
    validate_language(source)
    validate_language(target)
    if detect_game(Path(rom_path)) in list_available_games() and source == "en":
        source = "ja"
    config = TranslationConfig(
        source_lang=source,
        target_lang=target,
        rom_path=Path(rom_path),
    )
    engine = TranslationEngine(config, CLICallbacks())
    out = engine.extract_texts(
        Path(rom_path),
        Path(output) if output else None,
        modules=parse_modules_csv(modules),
    )
    click.echo(f"Texts: {out} (source={source})")


@main.command("seed-translate")
@click.argument("texts_json", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output path (default: configs/<game_id>/translate/texts_translated.json)")
@click.option("--only-seeded", is_flag=True, help="Keep only entries that got a seed translation")
def seed_translate(texts_json, output, only_seeded):
    """Offline ja→zh seed translations for AXVJ (no API key)."""
    from .seed_translate import seed_translate_file

    out = Path(output) if output else _default_translated_path(Path(texts_json))
    n_seed, n_total = seed_translate_file(
        Path(texts_json), out, only_seeded=only_seeded
    )
    click.echo(f"Seeded {n_seed}/{n_total} -> {out}")


@main.command()
@click.argument("texts_json", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output path (default: configs/<game_id>/translate/texts_translated.json)")
@click.option("--batch-size", default=30, help="Texts per LLM batch")
@click.option("--workers", default=10, help="Parallel translation threads")
@click.option("--source", default="en", help="Source language code (default: from config or en)")
@click.option("--target", default="zh-Hans", help="Target language code (default: from config or zh-Hans)")
@click.option("--seed-only", is_flag=True, help="Glossary+seed only (no LLM)")
@click.option("--rom", "rom_path", type=click.Path(exists=True), default=None,
              help="原版 ROM（可选；写入 reject 清单元数据）")
@add_provider_options
def translate(texts_json, output, batch_size, workers, source, target, seed_only,
              rom_path,
              provider, api_base, api_key, api_key_env, model):
    """Translate extracted texts JSON via LLM API (or --seed-only)."""
    source = _get_language(source, "en", "source_language")
    target = _get_language(target, "zh-Hans", "target_language")
    validate_language(source)
    validate_language(target)
    kwargs = _provider_kwargs(provider, api_base, api_key_env, model, api_key=api_key)

    config = TranslationConfig(
        source_lang=source,
        target_lang=target,
        batch_size=batch_size,
        max_workers=workers,
        seed_only=seed_only,
        seed_first=True,
        rom_path=Path(rom_path) if rom_path else None,
        **kwargs
    )
    # Infer game from JSON meta
    import json
    from .config_loader import load_game_config
    meta = json.loads(Path(texts_json).read_text(encoding="utf-8"))
    gid = meta.get("game_id", "")
    if gid:
        try:
            load_game_config(gid)
            config.game = gid
            if config.source_lang == "en":
                config.source_lang = "ja"
        except FileNotFoundError:
            pass
    engine = TranslationEngine(config, CLICallbacks())
    out = Path(output) if output else _default_translated_path(Path(texts_json))
    engine.translate_texts(Path(texts_json), out)
    click.echo(f"Translated: {out}")


@main.command()
@click.argument("rom_path", type=click.Path(exists=True))
@click.option("--translations", required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True)
@click.option("--source", default="en", help="Source language code (default: from config or en)")
@click.option("--target", default="zh-Hans", help="Target language code (default: from config or zh-Hans)")
def build(rom_path, translations, output, source, target):
    """Build translated ROM from translations."""
    source = _get_language(source, "en", "source_language")
    target = _get_language(target, "zh-Hans", "target_language")
    validate_language(source)
    validate_language(target)

    config = TranslationConfig(
        source_lang=source,
        target_lang=target,
        rom_path=Path(rom_path),
    )
    engine = TranslationEngine(config, CLICallbacks())
    engine.build_rom(Path(rom_path), Path(translations), Path(output))


@main.command()
@click.argument("rom_path", type=click.Path(exists=True))
@click.option("-o", "--output-dir", default="outputs")
@click.option("--work-dir", default="work")
@click.option("--source", default="en", help="Source language code (default: from config or en)")
@click.option("--target", default="zh-Hans", help="Target language code (default: from config or zh-Hans)")
@click.option("--seed-only", is_flag=True, help="Glossary+seed only (no LLM; good for AXVJ smoke)")
@click.option(
    "--bdf",
    "bdf_font_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="CJK BDF bitmap font; builds work fonts and keeps them (no default-bin overwrite)",
)
@click.option(
    "--tiles-dir",
    type=click.Path(dir_okay=True, path_type=Path),
    default=None,
    help="Tiles dir (tiles_patcher export output); patches graphics after translate",
)
@_modules_option
@add_provider_options
def full(rom_path, output_dir, work_dir, source, target, seed_only, bdf_font_path, tiles_dir,
         modules,
         provider, api_base, api_key, api_key_env, model):
    """Run full pipeline: load translate/texts.json -> translate -> build ROM."""
    from .modules import parse_modules_csv

    source = _get_language(source, "en", "source_language")
    target = _get_language(target, "zh-Hans", "target_language")
    validate_language(source)
    validate_language(target)
    kwargs = _provider_kwargs(provider, api_base, api_key_env, model, api_key=api_key)

    from .config_loader import list_available_games
    from .core.engine import detect_game

    game = detect_game(Path(rom_path))
    if game in list_available_games() and source == "en":
        source = "ja"
    config = TranslationConfig(
        source_lang=source,
        target_lang=target,
        rom_path=Path(rom_path),
        output_dir=Path(output_dir),
        work_dir=Path(work_dir),
        modules=parse_modules_csv(modules),
        seed_only=seed_only,
        seed_first=True,
        bdf_font_path=bdf_font_path,
        tiles_dir=tiles_dir,
        game=game if game != "unknown" else "firered",
        **kwargs
    )
    engine = TranslationEngine(config, CLICallbacks())
    engine.run_full()


if __name__ == "__main__":
    main()
