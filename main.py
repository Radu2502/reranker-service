import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sentence_transformers import CrossEncoder

from logging_setup import setup_logging
from models import RerankRequest, RerankResponse, RerankedChunk

setup_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()   # re-aplica: uvicorn si-a pus handlerele intre timp
    yield


app = FastAPI(lifespan=lifespan)

# rulează O DATĂ, la pornirea serverului — modelul rămâne în RAM
log.info("incarc modelul cross-encoder")
_t0 = time.perf_counter()
model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
log.info("model incarcat in %.1fs", time.perf_counter() - _t0)


@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": True}


@app.post("/api/rerank/chunks")
def rerank(request: RerankRequest) -> RerankResponse:
    log.info("rerank start: %d chunks, top_k=%d", len(request.chunks), request.top_k)
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
        "rerank done: %d returnate in %.0fms",
        len(reranked), (time.perf_counter() - _t) * 1000,
    )
    return RerankResponse(reranked_chunks=reranked)