import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4
import time as pytime
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .database import Database
from .model_service import ModelService
from .schemas import (
    Account,
    CASH_CHANNELS,
    CARD_CHANNELS,
    NO_RECEIVER_CHANNELS,
    SYSTEM_RECEIVER,
    DetectedSignalItem,
    HistoryResponse,
    PredictionRecord,
    PredictionRequest,
    PredictionResponse,
    StatsResponse,
    ModelsResponse,
    ModelStatus,
    RiskBatchRequest,
    RiskBatchResponse,
    RiskScoreRequest,
    RiskScoreResponse,
    RiskSignalResponse,
    TransactionCheckRequest,
    TransactionCheckResponse,
    TransactionConfirmRequest,
    TransactionConfirmResponse,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
SRC_PATH = str(PROJECT_ROOT / "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
from risk_engine import RiskEngine
from risk_engine.adapters import AMLSimAdapter, BankSimAdapter, FraudGraphAdapter, IEEECISAdapter, PaySimAdapter

app = FastAPI(title="PaySim Fraud Detector API", version="2.0.0")

# Support custom CORS origins via env var or default comprehensive list
cors_origins_env = os.getenv("CORS_ORIGINS", "")
custom_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://fraud-detection-0w6x.onrender.com",
]
allowed_origins = list(dict.fromkeys(default_origins + custom_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com|https://.*\.vercel\.app|https://.*\.netlify\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Fraud Detection API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "models": "/api/v1/models",
    }

model_service = ModelService()
database = Database()
risk_engine = RiskEngine(medium_threshold=0.30, high_threshold=0.60, critical_threshold=0.80)
ADAPTERS = {
    "paysim": PaySimAdapter(),
    "banksim": BankSimAdapter(),
    "ieee-cis": IEEECISAdapter(),
    "amlsim": AMLSimAdapter(),
    "fraud-graph": FraudGraphAdapter(),
}

IST = timezone(timedelta(hours=5, minutes=30))

MONTHS = {
    "January": 31,
    "February": 29,
    "March": 31,
    "April": 30,
    "May": 31,
    "June": 30,
    "July": 31,
    "August": 31,
    "September": 30,
    "October": 31,
    "November": 30,
    "December": 31,
}


def _get_timestamp_bundle(now_utc: datetime = None, custom_time: str = None) -> dict[str, Any]:
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    now_ist = now_utc.astimezone(IST)
    if custom_time and ":" in str(custom_time):
        time_clean = str(custom_time).strip()
        txn_time = f"{time_clean} IST" if not time_clean.endswith("IST") else time_clean
    else:
        txn_time = now_ist.strftime("%I:%M:%S %p IST")

    return {
        "timestamp_utc": now_utc.isoformat(),
        "timestamp_ist": now_ist.isoformat(),
        "transaction_time": txn_time,
        "processed_at": now_ist.strftime("%I:%M:%S %p IST"),
        "dt_utc": now_utc,
        "dt_ist": now_ist,
    }


def _parse_time_to_hour(raw_time: str | None) -> int:
    if raw_time is None or not str(raw_time).strip():
        return datetime.now(IST).hour
    value = str(raw_time).strip()
    try:
        hour = int(value.split(":", 1)[0])
        if 0 <= hour <= 23:
            return hour
    except ValueError:
        pass
    normalized = value.lower().replace(" ", "")
    for fmt in ("%I:%M%p", "%H:%M", "%I%p"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.hour
        except ValueError:
            pass
    try:
        dt = datetime.strptime(normalized, "%I:%M%p")
        return dt.hour
    except ValueError as exc:
        raise ValueError("Time must be a valid 24-hour or AM/PM value.") from exc


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model_service.model is not None}


@app.get("/accounts", response_model=list[Account])
def accounts():
    return [Account(**account) for account in database.list_accounts()]


@app.get("/accounts/{account_id}", response_model=Account)
def account_detail(account_id: str):
    account = database.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return Account(**account)


@app.post("/predict", response_model=PredictionResponse)
def predict(transaction: PredictionRequest):
    prediction = model_service.predict(transaction)
    now_utc = datetime.now(timezone.utc)
    ts_bundle = _get_timestamp_bundle(now_utc)
    try:
        database.insert_prediction(
            {
                "timestamp": now_utc,
                "timestamp_utc": ts_bundle["timestamp_utc"],
                "timestamp_ist": ts_bundle["timestamp_ist"],
                "transaction_time": f"{transaction.hour:02d}:00 IST",
                "amount": float(transaction.amount),
                "transaction_type": transaction.type,
                "channel": "UPI",
                "date": int(transaction.day),
                "month": "August",
                "time": f"{transaction.hour:02d}:00",
                "fraud_probability": float(prediction["fraud_probability"]),
                "risk_score": round(float(prediction["fraud_probability"]) * 100.0, 1),
                "risk_level": prediction["risk_level"],
                "decision": prediction["decision"],
            }
        )
    except Exception:
        pass
    return prediction


@app.post("/transactions/check", response_model=TransactionCheckResponse)
def transaction_check(request: TransactionCheckRequest):
    t_start = pytime.perf_counter()

    channel = request.channel
    is_no_receiver_channel = channel in NO_RECEIVER_CHANNELS
    is_cash_channel = channel in CASH_CHANNELS
    is_card_channel = channel in CARD_CHANNELS

    # ── Channel-specific transaction type coercion ────────────────────────────
    # Coerce transaction_type to sensible defaults per channel before any logic.
    if is_cash_channel and channel == "CASH_DEPOSIT":
        request.transaction_type = "CASH_IN"
    elif is_cash_channel:
        # ATM and CASH_WITHDRAWAL must always be CASH_OUT
        if request.transaction_type not in ("CASH_OUT", "DEBIT"):
            request.transaction_type = "CASH_OUT"
    elif is_card_channel:
        # Card channels are always PAYMENT
        if request.transaction_type not in ("PAYMENT", "DEBIT"):
            request.transaction_type = "PAYMENT"
    elif channel in ("UPI", "BANK_TRANSFER", "NET_BANKING"):
        # P2P / Transfer channels
        if request.transaction_type not in ("TRANSFER", "PAYMENT"):
            request.transaction_type = "TRANSFER"
    elif channel == "WALLET":
        if request.transaction_type not in ("PAYMENT", "TRANSFER"):
            request.transaction_type = "PAYMENT"

    sender = database.get_account(request.sender_id)
    if sender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sender account not found")

    # For channels with no real receiver (ATM / Card), use a system placeholder.
    # For P2P / beneficiary channels, require a real receiver account.
    if is_no_receiver_channel or request.receiver_id in (SYSTEM_RECEIVER, "", None):
        # Cash/card channel: no real receiver needed
        receiver = {"name": "System", "balance": 0.0, "account_id": SYSTEM_RECEIVER}
    else:
        receiver = database.get_account(request.receiver_id)
        if receiver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver account not found")
        if request.sender_id == request.receiver_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sender and receiver must be different accounts")

    if request.amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Amount must be greater than zero")

    sender_balance = float(request.balance_override if request.balance_override is not None else sender["balance"])
    receiver_balance = float(receiver["balance"])

    if request.amount > sender_balance:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Amount exceeds sender balance")

    # Temporal context auto-resolution in IST/UTC
    now_utc = datetime.now(timezone.utc)
    ts_bundle = _get_timestamp_bundle(now_utc, custom_time=request.time)

    date_val = request.date if request.date is not None else ts_bundle["dt_ist"].day
    month_val = request.month if request.month is not None else ts_bundle["dt_ist"].strftime("%B")
    time_val = request.time if request.time is not None else ts_bundle["dt_ist"].strftime("%H:%M")

    if month_val not in MONTHS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Month must be a valid month name")
    if date_val < 1 or date_val > MONTHS[month_val]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Date is not valid for the selected month")
    try:
        hour = _parse_time_to_hour(time_val)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # Automatic Duplicate Pending Transaction Check
    if database.has_duplicate_transaction(
        request.sender_id,
        request.receiver_id,
        request.amount,
        request.transaction_type,
        date_val,
        month_val,
        time_val,
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate transaction submission detected")

    # Auto-derive location if omitted
    sender_behavior = database.get_account_behavior(request.sender_id)
    derived_location = request.location or sender_behavior.get("normal_location", "Delhi")

    # Auto-derive auth failure counts
    recent_auth_fails = database.get_recent_auth_failures(request.sender_id, minutes=30)
    failed_pins = request.failed_pin_attempts if request.failed_pin_attempts is not None else recent_auth_fails
    wrong_pin_count = int(failed_pins or 0)

    # -------------------------------------------------------------
    # ML XGBoost Base Inference
    # -------------------------------------------------------------
    feature_request = PredictionRequest(
        amount=float(request.amount),
        oldbalanceOrg=sender_balance,
        oldbalanceDest=receiver_balance,
        type=request.transaction_type,
        hour=hour,
        day=min(int(date_val), 30),
    )
    prediction = model_service.predict(feature_request)
    base_prob = float(prediction["fraud_probability"])

    # -------------------------------------------------------------
    # Multi-Signal Behavioral & Channel Context Analysis
    # -------------------------------------------------------------
    device_changed = database.is_device_changed(request.sender_id, request.device_id)
    multiple_failed_pins = wrong_pin_count >= 3
    unusual_location = database.is_unusual_location(request.sender_id, derived_location)
    inactive_account = database.is_account_inactive(request.sender_id)
    unusually_large = database.is_unusually_large_transaction(request.sender_id, request.amount)
    unusual_time = database.is_unusual_time(request.sender_id, hour)
    balance_drain = database.is_balance_drain(request.sender_id, request.amount, balance_override=sender_balance)
    new_beneficiary = request.is_new_beneficiary if request.is_new_beneficiary is not None else database.is_new_beneficiary(request.sender_id, request.receiver_id)
    high_velocity, impossible_travel = database.detect_velocity_and_impossible_travel(request.sender_id, derived_location)

    # Channel-specific heuristics (channel already set at top of function)
    is_atm_anomaly = channel in ("ATM", "CASH_WITHDRAWAL") and (request.amount >= 20000 or wrong_pin_count >= 2 or unusual_location)
    is_card_anomaly = channel in CARD_CHANNELS and (unusual_location or unusually_large or wrong_pin_count > 0)
    is_cash_deposit_anomaly = channel == "CASH_DEPOSIT" and (inactive_account or unusually_large)
    is_upi_anomaly = channel == "UPI" and (device_changed or new_beneficiary or multiple_failed_pins)

    # Context score accumulation
    context_delta = 0.0
    signal_count = 0

    if device_changed:
        context_delta += 0.20
        signal_count += 1
    if wrong_pin_count >= 4:
        context_delta += 0.40
        signal_count += 1
    elif wrong_pin_count >= 3:
        context_delta += 0.25
        signal_count += 1
    elif wrong_pin_count > 0:
        context_delta += 0.10 * wrong_pin_count
        signal_count += 1
    if unusual_location:
        context_delta += 0.18
        signal_count += 1
    if inactive_account:
        context_delta += 0.20
        signal_count += 1
    if unusually_large:
        context_delta += 0.20
        signal_count += 1
    if unusual_time:
        context_delta += 0.15
        signal_count += 1
    if balance_drain:
        context_delta += 0.20
        signal_count += 1
    if new_beneficiary:
        context_delta += 0.15
        signal_count += 1
    if high_velocity:
        context_delta += 0.25
        signal_count += 1
    if impossible_travel:
        context_delta += 0.35
        signal_count += 1
    if is_atm_anomaly:
        context_delta += 0.15
    if is_card_anomaly:
        context_delta += 0.15
    if is_cash_deposit_anomaly:
        context_delta += 0.20

    # Multi-signal risk synergy boost
    if signal_count >= 5 or (device_changed and multiple_failed_pins and unusual_time and unusually_large and balance_drain):
        context_delta += 0.35
    elif signal_count >= 3:
        context_delta += 0.15

    raw_combined = min(1.0, max(0.0, base_prob * 0.40 + context_delta))
    # If severe risk combination triggers, ensure score enters critical/high band
    if (signal_count >= 4 and unusually_large) or impossible_travel or (multiple_failed_pins and device_changed):
        raw_combined = max(0.82, raw_combined)
    elif signal_count >= 3 or (wrong_pin_count >= 3) or (device_changed and unusually_large):
        raw_combined = max(0.65, raw_combined)

    combined_score = round(raw_combined, 4)
    risk_score_100 = round(combined_score * 100.0, 1)

    # Canonical Decision Matrix (0-29 LOW/ALLOW, 30-59 MEDIUM/REVIEW, 60-79 HIGH/BLOCK, 80-100 CRITICAL/BLOCK)
    if risk_score_100 >= 80.0:
        risk_level = "CRITICAL"
        decision = "BLOCK"
    elif risk_score_100 >= 60.0 or impossible_travel:
        risk_level = "HIGH"
        decision = "BLOCK"
    elif risk_score_100 >= 30.0:
        risk_level = "MEDIUM"
        decision = "REVIEW"
    else:
        risk_level = "LOW"
        decision = "ALLOW"

    # Risk signals dictionary
    risk_signals = {
        "device_changed": device_changed,
        "multiple_failed_pin_attempts": multiple_failed_pins or (wrong_pin_count > 0),
        "unusual_location": unusual_location,
        "inactive_account": inactive_account,
        "unusually_large_transaction": unusually_large,
        "unusual_time": unusual_time,
        "balance_drain": balance_drain,
        "new_beneficiary": new_beneficiary,
        "high_velocity": high_velocity,
        "impossible_travel": impossible_travel,
        "atm_anomaly": is_atm_anomaly,
        "card_anomaly": is_card_anomaly,
        "cash_deposit_anomaly": is_cash_deposit_anomaly,
    }

    # Rich Detected Signals list
    detected_signals = [
        DetectedSignalItem(
            name="Device Identity",
            status="New Device Detected" if device_changed else "Known Device",
            alert=device_changed,
            category="device",
            signal_code="NEW_DEVICE" if device_changed else "KNOWN_DEVICE",
        ),
        DetectedSignalItem(
            name="Authentication Context",
            status=f"{wrong_pin_count} Failed Attempts" if wrong_pin_count > 0 else "Normal Authentication",
            alert=wrong_pin_count > 0,
            category="auth",
            signal_code="MULTIPLE_FAILED_AUTH" if wrong_pin_count >= 3 else "AUTH_ANOMALY" if wrong_pin_count > 0 else "NORMAL_AUTH",
        ),
        DetectedSignalItem(
            name="Geographic Context",
            status=f"Unusual Location ({derived_location})" if unusual_location else f"Normal Location ({derived_location})",
            alert=unusual_location or impossible_travel,
            category="location",
            signal_code="IMPOSSIBLE_TRAVEL" if impossible_travel else "UNUSUAL_LOCATION" if unusual_location else "NORMAL_LOCATION",
        ),
        DetectedSignalItem(
            name="Beneficiary Relationship",
            status="New / Unseen Beneficiary" if new_beneficiary else "Established Beneficiary",
            alert=new_beneficiary,
            category="beneficiary",
            signal_code="NEW_BENEFICIARY" if new_beneficiary else "KNOWN_BENEFICIARY",
        ),
        DetectedSignalItem(
            name="Amount vs Baseline",
            status="Significantly Above Historical Average" if unusually_large else "Within Expected Range",
            alert=unusually_large,
            category="amount",
            signal_code="AMOUNT_ANOMALY" if unusually_large else "NORMAL_AMOUNT",
        ),
        DetectedSignalItem(
            name="Balance Consumption",
            status="Consumes >75% of Available Balance" if balance_drain else "Healthy Balance Retention",
            alert=balance_drain,
            category="balance",
            signal_code="BALANCE_DRAIN" if balance_drain else "NORMAL_BALANCE",
        ),
        DetectedSignalItem(
            name="Account Activity State",
            status="Dormant Account Suddenly Active" if inactive_account else "Active Account",
            alert=inactive_account,
            category="dormancy",
            signal_code="DORMANT_ACCOUNT_REACTIVATION" if inactive_account else "ACTIVE_ACCOUNT",
        ),
        DetectedSignalItem(
            name="Activity Window",
            status=f"Outside Normal Hours ({hour:02d}:00)" if unusual_time else "Within Normal Hours",
            alert=unusual_time,
            category="temporal",
            signal_code="UNUSUAL_TIME" if unusual_time else "NORMAL_TIME",
        ),
        DetectedSignalItem(
            name="Transaction Velocity",
            status="High Velocity Detected (>3 txns/2m)" if high_velocity else "Normal Transaction Velocity",
            alert=high_velocity,
            category="velocity",
            signal_code="HIGH_VELOCITY" if high_velocity else "NORMAL_VELOCITY",
        ),
    ]

    # Filter out signals that are irrelevant for the current channel.
    # e.g. Beneficiary Relationship is irrelevant for ATM / Card channels.
    _is_no_recv = channel in NO_RECEIVER_CHANNELS
    if _is_no_recv:
        detected_signals = [
            s for s in detected_signals
            if s.category not in ("beneficiary",)
        ]

    # Explainable reasons
    reasons = []
    if unusual_time:
        reasons.append(f"Transaction occurred outside normal activity hours ({hour:02d}:00 IST)")
    if device_changed:
        reasons.append("New / previously unseen device was used for this transaction")
    elif request.device_id:
        reasons.append("Known device")
    if wrong_pin_count >= 3:
        reasons.append(f"Multiple authentication failures ({wrong_pin_count} failed attempts) preceded transaction")
    elif wrong_pin_count > 0:
        reasons.append(f"{wrong_pin_count} failed authentication attempt detected before transaction")
    else:
        reasons.append("No failed PIN attempts")
    if new_beneficiary:
        reasons.append("Payment directed to a new, previously unrecorded beneficiary")
    if unusually_large:
        reasons.append("Transaction amount is significantly above the historical baseline")
    if balance_drain:
        reasons.append("Transaction consumes most of the available account balance")
    if impossible_travel:
        reasons.append("Impossible travel detected — multiple geographic locations in rapid succession")
    elif unusual_location:
        reasons.append(f"Transaction location ({derived_location}) differs from normal activity")
    if inactive_account:
        reasons.append("Account was inactive/dormant before this transaction")
    if high_velocity:
        reasons.append("High transaction velocity detected within a 2-minute window")
    if is_atm_anomaly:
        reasons.append("ATM withdrawal anomaly detected on high-value cash transaction")
    if not reasons:
        reasons.append("Transaction matches normal behavioral baseline across all signals")

    generated_id = uuid4().hex
    t_end = pytime.perf_counter()
    processing_ms = round((t_end - t_start) * 1000.0, 2)

    # Insert into database
    transaction_id = database.insert_transaction_record(
        {
            "transaction_id": generated_id,
            "timestamp": now_utc,
            "timestamp_utc": ts_bundle["timestamp_utc"],
            "timestamp_ist": ts_bundle["timestamp_ist"],
            "transaction_time": ts_bundle["transaction_time"],
            "sender": request.sender_id,
            "receiver": request.receiver_id,
            "amount": float(request.amount),
            "transaction_type": request.transaction_type,
            "channel": channel,
            "date": date_val,
            "month": month_val,
            "time": time_val,
            "location": derived_location,
            "decision": decision,
            "risk_score": risk_score_100,
            "risk_level": risk_level,
            "status": "PENDING" if decision == "ALLOW" else "FLAGGED",
            "completed": False,
            "device_id": request.device_id,
            "failed_pin_attempts": wrong_pin_count,
            "risk_signals": risk_signals,
            "risk_reasons": reasons,
        }
    )

    # Persist prediction record
    try:
        database.insert_prediction(
            {
                "timestamp": now_utc,
                "timestamp_utc": ts_bundle["timestamp_utc"],
                "timestamp_ist": ts_bundle["timestamp_ist"],
                "transaction_time": ts_bundle["transaction_time"],
                "amount": float(request.amount),
                "transaction_type": request.transaction_type,
                "channel": channel,
                "date": int(date_val),
                "month": month_val,
                "time": time_val,
                "fraud_probability": combined_score,
                "risk_score": risk_score_100,
                "risk_level": risk_level,
                "decision": decision,
            }
        )
    except Exception:
        pass

    # Feed canonical event into central risk engine audit trail
    try:
        row_data = {
            "transaction_id": generated_id,
            "amount": request.amount,
            "type": request.transaction_type,
            "channel": channel,
            "nameOrig": request.sender_id,
            "nameDest": request.receiver_id,
            "oldbalanceOrg": sender_balance,
            "oldbalanceDest": receiver_balance,
            "timestamp": ts_bundle["timestamp_utc"],
        }
        engine_event = ADAPTERS["paysim"].adapt(row_data, {"fraud_probability": combined_score, "model_used": "paysim-xgb-realtime"})
        engine_event.risk_score = risk_score_100
        engine_event.risk_level = risk_level
        engine_event.decision = decision
        risk_engine.assess(engine_event)
    except Exception:
        pass

    status_value = "FLAGGED" if decision == "BLOCK" else "REVIEW" if decision == "REVIEW" else "ALLOWED"
    if decision == "BLOCK":
        message = "High risk security anomaly detected. Transaction blocked by Fraud Engine."
    elif decision == "REVIEW":
        message = "Medium risk detected. Transaction flagged for security review."
    else:
        message = "Security risk evaluated. Transaction allowed and ready for confirmation."

    return TransactionCheckResponse(
        transaction_id=str(transaction_id),
        timestamp_utc=ts_bundle["timestamp_utc"],
        timestamp_ist=ts_bundle["timestamp_ist"],
        transaction_time=ts_bundle["transaction_time"],
        processed_at=ts_bundle["processed_at"],
        processing_time_ms=processing_ms,
        status=status_value,
        sender_id=request.sender_id,
        receiver_id=request.receiver_id,
        sender_name=str(sender["name"]),
        receiver_name=str(receiver["name"]),
        amount=float(request.amount),
        currency=request.currency,
        channel=channel,
        transaction_type=request.transaction_type,
        order_id=request.order_id,
        merchant_id=request.merchant_id,
        oldbalanceOrg=sender_balance,
        oldbalanceDest=receiver_balance,
        ml_probability=round(base_prob, 4),
        fraud_probability=combined_score,
        base_probability=round(base_prob, 4),
        contextual_score=round(context_delta, 4),
        context_score=round(context_delta, 4),
        risk_score=risk_score_100,
        risk_level=risk_level,
        decision=decision,
        threshold=0.60,
        requires_confirmation=decision == "ALLOW",
        message=message,
        model="PaySim XGBoost + Behavioral Engine",
        risk_signals=risk_signals,
        detected_signals=detected_signals,
        reasons=reasons,
        risk_reasons=reasons,
        engine_metadata={
            "engine": "PaySim-Guard-v2",
            "model_status": "Ready",
            "active_model": "PaySim XGBoost Realtime",
            "channel": channel,
            "evaluated_signals": len(detected_signals),
            "triggered_signals": sum(1 for s in detected_signals if s.alert),
        },
    )


@app.post("/transactions/confirm", response_model=TransactionConfirmResponse)
def transaction_confirm(request: TransactionConfirmRequest):
    record = database.get_transaction(request.transaction_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    rec_channel = record.get("channel", "UPI")
    is_no_recv = rec_channel in NO_RECEIVER_CHANNELS or record.get("receiver") == SYSTEM_RECEIVER

    sender = database.get_account(record["sender"])
    if sender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction accounts no longer exist")

    # For ATM/card channels, receiver may be a SYSTEM placeholder — skip DB lookup.
    if is_no_recv:
        receiver = {"name": "System", "balance": 0.0, "account_id": SYSTEM_RECEIVER}
    else:
        receiver = database.get_account(record["receiver"])
        if receiver is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction accounts no longer exist")

    if record.get("decision") in ("FLAG", "BLOCK"):
        database.save_transaction(request.transaction_id, {"status": "FLAGGED", "completed": False})
        return TransactionConfirmResponse(
            transaction_id=request.transaction_id,
            channel=rec_channel,
            status="FLAGGED",
            message="Transaction was blocked by the risk engine and cannot be completed.",
        )
    if record.get("status") == "COMPLETED":
        return TransactionConfirmResponse(
            transaction_id=request.transaction_id,
            channel=rec_channel,
            status="COMPLETED",
            message="Transaction already completed.",
            sender_id=record["sender"],
            receiver_id=record["receiver"],
            sender_balance=float(sender["balance"]),
            receiver_balance=None if is_no_recv else float(receiver["balance"]),
        )

    amount = float(record["amount"])
    if amount > float(sender["balance"]):
        database.save_transaction(request.transaction_id, {"status": "REJECTED", "completed": False})
        return TransactionConfirmResponse(
            transaction_id=request.transaction_id,
            channel=rec_channel,
            status="REJECTED",
            message="Sender balance no longer covers this amount.",
        )

    new_sender_balance = float(sender["balance"]) - amount
    # Only credit receiver if it is a real account (not SYSTEM)
    new_receiver_balance = float(receiver["balance"]) + amount if not is_no_recv else 0.0
    if new_sender_balance < 0:
        database.save_transaction(request.transaction_id, {"status": "REJECTED", "completed": False})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transaction would create a negative balance")

    database.set_account_balance(record["sender"], new_sender_balance)
    if not is_no_recv:
        database.set_account_balance(record["receiver"], new_receiver_balance)
    database.save_transaction(
        request.transaction_id,
        {
            "status": "COMPLETED",
            "completed": True,
            "sender_balance": new_sender_balance,
            "receiver_balance": new_receiver_balance if not is_no_recv else None,
        },
    )
    return TransactionConfirmResponse(
        transaction_id=request.transaction_id,
        channel=rec_channel,
        status="COMPLETED",
        message="Transaction completed successfully after approval.",
        sender_id=record["sender"],
        receiver_id=record["receiver"] if not is_no_recv else None,
        previous_balance=float(sender["balance"]),
        amount_debited=amount,
        sender_balance=new_sender_balance,
        receiver_balance=new_receiver_balance if not is_no_recv else None,
    )


@app.get("/transactions", response_model=HistoryResponse)
def transactions(limit: int = Query(default=50, ge=1, le=500)):
    try:
        records = database.recent_predictions(limit)
    except Exception:
        records = None
    if records is None:
        return HistoryResponse(
            status="unavailable",
            message="MongoDB is not configured or unavailable.",
        )
    return HistoryResponse(
        status="ok",
        transactions=[PredictionRecord(**record) for record in records],
    )


@app.get("/stats", response_model=StatsResponse)
def stats():
    try:
        values = database.stats()
    except Exception:
        values = None
    if values is None:
        return StatsResponse(
            status="unavailable",
            message="MongoDB is not configured or unavailable.",
        )
    return StatsResponse(status="ok", **values)


def _risk_row(request: RiskScoreRequest):
    row = {
        "transaction_id": request.event_id,
        "amount": request.amount,
        "type": request.transaction_type,
        "channel": request.channel,
        "nameOrig": request.sender,
        "nameDest": request.receiver,
        "customer": request.sender,
        "merchant": request.merchant_id,
        "category": request.transaction_type,
        "TransactionID": request.event_id,
        "TransactionAmt": request.amount,
        "ProductCD": request.transaction_type,
        "tran_id": request.event_id,
        "orig_acct": request.sender,
        "bene_acct": request.receiver,
        "tx_type": request.transaction_type,
        "base_amt": request.amount,
        "tx_id": request.event_id,
        "src_id": request.sender,
        "dst_id": request.receiver,
        "timestamp": request.timestamp,
        "tran_timestamp": request.timestamp,
        "TransactionDT": request.timestamp,
        "step": request.timestamp,
        "oldbalanceOrg": request.oldbalance_org,
        "oldbalanceDest": request.oldbalance_dest,
        "zipcodeOri": request.signals.get("zipcodeOri"),
    }
    row.update(request.signals)
    return {key: value for key, value in row.items() if value is not None}


def _model_output(request, row):
    if request.dataset != "paysim":
        return {}
    try:
        hour = 0
        if isinstance(request.timestamp, str) and "T" in request.timestamp:
            hour = int(request.timestamp.split("T", 1)[1][:2])
        prediction = model_service.predict(
            PredictionRequest(
                amount=request.amount,
                oldbalanceOrg=request.oldbalance_org or 0,
                oldbalanceDest=request.oldbalance_dest or 0,
                type=request.transaction_type,
                hour=hour,
                day=0,
            )
        )
        return {"fraud_probability": prediction["fraud_probability"], "model_used": "paysim-xgb-realtime"}
    except Exception:
        return {}


def _score_request(request: RiskScoreRequest):
    t_start = pytime.perf_counter()
    row = _risk_row(request)
    event = ADAPTERS[request.dataset].adapt(row, _model_output(request, row))
    result = risk_engine.assess(event)
    audit_id = result.event_id or request.event_id
    t_end = pytime.perf_counter()
    processing_ms = round((t_end - t_start) * 1000.0, 2)

    ts_bundle = _get_timestamp_bundle(datetime.now(timezone.utc))

    reasons = [item["reason"] for item in result.signal_contributions]
    return RiskScoreResponse(
        event_id=request.event_id,
        transaction_id=request.event_id,
        timestamp_utc=ts_bundle["timestamp_utc"],
        timestamp_ist=ts_bundle["timestamp_ist"],
        transaction_time=ts_bundle["transaction_time"],
        processed_at=ts_bundle["processed_at"],
        processing_time_ms=processing_ms,
        merchant_id=request.merchant_id,
        sender_id=request.sender,
        receiver_id=request.receiver,
        amount=request.amount,
        channel=request.channel,
        transaction_type=request.transaction_type,
        risk_score=round(result.risk_score, 2),
        risk_level=result.risk_level,
        decision=result.decision,
        signals=[
            RiskSignalResponse(
                source=s.source,
                signal_name=s.signal_name,
                risk_value=s.risk_value,
                confidence=s.confidence,
                reason=s.reason,
                evidence=s.evidence,
                category=s.category,
            )
            for s in result.signals
        ],
        top_reasons=reasons[:3],
        reasons=reasons,
        model_probability=result.fraud_probability,
        ml_probability=result.fraud_probability,
        contextual_score=round(result.risk_score / 100.0, 4),
        dataset=request.dataset,
        model=f"{request.dataset.title()} Realtime Engine",
        audit_id=audit_id,
        explanation=result.explanation,
    )


@app.post("/api/v1/risk/score", response_model=RiskScoreResponse)
def risk_score(request: RiskScoreRequest):
    return _score_request(request)


@app.post("/api/v1/risk/batch", response_model=RiskBatchResponse)
def risk_batch(request: RiskBatchRequest):
    return RiskBatchResponse(results=[_score_request(event) for event in request.events])


@app.get("/api/v1/risk/transaction/{event_id}")
def risk_transaction(event_id: str):
    for record in reversed(risk_engine.get_audit_trail()):
        if record["event_id"] == event_id:
            return record
    raise HTTPException(status_code=404, detail="Risk event not found")


@app.get("/api/v1/audit")
def risk_audit(limit: int = Query(default=50, ge=1, le=500)):
    return {"records": risk_engine.get_audit_trail()[-limit:][::-1]}


@app.get("/api/v1/metrics")
def risk_metrics():
    records = risk_engine.get_audit_trail()
    total = len(records)
    high_count = sum(r["risk_level"] in ("HIGH", "CRITICAL") for r in records)
    crit_count = sum(r["risk_level"] == "CRITICAL" for r in records)
    med_count = sum(r["risk_level"] == "MEDIUM" for r in records)
    low_count = sum(r["risk_level"] == "LOW" for r in records)
    flagged_count = sum(r["decision"] in ("FLAG", "BLOCK") for r in records)
    scores = [float(r.get("risk_score", 0)) for r in records]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return {
        "transactions_analyzed": total,
        "critical_risk": crit_count,
        "high_risk": high_count,
        "medium_risk": med_count,
        "low_risk": low_count,
        "flagged_rate": (flagged_count / total) if total else 0.0,
        "avg_risk_score": avg_score,
        "estimated_fp_cost": 0,
        "estimated_fn_cost": 0,
    }


@app.get("/api/v1/health")
def risk_health():
    return {"status": "ok", "engine": "risk-engine-v2", "model_loaded": model_service.model is not None}


@app.get("/api/v1/models", response_model=ModelsResponse)
def risk_models():
    return ModelsResponse(
        models=[
            ModelStatus(dataset="PaySim", model="xgb_realtime_model.json", available=bool(model_service.is_loaded or (REPORTS_DIR / "xgb_realtime_model.json").is_file())),
            ModelStatus(dataset="BankSim", model="banksim_xgb_model.joblib", available=(REPORTS_DIR / "banksim_xgb_model.joblib").is_file()),
            ModelStatus(dataset="IEEE-CIS", model="ieee_cis_xgb_model.joblib", available=(REPORTS_DIR / "ieee_cis_xgb_model.joblib").is_file()),
            ModelStatus(dataset="AMLSim", model="signal-only", available=False),
            ModelStatus(dataset="Fraud Graph", model="signal-only", available=False),
        ]
    )

