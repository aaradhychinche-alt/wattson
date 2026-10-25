import Link from "next/link";

export function Flash({ notice, error }: { notice?: string; error?: string }) {
  if (!notice && !error) return null;
  const isError = Boolean(error);
  return (
    <div
      className={`mb-6 flex items-start justify-between gap-4 rounded-[6px] border px-4 py-3 text-xs font-mono transition-all ${
        isError
          ? "border-[#ff9592]/50 bg-[#000000] text-[#ff9592]"
          : "border-[#3ad389]/50 bg-[#000000] text-[#3ad389]"
      }`}
      role="status"
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            isError ? "bg-[#ff9592]" : "bg-[#3ad389]"
          }`}
        />
        <span>{error ?? notice}</span>
      </div>
      <Link
        href="?"
        className="shrink-0 uppercase tracking-wider text-[#a1a4a5] hover:text-white"
      >
        Dismiss
      </Link>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[16px] border border-dashed border-[#292d30] bg-[#000000] px-6 py-14 text-center">
      <div className="mx-auto mb-3 flex h-8 w-8 items-center justify-center rounded-full border border-[#292d30] text-[#a1a4a5]">
        <span className="font-mono text-xs">/</span>
      </div>
      <p className="text-sm font-medium text-white">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-xs text-[#a1a4a5] leading-relaxed">{body}</p>
    </div>
  );
}
