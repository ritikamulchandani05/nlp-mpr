import { useEffect, useRef, useState } from "react";
import { FileText, Paperclip, Send, Square, Zap } from "lucide-react";

const MODES = [
  { value: "factual", label: "Factual" },
  { value: "detailed", label: "Detailed" },
  { value: "reason", label: "Reason" },
];

export default function ChatInput({ files, streaming, onSend, onStop, onUpload, onSummarize }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("factual");
  const [summaryFile, setSummaryFile] = useState("");
  const fileRef = useRef(null);
  const areaRef = useRef(null);

  useEffect(() => {
    if (!files.includes(summaryFile)) setSummaryFile(files[0] || "");
  }, [files, summaryFile]);

  useEffect(() => {
    const el = areaRef.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 160) + "px"; }
  }, [text]);

  const submit = () => {
    const q = text.trim();
    if (!q || streaming) return;
    onSend(q, mode);
    setText("");
  };

  const selectCls = "rounded-lg border border-white/10 bg-slate-900/80 px-2 py-2 text-xs text-white";

  return (
    <div className="glass mx-auto flex w-full max-w-3xl flex-wrap items-end gap-2 rounded-2xl p-2">
      <input ref={fileRef} type="file" accept="application/pdf" multiple hidden onChange={(e) => { onUpload([...e.target.files]); e.target.value = ""; }} />
      <button onClick={() => fileRef.current.click()} className="rounded-lg bg-sky-500 p-2.5 hover:bg-sky-400" aria-label="Upload PDF files" title="Upload PDFs">
        <Paperclip size={16} />
      </button>
      <div className="flex items-center gap-1">
        <FileText size={14} className="text-emerald-300" aria-hidden />
        <select className={selectCls} value={summaryFile} onChange={(e) => setSummaryFile(e.target.value)} disabled={!files.length} aria-label="File to summarize">
          {files.length === 0 && <option>No files</option>}
          {files.map((f) => <option key={f} value={f}>{f.length > 22 ? f.slice(0, 20) + "…" : f}</option>)}
        </select>
        <button onClick={() => onSummarize(summaryFile)} disabled={!summaryFile || streaming} className="rounded-lg bg-emerald-600 px-2.5 py-2 text-xs font-medium hover:bg-emerald-500 disabled:opacity-40">
          Summary
        </button>
      </div>
      <div className="flex items-center gap-1">
        <Zap size={14} className="text-sky-300" aria-hidden />
        <select className={selectCls} value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Answer mode">
          {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>
      <textarea
        ref={areaRef} rows={1} value={text} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        placeholder="Ask me anything about your documents… (Shift+Enter for new line)"
        aria-label="Message"
        className="min-w-[200px] flex-1 resize-none rounded-lg bg-white/5 px-3 py-2.5 text-sm placeholder:text-slate-400"
      />
      {streaming ? (
        <button onClick={onStop} className="rounded-lg bg-red-500 p-2.5 hover:bg-red-400" aria-label="Stop generating"><Square size={16} /></button>
      ) : (
        <button onClick={submit} disabled={!text.trim()} className="rounded-lg bg-gradient-to-r from-fuchsia-500 to-purple-600 p-2.5 hover:opacity-90 disabled:opacity-40" aria-label="Send message"><Send size={16} /></button>
      )}
    </div>
  );
}
