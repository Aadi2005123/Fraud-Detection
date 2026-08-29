import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from banksim import EDGE_COLUMNS, TRANSACTION_COLUMNS, engineer_banksim_features, load_banksim

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "ieee-cis-fraud" / "archive"


def test_banksim_schema_and_edge_relationships():
    transactions = load_banksim(DATA_DIR / "bs140513_032310.csv", DATA_DIR / "bsNET140513_032310.csv")
    edges = pd.read_csv(DATA_DIR / "bsNET140513_032310.csv")
    assert list(transactions.columns) == TRANSACTION_COLUMNS
    assert list(edges.columns) == EDGE_COLUMNS
    assert len(transactions) == len(edges) == 594643
    assert transactions["fraud"].sum() == 7200


def test_graph_features_are_prior_only():
    sample = pd.DataFrame([
        {"step": 0, "customer": "'c1'", "age": "'2'", "gender": "'F'", "zipcodeOri": "'1'", "merchant": "'m1'", "zipMerchant": "'1'", "category": "'food'", "amount": 10.0, "fraud": 0},
        {"step": 1, "customer": "'c1'", "age": "'2'", "gender": "'F'", "zipcodeOri": "'1'", "merchant": "'m1'", "zipMerchant": "'1'", "category": "'food'", "amount": 20.0, "fraud": 1},
    ])
    engineered = engineer_banksim_features(sample)
    assert engineered.iloc[0]["customer_prior_tx_count"] == 0
    assert engineered.iloc[1]["customer_prior_tx_count"] == 1
    assert engineered.iloc[1]["customer_merchant_prior_tx_count"] == 1
    assert engineered.iloc[1]["customer_prior_amount_mean"] == 10.0