"""Deterministic, evidence-bound narration for local simulated research runs."""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

__all__ = ["summarize_research"]

_METRICS = {
    "mean_delay_ms": ("mean delay", "ms"),
    "loss_probability": ("loss probability", "percentage points"),
    "throughput_mbps": ("throughput", "Mbps"),
}


def summarize_research(candidate: Mapping[str, object], baseline: Mapping[str, object] | None = None) -> dict[str, list[str]]:
    """Report only paired, finite recorded values; never infer a quality claim."""
    baseline = baseline or {}
    observations: list[str] = []
    for key, (label, unit) in _METRICS.items():
        candidate_value, baseline_value = _number(candidate.get(key)), _number(baseline.get(key))
        if candidate_value is None or baseline_value is None:
            continue
        if key == "loss_probability":
            candidate_value, baseline_value = candidate_value * 100, baseline_value * 100
        delta = candidate_value - baseline_value
        observations.append(
            f"Recorded {label}: candidate {candidate_value:.3f} {unit}; baseline {baseline_value:.3f} {unit}; "
            f"delta {delta:+.3f} {unit}."
        )

    limitations = ["Simulated result only; it is not a network measurement."]
    if not observations:
        limitations.append("No paired baseline outcome metrics were recorded, so no comparative claim is made.")
    candidate_samples, baseline_samples = _positive_int(candidate.get("sample_count")), _positive_int(baseline.get("sample_count"))
    if candidate_samples is None or baseline_samples is None:
        limitations.append("Sample counts and confidence intervals were not recorded; uncertainty cannot be quantified.")
    else:
        limitations.append(
            f"Uncertainty: {candidate_samples} candidate and {baseline_samples} baseline samples; no confidence interval was recorded."
        )
    return {"observations": observations, "limitations": limitations}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
