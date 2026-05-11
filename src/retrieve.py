import os
import sqlite3
import numpy as np
import faiss
from dotenv import load_dotenv
from .schema import Chunk
from .ingest import get_embeddings
from rank_bm25 import BM25Okapi


load_dotenv()
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "data/faiss.index")
METADATA_DB_PATH = os.getenv("METADATA_DB_PATH", "data/metadata.db")


def load_index() -> tuple[faiss.Index, sqlite3.Connection]:

    index = faiss.read_index(FAISS_INDEX_PATH)
    connector = sqlite3.connect(METADATA_DB_PATH)

    return (index, connector)


def get_chunk_by_id(cursor: sqlite3.Cursor, row_id: int) -> Chunk:

    cursor.execute(
        "SELECT text, source, incident_id, chunk_type FROM chunks WHERE id = ?",
        (row_id,),
    )
    chunk_data = cursor.fetchone()

    if chunk_data is None:
        raise ValueError(f"No chunk found in SQLite for row id {row_id}")

    chunk = Chunk(
        text=chunk_data[0],
        source=chunk_data[1],
        incident_id=chunk_data[2],
        chunk_type=chunk_data[3],
    )

    return chunk


def retrieve(
    query: str,
    index: faiss.Index,
    connection: sqlite3.Connection,
    top_k: int = 10,
    top_n: int = 8,
) -> list[Chunk]:

    embeddings = get_embeddings(query)
    chunks = []

    faiss_embeddings = np.asarray([embeddings], dtype=np.float32)
    faiss.normalize_L2(faiss_embeddings)

    scores, indices = index.search(faiss_embeddings, top_k)

    sqlite_pairs = [
        (int(idx), float(score))
        for idx, score in zip(indices[0], scores[0])
        if idx != -1
    ]

    cursor = connection.cursor()

    for row_id, score in sqlite_pairs:
        chunk = get_chunk_by_id(cursor, row_id)
        chunk.score = score
        chunks.append(chunk)

    cursor.close()

    top_results = sorted(chunks, key=lambda x: x.score, reverse=True)[:top_n]

    return top_results


def build_bm25_index(chunks: list[Chunk]) -> tuple[BM25Okapi, list[Chunk]]:

    tokenised_corpus = []
    for chunk in chunks:
        tokens = chunk.text.lower().split()
        tokenised_corpus.append(tokens)

    bm25 = BM25Okapi(tokenised_corpus)

    return bm25, chunks


def normalize(scores: list[float]) -> list[float]:

    normalized_scores = []
    min_score = min(scores)
    max_score = max(scores)

    if max_score - min_score == 0:
        return [0.0] * len(scores)

    for score in scores:
        normalized_score = (score - min_score) / (max_score - min_score)
        normalized_scores.append(normalized_score)

    return normalized_scores


def hybrid_retrieve(
    query: str,
    index: faiss.Index,
    connection: sqlite3.Connection,
    bm25: BM25Okapi,
    bm25_chunks: list[Chunk],
    alpha: float = 0.7,
    top_k: int = 10,
    top_n: int = 8,
) -> list[Chunk]:

    faiss_chunks = retrieve(
        query=query, index=index, connection=connection, top_k=top_k, top_n=top_n
    )
    tokenized_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)

    faiss_score_map = {chunk.source: chunk.score for chunk in faiss_chunks}
    bm25_score_map = {
        chunk.source: score for chunk, score in zip(bm25_chunks, bm25_scores)
    }

    normal_faiss_vals = normalize(list(faiss_score_map.values()))
    normalized_faiss = dict(zip(faiss_score_map.keys(), normal_faiss_vals))
    normal_bm25_vals = normalize(list(bm25_score_map.values()))
    normalized_bm25 = dict(zip(bm25_score_map.keys(), normal_bm25_vals))

    combined = {}
    for source in normalized_bm25:
        faiss_score = normalized_faiss.get(source, 0.0)
        bm25_score = normalized_bm25.get(source, 0.0)
        combined[source] = alpha * faiss_score + (1 - alpha) * bm25_score

    top_sources = [
        source
        for source, score in sorted(combined.items(), key=lambda x: x[1], reverse=True)[
            :top_n
        ]
    ]

    source_to_chunk = {chunk.source: chunk for chunk in bm25_chunks}
    top_chunks = [
        source_to_chunk[source] for source in top_sources if source in source_to_chunk
    ]

    return top_chunks


def load_all_chunks(connection: sqlite3.Connection) -> list[Chunk]:
    cursor = connection.cursor()
    cursor.execute("SELECT text, source, incident_id, chunk_type FROM chunks")
    rows = cursor.fetchall()
    cursor.close()
    return [
        Chunk(text=row[0], source=row[1], incident_id=row[2], chunk_type=row[3])
        for row in rows
    ]
