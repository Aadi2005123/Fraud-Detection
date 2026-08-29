"""Human-readable explanations that mention only populated event fields."""


def explain(event):
    level = event.risk_level or "UNASSESSED"
    score = event.risk_score if event.risk_score is not None else 0.0
    contributions = sorted(event.signal_contributions, key=lambda item: item["contribution"], reverse=True)[:3]
    if not contributions:
        return f"{level} RISK - Score {score:.0f}. No risk signals were available."
    reasons = " ".join(f"{index}. {item['reason']} ({item['source']}; evidence: {item['evidence']})" for index, item in enumerate(contributions, 1))
    probability = f" Model probability: {event.fraud_probability:.1%}." if event.fraud_probability is not None else ""
    return f"{level} RISK - Score {score:.0f}; decision: {event.decision}. Reasons: {reasons}.{probability}"