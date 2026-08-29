"""
Evaluation on the held-out (time-based) test set.

Includes the cost-based threshold sweep the brief explicitly asks for:
"Honest metrics including false-positive cost."

Cost assumptions (documented, not hidden):
  - cost_per_FP: assumed customer-friction cost of wrongly flagging a
    legitimate transaction (support ticket + delayed transfer). Default
    INR 75 per flag — adjust to your real support-cost figure.
  - cost_per_FN: the actual fraud amount lost, computed per-transaction
    from `amount` (not a flat average) — a missed high-value fraud costs
    more than a missed small one, and the sweep reflects that.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    precision_recall_curve, average_precision_score, confusion_matrix,
)

DEFAULT_COST_PER_FP = 75.0  # INR, customer friction / support cost


def get_probabilities(model_type, model, X_test, scaler=None):
    if model_type == "lr":
        X_scaled = scaler.transform(X_test)
        return model.predict_proba(X_scaled)[:, 1]
    elif model_type == "xgb":
        return model.predict_proba(X_test)[:, 1]
    raise ValueError(model_type)


def metrics_at_threshold(y_true, y_prob, threshold):
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "threshold": threshold,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "n_flagged": int(y_pred.sum()),
    }


def cost_sweep(y_true, y_prob, amounts, cost_per_fp=DEFAULT_COST_PER_FP, thresholds=None):
    """Sweep thresholds, compute total business cost at each.
    total_cost = (false_positives * cost_per_fp) + (sum of amounts for false negatives)
    """
    if thresholds is None:
        thresholds = np.arange(0.01, 1.0, 0.01)

    y_true = np.asarray(y_true)
    amounts = np.asarray(amounts)
    rows = []
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        fp_mask = (y_pred == 1) & (y_true == 0)
        fn_mask = (y_pred == 0) & (y_true == 1)

        n_fp = fp_mask.sum()
        n_fn = fn_mask.sum()
        fn_amount_lost = amounts[fn_mask].sum()
        fp_cost = n_fp * cost_per_fp
        total_cost = fp_cost + fn_amount_lost

        rows.append({
            "threshold": t,
            "n_fp": int(n_fp),
            "n_fn": int(n_fn),
            "fp_cost": fp_cost,
            "fn_amount_lost": fn_amount_lost,
            "total_cost": total_cost,
        })
    return pd.DataFrame(rows)


def find_optimal_threshold(cost_df):
    best = cost_df.loc[cost_df["total_cost"].idxmin()]
    return best


def pr_auc(y_true, y_prob):
    return average_precision_score(y_true, y_prob)


def baseline_flagged_fraud_recall(df_test):
    """How well the dataset's own isFlaggedFraud rule performs, as a baseline
    to beat. (In the raw data this rule catches ~16/8213 fraud overall.)"""
    y_true = df_test["isFraud"]
    y_pred = df_test["isFlaggedFraud"]
    return {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "n_flagged": int(y_pred.sum()),
    }
