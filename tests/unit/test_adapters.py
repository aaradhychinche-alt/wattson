"""Adapter contract tests with mocks only: no cloud call, no spend, no network."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from wattson.providers.base import (
    ProviderCapabilityError,
    ProvisionedInstance,
    ProvisionRequest,
    TransientProviderError,
)
from wattson.providers.jarvislabs import JarvisLabsProvider, _instance_name
from wattson.providers.kepler import KeplerClient
from wattson.providers.simulator import SimulatorProvider
from wattson.simulator_math import CandidateConfig

CONFIG = CandidateConfig(
    gpu_type="L4", gpu_count=1, batch_size=64, precision="int8", checkpointing=True
)


def request(key: str = "workflow-1:execute:launch", **kwargs: object) -> ProvisionRequest:
    return ProvisionRequest(
        proposal_id="proposal-1",
        workflow_id="workflow-1",
        idempotency_key=key,
        config=CONFIG,
        dataset_samples=10_000,
        runtime_hours=1.0,
        **kwargs,  # type: ignore[arg-type]
    )


def test_simulator_transient_retry_does_not_duplicate_launch() -> None:
    provider = SimulatorProvider()
    with pytest.raises(TransientProviderError):
        provider.provision(request(inject_transient_launch=True))
    instance = provider.provision(request(inject_transient_launch=True))
    assert instance.instance_id.endswith("execute:launch")
    assert provider.find_by_key("workflow-1:execute:launch") is instance
    assert instance.meta["tags"]["wattson:managed"] == "true"


def test_simulator_cleanup_is_idempotent() -> None:
    provider = SimulatorProvider()
    instance = provider.provision(request(key="cleanup-key"))
    assert provider.cleanup(instance) is True
    stopped = provider.find_by_key("cleanup-key")
    assert stopped is not None and stopped.status == "stopped"
    assert provider.cleanup(instance) is True


def test_simulator_collects_only_labelled_simulated_metrics() -> None:
    provider = SimulatorProvider()
    instance = provider.provision(request(key="collect-key"))
    collected = provider.collect(instance, request(key="collect-key"))
    assert collected.provenance == "simulated"
    assert collected.source.startswith("wattson-simulator/")
    assert collected.cost_usd > 0


class _FakeInstances:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.destroyed: list[int] = []
        self.listed: list[SimpleNamespace] = []

    def list(self) -> list[SimpleNamespace]:
        return self.listed

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.created.append(kwargs)
        instance = SimpleNamespace(
            machine_id=42, status="running", name=kwargs["name"], region="in-mumbai"
        )
        self.listed.append(instance)
        return instance

    def destroy(self, machine_id: int) -> None:
        self.destroyed.append(machine_id)


class _FakeClient:
    def __init__(self) -> None:
        self.instances = _FakeInstances()

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_jarvislabs_name_is_deterministic_and_prefixed() -> None:
    assert _instance_name("workflow-1:execute:launch") == _instance_name(
        "workflow-1:execute:launch"
    )
    assert _instance_name("workflow-1:execute:launch").startswith("wattson-")
    assert len(_instance_name("workflow-1:execute:launch")) <= 40


def test_jarvislabs_provision_reconciles_by_name_without_paid_call(monkeypatch) -> None:
    provider = JarvisLabsProvider()
    fake = _FakeClient()
    monkeypatch.setattr(provider, "_client", lambda: fake)
    first = provider.provision(request(key="jl-key"))
    second = provider.provision(request(key="jl-key"))
    assert first.instance_id == "42"
    assert second.instance_id == "42"
    assert len(fake.instances.created) == 1
    assert fake.instances.created[0]["name"] == _instance_name("jl-key")
    assert fake.instances.created[0]["gpu_type"] == "L4"


def test_jarvislabs_refuses_unsupported_gpu_and_cleanup_without_tag(monkeypatch) -> None:
    provider = JarvisLabsProvider()
    unsupported = request()
    unsupported = ProvisionRequest(
        proposal_id="p",
        workflow_id="w",
        idempotency_key="k",
        config=CandidateConfig(
            gpu_type="V100",
            gpu_count=1,
            batch_size=32,
            precision="fp16",
            checkpointing=True,
        ),
        dataset_samples=100,
        runtime_hours=1.0,
    )
    with pytest.raises(ProviderCapabilityError):
        provider.provision(unsupported)

    fake = _FakeClient()
    monkeypatch.setattr(provider, "_client", lambda: fake)
    foreign = ProvisionedInstance(
        instance_id="99",
        provider="jarvislabs",
        status="running",
        idempotency_key="foreign",
        hourly_usd=None,
        created_at=datetime.now(UTC),
        meta={"name": "someone-elses-instance"},
    )
    with pytest.raises(ValueError):
        provider.cleanup(foreign)
    assert fake.instances.destroyed == []


def test_jarvislabs_collect_refuses_to_fabricate_measurements() -> None:
    provider = JarvisLabsProvider()
    instance = ProvisionedInstance(
        instance_id="42",
        provider="jarvislabs",
        status="running",
        idempotency_key="jl-key",
        hourly_usd=None,
        created_at=datetime.now(UTC),
        meta={"name": _instance_name("jl-key")},
    )
    with pytest.raises(ProviderCapabilityError):
        provider.collect(instance, request(key="jl-key"))


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_kepler_reads_documented_counter_and_converts_to_kwh(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> _FakeResponse:
        captured.update({"url": url, "params": params, "timeout": timeout})
        return _FakeResponse({"data": {"result": [{"value": [0, "3600000"]}]}})

    monkeypatch.setattr("wattson.providers.kepler.httpx.get", fake_get)
    reading = KeplerClient("http://prometheus:9090", "wattson-pod").read_pod_energy(
        timedelta(minutes=5)
    )
    assert reading.energy_kwh == pytest.approx(1.0)
    assert reading.provenance == "measured"
    assert "kepler_pod_gpu_joules_total" in str(captured["params"])
    assert reading.window_end > reading.window_start


def test_kepler_reports_disconnected_without_url(monkeypatch) -> None:
    client = KeplerClient(url="", pod_label="")
    status = client.status()
    assert status["status"] == "disconnected"
    assert status["provenance"] == "simulated"


def test_kepler_raises_when_no_series(monkeypatch) -> None:
    def fake_get(url: str, *, params: dict[str, object], timeout: float) -> _FakeResponse:
        return _FakeResponse({"data": {"result": []}})

    monkeypatch.setattr("wattson.providers.kepler.httpx.get", fake_get)
    with pytest.raises(RuntimeError, match="no pod GPU energy"):
        KeplerClient("http://prometheus:9090", "wattson-pod").read_pod_energy()
