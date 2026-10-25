import type { ReactNode } from "react";

import { humanize, provenanceLabel, statusTone } from "@/lib/format";
import type { Provenance } from "@/lib/types";

const provenanceStyles: Record<string, string> = {
  measured: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  calculated: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  estimated: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  predicted: "border-violet-500/40 bg-violet-500/10 text-violet-300",
  simulated: "border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-300",
  unavailable: "border-slate-600/50 bg-slate-800/60 text-slate-400",
};

export function ProvenanceBadge({
  provenance,
  compact = false,
}: {
  provenance: Provenance | string;
  compact?: boolean;
}) {
  const key = String(provenance).toLowerCase();
  const style = provenanceStyles[key] ?? provenanceStyles.unavailable;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${style} ${compact ? "" : "gap-1"}`}
      title={`Data provenance: ${provenanceLabel(provenance)}`}
    >
      {provenanceLabel(provenance)}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusTone(status)}`}
    >
      {humanize(status)}
    </span>
  );
}

export function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    slate: "border-slate-700 bg-slate-800/60 text-slate-300",
    sky: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    violet: "border-violet-500/40 bg-violet-500/10 text-violet-300",
    emerald: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone] ?? tones.slate}`}
    >
      {children}
    </span>
  );
}
