# HDL-Sim architecture

HDL-Sim is a lightweight, event-driven Verilog HDL simulator that emits VCD
files for waveform viewers such as GTKWave.

## Directory layout

```text
hdl-sim/
├── pyproject.toml
├── docs/
│   └── architecture.md
├── examples/
│   ├── clock.v
│   └── and_gate.v
├── src/
│   └── hdl_sim/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── core/
│       │   ├── events.py
│       │   └── signals.py
│       ├── parser/
│       │   ├── ast.py
│       │   ├── verilog.lark
│       │   ├── parser.py
│       │   └── preprocess.py
│       ├── engine/
│       │   ├── nets.py
│       │   ├── evaluator.py
│       │   ├── executor.py
│       │   ├── expr_deps.py
│       │   └── simulator.py
│       └── vcd/
│           └── writer.py
└── tests/
    ├── test_core.py
    ├── test_parser.py
    └── test_simulation.py
```

## Parser library

**Lark 1.2.2** is used for the Verilog subset grammar.

```bash
poetry add lark==1.2.2
```

Reasons: EBNF grammars, LALR mode, built-in tree transformers, pure Python, Python 3.12 compatible.

## Supported Verilog subset (MVP)

- `module` / `endmodule`
- `reg` / `wire` declarations (optional vector range)
- `assign` continuous assignments
- `initial` / `always` blocks with `begin` / `end`
- blocking `=` and non-blocking `<=` assignments
- `#delay` event controls
- `forever`, `repeat`, `if` / `else`
- `@(posedge/negedge signal)` and `@(*)`
- Expression operators: `~`, `&`, `|`, `^`, `+`, `-`, `*`, comparisons, `?:`

## Simulation pipeline

1. Preprocess comments (`parser/preprocess.py`)
2. Parse to AST (`parser/parser.py` + `verilog.lark`)
3. Build netlist (`engine/nets.py`)
4. Register continuous assigns (`engine/simulator.py`)
5. Spawn `initial` / `always` processes (`engine/executor.py`)
6. Run `EventQueue` until `until` / `max_events` / queue empty
7. Optional VCD dump (`vcd/writer.py`)

## CLI

```bash
poetry install
poetry run hdl-sim examples/clock.v --until 20 --max-events 100 -o build/clock.vcd
```

Or:

```bash
PYTHONPATH=src python3 -m hdl_sim examples/clock.v --until 20
```
