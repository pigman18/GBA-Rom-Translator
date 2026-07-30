import json, glob, sys
for path in sorted(glob.glob("configs/*/game.json")):
    cfg = json.loads(open(path, 'r', encoding='utf-8').read())
    rid = cfg.get("rom_id", "?")
    for m in cfg.get("modules", []):
        if m.get("id") in ("训练家名", "训练家类名"):
            sys.stdout.write(f"{rid:15s} {m['id']:10s} start={m.get('start','?'):10s} end={m.get('end','?'):10s}\n")
