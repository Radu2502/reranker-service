import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.logging.middleware import request_context
from app.logging.setup import setup_logging
from app.model import encoder
from app.models import RerankRequest, RerankResponse, RerankedChunk

setup_logging()
log = logging.getLogger(__name__)

# Fara default: daca lipsesc din mediu, procesul cade la import, nu la primul
# request cu o parola goala care ar fi trecut drept valida.
API_USER = os.environ["API_USER"]
API_PASSWORD = os.environ["API_PASSWORD"]

security = HTTPBasic()


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Valideaza Basic Auth in timp constant; intoarce userul autentificat."""
    # `&`, nu `and`: fara short-circuit, ambele comparatii se executa mereu, deci
    # durata raspunsului nu spune atacatorului daca userul era corect.
    user_ok = secrets.compare_digest(credentials.username.encode(), API_USER.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), API_PASSWORD.encode())
    if not (user_ok & pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credentiale invalide",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()   # re-aplica: uvicorn si-a pus handlerele intre timp
    # rulează O DATĂ, la pornirea serverului — modelul rămâne în RAM
    app.state.model = encoder.load_model()
    yield


app = FastAPI(lifespan=lifespan)
app.middleware("http")(request_context)


@app.get("/api/health")
def health(http_request: Request):
    # public, fara auth: orchestratorul trebuie sa poata verifica serviciul
    # starea reala, nu o constanta: fara lifespan rulat, app.state.model nu exista
    loaded = getattr(http_request.app.state, "model", None) is not None
    return {"status": "ok", "model_loaded": loaded}


@app.post("/api/rerank/chunks", dependencies=[Depends(require_basic_auth)])
def rerank(http_request: Request, request: RerankRequest) -> RerankResponse:
    log.info("rerank_start", extra={"n_chunks": len(request.chunks), "top_k": request.top_k})
    _t = time.perf_counter()

    model = http_request.app.state.model
    scores = encoder.score(model, request.query, [d.text for d in request.chunks])

    scored = [
        (i + 1, chunk, score)
        for i, (chunk, score) in enumerate(zip(request.chunks, scores))
    ]

    ranked = sorted(scored, key=lambda pair: pair[2], reverse=True)
    top = ranked[:request.top_k]

    reranked = [
        RerankedChunk(
            text=chunk.text,
            rerank_score=float(score),
            chunk_id=chunk.chunk_id,
            original_rank=rank,
        )
        for rank, chunk, score in top
    ]

    log.info(
        "rerank_done",
        extra={
            "n_returned": len(reranked),
            "duration_ms": round((time.perf_counter() - _t) * 1000, 1),
        },
    )
    return RerankResponse(reranked_chunks=reranked)
