from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TransactionType = Literal["TRANSFER", "CASH_OUT", "PAYMENT", "DEBIT", "CASH_IN"]
PaymentChannel = Literal[
    "UPI",
    "ATM",
    "DEBIT_CARD",
    "CREDIT_CARD",
    "NET_BANKING",
    "WALLET",
    "CASH_WITHDRAWAL",
    "BANK_TRANSFER",
    "CASH_DEPOSIT",
    "POS",
    "ECOMMERCE",
]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Decision = Literal["ALLOW", "REVIEW", "BLOCK", "FLAG"]


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    oldbalanceOrg: float = Field(ge=0)
    oldbalanceDest: float = Field(ge=0)
    type: str = "TRANSFER"
    hour: int = Field(ge=0, le=23)
    day: int = Field(ge=0, le=30)


class PredictionResponse(BaseModel):
    fraud_probability: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    decision: Literal["ALLOW", "FLAG", "REVIEW", "BLOCK"]
    threshold: float


class Account(BaseModel):
    account_id: str
    name: str
    balance: float
    primary_device: str | None = None
    normal_location: str | None = None
    is_inactive: bool = False


# Channels that do NOT require a real receiver account (ATM, card, cash ops)
CASH_CHANNELS: set[str] = {"ATM", "CASH_WITHDRAWAL", "CASH_DEPOSIT"}
CARD_CHANNELS: set[str] = {"DEBIT_CARD", "CREDIT_CARD", "POS", "ECOMMERCE"}
NO_RECEIVER_CHANNELS: set[str] = CASH_CHANNELS | CARD_CHANNELS

# Default receiver sentinel used when channel has no real beneficiary
SYSTEM_RECEIVER = "SYSTEM"


class TransactionCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Merchant transaction event fields
    sender_id: str
    # receiver_id is optional for ATM/Card channels (no real beneficiary)
    receiver_id: str = SYSTEM_RECEIVER
    amount: float = Field(gt=0)
    transaction_type: str = "TRANSFER"
    channel: PaymentChannel = "UPI"
    currency: str = "INR"
    order_id: str | None = None
    merchant_id: str | None = None

    # Temporal context (optional, defaults to current time if omitted)
    timestamp: str | None = None
    date: int | None = Field(default=None, ge=1, le=31)
    month: str | None = None
    time: str | None = None

    # Security & Behavioral context (auto-enriched or overridden in QA mode)
    device_id: str | None = None
    location: str | None = None
    failed_pin_attempts: int | None = Field(default=None, ge=0)
    auth_context: dict[str, Any] = Field(default_factory=dict)
    is_new_beneficiary: bool | None = None
    balance_override: float | None = Field(default=None, ge=0)


class DetectedSignalItem(BaseModel):
    name: str
    status: str
    alert: bool
    category: str = "behavioral"
    signal_code: str = ""


class TransactionCheckResponse(BaseModel):
    transaction_id: str
    timestamp_utc: str
    timestamp_ist: str
    transaction_time: str
    processed_at: str
    processing_time_ms: float = 0.0

    status: Literal["ALLOWED", "FLAGGED", "REJECTED", "REVIEW"]
    sender_id: str
    receiver_id: str
    sender_name: str
    receiver_name: str
    amount: float
    currency: str = "INR"
    channel: str = "UPI"
    transaction_type: str = "TRANSFER"
    order_id: str | None = None
    merchant_id: str | None = None
    oldbalanceOrg: float
    oldbalanceDest: float

    # Centralized scoring
    ml_probability: float = 0.0
    fraud_probability: float = 0.0
    base_probability: float = 0.0
    contextual_score: float = 0.0
    context_score: float = 0.0
    risk_score: float = 0.0
    risk_level: RiskLevel = "LOW"
    decision: Decision = "ALLOW"
    threshold: float = 0.60
    requires_confirmation: bool = False
    message: str = ""

    # Rich explainability
    model: str = "PaySim XGBoost"
    risk_signals: dict[str, bool] = Field(default_factory=dict)
    detected_signals: list[DetectedSignalItem] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)
    engine_metadata: dict[str, Any] = Field(default_factory=dict)


class TransactionConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str


class TransactionConfirmResponse(BaseModel):
    transaction_id: str
    status: Literal["COMPLETED", "FLAGGED", "REJECTED"]
    message: str
    channel: str | None = None
    sender_id: str | None = None
    receiver_id: str | None = None
    previous_balance: float | None = None
    amount_debited: float | None = None
    sender_balance: float | None = None
    receiver_balance: float | None = None


class PredictionRecord(BaseModel):
    timestamp: datetime | str
    timestamp_utc: str | None = None
    timestamp_ist: str | None = None
    transaction_time: str | None = None
    amount: float
    transaction_type: str
    channel: str = "UPI"
    date: int
    month: str
    time: str
    fraud_probability: float
    risk_score: float = 0.0
    risk_level: RiskLevel = "LOW"
    decision: Decision = "ALLOW"


class HistoryResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    transactions: list[PredictionRecord] = Field(default_factory=list)
    message: str | None = None


class StatsResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    total_transactions: int = 0
    flagged_transactions: int = 0
    high_risk_transactions: int = 0
    critical_risk_transactions: int = 0
    medium_risk_transactions: int = 0
    low_risk_transactions: int = 0
    fraud_rate: float = 0.0
    total_volume: float = 0.0
    blocked_volume: float = 0.0
    potential_loss_prevented: float = 0.0
    avg_risk_score: float = 0.0
    message: str | None = None


class RiskScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=100)
    dataset: Literal["paysim", "banksim", "ieee-cis", "amlsim", "fraud-graph"] = "paysim"
    amount: float = Field(gt=0)
    transaction_type: str = Field(min_length=1, max_length=60, default="TRANSFER")
    channel: PaymentChannel = "UPI"
    sender: str | None = Field(default=None, max_length=120)
    receiver: str | None = Field(default=None, max_length=120)
    merchant_id: str | None = Field(default=None, max_length=120)
    timestamp: datetime | str | None = None
    oldbalance_org: float | None = Field(default=None, ge=0)
    oldbalance_dest: float | None = Field(default=None, ge=0)
    signals: dict[str, Any] = Field(default_factory=dict, max_length=30)


class RiskBatchRequest(BaseModel):
    events: list[RiskScoreRequest] = Field(min_length=1, max_length=100)


class RiskSignalResponse(BaseModel):
    source: str
    signal_name: str
    risk_value: float
    confidence: float
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    category: str = "behavioral"


class RiskScoreResponse(BaseModel):
    event_id: str
    transaction_id: str | None = None
    timestamp_utc: str | None = None
    timestamp_ist: str | None = None
    transaction_time: str | None = None
    processed_at: str | None = None
    processing_time_ms: float = 0.0
    merchant_id: str | None = None
    sender_id: str | None = None
    receiver_id: str | None = None
    amount: float | None = None
    channel: str = "UPI"
    transaction_type: str = "TRANSFER"
    risk_score: float
    risk_level: RiskLevel
    decision: Decision
    signals: list[RiskSignalResponse] = Field(default_factory=list)
    top_reasons: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    model_probability: float | None = None
    ml_probability: float | None = None
    contextual_score: float | None = None
    dataset: str = "paysim"
    model: str = "PaySim XGBoost"
    audit_id: str = ""
    explanation: str = ""


class RiskBatchResponse(BaseModel):
    results: list[RiskScoreResponse]


class ModelStatus(BaseModel):
    dataset: str
    model: str
    available: bool


class ModelsResponse(BaseModel):
    models: list[ModelStatus]

