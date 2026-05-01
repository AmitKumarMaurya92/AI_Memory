"""
file_handler.py
---------------
Handles file uploads and text extraction from:
  - .txt files
  - .pdf files (via PyMuPDF)
  - .docx files (via python-docx)

Also provides text cleaning and chunking utilities.
"""

import os
import re
import fitz          # PyMuPDF – for PDF parsing
import docx          # python-docx – for Word documents
from pathlib import Path


# ──────────────────────────────────────────────
# Text Extraction
# ──────────────────────────────────────────────

def extract_text(file_path: str) -> str:
    """
    Dispatch text extraction based on file extension.
    Returns the raw text content of the file.
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_txt(file_path: str) -> str:
    """Read a plain-text file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_pdf(file_path: str) -> str:
    """Extract text from every page of a PDF using PyMuPDF."""
    doc = fitz.open(file_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def _extract_docx(file_path: str) -> str:
    """Extract text from all paragraphs in a Word document."""
    document = docx.Document(file_path)
    paragraphs = [para.text for para in document.paragraphs]
    return "\n".join(paragraphs)


# ──────────────────────────────────────────────
# Text Cleaning
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Basic text cleaning:
      - Collapse multiple whitespace / newlines into a single space.
      - Strip leading/trailing whitespace.
    """
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ──────────────────────────────────────────────
# Text Chunking
# ──────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    Args:
        text       : The cleaned input text.
        chunk_size : Number of words per chunk (default 500).
        overlap    : Number of words shared between consecutive chunks (default 50).

    Returns:
        A list of text chunks.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap   # slide window with overlap

    return chunks
