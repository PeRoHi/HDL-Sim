#!/usr/bin/env python3
"""Convert Silos-style .spj under examples/ into HDL-Sim JSON projects in ./spj/."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "examples"
LEGACY = EXAMPLES / "新しいフォルダー"
SPJ_OUT = ROOT / "spj"

MODULE_RE = re.compile(r"^\s*module\s+(\w+)", re.MULTILINE | re.IGNORECASE)


def resolve_v_file(base: Path, name: str) -> Path:
    direct = base / name
    if direct.is_file():
        return direct
    want = name.lower()
    for entry in base.iterdir():
        if entry.suffix.lower() == ".v" and entry.name.lower() == want:
            return entry
    msg = f"Verilog file not found: {name} in {base}"
    raise FileNotFoundError(msg)


def read_verilog(path: Path) -> str:
    for encoding in ("utf-8", "cp932", "shift_jis", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def module_name(path: Path) -> str:
    match = MODULE_RE.search(read_verilog(path))
    if match:
        return match.group(1)
    return path.stem


def parse_silos_files(text: str) -> list[str]:
    names: list[str] = []
    in_files = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[Files]":
            in_files = True
            continue
        if stripped.startswith("[") and in_files:
            break
        if not in_files:
            continue
        quoted = re.search(r'"([^"]+\.v)"', line, re.IGNORECASE)
        if quoted:
            names.append(quoted.group(1))
            continue
        bare = re.search(r"=\s*([A-Za-z0-9_./-]+\.v)\s*$", line, re.IGNORECASE)
        if bare:
            names.append(bare.group(1))
    return names


def build_project(
    *,
    name: str,
    base_dir: Path,
    rel_names: list[str],
    top: str | None = None,
    label: str | None = None,
) -> dict:
    files: list[dict[str, str]] = []
    for rel in rel_names:
        path = resolve_v_file(base_dir, rel)
        files.append({"path": path.name, "content": read_verilog(path)})
    if top is None:
        top = module_name(resolve_v_file(base_dir, rel_names[0]))
    payload: dict = {
        "format": "hdl-sim-project",
        "version": 1,
        "name": name,
        "top": top,
        "files": files,
    }
    if label:
        payload["label"] = label
    return payload


# Explicit tops from docs/tests; Silos [Files] order preserved.
PROJECTS: list[dict] = [
    {
        "name": "saikoro",
        "base": EXAMPLES,
        "files": ["saitest.v", "sai.v"],
        "top": "sai_test",
        "label": "サイコロ (sai + saitest)",
    },
    {
        "name": "test4add",
        "base": EXAMPLES,
        "files": ["4addtest.v", "4add.v"],
        "top": "mul_ts",
        "label": "4-bit adder",
    },
    {
        "name": "testcounter",
        "base": EXAMPLES,
        "files": ["counter_reset_tp.v", "couter_reset.v"],
        "top": "counter_reset_tp",
        "label": "Counter with reset",
    },
    {
        "name": "testDFF",
        "base": EXAMPLES,
        "files": ["DFF_TST.v", "DFF.v"],
        "top": "DFF_tp",
        "label": "DFF testbench",
    },
    {
        "name": "testTFF",
        "base": EXAMPLES,
        "files": ["tff_TST.v", "tff.v"],
        "top": "TFF_tp",
        "label": "TFF testbench",
    },
    {
        "name": "watch",
        "base": EXAMPLES,
        "files": ["watch_test.v", "watch.v"],
        "top": "DFF_tp",
        "label": "Watch / state decoder",
    },
    {
        "name": "silos_code_coverage",
        "base": LEGACY,
        "files": ["testbench.v", "code_coverage.v"],
        "top": "testbench",
        "label": "Code coverage sample 1",
    },
    {
        "name": "silos_code_coverage2",
        "base": LEGACY,
        "files": ["testbench2.v", "code_coverage.v"],
        "top": "testbench",
        "label": "Code coverage sample 2",
    },
    {
        "name": "silos_vending",
        "base": LEGACY,
        "files": ["vending_testbench.v"],
        "top": "stimulus",
        "label": "Vending machine TB (include)",
    },
    {
        "name": "silos_gate",
        "base": LEGACY,
        "files": ["vendtest.v"],
        "top": "stimulus",
        "label": "Gate / vendtest stimulus",
    },
    {
        "name": "silos_fltsim",
        "base": LEGACY,
        "files": ["faulttst.v"],
        "top": "fault_strobe",
        "label": "Fault sim fragment (PLI)",
    },
    {
        "name": "silos_analog",
        "base": LEGACY,
        "files": ["analog.v"],
        "top": None,
        "label": "Analog/mixed (Silos; limited sim support)",
    },
]


def write_spj(payload: dict) -> Path:
    SPJ_OUT.mkdir(parents=True, exist_ok=True)
    path = SPJ_OUT / f"{payload['name']}.spj"
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    written: list[str] = []
    for spec in PROJECTS:
        payload = build_project(
            name=spec["name"],
            base_dir=spec["base"],
            rel_names=spec["files"],
            top=spec.get("top"),
            label=spec.get("label"),
        )
        write_spj(payload)
        written.append(payload["name"])

    # Remove Silos .spj left under examples (HDL-Sim uses ./spj/ only).
    removed = 0
    for old in EXAMPLES.rglob("*.spj"):
        old.unlink()
        removed += 1

    print(f"Wrote {len(written)} projects to {SPJ_OUT}")
    for name in written:
        print(f"  - {name}.spj")
    print(f"Removed {removed} legacy .spj file(s) from examples/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
