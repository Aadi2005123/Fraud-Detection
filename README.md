# Fraud-Spike Detector

Built for the **Razorpay AI Buildathon — Track 02: AI Risk Manager**.

A two-layer fraud risk system on the PaySim synthetic mobile-money dataset:

1. **Per-transaction risk model** — scores each transaction's fraud probability
   *before* it completes, using only information available at that moment
   (amount, current balances, transaction type, time).
2. **Macro spike detector** — aggregates flagged transactions into an hourly
   time series and alerts when the flagged rate deviates sharply from its
   recent rolling baseline, independent of the per-transaction model.

Full results, all metrics, and — importantly — an honest investigation into
why one version of this model scores suspiciously well are in
**[`reports/REPORT.md`](reports/REPORT.md)**. Read that before the numbers
below; it's the part that actually matters for a risk-management pitch.

## Headline result

| | PR-AUC | Precision | Recall |
|---|---|---|---|
| Dataset's own `isFlaggedFraud` rule | — | 1.00 | 0.005 |
| Our real-time model (deployable, honest) | 0.996 | 0.95 | 0.999 |
| Retrospective model (batch review only — see caveat in report) | 1.000 | 1.00 | 1.00 |

The retrospective model's perfect score comes from features that only exist
*after* a transaction settles — it's a good tool for offline chargeback
review, not for blocking transactions in real time. The report explains why,
with the actual numbers behind that call. That distinction is the main thing
this project is trying to demonstrate, not just a leaderboard score.

## Get the data

Dataset: **PaySim — "Synthetic Financial Datasets For Fraud Detection"**
(search that name on Kaggle, by Edgar Lopez-Rojas / ealaxi). Download the CSV
and place it at `data/paysim.csv` (not committed to this repo — ~490MB).

## Run it

```bash
pip install -r requirements.txt
python run_pipeline.py
```

On Windows, use the project virtual environment if it exists:

```powershell
.venv\Scripts\python.exe run_pipeline.py
```

Takes a few minutes on ~2.8M rows. Outputs:
- `reports/REPORT.md` — full write-up
- `reports/metrics.json` — every number, machine-readable
- `reports/figures/*.png` — cost curve, PR curve, confusion matrix, spike
  timeline, SHAP importance, volume-collapse artifact
- `reports/*.joblib` / `reports/*.json` — trained model artifacts

## Project structure

```
src/
  features.py        - data loading, filtering, feature engineering, time-split
  train.py            - Logistic Regression baseline + XGBoost training
  evaluate.py          - metrics, cost-based threshold sweep
  spike_detector.py   - macro-layer hourly spike alerting
  explain.py          - SHAP explainability
run_pipeline.py        - orchestrates everything end-to-end, writes the report
reports/               - generated output (metrics, figures, models)
```

## Real-Time API

The optional FastAPI service loads `reports/xgb_realtime_model.json` and the
generated cost-optimal threshold from `reports/metrics.json`. It never retrains
the model at startup and accepts only pre-transaction fields.

Install the backend dependencies and start the API from the project root:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

The dashboard is a separate Vite app:

```powershell
cd frontend
npm install
npm run dev
```

MongoDB is optional. Copy `.env.example` to `.env`, then set `MONGODB_URI` and
`MONGODB_DATABASE` to persist prediction history. Predictions continue to work
when MongoDB is missing or unavailable.

Example request:

```json
{
  "amount": 1000,
  "oldbalanceOrg": 2000,
  "oldbalanceDest": 0,
  "type": "TRANSFER",
  "hour": 12,
  "day": 10
}
```

Example response:

```json
{
  "fraud_probability": 0.94,
  "risk_level": "HIGH",
  "decision": "FLAG",
  "threshold": 0.05
}
```

Endpoints: `GET /health`, `POST /predict`, `GET /transactions?limit=50`, and
`GET /stats`. The architecture is `React dashboard -> FastAPI -> saved
real-time XGBoost model`, with MongoDB used only as optional prediction storage.

## Scope: defense-only

This system scores and flags transactions for review. It does not generate,
simulate, or optimize fraud patterns, and does not expose thresholds or
weights in a way that would help an attacker probe or evade it in
production.

## What broke, and how we got out

The first full-feature model scored a suspicious PR-AUC of 1.0000. Rather
than report that, we traced it to `errorBalanceOrig` — a feature computed
from *post-transaction* balances that turns out to be a near-deterministic
artifact of how PaySim's fraud-injection logic works, not a realistic
real-world signal. We rebuilt the model using only pre-transaction
information and reported that (0.996 PR-AUC) as the honest, deployable
number. Full details in `reports/REPORT.md`, Section 2.
