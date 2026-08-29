# BankSim Pipeline

## Dataset inspection

BankSim's transaction file is `data/ieee-cis-fraud/archive/bs140513_032310.csv`.
It contains 594,643 rows and the columns `step`, `customer`, `age`, `gender`,
`zipcodeOri`, `merchant`, `zipMerchant`, `category`, `amount`, and `fraud`.
There are 7,200 fraud rows (1.2108%). It contains 4,112 customers, 50
merchants, 15 categories, 180 steps, and age/gender values including unknowns.

The graph/edge-list file is `data/ieee-cis-fraud/archive/bsNET140513_032310.csv`.
It has the same rows and the columns `Source`, `Target`, `Weight`, `typeTrans`,
and `fraud`. Every row aligns with the transaction file: `Source` is customer,
`Target` is merchant, `Weight` is amount, and `typeTrans` is category.

## Features and evaluation

The separate pipeline uses a chronological 80/20 split at step 143. Features
include current amount, age, zipcodes, gender, category, and prior-history
customer/merchant counts, repeated customer-merchant edge count, merchant
customer concentration, customer merchant diversity, and prior mean amounts.
Counts and means exclude the current row and all future rows. No fraud label or
post-transaction field is used.

Run `.venv\Scripts\python.exe run_banksim_pipeline.py`. The model is saved as
`reports/banksim_xgb_model.joblib`; metrics, including precision, recall, F1,
PR-AUC, confusion matrix, and false-positive cost, are saved as
`reports/banksim_metrics.json`. False-positive cost is explicitly assumed to be
INR 75 per false positive and should be replaced with a measured business cost.

## Limitations

BankSim is synthetic, all origin zipcodes are identical, and the edge list is a
transaction-level duplicate rather than a richer independent graph. The
pipeline uses simple graph history features only; no GNN is implemented.