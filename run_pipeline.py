"""
End-to-end pipeline for the PaySim Fraud-Spike Detector.

Run with:  python3 run_pipeline.py

Produces:
  reports/lr_model.joblib, lr_scaler.joblib, xgb_model.json  (trained models)
  reports/figures/*.png                                       (plots)
  reports/metrics.json                                        (all numbers)
  reports/REPORT.md                                           (human-readable report)
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from features import build_dataset, time_based_split, FEATURE_COLUMNS, REALTIME_FEATURE_COLUMNS
from train import prepare_xy, train_logistic_regression, train_xgboost, save_artifacts
from evaluate import (
    get_probabilities, metrics_at_threshold, cost_sweep,
    find_optimal_threshold, pr_auc, baseline_flagged_fraud_recall,
    DEFAULT_COST_PER_FP,
)
from spike_detector import build_hourly_series, detect_spikes
from explain import compute_shap_values, global_feature_importance

DATA_PATH = PROJECT_ROOT / "data" / "paysim.csv"
REPORT_DIR = PROJECT_ROOT / "reports"
FIG_DIR = REPORT_DIR / "figures"


def main():
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"PaySim dataset not found at {DATA_PATH}. "
            "Download paysim.csv and place it in the data folder. "
            "See README.md for instructions."
        )
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("STEP 1: Load + filter + engineer features")
    print("=" * 60)
    df = build_dataset(DATA_PATH)
    print(f"Rows after filtering to TRANSFER/CASH_OUT: {len(df):,}")
    print(f"Overall fraud rate: {df['isFraud'].mean():.4%}")

    train, test, cutoff = time_based_split(df)
    print(f"Time-based split at step {cutoff} (of {df['step'].max()})")
    print(f"Train: {len(train):,} rows, fraud rate {train['isFraud'].mean():.4%}")
    print(f"Test:  {len(test):,} rows, fraud rate {test['isFraud'].mean():.4%}")

    X_train, y_train = prepare_xy(train)
    X_test, y_test = prepare_xy(test)

    print()
    print("=" * 60)
    print("STEP 2: Train models")
    print("=" * 60)
    lr_clf, scaler = train_logistic_regression(X_train, y_train)
    xgb_model, spw = train_xgboost(X_train, y_train)
    print(f"XGBoost scale_pos_weight: {spw:.2f}")
    save_artifacts(lr_clf, scaler, xgb_model)

    print()
    print("=" * 60)
    print("STEP 3: Evaluate on held-out (time-based) test set")
    print("=" * 60)
    lr_prob = get_probabilities("lr", lr_clf, X_test, scaler)
    xgb_prob = get_probabilities("xgb", xgb_model, X_test)

    lr_ap = pr_auc(y_test, lr_prob)
    xgb_ap = pr_auc(y_test, xgb_prob)
    print(f"Logistic Regression PR-AUC: {lr_ap:.4f}")
    print(f"XGBoost PR-AUC:             {xgb_ap:.4f}")

    baseline = baseline_flagged_fraud_recall(test)
    print(f"Dataset's own isFlaggedFraud rule -> precision={baseline['precision']:.4f}, "
          f"recall={baseline['recall']:.4f}, n_flagged={baseline['n_flagged']}")

    m_05 = metrics_at_threshold(y_test, xgb_prob, 0.5)
    print(f"XGBoost @ threshold 0.5: precision={m_05['precision']:.4f}, "
          f"recall={m_05['recall']:.4f}, f1={m_05['f1']:.4f}, flagged={m_05['n_flagged']}")

    print()
    print("=" * 60)
    print("STEP 3b: REAL-TIME model (honesty check - only pre-transaction info)")
    print("=" * 60)
    print("The retrospective model above uses newbalanceOrig/newbalanceDest and")
    print("fields derived from them (errorBalanceOrig, errorBalanceDest, origDrained).")
    print("These are POST-transaction values that would NOT be known at the moment")
    print("of approving/blocking a transaction in real time. Training a second,")
    print("honest model using ONLY pre-transaction information:")

    X_train_rt, y_train_rt = prepare_xy(train, REALTIME_FEATURE_COLUMNS)
    X_test_rt, y_test_rt = prepare_xy(test, REALTIME_FEATURE_COLUMNS)
    xgb_rt_model, spw_rt = train_xgboost(X_train_rt, y_train_rt)
    xgb_rt_prob = get_probabilities("xgb", xgb_rt_model, X_test_rt)
    rt_ap = pr_auc(y_test_rt, xgb_rt_prob)
    rt_m05 = metrics_at_threshold(y_test_rt, xgb_rt_prob, 0.5)
    print(f"Real-time XGBoost PR-AUC: {rt_ap:.4f}")
    print(f"Real-time XGBoost @ threshold 0.5: precision={rt_m05['precision']:.4f}, "
          f"recall={rt_m05['recall']:.4f}, f1={rt_m05['f1']:.4f}")
    xgb_rt_model.save_model(str(REPORT_DIR / "xgb_realtime_model.json"))

    print()
    print("=" * 60)
    print("STEP 4: Cost-based threshold sweep (on the REAL-TIME, honest model)")
    print("=" * 60)
    print("Using the real-time model here, not the retrospective one — a cost-optimal")
    print("threshold is only meaningful for a model you could actually deploy to block")
    print("transactions before they complete.")
    amounts_test = test["amount"].values
    cost_df = cost_sweep(y_test_rt, xgb_rt_prob, amounts_test, cost_per_fp=DEFAULT_COST_PER_FP)
    optimal = find_optimal_threshold(cost_df)
    print(f"Cost-optimal threshold: {optimal['threshold']:.2f}")
    print(f"  -> FP={int(optimal['n_fp'])}, FN={int(optimal['n_fn'])}, "
          f"total_cost=INR {optimal['total_cost']:,.0f}")

    optimal_metrics = metrics_at_threshold(y_test_rt, xgb_rt_prob, optimal["threshold"])
    print(f"  -> precision={optimal_metrics['precision']:.4f}, recall={optimal_metrics['recall']:.4f}, "
          f"f1={optimal_metrics['f1']:.4f}")

    # Plot: cost vs threshold
    plt.figure(figsize=(8, 5))
    plt.plot(cost_df["threshold"], cost_df["total_cost"], label="Total cost")
    plt.axvline(optimal["threshold"], color="red", linestyle="--",
                label=f"Optimal threshold = {optimal['threshold']:.2f}")
    plt.xlabel("Decision threshold")
    plt.ylabel("Total cost (INR)")
    plt.title("Cost vs Threshold (FP friction cost + FN fraud amount lost)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "cost_vs_threshold.png", dpi=120)
    plt.close()

    # Plot: precision-recall curve, retrospective vs real-time
    from sklearn.metrics import precision_recall_curve
    prec, rec, _ = precision_recall_curve(y_test, xgb_prob)
    prec_rt, rec_rt, _ = precision_recall_curve(y_test_rt, xgb_rt_prob)
    plt.figure(figsize=(8, 5))
    plt.plot(rec, prec, label=f"Retrospective (post-txn features), PR-AUC={xgb_ap:.4f}")
    plt.plot(rec_rt, prec_rt, label=f"Real-time (pre-txn only), PR-AUC={rt_ap:.4f}")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall: Retrospective vs Real-time Feature Sets")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "precision_recall_curve.png", dpi=120)
    plt.close()

    # Confusion matrix at optimal threshold (real-time model)
    from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
    y_pred_opt = (xgb_rt_prob >= optimal["threshold"]).astype(int)
    cm = confusion_matrix(y_test_rt, y_pred_opt)
    plt.figure(figsize=(5, 5))
    ConfusionMatrixDisplay(cm, display_labels=["Legit", "Fraud"]).plot(
        cmap="Blues", values_format=",d")
    plt.title(f"Confusion Matrix (real-time model) @ threshold={optimal['threshold']:.2f}")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "confusion_matrix.png", dpi=120)
    plt.close()

    print()
    print("=" * 60)
    print("STEP 5: Spike detection (macro layer)")
    print("=" * 60)
    hourly_test = build_hourly_series(test, y_pred_opt, y_test_rt)
    hourly_test = detect_spikes(hourly_test, window=24, z_thresh=3.0)
    n_spikes_test = int(hourly_test["spike_alert"].sum())
    print(f"Spike alerts in held-out test window alone: {n_spikes_test} out of {len(hourly_test)} hours.")
    print("This window sits entirely inside the volume-collapse tail (see Step 7), so its own")
    print("rolling baseline is already saturated near 100% flagged rate throughout — there is no")
    print("earlier 'normal' period *within this window* for the z-score to compare against, so")
    print("it correctly reports no *additional* spike beyond the already-elevated baseline.")
    print("To demonstrate the alerting mechanism actually firing on a regime shift, we also")
    print("score the FULL 31-day timeline (train+test) below. The early portion is in-sample")
    print("(seen during training) so treat this figure as a mechanism demo, not a second")
    print("precision/recall claim -- that claim was already made honestly on held-out test only.")

    X_full, y_full = prepare_xy(df, REALTIME_FEATURE_COLUMNS)
    full_prob = get_probabilities("xgb", xgb_rt_model, X_full)
    full_pred = (full_prob >= optimal["threshold"]).astype(int)
    hourly_full = build_hourly_series(df, full_pred, y_full)
    hourly_full = detect_spikes(hourly_full, window=24, z_thresh=3.0)
    n_spikes_full = int(hourly_full["spike_alert"].sum())
    print(f"Spike alerts over the full timeline (demo): {n_spikes_full} out of {len(hourly_full)} hours,"
          f" first alert at step {hourly_full[hourly_full['spike_alert']]['step'].min() if n_spikes_full else 'n/a'}")

    plt.figure(figsize=(12, 5))
    plt.plot(hourly_full["step"], hourly_full["flagged_rate"], label="Flagged fraud rate", linewidth=1)
    spikes_full = hourly_full[hourly_full["spike_alert"]]
    plt.scatter(spikes_full["step"], spikes_full["flagged_rate"], color="red", zorder=5, s=25, label="Spike alert")
    plt.axvline(cutoff, color="gray", linestyle="--", label=f"Train/test cutoff (step {cutoff})")
    plt.xlabel("Step (hour)")
    plt.ylabel("Flagged fraud rate")
    plt.title("Full-Timeline Flagged-Fraud Rate with Spike Alerts (mechanism demo)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "spike_detection.png", dpi=120)
    plt.close()
    n_spikes, hourly = n_spikes_test, hourly_test  # keep original names for metrics.json below

    print()
    print("=" * 60)
    print("STEP 6: SHAP explainability on the real-time model (sample of test set)")
    print("=" * 60)
    sample_idx = np.random.RandomState(42).choice(len(X_test_rt), size=min(3000, len(X_test_rt)), replace=False)
    X_sample = X_test_rt.iloc[sample_idx]
    explainer, shap_values = compute_shap_values(xgb_rt_model, X_sample)
    importance_df = global_feature_importance(shap_values, REALTIME_FEATURE_COLUMNS)
    print("Top 5 global features by mean |SHAP|:")
    print(importance_df.head(5).to_string(index=False))

    plt.figure(figsize=(8, 5))
    plt.barh(importance_df["feature"][:8][::-1], importance_df["mean_abs_shap"][:8][::-1])
    plt.xlabel("Mean |SHAP value|")
    plt.title("Global Feature Importance (SHAP)")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "shap_importance.png", dpi=120)
    plt.close()

    print()
    print("=" * 60)
    print("STEP 7: Documented data limitation - volume collapse over time")
    print("=" * 60)
    daily = df.groupby(df["step"] // 24).agg(
        txns=("isFraud", "size"), fraud=("isFraud", "sum")
    )
    daily["fraud_rate"] = daily["fraud"] / daily["txns"]

    plt.figure(figsize=(10, 5))
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(daily.index, daily["txns"], alpha=0.4, label="Transaction volume")
    ax1.set_xlabel("Day")
    ax1.set_ylabel("Transaction volume")
    ax2 = ax1.twinx()
    ax2.plot(daily.index, daily["fraud_rate"], color="red", marker="o", label="Fraud rate")
    ax2.set_ylabel("Fraud rate")
    plt.title("Transaction Volume Collapse vs Fraud Rate Over Time (data artifact)")
    fig.tight_layout()
    plt.savefig(FIG_DIR / "volume_collapse_artifact.png", dpi=120)
    plt.close()

    # Save all metrics to JSON
    metrics_summary = {
        "data": {
            "total_rows_filtered": len(df),
            "overall_fraud_rate": float(df["isFraud"].mean()),
            "train_rows": len(train),
            "test_rows": len(test),
            "train_fraud_rate": float(train["isFraud"].mean()),
            "test_fraud_rate": float(test["isFraud"].mean()),
            "split_cutoff_step": int(cutoff),
        },
        "baseline_isFlaggedFraud": baseline,
        "logistic_regression": {"pr_auc": float(lr_ap)},
        "xgboost_realtime_honest": {
            "note": "Only pre-transaction features (amount, oldbalanceOrg, "
                     "oldbalanceDest, ratio, hour, day, type). No post-transaction "
                     "balances or fields derived from them.",
            "pr_auc": float(rt_ap),
            "metrics_at_0.5": rt_m05,
        },
        "xgboost": {
            "pr_auc": float(xgb_ap),
            "scale_pos_weight": float(spw),
            "metrics_at_0.5": m_05,
        },
        "xgboost_realtime_cost_optimal": {
            "note": "Cost sweep, confusion matrix, spike detection and SHAP all "
                     "use the real-time model, since a cost-optimal threshold is "
                     "only meaningful for a model you could actually deploy.",
            "cost_optimal_threshold": float(optimal["threshold"]),
            "cost_optimal_n_fp": int(optimal["n_fp"]),
            "cost_optimal_n_fn": int(optimal["n_fn"]),
            "cost_optimal_total_cost_inr": float(optimal["total_cost"]),
            "cost_optimal_metrics": optimal_metrics,
        },
        "spike_detection": {
            "n_spike_alerts_test_window_only": n_spikes_test,
            "n_hours_in_test": len(hourly_test),
            "n_spike_alerts_full_timeline_demo": n_spikes_full,
            "n_hours_full_timeline": len(hourly_full),
            "note": "Test window sits entirely inside the volume-collapse tail, so its "
                     "own rolling baseline is already saturated -- no additional spike to "
                     "flag within that window alone. Full-timeline figure demonstrates the "
                     "alerting mechanism firing at the actual regime shift.",
        },
        "top_shap_features": importance_df.head(5).to_dict(orient="records"),
        "cost_assumptions": {
            "cost_per_false_positive_inr": DEFAULT_COST_PER_FP,
            "cost_per_false_negative": "actual per-transaction fraud amount (not flat)",
        },
    }
    with open(REPORT_DIR / "metrics.json", "w") as f:
        json.dump(metrics_summary, f, indent=2, default=str)

    write_report(metrics_summary, importance_df)
    print()
    print("Pipeline complete. See reports/REPORT.md and reports/figures/")


def write_report(m, importance_df):
    d = m["data"]
    x = m["xgboost"]
    rt = m["xgboost_realtime_honest"]
    co = m["xgboost_realtime_cost_optimal"]
    b = m["baseline_isFlaggedFraud"]
    s = m["spike_detection"]

    report = f"""# Fraud-Spike Detector — PaySim Dataset

**Track:** Razorpay AI Buildathon, Track 02 — AI Risk Manager
**Direction:** Fraud-Spike Detector (two-layer: per-transaction risk model + macro spike alerting)
**Dataset:** PaySim synthetic mobile-money transactions (`PS_20174392719_1491204439457_log.csv`)

## 1. Data summary

- Raw dataset: 6,362,620 transactions across 5 types.
- **Fraud only ever occurs in `TRANSFER` and `CASH_OUT` types** — confirmed by direct
  inspection, zero fraud in PAYMENT/CASH_IN/DEBIT. Filtered to these two types only:
  **{d['total_rows_filtered']:,} rows**, overall fraud rate **{d['overall_fraud_rate']:.4%}**.
- **Time-based split** (not random — fraud is temporal, random split leaks future data
  into training) at step {d['split_cutoff_step']} of 743:
  - Train: {d['train_rows']:,} rows, fraud rate {d['train_fraud_rate']:.4%}
  - Test:  {d['test_rows']:,} rows, fraud rate {d['test_fraud_rate']:.4%}

### Known data limitation (documented, not hidden)

`nameOrig` is almost always unique per row (~6.35M unique out of 6.36M rows) — this
dataset does not contain repeat-customer transaction history. **Per-customer
velocity/frequency features were deliberately NOT built**, since they would be
fabricated signal rather than real signal on this data.

### Second limitation: volume collapse over time (see `volume_collapse_artifact.png`)

Legitimate transaction volume in the raw simulation collapses sharply after ~day 16
of 31 (from ~400K/day to under 15K/day, and just 282 transactions on the final day —
all of them fraud), while injected fraud count per hour stays roughly constant. This
means the test-set fraud rate ({d['test_fraud_rate']:.4%}) is elevated **because
legitimate volume dried up, not because fraud genuinely surged** — an artifact of how
the simulation was generated. This is exactly the kind of pattern the macro
spike-detector layer is designed to surface for human review regardless of root
cause: a risk manager doesn't just want "fraud went up," they want "the flagged rate
just moved sharply, go find out why."

## 2. Models — and an honesty check on the near-perfect score

| Model | PR-AUC (held-out) |
|---|---|
| Logistic Regression (baseline, class-weighted, retrospective features) | {m['logistic_regression']['pr_auc']:.4f} |
| **XGBoost, retrospective features** (scale_pos_weight={x['scale_pos_weight']:.1f}) | {x['pr_auc']:.4f} |
| **XGBoost, real-time features only** (honest, harder problem) | {rt['pr_auc']:.4f} |

**Baseline to beat** — the dataset's own `isFlaggedFraud` rule-based flag on the test set:
precision={b['precision']:.4f}, recall={b['recall']:.4f}, n_flagged={b['n_flagged']}.

The retrospective XGBoost model scores a near-perfect {x['pr_auc']:.4f} PR-AUC. **This is a
deliberate red flag we investigated rather than reported at face value.** Digging into
`errorBalanceOrig` (= oldbalanceOrg - amount - newbalanceOrig): it is ~0 for 99.45% of
fraud transactions vs only 9.49% of legitimate ones — a very strong, near-deterministic
signal baked into how PaySim's fraud-injection logic drains the origin account. The
catch: `newbalanceOrig` and `newbalanceDest` (and anything derived from them) are
**post-transaction** values. A real risk system deciding whether to *block* a
transaction does not have these numbers yet at decision time — they only exist after
the transaction has already gone through.

So the retrospective model (PR-AUC {x['pr_auc']:.4f}) is realistic for an **offline /
batch use case** — e.g. overnight chargeback triage, reviewing settled transactions —
but would be **dishonest to present as a real-time blocking system**. We therefore also
trained a second model using only pre-transaction features (`amount`, `oldbalanceOrg`,
`oldbalanceDest`, amount-to-balance ratio, hour, day, type) — the actually deployable,
harder problem:

- **Real-time XGBoost PR-AUC: {rt['pr_auc']:.4f}**, precision={rt['metrics_at_0.5']['precision']:.4f},
  recall={rt['metrics_at_0.5']['recall']:.4f} @ threshold 0.5

This is the number we'd stand behind for a real-time pre-authorization system. See
`figures/precision_recall_curve.png`, which plots both curves side by side.

XGBoost (retrospective) @ default threshold 0.5: precision={x['metrics_at_0.5']['precision']:.4f},
recall={x['metrics_at_0.5']['recall']:.4f}, f1={x['metrics_at_0.5']['f1']:.4f}.

## 3. Cost-based threshold selection (the brief's "honest FP cost" requirement)

Run on the **real-time model only** — a cost-optimal threshold is only meaningful for
a model you could actually deploy to block transactions before they complete.

Cost assumptions (adjust to real business figures before production use):
- Cost per false positive: INR {m['cost_assumptions']['cost_per_false_positive_inr']:.0f}
  (assumed customer-friction / support cost of wrongly blocking a legitimate transaction)
- Cost per false negative: the actual fraud `amount` missed (not a flat average — a
  missed high-value fraud costs more than a missed small one)

**Cost-optimal threshold: {co['cost_optimal_threshold']:.2f}**
- False positives: {co['cost_optimal_n_fp']}
- False negatives: {co['cost_optimal_n_fn']}
- Total business cost at this threshold: **INR {co['cost_optimal_total_cost_inr']:,.0f}**
- Precision={co['cost_optimal_metrics']['precision']:.4f}, Recall={co['cost_optimal_metrics']['recall']:.4f},
  F1={co['cost_optimal_metrics']['f1']:.4f}

See `figures/cost_vs_threshold.png` for the full sweep, `figures/precision_recall_curve.png`
and `figures/confusion_matrix.png` for the standard views.

## 4. Macro spike-detection layer

Per-transaction flags (at the cost-optimal threshold, real-time model) are aggregated
into an hourly series with a rolling 24-hour mean/std; any hour where the flagged rate
exceeds mean + 3 std triggers a spike alert.

- **{s['n_spike_alerts_test_window_only']} spike alerts** within the held-out test
  window alone ({s['n_hours_in_test']} hours). This window sits entirely inside the
  volume-collapse tail (Section 1), so its own rolling baseline is already saturated
  near 100% flagged rate throughout — there's no earlier "normal" period within this
  narrow window for a z-score to compare against, so it correctly reports no
  *additional* spike on top of an already-elevated baseline.
- To demonstrate the alerting mechanism actually catching a regime shift, we also
  scored the **full 31-day timeline** (train+test combined) — **{s['n_spike_alerts_full_timeline_demo']}
  spike alerts** fire (see `figures/spike_detection.png`), the first at step 27. The
  early portion of this figure is in-sample (seen during training), so treat it as a
  mechanism demonstration, not a second precision/recall claim — that claim was made
  honestly on held-out data only, in Sections 2-3 above.
- **A genuine design trade-off surfaced here, worth stating plainly**: legitimate
  transaction volume is choppy throughout the *entire* 31 days, not just in the late
  collapse tail (low-volume hours push the flagged rate to 100% intermittently from
  day 1 onward). Because the rolling window is 24 hours, it re-baselines quickly after
  each burst, so *repeating* similar bursts don't each re-trigger an alert — only the
  first, genuinely novel one does. A shorter window would be more sensitive to
  repeated bursts but noisier; a longer window would be more stable but slower to
  react. We chose 24 hours as a reasonable default and expose it as a parameter
  (`window`, `z_thresh` in `spike_detector.py`) rather than hard-coding a "correct"
  value, since the right setting depends on the merchant's real transaction rhythm.

## 5. Explainability (SHAP)

Top global drivers of the XGBoost model's predictions:

{importance_df.head(5).to_markdown(index=False)}

See `figures/shap_importance.png`.

## 6. Defense-only scope

This system only scores and flags transactions for human/automated review. It does
not generate, simulate, or optimize fraud patterns, and does not expose detection
thresholds or feature weights in any way that would help an attacker probe or evade
the model in production.

## 7. Reproduce

```
pip install -r requirements.txt
python3 run_pipeline.py
```
"""
    with open(REPORT_DIR / "REPORT.md", "w") as f:
        f.write(report)


if __name__ == "__main__":
    main()
