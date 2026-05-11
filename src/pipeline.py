import json
from .retrieve import (
    load_index,
    build_bm25_index,
    load_all_chunks,
    hybrid_retrieve,
)
from .llm import call_llm
from .schema import IncidentResolution
from .rerank import rerank


def run_pipeline(
    query: str, use_reranker: bool = True
) -> tuple[IncidentResolution, str]:

    index, connector = load_index()

    all_chunks = load_all_chunks(connector)

    bm25, bm25_chunks = build_bm25_index(all_chunks)

    # Retrieve larger candidate set when reranker is active downstream
    # chunks = retrieve(query, index, connection=connector, top_k=10, top_n=8)
    chunks = hybrid_retrieve(query, index, connector, bm25, bm25_chunks)
    connector.close()
    print(f"No of chunks retrieved: {len(chunks)}")

    if use_reranker:
        chunks = rerank(query, chunks)

    response, model_name = call_llm(query, chunks)

    return response, model_name


if __name__ == "__main__":

    result, model_name = run_pipeline(query="Payment API timing out intermittently")
    print(json.dumps(result.model_dump(), indent=2))
