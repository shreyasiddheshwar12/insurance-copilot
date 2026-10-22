"""Simulated domain tools with explicit safety contracts.

lookup_synthetic_customer  READ   fetch renewal and consent fields by synthetic ID
save_draft                 WRITE  save a draft in the mock CRM; never contacts the customer
approve_draft              WRITE  records that a named agent reviewed the draft
simulate_send              WRITE  simulated only; needs approval AND opt-in consent

Every function writes an audit event. Audit details contain IDs and statuses only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .store import NotFoundError, PolicyError, Store

TEMPLATE_CITATION_PREFIX = "TEMPLATE:"


def lookup_synthetic_customer(store: Store, customer_id: str) -> dict[str, Any]:
    customer = store.customers.get(customer_id)
    if customer is None:
        raise NotFoundError(f"customer {customer_id} not found")
    policy = store.policies.get(customer_id, {})
    store.log("tool.lookup_synthetic_customer", customer_id=customer_id)
    return {
        **customer,
        "fictional_plan_id": policy.get("fictional_plan_id"),
        "policy_renewal_date": policy.get("renewal_date"),
    }


def save_draft(store: Store, customer_id: str, template_id: str) -> dict[str, Any]:
    customer = lookup_synthetic_customer(store, customer_id)
    if customer["consent_status"] != "opt_in":
        raise PolicyError(
            f"customer {customer_id} consent is '{customer['consent_status']}'; no draft may be prepared"
        )
    template = store.templates.get(template_id)
    if template is None:
        raise NotFoundError(f"template {template_id} not found")
    text = template["text"].format(customer_id=customer_id, renewal_date=customer["renewal_date"])
    draft = store.new_draft(
        customer_id=customer_id,
        template_id=template_id,
        text=text,
        citations=[f"{TEMPLATE_CITATION_PREFIX}{template_id}@{template['compliance_version']}"],
    )
    store.log("tool.save_draft", draft_id=draft["draft_id"], customer_id=customer_id, template_id=template_id)
    return draft


def approve_draft(store: Store, draft_id: str, agent_id: str) -> dict[str, Any]:
    if not agent_id or not agent_id.strip():
        raise PolicyError("an agent_id is required to approve a draft")
    draft = store.get_draft(draft_id)
    if draft["status"] != "pending_approval":
        raise PolicyError(f"draft {draft_id} is '{draft['status']}', not pending approval")
    draft["status"] = "approved"
    draft["approved_by"] = agent_id.strip()
    store.log("tool.approve_draft", draft_id=draft_id, agent_id=agent_id.strip())
    return draft


def simulate_send(store: Store, draft_id: str, agent_id: str | None) -> dict[str, Any]:
    draft = store.get_draft(draft_id)
    if not agent_id or not agent_id.strip():
        store.log("blocked.simulate_send", draft_id=draft_id, reason="no_agent")
        raise PolicyError("sending requires an explicit agent approval")
    if draft["status"] != "approved" or not draft["approved_by"]:
        store.log("blocked.simulate_send", draft_id=draft_id, reason="not_approved")
        raise PolicyError("sending is blocked until an agent approves the draft")
    consent = store.customers[draft["customer_id"]]["consent_status"]
    if consent != "opt_in":
        store.log("blocked.simulate_send", draft_id=draft_id, reason="consent")
        raise PolicyError(f"sending is blocked: consent is '{consent}'")
    draft["status"] = "simulated_sent"
    draft["simulated_sent_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.log("tool.simulate_send", draft_id=draft_id, agent_id=agent_id.strip())
    return draft
