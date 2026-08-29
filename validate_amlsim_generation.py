"""Validate AMLSim-compatible generated files and deterministic regeneration."""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "amlsim_generated" / "output"
EXPECTED = {"accounts_raw.csv": ["acct_id", "bank_id"], "transactions_raw.csv": ["tran_id", "orig_acct", "bene_acct", "base_amt", "tran_timestamp", "is_sar"], "alerts_raw.csv": ["alert_id", "alert_type", "is_sar"]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate():
    before = {}
    for filename, required in EXPECTED.items():
        path = OUTPUT / filename
        if not path.is_file():
            raise AssertionError(f"Missing generated file: {path}")
        before[filename] = digest(path)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise AssertionError(f"Generated file is empty: {path}")
        if any(column not in rows[0] for column in required):
            raise AssertionError(f"Missing columns in {path}")
        if filename == "transactions_raw.csv":
            for row in rows:
                if not row["tran_id"] or row["orig_acct"] == row["bene_acct"] or float(row["base_amt"]) <= 0 or row["is_sar"] not in {"True", "False"}:
                    raise AssertionError(f"Malformed transaction: {row}")
        if filename == "alerts_raw.csv" and not any(row["is_sar"] == "True" for row in rows):
            raise AssertionError("No SAR labels present")
    subprocess.run([sys.executable, str(ROOT / "generate_amlsim_dataset.py")], check=True, capture_output=True, text=True)
    after = {filename: digest(OUTPUT / filename) for filename in EXPECTED}
    if before != after:
        raise AssertionError("Generation is not reproducible for the configured seed")
    return {filename: sum(1 for _ in csv.DictReader((OUTPUT / filename).open(encoding="utf-8"))) for filename in EXPECTED}


if __name__ == "__main__":
    print(json.dumps({"status": "ok", "rows": validate()}, indent=2))