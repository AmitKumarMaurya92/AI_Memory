"""
summarizer.py
-------------
Generates AI answers and summaries using:
  - Groq API (primary)   → set GROQ_API_KEY env variable
  - HuggingFace Inference API (fallback) → set HF_API_KEY env variable
  - Offline rule-based fallback → works with no API key at all

Priority: Groq → HuggingFace → Offline
"""

import os
import textwrap
import requests as http_requests

# ──────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HF_API_KEY   = os.getenv("HF_API_KEY", "")


# ──────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────

def generate_answer(context: str, query: str) -> dict:
    """
    Generate an AI answer + summary given retrieved context.

    Returns:
        {"answer": str, "summary": str}
    """
    if GROQ_API_KEY:
        return _answer_groq(context, query)
    elif HF_API_KEY:
        return _answer_huggingface(context, query)
    else:
        return _answer_offline(context, query)


# ──────────────────────────────────────────────
# Groq Backend (fast inference, free tier)
# ──────────────────────────────────────────────

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-8b-8192"   # fast & free on Groq


def _answer_groq(context: str, query: str) -> dict:
    """Call the Groq Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }

    system_prompt = (
        "You are a helpful AI Memory Companion. "
        "You help users recall information from their uploaded notes and documents. "
        "Answer based ONLY on the provided context. "
        "If the context doesn't contain enough information, say so honestly."
    )

    user_message = (
        f"Context from memory:\n\n{context}\n\n"
        f"User question: {query}\n\n"
        "Please provide a clear, concise answer based on the context above."
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens": 500,
        "temperature": 0.3,
    }

    response = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    answer  = data["choices"][0]["message"]["content"].strip()
    summary = _summarize_groq(context)
    return {"answer": answer, "summary": summary}


def _summarize_groq(context: str) -> str:
    """Generate a 2-3 sentence summary of the context using Groq."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Summarize the following in 2-3 sentences:\n\n{context}",
            }
        ],
        "max_tokens": 150,
        "temperature": 0.3,
    }

    response = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


# ──────────────────────────────────────────────
# HuggingFace Inference API Backend (fallback)
# ──────────────────────────────────────────────

HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
HF_URL   = f"https://api-inference.huggingface.co/models/{HF_MODEL}"


def _answer_huggingface(context: str, query: str) -> dict:
    """Call HuggingFace Inference API."""
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}

    prompt = (
        f"[INST] You are an AI Memory Companion. "
        f"Answer the user question using ONLY the context below.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query} [/INST]"
    )

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 400, "temperature": 0.3},
    }

    response = http_requests.post(HF_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    answer  = data[0]["generated_text"].split("[/INST]")[-1].strip()
    summary = _summarize_offline(context)
    return {"answer": answer, "summary": summary}


# ──────────────────────────────────────────────
# Offline Fallback (no API key needed)
# ──────────────────────────────────────────────

def _answer_offline(context: str, query: str) -> dict:
    """
    Simple fallback when no API key is set.
    Returns the most relevant retrieved chunk as the answer.
    """
    if context.strip() == "No relevant information found in your memory.":
        return {
            "answer":  "I couldn't find relevant information in your memory for that question.",
            "summary": "No memories retrieved.",
        }

    first_block = context.split("\n\n")[0]
    answer = (
        f"Based on your stored memories, here is the most relevant information:\n\n"
        f"{first_block}\n\n"
        f"(Tip: Set GROQ_API_KEY in your .env file for full AI-generated responses. "
        f"Get a free key at https://console.groq.com)"
    )

    return {"answer": answer, "summary": _summarize_offline(context)}


def _summarize_offline(context: str) -> str:
    """Return a truncated snippet of context as a basic summary."""
    raw = context.replace("\n", " ").strip()
    return textwrap.shorten(raw, width=300, placeholder="…")
