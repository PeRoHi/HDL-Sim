# Imported legacy Verilog examples

`cursor/dev-ui-9db8` から取り込まれた古い Silos 系 `.v` サンプルの動作状況です。

## 動作確認済み

以下は `load_design_with_meta` で読み込み、`simulate_files` で実行できることを回帰テストしています。

| 例 | ファイル | Top | 備考 |
|----|----------|-----|------|
| 4-bit adder | `examples/examples/4add.v`, `4addtest.v` | `mul_ts` | `#STEP`, `%h`, `$stime` |
| DFF | `DFF.v`, `DFF_TST.v` | `DFF_tp` | CP932 読み込み |
| reset counter | `couter_reset.v`, `counter_reset_tp.v` | `counter_reset_tp` | CP932 読み込み |
| sai dice | `sai.v`, `saitest.v` | `sai_test` | function, 階層 monitor `sai.cnt` |
| TFF | `tff.v`, `tff_TST.v` | `TFF_tp` | ternary |
| watch state decoder | `watch.v`, `watch_test.v` | `DFF_tp` | multi-parameter declarations |
| code coverage sample 1 | `code_coverage.v`, `testbench.v` | `testbench` | tool directive ignored |
| code coverage sample 2 | `code_coverage.v`, `testbench2.v` | `testbench` | tool directive ignored |
| vending include FSM | `vending_testbench.v` | `stimulus` | `include`, initialized wire, fork statement list |

## 読み込み対応を追加した構文/挙動

- UTF-8 / CP932 / Shift-JIS の Verilog 読み込み
- `parameter A=..., B=...;` の複数宣言
- `wire x = expr;` 形式の初期化付きネット宣言（declaration + continuous assign）
- `always begin ... end` の forever プロセス扱い
- `fork #10 a=...; #20 b=...; join` 形式
- `$time` / `$stime`
- `%b` / `%h` / `%d` 表示フォーマット
- 未知の vendor/PLI system task は無視（例: `$sdf_annotate`）
- `disable_codecoverage` / `enable_codecoverage` などのツール directive を無視

## 現状対象外

以下はファイル自体が断片、意図的エラー、または本シミュレータの範囲外です。

| ファイル | 理由 |
|----------|------|
| `examples/lib/clk_gen.v` | module ではなく include 用 fragment |
| `examples/examples/新しいフォルダー/abc_100.v` | gate primitive / `specify` timing library |
| `examples/examples/新しいフォルダー/analog.v` | Silos analog switch、real nets、UDP など mixed-signal |
| `examples/examples/新しいフォルダー/design.v` | Actel gate-level netlist + tool directives/primitives |
| `examples/examples/新しいフォルダー/faulttst.v` | fault-sim PLI (`$fs_strobe`) 向け断片 |
| `examples/examples/新しいフォルダー/vend.v` | concat lvalue continuous assign (`assign {a,b}=...`) は未対応 |
| `examples/examples/新しいフォルダー/venderr.v` | 教材上の意図的な文法エラー（module header の `;` 欠落） |
| `examples/examples/新しいフォルダー/vending.v` | include 断片（単体 module ではない）。`vending_testbench.v` 経由なら動作確認済み |
