"""Netlist signal storage for multi-bit values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from hdl_sim.core.events import SimTime
from hdl_sim.parser.ast import DeclKind, Range


NetObserver = Callable[["SimNet", int, int, SimTime], None]


@dataclass(slots=True)
class SimNet:
    """A simulation net with an integer value and explicit bit width."""

    name: str
    width: int
    kind: DeclKind
    value: int = 0
    previous: int | None = None
    _observers: list[NetObserver] = field(default_factory=list, repr=False)
    _mask: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width < 1:
            msg = "net width must be positive"
            raise ValueError(msg)
        object.__setattr__(self, "_mask", (1 << self.width) - 1)
        self.value &= self._mask

    @classmethod
    def from_declaration(cls, name: str, kind: DeclKind, value_range: Range | None) -> SimNet:
        width = value_range.width if value_range is not None else 1
        return cls(name=name, width=width, kind=kind)

    def subscribe(self, observer: NetObserver) -> None:
        self._observers.append(observer)

    def update(self, value: int, *, time: SimTime) -> bool:
        masked = value & self._mask
        if masked == self.value:
            return False
        self.previous = self.value
        self.value = masked
        for observer in tuple(self._observers):
            observer(self, self.previous, masked, time)
        return True

    def bit(self, index: int) -> int:
        return (self.value >> index) & 1

    def vcd_value(self) -> str:
        if self.width == 1:
            return "1" if self.bit(0) else "0"
        return "b" + format(self.value, f"0{self.width}b")
