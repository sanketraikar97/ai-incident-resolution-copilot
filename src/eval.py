import json
from functools import lru_cache
from .retrieve import retrieve, load_index
from .rerank import rerank
from .schema import Chunk
from src import ingest
from .ingest import get_embeddings


cached_get_embeddings = lru_cache(maxsize=256)(get_embeddings)


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


def evaluate(k: int = 5) -> None:

    index, connection = load_index()

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

        base_chunks = retrieve(query, index, connection)

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


if __name__ == "__main__":
    evaluate(k=5)
