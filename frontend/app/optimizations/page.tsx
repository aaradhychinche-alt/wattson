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
    <Card className="overflow-hidden">
      <div id={`proposal-${proposal.id}`} className="scroll-mt-6 border-b border-[#292d30] bg-[#000000] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={proposal.status} />
              <span className="font-mono text-[10px] text-[#6e727a]">{proposal.id.slice(0, 12)}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#a1a4a5]">
                obj: {humanize(proposal.objective)}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="font-mono text-xs text-[#9281f7]">&gt;</span>
              <h2 className="text-base font-semibold text-white">{workloadName}</h2>
            </div>
            <p className="mt-1 font-mono text-xs text-[#a1a4a5]">
              Created {fmtDate(proposal.created_at)} — {proposal.candidates.length} candidates evaluated
            </p>
          </div>
          <div className="text-right">
            {proposal.report_id ? (
              <Link className="btn btn-ghost px-3 py-1.5" href={`/reports#report-${proposal.report_id}`}>
                Open Evidence Report &rarr;
              </Link>
            ) : proposal.workflow_id ? (
              <Link className="btn btn-muted px-3 py-1.5" href={`/workflows#workflow-${proposal.workflow_id}`}>
                Track Workflow &rarr;
              </Link>
            ) : null}
            {proposal.verdict ? (
              <p className="mt-2 font-mono text-xs font-semibold capitalize text-[#f0f0f0]">Verdict: {proposal.verdict}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-6 px-5 py-5 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-4">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-[#9281f7]">Selected Plan</p>
            {selected ? (
              <div className="mt-2 rounded-[6px] border border-[#292d30] bg-[#000000] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-mono text-sm font-semibold text-white">
                    {selected.config.gpu_count}x {selected.config.gpu_type} / batch {selected.config.batch_size} / {selected.config.precision}
                  </p>
                  <div className="flex items-center gap-2">
                    <Pill tone="iris">rank {selected.rank ?? "Unavailable"}</Pill>
                    <ProvenanceBadge provenance={selected.provenance} />
                  </div>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3 font-mono text-xs sm:grid-cols-4">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Est. Cost</dt>
                    <dd className="mt-1 text-white">{estimateText(selected, "cost_usd")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Energy</dt>
                    <dd className="mt-1 text-white">{estimateText(selected, "energy_kwh")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Latency</dt>
                    <dd className="mt-1 text-white">{estimateText(selected, "latency_ms")}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Throughput</dt>
                    <dd className="mt-1 text-white">{estimateText(selected, "throughput_samples_s")}</dd>
                  </div>
                </dl>
                <p className="mt-3 font-mono text-[10px] text-[#6e727a]">
                  Score {selected.score === null ? "Unavailable" : fmtNumber(selected.score, 4)} via min-max normalization. Estimates represent predictions, not confirmed runtimes.
                </p>
              </div>
            ) : (
              <p className="mt-2 rounded-[6px] border border-dashed border-[#292d30] p-4 font-mono text-xs text-[#a1a4a5]">
                No eligible candidate satisfies all hard constraints.
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
            <SectionTitle
              title="Candidate Evaluation Field"
              hint="Scores and eligibility calculated deterministically. Rejections are auditable."
            />
            <details className="rounded-[6px] border border-[#292d30] bg-[#000000]">
              <summary className="cursor-pointer list-none px-4 py-3 font-mono text-xs text-[#f0f0f0] hover:text-white transition-colors">
                <span className="text-[#9281f7]">&gt;</span> {proposal.candidates.length} candidates — {proposal.candidates.filter((c) => c.eligible).length} eligible
              </summary>
              <div className="table-shell border-0 border-t border-[#292d30] rounded-none">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Configuration</th>
                      <th>Est. Cost</th>
                      <th>Runtime</th>
                      <th>Score</th>
                      <th>Eligibility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranked.map((candidate) => {
                      const isSelected = candidate.id === proposal.selected_candidate_id;
                      return (
                        <tr key={candidate.id} className={isSelected ? "bg-[#0b0e14]" : ""}>
                          <td className="font-mono text-xs">{candidate.rank ?? "-"}</td>
                          <td className="font-mono text-xs">
                            {candidate.config.gpu_count}x {candidate.config.gpu_type} / {candidate.config.batch_size} / {candidate.config.precision}
                            {isSelected ? (
                              <span className="ml-2 rounded-[4px] border border-[#9281f7]/50 bg-[#9281f7]/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[#9281f7]">
                                selected
                              </span>
                            ) : null}
                          </td>
                          <td className="font-mono text-xs">{estimateText(candidate, "cost_usd")}</td>
                          <td className="font-mono text-xs">{candidate.runtime_hours === null ? "Unavailable" : `${fmtNumber(candidate.runtime_hours, 2)} h`}</td>
                          <td className="font-mono text-xs">{candidate.score === null ? "Unavailable" : fmtNumber(candidate.score, 4)}</td>
                          <td className="font-mono text-xs">
                            {candidate.eligible ? (
                              <span className="text-[#3ad389]">eligible</span>
                            ) : (
                              <ul className="space-y-1 text-[#a1a4a5]">
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
              title="Analysis Synthesis"
              hint={isAi ? "External model output. Validated before use." : "Deterministic fallback. No external model output presented as fact."}
              right={<Pill tone={isAi ? "iris" : "default"}>{isAi ? "Gemma Model" : "Deterministic"}</Pill>}
            />
            <div className="rounded-[6px] border border-[#292d30] bg-[#000000] p-4 font-mono text-xs">
              <p className="text-[#a1a4a5]">
                source: <span className="text-white">{analysis.source ?? "Unavailable"}</span>
                {analysis.model ? <> / model: <span className="text-[#9281f7]">{analysis.model}</span></> : null}
              </p>
              {analysis.fallback_reason ? (
                <p className="mt-1 text-[#ffca16]">fallback: {analysis.fallback_reason}</p>
              ) : null}

              {payload?.observed_facts?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6e727a]">Observed facts</p>
                  <ul className="mt-1 space-y-1.5 text-xs text-[#f0f0f0]">
                    {payload.observed_facts.map((fact, index) => (
                      <li key={`${fact.statement}-${index}`} className="leading-relaxed">
                        • {fact.statement} <span className="text-[#6e727a]">[{fact.evidence}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.hypotheses?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6e727a]">Hypotheses</p>
                  <ul className="mt-1 space-y-1.5 text-xs text-[#a1a4a5]">
                    {payload.hypotheses.map((hypothesis, index) => (
                      <li key={`${hypothesis.statement}-${index}`} className="leading-relaxed">
                        • {hypothesis.statement} <span className="text-[#6e727a]">({Math.round(hypothesis.confidence * 100)}%)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.missing_info?.length ? (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6e727a]">Missing information</p>
                  <ul className="mt-1 space-y-1.5 text-xs text-[#ffca16]">
                    {payload.missing_info.map((item, index) => (
                      <li key={`${item.item}-${index}`} className="leading-relaxed">
                        • {item.item}: <span className="text-[#a1a4a5]">{item.why_it_matters}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {payload?.proposed_tweak ? (
                <p className="mt-3 rounded-[6px] border border-[#292d30] bg-[#0b0e14] px-3 py-2 text-xs text-[#a1a4a5]">
                  Tweak suggestion: <span className="text-white">{payload.proposed_tweak.field}</span> ={" "}
                  <span className="text-[#9281f7]">{valueText(payload.proposed_tweak.value)}</span>
                  <span className="mt-1 block text-[#6e727a]">{payload.proposed_tweak.rationale}</span>
                </p>
              ) : null}

              <p className="mt-3 border-t border-[#292d30] pt-2 text-[10px] leading-relaxed text-[#6e727a]">
                AI synthesis cannot alter hard constraints or budget limits. Policy validation governs execution eligibility.
              </p>
            </div>
          </div>

          {/* Decision and Execution Box */}
          <div className="rounded-[6px] border border-[#292d30] bg-[#000000] p-4">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-[#a1a4a5]">
              Decision & Execution Gate
            </p>
            {proposal.approval ? (
              <div className="mt-2 font-mono text-xs leading-relaxed text-[#a1a4a5]">
                <p>
                  <span className={`font-semibold ${proposal.approval.decision === "approved" ? "text-[#3ad389]" : "text-[#ff9592]"}`}>
                    {humanize(proposal.approval.decision)}
                  </span>{" "}
                  by {proposal.approval.actor} at {fmtDate(proposal.approval.created_at)}
                </p>
                <p className="mt-1 text-[#6e727a]">Reason: {proposal.approval.reason || "No reason supplied."}</p>
              </div>
            ) : proposal.status === "awaiting_approval" ? (
              <p className="mt-2 font-mono text-xs leading-relaxed text-[#baa7ff]">
                BLOCKED: Waiting for recorded human decision. Workload cannot execute until approval is persisted in ledger.
              </p>
            ) : (
              <p className="mt-2 font-mono text-xs leading-relaxed text-[#6e727a]">
                {proposal.workflow_id ? "No decision recorded yet." : "Launch workflow to initiate the approval gate."}
              </p>
            )}

            {proposal.error ? (
              <p className="mt-2 rounded-[6px] border border-[#ff9592]/50 bg-[#000000] px-3 py-2 font-mono text-xs text-[#ff9592]">
                {proposal.error}
              </p>
            ) : null}

            {canStart ? (
              <form action={startWorkflowAction} className="mt-4">
                <input type="hidden" name="proposalId" value={proposal.id} />
                <button className="btn btn-ghost w-full py-2" type="submit">
                  Start Workflow & Request Approval &rarr;
                </button>
              </form>
            ) : null}

            {canDecide ? (
              <div className="mt-4 space-y-3 font-mono">
                <form action={approveAction} className="space-y-2 rounded-[6px] border border-[#3ad389]/40 bg-[#000000] p-3">
                  <input type="hidden" name="proposalId" value={proposal.id} />
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-[#3ad389]" htmlFor={`approve-reason-${proposal.id}`}>
                    Approval Rationale
                  </label>
                  <input
                    className="field"
                    id={`approve-reason-${proposal.id}`}
                    name="reason"
                    placeholder="Why is this plan safe to execute?"
                    required
                    minLength={3}
                  />
                  <label className="flex items-start gap-2 text-[10px] leading-relaxed text-[#a1a4a5]">
                    <input className="mt-0.5 accent-[#3ad389]" name="confirm" type="checkbox" required />
                    Confirm recorded approval authorizing cloud provider execution.
                  </label>
                  <button className="btn btn-ghost w-full border-[#3ad389]/60 text-[#3ad389] hover:border-[#3ad389] hover:bg-[#3ad389]/10" type="submit">
                    Record Approval & Proceed
                  </button>
                </form>
                <form action={rejectAction} className="space-y-2 rounded-[6px] border border-[#ff9592]/40 bg-[#000000] p-3">
                  <input type="hidden" name="proposalId" value={proposal.id} />
                  <label className="block text-[10px] font-semibold uppercase tracking-wider text-[#ff9592]" htmlFor={`reject-reason-${proposal.id}`}>
                    Rejection Rationale
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
                    Record Rejection
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
    <div className="space-y-10">
      <PageHeader
        eyebrow="02_ANALYZE_&_SIMULATE"
        title="Plans, Candidates & Approvals"
        description="The optimizer ranks only eligible configurations. Every estimate is labelled predicted or simulated, and every launch waits for a recorded human decision."
        action={<AutoRefresh active={active} />}
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Proposals</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{proposals.total}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Deterministic, reproducible plans</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Awaiting Approval</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-[#baa7ff]">{awaiting}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Execution deliberately blocked</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Past Approval Gate</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{executed}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Executed, failed, or completed</p>
        </Card>
      </div>

      {proposals.items.length === 0 ? (
        <EmptyState
          title="No optimization proposals"
          body="Open a workload and create a proposal. The optimizer will generate candidates and enforce hard constraints."
        />
      ) : (
        <section className="space-y-6">
          <SectionTitle
            title="Proposal Ledger"
            hint="Approval controls appear only when a workflow is blocked at the approval gate."
            right={<Link className="font-mono text-xs text-[#9281f7] hover:underline" href="/workloads">Create from workload &gt;</Link>}
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
