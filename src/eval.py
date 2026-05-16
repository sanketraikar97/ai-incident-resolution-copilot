import json
from functools import lru_cache
from .retrieve import (
    retrieve,
    load_index,
    hybrid_retrieve,
    load_all_chunks,
    build_bm25_index,
)
from .rerank import rerank
from .schema import Chunk, IncidentResolution, FaithfulnessResult
from src import ingest
from .ingest import get_embeddings

# Faithfulness Evaluation
import os
import hashlib
from typing import Optional
from pydantic import ValidationError
from .faithful_eval import evaluate_faithfulness
from .llm import call_llm

cached_get_embeddings = lru_cache(maxsize=256)(get_embeddings)

FAITHFULNESS_CACHE_DIR = os.getenv("FAITHFULNESS_DIR", "data/faithfulness_cache")


def _get_cache_path(query: str) -> str:

    file_name = f"{hashlib.sha256(query.encode('utf-8')).hexdigest()}.json"

    return os.path.join(FAITHFULNESS_CACHE_DIR, file_name)


def _load_cached_resolution(query: str) -> Optional[IncidentResolution]:

    file_path = _get_cache_path(query)

    if os.path.isfile(file_path):

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()

            return IncidentResolution.model_validate_json(data)

        except json.JSONDecodeError as je:
            print(f"Error: Cache returned invalid JSON syntax. {je}")
            return None

        except ValidationError as ve:
            print(
                f"Cache data parsed but does not match Incident Resolution Schema. {ve.json()}"
            )
            return None

    return None


def _save_resolution(query: str, resolution: IncidentResolution) -> None:

    os.makedirs(FAITHFULNESS_CACHE_DIR, exist_ok=True)
    file_path = _get_cache_path(query)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(resolution.model_dump_json())


def load_eval_queries(path: str = "data/eval_queries.json") -> list[dict]:

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def recall_at_k(chunks: list[Chunk], expected_source: str, k: int) -> float:

    for chunk in chunks[:k]:
        if chunk.source == expected_source:
            return 1.0
    return 0.0


def reciprocal_rank(chunks: list[Chunk], expected_source: str) -> float:

    for i in range(len(chunks)):
        chunk = chunks[i]
        if chunk.source == expected_source:
            return 1 / (i + 1)
    return 0.0


def evaluate(k: int = 5) -> list[FaithfulnessResult]:

    faithfulness_results = []
    index, connection = load_index()

    all_chunks = load_all_chunks(connection)
    bm25, bm25_chunks = build_bm25_index(all_chunks)

    eval_queries = load_eval_queries()

    rr_scores_base, rr_scores_reranked, recall_scores, recall_scores_reranked = (
        [],
        [],
        [],
        [],
    )
    ingest.get_embeddings = cached_get_embeddings

    for item in eval_queries:

        query = item["query"]
        expected_source = item["expected_source"]

        # base_chunks = retrieve(query, index, connection)
        base_chunks = hybrid_retrieve(query, index, connection, bm25, bm25_chunks)

        # step 2: check disk cache for existing resolution
        resolution = _load_cached_resolution(query)

        # step 3: if no cached resolution, call LLM and save
        if not resolution:
            resolution, _ = call_llm(query, base_chunks)
            _save_resolution(query, resolution)

        # step 4: run faithfulness check
        faith_eval_result = evaluate_faithfulness(
            query=query, resolution=resolution, chunks=base_chunks
        )
        faithfulness_results.append(faith_eval_result)

        reranked_chunks = rerank(query, base_chunks)

        rerank_rr = reciprocal_rank(reranked_chunks, expected_source)
        if rerank_rr == 0.0:
            print(f"Failed Query:{query}")
            print(
                f" Base Chunks: {[(chunk.source, chunk.score) for chunk in base_chunks]}"
            )

        recall_scores.append(recall_at_k(base_chunks, expected_source, k))
        recall_scores_reranked.append(recall_at_k(reranked_chunks, expected_source, k))
        rr_scores_base.append(reciprocal_rank(base_chunks, expected_source))
        rr_scores_reranked.append(rerank_rr)

    connection.close()

    print(f"Recall@{k} baseline score: {sum(recall_scores)/len(recall_scores)}")
    print("\n")
    print(
        f"Recall@{k} reranked score: {sum(recall_scores_reranked)/len(recall_scores_reranked)}"
    )
    print("\n")
    print(f"MRR baseline score: {sum(rr_scores_base)/len(rr_scores_base)}")
    print("\n")
    print(f"MRR reranked score: {sum(rr_scores_reranked)/len(rr_scores_reranked)}")

    return faithfulness_results


def print_faithfulness_report(results: list[FaithfulnessResult]) -> None:

    evaluated = [result for result in results if result.was_evaluated]
    failed = [
        result
        for result in results
        if result.fabricated_incidents or result.fabricated_sources
    ]

    print(
        f"No of evaluations: {len(evaluated)} \n No of sucessful evaluations: {len(evaluated)-len(failed)} \n No of failed evaluations: {len(failed)}"
    )

    for eval in failed:
        print(f"Query:{eval.query} \n")
        print(f"Fabricated Sources:{eval.fabricated_sources} \n")
        print(f"Fabricated Incidents:{eval.fabricated_incidents} \n")


if __name__ == "__main__":
    # evaluate(k=5)
    print_faithfulness_report(evaluate(k=5))
