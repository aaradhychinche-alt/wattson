"""Report construction with honest regression handling and data completeness."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.provider import (
    fallback_analysis,  # noqa: F401  (ensures AI package loads)
    summarize_verified_result,
)
from ..ai.summary import fallback_summary
from ..config import get_settings
from ..models import Measurement, OptimizationProposal, Report, Run
from ..provenance import LOWER_IS_BETTER, METRIC_UNITS, pct_change

METRIC_ORDER = ["cost_usd", "energy_kwh", "latency_ms", "throughput_samples_s"]


def _metric_map(run: Run | None) -> dict[str, Measurement]:
    if run is None:
        return {}
    return {m.metric: m for m in run.measurements}


def build_report_payload(
    proposal: OptimizationProposal, baseline: Run, result: Run
) -> dict[str, Any]:
    base = _metric_map(baseline)
    after = _metric_map(result)
    metrics: dict[str, Any] = {}
    weighted = 0.0
    weight_used = 0.0
    available = 0
    regressions: list[str] = []
    weights = proposal.weights or {}

    for metric in METRIC_ORDER:
        bm = base.get(metric)
        rm = after.get(metric)
        bval = bm.value if bm and bm.value is not None else None
        rval = rm.value if rm and rm.value is not None else None
        change = pct_change(bval, rval, metric in LOWER_IS_BETTER)
        weight = float(weights.get(metric, 0.0))
        if change is not None:
            available += 1
            weighted += weight * change
            weight_used += weight
            if change < -5.0:
                regressions.append(metric)
        metrics[metric] = {
            "baseline": bval,
            "result": rval,
            "change_pct": change,
            "unit": METRIC_UNITS.get(metric, (rm.unit if rm else "")),
            "baseline_provenance": bm.provenance if bm else "unavailable",
            "result_provenance": rm.provenance if rm else "unavailable",
            "baseline_available": bval is not None,
            "result_available": rval is not None,
            "baseline_source": bm.source if bm else "",
            "result_source": rm.source if rm else "",
            "baseline_measured_at": bm.measured_at.isoformat() if bm else None,
            "result_measured_at": rm.measured_at.isoformat() if rm else None,
        }

    overall = round(weighted / weight_used, 3) if weight_used else None
    if available < len(METRIC_ORDER) or overall is None or abs(overall) < 1.0:
        verdict = "inconclusive"
    elif overall < 0:
        verdict = "regressed"
    elif regressions:
        verdict = "mixed"
    else:
        verdict = "improved"

    completeness = {
        "available_metrics": available,
        "total_metrics": len(METRIC_ORDER),
        "ratio": round(available / len(METRIC_ORDER), 3),
        "missing": [
            metric
            for metric, node in metrics.items()
            if not node["baseline_available"] or not node["result_available"]
        ],
    }
    window = {
        "baseline_started_at": baseline.started_at.isoformat()
        if isinstance(baseline.started_at, datetime)
        else None,
        "baseline_completed_at": baseline.completed_at.isoformat()
        if baseline.completed_at
        else None,
        "result_started_at": result.started_at.isoformat() if result.started_at else None,
        "result_completed_at": result.completed_at.isoformat() if result.completed_at else None,
    }
    simulated = any(
        node["baseline_provenance"] == "simulated"
        or node["result_provenance"] == "simulated"
        for node in metrics.values()
    )
    uncertainty = (
        f"Single {'simulated ' if simulated else ''}observation per metric; no statistical "
        "confidence interval is available. Simulator results depend on illustrative assumptions "
        "in simulator_assumptions.yaml and are not vendor benchmarks."
        if simulated
        else "Single observation per metric; no statistical confidence interval is available."
    )
    return {
        "verdict": verdict,
        "overall_change_pct": overall,
        "summary": {
            "metrics": metrics,
            "weights": weights,
            "normalization": proposal.normalization,
            "selected_candidate_id": proposal.selected_candidate_id,
            "provider": result.provider,
            "result_run_id": result.id,
            "baseline_run_id": baseline.id,
        },
        "completeness": completeness,
        "measurement_window": window,
        "uncertainty": uncertainty,
        "regressions": regressions,
        "simulated": simulated,
    }


def persist_report(
    session: Session, proposal: OptimizationProposal, baseline: Run, result: Run
) -> Report:
    existing = session.scalar(select(Report).where(Report.proposal_id == proposal.id))
    if existing is not None:
        return existing
    payload = build_report_payload(proposal, baseline, result)
    narrative, narrative_source = summarize_verified_result(
        payload, fallback_summary(payload), settings=get_settings()
    )
    report = Report(
        proposal_id=proposal.id,
        baseline_run_id=baseline.id,
        result_run_id=result.id,
        verdict=payload["verdict"],
        overall_change_pct=payload["overall_change_pct"],
        summary=payload["summary"],
        narrative=narrative,
        narrative_source=narrative_source,
        uncertainty=payload["uncertainty"],
        completeness=payload["completeness"],
        measurement_window=payload["measurement_window"],
    )
    session.add(report)
    session.flush()
    return report
