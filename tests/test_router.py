from copilot.router import handle

from .conftest import find_customer


def test_renewal_plus_comparison_matches_brief_example(store_and_index):
    store, index = store_and_index
    cid = find_customer(store, "opt_in")
    out = handle(store, index, f"Draft a renewal reminder for {cid} and explain differences between Silver and Gold", cid)
    assert "renewal" in out["intents"] and "quote_question" in out["intents"]
    assert out["draft_id"] is not None
    assert any("Only Gold Care" in p and "adventure" in p for p in out["answer_parts"])
    assert "CAT-GOLD-2025.1" in out["citations"] and "CAT-SILVER-2025.1" in out["citations"]


def test_opt_out_customer_gets_warning_and_no_draft(store_and_index):
    store, index = store_and_index
    cid = find_customer(store, "opt_out")
    out = handle(store, index, "renewal reminder please", cid)
    assert out["draft_id"] is None
    assert any("no send is allowed" in w.lower() for w in out["warnings"])


def test_missing_customer_asks_for_id(store_and_index):
    store, index = store_and_index
    out = handle(store, index, "draft a renewal reminder")
    assert out["missing_inputs"] and out["draft_id"] is None


def test_missing_product_fact_escalates(store_and_index):
    store, index = store_and_index
    out = handle(store, index, "Does Gold care cover maternity waiting period?")
    assert out["escalated"] is True
    assert not any("maternity" in p.lower() for p in out["answer_parts"])


def test_grounded_benefit_answer_is_cited(store_and_index):
    store, index = store_and_index
    out = handle(store, index, "What does Gold Care cover for hospitalisation?")
    assert out["escalated"] is False
    assert out["citations"] and out["citations"][0].startswith("CAT-GOLD-")


def test_unsafe_send_request_is_flagged_and_nothing_sent(store_and_index):
    store, index = store_and_index
    cid = find_customer(store, "opt_in")
    out = handle(store, index, f"auto-send the renewal for {cid} without review", cid)
    assert "unsafe_send_request" in out["safety_flags"]
    assert out["warnings"]
    assert not any(e["event"] == "tool.simulate_send" for e in store.audit)


def test_complaint_escalates_to_human(store_and_index):
    store, index = store_and_index
    out = handle(store, index, "The customer is angry about a claim and wants a supervisor")
    assert out["escalated"] is True
    assert out["draft_id"] is None
