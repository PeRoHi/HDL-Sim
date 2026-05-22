"""Value Change Dump (VCD) writer for GTKWave."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from hdl_sim.core.events import SimTime
from hdl_sim.engine.nets import SimNet


@dataclass(slots=True)
class VCDChange:
    time: SimTime
    code: str
    value: str


@dataclass
class VCDWriter:
    """Collect signal transitions and emit a VCD file."""

    scope: str
    nets: dict[str, SimNet]
    timescale: str = "1ns"
    _codes: dict[str, str] = field(init=False, repr=False)
    _changes: list[VCDChange] = field(default_factory=list, init=False, repr=False)
    _last_dumped: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        alphabet = "!" + "".join(chr(code) for code in range(34, 127) if chr(code) not in {"!", " "})
        self._codes = {}
        index = 0
        for name in sorted(self.nets):
            if index >= len(alphabet):
                msg = "too many nets for compact VCD identifiers"
                raise ValueError(msg)
            self._codes[name] = alphabet[index]
            index += 1

    def change(self, net: SimNet, time: SimTime) -> None:
        value = net.vcd_value()
        if self._last_dumped.get(net.name) == value:
            return
        self._last_dumped[net.name] = value
        self._changes.append(VCDChange(time=time, code=self._codes[net.name], value=value))

    def dump_initial(self, time: SimTime) -> None:
        for net in self.nets.values():
            self.change(net, time)

    def render(self) -> str:
        lines = [
            f"$date {datetime.now(tz=UTC).isoformat()} $end",
            "$version HDL-Sim 0.1.0 $end",
            f"$timescale {self.timescale} $end",
            "$scope module {} $end".format(self.scope),
        ]
        for name in sorted(self.nets):
            net = self.nets[name]
            code = self._codes[name]
            lines.append(f"$var wire {net.width} {code} {name} $end")
        lines.extend(["$upscope $end", "$enddefinitions $end", "$dumpvars", "#0"])
        for name in sorted(self.nets):
            net = self.nets[name]
            lines.append(f"{net.vcd_value()}{self._codes[name]}")
        lines.append("$end")

        current_time: SimTime | None = None
        for change in self._changes:
            if change.time != current_time:
                lines.append(f"#{change.time}")
                current_time = change.time
            lines.append(f"{change.value}{change.code}")
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> None:
        path.write_text(self.render(), encoding="utf-8")
