import pytest

from tests.conftest import PAROLA, UTILIZATOR

CALE = "/api/rerank/chunks"

PAYLOAD = {
    "query": "test",
    "chunks": [{"text": "unu", "score": 0.0, "chunk_id": "x"}],
    "top_k": 1,
}


def test_fara_credentiale_da_401(client_fara_auth):
    r = client_fara_auth.post(CALE, json=PAYLOAD)

    assert r.status_code == 401
    # fara headerul asta clientul nu stie ce schema de auth sa foloseasca
    assert r.headers["WWW-Authenticate"].startswith("Basic")


@pytest.mark.parametrize(
    ("user", "parola"),
    [
        (UTILIZATOR, "gresit"),
        ("altcineva", PAROLA),
        ("altcineva", "gresit"),
    ],
)
def test_credentiale_gresite_dau_401(client_fara_auth, user, parola):
    client_fara_auth.auth = (user, parola)
    r = client_fara_auth.post(CALE, json=PAYLOAD)

    assert r.status_code == 401


def test_credentiale_corecte_dau_200(client):
    r = client.post(CALE, json=PAYLOAD)

    assert r.status_code == 200
    assert len(r.json()["reranked_chunks"]) == 1


def test_health_ramane_liber(client_fara_auth):
    # sondat de healthcheck-ul din compose, care nu trimite credentiale
    r = client_fara_auth.get("/api/health")

    assert r.status_code == 200


def test_auth_neconfigurat_da_500_nu_trece_cererea(client, monkeypatch):
    # Deploy fara variabile in env: cererile trebuie sa cada, nu sa treaca.
    monkeypatch.delenv("RAG_SERVICE_PASSWORD")
    r = client.post(CALE, json=PAYLOAD)

    assert r.status_code == 500
