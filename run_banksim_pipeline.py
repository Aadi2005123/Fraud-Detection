"""Train and evaluate the isolated BankSim model pipeline."""
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from banksim import chronological_split, engineer_banksim_features, evaluate_model, load_banksim, make_xy, save_model, train_model

TRANSACTION_PATH = PROJECT_ROOT / "data" / "ieee-cis-fraud" / "archive" / "bs140513_032310.csv"
EDGE_PATH = PROJECT_ROOT / "data" / "ieee-cis-fraud" / "archive" / "bsNET140513_032310.csv"
REPORT_PATH = PROJECT_ROOT / "reports" / "banksim_metrics.json"
MODEL_PATH = PROJECT_ROOT / "reports" / "banksim_xgb_model.joblib"


def main():
    raw = load_banksim(TRANSACTION_PATH, EDGE_PATH)
    features = engineer_banksim_features(raw)
    train, test, cutoff = chronological_split(features)
    X_train, y_train = make_xy(train)
    X_test, y_test = make_xy(test, X_train.columns)
    model = train_model(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test, test["amount"].to_numpy())
    save_model(model, X_train.columns, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps({"dataset": "BankSim", "transaction_rows": len(raw), "fraud_count": int(raw["fraud"].sum()), "fraud_rate": float(raw["fraud"].mean()), "train_rows": len(train), "test_rows": len(test), "split_cutoff_step": cutoff, "features": list(X_train.columns), "graph_relationship": "customer -> merchant; edge Weight=amount and typeTrans=category", "false_positive_cost_assumption_inr": 75.0, "metrics": metrics}, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"Saved model: {MODEL_PATH}")
    print(f"Saved metrics: {REPORT_PATH}")


if __name__ == "__main__":
    main()