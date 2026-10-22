"""Routes an agent's message to the right deterministic workflow.

The MVP uses rules and only ever answers from approved sources, so every claim is cited.
A Hugging Face classifier (Day 35) and an LLM adapter (Day 40) plug in here later.
"""

from __future__ import annotations

import re
from typing import Any

from .classifier import UNCLEAR
from .rag import BM25Index, tokenize
from .store import NotFoundError, PolicyError, Store
from .tools import lookup_synthetic_customer, save_draft

COMPLAINT = re.compile(r"complain|unhappy|angry|refund|not satisfied", re.IGNORECASE)
ESCALATE = re.compile(r"escalat|supervisor|manager", re.IGNORECASE)
RENEWAL = re.compile(r"renew|due date|reminder", re.IGNORECASE)
QUOTE = re.compile(r"compar|differen|versus|\bvs\b|benefit|cover|exclusion|silver|gold|platinum", re.IGNORECASE)
CUSTOMER_ID = re.compile(r"\bC-\d{3}\b", re.IGNORECASE)
UNSAFE_SEND = re.compile(
    r"auto-?send|send (it|this|the message|the draft) (now|without)|without (my |any )?(approval|review)",
    re.IGNORECASE,
)
PLAN_WORDS = {"silver": "SILVER", "gold": "GOLD", "platinum": "PLATINUM"}
STOPWORDS = {"what", "does", "for", "the", "and", "are", "is", "how", "with", "from", "that", "this", "about"}
COVERAGE_THRESHOLD = 0.7


def _content_terms(message: str) -> list[str]:
    return [t for t in tokenize(message) if len(t) > 2 and t not in STOPWORDS]


def _term_matches(term: str, text_tokens: set[str]) -> bool:
    # Light prefix match so "cover" matches "coverage" and "hospitalisation" matches itself.
    if term in text_tokens:
        return True
    return len(term) >= 5 and any(tok.startswith(term[:5]) for tok in text_tokens)


def handle(
    store: Store,
    index: BM25Index,
    message: str,
    customer_id: str | None = None,
    classifier: Any | None = None,
) -> dict[str, Any]:
    """Route one agent message.

    `classifier` is optional and only ever *informs* routing: it supplies an intent when the
    deterministic rules match nothing, instead of the old blind fallback to `documentation`.
    Safety controls below (unsafe-send detection, consent and approval gates) stay rule-based
    on purpose, so no model confidence score can unlock a send.
    """
    out: dict[str, Any] = {
        "intents": [],
        "answer_parts": [],
        "citations": [],
        "warnings": [],
        "missing_inputs": [],
        "escalated": False,
        "draft_id": None,
        "safety_flags": [],
        "predicted_intent": None,
        "intent_confidence": None,
    }

    if classifier is not None:
        predicted, confidence = classifier.predict_with_threshold(message)
        out["predicted_intent"] = predicted
        out["intent_confidence"] = confidence

    if UNSAFE_SEND.search(message):
        out["safety_flags"].append("unsafe_send_request")
        out["warnings"].append("Sending needs explicit agent approval and a consent check. Nothing was sent.")

    cid = customer_id
    if cid is None and (match := CUSTOMER_ID.search(message)):
        cid = match.group(0).upper()

    if COMPLAINT.search(message) or ESCALATE.search(message):
        out["intents"].append("escalation")
        out["escalated"] = True
        out["answer_parts"].append("This needs a human supervisor. No automated reply is prepared.")
    if RENEWAL.search(message):
        out["intents"].append("renewal")
        _handle_renewal(store, cid, out)
    plans = _plans_in(message)
    if QUOTE.search(message) and "escalation" not in out["intents"] and len(plans) >= 2:
        out["intents"].append("quote_question")
        _handle_compare(store, plans, out)
    elif QUOTE.search(message) and "escalation" not in out["intents"] and len(plans) == 1:
        out["intents"].append("documentation")
        _handle_docs(index, message, out)
    elif QUOTE.search(message) and "escalation" not in out["intents"]:
        out["intents"].append("quote_question")
        out["missing_inputs"].append("which plan (Silver, Gold or Platinum) the question is about")
    if not out["intents"]:
        _handle_unmatched(index, message, out)

    store.log(
        "ask",
        intents=out["intents"],
        escalated=out["escalated"],
        safety_flags=out["safety_flags"],
        predicted_intent=out["predicted_intent"],
        intent_confidence=out["intent_confidence"],
    )
    return out


def _handle_unmatched(index: BM25Index, message: str, out: dict[str, Any]) -> None:
    """No rule matched. Use the classifier's intent if it was confident, else ask.

    Previously this defaulted to `documentation` for everything, which silently mislabelled
    complaints and escalations.
    """
    predicted = out["predicted_intent"]

    if predicted in ("complaint", "escalation"):
        out["intents"].append(predicted)
        out["escalated"] = True
        out["answer_parts"].append("This needs a human supervisor. No automated reply is prepared.")
        return

    if predicted == "renewal":
        out["intents"].append("renewal")
        out["missing_inputs"].append("customer_id (for example C-204)")
        return

    if predicted in (None, UNCLEAR):
        # Name the missing input rather than guess, per the prompt standard.
        out["intents"].append("unclear")
        out["missing_inputs"].append("what the task is: a renewal, a product question, or filing")
        return

    out["intents"].append("documentation")
    _handle_docs(index, message, out)


def _handle_renewal(store: Store, cid: str | None, out: dict[str, Any]) -> None:
    if not cid:
        out["missing_inputs"].append("customer_id (for example C-204)")
        return
    try:
        customer = lookup_synthetic_customer(store, cid)
    except NotFoundError:
        out["missing_inputs"].append(f"a valid customer_id; {cid} was not found")
        return
    out["answer_parts"].append(f"{cid} renews on {customer['renewal_date']}.")
    if customer["consent_status"] != "opt_in":
        out["warnings"].append(
            f"Consent is '{customer['consent_status']}'. No reminder draft was prepared and no send is allowed."
        )
        return
    try:
        draft = save_draft(store, cid, "RENEWAL_REMINDER_V1")
    except PolicyError as exc:
        out["warnings"].append(str(exc))
        return
    out["draft_id"] = draft["draft_id"]
    out["citations"].extend(draft["citations"])
    out["answer_parts"].append(
        f"Reminder draft {draft['draft_id']} is saved and waits for your approval. It has not been sent."
    )


def _plans_in(message: str) -> list[str]:
    plans: list[str] = []
    for word, pid in PLAN_WORDS.items():
        if re.search(rf"\b{word}\b", message, re.IGNORECASE) and pid not in plans:
            plans.append(pid)
    return plans


def _handle_compare(store: Store, plans: list[str], out: dict[str, Any]) -> None:
    entries = {p["product_id"]: p for p in store.catalog if p["product_id"] in plans}
    if len(entries) < len(plans):
        out["missing_inputs"].append("a plan that is missing from the approved catalogue")
        return

    for pid in plans:
        entry = entries[pid]
        out["answer_parts"].append(f"{entry['name']}: {entry['coverage_summary']} [{entry['source_id']}]")
        out["citations"].append(entry["source_id"])

    for pid in plans:
        others = set().union(*(set(entries[o]["exclusions"]) for o in plans if o != pid))
        unique = [e for e in entries[pid]["exclusions"] if e not in others]
        if unique:
            out["answer_parts"].append(
                f"Only {entries[pid]['name']} excludes: {', '.join(unique)} [{entries[pid]['source_id']}]"
            )


def _handle_docs(index: BM25Index, message: str, out: dict[str, Any]) -> None:
    terms = _content_terms(message)
    hits = index.search(message, k=3)
    usable = []
    for hit in hits:
        if hit.flagged:
            out["safety_flags"].append(f"untrusted_instruction_in_source:{hit.chunk.source_id}")
            continue  # retrieved text is data, never instructions
        tokens = set(tokenize(hit.chunk.text))
        matched = sum(_term_matches(t, tokens) for t in terms)
        if terms and matched / len(terms) >= COVERAGE_THRESHOLD:
            usable.append(hit)
    if not usable:
        out["escalated"] = True
        out["answer_parts"].append("This is not in the approved sources, so I am escalating it to a human.")
        out["warnings"].append("Missing product fact: do not quote an answer to the customer.")
        return
    best = usable[0]
    out["answer_parts"].append(f"{best.chunk.text} [{best.chunk.source_id}]")
    out["citations"].append(best.chunk.source_id)
