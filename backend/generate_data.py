"""
Synthetic Telecom Dataset Generator & Validator
================================================
Generates reproducible synthetic SIM swap request datasets for development, testing,
and live demonstration of the SIM Swap Fraud Detection System.

CRITICAL NOTICE (Synthetic Data Disclaimer):
--------------------------------------------
Synthetic telecom data is generated solely for system development, functional
verification, and demonstration. Synthetic data distributions and rule-derived
labels cannot establish or prove real-world machine learning model accuracy,
precision, or recall in actual telecommunications networks.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import random
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DEFAULT_DATA_PATH = DATA / "sim_swap_requests.csv"

REQUIRED_COLUMNS = [
    "request_id",
    "subscriber_ref",
    "agent_uid",
    "repeat_requests_24h",
    "device_change",
    "location_mismatch",
    "subscriber_mismatch",
    "hours_since_last_request",
    "fraud_label",
]

AGENT_UIDS = ["A1B2C3D4", "11223344", "DEMO1234"]

SYNTHETIC_DATA_DISCLAIMER = (
    "Synthetic telecom data is generated solely for system development, functional "
    "verification, and demonstration. Synthetic data distributions and rule-derived "
    "labels cannot establish or prove real-world machine learning model accuracy, "
    "precision, or recall in actual telecommunications networks."
)


def validate_dataset(
    data_or_path: Union[pd.DataFrame, str, Path],
    raise_error: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validates the integrity, schema, types, missing values, duplicate IDs,
    and logical range constraints of a synthetic telecom dataset.

    Parameters:
    - data_or_path: pd.DataFrame or path (str/Path) to the CSV file.
    - raise_error: If True, raises ValueError upon any validation failure.

    Returns:
    - (is_valid, errors): Tuple of boolean status and list of error descriptions.
    """
    errors: List[str] = []

    def _fail():
        if raise_error:
            raise ValueError(f"Dataset validation failed with {len(errors)} error(s):\n" + "\n".join(f"- {e}" for e in errors))
        return False, errors

    # 1. Load data
    if isinstance(data_or_path, (str, Path)):
        path = Path(data_or_path)
        if not path.exists():
            errors.append(f"Dataset file does not exist: {path}")
            return _fail()
        try:
            df = pd.read_csv(path)
        except Exception as e:
            errors.append(f"Failed to read CSV file: {e}")
            return _fail()
    elif isinstance(data_or_path, pd.DataFrame):
        df = data_or_path.copy()
    else:
        errors.append(f"Unsupported data type: {type(data_or_path)}. Expected DataFrame, str, or Path.")
        return _fail()

    # 2. Check for empty dataframe
    if len(df) == 0:
        errors.append("Dataset is empty (0 rows).")
        return _fail()

    # 3. Check required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return _fail()

    # 4. Check for missing / null / NaN values
    null_counts = df[REQUIRED_COLUMNS].isna().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if not cols_with_nulls.empty:
        for col, count in cols_with_nulls.items():
            errors.append(f"Column '{col}' contains {count} missing/null values.")

    # 5. Check duplicate request IDs
    duplicate_count = int(df["request_id"].duplicated().sum())
    if duplicate_count > 0:
        dup_samples = df[df["request_id"].duplicated()]["request_id"].head(5).tolist()
        errors.append(f"Found {duplicate_count} duplicate request_id values. Examples: {dup_samples}")

    # 6. Check data types and value constraints
    empty_reqs = df["request_id"].astype(str).str.strip().eq("").sum()
    if empty_reqs > 0:
        errors.append(f"Found {empty_reqs} empty or whitespace-only request_id values.")

    empty_subs = df["subscriber_ref"].astype(str).str.strip().eq("").sum()
    if empty_subs > 0:
        errors.append(f"Found {empty_subs} empty or whitespace-only subscriber_ref values.")

    empty_agents = df["agent_uid"].astype(str).str.strip().eq("").sum()
    if empty_agents > 0:
        errors.append(f"Found {empty_agents} empty or whitespace-only agent_uid values.")

    try:
        repeats = pd.to_numeric(df["repeat_requests_24h"], errors="coerce")
        if repeats.isna().any():
            errors.append("Column 'repeat_requests_24h' contains non-numeric values.")
        elif (repeats < 0).any():
            errors.append("Column 'repeat_requests_24h' contains negative values.")
    except Exception as e:
        errors.append(f"Failed to validate 'repeat_requests_24h': {e}")

    binary_cols = ["device_change", "location_mismatch", "subscriber_mismatch", "fraud_label"]
    for col in binary_cols:
        try:
            col_vals = pd.to_numeric(df[col], errors="coerce")
            if col_vals.isna().any():
                errors.append(f"Column '{col}' contains non-numeric values.")
            else:
                invalid_vals = set(col_vals.dropna().unique()) - {0, 1}
                if invalid_vals:
                    errors.append(f"Column '{col}' must be binary {0, 1}, found invalid values: {invalid_vals}")
        except Exception as e:
            errors.append(f"Failed to validate binary column '{col}': {e}")

    try:
        hours = pd.to_numeric(df["hours_since_last_request"], errors="coerce")
        if hours.isna().any():
            errors.append("Column 'hours_since_last_request' contains non-numeric values.")
        elif (hours < 0).any():
            errors.append("Column 'hours_since_last_request' contains negative values.")
    except Exception as e:
        errors.append(f"Failed to validate 'hours_since_last_request': {e}")

    # 7. Class representation check
    fraud_labels = set(df["fraud_label"].unique())
    if len(fraud_labels) < 2:
        errors.append(f"Dataset lacks class diversity. Found only classes: {fraud_labels}. Both 0 and 1 required.")

    is_valid = len(errors) == 0
    if raise_error and not is_valid:
        raise ValueError(f"Dataset validation failed with {len(errors)} error(s):\n" + "\n".join(f"- {e}" for e in errors))

    return is_valid, errors


def generate_scenario_record(
    scenario_type: str,
    index: int = 1,
    rng: Optional[random.Random] = None
) -> Dict[str, Union[str, int, float]]:
    """
    Generates a single, logically consistent synthetic record for a specific test scenario.

    Supported scenarios:
    - "normal": Clean, legitimate request with zero risk indicators (fraud_label=0).
    - "suspicious_multi_repeat": Attack with rapid repeated requests within 24 hours (fraud_label=1).
    - "suspicious_identity_takeover": Subscriber details mismatch + device swap (fraud_label=1).
    - "suspicious_roaming_hijack": Location mismatch + device change + rapid repeat (fraud_label=1).
    - "borderline_device_upgrade": Legitimate user replaced phone, normal gap (fraud_label=0).
    - "borderline_traveler": Legitimate user traveling, location mismatch (fraud_label=0).
    """
    if rng is None:
        rng = random.Random()

    request_id = f"REQ{index:05d}"
    subscriber_ref = f"SUB{rng.randint(10000, 99999)}"
    agent_uid = rng.choice(AGENT_UIDS)

    if scenario_type == "normal":
        repeats = 0
        device = 0
        location = 0
        mismatch = 0
        hours = round(rng.uniform(24.0, 720.0), 1)
        fraud = 0

    elif scenario_type == "suspicious_multi_repeat":
        repeats = rng.randint(2, 4)
        device = int(rng.random() < 0.7)
        location = int(rng.random() < 0.5)
        mismatch = int(rng.random() < 0.3)
        hours = round(rng.uniform(0.1, 24.0), 1)
        fraud = 1

    elif scenario_type == "suspicious_identity_takeover":
        repeats = rng.randint(0, 2)
        device = 1
        location = int(rng.random() < 0.6)
        mismatch = 1
        hours = round(rng.uniform(1.0, 360.0), 1)
        fraud = 1

    elif scenario_type == "suspicious_roaming_hijack":
        repeats = rng.randint(1, 3)
        device = 1
        location = 1
        mismatch = int(rng.random() < 0.4)
        hours = round(rng.uniform(0.5, 96.0), 1)
        fraud = 1

    elif scenario_type == "borderline_device_upgrade":
        repeats = 0
        device = 1
        location = 0
        mismatch = 0
        hours = round(rng.uniform(6.0, 400.0), 1)
        fraud = 0

    elif scenario_type == "borderline_traveler":
        repeats = 0
        device = 0
        location = 1
        mismatch = 0
        hours = round(rng.uniform(12.0, 500.0), 1)
        fraud = 0

    else:
        raise ValueError(f"Unknown scenario_type: '{scenario_type}'.")

    return {
        "request_id": request_id,
        "subscriber_ref": subscriber_ref,
        "agent_uid": agent_uid,
        "repeat_requests_24h": repeats,
        "device_change": device,
        "location_mismatch": location,
        "subscriber_mismatch": mismatch,
        "hours_since_last_request": hours,
        "fraud_label": fraud,
    }


def generate(
    seed: int = 42,
    n: int = 1000,
    output_path: Optional[Union[str, Path]] = None,
    validate_after: bool = True
) -> Path:
    """
    Generates a reproducible synthetic telecom dataset for development, testing,
    and demonstrator evaluation.

    Scenario distribution:
    - ~70% Normal legitimate requests (clean history, fraud_label=0)
    - ~18% Suspicious fraud attempts (multi-factor warnings, fraud_label=1)
    - ~12% Borderline review cases (single warning flag, realistic decision boundary)

    Preserves 100% column and schema compatibility with existing project modules.
    """
    rng = random.Random(seed)
    target_path = Path(output_path) if output_path else DEFAULT_DATA_PATH
    target_path.parent.mkdir(exist_ok=True)

    rows: List[Dict[str, Union[str, int, float]]] = []

    n_suspicious = int(n * 0.18)
    n_borderline = int(n * 0.12)
    n_normal = n - n_suspicious - n_borderline

    # First record (REQ00001) is guaranteed normal for baseline demo evaluation
    rows.append(generate_scenario_record("normal", index=1, rng=rng))

    for i in range(2, n_normal + 1):
        rows.append(generate_scenario_record("normal", index=i, rng=rng))

    suspicious_types = [
        "suspicious_multi_repeat",
        "suspicious_identity_takeover",
        "suspicious_roaming_hijack",
    ]
    for i in range(n_normal + 1, n_normal + n_suspicious + 1):
        stype = rng.choice(suspicious_types)
        rows.append(generate_scenario_record(stype, index=i, rng=rng))

    borderline_types = [
        "borderline_device_upgrade",
        "borderline_traveler",
    ]
    for i in range(n_normal + n_suspicious + 1, n + 1):
        btype = rng.choice(borderline_types)
        rows.append(generate_scenario_record(btype, index=i, rng=rng))

    df = pd.DataFrame(rows)

    if validate_after:
        validate_dataset(df, raise_error=True)

    df.to_csv(target_path, index=False)
    print(f"Generated {len(df)} synthetic records (Seed: {seed}): {target_path}")
    print(f"Distribution: Normal={n_normal}, Suspicious={n_suspicious}, Borderline={n_borderline}")
    print(f"Class counts: Fraud(1)={df['fraud_label'].sum()}, Non-Fraud(0)={(df['fraud_label'] == 0).sum()}")

    return target_path


if __name__ == "__main__":
    generate()
