"""
main.py
-------
FastAPI entry point for the AI Memory Companion.

Endpoints:
  POST /upload   – Upload a .txt / .pdf / .docx file, extract text,
                   chunk it, embed it, and store metadata.
  POST /query    – Accept a natural-language question, retrieve
                   relevant chunks from FAISS, and return an AI answer.
  GET  /history  – Return a list of past queries and answers.
"""

import os
import sqlite3
import shutil
from datetime import datetime
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Local modules
from file_handler import extract_text, clean_text, chunk_text
from embedding   import embed_and_store, embed_query
from retrieval   import search_similar_chunks, build_context, get_query_history
from summarizer  import generate_answer

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR  = os.path.join(BASE_DIR, "uploads")
DB_PATH     = os.path.join(BASE_DIR, "database", "metadata.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ──────────────────────────────────────────────
# Database Initialisation
# ──────────────────────────────────────────────

def init_db() -> None:
    """Create SQLite tables on first run if they don't already exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Stores metadata for every uploaded file
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT    NOT NULL,
            upload_date TEXT    NOT NULL,
            num_chunks  INTEGER NOT NULL
        )
        """
    )

    # Stores every query and the AI-generated answer
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            query      TEXT NOT NULL,
            answer     TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


init_db()

# ──────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="AI Memory Companion API",
    description="RAG-based digital brain: upload files, ask questions, recall memories.",
    version="1.0.0",
)

# Allow the HTML/JS frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend at "/"
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main HTML page."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ──────────────────────────────────────────────
# Request / Response Schemas
# ──────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5   # number of chunks to retrieve


class UploadResponse(BaseModel):
    filename:   str
    num_chunks: int
    message:    str


class QueryResponse(BaseModel):
    query:   str
    answer:  str
    summary: str
    chunks_used: int


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a .txt / .pdf / .docx file.

    Pipeline:
      1. Save the file to /uploads
      2. Extract text from the file
      3. Clean and chunk the text
      4. Embed chunks and store in FAISS
      5. Save metadata to SQLite
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # ── 1. Save file ──────────────────────────
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ── 2. Extract text ───────────────────────
    try:
        raw_text = extract_text(file_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {exc}")

    # ── 3. Clean & chunk ──────────────────────
    cleaned   = clean_text(raw_text)
    chunks    = chunk_text(cleaned, chunk_size=500, overlap=50)

    if not chunks:
        raise HTTPException(status_code=400, detail="File appears to be empty or unreadable.")

    # ── 4. Embed & store in FAISS ─────────────
    embed_and_store(chunks)

    # ── 5. Store metadata in SQLite ───────────
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO files (filename, upload_date, num_chunks) VALUES (?, ?, ?)",
        (file.filename, datetime.utcnow().isoformat(), len(chunks)),
    )
    conn.commit()
    conn.close()

    return UploadResponse(
        filename=file.filename,
        num_chunks=len(chunks),
        message=f"Successfully processed '{file.filename}' into {len(chunks)} memory chunks.",
    )


@app.post("/query", response_model=QueryResponse)
async def query_memory(request: QueryRequest):
    """
    Answer a natural-language question from stored memories.

    Pipeline:
      1. Embed the query
      2. Search FAISS for top-k similar chunks
      3. Build context string
      4. Generate answer + summary via LLM
      5. Save query + answer to SQLite
    """
    # ── 1. Embed query ────────────────────────
    query_embedding = embed_query(request.query)

    # ── 2. Retrieve top chunks ────────────────
    chunks = search_similar_chunks(query_embedding, top_k=request.top_k)

    # ── 3. Build context ──────────────────────
    context = build_context(chunks)

    # ── 4. Generate answer ────────────────────
    result = generate_answer(context, request.query)

    # ── 5. Persist to SQLite ──────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO queries (query, answer, created_at) VALUES (?, ?, ?)",
        (request.query, result["answer"], datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    return QueryResponse(
        query=request.query,
        answer=result["answer"],
        summary=result["summary"],
        chunks_used=len(chunks),
    )


@app.get("/history")
async def query_history(limit: int = 20):
    """Return the most recent queries and answers (newest first)."""
    return {"history": get_query_history(limit=limit)}


@app.get("/files")
async def list_files():
    """Return a list of all uploaded files with their metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, upload_date, num_chunks FROM files ORDER BY upload_date DESC")
    rows = cursor.fetchall()
    conn.close()
    return {
        "files": [
            {"id": r[0], "filename": r[1], "upload_date": r[2], "num_chunks": r[3]}
            for r in rows
        ]
    }


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
