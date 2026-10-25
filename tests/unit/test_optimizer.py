"""Deterministic optimizer and simulator-math tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from wattson.assumptions import load_assumptions
from wattson.optimizer import (
    ConstraintInput,
    PlanContext,
    generate_configs,
    plan_optimization,
    weights_for,
)
from wattson.simulator_math import CandidateConfig, CapabilityError, estimate

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
DEMO_CONSTRAINTS = ConstraintInput(
    budget_usd=1.25,
    max_runtime_hours=6.0,
    deadline_at=NOW + timedelta(hours=48),
    allowed_gpu_types=["L4", "A100", "H100"],
)


def plan():
    return plan_optimization(
        dataset_samples=2_500_000,
        constraints=DEMO_CONSTRAINTS,
        context=PlanContext(now=NOW),
        objective="balanced",
    )


def test_generates_all_24_candidates_once() -> None:
    configs = generate_configs(load_assumptions())
    assert len(configs) == 24
    assert len({(c.gpu_type, c.gpu_count, c.batch_size, c.precision) for c in configs}) == 24


def test_demo_plan_is_deterministic_and_budget_aware() -> None:
    first = plan()
    second = plan()

    assert first.selected_candidate_id == second.selected_candidate_id
    assert [c.id for c in first.candidates] == [c.id for c in second.candidates]
    assert len(first.candidates) == 24
    eligible = [c for c in first.candidates if c.eligible]
    assert len(eligible) == 13
    rejected = [c for c in first.candidates if not c.eligible]
    assert len(rejected) == 11
    assert all(
        any(f["code"] == "budget_exceeded" for f in c.constraint_failures) for c in rejected
    )

    selected = next(c for c in first.candidates if c.id == first.selected_candidate_id)
    assert selected.eligible is True
    assert selected.rank == 1
    assert selected.config.gpu_type == "L4"
    assert selected.config.gpu_count == 2
    assert selected.config.batch_size == 64
    assert selected.config.precision == "int8"
    assert selected.estimates is not None
    assert selected.estimates["cost_usd"] < 1.25

    assert all(c.score is not None for c in eligible)
    assert all(0.0 <= (c.score or 0.0) <= 1.0 for c in eligible)
    assert sorted(c.rank for c in eligible) == list(range(1, len(eligible) + 1))
    assert all(c.normalized is not None for c in eligible)


def test_objective_changes_weights_and_selection() -> None:
    cost_plan = plan_optimization(
        dataset_samples=2_500_000,
        constraints=DEMO_CONSTRAINTS,
        context=PlanContext(now=NOW),
        objective="lowest_cost",
    )
    assert cost_plan.weights == weights_for("lowest_cost")
    eligible = [c for c in cost_plan.candidates if c.eligible]
    cheapest = min(eligible, key=lambda c: c.estimates["cost_usd"])  # type: ignore[index]
    assert cost_plan.selected_candidate_id == cheapest.id


def test_hard_constraints_reject_everything() -> None:
    result = plan_optimization(
        dataset_samples=2_500_000,
        constraints=ConstraintInput(budget_usd=0.01, max_runtime_hours=0.1),
        context=PlanContext(now=NOW),
    )
    assert result.selected_candidate_id is None
    assert all(not candidate.eligible for candidate in result.candidates)
    codes = {failure["code"] for c in result.candidates for failure in c.constraint_failures}
    assert "budget_exceeded" in codes
    assert "runtime_exceeded" in codes


def test_disallowed_gpu_is_filtered_explicitly() -> None:
    result = plan_optimization(
        dataset_samples=1_000,
        constraints=ConstraintInput(allowed_gpu_types=["H100"]),
        context=PlanContext(now=NOW),
    )
    for candidate in result.candidates:
        if candidate.config.gpu_type != "H100":
            assert not candidate.eligible
            assert any(f["code"] == "gpu_not_allowed" for f in candidate.constraint_failures)


def test_past_deadline_is_a_hard_failure() -> None:
    result = plan_optimization(
        dataset_samples=2_500_000,
        constraints=ConstraintInput(deadline_at=NOW - timedelta(hours=1)),
        context=PlanContext(now=NOW),
    )
    assert result.selected_candidate_id is None
    assert all(
        any(f["code"] == "deadline_exceeded" for f in c.constraint_failures)
        for c in result.candidates
    )


def test_estimate_is_reproducible_and_profile_sensitive() -> None:
    assumptions = load_assumptions()
    config = CandidateConfig(
        gpu_type="L4", gpu_count=1, batch_size=64, precision="int8", checkpointing=True
    )
    nominal = estimate(config, 2_500_000, assumptions)
    again = estimate(config, 2_500_000, assumptions)
    throttled = estimate(config, 2_500_000, assumptions, profile="throttled_execution")

    assert nominal == again
    assert throttled.throughput_samples_s < nominal.throughput_samples_s
    assert throttled.latency_ms > nominal.latency_ms
    assert throttled.runtime_hours > nominal.runtime_hours


def test_jitter_is_bounded_and_deterministic() -> None:
    assumptions = load_assumptions()
    config = CandidateConfig(
        gpu_type="L4", gpu_count=1, batch_size=32, precision="fp16", checkpointing=True
    )
    first = estimate(config, 1_000_000, assumptions, jitter_key="run-a")
    second = estimate(config, 1_000_000, assumptions, jitter_key="run-a")
    other = estimate(config, 1_000_000, assumptions, jitter_key="run-b")
    baseline = estimate(config, 1_000_000, assumptions)

    assert first == second
    assert first != other
    assert abs(first.throughput_samples_s - baseline.throughput_samples_s) / (
        baseline.throughput_samples_s
    ) <= assumptions.jitter_fraction + 1e-6


def test_unknown_capabilities_fail_loudly() -> None:
    assumptions = load_assumptions()
    with pytest.raises(CapabilityError):
        estimate(
            CandidateConfig(
                gpu_type="V100", gpu_count=1, batch_size=32, precision="fp16", checkpointing=True
            ),
            100,
            assumptions,
        )
    with pytest.raises(CapabilityError):
        estimate(
            CandidateConfig(
                gpu_type="L4", gpu_count=1, batch_size=32, precision="int8", checkpointing=True
            ),
            100,
            assumptions,
            profile="does-not-exist",
        )
