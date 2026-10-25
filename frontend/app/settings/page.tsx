import Link from "next/link";

import { toggleKillSwitchAction } from "@/app/actions";
import { Pill, ProvenanceBadge, StatusBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { Card, PageHeader, SectionTitle } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, humanize } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";

export const dynamic = "force-dynamic";

function payloadPreview(payload: Record<string, unknown>): string {
  const entries = Object.entries(payload);
  if (entries.length === 0) return "No payload";
  return entries
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join("  /  ");
}

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const messages = flashMessages(params);
  const [settings, integrations, audit] = await Promise.all([
    api.settings(),
    api.integrations(),
    api.audit(100),
  ]);

  const config: { label: string; value: string }[] = [
    { label: "Provider", value: settings.provider },
    { label: "AI provider", value: settings.ai_provider },
    { label: "Gemma model", value: settings.gemma_model || "Not configured" },
    { label: "AI configured", value: settings.ai_configured ? "Yes" : "No - deterministic fallback" },
    { label: "Temporal host", value: settings.temporal_host },
    { label: "Temporal namespace", value: settings.temporal_namespace },
    { label: "Task queue", value: settings.task_queue },
    { label: "Database driver", value: settings.database_driver },
    { label: "API token", value: settings.api_token_configured ? "Configured (token hidden)" : "Missing" },
  ];

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="SAFETY_&_SYSTEM_INTEGRATIONS"
        title="Settings & Audit"
        description="The kill switch, integration status, and append-only audit ledger are exposed here. Secrets are never rendered. Environment configuration always overrides dashboard state."
        action={
          <Link className="btn btn-ghost px-4 py-2" href="#audit">
            Jump to Audit Ledger &darr;
          </Link>
        }
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-6 xl:grid-cols-[1fr_1.25fr]">
        <Card className={`p-5 ${settings.kill_switch_active ? "border-[#ff9592]/50" : ""}`}>
          <SectionTitle
            title="Kill Switch Guard"
            hint="Checked by execution guard immediately before cloud launch."
            right={
              <div className="inline-flex items-center gap-1.5 rounded-[6px] border border-[#292d30] bg-[#000000] px-2.5 py-1 font-mono text-[11px]">
                <span className={`h-1.5 w-1.5 rounded-full ${settings.kill_switch_active ? "bg-[#ff9592]" : "bg-[#3ad389]"}`} />
                <span className={settings.kill_switch_active ? "text-[#ff9592]" : "text-[#3ad389]"}>
                  {settings.kill_switch_active ? "ACTIVE" : "STANDBY"}
                </span>
              </div>
            }
          />
          <p className="text-xs leading-relaxed text-[#a1a4a5]">
            When active, every new execution is stopped at safety revalidation. The switch cannot bypass approval; it strictly aborts jobs.
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-3 rounded-[6px] border border-[#292d30] bg-[#000000] p-3 font-mono text-xs">
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Effective Source</dt>
              <dd className="mt-1 text-white">{settings.kill_switch_source}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Env Override</dt>
              <dd className="mt-1 text-white">{settings.kill_switch_env ? "WATTSON_KILL_SWITCH=true" : "Not set"}</dd>
            </div>
          </dl>
          {settings.kill_switch_env ? (
            <p className="mt-3 rounded-[6px] border border-[#ffca16]/40 bg-[#000000] px-3 py-2 font-mono text-xs leading-relaxed text-[#ffca16]">
              The environment variable is active and takes precedence. Remove the env variable to deactivate.
            </p>
          ) : null}
          <form action={toggleKillSwitchAction} className="mt-4">
            <input type="hidden" name="enabled" value={settings.kill_switch_active ? "false" : "true"} />
            <button
              className={`btn w-full ${settings.kill_switch_active ? "btn-ghost text-white" : "btn-danger"}`}
              type="submit"
            >
              {settings.kill_switch_active ? "Deactivate Kill Switch" : "Activate Emergency Kill Switch"}
            </button>
          </form>
          <p className="mt-3 font-mono text-[10px] text-[#6e727a]">
            Changing the kill switch appends an immutable event to the audit ledger.
          </p>
        </Card>

        <Card className="p-5 font-mono">
          <SectionTitle
            title="Runtime Configuration"
            hint="Read-only view of server-side environment parameters. Secrets redacted."
          />
          <dl className="grid gap-2 sm:grid-cols-2 mt-2">
            {config.map((item) => (
              <div key={item.label} className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">{item.label}</dt>
                <dd className="mt-0.5 break-words text-xs text-[#f0f0f0]">{item.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-[11px] text-[#6e727a]">
            Configure live cloud or hosted Gemma models via environment variables and restart API and workers.
          </p>
        </Card>
      </div>

      <section>
        <SectionTitle
          title="Subsystem Integrations"
          hint="Status checks queried in real time. Simulated adapters labelled explicitly."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {integrations.map((integration) => (
            <Card key={integration.integration} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-[#9281f7]">&gt;</span>
                  <p className="text-sm font-semibold text-white">{humanize(integration.integration)}</p>
                </div>
                <StatusBadge status={integration.status} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <ProvenanceBadge provenance={integration.provenance} />
                <span className="font-mono text-[10px] text-[#6e727a]">checked {fmtDate(integration.checked_at)}</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-[#a1a4a5]">{integration.detail}</p>
              {Object.keys(integration.meta).length > 0 ? (
                <details className="mt-3 rounded-[6px] border border-[#292d30] bg-[#000000]">
                  <summary className="cursor-pointer px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-[#6e727a] hover:text-white transition-colors">
                    Metadata Payload
                  </summary>
                  <pre className="max-h-40 overflow-auto border-t border-[#292d30] p-2.5 font-mono text-[10px] leading-relaxed text-[#a1a4a5]">
                    {JSON.stringify(integration.meta, null, 2)}
                  </pre>
                </details>
              ) : null}
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <Card className="p-5">
          <SectionTitle
            title="Safety Protocol"
            hint="Enforced at workflow orchestration, never by language model prompts."
          />
          <ul className="space-y-2.5 font-mono text-xs leading-relaxed text-[#a1a4a5]">
            <li className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5">
              <span className="text-white font-medium">1. Gate before spend:</span> Pre-execution guard verifies persisted human approval signature.
            </li>
            <li className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5">
              <span className="text-white font-medium">2. Provenance tags:</span> Missing metrics returned as unavailable, never fabricated as zeros.
            </li>
            <li className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5">
              <span className="text-white font-medium">3. Untrusted AI bounds:</span> Gemma output schema-constrained; cannot modify budgets or candidates.
            </li>
            <li className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5">
              <span className="text-white font-medium">4. Idempotent launches:</span> Deterministic run names protect from duplicate cloud provision costs.
            </li>
            <li className="rounded-[6px] border border-[#292d30] bg-[#000000] px-3.5 py-2.5">
              <span className="text-white font-medium">5. Regressions exposed:</span> Performance degradation is flagged directly in evidence reports.
            </li>
          </ul>
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="Demonstration Environment"
            hint="Distinguishing simulated sandboxes from live compute paths."
            right={<Pill tone="iris">Deterministic Simulator</Pill>}
          />
          <div className="space-y-3 font-mono text-xs leading-relaxed text-[#a1a4a5]">
            <p>
              The default setup operates in simulation mode with seeded workloads. All synthetic metrics are tagged <span className="text-[#baa7ff]">simulated</span>.
            </p>
            <p>
              Temporal task queues, SQLite audit transactions, kill-switch interrupts, and the Next.js control plane run genuine system code.
            </p>
            <p>
              Zero external charges are incurred in simulation mode. Live JarvisLabs compute requires explicit API keys and operator approval.
            </p>
          </div>
        </Card>
      </div>

      <section id="audit" className="scroll-mt-6">
        <SectionTitle
          title="Audit Ledger"
          hint="Append-only cryptographic event log. Recent 100 entries displayed."
          right={<span className="font-mono text-[10px] uppercase tracking-wider text-[#6e727a]">{audit.total} events recorded</span>}
        />
        {audit.items.length === 0 ? (
          <EmptyState title="No audit events" body="Events appear when a workload is seeded, a proposal is created, or a workflow stage advances." />
        ) : (
          <Card className="overflow-hidden">
            <div className="table-shell border-0 rounded-none">
              <table className="data-table min-w-[900px]">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>References</th>
                    <th>Payload</th>
                    <th>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.items.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <p className="font-mono text-xs text-[#9281f7]">{event.event_type}</p>
                        <p className="mt-1 text-xs text-[#f0f0f0]">{event.message}</p>
                      </td>
                      <td className="font-mono text-xs text-[#a1a4a5]">{event.actor}</td>
                      <td className="font-mono text-[10px] text-[#6e727a]">
                        {event.proposal_id ? <p className="break-all">prop: {event.proposal_id.slice(0, 12)}</p> : null}
                        {event.workflow_id ? <p className="break-all">wf: {event.workflow_id.slice(0, 18)}</p> : null}
                      </td>
                      <td className="max-w-[320px]">
                        <p className="break-words font-mono text-[10px] leading-relaxed text-[#6e727a]">{payloadPreview(event.payload)}</p>
                      </td>
                      <td className="whitespace-nowrap font-mono text-[10px] text-[#a1a4a5]">{fmtDate(event.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>
    </div>
  );
}
