import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=open(f,encoding='utf-8').read().splitlines()
print("lines",len(lines))
import collections
c=collections.Counter()
for ln in lines:
    if not ln.strip(): continue
    try: o=json.loads(ln)
    except Exception as e: print("bad",ln[:100]); continue
    c[o.get('type') or o.get('kind') or str(list(o.keys()))]+=1
for k,v in c.most_common(40): print(k,v)
print(json.dumps(json.loads(lines[0]),ensure_ascii=False)[:2000])
