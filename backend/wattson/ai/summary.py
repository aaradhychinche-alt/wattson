"""Deterministic report narrative used when Gemma is unavailable."""

from __future__ import annotations

from typing import Any

from .schemas import AnalysisPayload


def fallback_summary(report: dict[str, Any]) -> str:
    verdict = report.get("verdict", "inconclusive")
    change = report.get("overall_change_pct")
    change_text = "unavailable" if change is None else f"{change:+.2f}%"
    lines = [
        f"Verified result: {verdict}. Weighted overall change: {change_text}.",
    ]
    metrics = report.get("summary", {}).get("metrics", {})
    for metric, node in metrics.items():
        if not isinstance(node, dict):
            continue
        before = node.get("baseline")
        after = node.get("result")
        pct = node.get("change_pct")
        provenance = node.get("result_provenance", "unavailable")
        if before is None or after is None:
            lines.append(f"{metric}: unavailable (baseline or result missing).")
        else:
            pct_text = "unavailable" if pct is None else f"{pct:+.2f}%"
            lines.append(
                f"{metric}: {before} -> {after} ({pct_text}), result provenance {provenance}."
            )
    lines.append(
        "All simulator values are labelled simulated; no real cloud benchmark was run. "
        "A single simulated observation provides no statistical confidence interval."
    )
    return " ".join(lines)


def render_gemma_summary(payload: AnalysisPayload) -> str:
    """Only used if a future provider returns a summary payload; never fabricated."""
    facts = " ".join(item.statement for item in payload.observed_facts)
    return facts[:1200]
