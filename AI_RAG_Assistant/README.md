# AI RAG Assistant

Retrieval-Augmented Generation over your own PDFs. Flask backend, React frontend.

- **Hybrid retrieval**: ChromaDB semantic search + BM25 keyword search, fused (RRF) and reranked with a cross-encoder
- **Modes**: Factual (top 3), Detailed (top 7), Reason (question decomposition → sub-answers → synthesis)
- **Sessions**: isolated files, vector store and persistent history per chat; auto-titled
- **Streaming**: Server-Sent Events (status, sources, reasoning, content); Stop button
- **Citations**: page-level sources with snippets
- **LLMs**: local LM Studio (default), Groq API (when `GROQ_API_KEY` is set), or Ollama

## Setup
Requires Python 3.10+, Node 18+, and an LLM: LM Studio (local server on), a Groq key, or Ollama.

```bash
# backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # defaults to LM Studio at localhost:1234
python app.py                 # http://localhost:5000

# frontend (new terminal)
cd frontend
npm install
npm start                     # http://localhost:3000
```
The first upload/query downloads the embedding and reranker models from Hugging Face.

## Configuration
Environment variables (`backend/.env`): `GROQ_API_KEY`, `LLM_PROVIDER` (`lmstudio|groq|ollama|auto`),
`LMSTUDIO_URL`, `LMSTUDIO_MODEL`, `OLLAMA_MODEL`, `GROQ_MAIN_MODEL` (default `openai/gpt-oss-120b`), `GROQ_FAST_MODEL`.
Chunking and retrieval parameters live in `backend/config.py`. The frontend reads `VITE_API_URL`
(default `http://localhost:5000`).

## API
| Method | Path | Purpose |
|---|---|---|
| POST/GET | `/sessions` | create / list |
| GET/DELETE | `/sessions/{id}` | history + files / delete |
| POST | `/sessions/{id}/upload` | multipart `files` (PDF) |
| GET | `/sessions/{id}/files` | list files |
| POST | `/sessions/{id}/query-stream` | `{question, mode: factual\|detailed\|reason}` → SSE |
| POST | `/sessions/{id}/summarize` | `{filename}` |
