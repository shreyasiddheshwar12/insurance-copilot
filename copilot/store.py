"""In-memory store loaded from synthetic fixtures, plus the audit trail.

Good enough for the MVP. Swap for SQLite or Azure later without touching the tools.
"""

from __future__ import annotations

import csv
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class NotFoundError(LookupError):
    pass


class PolicyError(PermissionError):
    """Raised when a sensitive action breaks consent or approval rules."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Store:
    customers: dict[str, dict[str, Any]] = field(default_factory=dict)
    policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    catalog: list[dict[str, Any]] = field(default_factory=list)
    brochures: list[dict[str, Any]] = field(default_factory=list)
    templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    drafts: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def load(cls, data_dir: Path) -> "Store":
        store = cls()
        with (data_dir / "customers.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                store.customers[row["customer_id"]] = row
        with (data_dir / "policies.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                store.policies[row["customer_id"]] = row
        store.catalog = _read_jsonl(data_dir / "product_catalog.jsonl")
        store.brochures = _read_jsonl(data_dir / "brochures.jsonl")
        store.templates = {t["template_id"]: t for t in _read_jsonl(data_dir / "approved_templates.jsonl")}
        return store

    # ---- audit -------------------------------------------------------------
    def log(self, event: str, **details: Any) -> None:
        """Append an audit event. Never store free text from customers or secrets here."""
        with self._lock:
            self.audit.append({"ts": _utcnow(), "event": event, **details})

    # ---- drafts ------------------------------------------------------------
    def new_draft(self, customer_id: str, template_id: str, text: str, citations: list[str]) -> dict[str, Any]:
        draft = {
            "draft_id": f"D-{uuid.uuid4().hex[:8]}",
            "customer_id": customer_id,
            "template_id": template_id,
            "text": text,
            "citations": citations,
            "status": "pending_approval",
            "approved_by": None,
            "simulated_sent_at": None,
            "created_at": _utcnow(),
        }
        with self._lock:
            self.drafts[draft["draft_id"]] = draft
        return draft

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"draft {draft_id} not found")
        return draft


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
