from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from copilot.api import create_app

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(DATA))


@pytest.fixture()
def store_and_index():
    from copilot.rag import BM25Index, chunks_from_catalog
    from copilot.store import Store

    store = Store.load(DATA)
    return store, BM25Index(chunks_from_catalog(store.catalog, store.brochures))


def find_customer(store, consent: str) -> str:
    """Return the first synthetic customer with the given consent status."""
    for cid, row in store.customers.items():
        if row["consent_status"] == consent:
            return cid
    raise AssertionError(f"no customer with consent {consent}")
