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
  switch (status.toLowerCase()) {
    case "completed":
    case "connected":
    case "approved":
    case "measured":
    case "ok":
      return "border-[#292d30] bg-[#000000] text-[#3ad389]";
    case "running":
    case "executing":
    case "awaiting_approval":
      return "border-[#292d30] bg-[#000000] text-[#70b8ff]";
    case "failed":
    case "regressed":
    case "error":
      return "border-[#292d30] bg-[#000000] text-[#ff9592]";
    case "needs_intervention":
    case "mixed":
      return "border-[#292d30] bg-[#000000] text-[#ffca16]";
    case "rejected":
    case "cancelled":
      return "border-[#292d30] bg-[#000000] text-[#a1a4a5]";
    case "simulated":
    case "improved":
      return "border-[#292d30] bg-[#000000] text-[#9281f7]";
    default:
      return "border-[#292d30] bg-[#000000] text-[#f0f0f0]";
  }
}

export function verdictTone(verdict: string | null | undefined): string {
  switch (verdict) {
    case "improved":
      return "text-[#3ad389]";
    case "regressed":
      return "text-[#ff9592]";
    case "mixed":
      return "text-[#ffca16]";
    default:
      return "text-[#f0f0f0]";
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
