"""JarvisLabs adapter using the documented `jarvislabs` SDK (0.2.x).

Verified against https://docs.jarvislabs.ai/sdk/ on 2026-10-25:
  - Client(api_key=...), client.instances.list/create/get/pause/destroy
  - create(gpu_type, num_gpus, template, storage, name) is documented
  - supported GPUs: A30, L4, A100, A100-80GB, H100, H200, RTX-PRO6000

The SDK has no documented arbitrary job-execution call. WATTSON therefore never
invents one: provisioning and cleanup are implemented, while measured workload
collection is explicitly unsupported. The UI reports the adapter as unverified
without a live credential.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from ..config import get_settings
from .base import (
    CollectedMetrics,
    PermanentProviderError,
    ProviderAdapter,
    ProviderCapabilityError,
    ProvisionedInstance,
    ProvisionRequest,
)

JARVISLABS_GPUS = ("A30", "L4", "A100", "A100-80GB", "H100", "H200", "RTX-PRO6000")
WATTSON_PREFIX = "wattson-"


def _instance_name(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"{WATTSON_PREFIX}{digest}"  # 20 chars, documented max is 40


class JarvisLabsProvider(ProviderAdapter):
    name = "jarvislabs"
    provenance = "measured"

    def __init__(self) -> None:
        self._settings = get_settings()

    def _client(self) -> Any:
        if not self._settings.jl_api_key:
            raise PermanentProviderError("JL_API_KEY is not configured")
        try:
            from jarvislabs import Client
        except ImportError as exc:
            raise PermanentProviderError(
                "jarvislabs SDK is not installed (uv sync --extra jarvis)"
            ) from exc
        return Client(api_key=self._settings.jl_api_key)

    def status(self) -> dict[str, Any]:
        if not self._settings.jl_api_key:
            return {
                "integration": "provider",
                "status": "disconnected",
                "detail": "JL_API_KEY is not set. No JarvisLabs calls are made.",
                "provenance": "measured",
                "provider": self.name,
            }
        try:
            import jarvislabs  # noqa: F401
        except ImportError:
            return {
                "integration": "provider",
                "status": "error",
                "detail": "jarvislabs SDK not installed; run uv sync --extra jarvis.",
                "provenance": "measured",
                "provider": self.name,
            }
        return {
            "integration": "provider",
            "status": "connected",
            "detail": "Credential present. Live API contract not verified in this build.",
            "provenance": "measured",
            "provider": self.name,
            "verification": "unverified_without_live_credential",
        }

    def supports(self, gpu_type: str) -> bool:
        return gpu_type in JARVISLABS_GPUS

    def provision(self, request: ProvisionRequest) -> ProvisionedInstance:
        if not self.supports(request.config.gpu_type):
            raise ProviderCapabilityError(
                f"JarvisLabs docs do not list GPU type {request.config.gpu_type}"
            )
        name = _instance_name(request.idempotency_key)
        with self._client() as client:
            for instance in client.instances.list():
                if getattr(instance, "name", None) == name:
                    return self._from_sdk(instance, request.idempotency_key)
            instance = client.instances.create(
                gpu_type=request.config.gpu_type,
                num_gpus=request.config.gpu_count,
                template="pytorch",
                storage=100,
                name=name,
            )
            return self._from_sdk(instance, request.idempotency_key)

    def _from_sdk(self, instance: Any, key: str) -> ProvisionedInstance:
        return ProvisionedInstance(
            instance_id=str(getattr(instance, "machine_id", "")),
            provider=self.name,
            status=str(getattr(instance, "status", "unknown")),
            idempotency_key=key,
            hourly_usd=None,
            created_at=datetime.now(UTC),
            detail=f"JarvisLabs instance {getattr(instance, 'name', '')}",
            meta={
                "tags": {"wattson:managed": "true"},
                "name": getattr(instance, "name", ""),
                "region": str(getattr(instance, "region", "")),
            },
        )

    def collect(self, instance: ProvisionedInstance, request: ProvisionRequest) -> CollectedMetrics:
        raise ProviderCapabilityError(
            "JarvisLabs workload execution/measurement is not implemented: the documented "
            "SDK has no verified arbitrary job-run + metrics API. WATTSON refuses to "
            "fabricate measured values."
        )

    def cleanup(self, instance: ProvisionedInstance) -> bool:
        if not str(instance.meta.get("name", "")).startswith(WATTSON_PREFIX):
            raise ValueError("refusing to clean a JarvisLabs instance without a wattson- name")
        with self._client() as client:
            try:
                client.instances.destroy(int(instance.instance_id))
            except Exception as exc:  # SDK NotFoundError is not imported eagerly
                if "not found" in str(exc).lower():
                    return True
                raise
        return True
