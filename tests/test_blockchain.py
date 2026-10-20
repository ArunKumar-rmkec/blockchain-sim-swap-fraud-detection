import pytest
from pathlib import Path
from fastapi import HTTPException
from web3 import Web3

from backend.blockchain_client import (
    BlockchainClient,
    CONTRACT_ABI,
    DEFAULT_RPC_URL,
    load_contract_artifact,
)
from blockchain.compile import compile_contract, ARTIFACT_PATH
from blockchain.deploy import deploy_contract
from backend.main import (
    blockchain_status,
    blockchain_records,
    blockchain_record,
    blockchain_verify,
    BlockchainVerifyRequest,
    evaluate,
    hardware_evaluate,
    EvaluationRequest,
    TerminalEvaluationRequest,
)
from backend import ledger


# ==============================================================================
# SECTION A: STATIC SCHEMA & COMPILER TESTS (No EVM Required)
# ==============================================================================

def test_solidity_contract_file_exists():
    contract_path = Path(__file__).resolve().parent.parent / "blockchain" / "contracts" / "SimSwapAudit.sol"
    assert contract_path.exists()
    assert contract_path.stat().st_size > 500
    content = contract_path.read_text(encoding="utf-8")
    assert "contract SimSwapAudit" in content
    assert "recordAudit" in content
    assert "AuditRecorded" in content


def test_contract_abi_structure():
    func_names = [x["name"] for x in CONTRACT_ABI if x.get("type") == "function"]
    assert "recordAudit" in func_names
    assert "getRecord" in func_names
    assert "getRecordCount" in func_names
    assert "verifyRecord" in func_names


def test_solidity_compilation_and_artifact():
    artifact = compile_contract()
    assert ARTIFACT_PATH.exists()
    assert "abi" in artifact
    assert "bytecode" in artifact
    assert len(artifact["bytecode"]) > 1000
    assert artifact["bytecode"].startswith("0x")


# ==============================================================================
# SECTION B: OFFLINE EMULATION & EDGE-CASE FALLBACK TESTS (Disconnected RPC)
# ==============================================================================

def test_offline_emulation_record_audit(tmp_path):
    # Guaranteed disconnected RPC URL
    client = BlockchainClient(rpc_url="http://127.0.0.1:59999", state_path=tmp_path / "emulation.json")
    client.reset_chain()

    assert client._is_live is False
    res = client.record_audit(
        request_id="REQ_OFFLINE_01",
        decision="LOW RISK",
        risk_percent=0.3,
        explanation_hash="a" * 64,
        agent_uid="A1B2C3D4",
    )
    assert res["status"] == "SIMULATED_OFFLINE"
    assert res["mode"] == "offline_emulation"
    assert res["tx_hash"].startswith("0x")
    assert len(res["tx_hash"]) == 66
    assert client.get_record_count() == 1


def test_offline_emulation_tamper_detection(tmp_path):
    client = BlockchainClient(rpc_url="http://127.0.0.1:59999", state_path=tmp_path / "emulation.json")
    client.reset_chain()

    original_hash = "f" * 64
    rec = client.record_audit("REQ_OFFLINE_02", "HIGH RISK", 96.7, original_hash, "A1B2C3D4")
    idx = rec["record_index"]

    assert client.verify_record(idx, original_hash) is True
    assert client.verify_record(idx, "e" * 64) is False
    assert client.verify_record(999, original_hash) is False


def test_disconnected_rpc_falls_back_to_emulation(tmp_path):
    client = BlockchainClient(rpc_url="http://127.0.0.1:59999", state_path=tmp_path / "emulation.json")
    status = client.get_status()
    assert status["is_live_node"] is False
    assert status["mode"] == "offline_emulation"
    assert "Offline" in status["status_label"]
    assert status["connection_error"] == "RPC_DISCONNECTED"


def test_invalid_contract_address_falls_back_to_emulation(tmp_path):
    client = BlockchainClient(
        rpc_url=DEFAULT_RPC_URL,
        contract_address="NOT_AN_ETHEREUM_ADDRESS",
        state_path=tmp_path / "emulation.json",
    )
    status = client.get_status()
    assert status["is_live_node"] is False
    assert status["mode"] == "offline_emulation"
    assert "INVALID_CONTRACT_ADDRESS" in str(status["connection_error"])


def test_contract_without_bytecode_rejected_from_live_mode(tmp_path):
    # If a live EVM is reachable, pointing contract_address to an EOA (account[1])
    # has 0 bytecode stored, so live mode MUST NOT activate.
    w3 = Web3(Web3.HTTPProvider(DEFAULT_RPC_URL))
    if w3.is_connected() and len(w3.eth.accounts) > 1:
        eoa_address = w3.eth.accounts[1]
        client = BlockchainClient(
            rpc_url=DEFAULT_RPC_URL,
            contract_address=eoa_address,
            state_path=tmp_path / "emulation.json",
        )
        status = client.get_status()
        assert status["is_live_node"] is False
        assert status["mode"] == "offline_emulation"
        assert "NO_DEPLOYED_BYTECODE_AT_ADDRESS" in str(status["connection_error"])


# ==============================================================================
# SECTION C: LIVE LOCAL EVM INTEGRATION TESTS (Requires Local EVM Node)
# ==============================================================================

@pytest.fixture(scope="module")
def live_w3():
    w3 = Web3(Web3.HTTPProvider(DEFAULT_RPC_URL))
    if not w3.is_connected():
        pytest.skip("No live local EVM node running on http://127.0.0.1:8545.")
    return w3


@pytest.fixture(scope="module")
def deployed_contract_info(live_w3):
    deployment = deploy_contract(DEFAULT_RPC_URL)
    return deployment


@pytest.mark.evm
def test_live_evm_deployment_verification(live_w3, deployed_contract_info):
    addr = deployed_contract_info["contract_address"]
    tx_hash = deployed_contract_info["deployment_tx_hash"]
    
    assert deployed_contract_info["status"] == "CONFIRMED_ON_CHAIN"
    assert addr.startswith("0x")
    assert len(addr) == 42
    
    # Verify bytecode is on-chain
    code = live_w3.eth.get_code(addr)
    assert len(code) > 100

    # Verify transaction receipt on node
    receipt = live_w3.eth.get_transaction_receipt(tx_hash)
    assert receipt.status == 1
    assert receipt.contractAddress.lower() == addr.lower()
    assert receipt.gasUsed > 100000


@pytest.mark.evm
def test_live_evm_record_audit_real_receipt(live_w3, deployed_contract_info):
    client = BlockchainClient(
        rpc_url=DEFAULT_RPC_URL,
        contract_address=deployed_contract_info["contract_address"],
    )
    assert client.get_status()["is_live_node"] is True

    res = client.record_audit(
        request_id="REQ_EVM_TEST_01",
        decision="LOW RISK",
        risk_percent=0.3,
        explanation_hash="11" * 32,
        agent_uid="A1B2C3D4",
    )
    assert res["status"] == "CONFIRMED_ON_CHAIN"
    assert res["mode"] == "live_evm"
    assert res["tx_hash"].startswith("0x")
    assert res["block_number"] > 0
    assert res["gas_used"] > 21000

    # Confirm receipt actually exists in the EVM node
    receipt = live_w3.eth.get_transaction_receipt(res["tx_hash"])
    assert receipt.status == 1
    assert receipt.blockNumber == res["block_number"]
    assert receipt.gasUsed == res["gas_used"]


@pytest.mark.evm
def test_live_evm_record_retrieval_matches(live_w3, deployed_contract_info):
    client = BlockchainClient(
        rpc_url=DEFAULT_RPC_URL,
        contract_address=deployed_contract_info["contract_address"],
    )
    target_hash = "22" * 32
    res = client.record_audit(
        request_id="REQ_EVM_TEST_02",
        decision="HIGH RISK",
        risk_percent=98.5,
        explanation_hash=target_hash,
        agent_uid="DEMO1234",
    )
    rec = client.get_record(res["record_index"])
    assert rec["request_id"] == "REQ_EVM_TEST_02"
    assert rec["decision"] == "HIGH RISK"
    assert rec["risk_percent"] == 98.5
    assert rec["explanation_hash"].lower() == ("0x" + target_hash).lower()
    assert rec["status"] == "CONFIRMED_ON_CHAIN"


@pytest.mark.evm
def test_live_evm_digest_verification_positive_and_negative(deployed_contract_info):
    client = BlockchainClient(
        rpc_url=DEFAULT_RPC_URL,
        contract_address=deployed_contract_info["contract_address"],
    )
    target_hash = "33" * 32
    res = client.record_audit("REQ_EVM_TEST_03", "REVIEW", 55.0, target_hash, "A1B2C3D4")
    idx = res["record_index"]

    # Positive match
    assert client.verify_record(idx, target_hash) is True
    # Tampered / different hash
    assert client.verify_record(idx, "99" * 32) is False


@pytest.mark.evm
def test_live_evm_reverts_on_invalid_basis_points(live_w3, deployed_contract_info):
    # SimSwapAudit requires: require(riskScoreBp <= 10000)
    # Calling raw function with riskScoreBp = 15000 must revert on-chain
    abi, _ = load_contract_artifact()
    contract = live_w3.eth.contract(address=deployed_contract_info["contract_address"], abi=abi)
    account = live_w3.eth.accounts[0]

    with pytest.raises(Exception):
        contract.functions.recordAudit(
            "REQ_REVERT_BP",
            "HIGH RISK",
            15000,  # Exceeds 10,000 bps
            bytes.fromhex("44" * 32),
            "A1B2C3D4",
        ).transact({"from": account})


@pytest.mark.evm
def test_live_evm_reverts_on_empty_request_id(live_w3, deployed_contract_info):
    # SimSwapAudit requires: require(bytes(requestId).length > 0)
    abi, _ = load_contract_artifact()
    contract = live_w3.eth.contract(address=deployed_contract_info["contract_address"], abi=abi)
    account = live_w3.eth.accounts[0]

    with pytest.raises(Exception):
        contract.functions.recordAudit(
            "",  # Empty request ID
            "LOW RISK",
            500,
            bytes.fromhex("55" * 32),
            "A1B2C3D4",
        ).transact({"from": account})


@pytest.mark.evm
def test_live_evm_evaluate_anchors_real_tx(tmp_path, monkeypatch):
    import backend.main as main_mod
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")

    payload = EvaluationRequest(request_id="REQ00001", agent_uid="A1B2C3D4")
    res = evaluate(payload)

    assert "blockchain" in res
    bc = res["blockchain"]
    assert bc["status"] == "CONFIRMED_ON_CHAIN"
    assert bc["mode"] == "live_evm"
    assert bc["tx_hash"].startswith("0x")
    assert bc["block_number"] > 0
    assert bc["gas_used"] > 21000


@pytest.mark.evm
def test_live_evm_hardware_evaluate_anchors_real_tx(tmp_path, monkeypatch):
    import backend.main as main_mod
    monkeypatch.setattr(ledger, "LEDGER_PATH", tmp_path / "ledger.jsonl")

    payload = TerminalEvaluationRequest(
        request_id="REQ00701",
        agent_uid="A1B2C3D4",
        terminal_id="ESP32_TERM_01",
    )
    res = hardware_evaluate(payload)

    assert "blockchain" in res
    bc = res["blockchain"]
    assert bc["status"] == "CONFIRMED_ON_CHAIN"
    assert bc["mode"] == "live_evm"
    assert "hardware" in res


@pytest.mark.evm
def test_live_evm_api_endpoints_status_and_records():
    status = blockchain_status()
    assert status["is_live_node"] is True
    assert status["mode"] == "live_evm"
    assert "Live EVM" in status["status_label"]
    assert status["has_deployed_bytecode"] is True

    records = blockchain_records()
    assert len(records) > 0
    r0 = records[0]
    assert r0["status"] == "CONFIRMED_ON_CHAIN"
    assert r0["tx_hash"].startswith("0x")

    # Test verify endpoint
    req = BlockchainVerifyRequest(record_index=0, expected_hash=r0["explanation_hash"])
    v_res = blockchain_verify(req)
    assert v_res["verified"] is True
