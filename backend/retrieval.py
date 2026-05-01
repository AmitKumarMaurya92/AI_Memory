"""
retrieval.py
------------
Handles:
  - Searching FAISS for the top-k chunks relevant to a query embedding.
  - Combining retrieved chunks into a single context string.
  - Fetching query history from SQLite for the /history endpoint.
"""

import os
import json
import sqlite3
import faiss
import numpy as np

# ──────────────────────────────────────────────
# Paths (mirror those in embedding.py)
# ──────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR   = os.path.join(BASE_DIR, "database", "faiss_index")
FAISS_FILE  = os.path.join(INDEX_DIR, "index.faiss")
CHUNKS_FILE = os.path.join(INDEX_DIR, "chunks.json")
DB_PATH     = os.path.join(BASE_DIR, "database", "metadata.db")


# ──────────────────────────────────────────────
# FAISS Search
# ──────────────────────────────────────────────

def search_similar_chunks(query_embedding: np.ndarray, top_k: int = 5) -> list[str]:
    """
    Search the FAISS index for the top-k most similar chunks.

    Args:
        query_embedding : numpy array of shape (1, dim).
        top_k           : Number of results to return.

    Returns:
        List of chunk text strings, ordered by relevance (closest first).
        Returns an empty list if no index exists yet.
    """
    if not os.path.exists(FAISS_FILE) or not os.path.exists(CHUNKS_FILE):
        return []   # Nothing indexed yet

    index = faiss.read_index(FAISS_FILE)

    if index.ntotal == 0:
        return []   # Index exists but is empty

    # Clamp top_k to the number of stored vectors
    k = min(top_k, index.ntotal)

    # FAISS returns distances (D) and indices (I) as numpy arrays
    _distances, indices = index.search(query_embedding, k)

    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        all_chunks: list[str] = json.load(f)

    results = []
    for idx in indices[0]:
        if idx != -1 and idx < len(all_chunks):   # -1 means "not found"
            results.append(all_chunks[idx])

    return results


# ──────────────────────────────────────────────
# Context Builder
# ──────────────────────────────────────────────

def build_context(chunks: list[str]) -> str:
    """
    Concatenate retrieved chunks into a numbered context block
    that can be sent to an LLM.
    """
    if not chunks:
        return "No relevant information found in your memory."

    sections = []
    for i, chunk in enumerate(chunks, start=1):
        sections.append(f"[Memory {i}]\n{chunk}")

    return "\n\n".join(sections)


# ──────────────────────────────────────────────
# Query History
# ──────────────────────────────────────────────

def get_query_history(limit: int = 20) -> list[dict]:
    """
    Fetch the most recent queries from the SQLite database.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of dicts: {id, query, answer, created_at}
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, query, answer, created_at
        FROM queries
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": r[0], "query": r[1], "answer": r[2], "created_at": r[3]}
        for r in rows
    ]
