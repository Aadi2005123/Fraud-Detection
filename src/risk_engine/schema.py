"""Dataset-neutral risk event contract."""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class NormalizedRiskSignal:
    source: str
    signal_name: str
    risk_value: float
    confidence: float
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[Any] = None
    model_name: Optional[str] = None
    category: str = "behavioral"

    def __post_init__(self):
        self.risk_value = max(0.0, min(1.0, float(self.risk_value)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


@dataclass
class RiskEvent:
    dataset: str
    transaction_id: Optional[str] = None
    timestamp: Optional[Any] = None
    amount: Optional[float] = None
    transaction_type: Optional[str] = None
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    merchant_id: Optional[str] = None
    payment_method: Optional[str] = None
    device_signal: Optional[str] = None
    identity_signal: Optional[str] = None
    location_signal: Optional[str] = None
    amount_risk: Optional[float] = None
    balance_risk: Optional[float] = None
    velocity_risk: Optional[float] = None
    merchant_risk: Optional[float] = None
    network_risk: Optional[float] = None
    fraud_probability: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    decision: Optional[str] = None
    explanation: Optional[str] = None
    model_used: Optional[str] = None
    input_signals: Dict[str, Any] = field(default_factory=dict)
    signals: list = field(default_factory=list)
    signal_contributions: list = field(default_factory=list)
    policy_version: Optional[str] = None
    event_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)