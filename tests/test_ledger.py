import json
from backend import ledger

def test_chain_valid_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    ledger.append_event({"request_id": "REQ1", "decision": "REVIEW"})
    ledger.append_event({"request_id": "REQ2", "decision": "LOW RISK"})
    ok, message = ledger.verify_chain()
    assert ok, message
    path = ledger.LEDGER_PATH
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    row["decision"] = "CHANGED"
    path.write_text(json.dumps(row) + "\n" + path.read_text(encoding="utf-8").splitlines()[1] + "\n", encoding="utf-8")
    ok, message = ledger.verify_chain()
    assert not ok and "hash mismatch" in message.lower()
