"""Train baseline Logistic Regression and XGBoost fraud models."""
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

from features import FEATURE_COLUMNS


def prepare_xy(df, feature_columns=FEATURE_COLUMNS):
    X = df[feature_columns].copy()
    y = df["isFraud"].copy()
    return X, y


def train_logistic_regression(X_train, y_train):
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)
    clf = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",  # handles imbalance without distorting rare fraud patterns
        random_state=42,
    )
    clf.fit(X_scaled, y_train)
    return clf, scaler


def train_xgboost(X_train, y_train):
    n_pos = y_train.sum()
    n_neg = len(y_train) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model, scale_pos_weight


def save_artifacts(lr_clf, scaler, xgb_model, out_dir="reports"):
    joblib.dump(lr_clf, f"{out_dir}/lr_model.joblib")
    joblib.dump(scaler, f"{out_dir}/lr_scaler.joblib")
    xgb_model.save_model(f"{out_dir}/xgb_model.json")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from features import build_dataset, time_based_split

    df = build_dataset("data/paysim.csv")
    train, test, cutoff = time_based_split(df)
    X_train, y_train = prepare_xy(train)
    X_test, y_test = prepare_xy(test)

    print("Training Logistic Regression baseline...")
    lr_clf, scaler = train_logistic_regression(X_train, y_train)

    print("Training XGBoost...")
    xgb_model, spw = train_xgboost(X_train, y_train)
    print(f"scale_pos_weight used: {spw:.2f}")

    save_artifacts(lr_clf, scaler, xgb_model)
    print("Models saved to reports/")
