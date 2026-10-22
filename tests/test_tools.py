import pytest

from copilot.store import NotFoundError, PolicyError
from copilot.tools import approve_draft, lookup_synthetic_customer, save_draft, simulate_send

from .conftest import find_customer


def test_lookup_is_read_only_and_returns_consent(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    before = dict(store.customers[cid])
    result = lookup_synthetic_customer(store, cid)
    assert result["consent_status"] == "opt_in"
    assert store.customers[cid] == before  # no mutation


def test_lookup_unknown_customer_raises(store_and_index):
    store, _ = store_and_index
    with pytest.raises(NotFoundError):
        lookup_synthetic_customer(store, "C-999")


def test_save_draft_does_not_send(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    assert draft["status"] == "pending_approval"
    assert draft["simulated_sent_at"] is None


def test_opt_out_customer_cannot_get_draft(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_out")
    with pytest.raises(PolicyError):
        save_draft(store, cid, "RENEWAL_REMINDER_V1")


def test_auto_send_without_review_is_blocked(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    with pytest.raises(PolicyError, match="approv"):
        simulate_send(store, draft["draft_id"], agent_id="agent-1")
    assert any(e["event"] == "blocked.simulate_send" for e in store.audit)


def test_send_needs_agent_id(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    approve_draft(store, draft["draft_id"], "agent-1")
    with pytest.raises(PolicyError):
        simulate_send(store, draft["draft_id"], agent_id="  ")


def test_approved_opt_in_send_is_simulated_and_audited(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    approve_draft(store, draft["draft_id"], "agent-1")
    sent = simulate_send(store, draft["draft_id"], agent_id="agent-1")
    assert sent["status"] == "simulated_sent"
    assert sent["simulated_sent_at"] is not None
    assert any(e["event"] == "tool.simulate_send" for e in store.audit)


def test_consent_changed_after_approval_still_blocks(store_and_index):
    store, _ = store_and_index
    cid = find_customer(store, "opt_in")
    draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    approve_draft(store, draft["draft_id"], "agent-1")
    store.customers[cid]["consent_status"] = "opt_out"
    with pytest.raises(PolicyError, match="consent"):
        simulate_send(store, draft["draft_id"], agent_id="agent-1")
