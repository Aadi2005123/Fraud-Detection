# IEEE-CIS Fraud Detection Pipeline

## Dataset statistics

`train_transaction.csv` contains 590,540 transactions, 394 columns, and the
`isFraud` target. There are 3,142 frauds (0.5321%) and 587,398 legitimate rows.
`train_identity.csv` contains 144,233 identity records across 41 columns. It is
left-joined to transactions on `TransactionID`; the result remains exactly
590,540 rows. `TransactionDT` spans 86,400 to 15,811,131 and is used for a
chronological 80/20 held-out split.

## Selected features

Transaction-time features are amount and log amount, transaction hour/day/week,
card network (`card4`), card type (`card6`), card3, addresses (`addr1`, `addr2`),
purchase/receiver email domains, and selected identity-time verification fields:
`DeviceType`, `id_12`, `id_15`, `id_16`, `id_28`, `id_29`, `id_30` (OS), `id_31`
(browser), and `id_35`-`id_38`. Missing categorical values are an explicit
category and numeric missing values are zero-filled after conversion.

Raw `V`, `C`, `D`, and `M` families are excluded because they are opaque
engineered aggregates whose observation windows and construction are not clear.
Raw identity measurements, `DeviceInfo`, and high-cardinality card identifiers
`card1`, `card2`, and `card5` are excluded to reduce memorization and leakage
risk. `TransactionID` is excluded as a row identifier.

## Evaluation

The XGBoost model uses `scale_pos_weight = negatives / positives` for imbalance.
Metrics are evaluated only on the later chronological test period and written to
`reports/ieee_cis_metrics.json`. False-positive cost is assumed to be INR 75 per
false positive. False-negative cost is the sum of `TransactionAmt` for missed
fraud transactions. The separate model is saved at
`reports/ieee_cis_xgb_model.joblib`.

Run with:

```powershell
.venv\Scripts\python.exe run_ieee_cis_pipeline.py
```

## Limitations and leakage concerns

IEEE-CIS is a competition dataset with sparse identity coverage and many opaque
features. Some selected identity verification fields may encode collection or
device-era effects rather than durable fraud behavior; they should be reviewed
before production use. No post-transaction outcome, fraud label, or future
history feature is used. This pipeline is intentionally separate from PaySim
and BankSim and does not build a unified risk engine.