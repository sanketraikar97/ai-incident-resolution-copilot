import json
from .retrieve import (
    load_index,
    build_bm25_index,
    load_all_chunks,
    hybrid_retrieve,
)
from .llm import call_llm
from .schema import IncidentResolution, Chunk
from .rerank import rerank
from typing import Optional
import os
import time

# --- Constants ---
# read both thresholds from env with safe float conversion
""" why string defaults in os.getenv: to ovid runtime errors and leading to code failure because of incorrect values """
HYBRID_THRESHOLD = float(os.getenv("HYBRID_THRESHOLD", "0.3"))
RERANK_THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.0"))
ISSUE_SUM = "Insufficient context to diagnose this incident reliably"
CONF_REASON = "Retrieval scores below minimum threshold — no sufficiently relevant incidents or runbooks found for this query"


# --- Retrieval Quality Check ---
def check_retrieval_quality(
    chunks: list[Chunk], use_reranker: bool
) -> Optional[IncidentResolution]:

    # step 1: get the top chunk — chunks are already sorted by score
    # what happens if chunks is empty — guard against it
    """why check only the top chunk and not average all scores: Because the top chunk is the best chunk the indexing had found so all other would have worse similarity and it is the best possible benchmark"""
    if not chunks:
        return IncidentResolution(
            issue_summary="No context available — index may be empty or not built",
            likely_causes=[],
            recommended_actions=[],
            similar_incidents=[],
            confidence="low",
            confidence_reason="Retrieval returned zero chunks — verify the FAISS index has been built",
            sources=[],
        )
    top_chunk = chunks[0]

    # step 2: determine which score to check based on use_reranker
    # if use_reranker: check rerank_score
    # if not use_reranker: check score
    # what if the relevant score field is None — guard against it: if chunk.score else 0.0
    if not use_reranker:
        score = top_chunk.score if top_chunk.score else 0.0
    else:
        score = top_chunk.rerank_score if top_chunk.rerank_score else 0.0

    # step 3: compare score against appropriate threshold
    # if above threshold: return None — retrieval is good enough
    """ why return None and not True/False: Because run_pipeline returns an incidentresolution object and not boolean so need to stay inline with it """
    threshold = RERANK_THRESHOLD if use_reranker else HYBRID_THRESHOLD

    if score >= threshold:
        return None
    else:
        # step 4: score is below threshold — build and return fallback IncidentResolution
        return IncidentResolution(
            issue_summary=ISSUE_SUM,
            likely_causes=[],
            recommended_actions=[],
            similar_incidents=[],
            confidence="low",
            confidence_reason=f"{CONF_REASON}. Top Chunk score: {score:.3f}, threshold: {threshold:.3f}",
            sources=[],
        )


def run_pipeline(
    query: str, use_reranker: bool = True
) -> tuple[IncidentResolution, str, dict, list[Chunk]]:

    latency = {}
    rerank_ms = None
    llm_ms = None
    index, connector = load_index()

    all_chunks = load_all_chunks(connector)

    bm25, bm25_chunks = build_bm25_index(all_chunks)

    # Retrieve larger candidate set when reranker is active downstream
    # chunks = retrieve(query, index, connection=connector, top_k=10, top_n=8)
    start = time.perf_counter()
    chunks = hybrid_retrieve(query, index, connector, bm25, bm25_chunks)
    retrieval_ms = (time.perf_counter() - start) * 1000
    connector.close()
    print(f"No of chunks retrieved: {len(chunks)}")

    if use_reranker:
        rerank_start = time.perf_counter()
        chunks = rerank(query, chunks)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

    # step 5: check retrieval quality
    # if fallback is not None: return early with tuple
    """ why return LLM_MODEL even on fallback path: To tell the user which model would have been used """
    fallback = check_retrieval_quality(chunks, use_reranker)
    if fallback is not None:
        latency["retrieval_ms"] = retrieval_ms
        latency["rerank_ms"] = rerank_ms
        latency["llm_ms"] = llm_ms
        return fallback, os.getenv("LLM_MODEL", "gpt-4o"), latency, chunks

    llm_start = time.perf_counter()
    response, model_name = call_llm(query, chunks)
    llm_ms = (time.perf_counter() - llm_start) * 1000

    latency["retrieval_ms"] = retrieval_ms
    latency["rerank_ms"] = rerank_ms if use_reranker else None
    latency["llm_ms"] = llm_ms

    return response, model_name, latency, chunks


if __name__ == "__main__":

    result, model_name, _, _ = run_pipeline(
        query="Payment API timing out intermittently"
    )
    print(json.dumps(result.model_dump(), indent=2))
