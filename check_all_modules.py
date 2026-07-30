import json, glob
for path in sorted(glob.glob("configs/*/game.json")):
    cfg = json.loads(open(path, 'r', encoding='utf-8').read())
    rid = cfg.get("rom_id", "?")
    print(f"\n=== {rid} ===")
    for m in cfg.get("modules", []):
        print(f"  {m['id']:15s}  {m.get('start','?'):10s}  {m.get('end','?'):10s}")
