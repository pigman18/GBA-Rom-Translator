import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=[l for l in open(f,encoding='utf-8').read().splitlines() if l.strip()]
for i,ln in enumerate(lines[:20]):
    o=json.loads(ln)
    print('---',i,o.get('type'))
    print(json.dumps(o,ensure_ascii=False)[:1500])
