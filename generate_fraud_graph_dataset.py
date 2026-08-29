"""Run the preserved gen_fraud_graph package into an isolated output area."""
import csv
from concurrent.futures import Future
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "data" / "gen-fraud-graph-main" / "gen-fraud-graph-main"
OUTPUT_ROOT = ROOT / "data" / "fraud_graph_generated"
GENERATOR_OUTPUT = OUTPUT_ROOT / "generator_output"
sys.path.insert(0, str(SOURCE_ROOT / "src"))

from gen_fraud_graph import Config, FraudGraphGenerator  # noqa: E402
from gen_fraud_graph.embeddings import EmbeddingGenerator  # noqa: E402
import gen_fraud_graph.generator as generator_module  # noqa: E402

CONFIG = {
    "source": "data/gen-fraud-graph-main/gen-fraud-graph-main",
    "scale_factor": 0.001,
    "num_accounts": 10000,
    "num_transactions": 90000,
    "num_fraud_rings": 50,
    "fraud_ring_depth_range": [4, 7],
    "embedding_provider": "fake",
    "embedding_dim": 8,
    "workers": 1,
    "batches_per_worker": 1,
    "output_format": "csv",
    "hardness": "medium",
    "random_seed": 20260824,
}


def deterministic_embeddings(self, texts):
    """Make the source generator's fake provider deterministic per description."""
    vectors = []
    for text in texts:
        seed = int(hashlib.sha256(f"{CONFIG['random_seed']}:{text}".encode()).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vectors.append(rng.random(self.dim).astype("float32"))
    return np.asarray(vectors)


class InlineExecutor:
    """Run the source generator's one-worker jobs in-process for reproducibility."""

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except BaseException as error:
            future.set_exception(error)
        return future


def consolidate():
    account_files = sorted((GENERATOR_OUTPUT / "accounts").glob("accounts_*.csv"))
    transaction_files = sorted((GENERATOR_OUTPUT / "transactions").glob("transactions_*.csv"))
    fraud_file = GENERATOR_OUTPUT / "fraud" / "transactions_fraud.csv"
    cases_file = GENERATOR_OUTPUT / "fraud" / "fraud_cases.csv"
    with (OUTPUT_ROOT / "raw_nodes.csv").open("w", newline="", encoding="utf-8") as target:
        writer = None
        for path in account_files:
            with path.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                if writer is None:
                    writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
                    writer.writeheader()
                writer.writerows(reader)
    cases = {}
    with cases_file.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            for account_id in row["involved_accounts"].split("|"):
                cases[account_id] = row["pattern_id"]
    with (OUTPUT_ROOT / "raw_edges.csv").open("w", newline="", encoding="utf-8") as target:
        writer = None
        for path in transaction_files + [fraud_file]:
            with path.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                fields = list(reader.fieldnames) + ["fraud_label", "ring_id"]
                if writer is None:
                    writer = csv.DictWriter(target, fieldnames=fields)
                    writer.writeheader()
                for row in reader:
                    row["fraud_label"] = "1" if path == fraud_file else "0"
                    row["ring_id"] = next((cases.get(node) for node in (row.get("src_id"), row.get("dst_id")) if cases.get(node)), "") if path == fraud_file else ""
                    writer.writerow(row)
    shutil.copyfile(cases_file, OUTPUT_ROOT / "fraud_labels.csv")


def generate():
    if OUTPUT_ROOT.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True)
    (OUTPUT_ROOT / "config.json").write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    random.seed(CONFIG["random_seed"])
    np.random.seed(CONFIG["random_seed"])
    EmbeddingGenerator.generate = deterministic_embeddings
    generator_module.ProcessPoolExecutor = InlineExecutor
    config = Config(
        scale_factor=CONFIG["scale_factor"],
        num_fraud_rings=CONFIG["num_fraud_rings"],
        fraud_ring_depth_range=tuple(CONFIG["fraud_ring_depth_range"]),
        embedding_provider=CONFIG["embedding_provider"],
        embedding_dim=CONFIG["embedding_dim"],
        workers=CONFIG["workers"],
        batches_per_worker=CONFIG["batches_per_worker"],
        output_format=CONFIG["output_format"],
        output_dir=str(GENERATOR_OUTPUT),
        hardness=CONFIG["hardness"],
    )
    FraudGraphGenerator(config).run()
    consolidate()
    print(f"Generated graph dataset at {OUTPUT_ROOT}")


if __name__ == "__main__":
    generate()