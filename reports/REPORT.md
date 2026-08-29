# Fraud-Spike Detector — PaySim Dataset

**Track:** Razorpay AI Buildathon, Track 02 — AI Risk Manager
**Direction:** Fraud-Spike Detector (two-layer: per-transaction risk model + macro spike alerting)
**Dataset:** PaySim synthetic mobile-money transactions (`PS_20174392719_1491204439457_log.csv`)

## 1. Data summary

- Raw dataset: 6,362,620 transactions across 5 types.
- **Fraud only ever occurs in `TRANSFER` and `CASH_OUT` types** — confirmed by direct
  inspection, zero fraud in PAYMENT/CASH_IN/DEBIT. Filtered to these two types only:
  **2,770,409 rows**, overall fraud rate **0.2965%**.
- **Time-based split** (not random — fraud is temporal, random split leaks future data
  into training) at step 594 of 743:
  - Train: 2,719,123 rows, fraud rate 0.2412%
  - Test:  51,286 rows, fraud rate 3.2251%

### Known data limitation (documented, not hidden)

`nameOrig` is almost always unique per row (~6.35M unique out of 6.36M rows) — this
dataset does not contain repeat-customer transaction history. **Per-customer
velocity/frequency features were deliberately NOT built**, since they would be
fabricated signal rather than real signal on this data.

### Second limitation: volume collapse over time (see `volume_collapse_artifact.png`)

Legitimate transaction volume in the raw simulation collapses sharply after ~day 16
of 31 (from ~400K/day to under 15K/day, and just 282 transactions on the final day —
all of them fraud), while injected fraud count per hour stays roughly constant. This
means the test-set fraud rate (3.2251%) is elevated **because
legitimate volume dried up, not because fraud genuinely surged** — an artifact of how
the simulation was generated. This is exactly the kind of pattern the macro
spike-detector layer is designed to surface for human review regardless of root
cause: a risk manager doesn't just want "fraud went up," they want "the flagged rate
just moved sharply, go find out why."

## 2. Models — and an honesty check on the near-perfect score

| Model | PR-AUC (held-out) |
|---|---|
| Logistic Regression (baseline, class-weighted, retrospective features) | 0.9572 |
| **XGBoost, retrospective features** (scale_pos_weight=413.6) | 1.0000 |
| **XGBoost, real-time features only** (honest, harder problem) | 0.9959 |

**Baseline to beat** — the dataset's own `isFlaggedFraud` rule-based flag on the test set:
precision=1.0000, recall=0.0048, n_flagged=8.

The retrospective XGBoost model scores a near-perfect 1.0000 PR-AUC. **This is a
deliberate red flag we investigated rather than reported at face value.** Digging into
`errorBalanceOrig` (= oldbalanceOrg - amount - newbalanceOrig): it is ~0 for 99.45% of
fraud transactions vs only 9.49% of legitimate ones — a very strong, near-deterministic
signal baked into how PaySim's fraud-injection logic drains the origin account. The
catch: `newbalanceOrig` and `newbalanceDest` (and anything derived from them) are
**post-transaction** values. A real risk system deciding whether to *block* a
transaction does not have these numbers yet at decision time — they only exist after
the transaction has already gone through.

So the retrospective model (PR-AUC 1.0000) is realistic for an **offline /
batch use case** — e.g. overnight chargeback triage, reviewing settled transactions —
but would be **dishonest to present as a real-time blocking system**. We therefore also
trained a second model using only pre-transaction features (`amount`, `oldbalanceOrg`,
`oldbalanceDest`, amount-to-balance ratio, hour, day, type) — the actually deployable,
harder problem:

- **Real-time XGBoost PR-AUC: 0.9959**, precision=0.9522,
  recall=0.9994 @ threshold 0.5

This is the number we'd stand behind for a real-time pre-authorization system. See
`figures/precision_recall_curve.png`, which plots both curves side by side.

XGBoost (retrospective) @ default threshold 0.5: precision=1.0000,
recall=1.0000, f1=1.0000.

## 3. Cost-based threshold selection (the brief's "honest FP cost" requirement)

Run on the **real-time model only** — a cost-optimal threshold is only meaningful for
a model you could actually deploy to block transactions before they complete.

Cost assumptions (adjust to real business figures before production use):
- Cost per false positive: INR 75
  (assumed customer-friction / support cost of wrongly blocking a legitimate transaction)
- Cost per false negative: the actual fraud `amount` missed (not a flat average — a
  missed high-value fraud costs more than a missed small one)

**Cost-optimal threshold: 0.05**
- False positives: 83
- False negatives: 1
- Total business cost at this threshold: **INR 405,270**
- Precision=0.9522, Recall=0.9994,
  F1=0.9752

See `figures/cost_vs_threshold.png` for the full sweep, `figures/precision_recall_curve.png`
and `figures/confusion_matrix.png` for the standard views.

## 4. Macro spike-detection layer

Per-transaction flags (at the cost-optimal threshold, real-time model) are aggregated
into an hourly series with a rolling 24-hour mean/std; any hour where the flagged rate
exceeds mean + 3 std triggers a spike alert.

- **0 spike alerts** within the held-out test
  window alone (149 hours). This window sits entirely inside the
  volume-collapse tail (Section 1), so its own rolling baseline is already saturated
  near 100% flagged rate throughout — there's no earlier "normal" period within this
  narrow window for a z-score to compare against, so it correctly reports no
  *additional* spike on top of an already-elevated baseline.
- To demonstrate the alerting mechanism actually catching a regime shift, we also
  scored the **full 31-day timeline** (train+test combined) — **3
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

| feature                  |   mean_abs_shap |
|:-------------------------|----------------:|
| amountToBalanceRatio_pre |        8.34907  |
| oldbalanceDest           |        1.51552  |
| amount                   |        1.11191  |
| dayNumber                |        1.01664  |
| hourOfDay                |        0.721974 |

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
