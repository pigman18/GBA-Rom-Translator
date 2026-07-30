"""Build full ROM with font patch + Chinese text inject."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(r"C:\code\gba\tools\Meowth-GBA-Translator-JP\src")))

from meowth.core.config import TranslationConfig
from meowth.core.engine import TranslationEngine

rom_in = Path(r"C:\code\gba\roms\origin\POKEMON_RUBY_AXVJ00.gba")
texts = Path(r"C:\code\gba\work\texts_translated.json")
rom_out = Path(r"C:\code\gba\roms\outputs\POKEMON_RUBY_AXVJ00_zh.gba")

config = TranslationConfig(
    source_lang="ja",
    target_lang="zh-Hans",
    game="ruby_jp",
    work_dir=Path(r"C:\code\gba\work"),
    output_dir=Path(r"C:\code\gba\roms\outputs"),
)
engine = TranslationEngine(config)

print("Building ROM...")
engine.build_rom(rom_in, texts, rom_out)
print(f"Done: {rom_out}")
