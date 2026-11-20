import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=[l for l in open(f,encoding='utf-8').read().splitlines() if l.strip()]
def text_of(o):
    d=o.get('data',o)
    parts=d.get('content') or []
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
        d=o.get('data',{})
        src=(d.get('source') or {}).get('kind')
        if src in ('user',):
            n+=1
            print('='*15,'USERMSG',n,'idx',i,'='*15)
            print(text_of(o))
