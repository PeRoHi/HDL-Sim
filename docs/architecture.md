# HDL-Sim architecture

## Local Web API (assume)

The browser UI is a same-origin app on loopback. Destructive and file APIs are not a public HTTP service.

- Bind / Host: `127.0.0.1` or `localhost` (or `::1`) plus the UI port (launcher default **8765**, overridable via `--port` / `HDL_SIM_UI_PORT`). Other Host values are rejected.
- If the request has an `Origin` header, it must be `http://127.0.0.1:<port>` (or localhost / `[::1]`). `Origin: null` is rejected. CORS is limited to those origins and does **not** use `*`. CORS is not authentication.
- Source paths written under `verilog_sources/` and virtual files sent to elaborate/simulate must stay inside a jail. Nested relatives such as `lib/and2.v` are allowed; `..`, absolute paths, drive letters, and symlink escapes are not.
- `$dumpfile` names a file under the simulation VCD directory (the Web UI temp workspace). Absolute / `..` dump paths are rejected when an anchor is set.
- `` `include `` files must resolve under a configured search directory.

## Pipeline

1. **前処理** — コメント除去（`parser/preprocess.py`）
2. **パース** — Lark → AST（`parser/verilog.lark`）
3. **Elaboration** — 階層フラット化、generate 展開、ポート接続（`engine/elaborator.py`, `engine/generate.py`）
4. **シミュレーション** — イベントキュー、アクティブ/NBA リージョン、デルタ（`core/events.py`, `engine/delta.py`, `engine/nba.py`）
5. **VCD** — 任意（`vcd/writer.py`）

## 主要コンポーネント

| モジュール | 役割 |
|------------|------|
| `engine/simulator.py` | エントリ、連続代入の再計算、プロセス起動 |
| `engine/executor.py` | 手続き文、`#delay`、fork、NBA スケジュール |
| `engine/nba.py` | 非ブロッキング更新の集約とフラッシュ（四値、階層 net 名） |
| `engine/logic_eval.py` | 四値式評価 |
| `engine/net_state.py` | net への四値反映 |
| `engine/elaborator.py` | グローバル net 表とスコープ付きプロセス |

## イベントと NBA

- 各シミュレーション時刻の末尾で **NBA リージョン** をフラッシュ
- 子モジュール内の `q <= ...` は、ポート接続先の **グローバル net 名**（例: `count`）にスケジュール
- 連続代入は式変更時に `eval_logic` → `apply_four_state`

## Silos 回帰例

```bash
PYTHONPATH=src python3 -m hdl_sim examples/silos_regression.v \
  --top silos_regression_tb --until 50 --max-events 500
```

`examples/silos_regression.v` は `counter` + テストベンチで、クロック・リセット・posedge カウンタ・`$display` による PASS/FAIL を確認します。

## CLI

```bash
poetry run hdl-sim examples/counter.v --until 30 -o build/counter.vcd
poetry run hdl-sim examples/hierarchy.v --until 5
poetry run hdl-sim examples/silos_regression.v --top silos_regression_tb --until 50
```
