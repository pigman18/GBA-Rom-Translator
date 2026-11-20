import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=[l for l in open(f,encoding='utf-8').read().splitlines() if l.strip()]
def text_of(o):
    m=o.get('message') or o
    parts=m.get('content') or m.get('parts') or []
    out=[]
    if isinstance(parts,str): return parts
    for p in parts:
        if isinstance(p,str): out.append(p)
        elif isinstance(p,dict):
            t=p.get('type')
            if t=='text': out.append(p.get('text',''))
            else: out.append('['+str(t)+']')
    return '\n'.join(out)
n=0
for i,ln in enumerate(lines):
    o=json.loads(ln)
    if o.get('type')=='user/message':
        n+=1
        print('='*20,'USER',n,'idx',i,'='*20)
        print(text_of(o)[:3000])
