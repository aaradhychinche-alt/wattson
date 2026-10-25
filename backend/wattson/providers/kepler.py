"""Kepler energy reader (CNCF Kepler exposes Prometheus metrics).

Verified against https://sustainable-computing.io/kepler/design/metrics/ on
2026-10-25: counters `kepler_pod_gpu_joules_total` / `kepler_node_gpu_joules_total`
and gauges `kepler_node_gpu_watts`; Prometheus-compatible scraping.

Kepler is *not* installed by WATTSON. Without WATTSON_KEPLER_PROMETHEUS_URL this
adapter reports disconnected and the simulator labels energy as simulated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ..config import get_settings


@dataclass(frozen=True)
class EnergyReading:
    energy_kwh: float
    source: str
    provenance: str
    window_start: datetime
    window_end: datetime


class KeplerClient:
    name = "kepler"

    def __init__(self, url: str | None = None, pod_label: str | None = None) -> None:
        settings = get_settings()
        self.url = (url if url is not None else settings.wattson_kepler_prometheus_url).rstrip("/")
        self.pod_label = pod_label if pod_label is not None else settings.wattson_kepler_pod_label

    def status(self) -> dict[str, Any]:
        if not self.url:
            return {
                "integration": "kepler",
                "status": "disconnected",
                "detail": "WATTSON_KEPLER_PROMETHEUS_URL is not set. Energy is simulated.",
                "provenance": "simulated",
            }
        try:
            response = httpx.get(f"{self.url}/api/v1/status/config", timeout=3.0)
            response.raise_for_status()
        except Exception as exc:
            return {
                "integration": "kepler",
                "status": "error",
                "detail": f"Prometheus endpoint unreachable: {type(exc).__name__}",
                "provenance": "measured",
            }
        return {
            "integration": "kepler",
            "status": "connected",
            "detail": (
                "Prometheus-compatible endpoint reachable. Contract verified with mocks only."
            ),
            "provenance": "measured",
        }

    def read_pod_energy(self, window: timedelta = timedelta(minutes=5)) -> EnergyReading:
        if not self.url or not self.pod_label:
            raise RuntimeError("Kepler is not configured (URL and pod label are required)")
        end = datetime.now(UTC)
        start = end - window
        query = (
            f'sum(increase(kepler_pod_gpu_joules_total{{pod_name="{self.pod_label}"}}'
            f'[{int(window.total_seconds())}s]))'
        )
        response = httpx.get(
            f"{self.url}/api/v1/query",
            params={"query": query, "time": end.timestamp()},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("data", {}).get("result", [])
        if not results:
            raise RuntimeError("Kepler returned no pod GPU energy series")
        joules = float(results[0]["value"][1])
        return EnergyReading(
            energy_kwh=joules / 3_600_000.0,
            source=f"kepler kepler_pod_gpu_joules_total{{pod_name={self.pod_label}}}",
            provenance="measured",
            window_start=start,
            window_end=end,
        )
