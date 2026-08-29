"""SHAP explanations for the XGBoost model - top drivers per prediction."""
import numpy as np
import pandas as pd
import shap


def compute_shap_values(xgb_model, X_sample):
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_sample)
    return explainer, shap_values


def top_features_for_row(shap_values_row, feature_names, top_n=3):
    idx = np.argsort(-np.abs(shap_values_row))[:top_n]
    return [(feature_names[i], float(shap_values_row[i])) for i in idx]


def global_feature_importance(shap_values, feature_names):
    mean_abs = np.abs(shap_values).mean(axis=0)
    order = np.argsort(-mean_abs)
    return pd.DataFrame({
        "feature": [feature_names[i] for i in order],
        "mean_abs_shap": mean_abs[order],
    })
