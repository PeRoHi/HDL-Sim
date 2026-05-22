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


@dataclass(slots=True)
class _VCDScopeNode:
    name: str
    children: dict[str, _VCDScopeNode] = field(default_factory=dict)
    nets: list[str] = field(default_factory=list)


@dataclass
class VCDWriter:
    """Collect signal transitions and emit a VCD file with hierarchical scopes."""

    scope: str
    nets: dict[str, SimNet]
    timescale: str = "1ns"
    _codes: dict[str, str] = field(init=False, repr=False)
    _changes: list[VCDChange] = field(default_factory=list, init=False, repr=False)
    _last_dumped: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _scope_root: _VCDScopeNode = field(init=False, repr=False)
    _active_nets: frozenset[str] | None = field(default=None, init=False, repr=False)

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
        self._scope_root = _build_scope_tree(self.scope, sorted(self.nets))

    def set_active_nets(self, names: frozenset[str]) -> None:
        self._active_nets = names

    def change(self, net: SimNet, time: SimTime) -> None:
        if self._active_nets is not None and net.name not in self._active_nets:
            return
        value = net.vcd_value()
        if self._last_dumped.get(net.name) == value:
            return
        self._last_dumped[net.name] = value
        self._changes.append(VCDChange(time=time, code=self._codes[net.name], value=value))

    def dump_initial(self, time: SimTime) -> None:
        targets = self.nets.values()
        if self._active_nets is not None:
            targets = (self.nets[n] for n in self._active_nets if n in self.nets)
        for net in targets:
            self.change(net, time)

    def render(self) -> str:
        lines = [
            f"$date {datetime.now(tz=UTC).isoformat()} $end",
            "$version HDL-Sim 0.2.0 $end",
            f"$timescale {self.timescale} $end",
        ]
        _emit_scope(lines, self._scope_root, self.nets, self._codes)
        lines.extend(["$enddefinitions $end", "$dumpvars", "#0"])
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


def _build_scope_tree(top: str, net_names: list[str]) -> _VCDScopeNode:
    root = _VCDScopeNode(name=top)
    for full_name in net_names:
        if "." not in full_name:
            root.nets.append(full_name)
            continue
        parts = full_name.split(".")
        node = root
        for part in parts[:-1]:
            if part not in node.children:
                node.children[part] = _VCDScopeNode(name=part)
            node = node.children[part]
        node.nets.append(full_name)
    return root


def _emit_scope(
    lines: list[str],
    node: _VCDScopeNode,
    nets: dict[str, SimNet],
    codes: dict[str, str],
) -> None:
    lines.append(f"$scope module {node.name} $end")
    for child in sorted(node.children.values(), key=lambda item: item.name):
        _emit_scope(lines, child, nets, codes)
    for net_name in sorted(node.nets):
        net = nets[net_name]
        code = codes[net_name]
        lines.append(f"$var wire {net.width} {code} {net_name.split('.')[-1]} $end")
    lines.append("$upscope $end")
