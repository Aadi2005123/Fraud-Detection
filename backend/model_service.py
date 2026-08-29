import json
import sys
from pathlib import Path

import pandas as pd
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from features import build_realtime_features

MODEL_PATH = REPORTS_DIR / "xgb_realtime_model.json"
METRICS_PATH = REPORTS_DIR / "metrics.json"
MODEL_VERSION = "xgb-realtime"


class ModelService:
    def __init__(self, model_path=MODEL_PATH, metrics_path=METRICS_PATH):
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(model_path))
        with open(metrics_path, encoding="utf-8") as metrics_file:
            metrics = json.load(metrics_file)
        self.threshold = float(
            metrics["xgboost_realtime_cost_optimal"]["cost_optimal_threshold"]
        )

    def predict(self, transaction):
        frame = pd.DataFrame([transaction.model_dump()])
        features = build_realtime_features(frame)
        probability = float(self.model.predict_proba(features)[0, 1])
        if probability >= self.threshold:
            risk_level = "HIGH"
            decision = "FLAG"
        elif probability >= 0.30:
            risk_level = "MEDIUM"
            decision = "ALLOW"
        else:
            risk_level = "LOW"
            decision = "ALLOW"
        return {
            "fraud_probability": probability,
            "risk_level": risk_level,
            "decision": decision,
            "threshold": self.threshold,
        }
