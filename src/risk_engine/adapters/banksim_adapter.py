from ..schema import NormalizedRiskSignal, RiskEvent


class BankSimAdapter:
    dataset = "BankSim"

    def adapt(self, row, model_output=None):
        model_output = model_output or {}
        event = RiskEvent(
            dataset=self.dataset,
            transaction_id=_text(row.get("transaction_id")),
            timestamp=row.get("step"),
            amount=_number(row.get("amount")),
            sender_id=_text(row.get("customer")),
            merchant_id=_text(row.get("merchant")),
            transaction_type=_text(row.get("category")),
            location_signal=_text(row.get("zipcodeOri")),
            fraud_probability=_probability(model_output.get("fraud_probability")),
            model_used=model_output.get("model_used", "banksim-xgb") if model_output else None,
            input_signals={key: row[key] for key in row if key in {"step", "amount", "customer", "merchant", "category", "zipcodeOri", "zipMerchant"}},
        )
        event.signals = _signals(row, event)
        return event


def _signals(row, event):
    signals = []
    if event.fraud_probability is not None:
        signals.append(NormalizedRiskSignal("BankSim", "transaction_model", event.fraud_probability, 1.0, "BankSim model probability", {"model_probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
    if row.get("customer_prior_tx_count") is not None:
        count = float(row["customer_prior_tx_count"])
        signals.append(NormalizedRiskSignal("BankSim", "customer_behavior_risk", min(count / 50.0, 1.0), 0.8, "Prior customer transaction history is available", {"prior_tx_count": count}, event.timestamp, None, "behavioral"))
    if row.get("merchant_prior_tx_count") is not None:
        count = float(row["merchant_prior_tx_count"])
        signals.append(NormalizedRiskSignal("BankSim", "merchant_behavior_risk", min(count / 10000.0, 1.0), 0.6, "Prior merchant transaction history is available", {"prior_tx_count": count}, event.timestamp, None, "network"))
    if row.get("customer_merchant_prior_tx_count") is not None:
        count = float(row["customer_merchant_prior_tx_count"])
        signals.append(NormalizedRiskSignal("BankSim", "customer_merchant_relationship_risk", min(count / 20.0, 1.0), 0.7, "Prior customer-merchant relationship is available", {"prior_relationship_count": count}, event.timestamp, None, "network"))
    return signals


def _text(value):
    return None if value is None else str(value).strip("'")


def _number(value):
    return None if value is None else float(value)


def _probability(value):
    return None if value is None else float(value)