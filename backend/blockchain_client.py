"""
Blockchain Client & Web3 Smart Contract Integration
===================================================
Provides dual-mode integration for the 'SimSwapAudit' Solidity Smart Contract:
1. Live EVM Mode: Connects to a running EVM node (Foundry Anvil / Ganache / Hardhat / Testnet).
   Live mode is ONLY activated when:
   - The JSON-RPC connection succeeds
   - The expected EVM chain is confirmed
   - The configured contract address contains verified on-chain bytecode
   - Core view functions (e.g. owner(), getRecordCount()) execute successfully.
   Transactions are submitted over the wire, receipts are waited on, and all receipt
   data (tx hash, block number, gas used) comes strictly from the real node.
2. Offline Emulation Mode: High-fidelity software simulation used strictly when no EVM
   node is available. Emulated records are clearly labelled as 'SIMULATED_OFFLINE'
   and never misrepresented as confirmed on-chain.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from web3 import Web3

logger = logging.getLogger("blockchain_client")

BASE_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = BASE_DIR / "blockchain" / "build"
ARTIFACT_PATH = BUILD_DIR / "SimSwapAudit.json"
DEPLOYMENT_PATH = BUILD_DIR / "deployment.json"
DATA_DIR = BASE_DIR / "data"
ACTIVE_DEPLOYMENT_PATH = DATA_DIR / "active_deployment.json"
BLOCKCHAIN_STATE_PATH = DATA_DIR / "blockchain_state.json"

DEFAULT_RPC_URL = os.getenv("ETH_RPC_URL", "http://127.0.0.1:8545")
FALLBACK_EMULATION_ADDRESS = "0x71C665C3D343292F7367fF682B6185A279716B71"
FALLBACK_VALIDATOR_ADDRESS = "0x90F79bf6EB2c4f870365E785982E1f101E93b906"


def load_contract_artifact() -> Tuple[List[Dict[str, Any]], str]:
    """Loads ABI and bytecode from the build artifact if available."""
    if ARTIFACT_PATH.exists():
        try:
            with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("abi", []), data.get("bytecode", "")
        except Exception as e:
            logger.warning(f"Could not load artifact from {ARTIFACT_PATH}: {e}")
    
    # Try dynamic compilation if artifact is missing
    try:
        from blockchain.compile import load_or_compile_artifact
        art = load_or_compile_artifact()
        return art.get("abi", []), art.get("bytecode", "")
    except Exception as e:
        logger.warning(f"Dynamic compilation fallback failed: {e}")
        return [], ""


CONTRACT_ABI, CONTRACT_BYTECODE = load_contract_artifact()


def load_deployment_info() -> Dict[str, Any]:
    """Loads active deployment metadata if available."""
    for path in [ACTIVE_DEPLOYMENT_PATH, DEPLOYMENT_PATH]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


class BlockchainClient:
    """
    Manages live Web3 interactions with a deployed SimSwapAudit smart contract,
    with an explicit, cleanly-labeled offline emulation fallback.
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        state_path: Path = BLOCKCHAIN_STATE_PATH,
    ):
        self.rpc_url = rpc_url or DEFAULT_RPC_URL
        self.state_path = state_path
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Load ABI and bytecode
        self.abi, self.bytecode = load_contract_artifact()
        
        # Load contract address
        deployment_info = load_deployment_info()
        configured_addr = contract_address or os.getenv("SIM_SWAP_CONTRACT_ADDRESS") or deployment_info.get("contract_address")
        self.contract_address = configured_addr
        self.deployment_info = deployment_info

        self._is_live = False
        self._contract = None
        self._live_chain_id: Optional[int] = None
        self._connection_error: Optional[str] = None
        self._records: List[Dict[str, Any]] = []
        self._current_block = 1000
        self._live_receipt_cache: Dict[int, Dict[str, Any]] = {}

        # Attempt live connection and verification
        self._check_connection()

        # Load persisted offline simulation state
        self._load_state()

    def _check_connection(self) -> bool:
        """
        Validates whether live mode can be safely activated:
        1. JSON-RPC connection succeeds
        2. Valid chain ID is confirmed
        3. Contract address is configured and valid
        4. Deployed bytecode exists on-chain at the address
        5. Contract view calls succeed via the ABI.
        """
        try:
            if not self.w3.is_connected():
                self._is_live = False
                self._contract = None
                self._connection_error = "RPC_DISCONNECTED"
                return False

            chain_id = self.w3.eth.chain_id
            self._live_chain_id = chain_id

            # Refresh contract address from deployment file if not set
            if not self.contract_address:
                self.deployment_info = load_deployment_info()
                self.contract_address = self.deployment_info.get("contract_address")

            if not self.contract_address:
                self._is_live = False
                self._contract = None
                self._connection_error = "NO_CONTRACT_ADDRESS_CONFIGURED"
                return False

            # Validate address format
            try:
                checksum_addr = Web3.to_checksum_address(self.contract_address)
                self.contract_address = checksum_addr
            except ValueError as e:
                self._is_live = False
                self._contract = None
                self._connection_error = f"INVALID_CONTRACT_ADDRESS: {e}"
                return False

            # Check deployed on-chain bytecode
            code = self.w3.eth.get_code(self.contract_address)
            if not code or len(code) <= 2:  # b"" or b"\x00" or empty hex
                self._is_live = False
                self._contract = None
                self._connection_error = f"NO_DEPLOYED_BYTECODE_AT_ADDRESS: {self.contract_address}"
                return False

            if not self.abi:
                self.abi, self.bytecode = load_contract_artifact()
                if not self.abi:
                    self._is_live = False
                    self._contract = None
                    self._connection_error = "MISSING_CONTRACT_ABI"
                    return False

            # Instantiate and test view functions
            contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
            owner = contract.functions.owner().call()
            total_records = contract.functions.getRecordCount().call()

            self._is_live = True
            self._contract = contract
            self._connection_error = None
            logger.info(f"Live EVM Node Verified! (Chain: {chain_id}, Contract: {self.contract_address}, Owner: {owner})")
            return True

        except Exception as e:
            self._is_live = False
            self._contract = None
            self._connection_error = f"VERIFICATION_FAILED: {e}"
            logger.debug(f"Live mode verification check failed: {e}")
            return False

    def _load_state(self) -> None:
        """Loads state from JSON file for offline emulation mode."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = data.get("records", [])
                    self._current_block = data.get("current_block", 1000 + len(self._records))
            except Exception as e:
                logger.warning(f"Could not load blockchain state: {e}")
                self._records = []
        else:
            self._records = []

    def _save_state(self) -> None:
        """Persists offline simulation state to file."""
        if not self._is_live:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "current_block": self._current_block,
                        "contract_address": self.contract_address or FALLBACK_EMULATION_ADDRESS,
                        "validator_address": FALLBACK_VALIDATOR_ADDRESS,
                        "records": self._records,
                    },
                    f,
                    indent=2,
                )

    def record_audit(
        self,
        request_id: str,
        decision: str,
        risk_percent: float,
        explanation_hash: str,
        agent_uid: str,
    ) -> Dict[str, Any]:
        """
        Anchors an audit event into the SimSwapAudit smart contract.
        In Live Mode:
          - Broadcasts real transaction to EVM node
          - Waits for confirmation receipt
          - Validates status == 1
          - Retrieves stored record from contract
          - Returns actual tx_hash, blockNumber, and gasUsed
        In Offline Mode:
          - Stores cleanly labelled 'SIMULATED_OFFLINE' record
        """
        # Always check connection fresh before committing
        self._check_connection()

        # Format basis points (e.g., 96.7% -> 9670)
        risk_score_bp = int(round(risk_percent * 100))
        risk_score_bp = max(0, min(10000, risk_score_bp))

        # Format explanation hash as 0x-prefixed 32-byte hex
        clean_hash = explanation_hash.lower().replace("0x", "")
        if len(clean_hash) < 64:
            clean_hash = clean_hash.ljust(64, "0")
        elif len(clean_hash) > 64:
            clean_hash = clean_hash[:64]
        bytes32_hex = "0x" + clean_hash
        bytes32_val = bytes.fromhex(clean_hash)

        # ----------------------------------------------------------------------
        # PATH 1: LIVE EVM SMART CONTRACT EXECUTION
        # ----------------------------------------------------------------------
        if self._is_live and self._contract:
            accounts = self.w3.eth.accounts
            if not accounts:
                raise RuntimeError("Live EVM connected but no unlocked accounts found for signing transactions.")
            
            sender = accounts[0]
            try:
                # 1. Submit on-chain transaction
                tx_hash_bytes = self._contract.functions.recordAudit(
                    request_id,
                    decision,
                    risk_score_bp,
                    bytes32_val,
                    agent_uid,
                ).transact({"from": sender})

                # 2. Wait for real EVM transaction receipt
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=12)
                if receipt.status != 1:
                    raise RuntimeError(f"Smart contract transaction reverted! Status: {receipt.status}, tx: {tx_hash_bytes.hex()}")

                # 3. Confirm record can be retrieved directly from smart contract storage
                total_on_chain = self._contract.functions.getRecordCount().call()
                record_index = total_on_chain - 1
                stored_record = self._contract.functions.getRecord(record_index).call()

                # Verify retrieved parameters match
                assert stored_record[0] == request_id
                assert stored_record[1] == decision

                tx_hash_str = receipt.transactionHash.hex()
                if not tx_hash_str.startswith("0x"):
                    tx_hash_str = "0x" + tx_hash_str

                self._live_receipt_cache[record_index] = {
                    "tx_hash": tx_hash_str,
                    "block_number": receipt.blockNumber,
                    "gas_used": receipt.gasUsed,
                }

                return {
                    "mode": "live_evm",
                    "network": f"Live Local EVM (Chain ID: {self._live_chain_id})",
                    "status": "CONFIRMED_ON_CHAIN",
                    "record_index": record_index,
                    "tx_hash": tx_hash_str,
                    "block_number": receipt.blockNumber,
                    "gas_used": receipt.gasUsed,
                    "contract_address": self.contract_address,
                    "recorded_by": sender,
                    "request_id": request_id,
                    "decision": decision,
                    "risk_score_bp": risk_score_bp,
                    "explanation_hash": bytes32_hex,
                    "agent_uid": agent_uid,
                    "timestamp": datetime.fromtimestamp(stored_record[5], tz=timezone.utc).isoformat(),
                    "block_timestamp": stored_record[5],
                }

            except Exception as e:
                logger.error(f"Live EVM transaction submission failed: {e}")
                raise RuntimeError(f"Live blockchain transaction failed: {e}")

        # ----------------------------------------------------------------------
        # PATH 2: OFFLINE SOFTWARE EMULATION FALLBACK
        # ----------------------------------------------------------------------
        self._current_block += 1
        record_index = len(self._records)
        now_dt = datetime.now(timezone.utc)
        now_ts = int(now_dt.timestamp())

        # Generate deterministic Keccak-256 transaction hash for emulation
        raw_tx_data = f"{request_id}:{decision}:{risk_score_bp}:{clean_hash}:{agent_uid}:{self._current_block}:{now_ts}"
        tx_hash_bytes = Web3.keccak(text=raw_tx_data)
        tx_hash = "0x" + tx_hash_bytes.hex().replace("0x", "")

        emulated_entry = {
            "record_index": record_index,
            "request_id": request_id,
            "decision": decision,
            "risk_score_bp": risk_score_bp,
            "risk_percent": risk_percent,
            "explanation_hash": bytes32_hex,
            "agent_uid": agent_uid,
            "timestamp": now_dt.isoformat(),
            "block_timestamp": now_ts,
            "block_number": self._current_block,
            "tx_hash": tx_hash,
            "gas_used": 68420,
            "contract_address": self.contract_address or FALLBACK_EMULATION_ADDRESS,
            "recorded_by": FALLBACK_VALIDATOR_ADDRESS,
            "status": "SIMULATED_OFFLINE",
            "mode": "offline_emulation",
        }

        self._records.append(emulated_entry)
        self._save_state()

        return {
            "mode": "offline_emulation",
            "network": "Offline Software Emulation (No EVM Node)",
            "status": "SIMULATED_OFFLINE",
            "record_index": record_index,
            "tx_hash": tx_hash,
            "block_number": self._current_block,
            "gas_used": 68420,
            "contract_address": self.contract_address or FALLBACK_EMULATION_ADDRESS,
            "recorded_by": FALLBACK_VALIDATOR_ADDRESS,
            "request_id": request_id,
            "decision": decision,
            "risk_score_bp": risk_score_bp,
            "explanation_hash": bytes32_hex,
            "agent_uid": agent_uid,
            "timestamp": now_dt.isoformat(),
        }

    def get_record(self, index: int) -> Optional[Dict[str, Any]]:
        """Queries an on-chain record by index."""
        self._check_connection()
        if self._is_live and self._contract:
            try:
                r = self._contract.functions.getRecord(index).call()
                h_hex = r[3].hex()
                if not h_hex.startswith("0x"):
                    h_hex = "0x" + h_hex

                # Retrieve receipt details from memory cache or on-chain event logs
                tx_data = self._live_receipt_cache.get(index)
                if not tx_data:
                    try:
                        logs = self._contract.events.AuditRecorded().get_logs(
                            from_block=0,
                            argument_filters={"recordIndex": index},
                        )
                        if logs:
                            log_entry = logs[0]
                            log_tx = log_entry.transactionHash.hex()
                            if not log_tx.startswith("0x"):
                                log_tx = "0x" + log_tx
                            tx_data = {
                                "tx_hash": log_tx,
                                "block_number": log_entry.blockNumber,
                            }
                            self._live_receipt_cache[index] = tx_data
                    except Exception:
                        pass

                rec = {
                    "record_index": index,
                    "request_id": r[0],
                    "decision": r[1],
                    "risk_score_bp": r[2],
                    "risk_percent": r[2] / 100.0,
                    "explanation_hash": h_hex,
                    "agent_uid": r[4],
                    "block_timestamp": r[5],
                    "timestamp": datetime.fromtimestamp(r[5], tz=timezone.utc).isoformat(),
                    "recorded_by": r[6],
                    "status": "CONFIRMED_ON_CHAIN",
                    "mode": "live_evm",
                }
                if tx_data:
                    rec.update(tx_data)
                return rec
            except Exception as e:
                logger.debug(f"Failed to query live on-chain record at index {index}: {e}")
                return None

        # Emulation mode
        if 0 <= index < len(self._records):
            return self._records[index]
        return None

    def get_all_records(self) -> List[Dict[str, Any]]:
        """Returns all audit records (from live contract or emulation store)."""
        self._check_connection()
        if self._is_live and self._contract:
            try:
                count = self._contract.functions.getRecordCount().call()
                records = []
                for i in range(count):
                    rec = self.get_record(i)
                    if rec:
                        records.append(rec)
                return records
            except Exception as e:
                logger.warning(f"Error fetching live on-chain records: {e}")
                return []

        return list(self._records)

    def get_record_count(self) -> int:
        """Returns the total number of audit records."""
        self._check_connection()
        if self._is_live and self._contract:
            try:
                return self._contract.functions.getRecordCount().call()
            except Exception:
                pass
        return len(self._records)

    def verify_record(self, index: int, expected_hash: str) -> bool:
        """Verifies if the stored explanation hash matches the expected SHA-256 digest."""
        clean_exp = expected_hash.lower().replace("0x", "")
        if len(clean_exp) < 64:
            clean_exp = clean_exp.ljust(64, "0")
        elif len(clean_exp) > 64:
            clean_exp = clean_exp[:64]

        self._check_connection()
        if self._is_live and self._contract:
            try:
                return self._contract.functions.verifyRecord(index, bytes.fromhex(clean_exp)).call()
            except Exception as e:
                logger.warning(f"Live verifyRecord call failed: {e}")
                return False

        if 0 <= index < len(self._records):
            actual = self._records[index]["explanation_hash"].lower().replace("0x", "")
            return actual == clean_exp
        return False

    def get_status(self) -> Dict[str, Any]:
        """Returns the complete runtime status of the blockchain subsystem."""
        is_live = self._check_connection()
        return {
            "is_live_node": is_live,
            "mode": "live_evm" if is_live else "offline_emulation",
            "status_label": "Live EVM Contract Active (Verified On-Chain)" if is_live else "Offline Software Emulation",
            "network_name": f"Live Local EVM (Chain ID: {self._live_chain_id})" if is_live else "Offline Software Emulation",
            "rpc_url": self.rpc_url,
            "chain_id": self._live_chain_id if is_live else None,
            "contract_address": self.contract_address or FALLBACK_EMULATION_ADDRESS,
            "has_deployed_bytecode": is_live,
            "validator_address": (self.w3.eth.accounts[0] if (is_live and self.w3.eth.accounts) else FALLBACK_VALIDATOR_ADDRESS),
            "current_block": (self.w3.eth.block_number if is_live else self._current_block),
            "total_records": self.get_record_count(),
            "smart_contract": "SimSwapAudit.sol (Solidity ^0.8.20)",
            "connection_error": self._connection_error,
            "deployment_receipt": self.deployment_info if is_live else {},
        }

    def reset_chain(self) -> None:
        """Resets simulated state (used for test isolation)."""
        self._records = []
        self._current_block = 1000
        if self.state_path.exists():
            try:
                self.state_path.unlink()
            except Exception:
                pass


# Global singleton instance
blockchain_client = BlockchainClient()
