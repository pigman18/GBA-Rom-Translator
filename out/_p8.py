import json
f=r"C:\code\GBA-Rom-Translator\out\sess_420dbb06.jsonl"
lines=[l for l in open(f,encoding='utf-8').read().splitlines() if l.strip()]
buf=[]
for i,ln in enumerate(lines):
    o=json.loads(ln)
    t=o.get('type')
    if t=='assistant/message':
        d=o.get('data',{})
        m=d.get('message',{})
        txt=[]
        for p in m.get('content',[]):
            if p.get('type')=='text' and p.get('text','').strip():
                txt.append(p['text'])
        if txt:
            buf.append('='*12+f' A idx {i} turn {d.get("turn")} '+'='*12)
            buf.append('\n'.join(txt))
open(r"C:\code\GBA-Rom-Translator\out\_assist_all.txt",'w',encoding='utf-8').write('\n'.join(buf))
print('ok',len(buf))
