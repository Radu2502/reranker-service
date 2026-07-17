from pydantic import BaseModel

class Chunk(BaseModel):
    text: str
    score: float
    chunk_id: str

class RerankRequest(BaseModel):
    query: str
    chunks: list[Chunk]
    top_k: int

class RerankedChunk(BaseModel):
    text: str
    rerank_score: float
    chunk_id: str
    original_rank: int

class RerankResponse(BaseModel):
    reranked_chunks: list[RerankedChunk]