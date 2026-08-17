from itertools import pairwise

import pytest

from reranker import main

# Scoruri distincte si deterministe, cheie = textul chunk-ului. FakeCrossEncoder din
# conftest.py da [0.0]*n, deci orice ordonare trece; aici fiecare text are alt scor.
SCORURI = {
    "alfa": 0.31,
    "beta": 0.87,
    "gama": 0.05,
    "delta": 0.64,
    "epsilon": 0.42,
}

# Ordinea de intrare e intentionat DIFERITA de ordinea descrescatoare a scorurilor,
# ca un endpoint care nu sorteaza (sau sorteaza crescator) sa pice.
CHUNKS = [
    {"text": text, "score": 0.0, "chunk_id": text[0]}
    for text in ("alfa", "beta", "gama", "delta", "epsilon")
]

# beta 0.87 > delta 0.64 > epsilon 0.42 > alfa 0.31 > gama 0.05
ORDINE_ASTEPTATA = ["b", "d", "e", "a", "g"]


class ScoringCrossEncoder:
    """Cross-encoder fals care intoarce un scor distinct si stabil per text."""

    def predict(self, pairs):
        return [SCORURI[text] for _query, text in pairs]


@pytest.fixture
def client_cu_scoruri(client, monkeypatch):
    """Client cu modelul inlocuit de un fake cu scoruri distincte."""
    monkeypatch.setattr(main, "model", ScoringCrossEncoder())
    return client


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "model_loaded": True}


def test_rerank_ordoneaza_dupa_scor(client, monkeypatch):
    # controlăm exact ce scoruri "dă modelul": al 2-lea chunk câștigă
    monkeypatch.setattr(main.model, "predict", lambda pairs: [0.1, 0.9, 0.5])

    payload = {
        "query": "Cum resetez parola?",
        "chunks": [
            {"text": "Programul bibliotecii.",       "score": 0.0, "chunk_id": "a"},
            {"text": "Resetează parola din Setări.",  "score": 0.0, "chunk_id": "b"},
            {"text": "Link de recuperare.",           "score": 0.0, "chunk_id": "c"},
        ],
        "top_k": 2,
    }
    r = client.post("/api/rerank/chunks", json=payload)
    assert r.status_code == 200

    chunks = r.json()["reranked_chunks"]
    assert len(chunks) == 2               # top_k=2 taie lista
    assert chunks[0]["chunk_id"] == "b"   # scorul 0.9 → primul
    assert chunks[0]["original_rank"] == 2
    assert chunks[0]["rerank_score"] == 0.9
    assert chunks[1]["chunk_id"] == "c"   # scorul 0.5 → al doilea


def test_top_k_mai_mare_decat_lista(client, monkeypatch):
    # cazul-limită: top_k depășește nr. de chunks → nu trebuie să crape
    monkeypatch.setattr(main.model, "predict", lambda pairs: [0.2, 0.8])
    payload = {
        "query": "test",
        "chunks": [
            {"text": "unu", "score": 0.0, "chunk_id": "x"},
            {"text": "doi", "score": 0.0, "chunk_id": "y"},
        ],
        "top_k": 10,
    }
    r = client.post("/api/rerank/chunks", json=payload)
    assert r.status_code == 200
    assert len(r.json()["reranked_chunks"]) == 2


def test_rezultatul_e_ordonat_descrescator_dupa_scor(client_cu_scoruri):
    # top_k = tot, ca sa verificam ordinea completa, nu doar castigatorul
    payload = {"query": "intrebare", "chunks": CHUNKS, "top_k": len(CHUNKS)}
    r = client_cu_scoruri.post("/api/rerank/chunks", json=payload)
    assert r.status_code == 200

    chunks = r.json()["reranked_chunks"]
    assert len(chunks) == len(CHUNKS)

    scoruri = [c["rerank_score"] for c in chunks]
    # invarianta propriu-zisa: fiecare scor >= urmatorul
    assert all(a >= b for a, b in pairwise(scoruri)), scoruri
    # si concret, ordinea exacta — prinde si o sortare "stabila" care nu misca nimic
    assert [c["chunk_id"] for c in chunks] == ORDINE_ASTEPTATA
    assert scoruri == [0.87, 0.64, 0.42, 0.31, 0.05]


def test_top_k_taie_dupa_sortare_nu_inainte(client_cu_scoruri):
    # daca slice-ul s-ar face inainte de sortare, ar iesi alfa/beta/gama, nu top-ul real
    payload = {"query": "intrebare", "chunks": CHUNKS, "top_k": 3}
    r = client_cu_scoruri.post("/api/rerank/chunks", json=payload)
    assert r.status_code == 200

    chunks = r.json()["reranked_chunks"]
    assert [c["chunk_id"] for c in chunks] == ORDINE_ASTEPTATA[:3]

    scoruri = [c["rerank_score"] for c in chunks]
    assert all(a >= b for a, b in pairwise(scoruri)), scoruri


def test_original_rank_pastreaza_pozitia_din_input(client_cu_scoruri):
    # rank-ul e pozitia 1-based din request, nu pozitia dupa reordonare
    payload = {"query": "intrebare", "chunks": CHUNKS, "top_k": len(CHUNKS)}
    r = client_cu_scoruri.post("/api/rerank/chunks", json=payload)
    assert r.status_code == 200

    rank_dupa_id = {c["chunk_id"]: c["original_rank"] for c in r.json()["reranked_chunks"]}
    assert rank_dupa_id == {"a": 1, "b": 2, "g": 3, "d": 4, "e": 5}
