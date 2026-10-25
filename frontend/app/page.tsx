import Link from "next/link";

import { AutoRefresh } from "@/components/auto-refresh";
import { ProvenanceBadge, StatusBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { Card, PageHeader, SectionTitle } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, fmtMetric, fmtPct, humanize, metricLabel, verdictTone } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";

export const dynamic = "force-dynamic";

const LOOP = [
  {
    title: "Measure",
    href: "/workloads",
    description: "Baseline runs record value, unit, timestamp, source, and provenance.",
  },
  {
    title: "Analyze",
    href: "/optimizations",
    description: "A deterministic optimizer ranks candidates; Gemma is optional and untrusted.",
  },
  {
    title: "Simulate",
    href: "/optimizations",
    description: "Eligible configurations are estimated before any spend is considered.",
  },
  {
    title: "Approve",
    href: "/optimizations",
    description: "A recorded human decision unlocks execution. There is no auto-approval.",
  },
  {
    title: "Execute",
    href: "/workflows",
    description: "Temporal runs the idempotent provider launch behind a safety re-check.",
  },
  {
    title: "Verify",
    href: "/reports",
    description: "The result is compared with the baseline, including honest regressions.",
  },
];

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const messages = flashMessages(params);
  const [health, settings, workloads, proposals, workflows, reports, audit] = await Promise.all([
    api.health(),
    api.settings(),
    api.workloads(),
    api.proposals(),
    api.workflows(),
    api.reports(),
    api.audit(8),
  ]);

  const activeWorkflows = workflows.items.filter((item) => item.status === "running");
  const awaiting = proposals.items.filter((item) => item.status === "awaiting_approval");
  const latestReport = reports.items[0] ?? null;
  const latestWorkflow = workflows.items[0] ?? null;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="MEASURE -> ANALYZE -> SIMULATE -> APPROVE -> EXECUTE -> VERIFY"
        title="Optimization control plane"
        description="WATTSON turns evidence into a bounded plan, stops for a recorded human decision, then proves whether the change helped or hurt."
        action={<AutoRefresh active={activeWorkflows.length > 0} />}
      />

      <Flash notice={messages.notice} error={messages.error} />

      {settings.kill_switch_active ? (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-5 py-4">
          <p className="text-sm font-semibold text-rose-200">Kill switch is active</p>
          <p className="mt-1 text-sm text-rose-200/70">
            New executions are blocked by <span className="font-mono">{settings.kill_switch_source}</span>.
            Existing workflows may be cancelled from the workflows page.
          </p>
          <Link className="mt-3 inline-flex text-xs font-semibold uppercase tracking-wider text-rose-200 underline-offset-4 hover:underline" href="/settings">
            Review safety settings
          </Link>
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Workloads</p>
          <p className="mt-2 text-3xl font-semibold text-white">{workloads.total}</p>
          <p className="mt-1 text-xs text-slate-500">Registered and measurable</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Plans</p>
          <p className="mt-2 text-3xl font-semibold text-white">{proposals.total}</p>
          <p className="mt-1 text-xs text-slate-500">Deterministic proposals</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Awaiting approval</p>
          <p className="mt-2 text-3xl font-semibold text-sky-300">{awaiting.length}</p>
          <p className="mt-1 text-xs text-slate-500">Blocked by design</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Active workflows</p>
          <p className="mt-2 text-3xl font-semibold text-white">{activeWorkflows.length}</p>
          <p className="mt-1 text-xs text-slate-500">Temporal execution or verification</p>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Evidence reports</p>
          <p className="mt-2 text-3xl font-semibold text-white">{reports.total}</p>
          <p className={`mt-1 text-xs ${verdictTone(latestReport?.verdict)}`}>
            {latestReport ? `Latest: ${humanize(latestReport.verdict)}` : "No verdict yet"}
          </p>
        </Card>
      </section>

      <section>
        <SectionTitle
          title="The closed loop"
          hint="Each stage writes an audit event. The workflow cannot skip approval."
          right={
            <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
              health.status === "ok"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border-amber-500/40 bg-amber-500/10 text-amber-300"
            }`}>
              control plane {health.status}
            </span>
          }
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {LOOP.map((stage, index) => (
            <Link key={stage.title} href={stage.href} className="group">
              <Card className="h-full p-5 transition group-hover:border-sky-500/40 group-hover:bg-slate-900/80">
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700 bg-slate-950/60 text-[10px] font-bold text-sky-300">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <p className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-200">{stage.title}</p>
                </div>
                <p className="mt-3 text-xs leading-5 text-slate-400">{stage.description}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <Card className="p-5">
          <SectionTitle
            title="Control plane health"
            hint="Checks are live; each check carries its own provenance."
            right={<span className="font-mono text-[10px] text-slate-500">v{health.version}</span>}
          />
          <ul className="space-y-2">
            {health.checks.map((check) => (
              <li key={check.name} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2.5">
                <span className="w-32 text-xs font-semibold uppercase tracking-wider text-slate-400">{humanize(check.name)}</span>
                <StatusBadge status={check.status} />
                <ProvenanceBadge provenance={check.provenance} compact />
                <span className="min-w-0 flex-1 text-xs text-slate-500">{check.detail}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Latest verdict"
            hint="VERIFY compares result against the recorded baseline."
            right={latestReport ? <Link href={`/reports#report-${latestReport.id}`} className="text-xs font-semibold text-sky-300 hover:underline">Open report</Link> : null}
          />
          {latestReport ? (
            <div>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className={`text-3xl font-semibold capitalize ${verdictTone(latestReport.verdict)}`}>{latestReport.verdict}</p>
                  <p className="mt-1 text-xs text-slate-500">Weighted change {fmtPct(latestReport.overall_change_pct)}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">Completeness</p>
                  <p className="text-sm font-semibold text-slate-200">
                    {latestReport.completeness.available_metrics}/{latestReport.completeness.total_metrics} metrics
                  </p>
                </div>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-2">
                {Object.entries(latestReport.summary.metrics).map(([metric, detail]) => (
                  <div key={metric} className="rounded-xl border border-slate-800/70 bg-slate-950/30 p-3">
                    <dt className="text-[10px] uppercase tracking-wider text-slate-500">{metricLabel(metric)}</dt>
                    <dd className="mt-1 text-sm font-semibold text-slate-200">{fmtMetric(metric, detail.result, detail.unit)}</dd>
                    <dd className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
                      <ProvenanceBadge provenance={detail.result_provenance} compact /> {fmtPct(detail.change_pct)}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="mt-4 text-xs leading-5 text-slate-500">{latestReport.uncertainty}</p>
            </div>
          ) : (
            <EmptyState title="No evidence yet" body="Run a plan through approval and execution to produce a verified report." />
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card className="p-5">
          <SectionTitle
            title="Recent workflows"
            hint="Temporal state plus persisted stage tracking."
            right={<Link href="/workflows" className="text-xs font-semibold text-sky-300 hover:underline">All workflows</Link>}
          />
          {workflows.items.length === 0 ? (
            <EmptyState title="No workflows" body="Create a proposal, start it, then record an approval to execute." />
          ) : (
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Workflow</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Retries</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.items.slice(0, 5).map((workflow) => (
                    <tr key={workflow.workflow_id}>
                      <td>
                        <Link className="font-mono text-xs text-sky-300 hover:underline" href={`/workflows#workflow-${workflow.workflow_id}`}>
                          {workflow.workflow_id.replace("optimization-", "").slice(0, 12)}
                        </Link>
                        <p className="mt-1 text-[10px] text-slate-500">{workflow.live_stage ?? workflow.stage}</p>
                      </td>
                      <td className="text-xs">{workflow.live_stage ?? workflow.stage}</td>
                      <td><StatusBadge status={workflow.status} /></td>
                      <td className="text-xs">{workflow.retries}</td>
                      <td className="text-xs text-slate-500">{fmtDate(workflow.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Audit trail"
            hint="Approvals, launches, retries, and cleanup are recorded."
            right={<Link href="/settings#audit" className="text-xs font-semibold text-sky-300 hover:underline">Full audit</Link>}
          />
          {audit.items.length === 0 ? (
            <EmptyState title="No audit events" body="The audit ledger is append-only and starts with the first action." />
          ) : (
            <ol className="space-y-3">
              {audit.items.map((event) => (
                <li key={event.id} className="border-l border-slate-800 pl-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[10px] text-sky-300">{event.event_type}</span>
                    <span className="shrink-0 text-[10px] text-slate-600">{fmtDate(event.created_at)}</span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-400">{event.message}</p>
                  <p className="text-[10px] text-slate-600">actor: {event.actor}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      {latestWorkflow ? (
        <p className="text-center text-[10px] uppercase tracking-[0.2em] text-slate-600">
          Last workflow update {fmtDate(latestWorkflow.updated_at)} - values shown with their provenance
        </p>
      ) : null}
    </div>
  );
}
