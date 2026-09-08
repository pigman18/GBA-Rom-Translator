"""译文字符集自动审计：打包期校验「译文 ⊆ 字库」。

对照 build_chinese_font 产出的字体 bin（Normal/Small/Middle），逐字检查
最终译文中的 F9 双字节字符是否真的有非空字形。缺字在打包时暴露
（报告文件 + 日志警告），不再靠实机花屏发现。

原则（2026-09-08 调研结论，抄 FEBuilderGBA glyph 审计模式）：
- 只审「落到中文字库的双字节字符」（``charmap.encode_char`` 返回 2 字节）。
  单字节（原版 PCS / 标点映射 / 空格）走游戏原字库，不在审计范围。
- charmap 编不出的字符（``encode_char`` → None）直接报 charmap 缺码——
  这类字符在 inject 阶段会编码失败，属于打包事故。
- 字形覆盖以实际产出的 bin 为准（空槽 = 全零 128B 字节段），不假设 BDF
  来源，fallback / 补画策略怎么改都不影响审计正确性。
- 仅报告不阻断打包：缺字渲染为空白，是否补字由人决定。

用法（管线内）：engine.build_rom 在 inject_texts 前调用
``audit_translation_glyphs``。独立使用：``meowth audit-glyphs texts.json``。
"""
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

BYTES_PER_GLYPH = 128
DEFAULT_GLYPH_COUNT = 7168
AUDIT_LIBS = ("Normal", "Small", "Middle")
_MAX_LOG_CHARS = 50

# 空槽合法白名单：全角空格等「空白即正确渲染」的字符。
_KNOWN_BLANK = frozenset("\u3000")


def _load_font_builder():
    """加载 scripts/build_chinese_font.py（复用 parse_charmap/glyph_index）。"""
    p = Path(__file__).resolve().parents[2] / "scripts" / "build_chinese_font.py"
    if not p.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            "meowth_build_chinese_font", p
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _pick_bins(fonts_dir: Path, prefix: str, prefer_unshadow: bool) -> dict:
    """按库标签选审计对象 bin：shadow=False 时 ROM 嵌入 *_unshadow 副本。"""
    bins: dict[str, bytes] = {}
    if not fonts_dir.is_dir():
        return bins
    for lbl in AUDIT_LIBS:
        all_bins = [
            f for f in sorted(fonts_dir.glob(f"{prefix}{lbl}*bin"))
            if f.suffix == ".bin"
        ]
        wanted = [f for f in all_bins if ("_unshadow" in f.name) == prefer_unshadow]
        if not wanted and prefer_unshadow:
            wanted = [f for f in all_bins if "_unshadow" not in f.name]
        if wanted:
            try:
                bins[lbl] = wanted[0].read_bytes()
            except OSError:
                continue
    return bins


def _example(entry: dict) -> str:
    """缺字示例：module/id + 译文片段。"""
    mod = entry.get("module") or "-"
    eid = entry.get("id") or "-"
    tr = str(entry.get("translated") or "").replace("\n", "\\n")
    if len(tr) > 24:
        tr = tr[:24] + "…"
    return f"[{mod}] {eid}: {tr}"


def audit_translation_glyphs(
    entries: list[dict],
    charmap,
    game_work: Path,
    log=None,
    *,
    game: str | None = None,
    report_name: str = "glyph_audit_report.txt",
) -> dict:
    """审计最终译文 ⊆ 字库。返回报告 dict；缺字只警告不抛错。

    ``entries``：含 ``translated`` 的最终条目（inject 前的 all_entries）。
    ``charmap``：engine 的 ``Charmap`` 实例（用 encode_char/_sanitize 镜像编码）。
    ``game_work``：work/<game> 目录（charmap.txt + graphic/fonts/*.bin）。
    """
    game_work = Path(game_work)

    def _log(level: str, msg: str):
        if log is not None:
            log(level, msg)

    # --- 1. 收集最终译文字符（sanitize 与 encode 同路，镜像最终落 ROM 文本）---
    # translated == original 的条目是「整条保留日文」：inject 前被
    # _injectable_translation 过滤、原样保留 JP 字节，不经 charmap，不审计。
    usage: dict[str, dict] = {}
    sanitize = getattr(charmap, "_sanitize", None)
    for e in entries or []:
        tr = e.get("translated")
        if not tr or tr == e.get("original"):
            continue
        s = sanitize(tr) if callable(sanitize) else str(tr)
        for ch in s:
            if ord(ch) < 0x80:
                continue  # ASCII / 反斜杠控制码不在审计范围
            if ch in _KNOWN_BLANK:
                continue  # 全角空格等：空白即正确渲染
            if ch not in usage:
                usage[ch] = e

    # --- 2. 分类：charmap 缺码 / 单字节原版字库 / 双字节中文字库 ---
    charmap_missing: list[str] = []
    zh_chars: list[str] = []
    for ch in sorted(usage):
        try:
            enc = charmap.encode_char(ch)
        except Exception:
            enc = None
        if enc is None:
            charmap_missing.append(ch)
        elif len(enc) >= 2:
            zh_chars.append(ch)
        # 单字节 → 原版 PCS 字库，跳过

    # --- 3. charmap → 槽位（与字体构建同一映射来源）---
    idx_of_char: dict[str, int] = {}
    fb = _load_font_builder()
    cm_path = game_work / "charmap.txt"
    if fb is not None and cm_path.is_file():
        try:
            idx_of_char = {c: i for i, c in fb.parse_charmap(cm_path).items()}
        except Exception as exc:  # pragma: no cover
            _log("warning", f"[字形审计] 解析 charmap.txt 失败: {exc}")
    if not idx_of_char and zh_chars:
        _log(
            "warning",
            "[字形审计] 无法建立 charmap→槽位映射（charmap.txt 或 "
            "build_chinese_font 不可用），bin 覆盖检查跳过",
        )

    # --- 4. 读实际产出的 bin，逐字检查空槽 ---
    prefix = "PokeRSFontChs"
    try:
        from .config_loader import load_game_config

        if game:
            fp_cfg = load_game_config(game).get("font_patch") or {}
            prefix = fp_cfg.get("font_bin_prefix", prefix)
            prefer_unshadow = fp_cfg.get("shadow") is False
    except Exception:
        prefer_unshadow = False
    bins = _pick_bins(game_work / "graphic" / "fonts", prefix, prefer_unshadow)

    missing: dict[str, dict[str, dict]] = {lbl: {} for lbl in bins}
    not_in_fontmap: list[str] = []
    for ch in zh_chars:
        idx = idx_of_char.get(ch)
        if idx is None:
            not_in_fontmap.append(ch)
            for lbl in bins:
                missing[lbl][ch] = usage[ch]
            continue
        if idx >= DEFAULT_GLYPH_COUNT:
            for lbl in bins:
                missing[lbl][ch] = usage[ch]
            continue
        off = idx * BYTES_PER_GLYPH
        for lbl, data in bins.items():
            chunk = data[off : off + BYTES_PER_GLYPH] if len(data) >= off + BYTES_PER_GLYPH else b""
            if not any(chunk):
                missing[lbl][ch] = usage[ch]

    # --- 5. 汇总报告 ---
    lib_missing_counts = {lbl: len(m) for lbl, m in missing.items()}
    report = {
        "entries_audited": len(entries or []),
        "chars_total": len(usage),
        "zh_chars": len(zh_chars),
        "charmap_missing": charmap_missing,
        "not_in_fontmap": not_in_fontmap,
        "missing": {lbl: sorted(m) for lbl, m in missing.items()},
        "missing_counts": lib_missing_counts,
        "bins_audited": sorted(bins),
        "clean": not (charmap_missing or any(missing.values())),
    }
    report_path = game_work / report_name
    try:
        _write_report(report, missing, usage, charmap_missing, report_path)
    except OSError as exc:  # pragma: no cover
        _log("warning", f"[字形审计] 报告写入失败: {exc}")
    report["report_path"] = str(report_path)

    # --- 6. 日志 ---
    libs_ok = " / ".join(
        f"{lbl}{'✓' if lbl in bins else '(无bin)'}" for lbl in AUDIT_LIBS
    )
    if report["clean"]:
        _log(
            "info",
            f"[字形审计] 通过：译文双字节字符 {len(zh_chars)} 个"
            f"（bin: {', '.join(bins) or '无'}），报告 {report_path}",
        )
        _ = libs_ok
    else:
        parts = []
        if charmap_missing:
            parts.append(f"charmap 缺码 {len(charmap_missing)}")
        for lbl, m in missing.items():
            if m:
                parts.append(f"{lbl} 空槽 {len(m)}")
        sample = "".join(sorted(set(charmap_missing) | set().union(*[set(m) for m in missing.values()]))[:_MAX_LOG_CHARS])
        _log(
            "warning",
            f"[字形审计] 缺字（{'，'.join(parts)}）：{sample}"
            f"… 详见 {report_path}",
        )
    return report


def _write_report(
    report: dict,
    missing: dict[str, dict[str, dict]],
    usage: dict[str, dict],
    charmap_missing: list[str],
    path: Path,
) -> None:
    lines: list[str] = []
    lines.append("译文字符集审计报告（打包期自动生成）")
    lines.append(f"条目数: {report['entries_audited']}  译文不同字符: {report['chars_total']}"
                 f"（双字节 {report['zh_chars']}）")
    lines.append(f"审计 bin: {', '.join(report['bins_audited']) or '无'}")
    lines.append("")
    if charmap_missing:
        lines.append(f"== charmap 缺码（编码失败，inject 会出错）: {len(charmap_missing)} ==")
        for ch in charmap_missing:
            lines.append(f"  {ch}  U+{ord(ch):04X}  例: {_example(usage[ch])}")
        lines.append("")
    for lbl in AUDIT_LIBS:
        m = missing.get(lbl) or {}
        if not m:
            continue
        lines.append(f"== {lbl} 空槽（实机渲染为空白）: {len(m)} ==")
        for ch in m:
            lines.append(
                f"  {ch}  U+{ord(ch):04X}  例: {_example(m[ch])}"
            )
        lines.append("")
    if report["clean"]:
        lines.append("全部通过：译文所有双字节字符在各库均有非空字形。")
    path.write_text("\n".join(lines), encoding="utf-8")


def audit_texts_file(
    texts_json: Path,
    game_work: Path,
    game: str,
    target_lang: str = "zh-Hans",
) -> dict:
    """独立入口：texts.json → 审计（供 CLI audit-glyphs 使用）。"""
    from .charmap import Charmap
    from .config_loader import load_game_config, load_codec

    data = json.loads(Path(texts_json).read_text(encoding="utf-8"))
    entries: list[dict] = list(data.get("entries") or [])
    entries += list(data.get("free_texts") or [])
    for tbl in data.get("tables") or []:
        entries += list(tbl.get("entries") or [])

    cfg = load_game_config(game) or {}
    charmap_cfg = dict(cfg.get("charmap") or {})
    codec_cm = (load_codec(game) or {}).get("charmap") or {}
    if isinstance(codec_cm, dict):
        charmap_cfg = {**codec_cm, **charmap_cfg}
    from .config_loader import get_charmap_path

    cm_path = Path(game_work) / "charmap.txt"
    if not cm_path.is_file():
        cm_path = get_charmap_path(game)
    charmap_cfg["charmap_path"] = str(cm_path)
    charmap = Charmap(target_lang=target_lang, charmap_cfg=charmap_cfg)
    return audit_translation_glyphs(
        entries, charmap, game_work, game=game,
    )
