"""Inactive (delta) region: stabilize combinational logic within a time step."""

from __future__ import annotations

from collections.abc import Callable

from hdl_sim.core.events import SimTime

ContinuousFn = Callable[[SimTime], bool]
CombFn = Callable[[], bool]


class DeltaRegion:
    """Re-evaluate combinational logic until nets stop changing."""

    MAX_ITERATIONS = 64

    def __init__(self) -> None:
        self._continuous: list[ContinuousFn] = []
        self._comb: list[CombFn] = []

    def add_continuous(self, callback: ContinuousFn) -> None:
        self._continuous.append(callback)

    def add_comb(self, callback: CombFn) -> None:
        self._comb.append(callback)

    def flush(self, time: SimTime) -> bool:
        """Run continuous and comb updates until stable. Returns True if anything changed."""

        any_changed = False
        for _ in range(self.MAX_ITERATIONS):
            changed = False
            for continuous in self._continuous:
                if continuous(time):
                    changed = True
            for comb in self._comb:
                if comb():
                    changed = True
            if not changed:
                break
            any_changed = True
        return any_changed
