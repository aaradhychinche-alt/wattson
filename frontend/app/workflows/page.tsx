import Link from "next/link";

import { cancelWorkflowAction } from "@/app/actions";
import { AutoRefresh } from "@/components/auto-refresh";
import { Pill, StatusBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { Card, PageHeader, SectionTitle } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, humanize, statusTone } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";
import type { Workflow } from "@/lib/types";

export const dynamic = "force-dynamic";

const STAGES = [
  "validate",
  "load_baseline",
  "generate_candidates",
  "gemma_analysis",
  "validate_proposal",
  "simulate_candidates",
  "approval_request",
  "awaiting_approval",
  "revalidate",
  "execute",
  "collect",
  "compare",
  "persist_report",
  "cleanup",
];

const TERMINAL = new Set(["completed", "failed", "cancelled", "rejected", "needs_intervention"]);

function stageState(workflow: Workflow, stage: string): "done" | "current" | "pending" | "failed" {
  if (workflow.status === "completed" || workflow.stage === "finished") return "done";
  const currentIndex = STAGES.indexOf(workflow.stage);
  const index = STAGES.indexOf(stage);
  if (currentIndex === -1) {
    return workflow.status === "failed" || workflow.status === "needs_intervention" ? "failed" : "pending";
  }
  if (index < currentIndex) return "done";
  if (index > currentIndex) return "pending";
  if (workflow.status === "failed" || workflow.status === "needs_intervention") return "failed";
  return "current";
}

const stageStyles: Record<string, string> = {
  done: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  current: "border-sky-500/40 bg-sky-500/15 text-sky-200",
  pending: "border-slate-800 bg-slate-950/40 text-slate-600",
  failed: "border-rose-500/40 bg-rose-500/10 text-rose-200",
};

export default async function WorkflowsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const messages = flashMessages(params);
  const [workflows, proposals] = await Promise.all([api.workflows(), api.proposals()]);
  const proposalNames = new Map(proposals.items.map((proposal) => [proposal.id, proposal.workload_id]));
  const active = workflows.items.some((workflow) => workflow.status === "running");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="APPROVE AND EXECUTE"
        title="Temporal workflows"
        description="A deterministic workflow records each stage, blocks on a human signal, revalidates every safety condition, then launches once with an idempotency key."
        action={<AutoRefresh active={active} />}
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Workflows</p>
          <p className="mt-2 text-3xl font-semibold text-white">{workflows.total}</p>
          <p className="mt-1 text-xs text-slate-500">Durable Temporal executions</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Running</p>
          <p className="mt-2 text-3xl font-semibold text-sky-300">
            {workflows.items.filter((workflow) => workflow.status === "running").length}
          </p>
          <p className="mt-1 text-xs text-slate-500">Waiting, executing, or verifying</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Retries observed</p>
          <p className="mt-2 text-3xl font-semibold text-white">
            {workflows.items.reduce((sum, workflow) => sum + workflow.retries, 0)}
          </p>
          <p className="mt-1 text-xs text-slate-500">Recorded activity retries</p>
        </Card>
      </div>

      {workflows.items.length === 0 ? (
        <EmptyState
          title="No workflows"
          body="Start a proposal from the optimizations page. The workflow will wait at the approval gate."
        />
      ) : (
        <section className="space-y-5">
          <SectionTitle
            title="Execution ledger"
            hint="Stage progress is persisted independently of the API process. Retries do not duplicate launches."
          />
          {workflows.items.map((workflow) => {
            const lastNote = typeof workflow.meta.last_note === "string" ? workflow.meta.last_note : "";
            const cancelRequested = workflow.meta.cancel_requested === true;
            const terminal = TERMINAL.has(workflow.status);
            return (
              <Card key={workflow.workflow_id} className="overflow-hidden">
                <div id={`workflow-${workflow.workflow_id}`} className="scroll-mt-6 border-b border-slate-800/80 bg-slate-950/30 px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={workflow.status} />
                        {workflow.verdict ? <StatusBadge status={workflow.verdict} /> : null}
                        {cancelRequested ? <Pill tone="violet">cancel requested</Pill> : null}
                      </div>
                      <p className="mt-2 break-all font-mono text-xs text-slate-300">{workflow.workflow_id}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        Proposal {workflow.proposal_id.slice(0, 12)} - started {fmtDate(workflow.created_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {workflow.report_id ? (
                        <Link className="btn btn-primary" href={`/reports#report-${workflow.report_id}`}>Report</Link>
                      ) : null}
                      <Link className="btn btn-muted" href={`/optimizations#proposal-${workflow.proposal_id}`}>Proposal</Link>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 px-5 py-5">
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-500">
                    <span>Stage <span className="font-semibold text-slate-200">{humanize(workflow.live_stage ?? workflow.stage)}</span></span>
                    <span>Retries <span className="font-semibold text-slate-200">{workflow.retries}</span></span>
                    <span>Run <span className="font-mono text-slate-300">{workflow.run_id ? workflow.run_id.slice(0, 12) : "not launched"}</span></span>
                    <span>Updated <span className="text-slate-300">{fmtDate(workflow.updated_at)}</span></span>
                    {proposalNames.get(workflow.proposal_id) ? (
                      <span>Workload <span className="font-mono text-slate-300">{proposalNames.get(workflow.proposal_id)?.slice(0, 10)}</span></span>
                    ) : null}
                  </div>

                  <div>
                    <div className="flex flex-wrap gap-1.5">
                      {STAGES.map((stage) => {
                        const state = stageState(workflow, stage);
                        return (
                          <span
                            key={stage}
                            className={`rounded-md border px-2 py-1 text-[10px] font-medium ${stageStyles[state]}`}
                            title={`${stage}: ${state}`}
                          >
                            {humanize(stage)}
                          </span>
                        );
                      })}
                    </div>
                    {lastNote ? <p className="mt-2 text-xs leading-5 text-slate-500">{lastNote}</p> : null}
                  </div>

                  {workflow.last_error ? (
                    <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs leading-5 text-rose-200">
                      <span className="font-semibold uppercase tracking-wider">Last error: </span>
                      {workflow.last_error}
                    </div>
                  ) : null}

                  {workflow.status === "running" && workflow.stage === "awaiting_approval" ? (
                    <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-200">
                      The workflow is blocked at the approval gate. Record a decision on the optimizations page to continue or reject.
                    </p>
                  ) : null}

                  {workflow.status === "running" ? (
                    <form action={cancelWorkflowAction} className="flex flex-col gap-2 rounded-xl border border-slate-800/70 bg-slate-950/30 p-3 sm:flex-row sm:items-end">
                      <input type="hidden" name="workflowId" value={workflow.workflow_id} />
                      <div className="flex-1">
                        <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500" htmlFor={`cancel-${workflow.workflow_id}`}>
                          Cancellation reason
                        </label>
                        <input
                          className="field mt-1"
                          id={`cancel-${workflow.workflow_id}`}
                          name="reason"
                          defaultValue="Cancelled from the WATTSON dashboard."
                          maxLength={500}
                        />
                      </div>
                      <button className="btn btn-danger" type="submit">Request cancellation</button>
                    </form>
                  ) : null}

                  {!terminal && workflow.status !== "running" ? (
                    <p className={`text-xs ${statusTone(workflow.status)}`}>Workflow state: {humanize(workflow.status)}</p>
                  ) : null}
                </div>
              </Card>
            );
          })}
        </section>
      )}
    </div>
  );
}
