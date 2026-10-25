"""Provider selection. Only the simulator is constructed by default."""

from __future__ import annotations

from ..config import get_settings
from .base import ProviderAdapter
from .jarvislabs import JarvisLabsProvider
from .simulator import SimulatorProvider

_simulator: SimulatorProvider | None = None


def get_provider() -> ProviderAdapter:
    global _simulator
    if get_settings().wattson_provider == "jarvislabs":
        return JarvisLabsProvider()
    if _simulator is None:
        _simulator = SimulatorProvider()
    return _simulator
