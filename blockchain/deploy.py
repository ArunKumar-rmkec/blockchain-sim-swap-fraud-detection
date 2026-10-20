"""
SimSwapAudit Smart Contract Deployment Script
=============================================
Compiles SimSwapAudit.sol and deploys it to a local EVM node (Ganache / Anvil)
or public Ethereum/Polygon testnet.
Verifies deployed bytecode and saves deployment receipt to blockchain/build/deployment.json.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
from web3 import Web3

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from blockchain.compile import load_or_compile_artifact

logger = logging.getLogger("blockchain_deploy")

BUILD_DIR = Path(__file__).resolve().parent / "build"
DEPLOYMENT_PATH = BUILD_DIR / "deployment.json"
DATA_DIR = BASE_DIR / "data"
DATA_DEPLOYMENT_PATH = DATA_DIR / "active_deployment.json"

DEFAULT_RPC_URL = os.getenv("ETH_RPC_URL", "http://127.0.0.1:8545")


def deploy_contract(rpc_url: str = DEFAULT_RPC_URL) -> dict:
    """
    Deploys the compiled SimSwapAudit contract to the EVM node at rpc_url,
    verifies deployed bytecode on-chain, and saves the deployment receipt.
    """
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Could not connect to EVM RPC node at {rpc_url}. Start Ganache or Anvil first.")

    chain_id = w3.eth.chain_id
    accounts = w3.eth.accounts
    if not accounts:
        raise RuntimeError(f"No unlocked accounts found on EVM node at {rpc_url}.")

    deployer = accounts[0]
    deployer_balance = w3.eth.get_balance(deployer)

    # 1. Load or compile artifact
    artifact = load_or_compile_artifact()
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    logger.info(f"Connected to EVM Node (Chain ID: {chain_id})")
    logger.info(f"Deployer Account: {deployer} (Balance: {w3.from_wei(deployer_balance, 'ether')} ETH)")

    # 2. Instantiate and send deployment transaction
    contract_factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = contract_factory.constructor().transact({"from": deployer})
    logger.info(f"Broadcasted deployment tx: {tx_hash.hex()}")

    # 3. Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
    if receipt.status != 1:
        raise RuntimeError(f"Contract deployment failed! Transaction status: {receipt.status}")

    contract_address = receipt.contractAddress
    if not contract_address:
        raise RuntimeError("Deployment receipt did not contain a contract address.")

    contract_address = Web3.to_checksum_address(contract_address)
    logger.info(f"Contract deployed successfully to address: {contract_address}")

    # 4. Verify deployed on-chain bytecode
    deployed_code = w3.eth.get_code(contract_address)
    if not deployed_code or len(deployed_code) <= 2:
        raise RuntimeError(f"Bytecode verification failed! No bytecode found at address {contract_address}")
    logger.info(f"Bytecode verification passed: {len(deployed_code)} bytes stored at {contract_address}")

    # 5. Verify contract state via ABI calls
    deployed_contract = w3.eth.contract(address=contract_address, abi=abi)
    owner = deployed_contract.functions.owner().call()
    total_records = deployed_contract.functions.getRecordCount().call()
    if owner != deployer:
        raise RuntimeError(f"Contract owner mismatch: expected {deployer}, got {owner}")
    if total_records != 0:
        raise RuntimeError(f"Expected 0 initial records, got {total_records}")

    deployment_data = {
        "contract_name": "SimSwapAudit",
        "contract_address": contract_address,
        "chain_id": chain_id,
        "rpc_url": rpc_url,
        "deployer_address": deployer,
        "deployment_tx_hash": tx_hash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "status": "CONFIRMED_ON_CHAIN",
        "solc_version": artifact.get("solc_version", "0.8.20"),
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save to build/ and data/
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEPLOYMENT_PATH, "w", encoding="utf-8") as f:
        json.dump(deployment_data, f, indent=2)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DEPLOYMENT_PATH, "w", encoding="utf-8") as f:
        json.dump(deployment_data, f, indent=2)

    return deployment_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rpc = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RPC_URL
    try:
        res = deploy_contract(rpc)
        print("=" * 65)
        print("Contract Deployed and Verified Successfully!")
        print(f"Contract Address:   {res['contract_address']}")
        print(f"Deployment Tx Hash: {res['deployment_tx_hash']}")
        print(f"Chain ID:           {res['chain_id']}")
        print(f"Block Number:       {res['block_number']}")
        print(f"Gas Used:           {res['gas_used']:,} gas")
        print(f"Saved Receipt:      {DEPLOYMENT_PATH}")
        print("=" * 65)
    except Exception as e:
        print(f"Deployment Failed: {e}", file=sys.stderr)
        sys.exit(1)
