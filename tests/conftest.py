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


@pytest.fixture
def client():
    return TestClient(main.app)
