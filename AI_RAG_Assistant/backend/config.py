"""Prompt templates and configuration for the RAG assistant."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SESSIONS_DIR = BASE_DIR / "sessions"
CHROMA_DIR = BASE_DIR / "chroma_sessions"

# --- Providers -------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_URL = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
# Leave empty to use whichever model LM Studio has loaded
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "")
# "gemini", "groq", "lmstudio", "ollama" or "auto" (first of Gemini key, Groq key, else LM Studio)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").lower()

# --- Models ----------------------------------------------------------------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L12-v2"
GROQ_MAIN_MODEL = os.getenv("GROQ_MAIN_MODEL", "openai/gpt-oss-120b")
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")

# --- Chunking / retrieval --------------------------------------------------
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
K_SEMANTIC = 15
K_BM25 = 15
FINAL_K = 10  # candidates passed to the reranker

MAX_UPLOAD_MB = 50
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))

# --- Modes -----------------------------------------------------------------
MODES = {
    "factual": {"temperature": 0.2, "top_k": 3, "model": GROQ_MAIN_MODEL},
    "detailed": {"temperature": 0.2, "top_k": 7, "model": GROQ_MAIN_MODEL},
    "reason": {"temperature": 0.2, "top_k": 5, "model": GROQ_MAIN_MODEL},
}

# --- Prompts ---------------------------------------------------------------
SYSTEM_BASE = (
    "You are an AI research assistant. Answer using ONLY the provided context "
    "excerpts from the user's documents. Cite sources inline as [n] using the "
    "excerpt numbers. If the context does not contain the answer, say so plainly "
    "instead of guessing. Use Markdown; use LaTeX ($...$) for math."
)

FACTUAL_PROMPT = SYSTEM_BASE + " Be concise and precise: give the direct answer in a few sentences."
DETAILED_PROMPT = SYSTEM_BASE + (
    " Give a comprehensive, well-structured explanation with headings and bullet "
    "points where useful, covering nuances and supporting evidence."
)

DECOMPOSE_PROMPT = (
    "Break the user's question into 2-4 simpler, self-contained sub-questions that "
    "together answer it. Reply with ONLY a JSON array of strings."
)
SUBANSWER_PROMPT = SYSTEM_BASE + " Answer the sub-question briefly (2-5 sentences)."
SYNTHESIS_PROMPT = (
    "You are an AI research assistant. Combine the sub-question answers below into "
    "one coherent, well-structured final answer to the original question. Keep "
    "inline [n] citations. Use Markdown."
)

SUMMARY_PROMPT = (
    "Summarize the following document text in Markdown with sections: Overview, "
    "Key Points, Methods/Approach (if applicable), Conclusions."
)
SUMMARY_COMBINE_PROMPT = (
    "Combine these partial summaries of one document into a single cohesive Markdown "
    "summary with sections: Overview, Key Points, Methods/Approach (if applicable), "
    "Conclusions."
)

for _d in (SESSIONS_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)
