"""Strict, untrusted-output-safe Gemma schemas and policy checks."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_LOGS_CHARS = 6000
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
ALLOWED_TWEAK_FIELDS = {"batch_size", "precision", "checkpointing"}
INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(all\s+)?(previous|above)\s+instructions|system\s+prompt|"
    r"you\s+are\s+now|disregard\s+the\s+above|set\s+gpu|rm\s+-rf|"
    r"execute\s+command|curl\s+http|<script)",
    re.IGNORECASE,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObservedFact(StrictModel):
    type: Literal["observed"] = "observed"
    statement: str = Field(min_length=1, max_length=500)
    evidence: str = Field(default="", max_length=500)


class Hypothesis(StrictModel):
    type: Literal["hypothesis"] = "hypothesis"
    statement: str = Field(min_length=1, max_length=500)
    rationale: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MissingInfo(StrictModel):
    type: Literal["missing_info"] = "missing_info"
    item: str = Field(min_length=1, max_length=300)
    why_it_matters: str = Field(default="", max_length=300)


class ProposedTweak(StrictModel):
    type: Literal["proposed_tweak"] = "proposed_tweak"
    field: Literal["batch_size", "precision", "checkpointing"]
    value: int | str | bool
    rationale: str = Field(default="", max_length=500)


class AnalysisPayload(StrictModel):
    observed_facts: list[ObservedFact] = Field(default_factory=list, min_length=1, max_length=12)
    hypotheses: list[Hypothesis] = Field(default_factory=list, min_length=1, max_length=12)
    missing_info: list[MissingInfo] = Field(default_factory=list, min_length=1, max_length=12)
    proposed_tweak: ProposedTweak | None = None

    @field_validator("observed_facts", "hypotheses", "missing_info")
    @classmethod
    def _nonempty(cls, value: list[object]) -> list[object]:
        if not value:
            raise ValueError("the model must provide at least one item in each list")
        return value

    @model_validator(mode="after")
    def _all_lists_present(self) -> AnalysisPayload:
        for name in ("observed_facts", "hypotheses", "missing_info"):
            if not getattr(self, name):
                raise ValueError(f"the model must provide at least one {name} item")
        return self


class NarrativePayload(StrictModel):
    summary: str = Field(min_length=1, max_length=1500)


class AnalysisEnvelope(StrictModel):
    source: Literal["gemma", "deterministic_fallback"]
    provider: str
    model: str = ""
    payload: AnalysisPayload
    fallback_reason: str | None = None
    input_flags: list[str] = Field(default_factory=list)


class PolicyError(ValueError):
    pass


def validate_tweak(tweak: ProposedTweak | None) -> ProposedTweak | None:
    """Policy gate. The model may only suggest bounded workload knobs."""
    if tweak is None:
        return None
    if tweak.field not in ALLOWED_TWEAK_FIELDS:
        raise PolicyError(f"tweak field {tweak.field!r} is not allowed")
    if tweak.field == "batch_size":
        if not isinstance(tweak.value, int) or isinstance(tweak.value, bool):
            raise PolicyError("batch_size tweak must be an integer")
        if tweak.value not in {16, 32, 64, 128}:
            raise PolicyError("batch_size tweak must be one of 16, 32, 64, 128")
    elif tweak.field == "precision":
        if tweak.value not in {"fp16", "bf16", "int8"}:
            raise PolicyError("precision tweak must be fp16, bf16 or int8")
    elif tweak.field == "checkpointing":
        if not isinstance(tweak.value, bool):
            raise PolicyError("checkpointing tweak must be boolean")
    return tweak


def sanitize_untrusted_text(text: str, limit: int = MAX_LOGS_CHARS) -> tuple[str, list[str]]:
    """Bound and neutralize untrusted log text. Never execute or follow it."""
    if not isinstance(text, str):
        return "", ["non_text_input"]
    flags: list[str] = []
    cleaned_lines: list[str] = []
    for line in text.splitlines()[:200]:
        line = "".join(ch for ch in line if ch == "\t" or ch.isprintable())
        line = line[:500]
        if INJECTION_PATTERNS.search(line):
            flags.append("instruction_like_text_ignored")
            cleaned_lines.append("[redacted: instruction-like untrusted text ignored]")
        else:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)[:limit]
    return cleaned, sorted(set(flags))


def validate_screenshot(
    data: bytes | None, mime: str | None = None
) -> tuple[bytes | None, str | None]:
    if data is None:
        return None, None
    if len(data) > MAX_SCREENSHOT_BYTES:
        raise PolicyError("screenshot exceeds 2 MiB limit")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    raise PolicyError("screenshot must be PNG or JPEG (magic-byte checked)")
