
import json, sys
import importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location("tp", "src/util/texts_patcher.py")
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

mapping = {
    "　": " ", "\\n": "\n", "\\c": "\n\n", "\\r": "\\l", "\\e": "",
    "[PLAYER]": "\\01", "[STR_VAR_1]": "\\02", "[STR_VAR_3]": "\\04",
    "[STR_VAR_2]": "\\03", "[KUN]": "\\05", "[RIVAL]": "\\06",
    "[RIGHT_ARROW]": "\\CC0CFA", "[LEFT_ARROW]": "\\CC0CF9",
    "[UP_ARROW]": "\\CC0CF7", "[DOWN_ARROW]": "\\CC0CF8",
    "[EVIL_TEAM]": "\\08", "[GOOD_TEAM]": "\\09",
    "[EVIL_LEADER]": "\\0A", "[GOOD_LEADER]": "\\0B",
    "[B_PLAYER_NAME]": "\\20", "[B_BUFF1]": "\\00", "[B_BUFF2]": "\\01",
    "[B_ATK_NAME_WITH_PREFIX]": "\\0C", "[B_DEF_NAME_WITH_PREFIX]": "\\0D",
}
doc = json.load(open("src/util/work/POKEMON_RUBY_AXVJ00/texts.json", encoding="utf-8"))
all_sks = [tp._msg_soft_key(e.get("original") or "") for e in doc["entries"]]
all_sks = [k for k in all_sks if k]
sk_set = set(all_sks)

lines = open("src/util/configs/reference_corpus/RubySapphire/ja-Hrkt_msg.txt", encoding="utf-8").read().splitlines()

physical = len(lines)          # 物理行（含空行）
valid = 0                      # 有效行（映射后确有文本）
hit_exact = hit_contains = 0   # 精确命中 / 包含命中
for ln in lines:
    if not ln.strip(): continue
    mp = tp._apply_msg_mapping(ln, mapping)
    if not mp.strip(): continue
    valid += 1
    k = tp._msg_soft_key(mp)
    if not k:
        continue
    if k in sk_set:
        hit_exact += 1; hit_contains += 1
        continue
    if any(k in s or s in k for s in all_sks):
        hit_contains += 1

print(f"语料物理行           : {physical}")
print(f"有效行(映射后非空)   : {valid}")
print(f"A) 包含式 / 物理行   : {hit_contains}/{physical} = {100*hit_contains/physical:.1f}%")
print(f"B) 包含式 / 有效行   : {hit_contains}/{valid} = {100*hit_contains/valid:.1f}%")
print(f"C) 整句精确 / 有效行 : {hit_exact}/{valid} = {100*hit_exact/valid:.1f}%")
