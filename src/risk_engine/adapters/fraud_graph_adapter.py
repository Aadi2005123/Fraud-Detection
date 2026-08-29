"""Adapter for transaction-time graph signals without fraud labels."""
from ..schema import NormalizedRiskSignal, RiskEvent

LABEL_FIELDS = {"fraud_label", "ring_id", "pattern_id", "involved_accounts", "fraud_cases"}


class FraudGraphAdapter:
    dataset = "FraudGraph"

    def adapt(self, row, model_output=None):
        model_output = model_output or {}
        event = RiskEvent(
            dataset=self.dataset,
            transaction_id=_text(row.get("tx_id")),
            timestamp=row.get("timestamp"),
            amount=_number(row.get("amount")),
            sender_id=_text(row.get("src_id")),
            receiver_id=_text(row.get("dst_id")),
            device_signal=None,
            fraud_probability=_number(model_output.get("fraud_probability")),
            model_used=model_output.get("model_used") if model_output else None,
            input_signals={key: value for key, value in row.items() if key not in LABEL_FIELDS},
        )
        event.signals = []
        if event.fraud_probability is not None:
            event.signals.append(NormalizedRiskSignal(self.dataset, "transaction_model", event.fraud_probability, 1.0, "Fraud Graph model probability", {"model_probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
        for name, key, category, divisor in (("network_degree_risk", "src_degree", "network", 50.0), ("suspicious_connection_risk", "suspicious_connection_count", "network", 10.0), ("graph_anomaly_risk", "local_network_concentration", "anomaly", 1.0), ("ring_membership_risk", "ring_like_structural_score", "network", 1.0)):
            if row.get(key) is not None:
                value = min(float(row[key]) / divisor, 1.0)
                event.signals.append(NormalizedRiskSignal(self.dataset, name, value, 0.8, f"Transaction-time graph field {key} is available", {key: row[key]}, event.timestamp, None, category))
        return event


def _text(value):
    return None if value is None else str(value)


def _number(value):
    return None if value is None else float(value)