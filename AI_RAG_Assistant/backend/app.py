"""Flask API for the AI RAG Assistant."""
import json
import logging
import time
from collections import defaultdict, deque
from functools import wraps

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config
import rag_utils as rag

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("rag")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
CORS(app, origins=[r"http://localhost:\d+", r"http://127\.0\.0\.1:\d+"])

_hits = defaultdict(deque)


@app.before_request
def rate_limit():
    now, q = time.time(), _hits[request.remote_addr]
    while q and q[0] < now - 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MIN:
        return jsonify(error="Rate limit exceeded. Try again shortly."), 429
    q.append(now)


def needs_session(fn):
    @wraps(fn)
    def wrapper(session_id, *a, **kw):
        if not rag.session_exists(session_id):
            return jsonify(error="Session not found"), 404
        return fn(session_id, *a, **kw)
    return wrapper


@app.errorhandler(413)
def too_large(_):
    return jsonify(error=f"File too large (max {config.MAX_UPLOAD_MB} MB)"), 413


@app.errorhandler(Exception)
def unhandled(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify(error=e.description), e.code
    log.exception("Unhandled error")
    return jsonify(error="Internal server error"), 500


@app.get("/health")
def health():
    return jsonify(status="ok")


# --- Sessions ----------------------------------------------------------------
@app.post("/sessions")
def create_session():
    title = (request.get_json(silent=True) or {}).get("title")
    if title is not None and not isinstance(title, str):
        return jsonify(error="title must be a string"), 400
    return jsonify(rag.create_session(title[:100] if title else None)), 201


@app.get("/sessions")
def list_sessions():
    return jsonify(rag.list_sessions())


@app.get("/sessions/<session_id>")
@needs_session
def get_session(session_id):
    return jsonify(meta=rag.get_meta(session_id), messages=rag.get_history(session_id),
                   files=rag.list_files(session_id))


@app.delete("/sessions/<session_id>")
@needs_session
def delete_session(session_id):
    rag.delete_session(session_id)
    return "", 204


# --- Documents ---------------------------------------------------------------
@app.post("/sessions/<session_id>/upload")
@needs_session
def upload(session_id):
    files = request.files.getlist("files")
    if not files:
        return jsonify(error="No files provided"), 400
    results = []
    for f in files:
        name = secure_filename(f.filename or "")
        if not name.lower().endswith(".pdf"):
            results.append({"filename": f.filename, "ok": False, "error": "Only PDF files are supported"})
            continue
        path = rag.session_dir(session_id) / "files" / name
        f.save(path)
        with open(path, "rb") as fh:
            is_pdf = fh.read(5) == b"%PDF-"
        if not is_pdf:
            path.unlink(missing_ok=True)
            results.append({"filename": name, "ok": False, "error": "Not a valid PDF"})
            continue
        try:
            results.append({"filename": name, "ok": True, "chunks": rag.process_pdf(session_id, path)})
        except Exception as e:  # corrupt/scanned PDFs
            path.unlink(missing_ok=True)
            log.warning("Ingest failed for %s: %s", name, e)
            results.append({"filename": name, "ok": False, "error": str(e)})
    status = 200 if any(r["ok"] for r in results) else 400
    return jsonify(results=results, files=rag.list_files(session_id)), status


@app.get("/sessions/<session_id>/files")
@needs_session
def files(session_id):
    return jsonify(rag.list_files(session_id))


# --- Query -------------------------------------------------------------------
def sse(event):
    return f"data: {json.dumps(event)}\n\n"


@app.post("/sessions/<session_id>/query-stream")
@needs_session
def query_stream(session_id):
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    mode = (body.get("mode") or "factual").strip().lower()
    mode = "reason" if mode.startswith("reason") else mode
    if not question:
        return jsonify(error="question is required"), 400
    if len(question) > 4000:
        return jsonify(error="question too long"), 400
    history = rag.get_history(session_id)

    @stream_with_context
    def generate():
        content, sources, reasoning = [], [], []
        try:
            for ev in rag.answer_query(session_id, question, mode, history):
                if ev["type"] == "content":
                    content.append(ev["text"])
                elif ev["type"] == "sources":
                    sources = ev["sources"]
                elif ev["type"] == "reasoning":
                    reasoning.append(ev["text"])
                yield sse(ev)
        except GeneratorExit:  # client pressed "stop": keep the partial answer
            pass
        except Exception as e:
            log.exception("query failed")
            yield sse({"type": "error", "message": str(e) or "Query failed"})
            return
        finally:
            if content:
                rag.append_history(
                    session_id,
                    {"role": "user", "content": question, "mode": mode, "ts": time.time()},
                    {"role": "assistant", "content": "".join(content), "sources": sources,
                     "reasoning": "".join(reasoning), "mode": mode, "ts": time.time()})
        yield sse({"type": "done"})

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/sessions/<session_id>/summarize")
@needs_session
def summarize(session_id):
    filename = secure_filename((request.get_json(silent=True) or {}).get("filename") or "")
    if filename not in rag.list_files(session_id):
        return jsonify(error="File not found in this session"), 404
    try:
        summary = rag.summarize_file(session_id, filename)
    except RuntimeError as e:
        return jsonify(error=str(e)), 502
    now = time.time()
    rag.append_history(
        session_id,
        {"role": "user", "content": f'Generate a summary of "{filename}"', "ts": now},
        {"role": "assistant", "content": summary, "sources": [], "ts": now})
    return jsonify(summary=summary)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
