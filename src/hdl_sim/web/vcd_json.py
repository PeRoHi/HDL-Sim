"""Convert VCD text to a compact JSON timeline for the waveform viewer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class VCDSignalMeta:
    code: str
    name: str
    width: int
    kind: str


@dataclass(slots=True)
class VCDTimeline:
    timescale: str
    signals: list[VCDSignalMeta]
    changes: dict[str, list[tuple[int, str]]] = field(default_factory=dict)


_VAR_RE = re.compile(
    r"^\$var\s+(wire|reg|integer|real)\s+(\d+)\s+(\S+)\s+(.+?)\s+\$end\s*$"
)
_REAL_VAL_RE = re.compile(r"^r([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(\S+)$")
_TIMESCALE_RE = re.compile(r"^\$timescale\s+(\S+)\s+\$end\s*$")
_BUS_VAL_RE = re.compile(r"^b([0-9a-zA-ZxzXZ]+)(\S+)$")


def _qualify_vcd_signal(scope_stack: list[str], short_name: str) -> str:
    """Map scoped VCD identifiers to flat net names (e.g. sai.cnt)."""

    if len(scope_stack) <= 1:
        return short_name
    return ".".join(scope_stack[1:]) + "." + short_name


def parse_vcd_timeline(vcd_text: str) -> VCDTimeline:
    """Parse VCD into signal metadata and per-code change lists."""

    timescale = "1ns"
    code_to_meta: dict[str, VCDSignalMeta] = {}
    changes: dict[str, list[tuple[int, str]]] = {}
    current_time = 0
    in_defs = True
    scope_stack: list[str] = []

    for raw_line in vcd_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$comment"):
            continue
        if line.startswith("$timescale"):
            match = _TIMESCALE_RE.match(line)
            if match:
                timescale = match.group(1)
            continue
        if line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scope_stack.append(parts[2])
            continue
        if line.startswith("$upscope"):
            if scope_stack:
                scope_stack.pop()
            continue
        if line.startswith("$enddefinitions"):
            in_defs = False
            continue
        if in_defs:
            match = _VAR_RE.match(line)
            if match:
                kind, width_s, code, name = match.groups()
                short_name = name.strip()
                full_name = _qualify_vcd_signal(scope_stack, short_name)
                meta = VCDSignalMeta(
                    code=code,
                    name=full_name,
                    width=int(width_s),
                    kind=kind,
                )
                code_to_meta[code] = meta
                changes[code] = []
            continue
        if line.startswith("#"):
            current_time = int(line[1:].split()[0])
            continue
        if line[0] == "r":
            match = _REAL_VAL_RE.match(line)
            if not match:
                continue
            value, code = match.group(1), match.group(2)
        elif line[0] in "01xXzZ":
            value = line[0]
            code = line[1:]
        elif line[0] == "b":
            match = _BUS_VAL_RE.match(line)
            if not match:
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                value, code = parts[0][1:], parts[1]
            else:
                value, code = match.group(1), match.group(2)
        else:
            continue
        if code in changes:
            changes[code].append((current_time, value))

    signals = list(code_to_meta.values())
    return VCDTimeline(timescale=timescale, signals=signals, changes=changes)


def timeline_to_json(timeline: VCDTimeline) -> dict:
    """Serialize timeline for the browser waveform panel."""

    return {
        "timescale": timeline.timescale,
        "signals": [
            {
                "code": s.code,
                "name": s.name,
                "width": s.width,
                "kind": s.kind,
                "changes": timeline.changes.get(s.code, []),
            }
            for s in timeline.signals
        ],
    }
