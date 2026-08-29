"""Train and evaluate the isolated IEEE-CIS fraud model."""
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ieee_cis import chronological_split, engineer_features, evaluate_model, load_ieee_cis, make_features, save_model, train_model

REPORT_PATH = PROJECT_ROOT / "reports" / "ieee_cis_metrics.json"
MODEL_PATH = PROJECT_ROOT / "reports" / "ieee_cis_xgb_model.joblib"


def main():
    raw = load_ieee_cis(PROJECT_ROOT / "data/ieee-cis-fraud/train_transaction.csv", PROJECT_ROOT / "data/ieee-cis-fraud/train_identity.csv")
    engineered = engineer_features(raw)
    train, test, cutoff = chronological_split(engineered)
    X_train = make_features(train)
    X_test = make_features(test, X_train.columns)
    model = train_model(X_train, train["isFraud"].astype(int))
    metrics = evaluate_model(model, X_test, test["isFraud"].astype(int), test["TransactionAmt"].to_numpy())
    save_model(model, X_train.columns, MODEL_PATH)
    summary = {
        "dataset": "IEEE-CIS Fraud Detection",
        "joined_rows": len(raw),
        "identity_rows": int(raw["DeviceType"].notna().sum()),
        "fraud_count": int(raw["isFraud"].sum()),
        "fraud_rate": float(raw["isFraud"].mean()),
        "train_rows": len(train),
        "test_rows": len(test),
        "split_transaction_dt": cutoff,
        "class_weighting": "scale_pos_weight = negatives / positives",
        "selected_features": list(X_train.columns),
        "excluded_feature_families": {"V_C_D_M": "opaque engineered/aggregate fields; excluded from conservative transaction-time baseline", "raw_id_fields": "opaque identifiers and identity measurements; excluded to reduce memorization/leakage risk", "DeviceInfo": "high-cardinality free text; excluded", "card1_card2_card5": "high-cardinality card identifiers; excluded", "TransactionID": "row identifier; excluded"},
        "false_positive_cost_assumption_inr": 75.0,
        "metrics": metrics,
    }
    REPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved metrics: {REPORT_PATH}")


if __name__ == "__main__":
    main()