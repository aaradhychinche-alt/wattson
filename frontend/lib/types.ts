export type Provenance =
  | "measured"
  | "calculated"
  | "estimated"
  | "predicted"
  | "simulated"
  | "unavailable";

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type Candidate = {
  id: string;
  config: {
    gpu_type: string;
    gpu_count: number;
    batch_size: number;
    precision: string;
    checkpointing: boolean;
  };
  estimates: Record<string, number> | null;
  runtime_hours: number | null;
  eligible: boolean;
  constraint_failures: { code: string; message: string }[];
  normalized: Record<string, number> | null;
  score: number | null;
  rank: number | null;
  provenance: "predicted" | "simulated";
};

export type Approval = {
  id: string;
  proposal_id: string;
  decision: "approved" | "rejected";
  actor: string;
  reason: string;
  workflow_id: string | null;
  created_at: string;
};

export type Proposal = {
  id: string;
  workload_id: string;
  baseline_run_id: string | null;
  status: string;
  objective: string;
  weights: Record<string, number>;
  config_snapshot: Record<string, unknown>;
  constraints_snapshot: {
    budget_usd?: number;
    max_runtime_hours?: number;
    deadline_at?: string;
    allowed_gpu_types?: string[];
  };
  candidates: Candidate[];
  selected_candidate_id: string | null;
  analysis: {
    source?: string;
    provider?: string;
    model?: string;
    fallback_reason?: string | null;
    payload?: {
      observed_facts?: { statement: string; evidence: string }[];
      hypotheses?: { statement: string; rationale: string; confidence: number }[];
      missing_info?: { item: string; why_it_matters: string }[];
      proposed_tweak?: { field: string; value: unknown; rationale: string } | null;
    };
  };
  normalization: string;
  workflow_id: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  approval: Approval | null;
  report_id: string | null;
  verdict: string | null;
};

export type Workload = {
  id: string;
  name: string;
  description: string;
  workload_type: string;
  provider: string;
  current_config: {
    gpu_type: string;
    gpu_count: number;
    batch_size: number;
    precision: string;
    checkpointing: boolean;
  };
  constraints: {
    budget_usd?: number;
    max_runtime_hours?: number;
    deadline_at?: string;
    allowed_gpu_types?: string[];
  };
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Workflow = {
  workflow_id: string;
  proposal_id: string;
  run_id: string | null;
  stage: string;
  status: string;
  retries: number;
  last_error: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  live_stage: string | null;
  verdict: string | null;
  report_id: string | null;
};

export type ReportMetric = {
  baseline: number | null;
  result: number | null;
  change_pct: number | null;
  unit: string;
  baseline_provenance: Provenance;
  result_provenance: Provenance;
  baseline_available: boolean;
  result_available: boolean;
  baseline_source: string;
  result_source: string;
  baseline_measured_at: string | null;
  result_measured_at: string | null;
};

export type Report = {
  id: string;
  proposal_id: string;
  baseline_run_id: string;
  result_run_id: string;
  verdict: "improved" | "regressed" | "mixed" | "inconclusive";
  overall_change_pct: number | null;
  summary: {
    metrics: Record<string, ReportMetric>;
    weights: Record<string, number>;
    normalization: string;
    selected_candidate_id: string | null;
    provider: string;
    result_run_id: string;
    baseline_run_id: string;
  };
  narrative: string;
  narrative_source: string;
  uncertainty: string;
  completeness: { available_metrics: number; total_metrics: number; ratio: number; missing: string[] };
  measurement_window: Record<string, string | null>;
  created_at: string;
};

export type AuditEvent = {
  id: number;
  event_key: string;
  event_type: string;
  actor: string;
  proposal_id: string | null;
  workflow_id: string | null;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type Integration = {
  integration: string;
  status: string;
  detail: string;
  provenance: Provenance;
  meta: Record<string, unknown>;
  checked_at: string;
};

export type Settings = {
  kill_switch_active: boolean;
  kill_switch_source: string;
  kill_switch_env: boolean;
  provider: string;
  ai_provider: string;
  gemma_model: string;
  ai_configured: boolean;
  temporal_host: string;
  temporal_namespace: string;
  task_queue: string;
  database_driver: string;
  api_token_configured: boolean;
};

export type Health = {
  status: "ok" | "degraded";
  version: string;
  timestamp: string;
  checks: {
    name: string;
    status: string;
    detail: string;
    provenance: Provenance;
  }[];
};
