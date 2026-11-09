"""Deciding when the chamber has equilibrated.

Criterion: fit a straight line to the jar RH over the last `window_s` seconds;
the RH is settled when that line changes by less than `rh_tol` across the whole
window. Same for the jar temperature with `t_tol`. Any missing value in the
window means "not stable", and so does having less than one window of history.

A fitted trend is used instead of max-minus-min because sensor noise alone
(about +-0.1 %RH on an SHT30) can make the peak-to-peak spread exceed a tight
tolerance even when nothing is drifting.

This is kept separate from any polling so it can be used two ways:
- scripts: Chamber.wait_until_stable() polls and feeds a StabilityMonitor;
- the suite: its own 1 Hz worker feeds a StabilityMonitor with every reading
  it already takes, and checks .stable whenever it wants.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable

from .reading import Reading


def drift(times: list[float], values: list[float]) -> float:
    """Change of the least-squares straight line across the time span."""
    n = len(times)
    if n < 2:
        return 0.0
    mt = sum(times) / n
    mv = sum(values) / n
    sxx = sum((t - mt) ** 2 for t in times)
    if sxx == 0:
        return 0.0
    slope = sum((t - mt) * (v - mv) for t, v in zip(times, values)) / sxx
    return abs(slope * (times[-1] - times[0]))


def is_stable(readings: Iterable[Reading], window_s: float, rh_tol: float, t_tol: float) -> bool:
    """True if the readings cover at least window_s and the drift is within tolerance."""
    readings = list(readings)
    if not readings:
        return False
    latest = readings[-1].time
    if latest - readings[0].time < window_s:
        return False  # not enough history yet
    recent = [r for r in readings if r.time >= latest - window_s]
    times = [r.time for r in recent]
    rh = [r.rh for r in recent]
    t = [r.t_jar for r in recent]
    if any(math.isnan(v) for v in rh + t):
        return False
    return drift(times, rh) <= rh_tol and drift(times, t) <= t_tol


class StabilityMonitor:
    """Keeps a rolling window of readings and reports whether they are stable."""

    def __init__(self, window_s: float = 600.0, rh_tol: float = 0.5, t_tol: float = 0.1):
        self.window_s = window_s
        self.rh_tol = rh_tol
        self.t_tol = t_tol
        self._buf: deque[Reading] = deque()

    def add(self, reading: Reading) -> None:
        self._buf.append(reading)
        # Keep slightly more than one window so is_stable() can see full coverage.
        while self._buf and reading.time - self._buf[0].time > self.window_s * 1.5:
            self._buf.popleft()

    def reset(self) -> None:
        """Forget history, e.g. after changing the salt or the setpoint."""
        self._buf.clear()

    @property
    def stable(self) -> bool:
        return is_stable(self._buf, self.window_s, self.rh_tol, self.t_tol)
