"""Seed / offline translate AXVJ extracts (no API required for known UI)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_GLOSSARY_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "glossary_ja_zh-Hans.json"
)
_ITEM_DESC_SEEDS_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "item_desc_seeds.json"
)


@lru_cache(maxsize=1)
def _ja_zh_glossary() -> dict[str, str]:
    """PokeAPI JA→ZH terms (moves/items/abilities/types/species)."""
    if not _GLOSSARY_PATH.is_file():
        return {}
    try:
        data = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data.get("source_to_target") or {})


@lru_cache(maxsize=1)
def _compact_glossary() -> dict[str, str]:
    """Whitespace-stripped glossary keys for flavor/desc matching."""
    out: dict[str, str] = {}
    for ja, zh in _ja_zh_glossary().items():
        ck = re.sub(r"[\s\u3000]+", "", ja)
        if ck and ck not in out:
            out[ck] = zh
    return out


@lru_cache(maxsize=1)
def _item_desc_seeds() -> dict[str, str]:
    if not _ITEM_DESC_SEEDS_PATH.is_file():
        return {}
    try:
        return dict(json.loads(_ITEM_DESC_SEEDS_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


# Exact-match seeds (decoded JP → 简中) — verified against AXVJ ROM strings
EXACT: dict[str, str] = {
    # Keep short: Chinese is 2 tiles/char; long lines overflow the main menu window
    # Pad short labels to 3 Hanzi width so shared title-menu VRAM tiles from
    # 「新游戏」are fully overwritten (0x00 ASCII spaces do NOT clear Chinese
    # tiles — use ideographic space → blank glyph 247).
    "さいしょから はじめる": "新游戏",
    "さいしょからはじめる": "新游戏",
    "つづきから はじめる": "继续　",
    "つづきからはじめる": "继续　",
    "せっていを かえる": "设置　",
    "せっていをかえる": "设置　",
    "ふしぎな できごと": "奇妙事件",
    "しゅじんこう": "主角",
    "ポケモンずかん": "宝可梦图鉴",
    "プレイヤーめい": "玩家名",
    "もっているバッグ": "持有的背包",
    "かいふくパワー": "回复力量",
    "オプション": "选项",
    "はい": "是",
    "いいえ": "否",
    "やめる": "取消",
    "いれかえる": "替换",
    "つよさをみる": "查看能力",
    "\\0Fは どうする？": "\\0F怎么办？",
    "\\20は どうする？": "\\20怎么办？",
    "\\02を どうする？": "\\02怎么办？",
    "おとこ": "男孩",
    "おんな": "女孩",
    "おとこのこ": "男孩",
    "おんなのこ": "女孩",
    "レポート": "记录",
    "カイオーガ": "盖欧卡",
    "グラードン": "固拉多",
    "レポートの ないようが きえてしまった！": "记录的内容消失了！",
    "おとこのこ？\nそれとも おんなのこ？": "你是男孩子？\n还是女孩子？",
    # Naming screen titles (spaces around の match AXVJ ROM)
    "あなた の なまえは？": "你的名字是？",
    "ボックス の なまえは？": "盒子的名字是？",
    "\\02 の ニックネームは？": "\\02 的昵称是？",
    # Battle main menu (FC color + window controls). OK with Chinese drawer.
    "\\CC0505\\CC040D0E0Fたたかう  バッグ\nポケモン  にげる": "\\CC0505\\CC040D0E0F战斗  背包\n宝可梦  逃跑",
    "\\CC0505\\CC040D0E0Fボール   ポロック\nちかづく  にげる": "\\CC0505\\CC040D0E0F精灵球 树果块\n靠近  逃跑",
    "わざ": "技能",
    "めいちゅう": "命中",
    "いりょく": "威力",
    "タイプ": "属性",
    "つよさ": "攻击",
    "ぼうぎょ": "防御",
    "とくこう": "特攻",
    "とくぼう": "特防",
    "すばやさ": "速度",
    # Battle prompts / move-type chrome
    "\\20は どうする？": "\\20怎么办？",
    "は どうする？": "怎么办？",
    "わざタイプ／": "技能属性／",
    "わざタイプ": "技能属性",
    "\\CC0505\\CC040D0E0FＰＰ\nわざタイプ／": "\\CC0505\\CC040D0E0FＰＰ\n技能属性／",
    "\\CC0505\\CC040D0E0FPP\nわざタイプ／": "\\CC0505\\CC040D0E0FPP\n技能属性／",
    "ノーマル": "一般",
    "ほのお": "火",
    "みず": "水",
    "くさ": "草",
    "でんき": "电",
    "こおり": "冰",
    "かくとう": "格斗",
    "どく": "毒",
    "じめん": "地面",
    "ひこう": "飞行",
    "エスパー": "超能",
    "むし": "虫",
    "いわ": "岩石",
    "ゴースト": "幽灵",
    "ドラゴン": "龙",
    "あく": "恶",
    "はがね": "钢",
    "マシンわざ": "机械招式",
    "ミツルは どうする？": "小智要怎么做？",
    # Bag / summary chrome
    "バッグをとじる": "关闭背包",
    "どうぐ": "道具",
    "ポケモンじょうほう": "宝可梦信息",
    "おぼえているわざ": "已学技能",
    "せつめい": "说明",
    "パーソナル": "资料",
    "トレーナーメモ": "训练家备忘",
    "とくせい": "特性",
    "おや/": "亲/",
    "きりかえ": "切换",
    "いれかえ": "替换",
    "たたかうわざ": "对战技能",
    "ポケモンのうりょく": "宝可梦能力",
    # Natures (AXVJ gNatureNamePointers)
    "がんばりや": "勤奋",
    "さみしがり": "孤独",
    "ゆうかん": "勇敢",
    "いじっぱり": "固执",
    "やんちゃ": "顽皮",
    "ずぶとい": "大胆",
    "すなお": "坦率",
    "のんき": "悠闲",
    "わんぱく": "淘气",
    "のうてんき": "乐天",
    "おくびょう": "胆小",
    "せっかち": "急躁",
    "まじめ": "认真",
    "ようき": "爽朗",
    "むじゃき": "天真",
    "ひかえめ": "内敛",
    "おっとり": "慢吞吞",
    "れいせい": "冷静",
    "てれや": "害羞",
    "うっかりや": "马虎",
    "おだやか": "温和",
    "おとなしい": "温顺",
    "なまいき": "自大",
    "しんちょう": "慎重",
    "きまぐれ": "浮躁",
}

# Prefix seeds for long opening dialogue (match after normalizing whitespace).
# Values keep \\01 player-name slots and \\l / blank-line page breaks.
PREFIX_SEEDS: list[tuple[str, str]] = [
    (
        "ママ『\\01 おつかれさま！",
        "妈妈『\\01 辛苦了！\n\n坐那么久卡车过来，很累吧？\n\n"
        "这里就是未白镇哦！\n\n怎么样？这就是我们的新家！\n\n"
        "有点复古的感觉，看起来很好住吧？",
    ),
    (
        "ママ『\\01！ \\01！\nオダマキはかせに あいさつ した？",
        "妈妈『\\01！ \\01！\n去跟小田卷博士问好了吗？\n\n"
        "哎呀！好可爱的宝可梦！\n是小田卷博士给你的吧\n\n"
        "果然是爸爸的孩子呢……\n和宝可梦在一起的样子\\l真合适！",
    ),
    (
        "ママ『\\01！\nこれが せつめいしょ よ",
        "妈妈『\\01！\n这是说明书哦\n\n"
        "「跑步鞋只要按住B键，就能跑得比平时\\l更快」",
    ),
    (
        "いやー おまたせ おまたせ！",
        "哎呀，久等久等了！\n\n"
        "欢迎来到宝可梦的世界！\n\n"
        "我的名字是小田卷！\n\n"
        "不过大家都叫我「宝可梦博士」哦！",
    ),
    (
        "ポケットモンスター\n‥‥すなわち ポケモン",
        "宝可梦\n……也就是宝可梦",
    ),
    (
        "この せかいには\nポケモンと よばれる いきもの たちが",
        "在这个世界上，\n到处都生活着\\l被称为宝可梦的生物！\n\n"
        "我们人类会和宝可梦\n一起玩耍、互相帮助工作，\n\n"
        "有时还会齐心协力\n并肩战斗，\n\n"
        "就这样共同生活着！\n\n"
        "……不过，我们并没有\n了解宝可梦的一切。\n\n"
        "宝可梦的秘密\n还有很多很多！\n\n"
        "为了揭开那些秘密，\n我一直在进行研究，\\l就是这么回事！",
    ),
    (
        "ところで きみは‥‥？",
        "对了，你是……？",
    ),
    # Gender / naming main lines: skip via translate/config.json (not seeded here).
    (
        "\\01\\05 だね？",
        "\\01\\05 对吧？",
    ),
    (
        "‥‥そうか！\n\nきみが こんど わたしの すむ まち",
        "……这样啊！\n\n原来你就是接下来要搬到\n我住的镇子——未白镇来的\\l\\01\\05 啊！",
    ),
    (
        "よーし じゅんびは いいかい？",
        "好了，准备好了吗？\n\n"
        "属于你自己的故事，\n就要开始了！\n\n"
        "在这个充满梦想、冒险和相遇的\n宝可梦世界里，\\l鼓起勇气跳进去吧！\n\n"
        "那么稍后再见！\n我在研究所等你哦！",
    ),
    (
        "おうちの かたづけは",
        "收拾屋子有搬家公司的宝可梦帮忙，\n所以很轻松哦！\n\n"
        "\\01也去二楼自己的房间看看吧！\n\n"
        "爸爸为了庆祝搬家给你买了钟表，\n去把房间的钟表调好吧！",
    ),
    (
        "この じかんで よろしいですか？",
        "就定这个时间吗？",
    ),
    (
        "えっ‥‥！？\nあなた だれ‥‥ なの？",
        "诶……！？\n你是……谁？\n\n"
        "………………\n………………\n\n"
        "你就是\\01\\05……\n对了，今天要搬家来的……\n\n"
        "啊，我是小遥！\n请、请多关照！\n\n"
        "我……\n梦想是和全世界的宝可梦\\l成为朋友……\n\n"
        "而且呢\n从爸爸……小田卷博士那里\\l听说了\\01\\05的事\n\n"
        "我还想着要是也能\\n和\\01\\05成为朋友就好了……\\l……\n\n"
        "啊，我真是的，明明是第一次\\n和\\01\\05说话\\l却说这些……\n\n"
        "嘿嘿……\n\n"
        "啊，糟了！\n\n"
        "我正要去帮爸爸\\n抓野生宝可梦呢！\n\n"
        "\\01\\05\n回、回头见！",
    ),
]

# Short menu labels (clock confirm, battle commands, IME chrome buttons)
# Also used by extract_short_menu_labels — keep entries FF-terminated PCS-friendly.
MENU_LABEL_SEEDS: dict[str, str] = {
    "はい": "是",
    "いいえ": "否",
    "たたかう": "战斗",
    "バッグ": "背包",
    "ポケモン": "宝可梦",
    "にげる": "逃跑",
    "けってい": "决定",
    # やめる: lexicon「取消」；勿再全词 skip（见 translate/README.md）
    "やめる": "取消",
    "いれかえる": "替换",
    "いれかえ": "替换",
    "つよさをみる": "查看能力",
    "\\0Fは どうする？": "\\0F怎么办？",
    "\\20は どうする？": "\\20怎么办？",
    "もどる": "返回",
    "おわり": "结束",
    "おわる": "关闭",
    "おとこ": "男孩",
    "おんな": "女孩",
    "じぶんできめる": "自己决定",
    "じぶんで きめる": "自己决定",
    "なまえ": "名字",
    "おこづかい": "零花钱",
    "プレイじかん": "游戏时间",
    "リーグバッジ": "道馆徽章",
    # Mart / PC chrome (UI bank 0x3E9Fxx / 0x3EBxxx) — screenshot gaps 2026-07-25
    "かいに きた": "来买东西",
    "うりに きた": "来卖东西",
    "なんでもないです": "没什么事",
    "かいもの を やめます": "取消购物",
    "だれかのパソコン": "某人的电脑",
    "マユミのパソコン": "真由美的电脑",
    "スイッチをきる": "关闭电源",
    "なにを しますか？": "要做什么？",
    "ポケモンを つれていく": "取出宝可梦",
    "ポケモンを あずける": "寄存宝可梦",
    "ポケモンを あずける ": "寄存宝可梦",
    "ボックスを せいりする": "整理盒子",
    "さようなら": "再见",
    "ケイ": "圭",
}

# Options menu (FC 05 xx color prefix must be preserved)
OPTION_SEEDS: dict[str, str] = {
    "\\CC0509せっていを かえる": "\\CC0509改变设置",
    "\\CC0509はなしの はやさ": "\\CC0509对话速度",
    "\\CC0509せんとうエフェクト": "\\CC0509战斗动画",
    "\\CC0509しあいの ルール": "\\CC0509对战规则",
    "\\CC0509サウンド": "\\CC0509声音",
    "\\CC0509ウインドウ": "\\CC0509窗口",
    "\\CC0509おわる": "\\CC0509关闭",
    "\\CC0509ボタンの モード": "\\CC0509按键模式",
    "\\CC050Fおそい": "\\CC050F慢",
    "\\CC050Fふつう": "\\CC050F普通",
    "\\CC050Fはやい": "\\CC050F快",
    "\\CC050Fみる": "\\CC050F看",
    "\\CC050Fみない": "\\CC050F不看",
    "\\CC050Fいれかえ": "\\CC050F替换",
    "\\CC050Fかちぬき": "\\CC050F打到底",
    "\\CC050Fモノラル": "\\CC050F单声道",
    "\\CC050Fステレオ": "\\CC050F立体声",
    "\\CC050Fタイプ": "\\CC050F类型",
    "\\CC050Fノーマル": "\\CC050F普通",
    "\\CC050FＬＲ": "\\CC050FLR",
}

GLOSSARY: list[tuple[str, str]] = [
    ("ポケモン", "宝可梦"),
    ("ずかん", "图鉴"),
    ("バッグ", "背包"),
    ("レポート", "记录"),
    ("プレイヤー", "玩家"),
    ("レベル", "等级"),
    ("ジム", "道馆"),
    ("バッジ", "徽章"),
]


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def seed_translate_entry(original: str) -> str | None:
    key = _normalize_ws(original.replace("\n", "").replace("\r", ""))
    compact = key.replace(" ", "")
    if original in MENU_LABEL_SEEDS:
        return MENU_LABEL_SEEDS[original]
    if key in MENU_LABEL_SEEDS:
        return MENU_LABEL_SEEDS[key]
    if original in OPTION_SEEDS:
        return OPTION_SEEDS[original]
    if key in OPTION_SEEDS:
        return OPTION_SEEDS[key]
    if original in EXACT:
        return EXACT[original]
    if key in EXACT:
        return EXACT[key]
    if compact in EXACT:
        return EXACT[compact]
    # Name tables / short terms from PokeAPI glossary
    gloss = _ja_zh_glossary()
    if original in gloss:
        return gloss[original]
    if key in gloss:
        return gloss[key]
    if compact in gloss:
        return gloss[compact]
    # AXVJ item bag descriptions (ROM-faithful seeds)
    idesc = _item_desc_seeds()
    if original in idesc:
        return idesc[original]
    if key in idesc:
        return idesc[key]
    for ja, zh in idesc.items():
        if re.sub(r"[\s\u3000\n\r]+", "", ja) == compact:
            return zh
    # Flavor/desc lines: match ignoring whitespace / fullwidth spaces
    compact_gloss = _compact_glossary()
    if compact in compact_gloss:
        return compact_gloss[compact]
    for prefix, zh in PREFIX_SEEDS:
        if original.startswith(prefix) or key.startswith(_normalize_ws(prefix.replace("\n", ""))):
            return zh
    if len(compact) <= 16:
        out = original
        changed = False
        for jp, zh in GLOSSARY:
            if jp in out:
                out = out.replace(jp, zh)
                changed = True
        if changed and not re.search(r"[\u3040-\u30ff]", out):
            return out
    return None


def looks_like_failed_zh_translation(original: str, translated: str) -> bool:
    """True when a ja→zh result is still Japanese dialogue (format-only fake)."""
    if not translated:
        return True
    if not re.search(r"[\u3040-\u30ff]", original or ""):
        return False
    if re.search(r"[\u4e00-\u9fff]", translated):
        return False
    # Still kana, no Hanzi — not a usable Simplified Chinese line
    return bool(re.search(r"[\u3040-\u30ff]", translated))


def seed_translate_file(inp: Path, out: Path, *, only_seeded: bool = False) -> tuple[int, int]:
    data = json.loads(Path(inp).read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    if not entries and "free_texts" in data:
        entries = list(data.get("free_texts") or [])
        for t in data.get("tables") or []:
            entries.extend(t.get("entries") or [])

    n_seed = 0
    n_total = len(entries)
    kept = []
    for e in entries:
        orig = e.get("original", "")
        if e.get("translated"):
            kept.append(e)
            n_seed += 1
            continue
        zh = seed_translate_entry(orig)
        if zh:
            e["translated"] = zh
            n_seed += 1
            kept.append(e)
        elif not only_seeded:
            kept.append(e)

    if only_seeded:
        data["entries"] = kept
        data.pop("tables", None)
        data.pop("free_texts", None)
        data["count"] = len(kept)
    else:
        data["entries"] = entries

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return n_seed, n_total
