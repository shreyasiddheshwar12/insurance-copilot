from .conftest import find_customer


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["customers"] >= 500


def test_get_customer_and_404(client):
    assert client.get("/customers/C-001").status_code == 200
    assert client.get("/customers/C-999").status_code == 404


def test_ask_never_sends(client):
    r = client.post("/ask", json={"message": "compare Silver and Gold"})
    assert r.status_code == 200
    body = r.json()
    assert body["draft_id"] is None
    assert "CAT-SILVER-2025.1" in body["citations"]


def test_full_approval_then_send_flow(client):
    store = client.app.state.store
    cid = find_customer(store, "opt_in")
    ask = client.post("/ask", json={"message": "renewal reminder", "customer_id": cid}).json()
    draft_id = ask["draft_id"]
    assert draft_id

    blocked = client.post(f"/drafts/{draft_id}/send", json={"agent_id": "agent-1"})
    assert blocked.status_code == 403

    approved = client.post(f"/drafts/{draft_id}/approve", json={"agent_id": "agent-1"})
    assert approved.status_code == 200

    sent = client.post(f"/drafts/{draft_id}/send", json={"agent_id": "agent-1"})
    assert sent.status_code == 200
    assert sent.json()["status"] == "simulated_sent"


def test_opt_out_send_is_forbidden(client):
    store = client.app.state.store
    cid = find_customer(store, "opt_in")
    draft_id = client.post("/ask", json={"message": "renewal", "customer_id": cid}).json()["draft_id"]
    store.customers[cid]["consent_status"] = "opt_out"
    client.post(f"/drafts/{draft_id}/approve", json={"agent_id": "agent-1"})
    assert client.post(f"/drafts/{draft_id}/send", json={"agent_id": "agent-1"}).status_code == 403


def test_rejects_bad_customer_id_format(client):
    r = client.post("/ask", json={"message": "hi", "customer_id": "204"})
    assert r.status_code == 422


def test_audit_trail_records_events(client):
    client.post("/ask", json={"message": "compare Silver and Gold"})
    events = client.get("/audit").json()
    assert any(e["event"] == "ask" for e in events)
