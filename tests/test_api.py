from fastapi.testclient import TestClient

from backend.database import Database
from backend.main import app, database

client = TestClient(app)

VALID_REQUEST = {
    "amount": 1000,
    "oldbalanceOrg": 2000,
    "oldbalanceDest": 0,
    "type": "TRANSFER",
    "hour": 12,
    "day": 10,
}


def reset_demo_state():
    database.reset_demo_state()


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Fraud Detection API"
    assert data["version"] == "2.0.0"


def test_docs():
    response = client.get("/docs")
    assert response.status_code == 200


def test_health():
    reset_demo_state()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}


def test_risk_v1_health_and_models():
    assert client.get("/api/v1/health").status_code == 200
    payload = client.get("/api/v1/models").json()
    assert {model["dataset"] for model in payload["models"]} == {"PaySim", "BankSim", "IEEE-CIS", "AMLSim", "Fraud Graph"}


def test_risk_score_creates_audit_and_retrieves_transaction():
    response = client.post(
        "/api/v1/risk/score",
        json={
            "event_id": "TXN-API-1",
            "dataset": "paysim",
            "amount": 850,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "sender": "C123",
            "receiver": "M456",
            "timestamp": "2026-08-24T12:45:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "TXN-API-1"
    assert body["audit_id"] == "TXN-API-1"
    assert 0 <= body["risk_score"] <= 100
    assert body["timestamp_utc"] is not None
    assert body["timestamp_ist"] is not None
    assert body["signals"]
    assert client.get("/api/v1/risk/transaction/TXN-API-1").status_code == 200
    assert client.get("/api/v1/audit").json()["records"]


def test_risk_score_rejects_unknown_dataset_and_missing_amount():
    assert client.post("/api/v1/risk/score", json={"event_id": "x", "dataset": "unknown", "amount": 1, "transaction_type": "TRANSFER"}).status_code == 422
    assert client.post("/api/v1/risk/score", json={"event_id": "x", "dataset": "banksim", "amount": -5, "transaction_type": "TRANSFER"}).status_code == 422


def test_signal_only_dataset_does_not_invent_model_probability():
    response = client.post(
        "/api/v1/risk/score",
        json={
            "event_id": "AML-API-1",
            "dataset": "amlsim",
            "amount": 100,
            "transaction_type": "TRANSFER",
            "channel": "BANK_TRANSFER",
            "sender": "A1",
            "receiver": "A2",
        },
    )
    assert response.status_code == 200
    assert response.json()["model_probability"] is None


def test_risk_batch_and_metrics():
    response = client.post(
        "/api/v1/risk/batch",
        json={
            "events": [
                {
                    "event_id": "B1",
                    "dataset": "fraud-graph",
                    "amount": 10,
                    "transaction_type": "TRANSFER",
                    "channel": "UPI",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    metrics = client.get("/api/v1/metrics").json()
    assert metrics["transactions_analyzed"] >= 1


def test_valid_prediction():
    reset_demo_state()
    response = client.post("/predict", json=VALID_REQUEST)
    assert response.status_code == 200
    assert set(response.json()) == {
        "fraud_probability",
        "risk_level",
        "decision",
        "threshold",
    }
    assert response.json()["threshold"] == 0.05


def test_invalid_request_is_rejected():
    reset_demo_state()
    invalid = {**VALID_REQUEST, "amount": -1}
    assert client.post("/predict", json=invalid).status_code == 422


def test_post_transaction_fields_are_rejected():
    reset_demo_state()
    invalid = {**VALID_REQUEST, "newbalanceOrig": 0}
    assert client.post("/predict", json=invalid).status_code == 422


def test_accounts_exist_and_returns_balances():
    reset_demo_state()
    response = client.get("/accounts")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(item["account_id"] == "AADI001" for item in payload)
    assert any(item["name"] == "Aadi" for item in payload)


def test_transaction_check_uses_sender_and_receiver_balances():
    reset_demo_state()
    response = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 22,
            "month": "August",
            "time": "15:00",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["oldbalanceOrg"] == 10000.0
    assert body["oldbalanceDest"] == 50000.0
    assert body["sender_id"] == "AADI001"
    assert body["receiver_id"] == "RAHUL001"
    assert body["timestamp_utc"] is not None
    assert body["timestamp_ist"] is not None
    assert "IST" in body["transaction_time"]
    assert body["processing_time_ms"] >= 0.0


def test_amount_greater_than_sender_balance_is_rejected():
    reset_demo_state()
    response = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": 25000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 22,
            "month": "August",
            "time": "15:00",
        },
    )
    assert response.status_code == 422


def test_same_sender_and_receiver_is_rejected():
    reset_demo_state()
    response = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "AADI001",
            "amount": 100,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 22,
            "month": "August",
            "time": "15:00",
        },
    )
    assert response.status_code == 422


def test_unknown_receiver_is_not_found():
    reset_demo_state()
    response = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "UNKNOWN001",
            "amount": 100,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 22,
            "month": "August",
            "time": "15:00",
        },
    )
    assert response.status_code == 404


def test_blocked_transaction_does_not_modify_balances():
    reset_demo_state()
    database.set_account_balance("AADI001", 1000.0)
    sender_before = database.get_account("AADI001")["balance"]
    receiver_before = database.get_account("RAHUL001")["balance"]
    response = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 1,
            "month": "January",
            "time": "00:00",
            "failed_pin_attempts": 4,
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] in ("FLAG", "BLOCK")
    assert database.get_account("AADI001")["balance"] == sender_before
    assert database.get_account("RAHUL001")["balance"] == receiver_before


def test_allowed_transaction_updates_balances_only_after_confirmation():
    reset_demo_state()
    first = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 22,
            "month": "August",
            "time": "15:00",
        },
    )
    assert first.status_code == 200
    tx_id = first.json()["transaction_id"]
    assert database.get_account("AADI001")["balance"] == 10000.0
    confirm = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "COMPLETED"
    assert database.get_account("AADI001")["balance"] == 9000.0
    assert database.get_account("RAHUL001")["balance"] == 51000.0


# ── QA Scenarios 1 to 13 ───────────────────────────────────────────────────

def test_scenario_1_normal_transaction():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 5000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Delhi",
            "failed_pin_attempts": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "LOW"
    assert data["decision"] == "ALLOW"
    assert data["requires_confirmation"] is True
    assert data["risk_signals"]["device_changed"] is False
    assert data["risk_signals"]["unusual_location"] is False


def test_scenario_2_new_device_large_transaction():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 100000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_NEW_999",
            "location": "Delhi",
            "failed_pin_attempts": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["device_changed"] is True
    assert data["risk_signals"]["unusually_large_transaction"] is True
    assert data["risk_level"] in ["MEDIUM", "HIGH", "CRITICAL"]


def test_scenario_3_multiple_wrong_pin_large_transaction():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 100000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Delhi",
            "failed_pin_attempts": 4,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["multiple_failed_pin_attempts"] is True
    assert data["decision"] == "BLOCK"


def test_scenario_4_unusual_location():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 75000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Mumbai",
            "failed_pin_attempts": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["unusual_location"] is True


def test_scenario_5_inactive_account():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "INACTIVE001",
            "receiver_id": "PRIYA001",
            "amount": 100000,
            "transaction_type": "TRANSFER",
            "channel": "BANK_TRANSFER",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_OLD_DORMANT",
            "location": "Kolkata",
            "failed_pin_attempts": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["inactive_account"] is True


def test_scenario_6_multiple_suspicious_signals_flagged():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 100000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "date": 24,
            "month": "August",
            "time": "10:00",
            "device_id": "DEVICE_SUSPICIOUS_UNKNOWN",
            "location": "Dubai",
            "failed_pin_attempts": 4,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["decision"] == "BLOCK"


def test_scenario_7_atm_withdrawal_anomaly():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "AMIT001",
            "amount": 50000,
            "transaction_type": "CASH_OUT",
            "channel": "ATM",
            "time": "23:30",
            "location": "Chandigarh",
            "failed_pin_attempts": 2,
        },
    )
    # Different accounts required for P2P but let's test with receiver PRIYA001
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 50000,
            "transaction_type": "CASH_OUT",
            "channel": "ATM",
            "time": "23:30",
            "location": "Chandigarh",
            "failed_pin_attempts": 2,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == "ATM"
    assert data["risk_signals"]["atm_anomaly"] is True


def test_scenario_8_card_payment_new_location():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 40000,
            "transaction_type": "PAYMENT",
            "channel": "CREDIT_CARD",
            "time": "14:00",
            "location": "London",
            "device_id": "DEVICE_AMIT_01",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["unusual_location"] is True
    assert data["risk_signals"]["card_anomaly"] is True


def test_scenario_9_upi_new_device_new_beneficiary():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "INACTIVE001",
            "amount": 80000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "11:00",
            "device_id": "DEVICE_NEW_UPI",
            "is_new_beneficiary": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["device_changed"] is True
    assert data["risk_signals"]["new_beneficiary"] is True


def test_scenario_10_impossible_travel():
    reset_demo_state()
    # 1. First transaction in Delhi (confirmed/completed)
    res1 = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 2000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "location": "Delhi",
            "time": "10:00",
        },
    )
    assert res1.status_code == 200
    tx1_id = res1.json()["transaction_id"]
    client.post("/transactions/confirm", json={"transaction_id": tx1_id})

    # 2. Immediate second transaction from Mumbai
    res2 = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 2500,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "location": "Mumbai",
            "time": "10:05",
        },
    )
    assert res2.status_code == 200
    data = res2.json()
    assert data["risk_signals"]["impossible_travel"] is True
    assert data["decision"] == "BLOCK"


def test_scenario_11_balance_drain():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "PRIYA001",
            "receiver_id": "AMIT001",
            "amount": 24000,  # 24k out of 25k (96%)
            "transaction_type": "TRANSFER",
            "channel": "BANK_TRANSFER",
            "time": "12:00",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["balance_drain"] is True


def test_scenario_12_high_velocity_transactions():
    reset_demo_state()
    for _ in range(3):
        client.post(
            "/transactions/check",
            json={
                "sender_id": "RAHUL001",
                "receiver_id": "PRIYA001",
                "amount": 1000,
                "transaction_type": "TRANSFER",
                "channel": "UPI",
                "time": f"12:{_}:00",
            },
        )
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "RAHUL001",
            "receiver_id": "PRIYA001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:05:00",
        },
    )
    assert res.status_code == 200
    assert res.json()["risk_signals"]["high_velocity"] is True


def test_scenario_13_3am_high_value_transaction():
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 90000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "03:00",
            "location": "Delhi",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["unusual_time"] is True
    assert data["risk_signals"]["unusually_large_transaction"] is True


# ── Final Verification Scenario 35 ─────────────────────────────────────────

def test_final_verification_scenario_35():
    """
    Scenario:
    Merchant normally transacts in Delhi (₹2,000–₹10,000, DEVICE_MERCHANT_01, 09:00–23:00).
    Incoming:
    Time: 03:00 AM IST
    Channel: UPI
    Amount: ₹300,000 (with balance_override ₹400,000)
    Device: NEW DEVICE
    Location: Mumbai
    Auth: 3 failed attempts
    Beneficiary: NEW
    """
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 300000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "03:00",
            "device_id": "DEVICE_NEW_UNRECOGNIZED_01",
            "location": "Mumbai",
            "failed_pin_attempts": 3,
            "is_new_beneficiary": True,
            "balance_override": 400000.0,
        },
    )
    assert res.status_code == 200
    data = res.json()

    # All signals must be detected
    signals = data["risk_signals"]
    assert signals["device_changed"] is True
    assert signals["unusual_location"] is True
    assert signals["unusual_time"] is True
    assert signals["multiple_failed_pin_attempts"] is True
    assert signals["new_beneficiary"] is True
    assert signals["unusually_large_transaction"] is True
    assert signals["balance_drain"] is True

    # Final result must be CRITICAL and BLOCK
    assert data["risk_level"] == "CRITICAL"
    assert data["decision"] == "BLOCK"
    assert data["risk_score"] >= 80.0
    assert len(data["reasons"]) >= 5


def test_duplicate_transaction_only_blocks_pending():
    reset_demo_state()
    tx_payload = {
        "sender_id": "AADI001",
        "receiver_id": "RAHUL001",
        "amount": 1000,
        "transaction_type": "TRANSFER",
        "channel": "UPI",
        "date": 22,
        "month": "August",
        "time": "15:00",
    }
    # 1. First submission succeeds (PENDING)
    first_res = client.post("/transactions/check", json=tx_payload)
    assert first_res.status_code == 200
    tx_id = first_res.json()["transaction_id"]

    # 2. Duplicate while PENDING is rejected with 422
    dup_res = client.post("/transactions/check", json=tx_payload)
    assert dup_res.status_code == 422
    assert "Duplicate transaction submission detected" in dup_res.json()["detail"]

    # 3. Confirm first transaction to make it COMPLETED
    confirm_res = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "COMPLETED"

    # 4. Same payload after completion is NO LONGER blocked as duplicate
    second_res = client.post("/transactions/check", json=tx_payload)
    assert second_res.status_code == 200
    assert second_res.json()["transaction_id"] != tx_id


# ── Phase 8 Explicit Verification Suite (Tests 1 - 14) ──────────────────────

def test_phase8_test_1_normal_upi():
    """TEST 1: Normal UPI transaction -> LOW / ALLOW"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 2000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Delhi",
            "failed_pin_attempts": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "LOW"
    assert data["decision"] == "ALLOW"
    assert 0.0 <= data["risk_score"] < 30.0


def test_phase8_test_2_large_unusual_transaction():
    """TEST 2: Large unusual transaction -> risk increases"""
    reset_demo_state()
    # Baseline normal
    res_normal = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 2000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Delhi",
        },
    )
    # Large unusual
    res_large = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 90000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
            "device_id": "DEVICE_AMIT_01",
            "location": "Delhi",
        },
    )
    assert res_large.status_code == 200
    assert res_large.json()["risk_score"] > res_normal.json()["risk_score"]
    assert res_large.json()["risk_signals"]["unusually_large_transaction"] is True


def test_phase8_test_3_new_device_plus_failed_pins():
    """TEST 3: New device + failed PINs -> risk increases significantly"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 10000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
            "device_id": "DEVICE_UNKNOWN_NEW_99",
            "location": "Delhi",
            "failed_pin_attempts": 3,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["risk_signals"]["device_changed"] is True
    assert data["risk_signals"]["multiple_failed_pin_attempts"] is True
    assert data["risk_score"] >= 60.0
    assert data["decision"] == "BLOCK"


def test_phase8_test_4_impossible_travel():
    """TEST 4: Impossible travel -> HIGH/CRITICAL and BLOCK"""
    reset_demo_state()
    # 1. Delhi txn
    res1 = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "location": "Delhi",
            "time": "10:00",
        },
    )
    tx1_id = res1.json()["transaction_id"]
    client.post("/transactions/confirm", json={"transaction_id": tx1_id})

    # 2. Mumbai txn immediately after
    res2 = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 1000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "location": "Mumbai",
            "time": "10:05",
        },
    )
    assert res2.status_code == 200
    data = res2.json()
    assert data["risk_signals"]["impossible_travel"] is True
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["decision"] == "BLOCK"


def test_phase8_test_5_atm_transaction_no_receiver():
    """TEST 5: ATM transaction -> no receiver-account requirement"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "amount": 5000,
            "channel": "ATM",
            "time": "12:00",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == "ATM"
    assert data["transaction_type"] == "CASH_OUT"
    assert data["receiver_id"] == "SYSTEM"


def test_phase8_test_6_cash_deposit_transaction_type():
    """TEST 6: Cash deposit -> correct transaction type (CASH_IN)"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "amount": 5000,
            "channel": "CASH_DEPOSIT",
            "time": "12:00",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == "CASH_DEPOSIT"
    assert data["transaction_type"] == "CASH_IN"


def test_phase8_test_7_card_transaction_type():
    """TEST 7: Card transaction -> correct transaction type (PAYMENT)"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "amount": 2500,
            "channel": "DEBIT_CARD",
            "time": "12:00",
            "merchant_id": "MERCH_AMAZON_01",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["channel"] == "DEBIT_CARD"
    assert data["transaction_type"] == "PAYMENT"


def test_phase8_test_8_insufficient_balance():
    """TEST 8: Insufficient balance -> 422/error, no transaction created"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",  # balance = 10000
            "receiver_id": "RAHUL001",
            "amount": 50000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
        },
    )
    assert res.status_code == 422
    assert "exceeds sender balance" in res.json()["detail"].lower()


def test_phase8_test_9_duplicate_transaction_rejected():
    """TEST 9: Duplicate transaction -> rejected"""
    reset_demo_state()
    payload = {
        "sender_id": "AMIT001",
        "receiver_id": "PRIYA001",
        "amount": 3000,
        "transaction_type": "TRANSFER",
        "channel": "UPI",
        "date": 25,
        "month": "August",
        "time": "14:30",
    }
    res1 = client.post("/transactions/check", json=payload)
    assert res1.status_code == 200
    res2 = client.post("/transactions/check", json=payload)
    assert res2.status_code == 422
    assert "duplicate" in res2.json()["detail"].lower()


def test_phase8_test_10_blocked_transaction_confirmation():
    """TEST 10: Blocked transaction confirmation -> cannot complete"""
    reset_demo_state()
    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AMIT001",
            "receiver_id": "PRIYA001",
            "amount": 100000,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "03:00",
            "failed_pin_attempts": 4,
            "device_id": "DEVICE_UNKNOWN_NEW",
        },
    )
    assert res.status_code == 200
    tx_id = res.json()["transaction_id"]
    assert res.json()["decision"] == "BLOCK"

    confirm_res = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "FLAGGED"
    assert "blocked" in confirm_res.json()["message"].lower()


def test_phase8_test_11_allowed_transaction_confirmation():
    """TEST 11: Allowed transaction confirmation -> sender balance decreases, receiver balance increases"""
    reset_demo_state()
    sender_init = database.get_account("AADI001")["balance"]
    receiver_init = database.get_account("RAHUL001")["balance"]
    amt = 1500.0

    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": amt,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
        },
    )
    assert res.status_code == 200
    tx_id = res.json()["transaction_id"]

    confirm_res = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "COMPLETED"

    assert database.get_account("AADI001")["balance"] == sender_init - amt
    assert database.get_account("RAHUL001")["balance"] == receiver_init + amt


def test_phase8_test_12_double_confirmation():
    """TEST 12: Double confirmation -> does not debit twice"""
    reset_demo_state()
    sender_init = database.get_account("AADI001")["balance"]
    receiver_init = database.get_account("RAHUL001")["balance"]
    amt = 1000.0

    res = client.post(
        "/transactions/check",
        json={
            "sender_id": "AADI001",
            "receiver_id": "RAHUL001",
            "amount": amt,
            "transaction_type": "TRANSFER",
            "channel": "UPI",
            "time": "12:00",
        },
    )
    tx_id = res.json()["transaction_id"]

    # First confirm
    c1 = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert c1.status_code == 200
    assert c1.json()["status"] == "COMPLETED"
    bal_after_first = database.get_account("AADI001")["balance"]
    assert bal_after_first == sender_init - amt

    # Second confirm (must be idempotent, not debit again)
    c2 = client.post("/transactions/confirm", json={"transaction_id": tx_id})
    assert c2.status_code == 200
    assert c2.json()["status"] == "COMPLETED"
    assert "already completed" in c2.json()["message"].lower()
    assert database.get_account("AADI001")["balance"] == bal_after_first


def test_phase8_test_13_missing_mongodb_handled_gracefully():
    """TEST 13: Missing MongoDB -> application handles failure gracefully"""
    # Create isolated database instance with invalid mongo URI
    db = Database()
    db._client = None
    assert db.available is False
    accounts = db.list_accounts()
    assert len(accounts) >= 4
    stats = db.stats()
    assert "total_transactions" in stats


def test_phase8_test_14_missing_ml_model_non_crashing():
    """TEST 14: Missing ML model -> backend does not crash"""
    from backend.model_service import ModelService
    from backend.schemas import PredictionRequest
    
    # Instantiate with non-existent path
    service = ModelService(model_path="non_existent_path.json")
    assert service.is_loaded is False
    assert service.model is None
    
    # Predict must succeed via fallback
    pred = service.predict(
        PredictionRequest(
            amount=5000.0,
            oldbalanceOrg=10000.0,
            oldbalanceDest=5000.0,
            type="TRANSFER",
            hour=12,
            day=10,
        )
    )
    assert "fraud_probability" in pred
    assert pred["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert pred["decision"] in ("ALLOW", "REVIEW", "BLOCK")
