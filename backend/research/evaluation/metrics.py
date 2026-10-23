"""Aligned, deterministic policy metrics for held-out simulator evaluations."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from research.baselines.runner import PolicyRun
from research.simulation.models import Scenario

__all__ = ["metrics_from_policy_run", "metrics_from_trace"]


def metrics_from_policy_run(run: PolicyRun, scenario: Scenario, flow_id: str) -> dict[str, float | None]:
    """Summarise one controlled flow; other flows remain matched background traffic."""
    index = run.flow_ids.index(flow_id)
    return metrics_from_trace(
        times_s=run.times_s,
        step_s=run.step_s,
        offered_mbps=run.flow_offered_mbps[:, index],
        delay_ms=run.flow_delay_ms[:, index],
        throughput_mbps=run.flow_throughput_mbps[:, index],
        switches=int(run.switches[index]),
        scenario=scenario,
    )


def metrics_from_trace(*, times_s: Sequence[float], step_s: float, offered_mbps: Sequence[float], delay_ms: Sequence[float],
                       throughput_mbps: Sequence[float], switches: int, scenario: Scenario) -> dict[str, float | None]:
    """Use finite delivered-packet delays and traffic-weighted loss; missing values remain explicit nulls."""
    times = np.asarray(times_s, dtype=np.float64)
    offered, delay, throughput = (np.asarray(values, dtype=np.float64) for values in (offered_mbps, delay_ms, throughput_mbps))
    if not (len(times) == len(offered) == len(delay) == len(throughput)):
        raise ValueError("trace arrays must have the same length")
    if step_s <= 0 or switches < 0:
        raise ValueError("step_s must be positive and switches non-negative")
    finite_delay = delay[np.isfinite(delay)]
    offered_total, delivered_total = float(offered.sum()), float(throughput.sum())
    recovery = _recovery_time(times, offered, throughput, scenario)
    return {
        "mean_delay_ms": _stat(finite_delay, np.mean), "p50_delay_ms": _stat(finite_delay, lambda values: np.percentile(values, 50)),
        "p95_delay_ms": _stat(finite_delay, lambda values: np.percentile(values, 95)), "p99_delay_ms": _stat(finite_delay, lambda values: np.percentile(values, 99)),
        "loss": None if offered_total == 0 else 1.0 - delivered_total / offered_total,
        "throughput_mbps": float(throughput.mean()) if throughput.size else None,
        "churn_per_min": float(switches) * 60.0 / (len(times) * step_s) if len(times) else None,
        "recovery_time_s": recovery,
    }


def _stat(values: np.ndarray, function) -> float | None:
    return float(function(values)) if values.size else None


def _recovery_time(times: np.ndarray, offered: np.ndarray, throughput: np.ndarray, scenario: Scenario) -> float | None:
    failures = [event.time_s for event in scenario.failures if event.action == "down"]
    recovered = []
    for failure_time in failures:
        eligible = np.flatnonzero((times >= failure_time) & (offered > 0) & (throughput > 0))
        if eligible.size:
            recovered.append(float(times[eligible[0]] - failure_time))
    return float(np.mean(recovered)) if recovered else None
