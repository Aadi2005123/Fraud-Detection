"""Validate fraud-graph output and deterministic regeneration in a temp area."""
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "fraud_graph_generated"
REQUIRED = ["raw_nodes.csv", "raw_edges.csv", "fraud_labels.csv", "config.json", "INVENTORY.md"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    for name in REQUIRED:
        if not (OUTPUT / name).is_file():
            raise AssertionError(f"Missing file: {OUTPUT / name}")
    nodes = {row["account_id"] for row in csv.DictReader((OUTPUT / "raw_nodes.csv").open(encoding="utf-8"))}
    edges = list(csv.DictReader((OUTPUT / "raw_edges.csv").open(encoding="utf-8")))
    labels = list(csv.DictReader((OUTPUT / "fraud_labels.csv").open(encoding="utf-8")))
    if not nodes or not edges or not labels:
        raise AssertionError("Required generated files must have non-zero rows")
    for row in edges:
        if row["src_id"] not in nodes or row["dst_id"] not in nodes or row["src_id"] == row["dst_id"] or float(row["amount"]) <= 0:
            raise AssertionError(f"Malformed or dangling edge: {row}")
        if row["fraud_label"] not in {"0", "1"}:
            raise AssertionError(f"Invalid fraud label: {row['fraud_label']}")
    if not labels or any(row["pattern_type"] != "cycle" for row in labels):
        raise AssertionError("Fraud labels do not match supported generator output")
    before = {name: digest(OUTPUT / name) for name in ["raw_nodes.csv", "raw_edges.csv", "fraud_labels.csv", "config.json"]}
    temp = OUTPUT.with_name("fraud_graph_generated_repeat")
    if temp.exists():
        shutil.rmtree(temp)
    repeat_script = ROOT / "generate_fraud_graph_dataset.py"
    source_text = repeat_script.read_text(encoding="utf-8")
    source_text = source_text.replace('OUTPUT_ROOT = ROOT / "data" / "fraud_graph_generated"', 'OUTPUT_ROOT = ROOT / "data" / "fraud_graph_generated_repeat"')
    probe = ROOT / "generate_fraud_graph_repeat.py"
    probe.write_text(source_text, encoding="utf-8")
    try:
        result = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"Repeat generation failed: {result.stderr[-4000:]}")
    finally:
        probe.unlink(missing_ok=True)
    after = {name: digest(temp / name) for name in before}
    if before != after:
        mismatches = [name for name in before if before[name] != after[name]]
        shutil.rmtree(temp)
        raise AssertionError(f"Repeated generation hash mismatches: {mismatches}")
    shutil.rmtree(temp)
    return {"nodes": len(nodes), "edges": len(edges), "fraud_labels": len(labels)}


if __name__ == "__main__":
    print(json.dumps({"status": "ok", **validate()}, indent=2))