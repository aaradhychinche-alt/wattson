import Link from "next/link";

import { approveAction, rejectAction, startWorkflowAction } from "@/app/actions";
import { AutoRefresh } from "@/components/auto-refresh";
import { Pill, ProvenanceBadge, StatusBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { Card, PageHeader, SectionTitle } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, fmtMetric, fmtNumber, humanize } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";
import type { Candidate, Proposal } from "@/lib/types";

export const dynamic = "force-dynamic";

const FINAL_STATUSES = new Set(["completed", "rejected", "cancelled", "failed", "needs_intervention"]);

function estimateText(candidate: Candidate, metric: string): string {
  if (!candidate.estimates) return "Unavailable";
  const unit =
    metric === "cost_usd" ? "USD" : metric === "energy_kwh" ? "kWh" : metric === "latency_ms" ? "ms" : "samples/s";
  return fmtMetric(metric, candidate.estimates[metric], unit);
}

function valueText(value: unknown): string {
  if (value === null || value === undefined) return "Unavailable";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function ProposalCard({ proposal, workloadName }: { proposal: Proposal; workloadName: string }) {
  const selected = proposal.candidates.find((candidate) => candidate.id === proposal.selected_candidate_id) ?? null;
  const ranked = [...proposal.candidates].sort((a, b) => {
    if (a.rank === null && b.rank === null) return 0;
    if (a.rank === null) return 1;
    if (b.rank === null) return -1;
    return a.rank - b.rank;
  });
  const analysis = proposal.analysis ?? {};
  const payload = analysis.payload;
  const isAi = analysis.source !== "deterministic_fallback" && analysis.source !== "deterministic";
  const canStart = !proposal.workflow_id && !FINAL_STATUSES.has(proposal.status);
  const canDecide = proposal.status === "awaiting_approval" && !proposal.approval;
  const constraints = proposal.constraints_snapshot;

  return (
    <Card className="overflow-hidden" >
      <div id={`proposal-${proposal.id}`} className="scroll-mt-6 border-b border-slate-800/80 bg-slate-950/30 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={proposal.status} />
              <span className="font-mono text-[10px] text-slate-500">{proposal.id.slice(0, 12)}</span>
              <span className="text-[10px] uppercase tracking-wider text-slate-600">objective: {humanize(proposal.objective)}</span>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-white">{workloadName}</h2>
            <p className="mt-1 text-xs text-slate-500">
              Created {fmtDate(proposal.created_at)} - {proposal.candidates.length} candidates generated
            </p>
          </div>
          <div className="text-right">
            {proposal.report_id ? (
              <Link className="btn btn-primary" href={`/reports#report-${proposal.report_id}`}>
                Open evidence report
              </Link>
            ) : proposal.workflow_id ? (
              <Link className="btn btn-muted" href={`/workflows#workflow-${proposal.workflow_id}`}>
                Track workflow
              </Link>
            ) : null}
            {proposal.verdict ? (
              <p className="mt-2 text-xs font-semibold capitalize text-slate-400">Verdict: {proposal.verdict}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-5 px-5 py-5 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-400">Selected plan</p>
            {selected ? (
              <div className="mt-2 rounded-xl border border-sky-500/30 bg-sky-500/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-base font-semibold text-white">
                    {selected.config.gpu_count}x {selected.config.gpu_type} / batch {selected.config.batch_size} / {selected.config.precision}
                  </p>
                  <div className="flex items-center gap-2">
                    <Pill tone="sky">rank {selected.rank ?? "Unavailable"}</Pill>
                    <ProvenanceBadge provenance={selected.provenance} />
                  </div>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-500">Estimated cost</dt>
                    <dd className="mt-1 font-semibold text-slate-200">{estimateText(selected, "cost_usd")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-500">Energy</dt>
                    <dd className="mt-1 font-semibold text-slate-200">{estimateText(selected, "energy_kwh")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-500">Latency</dt>
                    <dd className="mt-1 font-semibold text-slate-200">{estimateText(selected, "latency_ms")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-slate-500">Throughput</dt>
                    <dd className="mt-1 font-semibold text-slate-200">{estimateText(selected, "throughput_samples_s")}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-[10px] text-slate-500">
                  Score {selected.score === null ? "Unavailable" : fmtNumber(selected.score, 4)} after min-max normalization. Estimates are predictions, not measurements.
                </p>
              </div>
            ) : (
              <p className="mt-2 rounded-xl border border-dashed border-slate-700 p-4 text-sm text-slate-500">
                No eligible candidate was selected. Execution is impossible for this plan.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Pill>budget {constraints.budget_usd === undefined ? "Unavailable" : `$${constraints.budget_usd.toFixed(2)}`}</Pill>
            <Pill>max runtime {constraints.max_runtime_hours === undefined ? "Unavailable" : `${constraints.max_runtime_hours} h`}</Pill>
            <Pill>deadline {fmtDate(constraints.deadline_at)}</Pill>
            <Pill>{proposal.normalization.replaceAll("_", " ")}</Pill>
          </div>

          <div>
            <SectionTitle title="Candidate field" hint="Eligibility and scores are computed deterministically. Open to audit every rejection." />
            <details className="rounded-xl border border-slate-800/70 bg-slate-950/30">
              <summary className="cursor-pointer list-none px-4 py-3 text-xs font-semibold text-slate-300">
                {proposal.candidates.length} candidates - {proposal.candidates.filter((c) => c.eligible).length} eligible
              </summary>
              <div className="table-shell border-0 border-t border-slate-800/70">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Config</th>
                      <th>Est. cost</th>
                      <th>Runtime</th>
                      <th>Score</th>
                      <th>Eligibility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((candidate) => {
                      const isSelected = candidate.id === proposal.selected_candidate_id;
                      return (
                        <tr key={candidate.id} className={isSelected ? "bg-sky-500/10" : ""}>
                          <td className="text-xs">{candidate.rank ?? "-"}</td>
                          <td className="text-xs">
                            {candidate.config.gpu_count}x {candidate.config.gpu_type} / {candidate.config.batch_size} / {candidate.config.precision}
                            {isSelected ? <span className="ml-2 rounded bg-sky-500/20 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-sky-200">selected</span> : null}
                          </td>
                          <td className="text-xs">{estimateText(candidate, "cost_usd")}</td>
                          <td className="text-xs">{candidate.runtime_hours === null ? "Unavailable" : `${fmtNumber(candidate.runtime_hours, 2)} h`}</td>
                          <td className="text-xs">{candidate.score === null ? "Unavailable" : fmtNumber(candidate.score, 4)}</td>
                          <td className="text-xs">
                            {candidate.eligible ? (
                              <span className="text-emerald-300">eligible</span>
                            ) : (
                              <ul className="space-y-1 text-slate-500">
                                {candidate.constraint_failures.map((failure) => (
                                  <li key={failure.code} title={failure.code}>{failure.message}</li>
                                ))}
                              </ul>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <SectionTitle
              title="Analysis"
              hint={isAi ? "External model output. Treated as untrusted and validated before use." : "Deterministic fallback. No external model output is presented as fact."}
              right={<Pill tone={isAi ? "violet" : "slate"}>{isAi ? "Gemma" : "deterministic"}</Pill>}
            />
            <div className="rounded-xl border border-slate-800/70 bg-slate-950/30 p-4 text-xs">
              <p className="text-slate-500">
                source: <span className="font-mono text-slate-300">{analysis.source ?? "Unavailable"}</span>
                {analysis.model ? <> / model: <span className="font-mono text-slate-300">{analysis.model}</span></> : null}
              </p>
              {analysis.fallback_reason ? (
                <p className="mt-1 text-amber-300/80">fallback: {analysis.fallback_reason}</p>
              ) : null}

              {payload?.observed_facts?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Observed facts</p>
                  <ul className="mt-1 space-y-1.5">
                    {payload.observed_facts.map((fact, index) => (
                      <li key={`${fact.statement}-${index}`} className="leading-5 text-slate-300">
                        {fact.statement} <span className="text-slate-600">[{fact.evidence}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.hypotheses?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Hypotheses</p>
                  <ul className="mt-1 space-y-1.5">
                    {payload.hypotheses.map((hypothesis, index) => (
                      <li key={`${hypothesis.statement}-${index}`} className="leading-5 text-slate-400">
                        {hypothesis.statement} <span className="text-slate-600">({Math.round(hypothesis.confidence * 100)}%)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.missing_info?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Missing information</p>
                  <ul className="mt-1 space-y-1.5">
                    {payload.missing_info.map((item, index) => (
                      <li key={`${item.item}-${index}`} className="leading-5 text-amber-300/80">
                        {item.item}: <span className="text-slate-500">{item.why_it_matters}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.proposed_tweak ? (
                <p className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2 leading-5 text-slate-400">
                  Tweak suggestion: <span className="font-mono text-slate-200">{payload.proposed_tweak.field}</span> ={" "}
                  <span className="font-mono text-slate-200">{valueText(payload.proposed_tweak.value)}</span>
                  <span className="mt-1 block text-slate-600">{payload.proposed_tweak.rationale}</span>
                </p>
              ) : null}

              <p className="mt-3 border-t border-slate-800/70 pt-2 text-[10px] leading-4 text-slate-600">
                Model text cannot change constraints, budgets, or the selected candidate. Policy validation and the execution guard make the final decision.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800/70 bg-slate-950/30 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Decision and execution</p>
            {proposal.approval ? (
              <div className="mt-2 text-xs leading-5 text-slate-400">
                <p>
                  <span className={`font-semibold ${proposal.approval.decision === "approved" ? "text-emerald-300" : "text-rose-300"}`}>
                    {humanize(proposal.approval.decision)}
                  </span>{" "}
                  by {proposal.approval.actor} at {fmtDate(proposal.approval.created_at)}
                </p>
                <p className="mt-1 text-slate-500">Reason: {proposal.approval.reason || "No reason supplied."}</p>
              </div>
            ) : proposal.status === "awaiting_approval" ? (
              <p className="mt-2 text-xs leading-5 text-amber-300/80">
                BLOCKED: waiting for a recorded human decision. Nothing is launched until approval is persisted.
              </p>
            ) : (
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {proposal.workflow_id ? "No decision recorded yet." : "Start the workflow to reach the approval gate."}
              </p>
            )}

            {proposal.error ? (
              <p className="mt-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{proposal.error}</p>
            ) : null}

            {canStart ? (
              <form action={startWorkflowAction} className="mt-3">
                <input type="hidden" name="proposalId" value={proposal.id} />
                <button className="btn btn-primary w-full" type="submit">
                  Start workflow and request approval
                </button>
              </form>
            ) : null}

            {canDecide ? (
              <div className="mt-3 space-y-3">
                <form action={approveAction} className="space-y-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
                  <input type="hidden" name="proposalId" value={proposal.id} />
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-emerald-300" htmlFor={`approve-reason-${proposal.id}`}>
                    Approval reason
                  </label>
                  <input
                    className="field"
                    id={`approve-reason-${proposal.id}`}
                    name="reason"
                    placeholder="Why is this plan safe to execute?"
                    required
                    minLength={3}
                  />
                  <label className="flex items-start gap-2 text-[10px] leading-4 text-slate-400">
                    <input className="mt-0.5" name="confirm" type="checkbox" required />
                    I understand this records a human approval and may incur real provider charges when a live provider is configured.
                  </label>
                  <button className="btn btn-primary w-full border-emerald-500/50 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25" type="submit">
                    Record approval
                  </button>
                </form>
                <form action={rejectAction} className="space-y-2 rounded-lg border border-rose-500/30 bg-rose-500/5 p-3">
                  <input type="hidden" name="proposalId" value={proposal.id} />
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-rose-300" htmlFor={`reject-reason-${proposal.id}`}>
                    Rejection reason
                  </label>
                  <input
                    className="field"
                    id={`reject-reason-${proposal.id}`}
                    name="reason"
                    placeholder="Why should this plan not run?"
                    required
                    minLength={3}
                  />
                  <button className="btn btn-danger w-full" type="submit">
                    Record rejection
                  </button>
                </form>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default async function OptimizationsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const messages = flashMessages(params);
  const [proposals, workloads] = await Promise.all([api.proposals(), api.workloads()]);
  const workloadNames = new Map(workloads.items.map((workload) => [workload.id, workload.name]));
  const awaiting = proposals.items.filter((proposal) => proposal.status === "awaiting_approval").length;
  const executed = proposals.items.filter((proposal) =>
    ["executing", "completed", "failed", "needs_intervention"].includes(proposal.status),
  ).length;
  const active = proposals.items.some((proposal) => !FINAL_STATUSES.has(proposal.status));

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="ANALYZE AND SIMULATE"
        title="Plans, candidates, and approvals"
        description="The optimizer ranks only eligible configurations. Every estimate is labelled predicted or simulated, and every launch waits for a recorded human decision."
        action={<AutoRefresh active={active} />}
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Proposals</p>
          <p className="mt-2 text-3xl font-semibold text-white">{proposals.total}</p>
          <p className="mt-1 text-xs text-slate-500">Deterministic, reproducible plans</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Awaiting approval</p>
          <p className="mt-2 text-3xl font-semibold text-amber-300">{awaiting}</p>
          <p className="mt-1 text-xs text-slate-500">Execution deliberately blocked</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Past approval gate</p>
          <p className="mt-2 text-3xl font-semibold text-white">{executed}</p>
          <p className="mt-1 text-xs text-slate-500">Executed, failed, or completed</p>
        </Card>
      </div>

      {proposals.items.length === 0 ? (
        <EmptyState
          title="No optimization proposals"
          body="Open a workload and create a deterministic proposal. The optimizer will generate candidates and apply hard constraints."
        />
      ) : (
        <section className="space-y-6">
          <SectionTitle
            title="Proposal ledger"
            hint="Approval controls appear only when a workflow is blocked at the approval gate."
            right={<Link className="text-xs font-semibold text-sky-300 hover:underline" href="/workloads">Create from a workload</Link>}
          />
          {proposals.items.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              workloadName={workloadNames.get(proposal.workload_id) ?? `Workload ${proposal.workload_id.slice(0, 10)}`}
            />
          ))}
        </section>
      )}
    </div>
  );
}
