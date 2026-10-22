"""FastAPI application: the copilot's HTTP surface.

Run locally:  uvicorn copilot.api:app --reload
Docs:         http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .classifier import TaskClassifier, load_split
from .rag import BM25Index, chunks_from_catalog
from .router import handle
from .store import NotFoundError, PolicyError, Store
from .tools import approve_draft, lookup_synthetic_customer, simulate_send

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "synthetic"


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    customer_id: str | None = Field(default=None, pattern=r"^C-\d{3}$")


class AskResponse(BaseModel):
    intents: list[str]
    answer_parts: list[str]
    citations: list[str]
    warnings: list[str]
    missing_inputs: list[str]
    escalated: bool
    draft_id: str | None
    safety_flags: list[str]
    predicted_intent: str | None = None
    intent_confidence: float | None = None


class AgentAction(BaseModel):
    agent_id: str = Field(min_length=1, max_length=64)


def create_app(data_dir: Path | None = None) -> FastAPI:
    data_dir = data_dir or Path(os.environ.get("COPILOT_DATA_DIR", DEFAULT_DATA_DIR))
    store = Store.load(data_dir)
    index = BM25Index(chunks_from_catalog(store.catalog, store.brochures))
    # Trained once at startup from the train split only (a few seconds on CPU).
    classifier = TaskClassifier.train(load_split(data_dir)[0])

    app = FastAPI(
        title="Insurance Agent Copilot (synthetic)",
        version="0.1.0",
        description="Educational prototype. Synthetic data only. Not a real insurance service.",
    )
    app.state.store = store
    app.state.index = index
    app.state.classifier = classifier

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "customers": len(store.customers), "catalog_items": len(store.catalog)}

    @app.get("/customers/{customer_id}")
    def get_customer(customer_id: str) -> dict[str, Any]:
        try:
            return lookup_synthetic_customer(store, customer_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/products")
    def products() -> list[dict[str, Any]]:
        return store.catalog

    @app.post("/ask", response_model=AskResponse)
    def ask(body: AskRequest) -> AskResponse:
        # Asking never sends anything. Sending is a separate, approved step below.
        result = handle(store, index, body.message, body.customer_id, classifier=classifier)
        return AskResponse(
            intents=result["intents"],
            answer_parts=result["answer_parts"],
            citations=result["citations"],
            warnings=result["warnings"],
            missing_inputs=result["missing_inputs"],
            escalated=result["escalated"],
            draft_id=result["draft_id"],
            safety_flags=result["safety_flags"],
            predicted_intent=result["predicted_intent"],
            intent_confidence=result["intent_confidence"],
        )

    @app.get("/drafts/{draft_id}")
    def get_draft(draft_id: str) -> dict[str, Any]:
        try:
            return store.get_draft(draft_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/drafts/{draft_id}/approve")
    def approve(draft_id: str, body: AgentAction) -> dict[str, Any]:
        try:
            return approve_draft(store, draft_id, body.agent_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PolicyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/drafts/{draft_id}/send")
    def send(draft_id: str, body: AgentAction) -> dict[str, Any]:
        try:
            return simulate_send(store, draft_id, body.agent_id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PolicyError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/audit")
    def audit() -> list[dict[str, Any]]:
        return store.audit

    return app


app = create_app()
