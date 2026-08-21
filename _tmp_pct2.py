
import json, sys
import importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
spec = importlib.util.spec_from_file_location("tp", "src/util/texts_patcher.py")
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)

mapping = {
    "　": " ", "\\n": "\n", "\\c": "\n\n", "\\r": "\\l", "\\e": "",
    "[PLAYER]": "\\01", "[STR_VAR_1]": "\\02", "[STR_VAR_2]": "\\03",
    "[STR_VAR_3]": "\\04", "[KUN]": "\\05", "[RIVAL]": "\\06",
    "[RIGHT_ARROW]": "\\CC0CFA", "[LEFT_ARROW]": "\\CC0CF9",
    "[UP_ARROW]": "\\CC0CF7", "[DOWN_ARROW]": "\\CC0CF8",
    "[EVIL_TEAM]": "\\08", "[GOOD_TEAM]": "\\09",
    "[EVIL_LEADER]": "\\0A", "[GOOD_LEADER]": "\\0B",
    "[B_PLAYER_NAME]": "\\20", "[B_BUFF1]": "\\00", "[B_BUFF2]": "\\01",
    "[B_ATK_NAME_WITH_PREFIX]": "\\0C", "[B_DEF_NAME_WITH_PREFIX]": "\\0D",
}
doc = json.load(open("src/util/work/POKEMON_RUBY_AXVJ00/texts.json", encoding="utf-8"))
all_sks = [k for k in (tp._msg_soft_key(e.get("original") or "") for e in doc["entries"]) if k]
sk_set = set(all_sks)

lines = open("src/util/configs/reference_corpus/RubySapphire/ja-Hrkt_msg.txt", encoding="utf-8").read().splitlines()
physical = len(lines)
blank = empty_key = miss = hit = 0
samples_empty = []
for ln in lines:
    if not ln.strip():
        blank += 1; continue
    mp = tp._apply_msg_mapping(ln, mapping)
    if not mp.strip():
        blank += 1; continue
    k = tp._msg_soft_key(mp)
    if not k:
        empty_key += 1
        if len(samples_empty) < 8: samples_empty.append(ln[:30])
        continue
    if k in sk_set or any(k in s or s in k for s in all_sks):
        hit += 1
    else:
        miss += 1

testable = hit + miss
print(f"物理行 {physical} = 空行 {blank} + 有效行 {physical-blank}")
print(f"有效行 = 空键行(纯符号/占位符,不可判定) {empty_key} + 可判定行 {testable}")
print(f"可判定行中: 命中 {hit} + 残留 {miss}")
print()
print(f"=> 可判定行口径 : {100*hit/testable:.1f}%")
print(f"=> 有效行口径   : {100*hit/(physical-blank):.1f}%")
print(f"=> 物理行口径   : {100*hit/physical:.1f}%")
print("空键行样例:", samples_empty)
