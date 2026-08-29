"""Common Risk Engine V2 scoring and auditable decision layer."""
from copy import deepcopy
from datetime import datetime, timezone

from .explanation import explain
from .schema import NormalizedRiskSignal


class RiskEngine:
    POLICY_VERSION = "risk-engine-v2"
    WEIGHTS = {"model": 0.40, "behavioral": 0.20, "network": 0.20, "aml": 0.10, "anomaly": 0.10}

    def __init__(self, medium_threshold=0.30, high_threshold=0.60, critical_threshold=0.80):
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        self.audit_trail = []

    def assess(self, event):
        event.policy_version = self.POLICY_VERSION
        event.event_id = event.event_id or event.transaction_id
        signals = _valid_signals(event)
        active = [signal for signal in signals if signal.confidence > 0]
        weighted = []
        for signal in active:
            weight = self.WEIGHTS.get(signal.category, self.WEIGHTS["behavioral"])
            weighted.append((signal, weight * signal.risk_value * signal.confidence))
        total_weight = sum(self.WEIGHTS.get(signal.category, self.WEIGHTS["behavioral"]) * signal.confidence for signal in active)
        score = (sum(value for _, value in weighted) / total_weight * 100.0) if total_weight else 0.0
        event.signals = signals
        event.signal_contributions = [{"source": signal.source, "signal_name": signal.signal_name, "category": signal.category, "weight": self.WEIGHTS.get(signal.category, self.WEIGHTS["behavioral"]), "risk_value": signal.risk_value, "confidence": signal.confidence, "contribution": value / total_weight * 100.0 if total_weight else 0.0, "reason": signal.reason, "evidence": deepcopy(signal.evidence)} for signal, value in weighted]
        event.risk_score = round(score, 2)
        normalized = score / 100.0

        if normalized >= self.critical_threshold:
            event.risk_level = "CRITICAL"
            event.decision = "BLOCK"
        elif normalized >= self.high_threshold:
            event.risk_level = "HIGH"
            event.decision = "BLOCK"
        elif normalized >= self.medium_threshold:
            event.risk_level = "MEDIUM"
            event.decision = "REVIEW"
        else:
            event.risk_level = "LOW"
            event.decision = "ALLOW"

        event.explanation = explain(event)
        audit_time = datetime.now(timezone.utc).isoformat()
        audit = {
            "event_id": event.event_id,
            "audit_timestamp": audit_time,
            "dataset": event.dataset,
            "timestamp": event.timestamp,
            "model_names": [signal.model_name for signal in signals if signal.model_name],
            "model_probabilities": {signal.model_name: signal.risk_value for signal in signals if signal.model_name},
            "input_signals": deepcopy(event.input_signals),
            "individual_signals": [signal.__dict__.copy() for signal in signals],
            "signal_contributions": deepcopy(event.signal_contributions),
            "final_score": event.risk_score,
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "decision": event.decision,
            "explanation": event.explanation,
            "policy_version": event.policy_version,
        }
        self.audit_trail.append(audit)
        return event

    def get_audit_trail(self):
        return deepcopy(self.audit_trail)


def _bounded(value):
    return max(0.0, min(1.0, float(value)))


def _valid_signals(event):
    signals = list(event.signals)
    if event.fraud_probability is not None and not any(signal.model_name for signal in signals):
        signals.append(NormalizedRiskSignal(event.dataset, "dataset_model_probability", event.fraud_probability, 1.0, "Dataset-specific model output", {"probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
    legacy = [("amount_risk", event.amount_risk, "behavioral"), ("balance_risk", event.balance_risk, "behavioral"), ("velocity_risk", event.velocity_risk, "behavioral"), ("merchant_risk", event.merchant_risk, "network"), ("network_risk", event.network_risk, "network")]
    for name, value, category in legacy:
        if value is not None and not any(signal.signal_name == name for signal in signals):
            signals.append(NormalizedRiskSignal(event.dataset, name, value, 1.0, f"Available {name.replace('_', ' ')}", {}, event.timestamp, None, category))
    return signals