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
  done: "border-[#3ad389]/40 bg-[#000000] text-[#3ad389]",
  current: "border-[#70b8ff]/60 bg-[#0b0e14] text-[#70b8ff]",
  pending: "border-[#292d30] bg-[#000000] text-[#464a4d]",
  failed: "border-[#ff9592]/50 bg-[#000000] text-[#ff9592]",
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
    <div className="space-y-10">
      <PageHeader
        eyebrow="05_EXECUTE"
        title="Temporal Workflows"
        description="A deterministic workflow records each stage transition, blocks on a human signal, revalidates safety preconditions, then launches idempotently."
        action={<AutoRefresh active={active} />}
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Workflows</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{workflows.total}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Durable state machines</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Running State</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-[#70b8ff]">
            {workflows.items.filter((workflow) => workflow.status === "running").length}
          </p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Waiting, executing, or verifying</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Observed Retries</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">
            {workflows.items.reduce((sum, workflow) => sum + workflow.retries, 0)}
          </p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Recorded activity attempts</p>
        </Card>
      </div>

      {workflows.items.length === 0 ? (
        <EmptyState
          title="No workflows"
          body="Start a proposal from the optimizations page. The workflow will proceed until the approval gate."
        />
      ) : (
        <section className="space-y-6">
          <SectionTitle
            title="Execution Ledger"
            hint="Stage progress is persisted independently of API process state. Retries do not duplicate cloud jobs."
          />
          {workflows.items.map((workflow) => {
            const lastNote = typeof workflow.meta.last_note === "string" ? workflow.meta.last_note : "";
            const cancelRequested = workflow.meta.cancel_requested === true;
            const terminal = TERMINAL.has(workflow.status);
            return (
              <Card key={workflow.workflow_id} className="overflow-hidden">
                <div id={`workflow-${workflow.workflow_id}`} className="scroll-mt-6 border-b border-[#292d30] bg-[#000000] px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={workflow.status} />
                        {workflow.verdict ? <StatusBadge status={workflow.verdict} /> : null}
                        {cancelRequested ? <Pill tone="iris">cancel requested</Pill> : null}
                      </div>
                      <p className="mt-2 break-all font-mono text-xs text-white">{workflow.workflow_id}</p>
                      <p className="mt-1 font-mono text-xs text-[#a1a4a5]">
                        Proposal {workflow.proposal_id.slice(0, 12)} — started {fmtDate(workflow.created_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {workflow.report_id ? (
                        <Link className="btn btn-ghost px-3 py-1.5" href={`/reports#report-${workflow.report_id}`}>
                          View Report &rarr;
                        </Link>
                      ) : null}
                      <Link className="btn btn-muted px-3 py-1.5" href={`/optimizations#proposal-${workflow.proposal_id}`}>
                        Proposal &rarr;
                      </Link>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 px-5 py-5">
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-xs text-[#a1a4a5]">
                    <span>Stage: <span className="text-white">{humanize(workflow.live_stage ?? workflow.stage)}</span></span>
                    <span>Retries: <span className="text-white">{workflow.retries}</span></span>
                    <span>Run ID: <span className="text-[#9281f7]">{workflow.run_id ? workflow.run_id.slice(0, 12) : "not launched"}</span></span>
                    <span>Updated: <span className="text-white">{fmtDate(workflow.updated_at)}</span></span>
                    {proposalNames.get(workflow.proposal_id) ? (
                      <span>Workload: <span className="text-[#f0f0f0]">{proposalNames.get(workflow.proposal_id)?.slice(0, 10)}</span></span>
                    ) : null}
                  </div>

                  <div>
                    <div className="flex flex-wrap gap-1.5 font-mono">
                      {STAGES.map((stage) => {
                        const state = stageState(workflow, stage);
                        return (
                          <span
                            key={stage}
                            className={`rounded-[6px] border px-2 py-1 text-[10px] font-medium transition-colors ${stageStyles[state]}`}
                            title={`${stage}: ${state}`}
                          >
                            {humanize(stage)}
                          </span>
                        );
                      })}
                    </div>
                    {lastNote ? <p className="mt-2 font-mono text-xs text-[#6e727a]">{lastNote}</p> : null}
                  </div>

                  {workflow.last_error ? (
                    <div className="rounded-[6px] border border-[#ff9592]/50 bg-[#000000] px-3 py-2 font-mono text-xs text-[#ff9592]">
                      <span className="font-semibold uppercase tracking-wider">Last error: </span>
                      {workflow.last_error}
                    </div>
                  ) : null}

                  {workflow.status === "running" && workflow.stage === "awaiting_approval" ? (
                    <p className="rounded-[6px] border border-[#baa7ff]/40 bg-[#000000] px-3.5 py-2.5 font-mono text-xs leading-relaxed text-[#baa7ff]">
                      BLOCKED: The workflow is paused at the approval gate. Record an approval or rejection in the optimizer plans tab to proceed.
                    </p>
                  ) : null}

                  {workflow.status === "running" ? (
                    <form action={cancelWorkflowAction} className="flex flex-col gap-2 rounded-[6px] border border-[#292d30] bg-[#000000] p-3 sm:flex-row sm:items-end">
                      <input type="hidden" name="workflowId" value={workflow.workflow_id} />
                      <div className="flex-1">
                        <label className="block font-mono text-[10px] font-semibold uppercase tracking-wider text-[#a1a4a5]" htmlFor={`cancel-${workflow.workflow_id}`}>
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
                      <button className="btn btn-danger" type="submit">
                        Request Cancellation
                      </button>
                    </form>
                  ) : null}

                  {!terminal && workflow.status !== "running" ? (
                    <p className={`font-mono text-xs ${statusTone(workflow.status)}`}>Workflow state: {humanize(workflow.status)}</p>
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
