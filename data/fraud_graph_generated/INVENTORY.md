# Generated Fraud Graph Inventory

## Generator and configuration

This dataset is official output from the preserved `gen_fraud_graph` source
under `data/gen-fraud-graph-main/gen-fraud-graph-main`, invoked through the
project wrapper:

```powershell
.venv\Scripts\python.exe generate_fraud_graph_dataset.py
```

Configuration is recorded in [config.json](config.json). It uses scale `0.001`,
10,000 accounts, 90,000 normal transactions, 50 fraud rings, ring depth 4-7,
medium hardness, CSV output, fake 8-dimensional embeddings, one worker, and
random seed `20260824`. The wrapper makes the source fake embeddings deterministic
by deriving each vector from the fixed seed and description.

The native generator output is preserved under `generator_output/`, including
account shards, transaction shards, `fraud/transactions_fraud.csv`, and
`fraud/fraud_cases.csv`. The top-level CSVs are consolidated copies for analysis.

## Profile

- Nodes: 10,000, all supported node type `Account`
- Edges: 90,405 total: 90,135 normal and 270 fraud-ring edges
- Fraud rings: 50
- Ring sizes: depth 4 = 11, depth 5 = 16, depth 6 = 15, depth 7 = 8
- Fraud-ring involved nodes: 261
- Connected components: 1
- Directed graph density: 0.00090414
- Degree: mean 18.0810, median 18, minimum 4, maximum 36
- Node risk score: mean 0.4970, median 0.4991, minimum 0.0, maximum 0.9999
- Timestamps: normal edges `2024-01-01T10:00:00`; fraud edges
  `2024-01-01T12:00:00`; medium-hardness decoys
  `2024-01-01T13:00:00`

Fraud labels are supported by the generator's separate fraud transaction file
and `fraud_cases.csv`; consolidated edges carry `fraud_label` (`0` or `1`) and
`ring_id` only for fraud-ring edges. Fraud cases have native `pattern_id`,
`pattern_type=cycle`, `depth`, and pipe-separated `involved_accounts` fields.

## Available attributes

Account nodes contain `account_id`, synthetic customer name, balance, node
`risk_score`, creation date, and embedding. Transaction edges contain `tx_id`,
`src_id`, `dst_id`, amount, timestamp, description, and embedding. Native fraud
cases contain ring/group identifiers and involved accounts. The graph relation
is directed `src_id -> dst_id`; normal and fraud transaction edges share the
same account node universe.

## Decision-time boundary and leakage

Potential transaction-time features are amount, source/destination account IDs,
timestamp, transaction description, and any embedding computed from that
description before approval. Existing node balance, creation date, and account
risk score are available only if they represent a maintained pre-transaction
snapshot; their provenance must be enforced in production.

Do not use `fraud_label`, `ring_id`, `fraud_cases.csv`, `pattern_id`,
`pattern_type`, or `involved_accounts` as decision-time features. They are
generator labels and retrospective ground truth. Post-event graph aggregates,
future edges, and embeddings generated from post-investigation text would also
leak information. The generator timestamps are coarse and mostly constant, so
they do not provide realistic temporal variation.

## Limitations

The source generator documents cyclic fraud rings only; no other fraud typology
is represented. Medium hardness adds legitimate decoy cycles and amount jitter,
but the synthetic descriptions, risk scores, and random fake embeddings are not
calibrated production signals. No GNN or fraud model was trained, and this data
has not been integrated into the Common Risk Engine.