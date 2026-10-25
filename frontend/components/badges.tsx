import type { ReactNode } from "react";

import { humanize, provenanceLabel } from "@/lib/format";
import type { Provenance } from "@/lib/types";

// Semantic color mapping matching Resend Design Guide
const statusDotColors: Record<string, string> = {
  // Pulse Green (#3ad389)
  completed: "bg-[#3ad389]",
  connected: "bg-[#3ad389]",
  approved: "bg-[#3ad389]",
  measured: "bg-[#3ad389]",
  ok: "bg-[#3ad389]",
  improved: "bg-[#3ad389]",

  // Sky Blue (#70b8ff)
  running: "bg-[#70b8ff]",
  executing: "bg-[#70b8ff]",
  opened: "bg-[#70b8ff]",
  calculated: "bg-[#70b8ff]",

  // Iris Violet Glow (#baa7ff / #9281f7)
  awaiting_approval: "bg-[#baa7ff]",
  simulated: "bg-[#9281f7]",
  predicted: "bg-[#baa7ff]",

  // Alarm Red (#ff9592)
  failed: "bg-[#ff9592]",
  regressed: "bg-[#ff9592]",
  error: "bg-[#ff9592]",
  active: "bg-[#ff9592]", // for active kill switch
  rejected: "bg-[#ff9592]",

  // Amber (#ffca16)
  needs_intervention: "bg-[#ffca16]",
  mixed: "bg-[#ffca16]",
  estimated: "bg-[#ffca16]",
  warning: "bg-[#ffca16]",

  // Iron (#6e727a) / Ash (#a1a4a5)
  cancelled: "bg-[#6e727a]",
  unavailable: "bg-[#464a4d]",
};

export function StatusDot({ status }: { status: string }) {
  const key = status.toLowerCase();
  const color = statusDotColors[key] ?? "bg-[#6e727a]";
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${color}`} aria-hidden="true" />;
}

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  const dotColor = statusDotColors[key] ?? "bg-[#6e727a]";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#292d30] bg-[#000000] px-2.5 py-1 font-mono text-xs text-[#f0f0f0]"
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotColor}`} />
      <span>{humanize(status)}</span>
    </span>
  );
}

export function ProvenanceBadge({
  provenance,
  compact = false,
}: {
  provenance: Provenance | string;
  compact?: boolean;
}) {
  const key = String(provenance).toLowerCase();
  const dotColor = statusDotColors[key] ?? "bg-[#464a4d]";
  return (
    <span
      className={`inline-flex items-center rounded-[6px] border border-[#292d30] bg-[#000000] font-mono text-[11px] text-[#a1a4a5] ${
        compact ? "gap-1 px-1.5 py-0.5 text-[10px]" : "gap-1.5 px-2.5 py-0.5"
      }`}
      title={`Data provenance: ${provenanceLabel(provenance)}`}
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotColor}`} />
      <span className="uppercase tracking-wider">{provenanceLabel(provenance)}</span>
    </span>
  );
}

export function Pill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "iris" | "sky" | "pulse" | "alarm" | "amber" | string;
}) {
  const toneClasses: Record<string, string> = {
    default: "border-[#292d30] bg-[#000000] text-[#a1a4a5]",
    iris: "border-[#9281f7]/40 bg-[#000000] text-[#9281f7]",
    sky: "border-[#3b9eff]/40 bg-[#000000] text-[#70b8ff]",
    pulse: "border-[#3ad389]/40 bg-[#000000] text-[#3ad389]",
    alarm: "border-[#ff9592]/40 bg-[#000000] text-[#ff9592]",
    amber: "border-[#ffca16]/40 bg-[#000000] text-[#ffca16]",
    violet: "border-[#9281f7]/40 bg-[#000000] text-[#baa7ff]",
  };

  const selectedClass = toneClasses[tone] ?? toneClasses.default;

  return (
    <span
      className={`inline-flex items-center rounded-[6px] border px-2.5 py-0.5 font-mono text-xs font-normal ${selectedClass}`}
    >
      {children}
    </span>
  );
}

export function CodeIdentifier({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-xs text-[#9281f7]">
      {children}
    </span>
  );
}
