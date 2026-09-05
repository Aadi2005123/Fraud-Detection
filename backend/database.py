import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()


class Database:
    def __init__(self):
        self.database_name = os.getenv("MONGODB_DATABASE", "fraud_detector")

        self._demo_accounts = {
            "AADI001": {
                "account_id": "AADI001",
                "name": "Aadi",
                "balance": 10000.0,
                "primary_device": "DEVICE_AADI_01",
                "known_devices": ["DEVICE_AADI_01"],
                "normal_location": "Delhi",
                "known_locations": ["Delhi"],
                "known_beneficiaries": ["RAHUL001", "PRIYA001"],
                "is_inactive": False,
                "historical_amounts": [500.0, 1000.0, 1500.0, 2000.0],
                "normal_hours": (9, 23),
            },
            "RAHUL001": {
                "account_id": "RAHUL001",
                "name": "Rahul",
                "balance": 50000.0,
                "primary_device": "DEVICE_RAHUL_01",
                "known_devices": ["DEVICE_RAHUL_01"],
                "normal_location": "Bangalore",
                "known_locations": ["Bangalore"],
                "known_beneficiaries": ["AMIT001", "PRIYA001"],
                "is_inactive": False,
                "historical_amounts": [1500.0, 3000.0, 5000.0, 4500.0],
                "normal_hours": (9, 23),
            },
            "AMIT001": {
                "account_id": "AMIT001",
                "name": "Amit",
                "balance": 100000.0,
                "primary_device": "DEVICE_AMIT_01",
                "known_devices": ["DEVICE_AMIT_01", "DEVICE_MERCHANT_01"],
                "normal_location": "Delhi",
                "known_locations": ["Delhi", "Noida"],
                "known_beneficiaries": ["PRIYA001", "RAHUL001"],
                "is_inactive": False,
                "historical_amounts": [2000.0, 4500.0, 5000.0, 8000.0, 10000.0],
                "normal_hours": (9, 23),
            },
            "PRIYA001": {
                "account_id": "PRIYA001",
                "name": "Priya",
                "balance": 25000.0,
                "primary_device": "DEVICE_PRIYA_01",
                "known_devices": ["DEVICE_PRIYA_01"],
                "normal_location": "Mumbai",
                "known_locations": ["Mumbai"],
                "known_beneficiaries": ["AMIT001", "AADI001"],
                "is_inactive": False,
                "historical_amounts": [800.0, 1200.0, 2500.0, 3000.0],
                "normal_hours": (9, 23),
            },
            "INACTIVE001": {
                "account_id": "INACTIVE001",
                "name": "Dormant User",
                "balance": 150000.0,
                "primary_device": "DEVICE_OLD_DORMANT",
                "known_devices": ["DEVICE_OLD_DORMANT"],
                "normal_location": "Kolkata",
                "known_locations": ["Kolkata"],
                "known_beneficiaries": [],
                "is_inactive": True,
                "historical_amounts": [1000.0, 2000.0],
                "normal_hours": (9, 23),
            },
        }

        self._demo_transactions = {}
        self._demo_predictions = []
        self._demo_auth_events = []
        self._client = None

        self._init_client()

    def _init_client(self):
        uri = os.getenv("MONGODB_URI")

        if uri:
            try:
                self._client = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=3000,
                )
            except Exception:
                self._client = None
        else:
            self._client = None

    @property
    def client(self):
        if self._client is None:
            self._init_client()
        return self._client

    @property
    def available(self):
        if self.client is None:
            return False

        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def reset_demo_state(self):
        self._demo_accounts = {
            "AADI001": {
                "account_id": "AADI001",
                "name": "Aadi",
                "balance": 10000.0,
                "primary_device": "DEVICE_AADI_01",
                "known_devices": ["DEVICE_AADI_01"],
                "normal_location": "Delhi",
                "known_locations": ["Delhi"],
                "known_beneficiaries": ["RAHUL001", "PRIYA001"],
                "is_inactive": False,
                "historical_amounts": [500.0, 1000.0, 1500.0, 2000.0],
                "normal_hours": (9, 23),
            },
            "RAHUL001": {
                "account_id": "RAHUL001",
                "name": "Rahul",
                "balance": 50000.0,
                "primary_device": "DEVICE_RAHUL_01",
                "known_devices": ["DEVICE_RAHUL_01"],
                "normal_location": "Bangalore",
                "known_locations": ["Bangalore"],
                "known_beneficiaries": ["AMIT001", "PRIYA001"],
                "is_inactive": False,
                "historical_amounts": [1500.0, 3000.0, 5000.0, 4500.0],
                "normal_hours": (9, 23),
            },
            "AMIT001": {
                "account_id": "AMIT001",
                "name": "Amit",
                "balance": 100000.0,
                "primary_device": "DEVICE_AMIT_01",
                "known_devices": ["DEVICE_AMIT_01", "DEVICE_MERCHANT_01"],
                "normal_location": "Delhi",
                "known_locations": ["Delhi", "Noida"],
                "known_beneficiaries": ["PRIYA001", "RAHUL001"],
                "is_inactive": False,
                "historical_amounts": [2000.0, 4500.0, 5000.0, 8000.0, 10000.0],
                "normal_hours": (9, 23),
            },
            "PRIYA001": {
                "account_id": "PRIYA001",
                "name": "Priya",
                "balance": 25000.0,
                "primary_device": "DEVICE_PRIYA_01",
                "known_devices": ["DEVICE_PRIYA_01"],
                "normal_location": "Mumbai",
                "known_locations": ["Mumbai"],
                "known_beneficiaries": ["AMIT001", "AADI001"],
                "is_inactive": False,
                "historical_amounts": [800.0, 1200.0, 2500.0, 3000.0],
                "normal_hours": (9, 23),
            },
            "INACTIVE001": {
                "account_id": "INACTIVE001",
                "name": "Dormant User",
                "balance": 150000.0,
                "primary_device": "DEVICE_OLD_DORMANT",
                "known_devices": ["DEVICE_OLD_DORMANT"],
                "normal_location": "Kolkata",
                "known_locations": ["Kolkata"],
                "known_beneficiaries": [],
                "is_inactive": True,
                "historical_amounts": [1000.0, 2000.0],
                "normal_hours": (9, 23),
            },
        }

        self._demo_transactions = {}
        self._demo_predictions = []
        self._demo_auth_events = []

    def list_accounts(self):
        if self.available:
            try:
                docs = list(
                    self.client[self.database_name]
                    .accounts
                    .find({}, {"_id": 0})
                    .sort("account_id", 1)
                )

                if docs:
                    return docs

            except Exception:
                pass

        return [
            dict(account)
            for account in self._demo_accounts.values()
        ]

    def get_account(self, account_id):
        if self.available:
            try:
                doc = self.client[self.database_name].accounts.find_one(
                    {"account_id": account_id},
                    {"_id": 0},
                )

                if doc is not None:
                    return doc

            except Exception:
                pass

        return self._demo_accounts.get(account_id)

    def set_account_balance(self, account_id, balance):
        float_balance = float(balance)

        if self.available:
            try:
                self.client[self.database_name].accounts.update_one(
                    {"account_id": account_id},
                    {"$set": {"balance": float_balance}},
                    upsert=True,
                )

            except Exception:
                pass

        account = self._demo_accounts.get(account_id)

        if account is not None:
            account["balance"] = float_balance
            return float_balance

        return float_balance

    def record_auth_event(self, account_id: str, event_type: str, metadata: dict | None = None) -> None:
        """
        Record authentication & security events: LOGIN_FAILED, PIN_FAILED, PASSWORD_RESET, LOGIN_SUCCESS, etc.
        """
        event = {
            "account_id": account_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc),
            "metadata": metadata or {},
        }
        self._demo_auth_events.append(event)

        if self.available:
            try:
                self.client[self.database_name].auth_events.insert_one(event)
            except Exception:
                pass

    def get_recent_auth_failures(self, account_id: str, minutes: int = 30) -> int:
        """Calculate recent failed authentication events."""
        now = datetime.now(timezone.utc)
        count = 0
        for ev in self._demo_auth_events:
            if ev.get("account_id") == account_id and ev.get("event_type") in ("PIN_FAILED", "LOGIN_FAILED", "OTP_FAILED"):
                ts = ev.get("timestamp")
                if isinstance(ts, datetime):
                    diff = (now - ts).total_seconds() / 60.0
                    if diff <= minutes:
                        count += 1
        return count

    def get_account_behavior(self, account_id: str) -> dict:
        account = self.get_account(account_id) or {}
        return {
            "account_id": account_id,
            "primary_device": account.get("primary_device", f"DEVICE_{account_id}_01"),
            "known_devices": account.get("known_devices", [account.get("primary_device", f"DEVICE_{account_id}_01")]),
            "normal_location": account.get("normal_location", "Delhi"),
            "known_locations": account.get("known_locations", [account.get("normal_location", "Delhi")]),
            "known_beneficiaries": account.get("known_beneficiaries", ["PRIYA001", "RAHUL001"]),
            "is_inactive": bool(account.get("is_inactive", False)),
            "historical_amounts": account.get("historical_amounts", [2000.0, 4500.0, 5000.0, 8000.0]),
            "normal_hours": account.get("normal_hours", (9, 23)),
        }

    def is_device_changed(self, account_id: str, device_id: str | None) -> bool:
        if not device_id or not str(device_id).strip():
            return False
        behavior = self.get_account_behavior(account_id)
        known = [str(d).strip().lower() for d in behavior.get("known_devices", []) if d]
        if not known:
            return False
        return str(device_id).strip().lower() not in known

    def is_unusual_location(self, account_id: str, location: str | None) -> bool:
        if not location or not str(location).strip():
            return False
        behavior = self.get_account_behavior(account_id)
        known = [str(l).strip().lower() for l in behavior.get("known_locations", []) if l]
        if not known:
            return False
        return str(location).strip().lower() not in known

    def is_new_beneficiary(self, account_id: str, receiver_id: str | None) -> bool:
        if not receiver_id or not str(receiver_id).strip():
            return False
        behavior = self.get_account_behavior(account_id)
        known = [str(b).strip().upper() for b in behavior.get("known_beneficiaries", []) if b]
        if not known:
            return True
        return str(receiver_id).strip().upper() not in known

    def is_account_inactive(self, account_id: str) -> bool:
        behavior = self.get_account_behavior(account_id)
        return bool(behavior.get("is_inactive", False))

    def is_unusually_large_transaction(self, account_id: str, amount: float) -> bool:
        try:
            amt = float(amount)
        except (ValueError, TypeError):
            return False
        behavior = self.get_account_behavior(account_id)
        history = [float(x) for x in behavior.get("historical_amounts", []) if float(x) > 0]
        if not history:
            return amt >= 75000.0
        avg_amt = sum(history) / len(history)
        max_amt = max(history)
        return (amt >= avg_amt * 3.0 and amt > max_amt * 1.8) or (amt >= avg_amt * 5.0) or (amt >= 75000.0)

    def get_transaction_amount_risk(self, account_id: str, amount: float) -> float:
        """
        Calculate continuous/severity-aware transaction amount risk between 0.0 and 1.0
        based on the account's historical transaction baseline.
        """
        try:
            amt = float(amount)
        except (ValueError, TypeError):
            return 0.0
        if amt <= 0:
            return 0.0

        behavior = self.get_account_behavior(account_id)
        raw_history = behavior.get("historical_amounts", []) if isinstance(behavior, dict) else []
        history = []
        for x in raw_history:
            try:
                val = float(x)
                if val > 0:
                    history.append(val)
            except (ValueError, TypeError):
                continue

        if not history:
            if amt >= 500000.0:
                return 1.00
            if amt >= 200000.0:
                return 0.75
            if amt >= 100000.0:
                return 0.60
            if amt >= 75000.0:
                return 0.45
            if amt >= 50000.0:
                return 0.30
            return 0.00

        avg_amt = sum(history) / len(history)
        max_amt = max(history)

        if avg_amt <= 0:
            return 0.0

        ratio_to_avg = amt / avg_amt
        ratio_to_max = amt / max_amt if max_amt > 0 else ratio_to_avg

        if ratio_to_avg >= 100.0:
            risk = 1.00
        elif ratio_to_avg >= 50.0:
            risk = 0.90
        elif ratio_to_avg >= 20.0:
            risk = 0.75
        elif ratio_to_avg >= 10.0:
            risk = 0.60
        elif ratio_to_avg >= 5.0:
            risk = 0.45
        elif ratio_to_avg >= 3.0:
            risk = 0.30
        else:
            risk = 0.00

        # Absolute threshold safeguard consistent with ₹75,000 baseline
        if amt >= 500000.0:
            risk = max(risk, 0.90)
        elif amt >= 200000.0:
            risk = max(risk, 0.75)
        elif amt >= 100000.0:
            risk = max(risk, 0.50)
        elif amt >= 75000.0:
            risk = max(risk, 0.30)

        return min(1.0, max(0.0, float(risk)))

    def is_unusual_time(self, account_id: str, hour: int) -> bool:
        behavior = self.get_account_behavior(account_id)
        start_hour, end_hour = behavior.get("normal_hours", (9, 23))
        return hour < start_hour or hour > end_hour

    def is_balance_drain(self, account_id: str, amount: float, balance_override: float | None = None) -> bool:
        bal = float(balance_override) if balance_override is not None else None
        if bal is None:
            account = self.get_account(account_id)
            if not account or "balance" not in account:
                return False
            bal = float(account["balance"])
        if bal <= 0:
            return False
        return (float(amount) / bal) >= 0.75

    def detect_velocity_and_impossible_travel(
        self,
        account_id: str,
        current_location: str | None = None,
        tx_timestamp: datetime | None = None,
    ) -> tuple[bool, bool]:
        """
        Check recent transaction timestamps for velocity (>3 transactions in 2 mins)
        and impossible travel (multiple distinct locations within short time).
        """
        now = tx_timestamp or datetime.now(timezone.utc)
        recent_txs = []
        for tx in self._demo_transactions.values():
            if tx.get("sender") == account_id:
                ts = tx.get("timestamp")
                if isinstance(ts, datetime):
                    recent_txs.append(tx)

        recent_txs.sort(key=lambda t: t.get("timestamp"), reverse=True)
        # Check high velocity in last 2 mins
        last_2min = [t for t in recent_txs if abs((now - t.get("timestamp")).total_seconds()) <= 120]
        high_velocity = len(last_2min) >= 3

        # Check impossible travel
        impossible_travel = False
        if current_location and recent_txs:
            latest_tx = recent_txs[0]
            prev_loc = latest_tx.get("location")
            if prev_loc and str(prev_loc).strip().lower() != str(current_location).strip().lower():
                time_delta_sec = abs((now - latest_tx.get("timestamp")).total_seconds())
                if time_delta_sec <= 900:  # < 15 minutes between different cities
                    impossible_travel = True

        return high_velocity, impossible_travel

    def get_recent_transactions_for_account(self, account_id: str, limit: int = 10) -> list:
        records = []
        for tx in self._demo_transactions.values():
            if tx.get("sender") == account_id or tx.get("receiver") == account_id:
                records.append(tx)
        if self.available:
            try:
                mongo_records = list(
                    self.client[self.database_name].transactions.find(
                        {"$or": [{"sender": account_id}, {"receiver": account_id}]},
                        {"_id": 0},
                    ).sort("timestamp", DESCENDING).limit(limit)
                )
                if mongo_records:
                    return mongo_records
            except Exception:
                pass
        return records[:limit]

    def ensure_seed_accounts(self):
        if self.available:
            try:
                collection = self.client[self.database_name].accounts

                if collection.count_documents({}) == 0:
                    collection.insert_many(
                        list(self._demo_accounts.values())
                    )

            except Exception:
                pass

    def insert_prediction(self, record: dict) -> bool:
        ts = record.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                ts = datetime.now(timezone.utc)
        elif not isinstance(ts, datetime):
            ts = datetime.now(timezone.utc)

        amount = float(record.get("amount", 0))
        risk_score = float(record.get("risk_score", 0.0))
        if risk_score == 0.0 and record.get("fraud_probability"):
            risk_score = round(float(record.get("fraud_probability")) * 100.0, 1)

        document = {
            "timestamp": ts,
            "timestamp_utc": record.get("timestamp_utc") or ts.isoformat(),
            "timestamp_ist": record.get("timestamp_ist") or ts.isoformat(),
            "transaction_time": record.get("transaction_time") or record.get("time", "00:00"),
            "amount": amount,
            "transaction_type": str(record.get("transaction_type", "TRANSFER")),
            "channel": str(record.get("channel", "UPI")),
            "date": int(record.get("date", 1)),
            "month": str(record.get("month", "August")),
            "time": str(record.get("time", "00:00")),
            "fraud_probability": round(float(record.get("fraud_probability", 0.0)), 4),
            "risk_score": risk_score,
            "risk_level": str(record.get("risk_level", "LOW")),
            "decision": str(record.get("decision", "ALLOW")),
        }

        self._demo_predictions.append(dict(document))

        if self.available:
            try:
                self.client[self.database_name].predictions.insert_one(document)
                return True
            except Exception:
                return False

        return True

    def insert_transaction_record(self, record: dict) -> str:
        """
        Store a transaction together with all fields required
        for accurate duplicate detection and audit trail.
        """
        transaction_id = record.get("transaction_id") or uuid4().hex
        document = {
            "transaction_id": transaction_id,
            "timestamp": record.get("timestamp", datetime.now(timezone.utc)),
            "timestamp_utc": record.get("timestamp_utc"),
            "timestamp_ist": record.get("timestamp_ist"),
            "transaction_time": record.get("transaction_time"),
            "sender": record.get("sender"),
            "receiver": record.get("receiver"),
            "amount": float(record.get("amount", 0)),
            "transaction_type": record.get("transaction_type", "TRANSFER"),
            "channel": record.get("channel", "UPI"),
            "date": record.get("date"),
            "month": record.get("month"),
            "time": record.get("time"),
            "location": record.get("location"),
            "device_id": record.get("device_id"),
            "failed_pin_attempts": record.get("failed_pin_attempts", 0),
            "risk_score": record.get("risk_score", 0.0),
            "risk_level": record.get("risk_level", "LOW"),
            "decision": record.get("decision"),
            "status": record.get("status"),
            "completed": bool(record.get("completed", False)),
            "risk_signals": record.get("risk_signals", {}),
            "risk_reasons": record.get("risk_reasons", []),
        }

        # Keep in-memory demo transaction
        self._demo_transactions[transaction_id] = document

        # Keep MongoDB transaction
        if self.available:
            try:
                self.client[self.database_name].transactions.insert_one(document)
            except Exception:
                pass

        return transaction_id

    def get_transaction(self, transaction_id: str):
        if self.available:
            try:
                doc = self.client[self.database_name].transactions.find_one(
                    {"transaction_id": transaction_id},
                    {"_id": 0},
                )
                if doc is not None:
                    return doc
            except Exception:
                pass

        return self._demo_transactions.get(transaction_id)

    def save_transaction(self, transaction_id: str, updates: dict):
        if self.available:
            try:
                self.client[self.database_name].transactions.update_one(
                    {"transaction_id": transaction_id},
                    {"$set": updates},
                )
            except Exception:
                pass

        record = self._demo_transactions.get(transaction_id)
        if record is not None:
            record.update(updates)

    def recent_predictions(self, limit: int = 50):
        if self.available:
            try:
                docs = list(
                    self.client[self.database_name]
                    .predictions
                    .find({}, {"_id": 0})
                    .sort("timestamp", DESCENDING)
                    .limit(limit)
                )
                return docs
            except Exception:
                pass

        records = list(self._demo_predictions)
        records.sort(
            key=lambda item: item.get("timestamp")
            if isinstance(item.get("timestamp"), datetime)
            else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return records[:limit]

    def stats(self):
        records = []
        if self.available:
            try:
                collection = self.client[self.database_name].predictions
                docs = list(collection.find({}, {"_id": 0}))
                if docs:
                    records = docs
            except Exception:
                pass

        if not records:
            records = self._demo_predictions

        total = len(records)
        flagged = sum(1 for r in records if r.get("decision") in ("FLAG", "BLOCK"))
        critical_risk = sum(1 for r in records if r.get("risk_level") == "CRITICAL")
        high_risk = sum(1 for r in records if r.get("risk_level") == "HIGH")
        medium_risk = sum(1 for r in records if r.get("risk_level") == "MEDIUM")
        low_risk = sum(1 for r in records if r.get("risk_level") == "LOW")
        total_vol = sum(float(r.get("amount", 0)) for r in records)
        blocked_vol = sum(float(r.get("amount", 0)) for r in records if r.get("decision") in ("FLAG", "BLOCK"))
        scores = [float(r.get("risk_score", 0)) for r in records]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        return {
            "total_transactions": total,
            "flagged_transactions": flagged,
            "critical_risk_transactions": critical_risk,
            "high_risk_transactions": high_risk,
            "medium_risk_transactions": medium_risk,
            "low_risk_transactions": low_risk,
            "fraud_rate": (flagged / total if total else 0.0),
            "total_volume": round(total_vol, 2),
            "blocked_volume": round(blocked_vol, 2),
            "potential_loss_prevented": round(blocked_vol, 2),
            "avg_risk_score": avg_score,
        }

    def has_duplicate_transaction(
        self,
        sender_id,
        receiver_id,
        amount,
        transaction_type,
        date,
        month,
        time,
    ):
        """
        A transaction is a duplicate ONLY when all transaction
        identity fields match and the existing transaction is PENDING.
        """

        # ---------------------------------------------------------
        # Demo / in-memory transactions
        # ---------------------------------------------------------

        for record in self._demo_transactions.values():

            if (
                record.get("sender") == sender_id
                and record.get("receiver") == receiver_id
                and float(
                    record.get("amount", 0)
                ) == float(amount)
                and record.get(
                    "transaction_type"
                ) == transaction_type
                and record.get("date") == date
                and record.get("month") == month
                and record.get("time") == time
                and record.get("status") == "PENDING"
            ):
                return True

        # ---------------------------------------------------------
        # MongoDB transactions
        # ---------------------------------------------------------

        if self.available:
            try:
                collection = self.client[
                    self.database_name
                ].transactions

                return (
                    collection.count_documents(
                        {
                            "sender": sender_id,
                            "receiver": receiver_id,
                            "amount": float(amount),
                            "transaction_type": transaction_type,
                            "date": date,
                            "month": month,
                            "time": time,
                            "status": "PENDING",
                        }
                    )
                    > 0
                )

            except Exception:
                pass

        return False