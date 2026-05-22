# HDL-Sim architecture

## Pipeline

1. Preprocess comments
2. Parse to AST (Lark, multi-module)
3. Elaborate hierarchy (`engine/elaborator.py`)
4. Simulate with active/NBA regions (`core/events.py`, `engine/nba.py`)
5. Optional VCD output

## New in this iteration

- **NBA region**: non-blocking `<=` updates flush after each time step
- **Edge-sensitive `always`**: `@(posedge clk)` / `@(negedge rst)` detection
- **Hierarchy**: module ports, instances, named port connections (`.a(sig)`)
- **Examples**: `examples/counter.v`, `examples/hierarchy.v`

## CLI

```bash
poetry run hdl-sim examples/counter.v --until 30 -o build/counter.vcd
poetry run hdl-sim examples/hierarchy.v --until 5
```
