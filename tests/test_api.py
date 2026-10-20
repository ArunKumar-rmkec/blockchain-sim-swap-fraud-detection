import pytest
from fastapi import HTTPException
from backend.main import health, metrics, requests, evaluate, audit, EvaluationRequest
from backend import ledger

def test_health():
    res = health()
    assert res["status"] == "ok"
    assert res["mode"] == "synthetic-demo"

def test_metrics():
    res = metrics()
    assert "accuracy" in res
    assert "precision" in res
    assert "recall" in res
    assert "f1" in res
    assert res["test_records"] > 0

def test_requests():
    res = requests()
    assert len(res) > 0
    assert "request_id" in res[0]

def test_evaluate_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    payload = EvaluationRequest(request_id="REQ00001", agent_uid="A1B2C3D4")
    res = evaluate(payload)
    assert res["request_id"] == "REQ00001"
    assert res["decision"] in ["LOW RISK", "REVIEW", "HIGH RISK"]
    assert 0.0 <= res["risk_score"] <= 1.0
    assert "audit" in res
    assert res["audit"]["agent_uid"] == "A1B2C3D4"

def test_evaluate_invalid_agent():
    payload = EvaluationRequest(request_id="REQ00001", agent_uid="UNKNOWN_AGENT")
    with pytest.raises(HTTPException) as exc:
        evaluate(payload)
    assert exc.value.status_code == 403

def test_evaluate_missing_request():
    payload = EvaluationRequest(request_id="REQ99999_NONEXISTENT", agent_uid="A1B2C3D4")
    with pytest.raises(HTTPException) as exc:
        evaluate(payload)
    assert exc.value.status_code == 404

def test_audit_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    payload = EvaluationRequest(request_id="REQ00001", agent_uid="DEMO1234")
    evaluate(payload)
    res = audit()
    assert res["valid"] is True
    assert res["count"] == 1


def test_hardware_evaluate_valid(tmp_path, monkeypatch):
    from backend.main import hardware_evaluate, TerminalEvaluationRequest
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")
    payload = TerminalEvaluationRequest(
        request_id="REQ00001",
        agent_uid="A1B2C3D4",
        terminal_id="ESP32_LAB_01"
    )
    res = hardware_evaluate(payload)
    assert res["request_id"] == "REQ00001"
    assert res["terminal_id"] == "ESP32_LAB_01"
    assert "hardware" in res
    hw = res["hardware"]
    assert "hardware_commands" in hw
    assert "lcd" in hw["hardware_commands"]
    assert "led" in hw["hardware_commands"]
    assert "buzzer" in hw["hardware_commands"]
    assert hw["hardware_commands"]["led"]["color"] in ["GREEN", "YELLOW", "RED"]


def test_hardware_evaluate_invalid_agent():
    from backend.main import hardware_evaluate, TerminalEvaluationRequest
    payload = TerminalEvaluationRequest(
        request_id="REQ00001",
        agent_uid="ROGUE_CARD_99",
        terminal_id="ESP32_LAB_01"
    )
    with pytest.raises(HTTPException) as exc:
        hardware_evaluate(payload)
    assert exc.value.status_code == 403
    assert "INVALID CARD UID" in exc.value.detail["hardware"]["hardware_commands"]["lcd"]["line2"]


def test_hardware_evaluate_missing_request():
    from backend.main import hardware_evaluate, TerminalEvaluationRequest
    payload = TerminalEvaluationRequest(
        request_id="REQ_DOES_NOT_EXIST",
        agent_uid="A1B2C3D4",
        terminal_id="ESP32_LAB_01"
    )
    with pytest.raises(HTTPException) as exc:
        hardware_evaluate(payload)
    assert exc.value.status_code == 404
    assert "REQ NOT FOUND" in exc.value.detail["hardware"]["hardware_commands"]["lcd"]["line2"]


def test_hardware_terminal_state_and_reset():
    from backend.main import terminal_state, terminal_reset
    # Reset terminal
    reset_res = terminal_reset()
    assert reset_res["lcd"]["line1"] == "READY: TAP CARD"
    assert reset_res["led"]["color"] == "OFF"

    # Query state
    curr_state = terminal_state()
    assert curr_state["terminal_id"] == "ESP32_TERM_01"
    assert curr_state["lcd"]["line1"] == "READY: TAP CARD"


def test_hardware_ports():
    from backend.main import hardware_ports
    ports = hardware_ports()
    assert isinstance(ports, list)


def test_hardware_bridge_signal_mapping():
    from backend.hardware_bridge import format_hardware_response
    # Low Risk -> Green LED, 2 beeps
    low_hw = format_hardware_response("LOW RISK", 12.5, "REQ00001")
    assert low_hw["hardware_commands"]["led"]["color"] == "GREEN"
    assert low_hw["hardware_commands"]["led"]["pin_green"] == 1
    assert low_hw["hardware_commands"]["buzzer"]["mode"] == "SUCCESS"

    # Review -> Yellow LED, 3 beeps
    rev_hw = format_hardware_response("REVIEW", 55.0, "REQ00002")
    assert rev_hw["hardware_commands"]["led"]["color"] == "YELLOW"
    assert rev_hw["hardware_commands"]["led"]["pin_yellow"] == 1
    assert rev_hw["hardware_commands"]["buzzer"]["mode"] == "WARN"

    # High Risk -> Red LED, 5 beeps
    fraud_hw = format_hardware_response("HIGH RISK", 94.0, "REQ00701")
    assert fraud_hw["hardware_commands"]["led"]["color"] == "RED"
    assert fraud_hw["hardware_commands"]["led"]["pin_red"] == 1
    assert fraud_hw["hardware_commands"]["buzzer"]["mode"] == "ALERT"

