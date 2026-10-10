export default function TypingIndicator({ label }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-300" role="status" aria-live="polite">
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-2 w-2 animate-bounce_dot rounded-full bg-fuchsia-400" style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </span>
      {label || "Thinking…"}
    </div>
  );
}
