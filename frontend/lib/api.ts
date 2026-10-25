/**
 * Server-only API client. The Bearer token never reaches the browser: every
 * fetch happens in a server component, server action, or route handler.
 */
import type {
  AuditEvent,
  Health,
  Integration,
  Page,
  Proposal,
  Report,
  Settings,
  Workflow,
  Workload,
} from "./types";

const API_URL = process.env.WATTSON_API_URL ?? "http://localhost:8000";
const TOKEN = process.env.WATTSON_API_TOKEN ?? "";

export class APIError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!TOKEN) {
    throw new APIError(500, "auth_not_configured", "WATTSON_API_TOKEN is not configured for the dashboard.");
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let code = "api_error";
    let message = `API request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } };
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      // keep the generic message
    }
    throw new APIError(response.status, code, message);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  workloads: () => request<Page<Workload>>("/api/workloads?limit=200"),
  proposals: () => request<Page<Proposal>>("/api/optimizations?limit=200"),
  workflows: () => request<Page<Workflow>>("/api/workflows?limit=200"),
  reports: () => request<Page<Report>>("/api/reports?limit=200"),
  report: (id: string) => request<Report>(`/api/reports/${id}`),
  audit: (limit = 30) => request<Page<AuditEvent>>(`/api/audit?limit=${limit}`),
  integrations: () => request<Integration[]>("/api/integrations"),
  settings: () => request<Settings>("/api/settings"),
  createProposal: (workloadId: string) =>
    request<Proposal>("/api/optimizations", {
      method: "POST",
      body: JSON.stringify({ workload_id: workloadId, objective: "balanced" }),
    }),
  startWorkflow: (proposalId: string) =>
    request<Workflow>("/api/workflows", {
      method: "POST",
      body: JSON.stringify({ proposal_id: proposalId }),
    }),
  approve: (proposalId: string, reason: string) =>
    request<unknown>(`/api/optimizations/${proposalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  reject: (proposalId: string, reason: string) =>
    request<unknown>(`/api/optimizations/${proposalId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  cancel: (workflowId: string, reason: string) =>
    request<unknown>(`/api/workflows/${workflowId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  setKillSwitch: (enabled: boolean) =>
    request<Settings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({ kill_switch: enabled }),
    }),
};
