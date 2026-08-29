"""Adapter for transaction-time AMLSim signals; labels are excluded."""
from ..schema import NormalizedRiskSignal, RiskEvent


LABEL_FIELDS = {"is_sar", "alert_id", "alert_type", "pattern_id", "involved_accounts", "fraud_label", "ring_id"}


class AMLSimAdapter:
    dataset = "AMLSim"

    def adapt(self, row, model_output=None):
        model_output = model_output or {}
        event = RiskEvent(
            dataset=self.dataset,
            transaction_id=_text(row.get("tran_id")),
            timestamp=row.get("tran_timestamp"),
            amount=_number(row.get("base_amt")),
            transaction_type=_text(row.get("tx_type")),
            sender_id=_text(row.get("orig_acct")),
            receiver_id=_text(row.get("bene_acct")),
            fraud_probability=_number(model_output.get("fraud_probability")),
            model_used=model_output.get("model_used") if model_output else None,
            input_signals={key: value for key, value in row.items() if key not in LABEL_FIELDS},
        )
        event.signals = []
        if event.fraud_probability is not None:
            event.signals.append(NormalizedRiskSignal(self.dataset, "transaction_model", event.fraud_probability, 1.0, "AMLSim model probability", {"model_probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
        for name, key, category in (("fan_in_risk", "fan_in_prior_count", "aml"), ("fan_out_risk", "fan_out_prior_count", "aml"), ("cycle_risk", "cycle_prior_count", "aml"), ("AML_network_risk", "network_prior_count", "network")):
            if row.get(key) is not None:
                value = min(float(row[key]) / 10.0, 1.0)
                event.signals.append(NormalizedRiskSignal(self.dataset, name, value, 0.8, f"Prior {key.replace('_', ' ')} is available", {key: row[key]}, event.timestamp, None, category))
        return event


def _text(value):
    return None if value is None else str(value)


def _number(value):
    return None if value is None else float(value)