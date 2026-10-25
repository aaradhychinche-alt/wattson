"""One-command WATTSON demo.

The script drives the public API exactly like an operator would:
seed -> propose -> start workflow -> wait for approval -> approve -> verify.

It requires the API, worker, and Temporal dev server to be running. Use
scripts/demo.ps1 (Windows) or scripts/demo.sh (POSIX) for a single command that
starts the whole stack, or run `wattson-demo` against an existing stack.

Every simulated value is printed with its provenance. Scenario A must improve
and scenario B must regress; the demo exits non-zero if reality differs.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import httpx

from .config import get_settings
from .db import session_scope
from .services.demo_seed import seed_demo_workloads

SCENARIO_A = "Demo - Vision fine-tune"
SCENARIO_B = "Demo - Speech fine-tune (throttled I/O)"


class DemoError(RuntimeError):
    pass


class API:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def close(self) -> None:
        self.client.close()

    def get(self, path: str, **kwargs: Any) -> Any:
        response = self.client.get(path, **kwargs)
        if response.status_code >= 400:
            raise DemoError(f"GET {path} -> {response.status_code}: {response.text[:500]}")
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.client.post(path, json=payload)
        if response.status_code >= 400:
            raise DemoError(f"POST {path} -> {response.status_code}: {response.text[:500]}")
        return response.json()

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.client.patch(path, json=payload)
        if response.status_code >= 400:
            raise DemoError(f"PATCH {path} -> {response.status_code}: {response.text[:500]}")
        return response.json()


def wait_for_api(api: API, timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            return api.get("/api/health")
        except Exception as exc:  # noqa: BLE001 - demo startup retry
            last_error = type(exc).__name__
            time.sleep(1.0)
    raise DemoError(f"API did not become ready ({last_error})")


def wait_for_stage(
    api: API, workflow_id: str, wanted: set[str], timeout_seconds: int = 120
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = api.get(f"/api/workflows/{workflow_id}")
        stage = last.get("live_stage") or last.get("stage")
        if stage in wanted:
            return last
        if last.get("status") in {"failed", "cancelled", "needs_intervention"}:
            raise DemoError(
                f"Workflow ended as {last.get('status')} before reaching {sorted(wanted)}: "
                f"{last.get('last_error')}"
            )
        time.sleep(0.5)
    raise DemoError(
        f"Workflow {workflow_id} did not reach {sorted(wanted)}; last stage {last.get('stage')}"
    )


def wait_for_finish(api: API, workflow_id: str, timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = api.get(f"/api/workflows/{workflow_id}")
        if last.get("status") in {
            "completed",
            "failed",
            "cancelled",
            "rejected",
            "needs_intervention",
        }:
            return last
        time.sleep(0.5)
    raise DemoError(f"Workflow {workflow_id} did not finish; last stage {last.get('stage')}")


def find_workload(api: API, name: str) -> dict[str, Any]:
    page = api.get("/api/workloads", params={"limit": 200})
    for workload in page["items"]:
        if workload["name"] == name:
            return workload
    raise DemoError(f"demo workload {name!r} is missing")


def print_plan(proposal: dict[str, Any]) -> None:
    selected_id = proposal.get("selected_candidate_id")
    selected = next(
        (c for c in proposal["candidates"] if c["id"] == selected_id), None
    )
    eligible = sum(1 for c in proposal["candidates"] if c.get("eligible"))
    rejected = len(proposal["candidates"]) - eligible
    print(
        f"  candidates: {len(proposal['candidates'])} generated, {eligible} eligible, "
        f"{rejected} rejected by hard constraints"
    )
    if selected is None:
        print("  selected: none (no candidate satisfies the constraints)")
        return
    cfg = selected["config"]
    estimates = selected.get("estimates") or {}
    cost = estimates.get("cost_usd")
    budget = (proposal.get("constraints_snapshot") or {}).get("budget_usd")
    print(
        "  selected: "
        f"{cfg['gpu_count']}x {cfg['gpu_type']}, batch {cfg['batch_size']}, "
        f"{cfg['precision']}, checkpointing={cfg['checkpointing']}"
    )
    print(
        f"  predicted: ${cost:.3f} vs budget ${budget:.2f} "
        f"(provenance: {selected.get('provenance', 'predicted')})"
    )
    analysis = proposal.get("analysis") or {}
    print(
        f"  analysis: {analysis.get('source', 'unavailable')} "
        f"({analysis.get('provider', 'unavailable')})"
    )


def print_report(report: dict[str, Any]) -> None:
    print(f"  verdict: {report['verdict'].upper()}  overall {report['overall_change_pct']:+.2f}%")
    for metric, node in report["summary"]["metrics"].items():
        if node["baseline"] is None or node["result"] is None:
            print(f"  {metric:<24} unavailable (baseline or result missing)")
            continue
        print(
            f"  {metric:<24} {node['baseline']:.4f} -> {node['result']:.4f} "
            f"{node['unit']:<9} {node['change_pct']:+.2f}% "
            f"[{node['baseline_provenance']}->{node['result_provenance']}]"
        )
    print(
        f"  completeness: {report['completeness']['available_metrics']}/"
        f"{report['completeness']['total_metrics']} metrics"
    )
    print(f"  uncertainty: {report['uncertainty']}")
    print(f"  narrative ({report['narrative_source']}): {report['narrative']}")


def run_scenario(api: API, name: str, expected: str) -> bool:
    print()
    print("=" * 78)
    print(f"SCENARIO: {name}")
    print("=" * 78)
    workload = find_workload(api, name)
    print(f"  workload: {workload['id']}  provider={workload['provider']}")

    proposal = api.post(
        "/api/optimizations",
        {"workload_id": workload["id"], "objective": "balanced"},
    )
    print(f"  proposal: {proposal['id']}  status={proposal['status']}")
    print_plan(proposal)

    workflow = api.post("/api/workflows", {"proposal_id": proposal["id"]})
    workflow_id = workflow["workflow_id"]
    print(f"  workflow: {workflow_id}")
    wait_for_stage(api, workflow_id, {"awaiting_approval"})
    print("  stage: awaiting_approval (execution is blocked until a human decides)")

    approval = api.post(
        f"/api/optimizations/{proposal['id']}/approve",
        {"reason": "Demo operator approval after reviewing the simulated plan"},
    )
    print(f"  approval recorded: {approval['id']} decision={approval['decision']}")

    final = wait_for_finish(api, workflow_id)
    if final["status"] != "completed":
        raise DemoError(
            f"workflow finished as {final['status']}: {final.get('last_error')}"
        )
    report_id = final.get("report_id")
    if not report_id:
        raise DemoError("workflow completed without a report")
    report = api.get(f"/api/reports/{report_id}")

    audits = api.get("/api/audit", params={"proposal_id": proposal["id"], "limit": 200})
    launch_count = sum(
        1 for event in audits["items"] if event["event_type"] == "provider.launched"
    )
    retry_count = sum(
        1 for event in audits["items"] if event["event_type"] == "activity.retry"
    )
    cleanup_count = sum(
        1 for event in audits["items"] if event["event_type"] == "cleanup.completed"
    )
    print(f"  report: {report_id}")
    print_report(report)
    print(
        f"  evidence: provider launches={launch_count}, retries={retry_count}, "
        f"cleanup events={cleanup_count}"
    )

    ok = report["verdict"] == expected
    if not ok:
        print(
            f"  EXPECTATION FAILED: expected {expected}, measured {report['verdict']}. "
            "WATTSON reports the measured result instead of hiding it."
        )
    return ok


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the WATTSON end-to-end demo.")
    parser.add_argument(
        "--api-url",
        default=settings.wattson_api_url,
        help="WATTSON API base URL (default: WATTSON_API_URL)",
    )
    parser.add_argument(
        "--token",
        default=settings.wattson_api_token,
        help="Bearer token (default: WATTSON_API_TOKEN)",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Do not seed demo workloads into the shared database.",
    )
    args = parser.parse_args(argv)

    if not args.token:
        print("WATTSON_API_TOKEN is empty. Set it before running the demo.", file=sys.stderr)
        return 2

    api = API(args.api_url, args.token)
    try:
        health = wait_for_api(api)
        print("WATTSON - evidence-based AI cloud optimizer")
        print(f"API: {args.api_url}  status={health['status']}  version={health['version']}")
        for check in health["checks"]:
            print(
                f"  {check['name']:<10} {check['status']:<12} "
                f"[{check['provenance']}] {check['detail']}"
            )

        if not args.no_seed:
            with session_scope() as session:
                seed_demo_workloads(session)
            print("Seeded demo workloads and simulated baselines (provenance=simulated).")

        results = [
            run_scenario(api, SCENARIO_A, "improved"),
            run_scenario(api, SCENARIO_B, "regressed"),
        ]
    except DemoError as exc:
        print(f"\nDEMO FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        api.close()

    print()
    print("=" * 78)
    print("DEMO SUMMARY")
    print("=" * 78)
    print(f"  Scenario A -> {'improved (as expected)' if results[0] else 'unexpected outcome'}")
    print(
        f"  Scenario B -> {'regressed (reported honestly)' if results[1] else 'unexpected outcome'}"
    )
    print("  All metric values above are SIMULATED. No real cloud workload ran.")
    print("  Only WATTSON-tagged resources are cleaned up; no money was spent.")
    print("  Next steps: see README.md for the dashboard, API, and Gemma options.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
