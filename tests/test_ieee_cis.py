import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ieee_cis import engineer_features, make_features  # noqa: E402


def test_ieee_features_are_transaction_time_only():
    frame = pd.DataFrame({
        "TransactionID": [1], "isFraud": [0], "TransactionDT": [86400], "TransactionAmt": [12.5],
        "ProductCD": ["W"], "card1": [1], "card2": [2], "card3": [150], "card4": ["visa"], "card5": [1], "card6": ["credit"],
        "addr1": [100], "addr2": [10], "P_emaildomain": ["gmail.com"], "R_emaildomain": [None],
        "DeviceType": ["mobile"], "id_12": ["Found"], "id_15": ["New"], "id_16": ["Found"], "id_28": ["New"], "id_29": ["Found"],
        "id_30": ["Android 7.0"], "id_31": ["chrome 60"], "id_35": ["T"], "id_36": ["F"], "id_37": ["T"], "id_38": ["T"],
    })
    engineered = engineer_features(frame)
    features = make_features(engineered)
    assert "isFraud" not in features.columns
    assert "TransactionID" not in features.columns
    assert engineered.loc[0, "transaction_hour"] == 0
    assert engineered.loc[0, "transaction_day"] == 1


def test_feature_columns_align_when_category_is_unseen():
    first = pd.DataFrame({"TransactionDT": [1], "TransactionAmt": [1], "ProductCD": ["W"], "card3": [1], "addr1": [1], "addr2": [1], "card4": ["visa"], "card6": ["credit"], "P_emaildomain": ["a"], "R_emaildomain": ["a"], "DeviceType": ["mobile"], **{column: ["Found"] for column in ["id_12", "id_15", "id_16", "id_28", "id_29", "id_30", "id_31", "id_35", "id_36", "id_37", "id_38"]}})
    second = first.copy()
    second["ProductCD"] = "Z"
    train_features = make_features(engineer_features(first))
    test_features = make_features(engineer_features(second), train_features.columns)
    assert list(train_features.columns) == list(test_features.columns)