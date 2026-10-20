// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SimSwapAudit
 * @dev Cryptographic Immutable Audit Ledger for Telecom SIM Swap Fraud Evaluation.
 * Designed for College Capstone Project 2: Blockchain-Secured SIM Swap Fraud Detection.
 * 
 * Provides an on-chain, tamper-evident audit record of:
 * - Request ID
 * - Heuristic + ML Decision ("LOW RISK", "REVIEW", "HIGH RISK")
 * - Scaled Risk Score (Basis Points: 0 to 10,000 = 0.00% to 100.00%)
 * - SHA-256 Explanation Digest (Feature contribution & rule explanation hash)
 * - Agent Smart Card UID (RC522 RFID)
 * - Block Timestamp & Recording Validator Address
 */
contract SimSwapAudit {
    address public owner;
    uint256 public totalRecords;

    struct AuditRecord {
        string requestId;
        string decision;
        uint256 riskScoreBp;        // 0 to 10,000 basis points (e.g. 9670 = 96.7%)
        bytes32 explanationHash;    // SHA-256 digest of reasons/SHAP contributions
        string agentUid;            // RFID card identifier
        uint256 timestamp;          // EVM block timestamp
        address recordedBy;         // Ethereum address of the recording node
    }

    // Chronological on-chain ledger
    AuditRecord[] public auditTrail;

    // Mapping from Request ID to ledger indices
    mapping(string => uint256[]) private requestIndices;

    // Authorized validator / telecom operator nodes
    mapping(address => bool) public authorizedNodes;

    // Events
    event AuditRecorded(
        uint256 indexed recordIndex,
        string indexed requestId,
        string decision,
        uint256 riskScoreBp,
        bytes32 explanationHash,
        string agentUid,
        uint256 timestamp,
        address indexed recordedBy
    );

    event NodeAuthorized(address indexed node, bool isAuthorized);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "SimSwapAudit: caller is not the owner");
        _;
    }

    modifier onlyAuthorized() {
        require(
            msg.sender == owner || authorizedNodes[msg.sender],
            "SimSwapAudit: caller is not an authorized telecom node"
        );
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedNodes[msg.sender] = true;
        emit NodeAuthorized(msg.sender, true);
    }

    /**
     * @notice Records a new SIM swap fraud evaluation onto the blockchain.
     * @param requestId The telecom request identifier (e.g. "REQ00701")
     * @param decision The evaluation outcome ("LOW RISK", "REVIEW", "HIGH RISK")
     * @param riskScoreBp Numeric risk score in basis points (e.g. 9670 for 96.7%)
     * @param explanationHash Cryptographic SHA-256 digest of the decision reasons
     * @param agentUid Agent smart-card UID scanned via RFID
     * @return recordIndex The index of the newly added record in the audit trail
     */
    function recordAudit(
        string calldata requestId,
        string calldata decision,
        uint256 riskScoreBp,
        bytes32 explanationHash,
        string calldata agentUid
    ) external onlyAuthorized returns (uint256) {
        require(bytes(requestId).length > 0, "SimSwapAudit: requestId cannot be empty");
        require(bytes(decision).length > 0, "SimSwapAudit: decision cannot be empty");
        require(riskScoreBp <= 10000, "SimSwapAudit: riskScoreBp exceeds 10,000 basis points");

        uint256 newIndex = auditTrail.length;
        uint256 recordTime = block.timestamp;

        AuditRecord memory record = AuditRecord({
            requestId: requestId,
            decision: decision,
            riskScoreBp: riskScoreBp,
            explanationHash: explanationHash,
            agentUid: agentUid,
            timestamp: recordTime,
            recordedBy: msg.sender
        });

        auditTrail.push(record);
        requestIndices[requestId].push(newIndex);
        totalRecords = auditTrail.length;

        emit AuditRecorded(
            newIndex,
            requestId,
            decision,
            riskScoreBp,
            explanationHash,
            agentUid,
            recordTime,
            msg.sender
        );

        return newIndex;
    }

    /**
     * @notice Retrieves a specific audit record by index.
     */
    function getRecord(uint256 index)
        external
        view
        returns (
            string memory requestId,
            string memory decision,
            uint256 riskScoreBp,
            bytes32 explanationHash,
            string memory agentUid,
            uint256 timestamp,
            address recordedBy
        )
    {
        require(index < auditTrail.length, "SimSwapAudit: index out of bounds");
        AuditRecord storage r = auditTrail[index];
        return (
            r.requestId,
            r.decision,
            r.riskScoreBp,
            r.explanationHash,
            r.agentUid,
            r.timestamp,
            r.recordedBy
        );
    }

    /**
     * @notice Returns total number of on-chain audit records.
     */
    function getRecordCount() external view returns (uint256) {
        return auditTrail.length;
    }

    /**
     * @notice Verifies whether a record at a given index matches the expected explanation hash.
     */
    function verifyRecord(uint256 index, bytes32 expectedHash) external view returns (bool) {
        if (index >= auditTrail.length) {
            return false;
        }
        return auditTrail[index].explanationHash == expectedHash;
    }

    /**
     * @notice Queries all ledger indices associated with a particular Request ID.
     */
    function getRecordIndicesByRequest(string calldata requestId)
        external
        view
        returns (uint256[] memory)
    {
        return requestIndices[requestId];
    }

    /**
     * @notice Authorizes or deauthorizes a telecom validator node address.
     */
    function setNodeAuthorization(address node, bool isAuthorized) external onlyOwner {
        require(node != address(0), "SimSwapAudit: invalid node address");
        authorizedNodes[node] = isAuthorized;
        emit NodeAuthorized(node, isAuthorized);
    }

    /**
     * @notice Transfers contract ownership to a new address.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "SimSwapAudit: new owner is zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
        authorizedNodes[newOwner] = true;
    }
}
