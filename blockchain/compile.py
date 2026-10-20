"""
Solidity Compiler Script for SimSwapAudit.sol
=============================================
Compiles SimSwapAudit.sol using official solc 0.8.20 (via py-solc-x)
and outputs the ABI and deployment bytecode artifact.
"""

from pathlib import Path
import json
import logging
import solcx

logger = logging.getLogger("blockchain_compile")

BASE_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = BASE_DIR / "contracts"
BUILD_DIR = BASE_DIR / "build"
CONTRACT_PATH = CONTRACTS_DIR / "SimSwapAudit.sol"
ARTIFACT_PATH = BUILD_DIR / "SimSwapAudit.json"

SOLC_VERSION = "0.8.20"


def ensure_solc_installed(version: str = SOLC_VERSION) -> str:
    """Ensures solc compiler of the specified version is installed."""
    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if version not in installed:
        logger.info(f"Installing solc {version}...")
        solcx.install_solc(version)
    solcx.set_solc_version(version)
    return version


def compile_contract(contract_path: Path = CONTRACT_PATH, force: bool = False) -> dict:
    """
    Compiles SimSwapAudit.sol and writes build/SimSwapAudit.json artifact.
    """
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    ensure_solc_installed(SOLC_VERSION)

    compiled = solcx.compile_files(
        [contract_path],
        output_values=["abi", "bin", "bin-runtime"],
        solc_version=SOLC_VERSION,
    )

    # Find the target contract key
    contract_key = None
    for k in compiled.keys():
        if k.endswith(":SimSwapAudit"):
            contract_key = k
            break

    if not contract_key:
        raise RuntimeError(f"SimSwapAudit contract not found in compiled output: {list(compiled.keys())}")

    contract_data = compiled[contract_key]
    bytecode = contract_data["bin"]
    abi = contract_data["abi"]

    if not bytecode or len(bytecode) == 0:
        raise RuntimeError("Compilation produced empty bytecode.")

    if not bytecode.startswith("0x"):
        bytecode = "0x" + bytecode

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "contract_name": "SimSwapAudit",
        "source_file": str(contract_path.name),
        "solc_version": SOLC_VERSION,
        "abi": abi,
        "bytecode": bytecode,
        "bytecode_runtime": "0x" + contract_data.get("bin-runtime", ""),
    }

    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)

    logger.info(f"Saved compiled artifact to {ARTIFACT_PATH} (bytecode: {len(bytecode)} chars, ABI: {len(abi)} items)")
    return artifact


def load_or_compile_artifact() -> dict:
    """Loads existing artifact if available; compiles if missing."""
    if ARTIFACT_PATH.exists():
        try:
            with open(ARTIFACT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("bytecode") and data.get("abi"):
                    return data
        except Exception:
            pass
    return compile_contract()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = compile_contract()
    print("=" * 60)
    print("SimSwapAudit Compilation Succeeded!")
    print(f"Artifact:        {ARTIFACT_PATH}")
    print(f"Solc Version:    {res['solc_version']}")
    print(f"Bytecode Length: {len(res['bytecode'])} chars")
    print(f"ABI Methods:     {len(res['abi'])} items")
    print("=" * 60)
