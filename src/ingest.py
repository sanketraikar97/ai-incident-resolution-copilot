from openai import OpenAI
from .schema import Chunk
import json
import glob
import os
import sqlite3
import numpy as np
import faiss
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "data/faiss.index")
METADATA_DB_PATH = os.getenv("METADATA_DB_PATH", "data/metadata.db")
_embed_model = None


def load_inc_json(filepath: str) -> dict:

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def load_runbook_md(filepath: str) -> str:

    with open(filepath, "r", encoding="utf-8") as f:
        data = f.read()

    return data


def get_embeddings(text: str) -> list[float]:

    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")

    try:
        # embeddings = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        # return list(embeddings.data[0].embedding)
        return _embed_model.encode(text).tolist()
    except Exception as e:
        print(f"Embedding has Failed: {e}")
        raise


def load_incidents(path: str = "data/incidents") -> list[Chunk]:

    inc_chunks = []

    for filepath in glob.glob(f"{path}/*.json"):

        data = load_inc_json(filepath)

        title = data.get("title")
        description = data.get("description")
        symptoms = "\n".join(data.get("symptoms"))
        root_cause = data.get("root_cause")

        resolution = data.get("resolution")
        tags = data.get("tags")

        chunk_text = (
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Symptoms: {symptoms}\n"
            f"Root Cause: {root_cause}\n"
            f"Resolution: {resolution}\n"
            f"Tags: {','.join(tags)}"
        )

        chunk = Chunk(
            text=chunk_text,
            source=os.path.basename(filepath),
            incident_id=data.get("incident_id"),
            chunk_type="incident",
        )

        inc_chunks.append(chunk)
    return inc_chunks


def load_runbooks(path: str = "data/runbooks") -> list[Chunk]:

    runbook_chunks = []

    for filepath in glob.glob(f"{path}/*.md"):

        data = load_runbook_md(filepath)

        # sections = data.split("##")
        sections = ["##" + s for s in data.split("##") if s.strip()]

        for section in sections:

            if len(section) < 30:
                continue

            chunk = Chunk(
                text=section, source=os.path.basename(filepath), chunk_type="runbook"
            )
            runbook_chunks.append(chunk)

    return runbook_chunks


def build_index(chunks: list[Chunk]) -> None:

    vectors = []
    for i, chunk in enumerate(chunks):
        if i % 10 == 0:
            print(f"  Embedding {i}/{len(chunks)}...")
        embeddings = get_embeddings(chunk.text)
        vectors.append(embeddings)

    faiss_embeddings = np.asarray(vectors, dtype=np.float32)
    faiss.normalize_L2(faiss_embeddings)

    dimension = faiss_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(faiss_embeddings)
    faiss.write_index(index, FAISS_INDEX_PATH)

    connector = sqlite3.connect(METADATA_DB_PATH)
    cursor = connector.cursor()

    cursor.execute(
        """ CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY,
                   text TEXT,
                   source TEXT,
                   incident_id TEXT,
                   chunk_type TEXT) """
    )

    cursor.execute("DELETE FROM chunks")
    for i, chunk in enumerate(chunks):
        cursor.execute(
            "INSERT INTO chunks (id, text, source, incident_id, chunk_type) VALUES (?, ?, ?, ?, ?)",
            (i, chunk.text, chunk.source, chunk.incident_id, chunk.chunk_type),
        )

    connector.commit()
    connector.close()


if __name__ == "__main__":
    incident_chunks = load_incidents()
    runbook_chunks = load_runbooks()
    all_chunks = incident_chunks + runbook_chunks
    print(
        f"Loaded {len(incident_chunks)} incident chunks, {len(runbook_chunks)} runbook chunks"
    )
    build_index(all_chunks)
