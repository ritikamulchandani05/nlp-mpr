import { useCallback, useEffect, useRef, useState } from "react";
import { Brain, Menu, Plus } from "lucide-react";
import ChatInput from "./components/chat-input.jsx";
import ChatMessage from "./components/chat-message.jsx";
import FileUploadProgress from "./components/file-upload-progress.jsx";
import SessionSidebar from "./components/session-sidebar.jsx";

const API = import.meta.env.VITE_API_URL || "http://localhost:5000";

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}
const jsonOpts = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [online, setOnline] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768);
  const [error, setError] = useState("");
  const abortRef = useRef(null);
  const bottomRef = useRef(null);

  const refreshSessions = useCallback(() => api("/sessions").then(setSessions).catch(() => {}), []);

  useEffect(() => {
    const ping = () => api("/health").then(() => setOnline(true)).catch(() => setOnline(false));
    ping();
    refreshSessions();
    const t = setInterval(ping, 15000);
    return () => clearInterval(t);
  }, [refreshSessions]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const openSession = useCallback(async (id) => {
    abortRef.current?.abort();
    setError("");
    try {
      const data = await api(`/sessions/${id}`);
      setActiveId(id); setMessages(data.messages); setFiles(data.files); setUploads([]);
      if (window.innerWidth < 768) setSidebarOpen(false);
    } catch (e) { setError(e.message); refreshSessions(); }
  }, [refreshSessions]);

  const createSession = useCallback(async () => {
    try {
      const s = await api("/sessions", jsonOpts("POST", {}));
      await refreshSessions();
      await openSession(s.id);
      return s.id;
    } catch (e) { setError(e.message); }
  }, [openSession, refreshSessions]);

  const deleteSession = async (id) => {
    if (!window.confirm("Delete this session and its documents?")) return;
    try {
      await api(`/sessions/${id}`, { method: "DELETE" });
      if (id === activeId) { abortRef.current?.abort(); setActiveId(null); setMessages([]); setFiles([]); }
      refreshSessions();
    } catch (e) { setError(e.message); }
  };

  const patchLast = (patch) => setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, ...(typeof patch === "function" ? patch(x) : patch) } : x)));

  const upload = async (selected) => {
    if (!selected.length) return;
    const sid = activeId || (await createSession());
    if (!sid) return;
    const items = selected.map((f) => ({ id: crypto.randomUUID(), name: f.name, status: "uploading" }));
    setUploads((u) => [...u, ...items]);
    // upload one at a time so each file gets its own progress state
    for (const [i, f] of selected.entries()) {
      const form = new FormData();
      form.append("files", f);
      let patch;
      try {
        const data = await api(`/sessions/${sid}/upload`, { method: "POST", body: form });
        setFiles(data.files);
        patch = { status: "done" };
      } catch (e) { patch = { status: "error", error: e.message }; }
      setUploads((u) => u.map((x) => (x.id === items[i].id ? { ...x, ...patch } : x)));
    }
    setTimeout(() => setUploads((u) => u.filter((x) => x.status === "uploading")), 4000);
  };

  const send = async (question, mode) => {
    const sid = activeId || (await createSession());
    if (!sid) return;
    setError("");
    const ts = Date.now() / 1000;
    setMessages((m) => [...m, { role: "user", content: question, ts }, { role: "assistant", content: "", reasoning: "", sources: [], status: "Starting…", ts }]);
    setStreaming(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let stoppedByUser = false;
    ctrl.signal.addEventListener("abort", () => { stoppedByUser = true; });
    try {
      const res = await fetch(`${API}/sessions/${sid}/query-stream`, { ...jsonOpts("POST", { question, mode }), signal: ctrl.signal });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Request failed (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop();
        for (const raw of events) {
          if (!raw.startsWith("data: ")) continue;
          const ev = JSON.parse(raw.slice(6));
          if (ev.type === "status") patchLast({ status: ev.message });
          else if (ev.type === "sources") patchLast({ sources: ev.sources });
          else if (ev.type === "reasoning") patchLast((x) => ({ reasoning: x.reasoning + ev.text }));
          else if (ev.type === "content") patchLast((x) => ({ content: x.content + ev.text }));
          else if (ev.type === "error") patchLast({ error: ev.message });
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") patchLast({ error: e.message });
    } finally {
      setStreaming(false);
      abortRef.current = null;
      patchLast((x) => (x.content || x.error ? {} : stoppedByUser ? { content: "_Stopped._" } : { error: "No response received from the model." }));
      refreshSessions();
    }
  };

  const summarize = async (filename) => {
    if (!filename || !activeId) return;
    const ts = Date.now() / 1000;
    setMessages((m) => [...m, { role: "user", content: `Generate a summary of "${filename}"`, ts }, { role: "assistant", content: "", status: "Summarizing document…", ts }]);
    setStreaming(true);
    try {
      const data = await api(`/sessions/${activeId}/summarize`, jsonOpts("POST", { filename }));
      patchLast({ content: data.summary });
    } catch (e) { patchLast({ error: e.message }); }
    setStreaming(false);
    refreshSessions();
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionSidebar open={sidebarOpen} sessions={sessions} activeId={activeId} onSelect={openSession}
        onCreate={createSession} onDelete={deleteSession} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass flex items-center gap-3 border-x-0 border-t-0 px-4 py-3">
          <button onClick={() => setSidebarOpen((o) => !o)} className="rounded-lg p-2 hover:bg-white/10" aria-label="Toggle sidebar"><Menu size={18} /></button>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-fuchsia-500 to-purple-600"><Brain size={18} /></div>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-semibold">{sessions.find((s) => s.id === activeId)?.title || "AI Research Assistant"}</h1>
            <p className="text-xs text-slate-400">Powered by Advanced RAG Technology</p>
          </div>
          <button onClick={createSession} className="flex items-center gap-1 rounded-lg bg-gradient-to-r from-fuchsia-500 to-purple-600 px-3 py-1.5 text-xs font-medium hover:opacity-90"><Plus size={14} /> New Chat</button>
          <span className={`rounded-full px-2 py-0.5 text-xs ${online ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>{online ? "Online" : "Offline"}</span>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6">
          {error && <p role="alert" className="mx-auto mb-3 max-w-3xl rounded-lg bg-red-500/20 px-3 py-2 text-sm text-red-200">{error}</p>}
          {!activeId ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Brain size={40} className="mb-3 text-fuchsia-300" />
              <h2 className="text-lg font-semibold">Getting Started</h2>
              <p className="mb-4 text-sm text-slate-400">Create your first chat session to begin.</p>
              <button onClick={createSession} className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-fuchsia-500 to-purple-600 px-4 py-2 text-sm font-medium hover:opacity-90"><Plus size={16} /> Create New Chat</button>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {messages.length === 0 && <p className="pt-16 text-center text-sm text-slate-400">Upload a PDF with the paperclip, then ask a question or press Summary.</p>}
              {messages.map((m, i) => <ChatMessage key={i} message={m} streaming={streaming && i === messages.length - 1} />)}
              <div ref={bottomRef} />
            </div>
          )}
        </main>

        {activeId && (
          <footer className="px-4 pb-4">
            <FileUploadProgress uploads={uploads} />
            <ChatInput files={files} streaming={streaming} onSend={send} onStop={() => abortRef.current?.abort()} onUpload={upload} onSummarize={summarize} />
          </footer>
        )}
      </div>
    </div>
  );
}
