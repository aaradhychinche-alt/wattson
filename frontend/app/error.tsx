"use client";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-2xl rounded-2xl border border-rose-500/30 bg-rose-500/5 p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rose-300">Control plane error</p>
      <h1 className="mt-3 text-2xl font-semibold text-white">The dashboard could not load data</h1>
      <p className="mt-3 text-sm leading-6 text-slate-400">
        Check that the WATTSON API is running and that <code className="text-slate-200">WATTSON_API_URL</code>{" "}
        and <code className="text-slate-200">WATTSON_API_TOKEN</code> are set for the Next.js server.
      </p>
      <pre className="mt-4 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-rose-200">
        {error.message}
      </pre>
      <button className="btn btn-primary mt-5" onClick={reset} type="button">
        Retry
      </button>
    </div>
  );
}
