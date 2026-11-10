import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import main

# aceleasi valori pe care tests/conftest.py le pune in mediu inainte de import
AUTH = (os.environ["API_USER"], os.environ["API_PASSWORD"])

PAYLOAD = {
    "query": "Cum resetez parola?",
    "chunks": [
        {"text": "Programul bibliotecii.",       "score": 0.0, "chunk_id": "a"},
        {"text": "Resetează parola din Setări.",  "score": 0.0, "chunk_id": "b"},
        {"text": "Link de recuperare.",           "score": 0.0, "chunk_id": "c"},
    ],
    "top_k": 2,
}


class FakeCrossEncoder:
    """Model fals: intoarce scorurile primite, fara sa incarce nimic."""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        return self._scores


@pytest.fixture
def client() -> Iterator[TestClient]:
    # FARA `with`: asa lifespan-ul NU ruleaza, deci modelul real nu se incarca.
    c = TestClient(main.app)
    yield c
    # app-ul e un singleton de modul — starea nu are voie sa curga intre teste
    if hasattr(main.app.state, "model"):
        del main.app.state.model


def test_health(client: TestClient) -> None:
    # public: fara auth, si fara model incarcat spune adevarul, nu "ok" din oficiu
    assert client.get("/api/health").json() == {"status": "ok", "model_loaded": False}

    main.app.state.model = FakeCrossEncoder([])
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "model_loaded": True}


def test_rerank_ordoneaza_dupa_scor(client: TestClient) -> None:
    # controlăm exact ce scoruri "dă modelul": al 2-lea chunk câștigă
    main.app.state.model = FakeCrossEncoder([0.1, 0.9, 0.5])

    r = client.post("/api/rerank/chunks", json=PAYLOAD, auth=AUTH)
    assert r.status_code == 200

    chunks = r.json()["reranked_chunks"]
    assert len(chunks) == 2               # top_k=2 taie lista
    assert chunks[0]["chunk_id"] == "b"   # scorul 0.9 → primul
    assert chunks[0]["original_rank"] == 2
    assert chunks[0]["rerank_score"] == 0.9
    assert chunks[1]["chunk_id"] == "c"   # scorul 0.5 → al doilea


def test_top_k_mai_mare_decat_lista(client: TestClient) -> None:
    # cazul-limită: top_k depășește nr. de chunks → nu trebuie să crape
    main.app.state.model = FakeCrossEncoder([0.2, 0.8])
    payload = {
        "query": "test",
        "chunks": [
            {"text": "unu", "score": 0.0, "chunk_id": "x"},
            {"text": "doi", "score": 0.0, "chunk_id": "y"},
        ],
        "top_k": 10,
    }
    r = client.post("/api/rerank/chunks", json=payload, auth=AUTH)
    assert r.status_code == 200
    assert len(r.json()["reranked_chunks"]) == 2


def test_rerank_fara_credentiale(client: TestClient) -> None:
    main.app.state.model = FakeCrossEncoder([0.1, 0.9, 0.5])
    r = client.post("/api/rerank/chunks", json=PAYLOAD)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Basic"


def test_rerank_credentiale_gresite(client: TestClient) -> None:
    main.app.state.model = FakeCrossEncoder([0.1, 0.9, 0.5])
    # si user gresit, si parola gresita, si combinatia user corect + parola gresita
    for auth in (("alt-user", "alt-parola"), (AUTH[0], "parola-gresita"), ("alt-user", AUTH[1])):
        r = client.post("/api/rerank/chunks", json=PAYLOAD, auth=auth)
        assert r.status_code == 401, auth
        assert r.headers["WWW-Authenticate"] == "Basic"


def test_rerank_credentiale_corecte(client: TestClient) -> None:
    main.app.state.model = FakeCrossEncoder([0.1, 0.9, 0.5])
    r = client.post("/api/rerank/chunks", json=PAYLOAD, auth=AUTH)
    assert r.status_code == 200
    assert r.json()["reranked_chunks"][0]["chunk_id"] == "b"
