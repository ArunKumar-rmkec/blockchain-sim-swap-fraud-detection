from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from backend.risk_engine import load_data, evaluate_record, train_model, FEATURES
from backend.ledger import append_event, read_events, verify_chain, explanation_hash
from backend.hardware_bridge import (
    format_hardware_response,
    get_terminal_state,
    reset_terminal_state,
    list_serial_ports,
)
from backend.blockchain_client import blockchain_client

app = FastAPI(
    title="SIM Swap Fraud Detection API",
    version="0.2.0",
    description="Blockchain-Secured SIM Swap Fraud Detection Prototype with Solidity Smart Contract & Hardware Bridge.",
)

class EvaluationRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=40)
    agent_uid: str = Field(min_length=1, max_length=40)

class TerminalEvaluationRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=40)
    agent_uid: str = Field(min_length=1, max_length=40)
    terminal_id: str = Field(default="ESP32_TERM_01", max_length=40)

class BlockchainVerifyRequest(BaseModel):
    record_index: int
    expected_hash: str

@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic-demo", "smart_contract": "SimSwapAudit.sol"}

@app.get("/requests")
def requests():
    df = load_data()
    return df[["request_id", "subscriber_ref", *FEATURES, "fraud_label"]].head(100).to_dict("records")

@app.get("/metrics")
def metrics():
    return train_model()[1]

@app.post("/evaluate")
def evaluate(payload: EvaluationRequest):
    if payload.agent_uid not in {"A1B2C3D4", "11223344", "DEMO1234"}:
        raise HTTPException(status_code=403, detail="Unknown demo agent card; request denied.")
    df = load_data()
    match = df[df["request_id"].str.upper() == payload.request_id.strip().upper()]
    if match.empty:
        raise HTTPException(status_code=404, detail="Request ID not found in synthetic dataset.")
    record = match.iloc[0].to_dict()
    result = evaluate_record(record)
    exp_hash = explanation_hash(result["reasons"])
    event = append_event({
        "request_id": record["request_id"],
        "decision": result["decision"],
        "risk_score": result["risk_score"],
        "explanation_hash": exp_hash,
        "agent_uid": payload.agent_uid,
        "audit_type": "local_hash_chain_demo",
    })
    # Anchor to Solidity Smart Contract
    bc_receipt = blockchain_client.record_audit(
        request_id=record["request_id"],
        decision=result["decision"],
        risk_percent=result["risk_percent"],
        explanation_hash=exp_hash,
        agent_uid=payload.agent_uid,
    )
    return {
        "request_id": record["request_id"],
        **result,
        "audit": event,
        "blockchain": bc_receipt,
    }

@app.get("/audit")
def audit():
    events = read_events()
    valid, message = verify_chain()
    return {"valid": valid, "message": message, "count": len(events), "records": events}

@app.post("/hardware/terminal-evaluate")
def hardware_evaluate(payload: TerminalEvaluationRequest):
    """
    Evaluates SIM swap requests initiated by an ESP32 hardware terminal,
    anchors the record on the blockchain smart contract, and returns translated
    signals for LCD, LEDs, and Buzzer.
    """
    if payload.agent_uid not in {"A1B2C3D4", "11223344", "DEMO1234"}:
        hw_resp = format_hardware_response(
            decision="DENIED",
            risk_percent=100.0,
            request_id=payload.request_id,
            error_message="INVALID CARD UID",
            status_override="AUTH_FAILED",
        )
        raise HTTPException(
            status_code=403,
            detail={"message": "Unknown demo agent card; request denied.", "hardware": hw_resp}
        )

    df = load_data()
    match = df[df["request_id"].str.upper() == payload.request_id.strip().upper()]
    if match.empty:
        hw_resp = format_hardware_response(
            decision="NOT FOUND",
            risk_percent=0.0,
            request_id=payload.request_id,
            error_message="REQ NOT FOUND",
            status_override="NOT_FOUND",
        )
        raise HTTPException(
            status_code=404,
            detail={"message": "Request ID not found in synthetic dataset.", "hardware": hw_resp}
        )

    record = match.iloc[0].to_dict()
    result = evaluate_record(record)
    exp_hash = explanation_hash(result["reasons"])
    
    # 1. Local hash chain
    event = append_event({
        "request_id": record["request_id"],
        "decision": result["decision"],
        "risk_score": result["risk_score"],
        "explanation_hash": exp_hash,
        "agent_uid": payload.agent_uid,
        "audit_type": "esp32_terminal_hardware",
    })

    # 2. Solidity Smart Contract on-chain anchoring
    bc_receipt = blockchain_client.record_audit(
        request_id=record["request_id"],
        decision=result["decision"],
        risk_percent=result["risk_percent"],
        explanation_hash=exp_hash,
        agent_uid=payload.agent_uid,
    )

    # 3. ESP32 hardware signal formatting
    hw_resp = format_hardware_response(
        decision=result["decision"],
        risk_percent=result["risk_percent"],
        request_id=record["request_id"],
        audit_hash=event.get("record_hash", ""),
    )

    return {
        "request_id": record["request_id"],
        "terminal_id": payload.terminal_id,
        **result,
        "audit": event,
        "blockchain": bc_receipt,
        "hardware": hw_resp,
    }

@app.get("/hardware/terminal-state")
def terminal_state():
    """Returns the current state of the virtual/physical ESP32 terminal (LCD, LEDs, Buzzer)."""
    return get_terminal_state()

@app.post("/hardware/terminal-reset")
def terminal_reset():
    """Resets the virtual/physical ESP32 terminal to idle standby."""
    return reset_terminal_state()

@app.get("/hardware/ports")
def hardware_ports():
    """Scans and lists active physical and virtual COM ports on Windows."""
    return list_serial_ports()

# --- Blockchain Smart Contract Endpoints ---

@app.get("/blockchain/status")
def blockchain_status():
    """Returns connection, network name, contract address, block height, and record count."""
    return blockchain_client.get_status()

@app.get("/blockchain/records")
def blockchain_records():
    """Returns all immutable audit records recorded on the blockchain smart contract."""
    return blockchain_client.get_all_records()

@app.get("/blockchain/record/{index}")
def blockchain_record(index: int):
    """Retrieves a single smart contract audit record by index."""
    rec = blockchain_client.get_record(index)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Blockchain record at index {index} not found.")
    return rec

@app.post("/blockchain/verify")
def blockchain_verify(payload: BlockchainVerifyRequest):
    """Verifies that the on-chain explanation hash matches an expected hash."""
    is_valid = blockchain_client.verify_record(payload.record_index, payload.expected_hash)
    rec = blockchain_client.get_record(payload.record_index)
    return {"verified": is_valid, "record_index": payload.record_index, "record": rec}
