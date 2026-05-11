from sentence_transformers import CrossEncoder
from .schema import Chunk

_cross_encoder = None

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_model() -> CrossEncoder:

    global _cross_encoder

    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(RERANKER_MODEL)

    return _cross_encoder


def rerank(query: str, chunks: list[Chunk], top_n: int = 5) -> list[Chunk]:

    model = _get_model()

    rerank_pairs = []
    for chunk in chunks:
        rerank_pairs.append([query, chunk.text])

    scores = model.predict(rerank_pairs)  # , max_length=512)

    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = score

    top_results = sorted(
        chunks,
        key=lambda x: (x.rerank_score is None, x.rerank_score or 0.0),
        reverse=True,
    )[:top_n]

    return top_results
