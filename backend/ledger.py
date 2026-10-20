from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "data" / "ledger.jsonl"
GENESIS = "0" * 64

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def read_events():
    if not LEDGER_PATH.exists(): return []
    with LEDGER_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

def append_event(event):
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    events = read_events()
    body = {**event, "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": events[-1]["record_hash"] if events else GENESIS}
    body["record_hash"] = digest(body)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body, sort_keys=True) + "\n")
    return body

def verify_chain():
    previous = GENESIS
    for i, event in enumerate(read_events(), 1):
        if event.get("previous_hash") != previous:
            return False, f"Broken previous-hash link at record {i}"
        body = {k:v for k,v in event.items() if k != "record_hash"}
        if digest(body) != event.get("record_hash"):
            return False, f"Record hash mismatch at record {i}"
        previous = event["record_hash"]
    return True, "Hash chain valid"

def explanation_hash(reasons):
    return hashlib.sha256("|".join(reasons).encode()).hexdigest()
