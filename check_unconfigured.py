import json, glob
for path in sorted(glob.glob("configs/*/game.json")):
    cfg = json.loads(open(path, 'r', encoding='utf-8').read())
    rid = cfg.get("rom_id", "?")
    for m in cfg.get("modules", []):
        if m["start"] == "0x0" and m["end"] == "0x0":
            print(f"{rid:15s} {m['id']:15s} UNCONFIGURED")
