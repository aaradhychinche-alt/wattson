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
    { label: "API token", value: settings.api_token_configured ? "Configured (value hidden)" : "Missing" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="SAFETY AND INTEGRATIONS"
        title="Settings and audit"
        description="The kill switch, integration status, and append-only audit ledger are exposed here. Secrets are never rendered. Environment configuration always wins over dashboard state."
        action={
          <Link className="btn btn-muted" href="#audit">
            Jump to audit trail
          </Link>
        }
      />

      <Flash notice={messages.notice} error={messages.error} />

      <div className="grid gap-5 xl:grid-cols-[1fr_1.25fr]">
        <Card className={`p-5 ${settings.kill_switch_active ? "border-rose-500/40" : ""}`}>
          <SectionTitle
            title="Kill switch"
            hint="Checked by the execution guard immediately before any provider launch."
            right={
              <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                settings.kill_switch_active
                  ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
                  : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              }`}>
                {settings.kill_switch_active ? "active" : "off"}
              </span>
            }
          />
          <p className="text-sm leading-6 text-slate-400">
            When active, every new execution is blocked at revalidation. The switch cannot bypass recorded approval; it can only stop work.
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl border border-slate-800/70 bg-slate-950/30 p-3 text-xs">
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-slate-500">Effective source</dt>
              <dd className="mt-1 font-mono text-slate-200">{settings.kill_switch_source}</dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wider text-slate-500">Environment override</dt>
              <dd className="mt-1 text-slate-200">{settings.kill_switch_env ? "WATTSON_KILL_SWITCH=true" : "Not set"}</dd>
            </div>
          </dl>
          {settings.kill_switch_env ? (
            <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs leading-5 text-amber-200">
              The environment variable is active and takes precedence. Dashboard changes cannot turn execution back on until the environment value is removed.
            </p>
          ) : null}
          <form action={toggleKillSwitchAction} className="mt-4">
            <input type="hidden" name="enabled" value={settings.kill_switch_active ? "false" : "true"} />
            <button className={`btn w-full ${settings.kill_switch_active ? "btn-primary" : "btn-danger"}`} type="submit">
              {settings.kill_switch_active ? "Deactivate kill switch" : "Activate kill switch"}
            </button>
          </form>
          <p className="mt-3 text-[10px] leading-4 text-slate-600">
            Changing the switch writes an audit event with actor and timestamp.
          </p>
        </Card>

        <Card className="p-5">
          <SectionTitle title="Runtime configuration" hint="Read-only view of server-side settings. No secret values are returned by the API." />
          <dl className="grid gap-2 sm:grid-cols-2">
            {config.map((item) => (
              <div key={item.label} className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
                <dt className="text-[10px] uppercase tracking-wider text-slate-500">{item.label}</dt>
                <dd className="mt-0.5 break-words text-xs font-medium text-slate-200">{item.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-[10px] leading-4 text-slate-600">
            To configure a live provider or hosted Gemma, set the environment variables documented in the README and restart the API and worker.
          </p>
        </Card>
      </div>

      <section>
        <SectionTitle
          title="Integrations"
          hint="Status checks are live at request time. Simulated integrations are labelled, never presented as live connections."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {integrations.map((integration) => (
            <Card key={integration.integration} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-white">{humanize(integration.integration)}</p>
                <StatusBadge status={integration.status} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <ProvenanceBadge provenance={integration.provenance} />
                <span className="text-[10px] text-slate-600">checked {fmtDate(integration.checked_at)}</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-slate-400">{integration.detail}</p>
              {Object.keys(integration.meta).length > 0 ? (
                <details className="mt-3">
                  <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-500">Integration metadata</summary>
                  <pre className="mt-2 max-h-40 overflow-auto rounded-lg border border-slate-800 bg-slate-950/70 p-2 text-[10px] leading-5 text-slate-500">
                    {JSON.stringify(integration.meta, null, 2)}
                  </pre>
                </details>
              ) : null}
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_1.4fr]">
        <Card className="p-5">
          <SectionTitle title="Safety contract" hint="Enforced in the workflow and execution guard, not by the language model." />
          <ul className="space-y-3 text-xs leading-5 text-slate-400">
            <li className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
              <span className="font-semibold text-slate-200">No paid execution without approval.</span> The guard queries the persisted approval and revalidates budget, runtime, kill switch, and capability.
            </li>
            <li className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
              <span className="font-semibold text-slate-200">Every metric has provenance.</span> Values without evidence are returned as unavailable, never as zero.
            </li>
            <li className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
              <span className="font-semibold text-slate-200">Model output is untrusted.</span> Gemma output is schema-validated and cannot change constraints or the selected candidate.
            </li>
            <li className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
              <span className="font-semibold text-slate-200">Only WATTSON-tagged resources are touched.</span> Launches carry an idempotency key and deterministic naming; cleanup is restricted to owned instances.
            </li>
            <li className="rounded-xl border border-slate-800/70 bg-slate-950/30 px-3 py-2">
              <span className="font-semibold text-slate-200">Regressions are reported honestly.</span> A worse result produces a regressed verdict, not a rewritten narrative.
            </li>
          </ul>
        </Card>

        <Card className="p-5">
          <SectionTitle
            title="How to read this demo"
            hint="What is real and what is simulated in the default configuration."
            right={<Pill tone="violet">simulator</Pill>}
          />
          <div className="space-y-3 text-xs leading-5 text-slate-400">
            <p>
              The default demo uses the deterministic provider simulator and seeded baselines. All workload, baseline, candidate, and result metrics are labelled <span className="text-fuchsia-300">simulated</span>.
            </p>
            <p>
              Temporal execution, approval persistence, kill-switch enforcement, the audit ledger, idempotency, report generation, and the dashboard are real software paths exercised by the demo.
            </p>
            <p>
              No live cloud instance is created and no paid API is called in simulator mode. A JarvisLabs adapter exists for a configured, explicitly approved run; it is not exercised by automated tests.
            </p>
            <p className="text-slate-500">
              The AI analysis in this demo uses a deterministic fallback unless a hosted Gemma key or local Ollama model is configured.
            </p>
          </div>
        </Card>
      </div>

      <section id="audit" className="scroll-mt-6">
        <SectionTitle
          title="Audit trail"
          hint="Append-only event ledger. The latest 100 events are shown. Payloads are included for reproducibility."
          right={<span className="text-[10px] uppercase tracking-wider text-slate-500">{audit.total} events total</span>}
        />
        {audit.items.length === 0 ? (
          <EmptyState title="No audit events" body="Events appear when a workload is seeded, a proposal is created, a decision is recorded, or a workflow changes stage." />
        ) : (
          <Card className="overflow-hidden">
            <div className="table-shell border-0">
              <table className="data-table min-w-[900px]">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>References</th>
                    <th>Payload</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.items.map((event) => (
                    <tr key={event.id}>
                      <td>
                        <p className="font-mono text-[10px] text-sky-300">{event.event_type}</p>
                        <p className="mt-1 text-xs text-slate-300">{event.message}</p>
                      </td>
                      <td className="text-xs text-slate-400">{event.actor}</td>
                      <td className="text-[10px] text-slate-500">
                        {event.proposal_id ? <p className="break-all">proposal: {event.proposal_id.slice(0, 12)}</p> : null}
                        {event.workflow_id ? <p className="break-all">workflow: {event.workflow_id.slice(0, 18)}</p> : null}
                      </td>
                      <td className="max-w-[320px]">
                        <p className="break-words font-mono text-[10px] leading-5 text-slate-500">{payloadPreview(event.payload)}</p>
                      </td>
                      <td className="whitespace-nowrap text-[10px] text-slate-500">{fmtDate(event.created_at)}</td>
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
