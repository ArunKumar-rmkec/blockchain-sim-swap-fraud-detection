"""
Fraud Detection Risk Engine
===========================
Hybrid risk evaluation combining Machine Learning (XGBoost with RandomForest fallback)
and explicit rule-based telecom heuristics for SIM swap fraud detection.

CRITICAL NOTICE (Synthetic Data Disclaimer):
--------------------------------------------
Evaluated on synthetic telecom data. Synthetic distributions and rule-derived
labels cannot establish or prove real-world machine learning model accuracy,
precision, or recall in actual telecommunications networks.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "sim_swap_requests.csv"

FEATURES = [
    "repeat_requests_24h",
    "device_change",
    "location_mismatch",
    "subscriber_mismatch",
    "hours_since_last_request",
]

DEFAULT_FEATURE_VALUES = {
    "repeat_requests_24h": 0,
    "device_change": 0,
    "location_mismatch": 0,
    "subscriber_mismatch": 0,
    "hours_since_last_request": 168.0,  # 1 week default gap
}

SYNTHETIC_DATA_DISCLAIMER = (
    "Synthetic-label metrics only; not real-world performance. "
    "Synthetic data cannot establish real-world fraud detection accuracy."
)


@dataclass
class RiskEngineConfig:
    """Configurable weights, thresholds, and parameters for the risk scoring engine."""
    ml_weight: float = 0.70
    rule_weight: float = 0.30
    threshold_high: float = 0.70
    threshold_review: float = 0.35
    repeat_threshold: int = 2
    recent_hours_threshold: float = 24.0
    rule_weights: Dict[str, float] = field(default_factory=lambda: {
        "repeat_requests": 0.30,
        "device_change": 0.25,
        "location_mismatch": 0.20,
        "subscriber_mismatch": 0.35,
        "recent_request": 0.10,
    })


def create_classifier(model_type: str = "auto", random_state: int = 42) -> Tuple[Any, str]:
    """
    Model factory: Returns an XGBoost classifier if installed/requested,
    or gracefully falls back to scikit-learn RandomForestClassifier.

    Supported model_type values:
    - 'auto': Attempts to use XGBoost; if unavailable, uses RandomForest with a notice.
    - 'xgboost': Explicitly requests XGBoost; raises ImportError if not installed.
    - 'random_forest': Explicitly requests RandomForestClassifier.
    """
    mtype = model_type.lower().strip()

    if mtype in ("auto", "xgboost"):
        try:
            import xgboost as xgb
            model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=random_state,
                eval_metric="logloss",
            )
            return model, "XGBoost"
        except ImportError as e:
            if mtype == "xgboost":
                raise ImportError(f"XGBoost is not installed in the environment: {e}")
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=7,
                class_weight="balanced",
                random_state=random_state,
            )
            return model, "RandomForest (fallback)"

    elif mtype in ("random_forest", "rf"):
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=7,
            class_weight="balanced",
            random_state=random_state,
        )
        return model, "RandomForest"

    else:
        raise ValueError(f"Unknown model_type: '{model_type}'. Choose 'auto', 'xgboost', or 'random_forest'.")


def load_data(data_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    path = Path(data_path) if data_path else DATA_PATH
    if not path.exists():
        from backend.generate_data import generate
        generate(output_path=path)
    return pd.read_csv(path)


_MODEL_CACHE: Dict[str, Tuple[Any, Dict[str, Any]]] = {}


def train_model(
    model_type: str = "auto",
    data_path: Optional[Union[str, Path]] = None,
    test_size: float = 0.25,
    random_state: int = 42,
    force_retrain: bool = False,
) -> Tuple[Any, Dict[str, Any]]:
    """
    Trains the ML classifier on synthetic data using strict train/test split
    to prevent data leakage. Reports precision, recall, F1, and confusion matrix.
    """
    cache_key = f"{model_type}_{str(data_path)}_{test_size}_{random_state}"
    if not force_retrain and cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    df = load_data(data_path)
    X = df[FEATURES]
    y = df["fraud_label"].astype(int)

    # Strict featurization ordering: split strictly before model fitting
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    classifier, model_name = create_classifier(model_type, random_state=random_state)
    classifier.fit(X_train, y_train)

    pred = classifier.predict(X_test)
    cm = confusion_matrix(y_test, pred).tolist()

    metrics = {
        "model_name": model_name,
        "accuracy": round(float(accuracy_score(y_test, pred)), 3),
        "precision": round(float(precision_score(y_test, pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, pred, zero_division=0)), 3),
        "f1": round(float(f1_score(y_test, pred, zero_division=0)), 3),
        "confusion_matrix": {
            "tn": int(cm[0][0]),
            "fp": int(cm[0][1]),
            "fn": int(cm[1][0]),
            "tp": int(cm[1][1]),
            "matrix": cm,
        },
        "train_records": int(len(X_train)),
        "test_records": int(len(y_test)),
        "note": SYNTHETIC_DATA_DISCLAIMER,
    }

    _MODEL_CACHE[cache_key] = (classifier, metrics)
    return classifier, metrics


_SHAP_EXPLAINER_CACHE: Dict[int, Any] = {}


def get_shap_explainer(model: Any) -> Optional[Any]:
    """Retrieves or creates a cached SHAP TreeExplainer for the given model."""
    try:
        import shap
        model_id = id(model)
        if model_id not in _SHAP_EXPLAINER_CACHE:
            _SHAP_EXPLAINER_CACHE[model_id] = shap.TreeExplainer(model)
        return _SHAP_EXPLAINER_CACHE[model_id]
    except Exception:
        return None


def explain_record(sanitized_record: Dict[str, float], model: Any) -> Optional[Dict[str, Any]]:
    """
    Computes local SHAP explanations and interactive HTML force plot for an individual request.
    """
    try:
        import shap
        explainer = get_shap_explainer(model)
        if explainer is None:
            return None

        input_df = pd.DataFrame([{k: sanitized_record[k] for k in FEATURES}], columns=FEATURES)
        shap_values = explainer(input_df)[0]
        force_plot = shap.plots.force(shap_values)
        force_html = f"<head>{shap.getjs()}</head><body>{force_plot.html()}</body>"

        contributions = {
            feat: round(float(val), 4)
            for feat, val in zip(FEATURES, shap_values.values)
        }

        return {
            "base_value": round(float(shap_values.base_values), 4),
            "contributions": contributions,
            "force_plot_html": force_html,
        }
    except Exception as e:
        return {"error": str(e)}


def evaluate_record(
    record: Dict[str, Any],
    config: Optional[RiskEngineConfig] = None,
    model: Optional[Any] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates a single SIM swap request record combining Machine Learning scoring
    and rule-based telecom heuristics.

    Parameters:
    - record: Dictionary containing request features.
    - config: Optional RiskEngineConfig to override weights and thresholds.
    - model: Optional pre-trained model instance.
    - strict: If True, raises ValueError on invalid inputs; otherwise sanitizes gracefully.

    Returns:
    - Dictionary containing: ml_score, rule_score, risk_score, risk_percent,
      decision, reasons, model_used, missing_fields, and shap explanation.
    """
    cfg = config or RiskEngineConfig()
    reasons: List[str] = []
    missing_fields: List[str] = []
    sanitized: Dict[str, float] = {}

    # Validate, sanitize and handle missing / invalid fields
    for feat in FEATURES:
        if feat not in record or record[feat] is None or (isinstance(record[feat], str) and record[feat].strip() == ""):
            missing_fields.append(feat)
            default_val = float(DEFAULT_FEATURE_VALUES[feat])
            sanitized[feat] = default_val
            reasons.append(f"Missing field: '{feat}' (defaulted to {default_val})")
        else:
            try:
                val = float(record[feat])
                if feat in ("device_change", "location_mismatch", "subscriber_mismatch"):
                    if val not in (0.0, 1.0):
                        if strict:
                            raise ValueError(f"Field '{feat}' must be binary 0 or 1, got {val}")
                        reasons.append(f"Invalid binary value for '{feat}': {val}; clamped")
                        val = 1.0 if val > 0 else 0.0
                elif feat == "repeat_requests_24h":
                    if val < 0:
                        if strict:
                            raise ValueError(f"Field '{feat}' must be non-negative, got {val}")
                        reasons.append(f"Negative repeat requests: {val}; clamped to 0")
                        val = 0.0
                elif feat == "hours_since_last_request":
                    if val < 0:
                        if strict:
                            raise ValueError(f"Field '{feat}' must be non-negative, got {val}")
                        reasons.append(f"Negative hours: {val}; clamped to 0.0")
                        val = 0.0
                sanitized[feat] = val
            except (ValueError, TypeError) as e:
                if strict:
                    raise ValueError(f"Invalid non-numeric input for '{feat}': {record[feat]}") from e
                default_val = float(DEFAULT_FEATURE_VALUES[feat])
                reasons.append(f"Non-numeric value for '{feat}': '{record[feat]}' (defaulted to {default_val})")
                sanitized[feat] = default_val

    # 1. Machine Learning Scoring
    if model is None:
        trained_clf, metrics = train_model()
        model_name = metrics.get("model_name", "TrainedModel")
    else:
        trained_clf = model
        model_name = getattr(model, "__class__", type(model)).__name__

    input_df = pd.DataFrame([{k: sanitized[k] for k in FEATURES}], columns=FEATURES)
    ml_prob = float(trained_clf.predict_proba(input_df)[0][1])

    # 2. Rule-Based Checks
    rule_score = 0.0
    weights = cfg.rule_weights

    if sanitized["repeat_requests_24h"] >= cfg.repeat_threshold:
        rule_score += weights.get("repeat_requests", 0.30)
        reasons.append(f"Multiple replacement requests ({int(sanitized['repeat_requests_24h'])}) within 24 hours")

    if int(sanitized["device_change"]) == 1:
        rule_score += weights.get("device_change", 0.25)
        reasons.append("Device history differs from previous record")

    if int(sanitized["location_mismatch"]) == 1:
        rule_score += weights.get("location_mismatch", 0.20)
        reasons.append("Location/area mismatch in synthetic data")

    if int(sanitized["subscriber_mismatch"]) == 1:
        rule_score += weights.get("subscriber_mismatch", 0.35)
        reasons.append("Subscriber information inconsistency")

    if sanitized["hours_since_last_request"] < cfg.recent_hours_threshold:
        rule_score += weights.get("recent_request", 0.10)
        reasons.append(f"Previous request occurred less than {cfg.recent_hours_threshold:.0f} hours ago ({sanitized['hours_since_last_request']:.1f}h)")

    rule_score = min(rule_score, 1.0)

    # 3. Combined Hybrid Risk
    risk = min(1.0, cfg.ml_weight * ml_prob + cfg.rule_weight * rule_score)

    if risk >= cfg.threshold_high:
        decision = "HIGH RISK"
    elif risk >= cfg.threshold_review:
        decision = "REVIEW"
    else:
        decision = "LOW RISK"

    # Clean reasons if only default was applied and no warning
    rule_warnings = [r for r in reasons if not r.startswith("Missing field") and not r.startswith("Non-numeric") and not r.startswith("Invalid binary")]
    if not rule_warnings:
        reasons.append("No configured rule-based warning was triggered")

    # 4. SHAP Model Explainability
    shap_info = explain_record(sanitized, trained_clf)

    return {
        "ml_score": round(ml_prob, 4),
        "rule_score": round(rule_score, 4),
        "risk_score": round(risk, 4),
        "risk_percent": round(risk * 100, 1),
        "decision": decision,
        "reasons": reasons,
        "model_used": model_name,
        "missing_fields": missing_fields,
        "shap": shap_info,
    }
