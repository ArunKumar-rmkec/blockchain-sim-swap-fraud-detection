import pytest
import pandas as pd
from pathlib import Path
from backend.generate_data import (
    generate,
    validate_dataset,
    generate_scenario_record,
    REQUIRED_COLUMNS,
    AGENT_UIDS,
    SYNTHETIC_DATA_DISCLAIMER,
)


def test_reproducibility(tmp_path):
    path1 = tmp_path / "data1.csv"
    path2 = tmp_path / "data2.csv"
    generate(seed=123, n=50, output_path=path1)
    generate(seed=123, n=50, output_path=path2)

    df1 = pd.read_csv(path1)
    df2 = pd.read_csv(path2)
    pd.testing.assert_frame_equal(df1, df2)


def test_required_columns_and_non_null(tmp_path):
    path = tmp_path / "test_data.csv"
    generate(seed=42, n=100, output_path=path)
    df = pd.read_csv(path)

    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Missing required column: {col}"

    assert df.isna().sum().sum() == 0, "Dataset must not contain any null/NaN values"


def test_request_id_uniqueness_and_format(tmp_path):
    path = tmp_path / "test_unique.csv"
    generate(seed=42, n=100, output_path=path)
    df = pd.read_csv(path)

    assert df["request_id"].is_unique, "All request_id values must be unique"
    assert df["request_id"].str.startswith("REQ").all(), "All request_ids must start with REQ"
    assert df["subscriber_ref"].str.startswith("SUB").all(), "All subscriber_refs must start with SUB"
    assert df["agent_uid"].isin(AGENT_UIDS).all(), "All agent_uids must be valid recognized agent UIDs"


def test_data_types_and_ranges(tmp_path):
    path = tmp_path / "test_ranges.csv"
    generate(seed=42, n=100, output_path=path)
    df = pd.read_csv(path)

    assert (df["repeat_requests_24h"] >= 0).all()
    assert df["device_change"].isin([0, 1]).all()
    assert df["location_mismatch"].isin([0, 1]).all()
    assert df["subscriber_mismatch"].isin([0, 1]).all()
    assert (df["hours_since_last_request"] >= 0).all()
    assert df["fraud_label"].isin([0, 1]).all()


def test_scenario_generator_logic():
    normal = generate_scenario_record("normal", index=1)
    assert normal["fraud_label"] == 0
    assert normal["repeat_requests_24h"] == 0
    assert normal["device_change"] == 0
    assert normal["location_mismatch"] == 0
    assert normal["subscriber_mismatch"] == 0
    assert normal["hours_since_last_request"] >= 24

    multi_repeat = generate_scenario_record("suspicious_multi_repeat", index=2)
    assert multi_repeat["fraud_label"] == 1
    assert multi_repeat["repeat_requests_24h"] >= 2
    assert multi_repeat["hours_since_last_request"] <= 24

    identity_takeover = generate_scenario_record("suspicious_identity_takeover", index=3)
    assert identity_takeover["fraud_label"] == 1
    assert identity_takeover["subscriber_mismatch"] == 1
    assert identity_takeover["device_change"] == 1

    device_upgrade = generate_scenario_record("borderline_device_upgrade", index=4)
    assert device_upgrade["fraud_label"] == 0
    assert device_upgrade["device_change"] == 1
    assert device_upgrade["subscriber_mismatch"] == 0
    assert device_upgrade["location_mismatch"] == 0

    with pytest.raises(ValueError):
        generate_scenario_record("invalid_scenario_type", index=5)


def test_validation_detects_flaws():
    # 1. Missing columns
    bad_df = pd.DataFrame({"request_id": ["REQ00001"], "fraud_label": [0]})
    is_valid, errors = validate_dataset(bad_df)
    assert not is_valid
    assert any("Missing required columns" in e for e in errors)

    # 2. Duplicate IDs
    dup_df = pd.DataFrame({
        "request_id": ["REQ00001", "REQ00001"],
        "subscriber_ref": ["SUB1", "SUB2"],
        "agent_uid": ["A1B2C3D4", "A1B2C3D4"],
        "repeat_requests_24h": [0, 0],
        "device_change": [0, 0],
        "location_mismatch": [0, 0],
        "subscriber_mismatch": [0, 0],
        "hours_since_last_request": [10.0, 20.0],
        "fraud_label": [0, 1]
    })
    is_valid, errors = validate_dataset(dup_df)
    assert not is_valid
    assert any("duplicate request_id" in e for e in errors)

    # 3. Missing/null values
    null_df = dup_df.drop_duplicates(subset=["request_id"]).copy()
    null_df.loc[0, "hours_since_last_request"] = None
    is_valid, errors = validate_dataset(null_df)
    assert not is_valid
    assert any("missing/null values" in e for e in errors)

    # 4. Non-binary values in binary columns
    invalid_bin_df = dup_df.drop_duplicates(subset=["request_id"]).copy()
    invalid_bin_df.loc[0, "device_change"] = 5
    is_valid, errors = validate_dataset(invalid_bin_df)
    assert not is_valid
    assert any("must be binary" in e for e in errors)

    # 5. raise_error flag
    with pytest.raises(ValueError) as exc:
        validate_dataset(bad_df, raise_error=True)
    assert "Dataset validation failed" in str(exc.value)


def test_disclaimer_documented():
    assert "cannot establish or prove real-world" in SYNTHETIC_DATA_DISCLAIMER
    assert len(SYNTHETIC_DATA_DISCLAIMER) > 50
