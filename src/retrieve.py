import os
import sqlite3
import numpy as np
import faiss
from dotenv import load_dotenv
from schema import Chunk
from ingest import get_embeddings


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
    top_k: int = 8,
    top_n: int = 5,
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
