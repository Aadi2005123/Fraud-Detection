"""
Macro layer: aggregate per-transaction fraud flags into an hourly
(`step`) time series and flag hours where the flagged-fraud rate deviates
sharply from its recent rolling baseline — a "spike alert" a risk manager
can act on, independent of the underlying per-transaction model.

Note (documented limitation, verified from the raw data): in this dataset,
legitimate transaction VOLUME collapses sharply after ~day 16 of 31 while
injected fraud count per hour stays roughly constant, so the raw fraud
RATE rises late in the timeline as an artifact of the simulation winding
down — not because fraud genuinely surges. A rate-based spike detector
does not care about the cause: a rising flagged-fraud rate is exactly
the kind of thing a real risk manager needs to see and investigate,
whatever is driving it. This is called out explicitly in the report.
"""
import numpy as np
import pandas as pd


def build_hourly_series(df_test, y_pred, y_true):
    out = pd.DataFrame({
        "step": df_test["step"].values,
        "flagged": y_pred,
        "actual_fraud": y_true.values,
    })
    hourly = out.groupby("step").agg(
        n_txns=("flagged", "size"),
        n_flagged=("flagged", "sum"),
        n_actual_fraud=("actual_fraud", "sum"),
    ).reset_index()
    hourly["flagged_rate"] = hourly["n_flagged"] / hourly["n_txns"]
    return hourly


def detect_spikes(hourly, window=24, z_thresh=3.0):
    """Rolling z-score on flagged_rate; flag hours above z_thresh."""
    hourly = hourly.copy()
    roll_mean = hourly["flagged_rate"].rolling(window, min_periods=3).mean()
    roll_std = hourly["flagged_rate"].rolling(window, min_periods=3).std().replace(0, np.nan)
    hourly["rolling_mean"] = roll_mean
    hourly["rolling_std"] = roll_std
    hourly["z_score"] = (hourly["flagged_rate"] - roll_mean) / roll_std
    hourly["spike_alert"] = hourly["z_score"] > z_thresh
    return hourly
