# Risk Engine V2

## Architecture

Each source remains independent. A dataset adapter creates a `RiskEvent` and
`NormalizedRiskSignal` objects from fields that exist in that source. The
engine consumes those normalized objects; it never concatenates raw datasets
and never averages incompatible model probabilities.

## Signals and adapters

- PaySim: model probability, amount risk, and transfer/cash-out behavior.
- BankSim: model probability, prior customer behavior, prior merchant behavior,
  and prior customer-merchant relationship counts when supplied.
- IEEE-CIS: model probability, transaction amount, device, and identity signals.
- AMLSim: model probability and prior fan-in, fan-out, cycle, or network counts
  when supplied. `is_sar`, `alert_id`, `alert_type`, pattern IDs, involved
  accounts, and investigation fields are excluded.
- Fraud Graph: model probability plus transaction-time degree, connection,
  concentration, and structural scores when supplied. `fraud_label`, `ring_id`,
  pattern IDs, involved accounts, and fraud-case metadata are excluded.

Missing source fields remain null and do not generate signals.

## Scoring policy

Signals are clamped to `[0, 1]`. Categories use these transparent weights:

```text
model       0.40
behavioral  0.20
network     0.20
aml         0.10
anomaly     0.10
```

For each event, only available categories participate and the active weights
are renormalized. Each signal is multiplied by its confidence. The final score
is:

```text
100 * sum(active_weight * risk_value * confidence)
    / sum(active_weight * confidence)
```

The result is clamped to `[0, 100]`. This combines one dataset/model output
with independent behavioral, network, AML, and anomaly evidence without
blindly averaging model probabilities. The model probability remains visible
as its own signal and audit field.

Risk levels and decisions are:

| Score | Level | Decision |
|---:|---|---|
| 0-29 | LOW | ALLOW |
| 30-69 | MEDIUM | REVIEW |
| 70-100 | HIGH | FLAG |

No automatic blocking policy is implemented.

## Explainability and audit

Every decision includes the final score, level, decision, top three signal
contributors, source, reason, evidence, and model probability when available.
The audit trail stores event ID, dataset, event timestamp, model names and
probabilities, input signals, individual signals, weighted contributions, final
score, decision, explanation, and policy version `risk-engine-v2`.

## Cost and evaluation

V2 is a decision layer, not a retraining or evaluation pipeline. Existing
dataset-specific held-out metrics and cost reports remain authoritative. Any
future unified evaluation must evaluate each dataset independently first; a
single cross-dataset ground-truth metric is not statistically justified because
PaySim, BankSim, IEEE-CIS, AMLSim, and Fraud Graph use different labels,
sampling processes, and distributions. False-positive cost remains an explicit
dataset-pipeline assumption where available: INR 75 per false positive in the
existing evaluations. False-negative cost is the missed fraud amount in those
evaluations.

## Leakage prevention and limitations

Runtime adapters exclude labels, ring IDs, fraud cases, investigation outcomes,
and future graph aggregates. Prior-history fields are accepted only when the
caller has computed them before the decision; the engine cannot independently
prove their temporal provenance. The current adapters use simple heuristics and
do not calibrate scores across datasets. No raw datasets are merged, no models
are retrained, and no frontend/API integration is included in V2.