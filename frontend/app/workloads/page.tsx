import Link from "next/link";

import { createProposalAction } from "@/app/actions";
import { Pill, ProvenanceBadge } from "@/components/badges";
import { EmptyState, Flash } from "@/components/feedback";
import { Card, PageHeader, SectionTitle, TerminalHeader } from "@/components/layout";
import { api } from "@/lib/api";
import { fmtDate, humanize } from "@/lib/format";
import { flashMessages, type SearchParams } from "@/lib/search";

export const dynamic = "force-dynamic";

function metaString(meta: Record<string, unknown>, key: string): string | null {
  const value = meta[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function metaNumber(meta: Record<string, unknown>, key: string): number | null {
  const value = meta[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export default async function WorkloadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const messages = flashMessages(params);
  const workloads = await api.workloads();
  const simulated = workloads.items.filter((item) => metaString(item.meta, "provenance") === "simulated").length;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="01_MEASURE"
        title="Workloads & Baselines"
        description="Every workload carries its current configuration, explicit constraints, and the provenance of its baseline evidence. Optimization starts from immutable records, never from heuristics."
        action={
          <Link
            href="/optimizations"
            className="btn btn-ghost px-4 py-2"
          >
            View Optimizer Plans &rarr;
          </Link>
        }
      />

      <Flash notice={messages.notice} error={messages.error} />

      {/* Overview Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Registered</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">{workloads.total}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Workloads with stored config</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Simulated Baselines</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-[#baa7ff]">{simulated}</p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Explicitly labelled, not physical runs</p>
        </Card>
        <Card className="p-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#a1a4a5]">Providers</p>
          <p className="mt-3 text-3xl font-normal tracking-tight text-white">
            {new Set(workloads.items.map((item) => item.provider)).size}
          </p>
          <p className="mt-1 font-mono text-[11px] text-[#6e727a]">Simulator & physical adapters</p>
        </Card>
      </div>

      {workloads.items.length === 0 ? (
        <EmptyState
          title="No workloads registered"
          body="Seed demo instances or register a workload via API to start the measurement loop."
        />
      ) : (
        <section className="space-y-6">
          <SectionTitle
            title="Workload Registry"
            hint="Creating a proposal snapshots these constraints so subsequent changes cannot invalidate the approved plan."
          />
          <div className="grid gap-6 xl:grid-cols-2">
            {workloads.items.map((workload) => {
              const provenance = metaString(workload.meta, "provenance") ?? "unavailable";
              const datasetSamples = metaNumber(workload.meta, "dataset_samples");
              const logs = metaString(workload.meta, "logs");
              const profile = metaString(workload.meta, "execution_profile");
              const constraints = workload.constraints;
              return (
                <Card key={workload.id} className="overflow-hidden">
                  <div className="border-b border-[#292d30] bg-[#000000] px-5 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-[#9281f7]">&gt;</span>
                          <h2 className="truncate text-base font-semibold text-white">{workload.name}</h2>
                        </div>
                        <p className="mt-1 font-mono text-xs text-[#a1a4a5]">
                          {humanize(workload.workload_type)} — {workload.provider} provider
                        </p>
                      </div>
                      <ProvenanceBadge provenance={provenance} />
                    </div>
                  </div>

                  <div className="space-y-4 px-5 py-5">
                    <p className="text-xs leading-relaxed text-[#a1a4a5]">
                      {workload.description || "No workload description recorded."}
                    </p>

                    <div className="flex flex-wrap gap-2">
                      <Pill tone="sky">{workload.current_config.gpu_count}x {workload.current_config.gpu_type}</Pill>
                      <Pill>batch {workload.current_config.batch_size}</Pill>
                      <Pill>{workload.current_config.precision}</Pill>
                      <Pill>{workload.current_config.checkpointing ? "checkpointing" : "no checkpointing"}</Pill>
                      {profile ? <Pill tone="iris">{humanize(profile)}</Pill> : null}
                    </div>

                    <dl className="grid grid-cols-2 gap-3 rounded-[6px] border border-[#292d30] bg-[#000000] p-3 font-mono text-xs sm:grid-cols-4">
                      <div>
                        <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Budget</dt>
                        <dd className="mt-1 text-white">
                          {constraints.budget_usd === undefined ? "Unavailable" : `$${constraints.budget_usd.toFixed(2)}`}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Max Runtime</dt>
                        <dd className="mt-1 text-white">
                          {constraints.max_runtime_hours === undefined ? "Unavailable" : `${constraints.max_runtime_hours} h`}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Deadline</dt>
                        <dd className="mt-1 text-white">{fmtDate(constraints.deadline_at)}</dd>
                      </div>
                      <div>
                        <dt className="text-[10px] uppercase tracking-wider text-[#6e727a]">Dataset</dt>
                        <dd className="mt-1 text-white">
                          {datasetSamples === null ? "Unavailable" : `${datasetSamples.toLocaleString("en-US")} samples`}
                        </dd>
                      </div>
                    </dl>

                    {constraints.allowed_gpu_types?.length ? (
                      <p className="font-mono text-xs text-[#6e727a]">
                        Allowed GPUs: <span className="text-[#f0f0f0]">{constraints.allowed_gpu_types.join(", ")}</span>
                      </p>
                    ) : null}

                    {logs ? (
                      <details className="group rounded-[6px] border border-[#292d30] bg-[#000000]">
                        <summary className="cursor-pointer list-none px-3 py-2 font-mono text-xs text-[#a1a4a5] hover:text-white transition-colors">
                          <span className="text-[#9281f7]">&gt;</span> Baseline Execution Logs
                          <span className="ml-2 font-normal text-[#6e727a]">(untrusted input, sandboxed)</span>
                        </summary>
                        <pre className="max-h-44 overflow-auto border-t border-[#292d30] bg-[#000000] px-3 py-2 font-mono text-[11px] leading-relaxed text-[#a1a4a5]">
                          {logs}
                        </pre>
                      </details>
                    ) : null}

                    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#292d30] pt-4">
                      <p className="font-mono text-[10px] text-[#6e727a]">Registered {fmtDate(workload.created_at)}</p>
                      <form action={createProposalAction}>
                        <input type="hidden" name="workloadId" value={workload.id} />
                        <button className="btn btn-ghost px-3 py-1.5" type="submit">
                          Create Optimizer Proposal &rarr;
                        </button>
                      </form>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
