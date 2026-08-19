import pytest
import sentence_transformers


class FakeCrossEncoder:
    def __init__(self, *args, **kwargs):
        pass

    def predict(self, pairs):
        return [0.0] * len(pairs)


# Supresie temporara: monkeypatch global, la import-time, pe un simbol care e
# un tip. Nu e o eroare de adnotare — e [misc], nu [no-untyped-def], deci
# override-ul tests.* din pyproject nu o atinge. Dispare cand se schimba
# modul de injectare a modelului; pana atunci warn_unused_ignores semnaleaza
# ignore-ul daca ramane fara rost.
sentence_transformers.CrossEncoder = FakeCrossEncoder  # type: ignore[misc]

from fastapi.testclient import TestClient

from app import main

UTILIZATOR = "test_user"
PAROLA = "test_secret_123"


@pytest.fixture(autouse=True)
def credentiale(monkeypatch):
    # Autoused: fara ele, /api/rerank/chunks raspunde 500 (auth neconfigurat)
    # in toate testele, nu doar in cele de auth.
    monkeypatch.setenv("RAG_SERVICE_USERNAME", UTILIZATOR)
    monkeypatch.setenv("RAG_SERVICE_PASSWORD", PAROLA)


@pytest.fixture
def client():
    c = TestClient(main.app)
    c.auth = (UTILIZATOR, PAROLA)  # testele de rerank nu se ocupa de auth
    return c


@pytest.fixture
def client_fara_auth():
    return TestClient(main.app)
