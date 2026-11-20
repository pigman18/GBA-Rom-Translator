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
buf=[]
for i,ln in enumerate(lines):
    if i < 9000: continue
    o=json.loads(ln)
    if o.get('type')=='assistant/message':
        buf.append('='*15+f' ASSISTANT idx {i} '+'='*15)
        buf.append(text_of(o))
open(r"C:\code\GBA-Rom-Translator\out\_assist_tail.txt",'w',encoding='utf-8').write('\n'.join(buf))
print('ok')
