import Link from "next/link";

export function Flash({ notice, error }: { notice?: string; error?: string }) {
  if (!notice && !error) return null;
  const isError = Boolean(error);
  return (
    <div
      className={`mb-6 flex items-start justify-between gap-4 rounded-xl border px-4 py-3 text-sm ${
        isError
          ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
          : "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
      }`}
      role="status"
    >
      <span>{error ?? notice}</span>
      <Link href="?" className="shrink-0 text-xs uppercase tracking-wider opacity-70 hover:opacity-100">
        Dismiss
      </Link>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/30 px-6 py-12 text-center">
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <p className="mx-auto mt-2 max-w-xl text-sm text-slate-500">{body}</p>
    </div>
  );
}
