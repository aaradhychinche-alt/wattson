import type { Provenance } from "./types";

export function isUnavailable(value: number | null | undefined): boolean {
  return value === null || value === undefined;
}

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (isUnavailable(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value as number);
}

export function fmtMetric(metric: string, value: number | null | undefined, unit: string): string {
  if (isUnavailable(value)) return "Unavailable";
  const digits = metric === "cost_usd" ? 4 : metric === "energy_kwh" ? 4 : 2;
  return `${fmtNumber(value, digits)} ${unit}`;
}

export function fmtPct(value: number | null | undefined): string {
  if (isUnavailable(value)) return "Unavailable";
  const numeric = value as number;
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export function provenanceLabel(provenance: Provenance | string | null | undefined): string {
  if (!provenance) return "Unavailable";
  return provenance.charAt(0).toUpperCase() + provenance.slice(1);
}

export function statusTone(status: string): string {
  switch (status) {
    case "completed":
    case "connected":
    case "approved":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
    case "running":
    case "executing":
    case "awaiting_approval":
      return "border-sky-500/40 bg-sky-500/10 text-sky-300";
    case "failed":
    case "regressed":
    case "error":
      return "border-rose-500/40 bg-rose-500/10 text-rose-300";
    case "needs_intervention":
    case "mixed":
      return "border-amber-500/40 bg-amber-500/10 text-amber-300";
    case "rejected":
    case "cancelled":
      return "border-slate-500/40 bg-slate-500/10 text-slate-300";
    case "simulated":
    case "improved":
      return "border-violet-500/40 bg-violet-500/10 text-violet-300";
    default:
      return "border-slate-600/50 bg-slate-800/60 text-slate-300";
  }
}

export function verdictTone(verdict: string | null | undefined): string {
  switch (verdict) {
    case "improved":
      return "text-emerald-300";
    case "regressed":
      return "text-rose-300";
    case "mixed":
      return "text-amber-300";
    default:
      return "text-slate-300";
  }
}

export function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const METRIC_LABELS: Record<string, string> = {
  cost_usd: "Cost",
  energy_kwh: "Energy",
  latency_ms: "Latency",
  throughput_samples_s: "Throughput",
};

export function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? humanize(metric);
}
