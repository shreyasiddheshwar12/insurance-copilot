import csv
import json
from pathlib import Path

from copilot.data_gen import N_CUSTOMERS, generate

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def test_generator_is_reproducible(tmp_path):
    generate(tmp_path)
    for name in ["customers.csv", "policies.csv", "interactions.csv", "product_catalog.jsonl"]:
        assert (tmp_path / name).read_bytes() == (DATA / name).read_bytes(), name


def test_minimum_row_counts():
    with (DATA / "customers.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == N_CUSTOMERS >= 500


def test_no_real_looking_identifiers():
    # Synthetic IDs only: C-001 style. Fails if someone pastes a real-looking record.
    with (DATA / "customers.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            assert row["customer_id"].startswith("C-") and row["customer_id"][2:].isdigit()


def test_gold_has_extra_exclusion_vs_silver():
    catalog = {}
    for line in (DATA / "product_catalog.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        catalog[item["product_id"]] = set(item["exclusions"])
    assert catalog["GOLD"] - catalog["SILVER"] == {"Injuries from listed adventure sports"}
