import { AnimatePresence, motion } from "framer-motion";
import { MessageSquare, Plus, Trash2, X } from "lucide-react";

export default function SessionSidebar({ open, sessions, activeId, onSelect, onCreate, onDelete, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-20 bg-black/50 md:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside
            className="glass fixed inset-y-0 left-0 z-30 flex w-72 flex-col bg-slate-950/80 p-3 md:static md:z-auto md:bg-white/5"
            initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", damping: 28, stiffness: 300 }}
            aria-label="Chat sessions"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold">Sessions</h2>
              <button onClick={onClose} className="rounded p-1 hover:bg-white/10" aria-label="Close sidebar"><X size={18} /></button>
            </div>
            <button onClick={onCreate} className="mb-3 flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-fuchsia-500 to-purple-600 px-3 py-2 text-sm font-medium hover:opacity-90">
              <Plus size={16} /> New Chat
            </button>
            <ul className="flex-1 space-y-1 overflow-y-auto">
              {sessions.length === 0 && <li className="px-2 text-sm text-slate-400">No sessions yet.</li>}
              {sessions.map((s) => (
                <li key={s.id} className="group flex items-center">
                  <button
                    onClick={() => onSelect(s.id)}
                    aria-current={s.id === activeId}
                    className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-white/10 ${s.id === activeId ? "bg-white/15" : ""}`}
                  >
                    <MessageSquare size={14} className="shrink-0 text-fuchsia-300" />
                    <span className="truncate">{s.title}</span>
                  </button>
                  <button onClick={() => onDelete(s.id)} className="ml-1 rounded p-1.5 text-slate-400 opacity-0 hover:bg-red-500/20 hover:text-red-300 focus:opacity-100 group-hover:opacity-100" aria-label={`Delete ${s.title}`}>
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
