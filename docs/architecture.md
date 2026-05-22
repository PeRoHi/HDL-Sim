# HDL-Sim architecture

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
