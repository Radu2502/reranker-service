import logging

import pytest

from app.logging.logging_setup import setup_logging


@pytest.fixture(autouse=True)
def root_intact():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers, root.level = handlers, level


def test_lipsa_log_level_foloseste_info(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    setup_logging()
    assert logging.getLogger().level == logging.INFO


def test_log_level_minuscule_e_acceptat(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    setup_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_log_level_invalid_cade_pe_info_fara_sa_crape(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "TRACE")
    setup_logging()
    assert logging.getLogger().level == logging.INFO
