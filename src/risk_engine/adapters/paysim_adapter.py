from ..schema import NormalizedRiskSignal, RiskEvent


class PaySimAdapter:
    dataset = "PaySim"

    def adapt(self, row, model_output=None):
        model_output = model_output or {}
        event = RiskEvent(
            dataset=self.dataset,
            transaction_id=_text(row.get("transaction_id", row.get("nameOrig"))),
            timestamp=row.get("step"),
            amount=_number(row.get("amount")),
            transaction_type=_text(row.get("type")),
            sender_id=_text(row.get("nameOrig")),
            receiver_id=_text(row.get("nameDest")),
            fraud_probability=_probability(model_output.get("fraud_probability")),
            model_used=model_output.get("model_used", "paysim-xgb-realtime") if model_output else None,
            input_signals={key: row[key] for key in row if key in {"step", "amount", "type", "nameOrig", "nameDest", "oldbalanceOrg", "oldbalanceDest"}},
        )
        event.signals = _signals(row, event, model_output)
        return event


def _signals(row, event, model_output):
    signals = []
    if event.fraud_probability is not None:
        signals.append(NormalizedRiskSignal("PaySim", "transaction_model", event.fraud_probability, 1.0, "PaySim model probability", {"model_probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
    if row.get("amount") is not None:
        signals.append(NormalizedRiskSignal("PaySim", "transaction_amount_risk", min(float(row["amount"]) / 10000.0, 1.0), 0.7, "Transaction amount is available", {"amount": row["amount"]}, event.timestamp, None, "behavioral"))
    if row.get("type") in {"TRANSFER", "CASH_OUT"}:
        signals.append(NormalizedRiskSignal("PaySim", "transfer_risk", 0.6 if row["type"] == "TRANSFER" else 0.5, 0.6, "Fraud-prone transaction type", {"type": row["type"]}, event.timestamp, None, "behavioral"))
    return signals


def _text(value):
    return None if value is None else str(value)


def _number(value):
    return None if value is None else float(value)


def _probability(value):
    return None if value is None else float(value)