"""Simulation time management and event scheduling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from typing import TypeAlias

SimTime: TypeAlias = int
EventCallback: TypeAlias = Callable[[], None]
NBAFlushCallback: TypeAlias = Callable[[], None]


@dataclass(frozen=True, order=True, slots=True)
class ScheduledEvent:
    """A callback scheduled to run at a simulation timestamp."""

    time: SimTime
    sequence: int
    callback: EventCallback = field(compare=False)


class EventQueue:
    """Priority queue for deterministic event-driven simulation."""

    def __init__(self) -> None:
        self._now: SimTime = 0
        self._sequence = count()
        self._events: list[ScheduledEvent] = []
        self._nba_flush: NBAFlushCallback | None = None

    @property
    def now(self) -> SimTime:
        """Return the current simulation timestamp."""

        return self._now

    def __len__(self) -> int:
        return len(self._events)

    def set_nba_flush(self, callback: NBAFlushCallback | None) -> None:
        """Register a callback invoked after all active events at a time step."""

        self._nba_flush = callback

    def schedule(self, delay: SimTime, callback: EventCallback) -> ScheduledEvent:
        """Schedule ``callback`` after ``delay`` time units."""

        if delay < 0:
            msg = "delay must be non-negative"
            raise ValueError(msg)
        return self.schedule_at(self._now + delay, callback)

    def schedule_at(self, time: SimTime, callback: EventCallback) -> ScheduledEvent:
        """Schedule ``callback`` at an absolute simulation timestamp."""

        if time < self._now:
            msg = "cannot schedule an event in the past"
            raise ValueError(msg)

        event = ScheduledEvent(time=time, sequence=next(self._sequence), callback=callback)
        heappush(self._events, event)
        return event

    def step(self) -> bool:
        """Run the next scheduled event.

        Returns ``True`` when an event ran and ``False`` when the queue was
        empty.
        """

        if not self._events:
            return False

        event = heappop(self._events)
        self._now = event.time
        event.callback()
        return True

    def _run_time_step(self, time: SimTime) -> int:
        """Execute all active events scheduled for ``time``."""

        processed = 0
        while self._events and self._events[0].time == time:
            self.step()
            processed += 1
        return processed

    def run(self, *, until: SimTime | None = None, max_events: int | None = None) -> int:
        """Run scheduled events until the queue is empty or a limit is reached."""

        if until is not None and until < self._now:
            msg = "until must not be earlier than current simulation time"
            raise ValueError(msg)
        if max_events is not None and max_events < 0:
            msg = "max_events must be non-negative"
            raise ValueError(msg)

        processed = 0
        while self._events:
            next_time = self._events[0].time
            if until is not None and next_time > until:
                self._now = until
                break
            if max_events is not None and processed >= max_events:
                break

            processed += self._run_time_step(next_time)

            if max_events is not None and processed >= max_events:
                break

            if self._nba_flush is not None:
                self._nba_flush()

            if until is not None and next_time >= until:
                break

        return processed
