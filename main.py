from fastapi import FastAPI
from sentence_transformers import CrossEncoder
from models import RerankRequest, RerankResponse, RerankedChunk


app = FastAPI()

# rulează O DATĂ, la pornirea serverului — modelul rămâne în RAM
model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")

@app.get("/api/health")
def health():
    return {"status": "ok", "model_loaded": True}

@app.post("/api/rerank/chunks")
def rerank(request: RerankRequest) -> RerankResponse:
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

    return RerankResponse(reranked_chunks=reranked)