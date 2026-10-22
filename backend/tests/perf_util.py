"""Helpers for the performance-budget tests (docs/performance.md).

Timing tests are flaky by nature (this laptop also runs a browser and an editor), so: one warm-up call, then the BEST of several
repeats (the least disturbed run); a budget test keeps re-measuring, up to MAX_ATTEMPTS, until the budget is reached, so only
SUSTAINED slowness fails it; budgets sit 3x or more below the worst speed measured; and two switches for other machines:
NEUROROUTE_PERF_SCALE multiplies every budget (0.5 on a slower machine) and NEUROROUTE_SKIP_PERF=1 skips them.
"""
import os
import time
from collections.abc import Callable

import pytest

skip_perf = pytest.mark.skipif(os.environ.get("NEUROROUTE_SKIP_PERF") == "1", reason="NEUROROUTE_SKIP_PERF=1")


def budget(steps_per_second: float) -> float:
    return steps_per_second * float(os.environ.get("NEUROROUTE_PERF_SCALE", "1"))


MAX_ATTEMPTS = 20


def best_rate(run: Callable[[], object], steps: int, repeats: int = 5, target: float | None = None) -> float:
    """Highest steps per second over `repeats` runs of `run` (which must perform exactly `steps` steps).

    With `target`, keeps measuring (up to MAX_ATTEMPTS runs) until the best rate reaches it: a transient CPU spike cannot fail a budget.
    """
    run()
    best = 0.0
    for _ in range(MAX_ATTEMPTS if target is not None else repeats):
        t0 = time.perf_counter()
        run()
        best = max(best, steps / (time.perf_counter() - t0))
        if target is not None and best >= target:
            break
    return best
