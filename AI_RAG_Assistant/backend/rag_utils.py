"""Core RAG functionality: ingestion, hybrid retrieval, reranking and generation."""
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

import chromadb
import pymupdf as fitz  # PyMuPDF
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config
from bm25 import BM25Index
from get_embedding_function import get_embedding_function, get_reranker

_chroma_clients = {}
_bm25_cache = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Sessions (metadata + history on disk, vectors in per-session ChromaDB)
# ---------------------------------------------------------------------------
def session_dir(session_id):
    # session ids are server-generated UUIDs; reject anything else (path traversal)
    uuid.UUID(session_id)
    return config.SESSIONS_DIR / session_id


def session_exists(session_id):
    try:
        return (session_dir(session_id) / "meta.json").exists()
    except ValueError:
        return False


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def create_session(title=None):
    sid = str(uuid.uuid4())
    d = config.SESSIONS_DIR / sid
    (d / "files").mkdir(parents=True)
    meta = {"id": sid, "title": title or "New Chat", "auto_title": not title,
            "created_at": time.time(), "updated_at": time.time()}
    _write_json(d / "meta.json", meta)
    _write_json(d / "history.json", [])
    return meta


def list_sessions():
    out = []
    for d in config.SESSIONS_DIR.iterdir():
        meta = _read_json(d / "meta.json", None)
        if meta:
            out.append(meta)
    return sorted(out, key=lambda m: m["updated_at"], reverse=True)


def get_meta(session_id):
    return _read_json(session_dir(session_id) / "meta.json", None)


def get_history(session_id):
    return _read_json(session_dir(session_id) / "history.json", [])


def append_history(session_id, *messages):
    d = session_dir(session_id)
    history = _read_json(d / "history.json", [])
    history.extend(messages)
    _write_json(d / "history.json", history)
    meta = _read_json(d / "meta.json", {})
    meta["updated_at"] = time.time()
    first_user = next((m for m in history if m["role"] == "user"), None)
    if meta.get("auto_title") and first_user:
        text = first_user["content"].strip().replace("\n", " ")
        meta["title"] = text[:50] + ("…" if len(text) > 50 else "")
        meta["auto_title"] = False
    _write_json(d / "meta.json", meta)


def delete_session(session_id):
    d = session_dir(session_id)
    with _cache_lock:
        _chroma_clients.pop(session_id, None)
        _bm25_cache.pop(session_id, None)
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(config.CHROMA_DIR / session_id, ignore_errors=True)


def list_files(session_id):
    files = (session_dir(session_id) / "files")
    return sorted(p.name for p in files.glob("*.pdf")) if files.exists() else []


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def _collection(session_id):
    with _cache_lock:
        client = _chroma_clients.get(session_id)
        if client is None:
            client = chromadb.PersistentClient(
                path=str(config.CHROMA_DIR / session_id),
                settings=chromadb.Settings(anonymized_telemetry=False))
            _chroma_clients[session_id] = client
    return client.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})


def process_pdf(session_id, pdf_path):
    """Parse a PDF into overlapping chunks (with page metadata) and index them."""
    pdf_path = Path(pdf_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    ids, texts, metas = [], [], []
    with fitz.open(pdf_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            for i, chunk in enumerate(splitter.split_text(page.get_text())):
                if not chunk.strip():
                    continue
                ids.append(f"{pdf_path.name}:{page_no}:{i}")
                texts.append(chunk)
                metas.append({"source": pdf_path.name, "page": page_no})
    if not texts:
        raise ValueError("No extractable text found (scanned PDFs are not supported).")
    col = _collection(session_id)
    col.delete(where={"source": pdf_path.name})  # re-upload replaces old chunks
    embed = get_embedding_function()
    for s in range(0, len(texts), 64):  # batch to bound memory
        col.upsert(ids=ids[s:s + 64], documents=texts[s:s + 64],
                   metadatas=metas[s:s + 64], embeddings=embed(texts[s:s + 64]))
    with _cache_lock:
        _bm25_cache.pop(session_id, None)
    return len(texts)


def _all_chunks(session_id):
    data = _collection(session_id).get(include=["documents", "metadatas"])
    return data["ids"], data["documents"], data["metadatas"]


def _bm25(session_id):
    with _cache_lock:
        idx = _bm25_cache.get(session_id)
    if idx is None:
        ids, docs, _ = _all_chunks(session_id)
        idx = BM25Index(ids, docs)
        with _cache_lock:
            _bm25_cache[session_id] = idx
    return idx


# ---------------------------------------------------------------------------
# Retrieval: semantic + BM25 -> reciprocal rank fusion -> cross-encoder rerank
# ---------------------------------------------------------------------------
def retrieve(session_id, query, top_k):
    col = _collection(session_id)
    n = col.count()
    if n == 0:
        return []
    sem = col.query(query_embeddings=get_embedding_function()([query]),
                    n_results=min(config.K_SEMANTIC, n),
                    include=["documents", "metadatas"])
    cands = {cid: (doc, meta) for cid, doc, meta in
             zip(sem["ids"][0], sem["documents"][0], sem["metadatas"][0])}
    sem_rank = {cid: r for r, cid in enumerate(sem["ids"][0])}

    kw = _bm25(session_id).search(query, config.K_BM25)
    kw_rank = {cid: r for r, (cid, _) in enumerate(kw)}
    missing = [cid for cid in kw_rank if cid not in cands]
    if missing:
        got = col.get(ids=missing, include=["documents", "metadatas"])
        for cid, doc, meta in zip(got["ids"], got["documents"], got["metadatas"]):
            cands[cid] = (doc, meta)

    fused = {cid: sum(1.0 / (60 + r[cid]) for r in (sem_rank, kw_rank) if cid in r)
             for cid in cands}
    pool = sorted(fused, key=fused.get, reverse=True)[:config.FINAL_K]

    scores = get_reranker().predict([(query, cands[c][0]) for c in pool])
    ranked = sorted(zip(pool, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"id": cid, "text": cands[cid][0], "source": cands[cid][1]["source"],
             "page": cands[cid][1]["page"], "score": float(s)} for cid, s in ranked]


def format_context(chunks):
    return "\n\n".join(f"[{i}] ({c['source']}, p.{c['page']})\n{c['text']}"
                       for i, c in enumerate(chunks, 1))


def source_payload(chunks):
    return [{"n": i, "source": c["source"], "page": c["page"],
             "snippet": c["text"][:300]} for i, c in enumerate(chunks, 1)]


# ---------------------------------------------------------------------------
# LLM access (Groq or Ollama), always as a generator of text tokens
# ---------------------------------------------------------------------------
def _provider():
    if config.LLM_PROVIDER in ("gemini", "groq", "ollama", "lmstudio"):
        return config.LLM_PROVIDER
    if config.GEMINI_API_KEY:
        return "gemini"
    return "groq" if config.GROQ_API_KEY else "lmstudio"


class Thought(str):
    """A reasoning/"thinking" token from the model, kept apart from answer text."""


def _openai_compat_stream(base, model, messages, temperature, name, api_key=None):
    """Stream from any OpenAI-compatible /chat/completions endpoint (LM Studio, Gemini)."""
    base = base.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        if not model:
            models = requests.get(f"{base}/models", headers=headers, timeout=10).json().get("data", [])
            if not models:
                raise RuntimeError(f"{name} has no model loaded. Load one first.")
            model = models[0]["id"]
        with requests.post(f"{base}/chat/completions", headers=headers, stream=True, timeout=600, json={
                "model": model, "messages": messages, "temperature": temperature,
                "stream": True}) as r:
            if r.status_code != 200:
                raise RuntimeError(f"{name} error {r.status_code}: {r.text[:300]}")
            for line in r.iter_lines():
                if not line.startswith(b"data: "):
                    continue
                payload = line[6:].strip()
                if payload == b"[DONE]":
                    break
                data = json.loads(payload)
                if data.get("error"):
                    err = data["error"]
                    raise RuntimeError(f"{name} error: " + (err.get("message", str(err)) if isinstance(err, dict) else str(err)))
                choices = data.get("choices") or []
                delta = choices[0].get("delta", {}) if choices else {}
                if delta.get("reasoning_content"):
                    yield Thought(delta["reasoning_content"])
                if delta.get("content"):
                    yield delta["content"]
    except requests.ConnectionError:
        raise RuntimeError(f"Cannot reach {name} at {base}.")


def llm_stream(messages, model=None, temperature=0.2):
    if _provider() == "gemini":
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set (see backend/.env.example).")
        yield from _openai_compat_stream(config.GEMINI_URL, config.GEMINI_MODEL, messages,
                                         temperature, "Gemini", config.GEMINI_API_KEY)
    elif _provider() == "lmstudio":
        yield from _openai_compat_stream(config.LMSTUDIO_URL, config.LMSTUDIO_MODEL, messages,
                                         temperature, "LM Studio")
    elif _provider() == "groq":
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set (see backend/.env.example).")
        from groq import Groq
        stream = Groq(api_key=config.GROQ_API_KEY).chat.completions.create(
            model=model or config.GROQ_MAIN_MODEL, messages=messages,
            temperature=temperature, stream=True)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    else:
        try:
            with requests.post(f"{config.OLLAMA_URL}/api/chat", stream=True, timeout=300, json={
                    "model": config.OLLAMA_MODEL, "messages": messages, "stream": True,
                    "options": {"temperature": temperature}}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        part = json.loads(line)
                        if part.get("message", {}).get("content"):
                            yield part["message"]["content"]
        except requests.ConnectionError:
            raise RuntimeError(f"Cannot reach Ollama at {config.OLLAMA_URL}. Run `ollama serve` "
                               f"and `ollama pull {config.OLLAMA_MODEL}`, or set GROQ_API_KEY.")


def llm_complete(messages, model=None, temperature=0.2):
    return "".join(t for t in llm_stream(messages, model, temperature) if not isinstance(t, Thought))


def stream_events(messages, model, temperature):
    """Turn llm_stream tokens into content/reasoning events; fail loudly on empty output."""
    got_answer = False
    for token in llm_stream(messages, model, temperature):
        if isinstance(token, Thought):
            yield {"type": "reasoning", "text": token}
        else:
            got_answer = True
            yield {"type": "content", "text": token}
    if not got_answer:
        raise RuntimeError("The model returned no answer text. If it is a reasoning model, raise its "
                           "max tokens / context length in LM Studio, or try a shorter question.")


def _history_messages(history, limit=6):
    return [{"role": m["role"], "content": m["content"]} for m in history[-limit:]]


# ---------------------------------------------------------------------------
# Query pipelines. Each yields event dicts consumed by the SSE endpoint.
# ---------------------------------------------------------------------------
def answer_query(session_id, question, mode, history):
    mode = mode if mode in config.MODES else "factual"
    cfg = config.MODES[mode]
    yield {"type": "status", "message": "Searching documents…"}
    chunks = retrieve(session_id, question, cfg["top_k"])
    if not chunks:
        yield {"type": "content", "text": "No documents found in this session. Upload a PDF first."}
        return
    yield {"type": "sources", "sources": source_payload(chunks)}
    context = format_context(chunks)

    if mode == "reason":
        yield from _reasoning_pipeline(session_id, question, context, cfg, history)
        return

    system = config.FACTUAL_PROMPT if mode == "factual" else config.DETAILED_PROMPT
    messages = [{"role": "system", "content": system}, *_history_messages(history),
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}]
    yield {"type": "status", "message": "Generating answer…"}
    yield from stream_events(messages, cfg["model"], cfg["temperature"])


def _decompose(question):
    raw = llm_complete([{"role": "system", "content": config.DECOMPOSE_PROMPT},
                        {"role": "user", "content": question}],
                       model=config.GROQ_FAST_MODEL, temperature=0)
    try:
        start, end = raw.index("["), raw.rindex("]") + 1
        subs = [s for s in json.loads(raw[start:end]) if isinstance(s, str) and s.strip()]
    except (ValueError, json.JSONDecodeError):
        subs = []
    return (subs or [question])[:4]


def _reasoning_pipeline(session_id, question, context, cfg, history):
    yield {"type": "status", "message": "Decomposing question…"}
    subs = _decompose(question)
    yield {"type": "reasoning", "text": "**Sub-questions**\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(subs, 1)) + "\n\n"}
    answers = []
    for i, sub in enumerate(subs, 1):
        yield {"type": "status", "message": f"Answering sub-question {i}/{len(subs)}…"}
        sub_chunks = retrieve(session_id, sub, 3) or []
        ctx = format_context(sub_chunks) if sub_chunks else context
        ans = llm_complete([{"role": "system", "content": config.SUBANSWER_PROMPT},
                            {"role": "user", "content": f"Context:\n{ctx}\n\nSub-question: {sub}"}],
                           cfg["model"], cfg["temperature"])
        answers.append((sub, ans))
        yield {"type": "reasoning", "text": f"**{i}. {sub}**\n{ans}\n\n"}
    yield {"type": "status", "message": "Synthesizing final answer…"}
    joined = "\n\n".join(f"Sub-question: {q}\nAnswer: {a}" for q, a in answers)
    messages = [{"role": "system", "content": config.SYNTHESIS_PROMPT},
                {"role": "user", "content": f"Original question: {question}\n\nContext:\n{context}\n\n{joined}"}]
    yield from stream_events(messages, cfg["model"], cfg["temperature"])


def summarize_file(session_id, filename, max_chars=24000):
    ids, docs, metas = _all_chunks(session_id)
    rows = sorted(((m["page"], i, d) for i, d, m in zip(ids, docs, metas) if m["source"] == filename))
    if not rows:
        raise FileNotFoundError(filename)
    text = "\n".join(d for _, _, d in rows)
    parts = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    summaries = [llm_complete([{"role": "system", "content": config.SUMMARY_PROMPT},
                               {"role": "user", "content": p}]) for p in parts]
    if len(summaries) == 1:
        return summaries[0]
    return llm_complete([{"role": "system", "content": config.SUMMARY_COMBINE_PROMPT},
                         {"role": "user", "content": "\n\n---\n\n".join(summaries)}])
