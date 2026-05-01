"""
embedding.py
------------
Manages:
  - Loading a Sentence-Transformer model.
  - Generating embeddings for text chunks.
  - Creating / loading / saving a FAISS index.
  - Storing chunk text alongside the index so we can retrieve raw text later.
"""

import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR  = os.path.join(BASE_DIR, "database", "faiss_index")

FAISS_FILE = os.path.join(INDEX_DIR, "index.faiss")
CHUNKS_FILE = os.path.join(INDEX_DIR, "chunks.json")  # parallel list of chunk texts

os.makedirs(INDEX_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# Model
# ──────────────────────────────────────────────

# 'all-MiniLM-L6-v2' is small (~90 MB), fast, and high-quality.
MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Return the (cached) embedding model."""
    global _model
    if _model is None:
        print(f"[Embedding] Loading model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


# ──────────────────────────────────────────────
# FAISS index helpers
# ──────────────────────────────────────────────

def _load_or_create_index(dim: int) -> tuple[faiss.IndexFlatL2, list[str]]:
    """
    Load existing FAISS index + chunk list from disk,
    or create a fresh one if none exists.
    """
    if os.path.exists(FAISS_FILE) and os.path.exists(CHUNKS_FILE):
        index = faiss.read_index(FAISS_FILE)
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        return index, chunks

    # Create a flat L2 index for exact nearest-neighbour search
    index = faiss.IndexFlatL2(dim)
    return index, []


def _save_index(index: faiss.IndexFlatL2, chunks: list[str]) -> None:
    """Persist FAISS index and chunk list to disk."""
    faiss.write_index(index, FAISS_FILE)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def embed_and_store(chunks: list[str]) -> None:
    """
    Convert a list of text chunks into embeddings and add them to the
    FAISS index. Both the index and the raw chunk texts are saved to disk.

    Args:
        chunks: List of text strings to embed and store.
    """
    model = get_model()
    embeddings = model.encode(chunks, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    dim = embeddings.shape[1]
    index, stored_chunks = _load_or_create_index(dim)

    index.add(embeddings)
    stored_chunks.extend(chunks)

    _save_index(index, stored_chunks)
    print(f"[Embedding] Stored {len(chunks)} chunks. Total in index: {index.ntotal}")


def embed_query(query: str) -> np.ndarray:
    """
    Convert a single query string into an embedding vector.

    Returns:
        numpy array of shape (1, dim) ready for FAISS search.
    """
    model = get_model()
    vec = model.encode([query], convert_to_numpy=True).astype("float32")
    return vec
