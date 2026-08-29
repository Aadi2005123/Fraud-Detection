"""Generate a reproducible AMLSim-compatible fallback dataset.

The Java AMLSim runtime cannot run in this checkout because its dependency jars
and compiled classes are absent. This generator follows the checked-in AMLSim
parameter semantics without modifying or claiming to execute the Java runtime.
"""
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "data" / "amlsim_generated" / "config.json"


def timestamp(base, step):
    return (base + timedelta(days=step)).isoformat().replace("+00:00", "Z")


def generate(config):
    rng = random.Random(config["random_seed"])
    output = ROOT / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    base = datetime.fromisoformat(config["base_date"].replace("Z", "+00:00"))
    accounts = []
    for account_id in range(config["account_count"]):
        accounts.append({
            "acct_id": f"A{account_id:06d}", "dsply_nm": f"Account {account_id:06d}",
            "type": "SAV", "acct_stat": "A", "acct_rptng_crncy": "USD",
            "prior_sar_count": "False", "branch_id": account_id % 20,
            "open_dt": timestamp(base, 0), "close_dt": timestamp(base, config["total_steps"]),
            "initial_deposit": f"{rng.uniform(50000, 100000):.2f}",
            "tx_behavior_id": rng.choice([0, 1, 2, 3, 4, 5]), "bank_id": f"B{account_id % config['bank_count']:02d}",
            "country": "US", "zip": f"{10000 + account_id % 90000:05d}",
        })
    tx_header = ["tran_id", "orig_acct", "bene_acct", "tx_type", "base_amt", "tran_timestamp", "is_sar", "alert_id"]
    alert_header = ["alert_id", "alert_type", "is_sar", "member_count", "main_acct", "start_step", "end_step"]
    transactions = []
    alerts = []
    tx_id = 1
    alert_id = 1
    tx_types = ["TRANSFER", "WIRE", "CREDIT", "DEPOSIT"]
    for _ in range(config["normal_transaction_count"]):
        origin = rng.randrange(config["account_count"])
        beneficiary = rng.randrange(config["account_count"] - 1)
        if beneficiary >= origin:
            beneficiary += 1
        step = rng.randrange(1, config["total_steps"] + 1)
        transactions.append([tx_id, f"A{origin:06d}", f"A{beneficiary:06d}", rng.choice(tx_types), f"{rng.uniform(20, 1000):.2f}", timestamp(base, step), "False", ""])
        tx_id += 1
    typologies = ["fan_in", "fan_out", "cycle"]
    for typology_index in range(config["typology_count"]):
        typology = typologies[typology_index % len(typologies)]
        members = rng.sample(range(config["account_count"]), config["accounts_per_typology"])
        start = rng.randrange(1, config["total_steps"] - 20)
        end = start + rng.randrange(5, 21)
        current_alert = f"ALERT_{alert_id:06d}"
        alerts.append([current_alert, typology, "True", len(members), f"A{members[0]:06d}", start, end])
        if typology == "fan_in":
            pairs = [(member, members[0]) for member in members[1:]]
        elif typology == "fan_out":
            pairs = [(members[0], member) for member in members[1:]]
        else:
            pairs = list(zip(members, members[1:] + members[:1]))
        for offset, (origin, beneficiary) in enumerate(pairs):
            transactions.append([tx_id, f"A{origin:06d}", f"A{beneficiary:06d}", "WIRE", f"{rng.uniform(100, 2000):.2f}", timestamp(base, min(end, start + offset)), "True", current_alert])
            tx_id += 1
        alert_id += 1
    with (output / "accounts_raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(accounts[0]))
        writer.writeheader(); writer.writerows(accounts)
    with (output / "transactions_raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(tx_header); writer.writerows(transactions)
    with (output / "alerts_raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(alert_header); writer.writerows(alerts)
    return output, len(transactions), accounts, alerts


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    output, tx_count, accounts, alerts = generate(config)
    print(f"Generated {tx_count:,} transactions, {len(accounts):,} accounts, {len(alerts):,} alerts at {output}")


if __name__ == "__main__":
    main()