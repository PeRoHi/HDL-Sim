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
INCLUDE_RE = re.compile(r'`include\s+"([^"]+\.v)"', re.IGNORECASE)


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


def patch_vend_for_hdl_sim(source: str) -> str:
    """Replace unsupported concat-lvalue assign with split assigns."""

    old = "assign {newspaper, NEXT_STATE} = fsm(coin, PRES_STATE);"
    new = """wire [2:0] __fsm_out;
assign __fsm_out = fsm(coin, PRES_STATE);
assign newspaper = __fsm_out[2];
assign PRES_STATE = __fsm_out[1:0];"""
    if old in source:
        return source.replace(old, new)
    return source


def discover_includes(base_dir: Path, rel_names: list[str]) -> list[str]:
    found: list[str] = []
    for rel in rel_names:
        text = read_verilog(resolve_v_file(base_dir, rel))
        for match in INCLUDE_RE.finditer(text):
            inc = match.group(1)
            if inc not in rel_names and inc not in found:
                found.append(inc)
    return found


def build_project(
    *,
    name: str,
    base_dir: Path,
    rel_names: list[str],
    top: str | None = None,
    label: str | None = None,
    include_only: set[str] | None = None,
    patchers: dict[str, str] | None = None,
) -> dict:
    include_only = include_only or set()
    patchers = patchers or {}
    auto_includes = discover_includes(base_dir, rel_names)
    ordered = list(rel_names)
    for inc in auto_includes:
        if inc not in ordered:
            ordered.append(inc)
            include_only.add(inc)

    files: list[dict[str, str | bool]] = []
    for rel in ordered:
        path = resolve_v_file(base_dir, rel)
        content = read_verilog(path)
        if rel in patchers:
            content = patchers[rel](content)
        entry: dict[str, str | bool] = {"path": path.name, "content": content}
        if (
            rel in include_only
            or path.name in include_only
            or MODULE_RE.search(content) is None
        ):
            entry["include_only"] = True
        files.append(entry)

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


# HDL-Sim で Elab/Run できる例のみ（Silos 専用 PLI/混合信号は除外）
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
        "label": "Vending machine FSM (include)",
    },
    {
        "name": "silos_gate",
        "base": LEGACY,
        "files": ["vendtest.v", "vend.v"],
        "top": "stimulus",
        "label": "Vending RTL (vend + TB)",
        "patchers": {"vend.v": patch_vend_for_hdl_sim},
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
            include_only=set(spec.get("include_only") or []),
            patchers=spec.get("patchers"),
        )
        write_spj(payload)
        written.append(payload["name"])

    for stale in ("silos_fltsim", "silos_analog"):
        stale_path = SPJ_OUT / f"{stale}.spj"
        if stale_path.is_file():
            stale_path.unlink()
            print(f"Removed unsupported {stale}.spj")

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
