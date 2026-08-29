from ..schema import NormalizedRiskSignal, RiskEvent


class IEEECISAdapter:
    dataset = "IEEE-CIS"

    def adapt(self, row, model_output=None):
        model_output = model_output or {}
        device = _first(row, "DeviceType", "id_31")
        identity = _first(row, "id_12", "id_15", "id_16", "id_28", "id_29", "id_35", "id_36", "id_37", "id_38")
        location = _first(row, "addr1", "addr2")
        event = RiskEvent(
            dataset=self.dataset,
            transaction_id=_text(row.get("TransactionID")),
            timestamp=row.get("TransactionDT"),
            amount=_number(row.get("TransactionAmt")),
            transaction_type=_text(row.get("ProductCD")),
            merchant_id=None,
            payment_method=_first(row, "card4", "card6"),
            device_signal=_text(device),
            identity_signal=_text(identity),
            location_signal=_text(location),
            fraud_probability=_probability(model_output.get("fraud_probability")),
            model_used=model_output.get("model_used", "ieee-cis-xgb") if model_output else None,
            input_signals={key: row[key] for key in row if key in {"TransactionID", "TransactionDT", "TransactionAmt", "ProductCD", "card4", "card6", "addr1", "addr2", "DeviceType", "id_31"}},
        )
        event.signals = _signals(row, event)
        return event


def _signals(row, event):
    signals = []
    if event.fraud_probability is not None:
        signals.append(NormalizedRiskSignal("IEEE-CIS", "transaction_model", event.fraud_probability, 1.0, "IEEE-CIS model probability", {"model_probability": event.fraud_probability}, event.timestamp, event.model_used, "model"))
    if row.get("TransactionAmt") is not None:
        signals.append(NormalizedRiskSignal("IEEE-CIS", "transaction_risk", min(float(row["TransactionAmt"]) / 1000.0, 1.0), 0.6, "Transaction amount is available", {"amount": row["TransactionAmt"]}, event.timestamp, None, "behavioral"))
    if event.device_signal is not None:
        signals.append(NormalizedRiskSignal("IEEE-CIS", "device_risk", 0.4, 0.5, "Device signal is available", {"device": event.device_signal}, event.timestamp, None, "anomaly"))
    if event.identity_signal is not None:
        signals.append(NormalizedRiskSignal("IEEE-CIS", "identity_risk", 0.3, 0.5, "Identity verification signal is available", {"identity": event.identity_signal}, event.timestamp, None, "behavioral"))
    return signals


def _first(row, *keys):
    for key in keys:
        if row.get(key) is not None:
            return row[key]
    return None


def _text(value):
    return None if value is None else str(value)


def _number(value):
    return None if value is None else float(value)


def _probability(value):
    return None if value is None else float(value)