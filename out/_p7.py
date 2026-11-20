import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=[l for l in open(f,encoding='utf-8').read().splitlines() if l.strip()]
o=json.loads(lines[10298])
print(json.dumps(o,ensure_ascii=False)[:3000])
print('----- tool/call -----')
print(json.dumps(json.loads(lines[10300]),ensure_ascii=False)[:2000])
