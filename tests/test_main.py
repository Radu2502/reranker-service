import main


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