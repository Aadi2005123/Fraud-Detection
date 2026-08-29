"""Conservative, transaction-time IEEE-CIS fraud modelling helpers."""
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

TRANSACTION_PATH = "data/ieee-cis-fraud/train_transaction.csv"
IDENTITY_PATH = "data/ieee-cis-fraud/train_identity.csv"
TARGET = "isFraud"
IDENTITY_SELECTED = ["TransactionID", "DeviceType", "id_12", "id_15", "id_16", "id_28", "id_29", "id_30", "id_31", "id_35", "id_36", "id_37", "id_38"]
NUMERIC_COLUMNS = ["TransactionAmt", "card3", "addr1", "addr2"]
CATEGORICAL_COLUMNS = ["ProductCD", "card4", "card6", "P_emaildomain", "R_emaildomain", "DeviceType", "id_12", "id_15", "id_16", "id_28", "id_29", "id_30", "id_31", "id_35", "id_36", "id_37", "id_38"]
FEATURE_COLUMNS = ["TransactionAmt", "TransactionAmt_log", "transaction_hour", "transaction_day", "transaction_week"] + NUMERIC_COLUMNS[1:]
TRANSACTION_USECOLS = ["TransactionID", TARGET, "TransactionDT"] + FEATURE_COLUMNS[:1] + ["ProductCD", "card1", "card2", "card3", "card4", "card5", "card6", "addr1", "addr2", "P_emaildomain", "R_emaildomain"]


def load_ieee_cis(transaction_path=TRANSACTION_PATH, identity_path=IDENTITY_PATH):
    transactions = pd.read_csv(transaction_path, usecols=TRANSACTION_USECOLS)
    identities = pd.read_csv(identity_path, usecols=IDENTITY_SELECTED)
    if identities["TransactionID"].duplicated().any():
        raise ValueError("IEEE-CIS identity TransactionID must be unique")
    joined = transactions.merge(identities, on="TransactionID", how="left", validate="one_to_one")
    return joined


def engineer_features(df):
    """Create features available at transaction time; no target-derived values."""
    out = df.copy()
    out["TransactionAmt_log"] = np.log1p(out["TransactionAmt"].clip(lower=0))
    out["transaction_hour"] = (out["TransactionDT"] // 3600) % 24
    out["transaction_day"] = out["TransactionDT"] // 86400
    out["transaction_week"] = out["transaction_day"] // 7
    return out


def chronological_split(df, train_fraction=0.8):
    ordered = df.sort_values("TransactionDT", kind="stable")
    cutoff = ordered["TransactionDT"].quantile(train_fraction)
    train = ordered[ordered["TransactionDT"] <= cutoff].copy()
    test = ordered[ordered["TransactionDT"] > cutoff].copy()
    return train, test, float(cutoff)


def _clean_categories(df):
    out = df.copy()
    for column in CATEGORICAL_COLUMNS:
        out[column] = out[column].astype("string").fillna("__MISSING__")
    return out


def make_features(df, columns=None):
    clean = _clean_categories(df)
    numeric = clean[FEATURE_COLUMNS].copy()
    for column in numeric.columns:
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
        numeric[column] = numeric[column].replace([np.inf, -np.inf], np.nan).fillna(0)
    categorical = pd.get_dummies(clean[CATEGORICAL_COLUMNS], dtype=float)
    features = pd.concat([numeric.reset_index(drop=True), categorical.reset_index(drop=True)], axis=1)
    if columns is not None:
        features = features.reindex(columns=columns, fill_value=0)
    return features


def train_model(X_train, y_train):
    import xgboost as xgb

    positives = int(y_train.sum())
    negatives = len(y_train) - positives
    model = xgb.XGBClassifier(n_estimators=250, max_depth=6, learning_rate=0.08, subsample=0.9, colsample_bytree=0.85, scale_pos_weight=negatives / max(positives, 1), eval_metric="aucpr", random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, amounts, threshold=0.5, cost_per_fp=75.0):
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    y_array = np.asarray(y_test)
    amount_array = np.asarray(amounts)
    missed = (y_array == 1) & (predictions == 0)
    return {
        "threshold": threshold,
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "confusion_matrix": [[int(value) for value in row] for row in matrix],
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "false_positive_cost": float(fp * cost_per_fp),
        "false_negative_cost": float(amount_array[missed].sum()),
        "total_cost": float(fp * cost_per_fp + amount_array[missed].sum()),
        "true_negatives": int(tn),
        "true_positives": int(tp),
    }


def save_model(model, columns, output_path):
    joblib.dump({"model": model, "feature_columns": list(columns)}, output_path)