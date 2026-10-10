import { CheckCircle2, FileText, Loader2, XCircle } from "lucide-react";

export default function FileUploadProgress({ uploads }) {
  if (!uploads.length) return null;
  return (
    <ul className="mx-auto mb-2 w-full max-w-3xl space-y-1" aria-label="Uploads">
      {uploads.map((u) => (
        <li key={u.id} className="glass flex items-center gap-2 rounded-lg px-3 py-2 text-sm">
          <FileText size={16} className="shrink-0 text-fuchsia-300" />
          <span className="min-w-0 flex-1 truncate">{u.name}</span>
          {u.status === "uploading" && <><span className="text-xs text-slate-300">Indexing…</span><Loader2 size={16} className="animate-spin text-fuchsia-300" /></>}
          {u.status === "done" && <CheckCircle2 size={16} className="text-emerald-400" />}
          {u.status === "error" && <><span className="text-xs text-red-300">{u.error}</span><XCircle size={16} className="text-red-400" /></>}
        </li>
      ))}
    </ul>
  );
}
