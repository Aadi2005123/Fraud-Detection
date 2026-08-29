"""BankSim loading, prior-history graph features, training, and evaluation helpers."""
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score

TRANSACTION_COLUMNS = ["step", "customer", "age", "gender", "zipcodeOri", "merchant", "zipMerchant", "category", "amount", "fraud"]
EDGE_COLUMNS = ["Source", "Target", "Weight", "typeTrans", "fraud"]
FEATURE_COLUMNS = ["step", "age", "amount", "zipcodeOri", "zipMerchant", "customer_prior_tx_count", "merchant_prior_tx_count", "customer_merchant_prior_tx_count", "merchant_prior_customer_count", "customer_prior_merchant_count", "customer_prior_amount_mean", "merchant_prior_amount_mean"]
CATEGORICAL_COLUMNS = ["gender", "category"]


def load_banksim(transaction_path, edge_path=None):
    """Load and validate BankSim transactions and its equivalent edge list."""
    transactions = pd.read_csv(transaction_path)
    missing = set(TRANSACTION_COLUMNS) - set(transactions.columns)
    if missing:
        raise ValueError(f"BankSim transaction schema missing columns: {sorted(missing)}")
    if edge_path is not None:
        edges = pd.read_csv(edge_path)
        missing_edges = set(EDGE_COLUMNS) - set(edges.columns)
        if missing_edges:
            raise ValueError(f"BankSim edge schema missing columns: {sorted(missing_edges)}")
        if len(edges) != len(transactions):
            raise ValueError("BankSim transactions and edge list must have equal row counts")
        clean_customer = transactions["customer"].astype(str).str.strip("'").to_numpy()
        clean_source = edges["Source"].astype(str).str.strip("'").to_numpy()
        clean_merchant = transactions["merchant"].astype(str).str.strip("'").to_numpy()
        clean_target = edges["Target"].astype(str).str.strip("'").to_numpy()
        if not (clean_customer == clean_source).all() or not (clean_merchant == clean_target).all():
            raise ValueError("BankSim edge endpoints do not align with transactions")
    return transactions


def _clean_categories(df):
    out = df.copy()
    for column in ["customer", "merchant", "gender", "category", "zipcodeOri", "zipMerchant", "age"]:
        out[column] = out[column].astype(str).str.strip("'")
    return out


def engineer_banksim_features(df):
    """Build features using only the current row and earlier graph history."""
    out = _clean_categories(df).sort_values(["step"], kind="stable").copy()
    customer = out["customer"]
    merchant = out["merchant"]
    pair = customer + "\x1f" + merchant
    out["customer_prior_tx_count"] = customer.groupby(customer).cumcount()
    out["merchant_prior_tx_count"] = merchant.groupby(merchant).cumcount()
    out["customer_merchant_prior_tx_count"] = pair.groupby(pair).cumcount()
    first_customer_at_merchant = ~out.duplicated(["merchant", "customer"])
    out["merchant_prior_customer_count"] = first_customer_at_merchant.groupby(merchant).cumsum() - first_customer_at_merchant.astype(int)
    first_merchant_for_customer = ~out.duplicated(["customer", "merchant"])
    out["customer_prior_merchant_count"] = first_merchant_for_customer.groupby(customer).cumsum() - first_merchant_for_customer.astype(int)
    out["customer_prior_amount_mean"] = out.groupby("customer")["amount"].transform(
        lambda values: values.shift().expanding().mean()
    ).fillna(0)
    out["merchant_prior_amount_mean"] = out.groupby("merchant")["amount"].transform(
        lambda values: values.shift().expanding().mean()
    ).fillna(0)
    return out


def _numeric_features(df):
    numeric = df[["step", "age", "amount", "zipcodeOri", "zipMerchant"] + FEATURE_COLUMNS[5:]].copy()
    for column in ["age", "zipcodeOri", "zipMerchant"]:
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce").fillna(-1)
    categorical = pd.get_dummies(df[CATEGORICAL_COLUMNS], dtype=float)
    return pd.concat([numeric.reset_index(drop=True), categorical.reset_index(drop=True)], axis=1)


def make_xy(df, columns=None):
    features = _numeric_features(df)
    if columns is not None:
        features = features.reindex(columns=columns, fill_value=0)
    return features, df["fraud"].astype(int)


def chronological_split(df, train_fraction=0.8):
    cutoff = int(df["step"].max() * train_fraction)
    return df[df["step"] <= cutoff].copy(), df[df["step"] > cutoff].copy(), cutoff


def train_model(X_train, y_train):
    import xgboost as xgb

    positives = int(y_train.sum())
    negatives = len(y_train) - positives
    model = xgb.XGBClassifier(n_estimators=220, max_depth=5, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9, scale_pos_weight=negatives / max(positives, 1), eval_metric="aucpr", random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, amounts, threshold=0.5, cost_per_fp=75.0):
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    fraud_amounts = np.asarray(amounts)[np.asarray(y_test) == 1]
    missed_fraud = np.asarray(y_test)[np.asarray(y_test) == 1] & (predictions[np.asarray(y_test) == 1] == 0)
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "confusion_matrix": [[int(value) for value in row] for row in matrix],
        "false_positive_count": int(fp),
        "false_positive_cost": float(fp * cost_per_fp),
        "false_negative_count": int(fn),
        "false_negative_amount_lost": float(fraud_amounts[missed_fraud].sum()),
        "true_negative_count": int(tn),
        "true_positive_count": int(tp),
    }


def save_model(model, columns, output_path):
    joblib.dump({"model": model, "feature_columns": list(columns)}, output_path)