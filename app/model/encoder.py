"""Incarcarea si inferenta cross-encoder-ului, separate de stratul HTTP."""

import logging
import time
from typing import Any

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

log = logging.getLogger(__name__)


def load_model() -> Any:
    """Construieste cross-encoder-ul; se apeleaza O DATA, din lifespan."""
    log.info("model_loading")
    _t0 = time.perf_counter()
    model = CrossEncoder(MODEL_NAME)
    log.info("model_loaded", extra={"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)})
    return model


def score(model: Any, query: str, texts: list[str]) -> list[float]:
    """Un scor per text, in ordinea primita. Fara I/O, fara logare."""
    return list(model.predict([(query, text) for text in texts]))
