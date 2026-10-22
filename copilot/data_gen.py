"""Generate reproducible SYNTHETIC fixtures for the copilot.

Everything here is fictional: customer IDs, cities, plans, brochures and templates.
Run:  python scripts/generate_data.py
The seed is fixed so every teammate gets identical files.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_CUSTOMERS = 500
N_INTERACTIONS = 1200

CITIES = ["Pune", "Mumbai", "Bengaluru", "Chennai", "Hyderabad", "Delhi", "Kolkata", "Ahmedabad"]
SEGMENTS = ["A", "B", "C"]
CONSENT_CHOICES = ["opt_in"] * 8 + ["opt_out"] + ["unknown"]  # ~80% / 10% / 10%
CATEGORIES = ["renewal", "quote-question", "documentation", "complaint", "escalation"]
NOTES = [
    "Customer asked about renewal date.",
    "Requested a comparison of two fictional plans.",
    "Sent policy document reminder.",
    "Customer unhappy with waiting period; logged for review.",
    "Asked to escalate to supervisor.",
]

# Fictional product catalogue. Gold has one extra exclusion versus Silver (brief test case).
PRODUCTS = [
    {
        "product_id": "SILVER",
        "name": "Silver Shield (fictional)",
        "version": "2025.1",
        "coverage_summary": "In-patient hospitalisation up to 3,00,000 per policy year for listed illnesses.",
        "exclusions": [
            "Cosmetic procedures",
            "Pre-existing conditions during the first 36 months",
        ],
    },
    {
        "product_id": "GOLD",
        "name": "Gold Care (fictional)",
        "version": "2025.1",
        "coverage_summary": "In-patient hospitalisation up to 6,00,000 per policy year, plus day-care procedures.",
        "exclusions": [
            "Cosmetic procedures",
            "Pre-existing conditions during the first 36 months",
            "Injuries from listed adventure sports",
        ],
    },
    {
        "product_id": "PLATINUM",
        "name": "Platinum Plus (fictional)",
        "version": "2026.1",
        "coverage_summary": "In-patient hospitalisation up to 10,00,000 per policy year, with a second-opinion benefit.",
        "exclusions": [
            "Cosmetic procedures",
            "Pre-existing conditions during the first 24 months",
            "Injuries from listed adventure sports",
        ],
    },
]

TEMPLATES = [
    {
        "template_id": "RENEWAL_REMINDER_V1",
        "channel": "sms",
        "text": (
            "Hello {customer_id}, this is a reminder that your fictional plan renews on {renewal_date}. "
            "Please contact your advisor to review the details. This is a non-binding message."
        ),
        "compliance_version": "2026.1",
    },
    {
        "template_id": "RENEWAL_REMINDER_EMAIL_V1",
        "channel": "email",
        "text": (
            "Dear customer {customer_id}, your fictional policy is due for renewal on {renewal_date}. "
            "Your advisor can explain any options. Nothing in this message is a binding offer."
        ),
        "compliance_version": "2026.1",
    },
]

BROCHURE_DOCS = [
    {
        "source_id": "BRO-SILVER-2025.1",
        "product_id": "SILVER",
        "version": "2025.1",
        "text": "Silver Shield covers in-patient hospitalisation up to 3,00,000 per policy year for listed illnesses.",
    },
]


# Labelled agent tasks for the classifier. Phrasings are synthetic templates with noise,
# including deliberately ambiguous wording between complaint and escalation.
TASK_TEMPLATES = {
    "renewal": [
        "When does {c} renew?",
        "Prepare the renewal reminder for {c}",
        "Customer {c} policy is due soon, draft a reminder",
        "Renewal date check for {c} please",
        "Send a renewal nudge to {c} next week",
    ],
    "quote-question": [
        "What is the difference between Silver and Gold for {c}?",
        "Does Platinum cover day-care procedures?",
        "Compare the two plans {c} is considering",
        "Is there a waiting period on Gold care?",
        "What exclusions apply to Silver Shield?",
    ],
    "documentation": [
        "Please attach the policy document for {c}",
        "Log the call note about the brochure for {c}",
        "Update the interaction record for {c}",
        "Save the KYC copy in the file for {c}",
        "File the signed acknowledgement from {c}",
    ],
    "complaint": [
        "Customer is unhappy with the claim delay for {c}",
        "I want to complain about the service {c} received",
        "{c} is angry about a rejected reimbursement",
        "Refund not received, {c} is very frustrated",
        "Customer says the agent was rude, {c} wants this on record",
    ],
    "escalation": [
        "Customer {c} asked for a supervisor",
        "Escalate this case for {c} to the manager",
        "Need senior review for {c}",
        "Please route the {c} file to the escalation desk",
        "{c} wants a callback from a team lead",
    ],
}
FILLERS = ["", "urgent: ", "follow-up: ", "please ", "note: "]


def build_labelled_tasks(rng: random.Random, per_label: int = 100) -> list[dict]:
    rows = []
    for label, templates in TASK_TEMPLATES.items():
        for _ in range(per_label):
            cid = f"C-{rng.randint(1, N_CUSTOMERS):03d}"
            text = rng.choice(templates).format(c=cid)
            rows.append({"text": rng.choice(FILLERS) + text, "label": label})
    rng.shuffle(rows)
    # Fixed split BEFORE any training. The test rows are never used to fit the model.
    cut = int(len(rows) * 0.8)
    for i, row in enumerate(rows):
        row["id"] = f"T-{i + 1:04d}"
        row["split"] = "train" if i < cut else "test"
    return rows


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def generate(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    start_window = date(2026, 10, 1)

    customers, policies = [], []
    for i in range(1, N_CUSTOMERS + 1):
        cid = f"C-{i:03d}"
        renewal = start_window + timedelta(days=rng.randint(0, 270))
        plan = rng.choice(PRODUCTS)["product_id"]
        start = renewal - timedelta(days=365)
        customers.append(
            {
                "customer_id": cid,
                "city": rng.choice(CITIES),
                "renewal_date": renewal.isoformat(),
                "synthetic_segment": rng.choice(SEGMENTS),
                "consent_status": rng.choice(CONSENT_CHOICES),
            }
        )
        policies.append(
            {
                "customer_id": cid,
                "fictional_plan_id": plan,
                "start_date": start.isoformat(),
                "renewal_date": renewal.isoformat(),
            }
        )

    interactions = []
    for n in range(1, N_INTERACTIONS + 1):
        interactions.append(
            {
                "interaction_id": f"I-{n:05d}",
                "customer_id": f"C-{rng.randint(1, N_CUSTOMERS):03d}",
                "category": rng.choice(CATEGORIES),
                "timestamp": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}T10:{rng.randint(0, 59):02d}:00",
                "agent_note_synthetic": rng.choice(NOTES),
            }
        )

    catalog = [
        {
            "product_id": p["product_id"],
            "version": p["version"],
            "name": p["name"],
            "coverage_summary": p["coverage_summary"],
            "exclusions": p["exclusions"],
            "source_id": f"CAT-{p['product_id']}-{p['version']}",
        }
        for p in PRODUCTS
    ]

    _write_csv(out_dir / "customers.csv", customers,
               ["customer_id", "city", "renewal_date", "synthetic_segment", "consent_status"])
    _write_csv(out_dir / "policies.csv", policies,
               ["customer_id", "fictional_plan_id", "start_date", "renewal_date"])
    _write_csv(out_dir / "interactions.csv", interactions,
               ["interaction_id", "customer_id", "category", "timestamp", "agent_note_synthetic"])
    _write_jsonl(out_dir / "product_catalog.jsonl", catalog)
    _write_jsonl(out_dir / "approved_templates.jsonl", TEMPLATES)
    _write_jsonl(out_dir / "brochures.jsonl", BROCHURE_DOCS)
    _write_jsonl(out_dir / "labelled_tasks.jsonl", build_labelled_tasks(random.Random(SEED)))


if __name__ == "__main__":
    generate(Path(__file__).resolve().parent.parent / "data" / "synthetic")
    print("Synthetic data written to data/synthetic")
