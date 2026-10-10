import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { motion } from "framer-motion";
import { Brain, ChevronDown, FileText } from "lucide-react";
import TypingIndicator from "./typing-indicator.jsx";

function Markdown({ children }) {
  return (
    <div className="markdown break-words text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{children}</ReactMarkdown>
    </div>
  );
}

function Sources({ sources }) {
  const [active, setActive] = useState(null);
  if (!sources?.length) return null;
  return (
    <div className="mt-3 border-t border-white/10 pt-2">
      <div className="mb-1 text-xs uppercase tracking-wide text-slate-400">Sources</div>
      <div className="flex flex-wrap gap-2">
        {sources.map((s) => (
          <button key={s.n} onClick={() => setActive(active === s.n ? null : s.n)} aria-expanded={active === s.n}
            className="flex items-center gap-1 rounded-full bg-white/10 px-2.5 py-1 text-xs hover:bg-white/20">
            <FileText size={12} /> [{s.n}] {s.source} · p.{s.page}
          </button>
        ))}
      </div>
      {active && <p className="mt-2 rounded-lg bg-black/30 p-2 text-xs text-slate-300">“{sources.find((s) => s.n === active)?.snippet}…”</p>}
    </div>
  );
}

function Reasoning({ text, streaming }) {
  const [open, setOpen] = useState(streaming);
  if (!text) return null;
  return (
    <div className="mb-3 rounded-lg bg-black/20 p-2">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-2 text-xs font-medium text-fuchsia-200">
        <Brain size={14} /> Reasoning steps
        <ChevronDown size={14} className={`ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="mt-2 text-slate-300"><Markdown>{text}</Markdown></div>}
    </div>
  );
}

export default function ChatMessage({ message, streaming }) {
  const isUser = message.role === "user";
  const time = message.ts ? new Date(message.ts * 1000 || message.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[92%] rounded-2xl px-4 py-3 md:max-w-[80%] ${isUser ? "bg-gradient-to-r from-sky-500 to-blue-600" : "glass"}`}>
        {isUser ? <p className="whitespace-pre-wrap text-sm">{message.content}</p> : (
          <>
            <Reasoning text={message.reasoning} streaming={streaming} />
            {message.content ? <Markdown>{message.content}</Markdown> : (message.error ? null : <TypingIndicator label={message.status} />)}
            {message.error && <p className="text-sm text-red-300" role="alert">⚠ {message.error}</p>}
            <Sources sources={message.sources} />
          </>
        )}
        {time && <div className="mt-1 text-right text-[10px] text-white/50">{time}</div>}
      </div>
    </motion.div>
  );
}
