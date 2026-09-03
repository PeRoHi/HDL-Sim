"""Netlist signal storage for multi-bit values and unpacked memories."""

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
    real_value: float = 0.0
    x_mask: int = 0
    z_mask: int = 0
    previous: int | None = None
    is_signed: bool = False
    memory: list[int] = field(default_factory=list)
    memory_x_mask: list[int] = field(default_factory=list, repr=False)
    memory_z_mask: list[int] = field(default_factory=list, repr=False)
    _observers: list[NetObserver] = field(default_factory=list, repr=False)
    _mask: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.width < 1:
            msg = "net width must be positive"
            raise ValueError(msg)
        object.__setattr__(self, "_mask", (1 << self.width) - 1)
        if self.is_memory:
            if not self.memory:
                msg = "memory net requires at least one word"
                raise ValueError(msg)
            self.memory = [w & self._mask for w in self.memory]
            if not self.memory_x_mask:
                self.memory_x_mask = [0] * len(self.memory)
            if not self.memory_z_mask:
                self.memory_z_mask = [0] * len(self.memory)
            self.memory_x_mask = [x & self._mask for x in self.memory_x_mask]
            self.memory_z_mask = [z & self._mask for z in self.memory_z_mask]
            self.value = self.memory[0]
        else:
            self.value &= self._mask
            self.x_mask &= self._mask
            self.z_mask &= self._mask

    @property
    def is_memory(self) -> bool:
        return bool(self.memory)

    @classmethod
    def from_declaration(
        cls,
        name: str,
        kind: DeclKind,
        value_range: Range | None,
        *,
        unpacked_range: Range | None = None,
        is_signed: bool = False,
    ) -> SimNet:
        if kind is DeclKind.INTEGER:
            width = value_range.width if value_range is not None else 32
        elif kind is DeclKind.REAL:
            width = 64
        else:
            width = value_range.width if value_range is not None else 1
        memory: list[int] = []
        if unpacked_range is not None:
            depth = unpacked_range.width
            memory = [0] * depth
        return cls(
            name=name,
            width=width,
            kind=kind,
            is_signed=is_signed,
            memory=memory,
        )

    def subscribe(self, observer: NetObserver) -> None:
        self._observers.append(observer)

    def _notify(self, previous: int, masked: int, time: SimTime) -> None:
        for observer in tuple(self._observers):
            observer(self, previous, masked, time)

    def update(
        self,
        value: int,
        *,
        time: SimTime,
        x_mask: int | None = None,
        z_mask: int | None = None,
    ) -> bool:
        if self.is_memory:
            msg = "use update_word for memory nets"
            raise ValueError(msg)
        masked = value & self._mask
        next_x = (x_mask if x_mask is not None else self.x_mask) & self._mask
        next_z = (z_mask if z_mask is not None else self.z_mask) & self._mask
        if masked == self.value and next_x == self.x_mask and next_z == self.z_mask:
            return False
        self.previous = self.value
        self.value = masked
        self.x_mask = next_x
        self.z_mask = next_z
        self._notify(self.previous, masked, time)
        return True

    def read_word(self, index: int) -> int:
        if not self.is_memory:
            return self.value
        return self.memory[index] & self._mask

    def update_word(
        self,
        index: int,
        value: int,
        *,
        time: SimTime,
        x_mask: int | None = None,
        z_mask: int | None = None,
    ) -> bool:
        if not self.is_memory:
            return self.update(value, time=time, x_mask=x_mask, z_mask=z_mask)
        masked = value & self._mask
        next_x = (x_mask if x_mask is not None else self.memory_x_mask[index]) & self._mask
        next_z = (z_mask if z_mask is not None else self.memory_z_mask[index]) & self._mask
        prev = self.memory[index]
        if masked == prev and next_x == self.memory_x_mask[index] and next_z == self.memory_z_mask[index]:
            return False
        self.previous = prev
        self.memory[index] = masked
        self.memory_x_mask[index] = next_x
        self.memory_z_mask[index] = next_z
        if index == 0:
            self.value = masked
            self.x_mask = next_x
            self.z_mask = next_z
        self._notify(prev, masked, time)
        return True

    def bit(self, index: int) -> int:
        return (self.value >> index) & 1

    def word_bit(self, word_index: int, bit_index: int) -> int:
        return (self.read_word(word_index) >> bit_index) & 1

    def vcd_value(self) -> str:
        if self.kind is DeclKind.REAL:
            return f"r{self.real_value:g}"
        if self.width == 1:
            if self.x_mask & 1:
                return "x"
            if self.z_mask & 1:
                return "z"
            return "1" if self.bit(0) else "0"
        chars = []
        for index in range(self.width - 1, -1, -1):
            bit = 1 << index
            if self.x_mask & bit:
                chars.append("x")
            elif self.z_mask & bit:
                chars.append("z")
            else:
                chars.append("1" if self.value & bit else "0")
        return "b" + "".join(chars)
