"""
Feature engineering for the PaySim fraud dataset.

Key data facts baked into this module (verified by direct inspection of the
raw file):
  - Fraud ONLY occurs where type in {TRANSFER, CASH_OUT}. PAYMENT, CASH_IN,
    DEBIT contain zero fraud rows, so we filter to just these two types.
  - nameOrig is almost always unique per row (~6.353M unique out of 6.363M
    rows) so there is effectively no repeat-customer history in this
    dataset. Per-customer velocity/frequency features are therefore NOT
    built here — they would be fabricated signal, not real signal. This is
    called out explicitly in the report as a data limitation.
  - `step` = hour index (1..743, ~31 days), used both for a time-based
    train/test split and for hour-of-day / day-of-month features.
"""
import pandas as pd
import numpy as np

FRAUD_TYPES = ["TRANSFER", "CASH_OUT"]

RAW_COLUMNS = [
    "step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
    "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud",
]

# RETROSPECTIVE features: everything, including POST-transaction balances
# (newbalanceOrig, newbalanceDest) and fields derived from them
# (errorBalanceOrig, errorBalanceDest, origDrained). Appropriate for offline /
# batch review use cases where the transaction has already settled — e.g.
# chargeback triage, overnight risk reports. NOT appropriate for blocking a
# transaction in real time, because these values don't exist yet at that
# moment.
FEATURE_COLUMNS = [
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "errorBalanceOrig",
    "errorBalanceDest",
    "amountToBalanceRatio",
    "origDrained",
    "destWasEmpty",
    "hourOfDay",
    "dayNumber",
    "type_TRANSFER",
]

# REAL-TIME features: only what is known BEFORE the transaction is approved —
# the amount being requested, the balances as they stand right now, the
# transaction type, and time. This is the honest, harder problem: can we flag
# a transaction as risky before it happens, not after?
REALTIME_FEATURE_COLUMNS = [
    "amount",
    "oldbalanceOrg",
    "oldbalanceDest",
    "amountToBalanceRatio_pre",
    "hourOfDay",
    "dayNumber",
    "type_TRANSFER",
]


def load_raw(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Unexpected schema, missing columns: {missing}")
    return df


def filter_to_fraud_prone_types(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only TRANSFER / CASH_OUT rows — the only types that ever carry fraud."""
    out = df[df["type"].isin(FRAUD_TYPES)].copy()
    return out


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered columns. Returns a new dataframe; does not mutate input."""
    out = df.copy()

    out["errorBalanceOrig"] = (
        out["oldbalanceOrg"] - out["amount"] - out["newbalanceOrig"]
    )
    out["errorBalanceDest"] = (
        out["oldbalanceDest"] + out["amount"] - out["newbalanceDest"]
    )
    out["amountToBalanceRatio"] = out["amount"] / (out["oldbalanceOrg"] + 1.0)
    # identical formula, kept as a separate name so real-time feature list is
    # self-documenting about only using pre-transaction info
    out["amountToBalanceRatio_pre"] = out["amountToBalanceRatio"]
    out["origDrained"] = (out["newbalanceOrig"] == 0).astype(int)
    out["destWasEmpty"] = (
        (out["oldbalanceDest"] == 0) & (out["newbalanceDest"] == 0)
    ).astype(int)
    out["hourOfDay"] = out["step"] % 24
    out["dayNumber"] = out["step"] // 24
    out["type_TRANSFER"] = (out["type"] == "TRANSFER").astype(int)

    return out


def build_realtime_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build exactly the pre-transaction features used by the live model."""
    out = df.copy()
    out["amountToBalanceRatio_pre"] = out["amount"] / (out["oldbalanceOrg"] + 1.0)
    out["hourOfDay"] = out["hour"]
    out["dayNumber"] = out["day"]
    out["type_TRANSFER"] = (out["type"] == "TRANSFER").astype(int)
    return out[REALTIME_FEATURE_COLUMNS]


def build_dataset(csv_path: str) -> pd.DataFrame:
    """Full pipeline: load -> filter -> engineer. One call, ready for modeling."""
    df = load_raw(csv_path)
    df = filter_to_fraud_prone_types(df)
    df = engineer_features(df)
    return df


def time_based_split(df: pd.DataFrame, train_frac: float = 0.8):
    """Split by `step` (time), never randomly — fraud patterns are temporal
    and a random split would leak future information into training."""
    max_step = df["step"].max()
    cutoff = int(max_step * train_frac)
    train = df[df["step"] <= cutoff].copy()
    test = df[df["step"] > cutoff].copy()
    return train, test, cutoff


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/paysim.csv"
    df = build_dataset(path)
    train, test, cutoff = time_based_split(df)
    print(f"Filtered rows: {len(df):,} (fraud rate {df['isFraud'].mean():.4%})")
    print(f"Split at step {cutoff}: train {len(train):,} rows, test {len(test):,} rows")
    print(f"Train fraud rate: {train['isFraud'].mean():.4%}, Test fraud rate: {test['isFraud'].mean():.4%}")
