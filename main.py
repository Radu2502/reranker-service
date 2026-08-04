import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sentence_transformers import CrossEncoder

from logging_setup import setup_logging
from middleware import request_context
from models import RerankRequest, RerankResponse, RerankedChunk

setup_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()   # re-aplica: uvicorn si-a pus handlerele intre timp
    yield


app = FastAPI(lifespan=lifespan)
app.middleware("http")(request_context)

# rulează O DATĂ, la pornirea serverului — modelul rămâne în RAM
log.info("model_loading")
_t0 = time.perf_counter()
model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
log.info("model_loaded", extra={"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)})


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": True}


@app.post("/api/rerank/chunks")
def rerank(request: RerankRequest) -> RerankResponse:
    log.info("rerank_start", extra={"n_chunks": len(request.chunks), "top_k": request.top_k})
    _t = time.perf_counter()

    pairs = [(request.query, d.text) for d in request.chunks]
    scores = model.predict(pairs)

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