"""Verdict, missing-data, and provenance tests for evidence reports."""

from __future__ import annotations

from datetime import UTC, datetime

from wattson.db import utcnow
from wattson.models import Measurement, OptimizationProposal, Run
from wattson.provenance import pct_change
from wattson.services.reports import build_report_payload

WEIGHTS = {
    "cost_usd": 0.35,
    "energy_kwh": 0.25,
    "latency_ms": 0.25,
    "throughput_samples_s": 0.15,
}


def make_run(metrics: dict[str, float | None], provenance: str = "simulated") -> Run:
    run = Run(
        id="run-" + provenance,
        workload_id="w",
        kind="optimization",
        status="completed",
        config={},
        provider="simulator",
        started_at=datetime(2026, 10, 25, 8, 0, tzinfo=UTC),
        completed_at=datetime(2026, 10, 25, 9, 0, tzinfo=UTC),
    )
    run.measurements = [
        Measurement(
            run_id=run.id,
            metric=metric,
            value=value,
            unit={
                "cost_usd": "USD",
                "energy_kwh": "kWh",
                "latency_ms": "ms",
                "throughput_samples_s": "samples/s",
            }[metric],
            measured_at=utcnow(),
            source="wattson-simulator/v1",
            provenance=provenance,
        )
        for metric, value in metrics.items()
    ]
    return run


def make_proposal() -> OptimizationProposal:
    return OptimizationProposal(
        id="p1",
        workload_id="w",
        status="executing",
        weights=WEIGHTS,
        normalization="min_max_across_eligible_candidates",
        selected_candidate_id="cand-1",
    )


def test_pct_change_direction_and_unavailable() -> None:
    assert pct_change(10, 5, lower_is_better=True) == 50.0
    assert pct_change(10, 20, lower_is_better=True) == -100.0
    assert pct_change(100, 200, lower_is_better=False) == 100.0
    assert pct_change(None, 200, lower_is_better=False) is None
    assert pct_change(0, 200, lower_is_better=False) is None


def test_improved_report_carries_provenance_for_every_metric() -> None:
    baseline = make_run(
        {
            "cost_usd": 1.0,
            "energy_kwh": 0.2,
            "latency_ms": 1.0,
            "throughput_samples_s": 100.0,
        }
    )
    result = make_run(
        {
            "cost_usd": 0.5,
            "energy_kwh": 0.1,
            "latency_ms": 0.5,
            "throughput_samples_s": 200.0,
        }
    )
    payload = build_report_payload(make_proposal(), baseline, result)
    assert payload["verdict"] == "improved"
    assert payload["completeness"]["ratio"] == 1.0
    assert payload["simulated"] is True
    for _metric, node in payload["summary"]["metrics"].items():
        assert node["unit"]
        assert node["baseline_provenance"] == "simulated"
        assert node["result_provenance"] == "simulated"
        assert node["baseline_source"]
        assert node["baseline_measured_at"]
        assert node["result_measured_at"]
        assert node["change_pct"] is not None


def test_missing_metric_is_unavailable_not_zero() -> None:
    baseline = make_run({"cost_usd": 1.0, "energy_kwh": 0.2, "latency_ms": 1.0})
    result = make_run({"cost_usd": 0.5, "energy_kwh": 0.1, "latency_ms": 0.5})
    payload = build_report_payload(make_proposal(), baseline, result)
    throughput = payload["summary"]["metrics"]["throughput_samples_s"]
    assert payload["verdict"] == "inconclusive"
    assert throughput["baseline"] is None
    assert throughput["result"] is None
    assert throughput["baseline_available"] is False
    assert "throughput_samples_s" in payload["completeness"]["missing"]


def test_regression_is_reported_honestly() -> None:
    baseline = make_run(
        {
            "cost_usd": 1.0,
            "energy_kwh": 0.2,
            "latency_ms": 1.0,
            "throughput_samples_s": 100.0,
        }
    )
    result = make_run(
        {
            "cost_usd": 1.2,
            "energy_kwh": 0.25,
            "latency_ms": 3.0,
            "throughput_samples_s": 40.0,
        }
    )
    payload = build_report_payload(make_proposal(), baseline, result)
    assert payload["verdict"] == "regressed"
    assert payload["overall_change_pct"] < 0
    assert set(payload["regressions"]) == {
        "cost_usd",
        "energy_kwh",
        "latency_ms",
        "throughput_samples_s",
    }


def test_mixed_tradeoff_is_not_called_improved() -> None:
    baseline = make_run(
        {
            "cost_usd": 1.0,
            "energy_kwh": 1.0,
            "latency_ms": 1.0,
            "throughput_samples_s": 100.0,
        }
    )
    result = make_run(
        {
            "cost_usd": 0.5,
            "energy_kwh": 1.0,
            "latency_ms": 2.0,
            "throughput_samples_s": 200.0,
        }
    )
    payload = build_report_payload(make_proposal(), baseline, result)
    assert payload["verdict"] == "mixed"
    assert "latency_ms" in payload["regressions"]


def test_measured_report_does_not_claim_simulator_uncertainty() -> None:
    baseline = make_run({"cost_usd": 1.0}, provenance="measured")
    result = make_run({"cost_usd": 0.5}, provenance="measured")
    payload = build_report_payload(make_proposal(), baseline, result)
    assert payload["simulated"] is False
    assert "Simulator results" not in payload["uncertainty"]
