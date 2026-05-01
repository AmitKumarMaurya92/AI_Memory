# 🧠 AI Memory Companion — Digital Brain

A **Retrieval-Augmented Generation (RAG)** system that stores your notes, PDFs, and documents as vector embeddings, then lets you query them in natural language.

---

## 📁 Project Structure

```
AI_Memory/
├── backend/
│   ├── main.py          ← FastAPI app, all endpoints
│   ├── embedding.py     ← Sentence-Transformer + FAISS management
│   ├── retrieval.py     ← FAISS search + context builder
│   ├── summarizer.py    ← OpenAI / HuggingFace / offline AI answers
│   └── file_handler.py  ← Text extraction + chunking
├── database/
│   ├── metadata.db      ← SQLite (auto-created)
│   └── faiss_index/     ← FAISS index files (auto-created)
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── uploads/             ← Saved upload files
└── requirements.txt
```

---

## ⚡ Quick Start

### 1. Create a Virtual Environment

```bash
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac / Linux)
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note**: The first run will download the `all-MiniLM-L6-v2` model (~90 MB). This happens automatically.

### 3. (Optional) Set API Keys

For richer AI responses, set one of these environment variables:

```bash
# Option A: OpenAI (best quality)
set OPENAI_API_KEY=sk-...

# Option B: HuggingFace Inference API (free tier)
set HF_API_KEY=hf_...
```

> Without a key, the app still works using an offline fallback that returns the most relevant retrieved chunk.

### 4. Run the Server

```bash
cd backend
python main.py
```

Or with uvicorn directly:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the App

Visit **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload a `.txt`, `.pdf`, or `.docx` file |
| `POST` | `/query`  | Ask a natural-language question |
| `GET`  | `/history` | Get recent queries & answers |
| `GET`  | `/files`   | List all uploaded files |

### POST `/upload`
```
Content-Type: multipart/form-data
Body: file=<your-file>
```

### POST `/query`
```json
{
  "query": "What did I study last week?",
  "top_k": 5
}
```

### Response
```json
{
  "query": "What did I study last week?",
  "answer": "Based on your memories, you studied...",
  "summary": "Brief summary of retrieved content...",
  "chunks_used": 3
}
```

---

## 🧠 How It Works

```
┌──────────┐    ┌────────────┐    ┌──────────────┐    ┌─────────┐
│  Upload  │───▶│ Extract    │───▶│   Chunk      │───▶│  Embed  │
│  File    │    │  Text      │    │   Text       │    │  & FAISS│
└──────────┘    └────────────┘    └──────────────┘    └─────────┘

┌──────────┐    ┌────────────┐    ┌──────────────┐    ┌─────────┐
│  Query   │───▶│ Embed      │───▶│ Search FAISS │───▶│Build    │
│  Input   │    │  Query     │    │ (top-k)      │    │Context  │
└──────────┘    └────────────┘    └──────────────┘    └────┬────┘
                                                            │
                                                     ┌──────▼──────┐
                                                     │ LLM Answer  │
                                                     │ + Summary   │
                                                     └─────────────┘
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in the venv |
| Server not starting | Make sure you're `cd backend` before running `python main.py` |
| Slow first query | Normal — the embedding model loads once on startup |
| Empty answers | Upload a file first before querying |
| Port already in use | Change the port: `uvicorn main:app --port 8001` |

---

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `sentence-transformers` | Text → vector embeddings |
| `faiss-cpu` | Vector similarity search |
| `PyMuPDF` | PDF text extraction |
| `python-docx` | Word document parsing |
| `openai` | LLM responses (optional) |
| `sqlite3` | Metadata storage (built-in) |
