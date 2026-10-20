# SimSwapAudit Smart Contract & Web3 Architecture
## Capstone Project 2 — Blockchain Audit Subsystem

The **SimSwapAudit** subsystem provides decentralized, tamper-evident cryptographic auditability for telecom SIM swap fraud evaluations. 

---

## 🏛️ Smart Contract Specification (`SimSwapAudit.sol`)

- **Language**: Solidity `^0.8.20`
- **Location**: `blockchain/contracts/SimSwapAudit.sol`
- **License**: MIT
- **Standard Gas Consumption**: ~259,316 gas per anchored evaluation
- **Deployment Gas Consumption**: ~1,780,322 gas

### Data Structure (`AuditRecord`)
```solidity
struct AuditRecord {
    string requestId;           // Telecom SIM swap request ID (e.g., "REQ00701")
    string decision;            // "LOW RISK", "REVIEW", "HIGH RISK"
    uint256 riskScoreBp;        // Basis points: 0 to 10,000 (e.g. 9670 = 96.7%)
    bytes32 explanationHash;    // SHA-256 digest of reasons and SHAP contributions
    string agentUid;            // Scanned RC522 RFID card UID
    uint256 timestamp;          // EVM block timestamp
    address recordedBy;         // Ethereum address of the recording validator node
}
```

### Core Functions
| Function | Visibility | Gas | Description |
|---|---|---|---|
| `recordAudit(requestId, decision, riskScoreBp, explanationHash, agentUid)` | `external onlyAuthorized` | ~259k | Anchors a new evaluation record and emits `AuditRecorded` event |
| `getRecord(index)` | `external view` | Free | Retrieves audit record fields by chronological index |
| `getRecordCount()` | `external view` | Free | Returns total number of on-chain records |
| `verifyRecord(index, expectedHash)` | `external view` | Free | Verifies if stored bytes32 hash matches expected digest |
| `getRecordIndicesByRequest(requestId)` | `external view` | Free | Returns all audit indices for a specific request ID |
| `setNodeAuthorization(node, isAuthorized)` | `external onlyOwner` | ~28k | Whitelists telecom operator nodes to commit records |

---

## 🌐 Dual-Mode Blockchain Operation

The system features an automatic dual-mode Web3 client (`backend/blockchain_client.py`):

### Mode 1: High-Fidelity EVM Emulation (`offline_emulation`)
- **Zero-Setup Laptop Execution**: Requires no external Ethereum node, testnet faucets, or gas tokens.
- **Explicit Offline Status**: Status is stamped as `SIMULATED_OFFLINE` to ensure emulated records are never falsely presented as confirmed on-chain.
- **Deterministic Keccak-256 Hashes**: Uses `Web3.keccak(...)` to generate realistic transaction hashes (`0x...`).
- **Simulated Blocks & Gas**: Produces realistic block numbers, timestamps, gas metrics, and persistent storage in `data/blockchain_state.json`.

### Mode 2: Live EVM Smart Contract Execution (`live_evm`)
Live mode is activated **only** when all 5 verification conditions succeed:
1. JSON-RPC connection to `http://127.0.0.1:8545` succeeds.
2. EVM Chain ID is confirmed (e.g. 1337 or 31337).
3. Contract address is configured and valid checksum address.
4. On-chain deployed bytecode exists at the configured contract address (rejects uninitialized EOAs).
5. Contract view functions (`owner()`, `getRecordCount()`) execute successfully.

In Live Mode:
- Transactions are submitted to `recordAudit` over RPC.
- The client waits for the real transaction receipt and validates `receipt.status == 1`.
- The real `tx_hash`, `block_number`, and `gas_used` are extracted directly from the node.
- The stored record is queried back from on-chain contract storage to confirm state persistence.

---

## 🚀 How to Run with a Live Local EVM Node

### Step 1: Start Ganache or Foundry Anvil
```powershell
# Ganache:
npx --yes ganache --port 8545 --chain.chainId 1337 --wallet.deterministic

# OR Foundry Anvil:
anvil --port 8545 --chain-id 1337
```

### Step 2: Compile Contract with solc 0.8.20
```powershell
python blockchain/compile.py
```

### Step 3: Deploy Contract to Local Node
```powershell
python blockchain/deploy.py
```
This saves deployment receipts to:
- `blockchain/build/deployment.json`
- `data/active_deployment.json`

---

## 🧪 Testing

```powershell
# Run emulation tests only (no EVM node required):
pytest -m "not evm" -v

# Run live local EVM integration tests (requires node on :8545):
pytest -m "evm" -v

# Run entire test suite (49 tests):
pytest -v
```

---

## 🔍 Cryptographic Verification Workflow

1. **Feature Explanation Hashing**:
   When an evaluation occurs, the risk engine generates human-readable reasons and SHAP local feature contributions. A SHA-256 digest is calculated over the canonical JSON representation:
   $$\text{explanation\_hash} = \text{SHA256}(\text{reasons} + \text{contributions})$$

2. **On-Chain Commitment**:
   The `explanation_hash` is encoded as `bytes32` and submitted to `SimSwapAudit.recordAudit()`.

3. **Tamper Detection**:
   Any party (regulator, telecom operator, or audit tribunal) can call `verifyRecord(index, expectedHash)` or use the interactive UI form in Tab 3 of the Streamlit dashboard to verify that the historical decision reasons have not been altered or forged.
