import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from risk_engine import NormalizedRiskSignal, RiskEngine, RiskEvent
from risk_engine.adapters import AMLSimAdapter, BankSimAdapter, FraudGraphAdapter, IEEECISAdapter, PaySimAdapter


def test_paysim_adapter_preserves_sender_receiver_and_nulls_unsupported_fields():
    event = PaySimAdapter().adapt({"step": 10, "amount": 50, "type": "TRANSFER", "nameOrig": "C1", "nameDest": "M1"}, {"fraud_probability": 0.2})
    assert event.dataset == "PaySim"
    assert event.sender_id == "C1"
    assert event.receiver_id == "M1"
    assert event.transaction_type == "TRANSFER"
    assert event.fraud_probability == 0.2
    assert event.merchant_id is None
    assert event.device_signal is None


def test_banksim_adapter_maps_customer_merchant_and_location():
    event = BankSimAdapter().adapt({"step": 4, "amount": 12.5, "customer": "'C1'", "merchant": "'M1'", "category": "'food'", "zipcodeOri": "'28007'"})
    assert event.dataset == "BankSim"
    assert event.sender_id == "C1"
    assert event.merchant_id == "M1"
    assert event.transaction_type == "food"
    assert event.location_signal == "28007"
    assert event.receiver_id is None


def test_ieee_adapter_maps_available_device_identity_and_payment_fields():
    event = IEEECISAdapter().adapt({"TransactionID": 7, "TransactionDT": 100, "TransactionAmt": 20, "ProductCD": "W", "card4": "visa", "DeviceType": "mobile", "id_31": "chrome", "id_15": "New", "addr1": 123})
    assert event.dataset == "IEEE-CIS"
    assert event.transaction_id == "7"
    assert event.payment_method == "visa"
    assert event.device_signal == "mobile"
    assert event.identity_signal == "New"
    assert event.location_signal == "123"
    assert event.sender_id is None
    assert event.merchant_id is None


def test_engine_uses_model_probability_without_averaging_and_audits():
    event = RiskEvent(dataset="BankSim", fraud_probability=0.8, amount_risk=0.1, merchant_risk=0.2, input_signals={"amount": 10})
    engine = RiskEngine()
    result = engine.assess(event)
    assert result.risk_score == 47.5
    assert result.risk_level == "MEDIUM"
    assert result.decision == "REVIEW"
    assert "model probability" in result.explanation.lower()
    audit = engine.get_audit_trail()[0]
    assert audit["dataset"] == "BankSim"
    assert audit["risk_score"] == 47.5
    assert audit["input_signals"] == {"amount": 10}
    assert audit["audit_timestamp"]


def test_engine_does_not_claim_missing_signals():
    result = RiskEngine().assess(RiskEvent(dataset="PaySim"))
    assert result.risk_score == 0.0
    assert result.risk_level == "LOW"
    assert result.decision == "ALLOW"
    assert "LOW RISK" in result.explanation
    assert "No risk signals were available" in result.explanation


def test_amlsim_adapter_excludes_ground_truth_labels():
    event = AMLSimAdapter().adapt({"tran_id": "t1", "orig_acct": "a1", "bene_acct": "a2", "tx_type": "WIRE", "base_amt": 100, "tran_timestamp": "2024-01-01", "is_sar": "True", "alert_id": "ALERT_1", "alert_type": "cycle", "fan_in_prior_count": 2})
    assert event.sender_id == "a1"
    assert event.receiver_id == "a2"
    assert event.signals[0].signal_name == "fan_in_risk"
    assert "is_sar" not in event.input_signals
    assert "alert_id" not in event.input_signals
    assert all(signal.signal_name != "is_sar" for signal in event.signals)


def test_fraud_graph_adapter_uses_graph_fields_without_labels():
    event = FraudGraphAdapter().adapt({"tx_id": "tx1", "src_id": "acc1", "dst_id": "acc2", "amount": 200, "timestamp": "2024-01-01", "src_degree": 20, "ring_id": "pat_1", "fraud_label": 1, "pattern_id": "pat_1"})
    assert event.sender_id == "acc1"
    assert event.receiver_id == "acc2"
    assert any(signal.signal_name == "network_degree_risk" for signal in event.signals)
    assert "fraud_label" not in event.input_signals
    assert "ring_id" not in event.input_signals


def test_signal_values_are_normalized_and_score_contributions_are_recorded():
    signal = NormalizedRiskSignal("test", "out_of_range", 2, 3, "test reason", {"value": 2})
    result = RiskEngine().assess(RiskEvent(dataset="test", signals=[signal]))
    assert signal.risk_value == 1.0
    assert signal.confidence == 1.0
    assert result.risk_score == 100.0
    assert result.risk_level in ("HIGH", "CRITICAL")
    assert result.decision in ("FLAG", "BLOCK")
    assert result.signal_contributions[0]["contribution"] == 100.0


def test_engine_keeps_missing_signals_unclaimed_and_audit_is_complete():
    engine = RiskEngine()
    event = engine.assess(PaySimAdapter().adapt({"amount": 10, "type": "PAYMENT"}))
    assert event.device_signal is None
    assert "device" not in event.explanation.lower()
    audit_event = engine.assess(BankSimAdapter().adapt({"amount": 10}, {"fraud_probability": 0.4}))
    record = engine.get_audit_trail()[1]
    assert audit_event.decision == "REVIEW"
    assert record["policy_version"] == "risk-engine-v2"
    assert record["event_id"] is None
    assert record["signal_contributions"]