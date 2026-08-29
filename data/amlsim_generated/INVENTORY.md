# AMLSim-Generated Dataset Inventory

## Provenance and execution

The preserved AMLSim source is under `data/amlsim-master/AMLSim-master/`.
Its documented Java flow is:

```text
python3 scripts/transaction_graph_generator.py conf.json
sh scripts/build_AMLSim.sh
sh scripts/run_AMLSim.sh conf.json
python3 scripts/convert_logs.py conf.json
```

That authentic flow was not executable in this workspace: the checkout has no
AMLSim dependency JARs or compiled classes, Maven is unavailable, and the
installed Java runtime is 25 while the project documents Java 8. No AMLSim
source was modified.

The generated files below are therefore an explicitly labeled **AMLSim-compatible
fallback**, driven by the checked-in `paramFiles/1K` semantics and created by:

```powershell
.venv\Scripts\python.exe generate_amlsim_dataset.py
```

Configuration: `data/amlsim_generated/config.json`; random seed: `20260824`.

## Output statistics

- Transactions: 201,400
- Accounts: 1,000
- Banks: 5 (`B00` through `B04`)
- Time range: `2017-01-02T00:00:00Z` to `2018-12-22T00:00:00Z`
- Transaction types: WIRE 51,175; CREDIT 50,534; TRANSFER 49,859; DEPOSIT 49,832
- Labels: `is_sar=False` 200,000; `is_sar=True` 1,400
- Alert-linked transactions: 1,400
- Alerts: 150
- Typologies: `fan_in` 50, `fan_out` 50, `cycle` 50
- Amount range: 20.00 to 1,994.79

## Files

- `output/transactions_raw.csv`: transaction-level raw generated output
- `output/accounts_raw.csv`: account and bank attributes
- `output/alerts_raw.csv`: typology and SAR alert membership metadata

The raw CSVs are preserved exactly as generated. No derived parquet or merged
copy was created.

## Features and graph relationships

Transaction fields are `tran_id`, `orig_acct`, `bene_acct`, `tx_type`,
`base_amt`, `tran_timestamp`, `is_sar`, and `alert_id`. Account fields include
account ID, status, currency, initial deposit, behavior model, bank ID, country,
and zip. Alert fields include alert ID, AML typology, SAR flag, member count,
main account, and start/end steps.

The directed graph relationship is `orig_acct -> bene_acct`, with transaction
type, amount, timestamp, and alert membership on each edge. The generated data
contains 1,000 origin entities, 1,000 beneficiary entities, and 182,228 unique
directed account pairs. Typologies create fan-in, fan-out, and cycle subgraphs.

## Decision-time boundary and leakage

Legitimate transaction-time fields are origin account, beneficiary account,
transaction type, amount, timestamp, and known account metadata such as bank,
country, account status, and behavior model. A system may also use prior
transaction history, if that history is maintained before the current decision.

`is_sar`, `alert_id`, alert typology, alert members, SAR account status, and
any post-review or post-investigation outcome are labels or retrospective
signals. They must not be used as real-time model features. The generated
`initial_deposit` is account setup information, not a post-transaction balance.

## Limitations

This is not a Java AMLSim run because the required runtime dependencies are
missing. It is a reproducible fallback for pipeline experimentation and should
not be presented as an official AMLSim benchmark. It uses synthetic account
metadata, fixed US country values, and deliberately simple typology generation.
No AML model was trained and no existing PaySim, BankSim, IEEE-CIS, or Risk
Engine file was modified.