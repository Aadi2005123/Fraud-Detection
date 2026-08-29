import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import xgboost as xgb

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from features import build_realtime_features

DEFAULT_MODEL_PATH = REPORTS_DIR / "xgb_realtime_model.json"
DEFAULT_METRICS_PATH = REPORTS_DIR / "metrics.json"
MODEL_VERSION = "xgb-realtime"


class ModelService:
    def __init__(self, model_path=None, metrics_path=None):
        env_model = os.getenv("MODEL_PATH")
        env_metrics = os.getenv("METRICS_PATH")
        
        self.model_path = Path(model_path or (PROJECT_ROOT / env_model if env_model else DEFAULT_MODEL_PATH))
        self.metrics_path = Path(metrics_path or (PROJECT_ROOT / env_metrics if env_metrics else DEFAULT_METRICS_PATH))
        
        self.model = None
        self.is_loaded = False
        self.threshold = 0.05

        self._load_metrics()
        self._load_model()

    def _load_metrics(self):
        try:
            if self.metrics_path.is_file():
                with open(self.metrics_path, encoding="utf-8") as metrics_file:
                    metrics = json.load(metrics_file)
                self.threshold = float(
                    metrics.get("xgboost_realtime_cost_optimal", {}).get("cost_optimal_threshold", 0.05)
                )
        except Exception as exc:
            logger.warning("Could not load metrics file (%s): %s", self.metrics_path, exc)
            self.threshold = 0.05

    def _load_model(self):
        try:
            if self.model_path.is_file():
                model = xgb.XGBClassifier()
                model.load_model(str(self.model_path))
                self.model = model
                self.is_loaded = True
                logger.info("Successfully loaded XGBoost model from %s", self.model_path)
            else:
                logger.warning("Model file not found at %s. Falling back to heuristic mode.", self.model_path)
                self.model = None
                self.is_loaded = False
        except Exception as exc:
            logger.warning("Failed to load XGBoost model (%s): %s. Safe fallback active.", self.model_path, exc)
            self.model = None
            self.is_loaded = False

    def predict(self, transaction):
        if self.model is not None and self.is_loaded:
            try:
                frame = pd.DataFrame([transaction.model_dump()])
                features = build_realtime_features(frame)
                probability = float(self.model.predict_proba(features)[0, 1])
            except Exception as exc:
                logger.warning("Model inference error: %s. Using heuristic prediction.", exc)
                probability = self._fallback_probability(transaction)
        else:
            probability = self._fallback_probability(transaction)

        probability = max(0.0, min(1.0, float(probability)))
        score_100 = round(probability * 100.0, 1)

        # Canonical Decision Matrix: 0-29 LOW/ALLOW, 30-59 MEDIUM/REVIEW, 60-79 HIGH/BLOCK, 80-100 CRITICAL/BLOCK
        if score_100 >= 80.0:
            risk_level = "CRITICAL"
            decision = "BLOCK"
        elif score_100 >= 60.0:
            risk_level = "HIGH"
            decision = "BLOCK"
        elif score_100 >= 30.0:
            risk_level = "MEDIUM"
            decision = "REVIEW"
        else:
            risk_level = "LOW"
            decision = "ALLOW"

        return {
            "fraud_probability": round(probability, 4),
            "risk_level": risk_level,
            "decision": decision,
            "threshold": self.threshold,
        }

    def _fallback_probability(self, transaction) -> float:
        """Safe non-crashing heuristic fallback when model binary is not loaded."""
        amount = getattr(transaction, "amount", 0.0)
        oldbalance_org = getattr(transaction, "oldbalanceOrg", 0.0)
        
        # Simple baseline: high ratio of amount to balance or very large amount
        if oldbalance_org > 0 and (amount / oldbalance_org) >= 0.95 and amount >= 50000.0:
            return 0.75
        if amount >= 100000.0:
            return 0.45
        return 0.01
