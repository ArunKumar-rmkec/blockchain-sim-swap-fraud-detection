import json
import requests
from web3 import Web3
from backend.blockchain_client import load_contract_artifact

def run():
    # 1. Evaluate synthetic SIM swap request
    payload = {
        "request_id": "REQ00701",
        "agent_uid": "A1B2C3D4",
        "terminal_id": "ESP32_TERM_01"
    }
    resp = requests.post("http://127.0.0.1:8000/hardware/terminal-evaluate", json=payload).json()
    print("=================================================================")
    print("STEP 4: EVALUATION RESPONSE (FASTAPI + XGBOOST + RULES)")
    print("=================================================================")
    print(f"Request ID:    {resp['request_id']}")
    print(f"Decision:      {resp['decision']}")
    print(f"Risk Score:    {resp['risk_percent']}%")
    print(f"Rule Reasons:")
    for r in resp["reasons"]:
        print(f"  - {r}")

    bc = resp["blockchain"]
    print("\n=================================================================")
    print("STEP 5A: ACTUAL TRANSACTION RECEIPT FROM LOCAL EVM NODE")
    print("=================================================================")
    print(f"Execution Mode:       {bc['mode']}")
    print(f"Status:               {bc['status']}")
    print(f"Smart Contract Addr:  {bc['contract_address']}")
    print(f"Transaction Hash:     {bc['tx_hash']}")
    print(f"Block Number:         {bc['block_number']}")
    print(f"Gas Consumed:         {bc['gas_used']:,} gas")
    print(f"Explanation Digest:   {bc['explanation_hash']}")
    print(f"Record Index:         {bc['record_index']}")

    # Raw receipt from EVM node
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    raw_receipt = w3.eth.get_transaction_receipt(bc["tx_hash"])
    print("\n--- RAW JSON-RPC RECEIPT FIELDS ---")
    print(f"blockHash:            {raw_receipt.blockHash.hex()}")
    print(f"blockNumber:          {raw_receipt.blockNumber}")
    print(f"transactionIndex:     {raw_receipt.transactionIndex}")
    print(f"from (Validator):     {raw_receipt['from']}")
    print(f"to (Contract):        {raw_receipt['to']}")
    print(f"gasUsed:              {raw_receipt.gasUsed}")
    print(f"cumulativeGasUsed:    {raw_receipt.cumulativeGasUsed}")
    print(f"status (1=Mined OK):  {raw_receipt.status}")
    print(f"logsBloom:            {raw_receipt.logsBloom.hex()[:40]}...")

    # Step 5B: Retrieve stored audit record from smart contract storage
    abi, _ = load_contract_artifact()
    contract = w3.eth.contract(address=bc["contract_address"], abi=abi)
    stored = contract.functions.getRecord(bc["record_index"]).call()

    print("\n=================================================================")
    print("STEP 5B: RETRIEVED RECORD FROM SIMSWAPAUDIT SMART CONTRACT")
    print("=================================================================")
    print(f"stored.requestId:        {stored[0]}")
    print(f"stored.decision:         {stored[1]}")
    print(f"stored.riskScoreBp:      {stored[2]} ({stored[2] / 100.0}%)")
    print(f"stored.explanationHash:  0x{stored[3].hex()}")
    print(f"stored.agentUid:         {stored[4]}")
    print(f"stored.timestamp:        {stored[5]}")
    print(f"stored.recordedBy:       {stored[6]}")

    # Step 6: Verify explanation digest
    print("\n=================================================================")
    print("STEP 6: CRYPTOGRAPHIC EXPLANATION DIGEST VERIFICATION")
    print("=================================================================")
    # Positive check
    verify_resp = requests.post(
        "http://127.0.0.1:8000/blockchain/verify",
        json={"record_index": bc["record_index"], "expected_hash": bc["explanation_hash"]}
    ).json()
    print(f"Positive Check (Authentic Hash):  Verified = {verify_resp['verified']}")

    # Negative check (tampered hash)
    tampered_hash = "0x" + "9" * 64
    tampered_resp = requests.post(
        "http://127.0.0.1:8000/blockchain/verify",
        json={"record_index": bc["record_index"], "expected_hash": tampered_hash}
    ).json()
    print(f"Negative Check (Tampered Hash):   Verified = {tampered_resp['verified']} (Rejected!)")

if __name__ == "__main__":
    run()
