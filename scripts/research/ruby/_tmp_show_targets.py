import json

p = r"configs/POKEMON_RUBY_AXVJ00/translate/texts.json"
d = json.load(open(p, encoding="utf-8"))
targets = ["招式名", "特性名", "属性名", "道具名", "图鉴分类名", "秘密基地装饰名",
           "树果名", "性格名"]
for t in targets:
    m = d["modules"][t]
    print(f"--- {t}")
    print(json.dumps(m, ensure_ascii=False, indent=1))
