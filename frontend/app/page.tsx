import Link from "next/link";

import { AutoRefresh } from "@/components/auto-refresh";
import { ProvenanceBadge, StatusBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { HeroCube } from "@/components/hero-cube";
import { Card, PageHeader, SectionTitle, TerminalHeader } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, fmtMetric, fmtPct, humanize, metricLabel, verdictTone } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";

export const dynamic = "force-dynamic";

const LOOP = [
  {
    title: "Measure",
    href: "/workloads",
    code: "01_MEASURE",
    description: "Baseline runs record value, unit, timestamp, source, and provenance.",
  },
  {
    title: "Analyze",
    href: "/optimizations",
    code: "02_ANALYZE",
    description: "A deterministic optimizer ranks candidates; Gemma is optional and untrusted.",
  },
  {
    title: "Simulate",
    href: "/optimizations",
    code: "03_SIMULATE",
    description: "Eligible configurations are estimated before any spend is considered.",
  },
  {
    title: "Approve",
    href: "/optimizations",
    code: "04_APPROVE",
    description: "A recorded human decision unlocks execution. There is no auto-approval.",
  },
  {
    title: "Execute",
    href: "/workflows",
    code: "05_EXECUTE",
    description: "Temporal runs the idempotent provider launch behind a safety re-check.",
  },
  {
    title: "Verify",
    href: "/reports",
    code: "06_VERIFY",
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
    <div className="space-y-10">
      {/* Hero Section with 3D Cube Anchor */}
      <div className="border-b border-[#292d30] pb-10">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
          <div className="max-w-2xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#292d30] bg-[#000000] px-3.5 py-1 font-mono text-xs text-[#f0f0f0]">
              <span className="h-2 w-2 rounded-full bg-[#3ad389]" />
              <span className="tracking-wide">Evidence-First Optimization</span>
              <span className="text-[#9281f7]">&gt;</span>
            </div>
            
            <h1 className="text-4xl font-normal tracking-tight text-white sm:text-6xl md:leading-[1.08]">
              Evidence over intuition.
            </h1>
            
            <p className="mt-4 text-sm leading-relaxed text-[#a1a4a5] sm:text-base">
              WATTSON binds GPU metrics to a deterministic closed loop. It measures baseline runtimes, ranks configuration changes, pauses for human approval, and verifies regressions without spin.
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Link href="/workloads" className="btn btn-ghost px-4 py-2 text-xs">
                Explore Workloads &rarr;
              </Link>
              <Link href="/optimizations" className="btn btn-muted px-4 py-2 text-xs">
                View Optimizer Plans
              </Link>
              <AutoRefresh active={activeWorkflows.length > 0} />
            </div>
          </div>

          <div className="hidden lg:flex items-center justify-center pr-6">
            <HeroCube size={120} />
          </div>
        </div>
      </div>

      <Flash notice={messages.notice} error={messages.error} />

      {/* Safety Alert (Kill Switch) */}
      {settings.kill_switch_active ? (
        <div className="rounded-[16px] border border-[#ff9592]/50 bg-[#000000] p-5">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff9592] animate-pulse" />
            <p className="font-mono text-sm font-semibold uppercase tracking-wider text-[#ff9592]">
              Kill switch is active
            </p>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-[#a1a4a5]">
            New executions are blocked by <span className="font-mono text-white">{settings.kill_switch_source}</span>.
            Existing workflows may be cancelled from the workflows monitor.
          </p>
          <Link
            className="mt-3 inline-flex font-mono text-xs text-[#ff9592] underline-offset-4 hover:underline"
            href="/settings"
          >
            Review safety settings &gt;
          </Link>
        </div>
      ) : null}

      {/* Metric Cards Grid */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Workloads</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{workloads.total}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Registered & measurable</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Plans</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{proposals.total}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Deterministic proposals</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Awaiting Approval</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-[#baa7ff]">{awaiting.length}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Human gate enforced</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Active Workflows</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{activeWorkflows.length}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Temporal execution</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Evidence Reports</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{reports.total}</p>
          <p className={`mt-1 font-mono text-[11px] ${verdictTone(latestReport?.verdict)}`}>
            {latestReport ? `Latest: ${humanize(latestReport.verdict)}` : "No verdict yet"}
          </p>
        </Card>
      </section>

      {/* The Closed Loop Pipeline */}
      <section>
        <SectionTitle
          title="The Closed Loop"
          hint="Each stage writes an audit event. The workflow cannot skip approval."
          right={
            <div className="inline-flex items-center gap-2 rounded-[6px] border border-[#292d30] bg-[#000000] px-2.5 py-1 font-mono text-[11px] text-[#a1a4a5]">
              <span className={`h-1.5 w-1.5 rounded-full ${health.status === "ok" ? "bg-[#3ad389]" : "bg-[#ffca16]"}`} />
              <span>PLANE {health.status.toUpperCase()}</span>
            </div>
          }
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {LOOP.map((stage) => (
            <Link key={stage.title} href={stage.href} className="group">
              <Card className="h-full p-5 hover:border-white/50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs text-[#9281f7]">&gt;</span>
                    <span className="font-mono text-xs font-semibold uppercase tracking-wider text-white">
                      {stage.title}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-[#6e727a]">{stage.code}</span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-[#a1a4a5]">{stage.description}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Health & Verdict Terminal Panels */}
      <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
        <div className="terminal-window overflow-hidden">
          <TerminalHeader title="control-plane.health ~ verified" />
          <div className="p-5">
            <SectionTitle
              title="System Diagnostics"
              hint="Continuous runtime checks with source provenance."
              right={<span className="font-mono text-xs text-[#9281f7]">v{health.version}</span>}
            />
            <ul className="space-y-2 mt-4 font-mono">
              {health.checks.map((check) => (
                <li
                  key={check.name}
                  className="flex flex-wrap items-center gap-3 rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5 transition-colors hover:border-[#6e727a]"
                >
                  <span className="w-36 text-xs text-[#f0f0f0]">{humanize(check.name)}</span>
                  <StatusBadge status={check.status} />
                  <ProvenanceBadge provenance={check.provenance} compact />
                  <span className="min-w-0 flex-1 truncate text-xs text-[#a1a4a5]">{check.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="terminal-window overflow-hidden">
          <TerminalHeader title="provenance.verify ~ delta" />
          <div className="p-5">
            <SectionTitle
              title="Latest Verification"
              hint="Compares provider execution result against recorded baseline."
              right={
                latestReport ? (
                  <Link
                    href={`/reports#report-${latestReport.id}`}
                    className="font-mono text-xs text-[#9281f7] hover:underline"
                  >
                    Open Report &gt;
                  </Link>
                ) : null
              }
            />
            {latestReport ? (
              <div className="mt-4">
                <div className="flex items-start justify-between gap-4 border-b border-[#292d30] pb-4">
                  <div>
                    <p className={`text-3xl font-normal capitalize tracking-tight ${verdictTone(latestReport.verdict)}`}>
                      {latestReport.verdict}
                    </p>
                    <p className="mt-1 font-mono text-xs text-[#a1a4a5]">
                      Weighted change: <span className="text-white">{fmtPct(latestReport.overall_change_pct)}</span>
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-[#6e727a]">Coverage</p>
                    <p className="font-mono text-xs text-[#f0f0f0]">
                      {latestReport.completeness.available_metrics}/{latestReport.completeness.total_metrics} slots
                    </p>
                  </div>
                </div>

                <dl className="mt-4 grid grid-cols-2 gap-2 font-mono">
                  {Object.entries(latestReport.summary.metrics).map(([metric, detail]) => (
                    <div key={metric} className="rounded-[6px] border border-[#292d30] bg-[#000000] p-3">
                      <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">{metricLabel(metric)}</dt>
                      <dd className="mt-1 text-xs font-medium text-white">{fmtMetric(metric, detail.result, detail.unit)}</dd>
                      <dd className="mt-1 flex items-center gap-1.5 text-[10px] text-[#a1a4a5]">
                        <ProvenanceBadge provenance={detail.result_provenance} compact /> {fmtPct(detail.change_pct)}
                      </dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-4 font-mono text-[11px] leading-relaxed text-[#6e727a]">{latestReport.uncertainty}</p>
              </div>
            ) : (
              <EmptyState title="No evidence yet" body="Run an approved plan through execution to generate verified telemetry." />
            )}
          </div>
        </div>
      </div>

      {/* Workflows & Audit Trail */}
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card className="p-5">
          <SectionTitle
            title="Recent Workflows"
            hint="Temporal state machine execution history."
            right={
              <Link href="/workflows" className="font-mono text-xs text-[#9281f7] hover:underline">
                All Workflows &gt;
              </Link>
            }
          />
          {workflows.items.length === 0 ? (
            <EmptyState title="No workflows" body="Create a proposal and start execution after recording human approval." />
          ) : (
            <div className="table-shell mt-4">
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
                        <Link
                          className="font-mono text-xs text-[#9281f7] hover:underline"
                          href={`/workflows#workflow-${workflow.workflow_id}`}
                        >
                          {workflow.workflow_id.replace("optimization-", "").slice(0, 12)}
                        </Link>
                        <p className="mt-1 font-mono text-[10px] text-[#6e727a]">{workflow.live_stage ?? workflow.stage}</p>
                      </td>
                      <td className="font-mono text-xs">{workflow.live_stage ?? workflow.stage}</td>
                      <td><StatusBadge status={workflow.status} /></td>
                      <td className="font-mono text-xs">{workflow.retries}</td>
                      <td className="font-mono text-xs text-[#a1a4a5]">{fmtDate(workflow.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Audit Ledger"
            hint="Append-only cryptographic record of approvals & actions."
            right={
              <Link href="/settings#audit" className="font-mono text-xs text-[#9281f7] hover:underline">
                Full Audit &gt;
              </Link>
            }
          />
          {audit.items.length === 0 ? (
            <EmptyState title="No audit events" body="The audit ledger is immutable and records the first system action." />
          ) : (
            <ol className="mt-4 space-y-3 font-mono text-xs">
              {audit.items.map((event) => (
                <li key={event.id} className="border-l border-[#292d30] pl-3 py-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] text-[#9281f7]">{event.event_type}</span>
                    <span className="shrink-0 text-[10px] text-[#6e727a]">{fmtDate(event.created_at)}</span>
                  </div>
                  <p className="mt-1 text-xs text-[#f0f0f0]">{event.message}</p>
                  <p className="text-[10px] text-[#6e727a]">actor: {event.actor}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      {latestWorkflow ? (
        <p className="text-center font-mono text-[11px] text-[#6e727a]">
          Last workflow transition {fmtDate(latestWorkflow.updated_at)} — all metrics verified against recorded provenance
        </p>
      ) : null}
    </div>
  );
}
