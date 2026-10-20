import pytest
from backend.risk_engine import (
    evaluate_record,
    train_model,
    create_classifier,
    RiskEngineConfig,
    FEATURES,
)


def test_rule_flags_repeated_requests():
    row = {
        "repeat_requests_24h": 3,
        "device_change": 0,
        "location_mismatch": 0,
        "subscriber_mismatch": 0,
        "hours_since_last_request": 200,
    }
    result = evaluate_record(row)
    assert any("Multiple replacement requests" in s for s in result["reasons"])
    assert 0 <= result["risk_score"] <= 1


def test_evaluate_normal_case():
    row = {
        "repeat_requests_24h": 0,
        "device_change": 0,
        "location_mismatch": 0,
        "subscriber_mismatch": 0,
        "hours_since_last_request": 300.0,
    }
    result = evaluate_record(row)
    assert result["decision"] == "LOW RISK"
    assert result["risk_score"] < 0.35
    assert "No configured rule-based warning was triggered" in result["reasons"]
    assert result["rule_score"] == 0.0


def test_evaluate_suspicious_case():
    row = {
        "repeat_requests_24h": 3,
        "device_change": 1,
        "location_mismatch": 1,
        "subscriber_mismatch": 1,
        "hours_since_last_request": 1.5,
    }
    result = evaluate_record(row)
    assert result["decision"] == "HIGH RISK"
    assert result["risk_score"] >= 0.70
    assert any("Multiple replacement requests" in r for r in result["reasons"])
    assert any("Device history differs" in r for r in result["reasons"])
    assert any("Location/area mismatch" in r for r in result["reasons"])
    assert any("Subscriber information inconsistency" in r for r in result["reasons"])
    assert any("Previous request occurred less than" in r for r in result["reasons"])


def test_evaluate_review_borderline_case():
    # Only single device change with high hours gap
    row = {
        "repeat_requests_24h": 0,
        "device_change": 1,
        "location_mismatch": 0,
        "subscriber_mismatch": 0,
        "hours_since_last_request": 250.0,
    }
    result = evaluate_record(row)
    assert any("Device history differs" in r for r in result["reasons"])
    assert result["decision"] in ("LOW RISK", "REVIEW")


def test_evaluate_missing_field_handling():
    # Incomplete record with missing features
    row = {
        "repeat_requests_24h": 1,
        "location_mismatch": 0,
    }
    result = evaluate_record(row, strict=False)
    assert "missing_fields" in result
    assert "device_change" in result["missing_fields"]
    assert "subscriber_mismatch" in result["missing_fields"]
    assert "hours_since_last_request" in result["missing_fields"]
    assert any("Missing field" in r for r in result["reasons"])
    assert 0.0 <= result["risk_score"] <= 1.0


def test_evaluate_invalid_inputs_sanitized():
    # Non-numeric and negative values handled gracefully in standard mode
    row = {
        "repeat_requests_24h": -5,
        "device_change": 2.5,
        "location_mismatch": "invalid_str",
        "subscriber_mismatch": None,
        "hours_since_last_request": -10.0,
    }
    result = evaluate_record(row, strict=False)
    assert 0.0 <= result["risk_score"] <= 1.0
    assert result["decision"] in ("LOW RISK", "REVIEW", "HIGH RISK")


def test_evaluate_strict_mode_raises():
    # In strict mode, invalid types or out-of-range binary flags raise ValueError
    row = {
        "repeat_requests_24h": 1,
        "device_change": 5,  # Invalid binary
        "location_mismatch": 0,
        "subscriber_mismatch": 0,
        "hours_since_last_request": 100,
    }
    with pytest.raises(ValueError):
        evaluate_record(row, strict=True)


def test_train_model_metrics_and_confusion_matrix():
    model, metrics = train_model(force_retrain=True)
    assert "accuracy" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1" in metrics
    assert "confusion_matrix" in metrics

    cm = metrics["confusion_matrix"]
    assert "tn" in cm
    assert "fp" in cm
    assert "fn" in cm
    assert "tp" in cm
    assert "matrix" in cm
    assert cm["tn"] + cm["fp"] + cm["fn"] + cm["tp"] == metrics["test_records"]

    # Prevent data leakage: train set and test set strictly partition data
    total_records = metrics["train_records"] + metrics["test_records"]
    assert total_records == 1000
    assert metrics["test_records"] == 250
    assert metrics["train_records"] == 750


def test_model_factory_and_fallback():
    # 1. Explicit random forest
    rf, name_rf = create_classifier("random_forest")
    assert "RandomForest" in name_rf

    # 2. Auto selection
    auto_clf, name_auto = create_classifier("auto")
    assert name_auto in ("XGBoost", "RandomForest (fallback)")

    # 3. Invalid model type raises ValueError
    with pytest.raises(ValueError):
        create_classifier("unsupported_model_xyz")


def test_configurable_thresholds():
    row = {
        "repeat_requests_24h": 2,
        "device_change": 1,
        "location_mismatch": 0,
        "subscriber_mismatch": 0,
        "hours_since_last_request": 50,
    }
    # With standard threshold_high=0.70
    standard_cfg = RiskEngineConfig(threshold_high=0.70, threshold_review=0.35)
    res_std = evaluate_record(row, config=standard_cfg)

    # With very low threshold_high=0.20
    aggressive_cfg = RiskEngineConfig(threshold_high=0.20, threshold_review=0.10)
    res_agg = evaluate_record(row, config=aggressive_cfg)

    assert res_agg["risk_score"] == res_std["risk_score"]
    assert res_agg["decision"] == "HIGH RISK"


def test_shap_explanation_integration():
    row = {
        "repeat_requests_24h": 3,
        "device_change": 1,
        "location_mismatch": 1,
        "subscriber_mismatch": 1,
        "hours_since_last_request": 2.0,
    }
    result = evaluate_record(row)
    assert "shap" in result
    shap_data = result["shap"]
    assert shap_data is not None
    assert "base_value" in shap_data
    assert "contributions" in shap_data
    assert "force_plot_html" in shap_data
    assert len(shap_data["force_plot_html"]) > 100
    for feat in FEATURES:
        assert feat in shap_data["contributions"]

