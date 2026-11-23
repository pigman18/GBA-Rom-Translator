import json
d = json.load(open('work/POKEMON_RUBY_AXVJ00/translate.build.json', encoding='utf-8'))
entries = d.get('entries', [])

# 看图鉴说明 relocate 条目的完整字段结构
cnt = 0
for e in entries:
    if e.get('module') == '图鉴说明' and e.get('type') == 'relocate':
        print(json.dumps(e, ensure_ascii=False))
        cnt += 1
        if cnt >= 3:
            break
